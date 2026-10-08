"""
Aspect extraction module.

Strategy
--------
- Entirely config-driven: all category names, aspect names, and trigger
  patterns come from the ``aspect_config`` section of the domain YAML.
  No aspect names appear in this file.
- One compiled regex per (category, aspect) pair (alternation of all patterns).
- For each match, the clause containing the match is extracted and scored with
  the sentiment analyser — NOT the whole review.  This gives aspect-level
  sentiment that can differ from the review-level score.
- Text is first split on adversative conjunctions (but, however, although,
  though, yet, while, whereas) so that "fast charging BUT range dropped"
  correctly scores charging-clause as positive and range-clause as negative.
- A review can match many (category, aspect) pairs; each yields one
  AspectMatch.  Within a single review, only the *first* match per
  (category, aspect) key is kept to avoid trivial duplicates.
- All exceptions are caught and logged; a failed aspect never stops the batch.

Canonical example (must always hold with the lexicon analyser)
--------------------------------------------------------------
Input : "Charging is extremely fast but the battery range has dropped after
         two years"
Output:
  charging / charging_speed  → positive  (clause: "Charging is extremely fast")
  range    / range_loss      → negative  (clause: "battery range has dropped …")
  battery  / battery_health  → negative  (clause: "battery range has dropped …")
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

_MATCHED_MAX = 500

# Adversative / contrastive conjunctions that split a sentence into clauses
# with potentially opposing sentiment.
_CLAUSE_SPLIT = re.compile(
    r"\s+(?:but|however|although|though|yet|while|whereas|despite|even though"
    r"|nevertheless|on the other hand|that said)\s+",
    re.IGNORECASE,
)


# ── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class AspectMatch:
    category:        str
    aspect:          str
    sentiment_label: Optional[str]
    sentiment_score: Optional[float]
    confidence:      Optional[float]
    matched_text:    Optional[str]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _split_clauses(text: str) -> list[tuple[int, str]]:
    """
    Split *text* on adversative conjunctions.

    Returns a list of (start_offset, clause_text) tuples so that we can map a
    character position in the original text back to the clause it belongs to.
    """
    clauses: list[tuple[int, str]] = []
    prev_end = 0
    for m in _CLAUSE_SPLIT.finditer(text):
        clauses.append((prev_end, text[prev_end: m.start()]))
        prev_end = m.end()
    clauses.append((prev_end, text[prev_end:]))
    return clauses


def _clause_for_match(text: str, match: re.Match) -> str:
    """
    Return the clause that contains the match position.
    Falls back to the full text if no clauses are found.
    """
    clauses = _split_clauses(text)
    if len(clauses) == 1:
        return text.strip()[:_MATCHED_MAX]

    pos = match.start()
    for start, clause in clauses:
        clause_end = start + len(clause)
        if start <= pos < clause_end:
            return clause.strip()[:_MATCHED_MAX]

    # Fallback: return the last clause
    return clauses[-1][1].strip()[:_MATCHED_MAX]


# ── Core extractor class ─────────────────────────────────────────────────────

class AspectExtractor:
    """
    Extracts aspect mentions from text using config-driven regex patterns and
    scores each matched clause with a SentimentAnalyzer.

    Parameters
    ----------
    aspect_config : dict loaded from domain YAML ``aspect_config`` section.
    sentiment_analyzer : any SentimentAnalyzer.  If None, the module-level
        singleton is used (lazy-initialised on first call).
    """

    def __init__(
        self,
        aspect_config: dict[str, Any],
        sentiment_analyzer: Any = None,
    ) -> None:
        self._config    = aspect_config
        self._sentiment = sentiment_analyzer
        # Map (category, aspect) → compiled regex
        self._patterns: dict[tuple[str, str], re.Pattern[str]] = {}
        self._compile()

    # ── Setup ────────────────────────────────────────────────

    def _compile(self) -> None:
        for category, aspects in self._config.items():
            if not isinstance(aspects, dict):
                continue
            for aspect_name, aspect_cfg in aspects.items():
                if not isinstance(aspect_cfg, dict):
                    continue
                raw_patterns: list[str] = aspect_cfg.get("patterns", [])
                if not raw_patterns:
                    continue
                alternation = "|".join(f"(?:{p})" for p in raw_patterns)
                try:
                    self._patterns[(category, aspect_name)] = re.compile(
                        alternation, re.IGNORECASE | re.DOTALL
                    )
                except re.error as exc:
                    logger.warning(
                        "Skipping bad pattern for %s/%s: %s",
                        category, aspect_name, exc,
                    )

    def _get_analyzer(self) -> Any:
        if self._sentiment is None:
            from backend.nlp.sentiment import get_sentiment_analyzer
            self._sentiment = get_sentiment_analyzer()
        return self._sentiment

    # ── Public API ───────────────────────────────────────────

    def extract(
        self,
        text: str | None,
        title: str | None = None,
    ) -> list[AspectMatch]:
        """
        Scan *title* + *text* for aspect mentions.

        Returns a list of AspectMatch objects — one per matched
        (category, aspect) pair, de-duplicated within this call.
        """
        if not text and not title:
            return []

        combined = " ".join(filter(None, [title, text]))
        analyzer  = self._get_analyzer()
        results:  list[AspectMatch] = []
        seen:     set[tuple[str, str]] = set()

        for (category, aspect_name), pattern in self._patterns.items():
            key = (category, aspect_name)
            if key in seen:
                continue

            match = pattern.search(combined)
            if match is None:
                continue

            seen.add(key)

            # Extract the clause that contains this match (not the whole text)
            context = _clause_for_match(combined, match)

            sent_label: Optional[str]   = None
            sent_score: Optional[float] = None
            confidence: Optional[float] = None

            if context:
                try:
                    result      = analyzer.analyze(context)
                    sent_label  = result.label
                    sent_score  = result.score
                    confidence  = result.confidence
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "Sentiment failed for aspect %s/%s: %s",
                        category, aspect_name, exc,
                    )

            results.append(
                AspectMatch(
                    category        = category,
                    aspect          = aspect_name,
                    sentiment_label = sent_label,
                    sentiment_score = sent_score,
                    confidence      = confidence,
                    matched_text    = (context[:_MATCHED_MAX] if context else None),
                )
            )

        return results


# ── Module-level singleton factory ───────────────────────────────────────────

_EXTRACTOR: Optional[AspectExtractor] = None


def get_aspect_extractor(
    aspect_config: dict[str, Any] | None = None,
    sentiment_analyzer: Any = None,
) -> AspectExtractor:
    """
    Return the shared AspectExtractor for this process.

    Pass *aspect_config* explicitly to override the YAML default (useful in
    tests).  Passing *sentiment_analyzer* forces a specific analyser instance.
    """
    global _EXTRACTOR

    # Always rebuild when overrides are supplied (test scenario)
    if aspect_config is not None or sentiment_analyzer is not None:
        return AspectExtractor(
            aspect_config      = aspect_config or {},
            sentiment_analyzer = sentiment_analyzer,
        )

    if _EXTRACTOR is not None:
        return _EXTRACTOR

    # Load from YAML
    from backend.api.domain_config import _load_yaml, list_available_domains
    domains = list_available_domains()
    if not domains:
        logger.warning("No domain configs found — aspect extractor will be empty.")
        raw_cfg: dict[str, Any] = {}
    else:
        raw_cfg = _load_yaml(domains[0]).get("aspect_config", {})

    _EXTRACTOR = AspectExtractor(aspect_config=raw_cfg)
    return _EXTRACTOR


def reset_aspect_extractor() -> None:
    """Reset the cached singleton (tests only)."""
    global _EXTRACTOR
    _EXTRACTOR = None
