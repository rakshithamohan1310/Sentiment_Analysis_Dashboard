"""
Sentiment analysis module.

Architecture
------------
SentimentResult          – plain dataclass returned by every analyser.
SentimentAnalyzer        – abstract interface; implementations are swappable.
LexiconSentimentAnalyzer – rule-based fallback; zero extra dependencies.
TransformerSentimentAnalyzer – HuggingFace text-classification pipeline.
get_sentiment_analyzer() – process-level factory; caches a single instance.
reset_sentiment_analyzer() – resets the cache (tests only).

Label contract
--------------
All implementations return exactly one of: "positive" | "neutral" | "negative".
Callers must frame results as "customer-reported … sentiment signal", never as
a confirmed engineering defect or confirmed product quality claim.

Model name
----------
Controlled entirely by the SENTIMENT_MODEL environment variable / settings.
Set SENTIMENT_MODEL=lexicon to bypass the transformer entirely (useful in CI
or environments without torch).
"""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ── Canonical output labels ──────────────────────────────────────────────────
POSITIVE = "positive"
NEUTRAL  = "neutral"
NEGATIVE = "negative"
_VALID_LABELS = {POSITIVE, NEUTRAL, NEGATIVE}


# ── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class SentimentResult:
    label:      str    # "positive" | "neutral" | "negative"
    score:      float  # probability / strength of the predicted label [0, 1]
    confidence: float  # same as score for single-label models


# ── Abstract interface ────────────────────────────────────────────────────────

class SentimentAnalyzer(ABC):
    """All implementations must be safe to call from multiple coroutines."""

    @abstractmethod
    def analyze(self, text: str) -> SentimentResult: ...

    def analyze_batch(self, texts: list[str]) -> list[SentimentResult]:
        """Default: sequential map. Subclasses may batch for efficiency."""
        return [self.analyze(t) for t in texts]


# ── Lexicon-based fallback ────────────────────────────────────────────────────
# The word lists are deliberately small and generic — they are only used when
# the transformer model is unavailable, not as a production accuracy target.

_POS_WORDS = frozenset({
    "good", "great", "excellent", "perfect", "amazing", "awesome", "fantastic",
    "love", "best", "wonderful", "brilliant", "outstanding", "superb", "happy",
    "pleased", "impressed", "recommend", "fast", "reliable", "efficient",
    "smooth", "easy", "better", "improved", "works", "liked", "satisfied",
    "incredible", "impressive", "enjoyable", "convenient",
})
_NEG_WORDS = frozenset({
    "bad", "terrible", "awful", "horrible", "worst", "hate", "poor", "broken",
    "failed", "failure", "problem", "issue", "error", "wrong", "disappointing",
    "disappointed", "useless", "slow", "unreliable", "annoying", "frustrating",
    "frustrated", "expensive", "overpriced", "dead", "defective", "degradation",
    "degraded", "dropped", "declined", "lost", "missing", "concerned", "worried",
    "regret", "regretted", "stuck", "stranded", "shocking", "unacceptable",
})
_NEG_WORDS_EXTRA = frozenset({
    "has dropped", "have dropped", "dropping", "dropped after",
    "range has dropped", "fallen", "reduced",
})
_NEGATION = frozenset({"not", "no", "never", "without", "n't", "cannot", "cant"})


class LexiconSentimentAnalyzer(SentimentAnalyzer):
    """
    Negation-aware lexicon scorer.

    Scans tokens left-to-right; a negation word flips the polarity of the
    *next* sentiment word encountered.
    """

    def analyze(self, text: str) -> SentimentResult:
        if not text or not text.strip():
            return SentimentResult(label=NEUTRAL, score=0.5, confidence=0.5)

        tl = text.lower()

        # Check multi-word negative signals first
        extra_neg = sum(1 for phrase in _NEG_WORDS_EXTRA if phrase in tl)

        tokens = re.findall(r"\b\w+\b", tl)
        pos = neg = 0
        negate = False

        for tok in tokens:
            if tok in _NEGATION:
                negate = True
                continue
            if tok in _POS_WORDS:
                neg += 1 if negate else 0
                pos += 0 if negate else 1
                negate = False
            elif tok in _NEG_WORDS:
                pos += 1 if negate else 0
                neg += 0 if negate else 1
                negate = False
            else:
                negate = False

        neg += extra_neg
        total = pos + neg

        if total == 0:
            return SentimentResult(label=NEUTRAL, score=0.5, confidence=0.5)

        ratio_pos = pos / total
        ratio_neg = neg / total

        if ratio_pos > 0.55:
            s = round(min(0.5 + ratio_pos * 0.5, 0.99), 4)
            return SentimentResult(label=POSITIVE, score=s, confidence=s)
        if ratio_neg > 0.55:
            s = round(min(0.5 + ratio_neg * 0.5, 0.99), 4)
            return SentimentResult(label=NEGATIVE, score=s, confidence=s)
        return SentimentResult(label=NEUTRAL, score=0.5, confidence=0.5)


# ── Transformer-based analyser ────────────────────────────────────────────────

# Map raw model label strings to our canonical set.
# cardiffnlp/twitter-roberta-base-sentiment-latest uses LABEL_0/1/2.
_LABEL_MAP: dict[str, str] = {
    "label_0": NEGATIVE, "label_1": NEUTRAL, "label_2": POSITIVE,
    "negative": NEGATIVE, "neutral":  NEUTRAL, "positive": POSITIVE,
    "neg": NEGATIVE,      "neu":      NEUTRAL,  "pos":      POSITIVE,
}


def _norm_label(raw: str) -> str:
    return _LABEL_MAP.get(raw.lower(), NEUTRAL)


class TransformerSentimentAnalyzer(SentimentAnalyzer):
    """
    HuggingFace text-classification pipeline wrapper.

    - Lazy-loads the model on first call.
    - Truncates input to 512 tokens.
    - Falls back to LexiconSentimentAnalyzer on any load or inference error.
    - A failed inference for one text never propagates to callers.
    """

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._pipe = None
        self._fallback = LexiconSentimentAnalyzer()
        self._load_failed = False

    def _load(self) -> None:
        if self._pipe is not None or self._load_failed:
            return
        try:
            from transformers import pipeline  # type: ignore[import]
            self._pipe = pipeline(
                "text-classification",
                model=self._model_name,
                tokenizer=self._model_name,
                top_k=None,
                truncation=True,
                max_length=512,
                device=-1,  # CPU
            )
            logger.info("Sentiment model loaded: %s", self._model_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Could not load sentiment model %r: %s — using lexicon fallback.",
                self._model_name, exc,
            )
            self._load_failed = True

    def analyze(self, text: str) -> SentimentResult:
        self._load()
        if self._pipe is None:
            return self._fallback.analyze(text)
        try:
            raw = self._pipe(text[:2000])
            # pipeline returns list[list[dict]] when top_k=None
            labels: list[dict] = raw[0] if isinstance(raw[0], list) else raw
            best = max(labels, key=lambda x: x["score"])
            label = _norm_label(best["label"])
            score = round(float(best["score"]), 4)
            return SentimentResult(label=label, score=score, confidence=score)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Transformer inference error: %s — using fallback.", exc)
            return self._fallback.analyze(text)


# ── Process-level singleton factory ──────────────────────────────────────────

_INSTANCE: Optional[SentimentAnalyzer] = None


def get_sentiment_analyzer(model_name: str | None = None) -> SentimentAnalyzer:
    """
    Return the shared SentimentAnalyzer instance for this process.

    ``model_name="lexicon"`` (or ``SENTIMENT_MODEL=lexicon``) always returns
    the lightweight LexiconSentimentAnalyzer without any download.
    """
    global _INSTANCE
    if _INSTANCE is not None:
        return _INSTANCE

    from backend.config.settings import get_settings
    name = model_name if model_name is not None else get_settings().sentiment_model

    if name.lower() == "lexicon":
        _INSTANCE = LexiconSentimentAnalyzer()
        logger.info("Using lexicon-based sentiment analyser.")
    else:
        _INSTANCE = TransformerSentimentAnalyzer(name)

    return _INSTANCE


def reset_sentiment_analyzer() -> None:
    """Reset the cached singleton. Used in tests to swap implementations."""
    global _INSTANCE
    _INSTANCE = None
