"""Tests for backend/nlp/sentiment.py"""
from __future__ import annotations

import os
import pytest

# Force lexicon for all tests — never download a transformer
os.environ["SENTIMENT_MODEL"] = "lexicon"

from backend.nlp.sentiment import (
    NEGATIVE,
    NEUTRAL,
    POSITIVE,
    LexiconSentimentAnalyzer,
    SentimentResult,
    TransformerSentimentAnalyzer,
    get_sentiment_analyzer,
    reset_sentiment_analyzer,
)


# ── LexiconSentimentAnalyzer ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_singleton():
    reset_sentiment_analyzer()
    yield
    reset_sentiment_analyzer()


def test_lexicon_positive():
    a = LexiconSentimentAnalyzer()
    r = a.analyze("Great battery life, excellent performance, love it")
    assert r.label == POSITIVE
    assert r.score > 0.5


def test_lexicon_negative():
    a = LexiconSentimentAnalyzer()
    r = a.analyze("Terrible failure, broken and useless, very disappointing")
    assert r.label == NEGATIVE
    assert r.score > 0.5


def test_lexicon_neutral_empty():
    a = LexiconSentimentAnalyzer()
    r = a.analyze("")
    assert r.label == NEUTRAL


def test_lexicon_neutral_no_sentiment_words():
    a = LexiconSentimentAnalyzer()
    r = a.analyze("The car has four wheels and a battery")
    assert r.label == NEUTRAL


def test_lexicon_negation_flips_positive():
    a = LexiconSentimentAnalyzer()
    # "not good" should score negatively
    r = a.analyze("This is not good at all")
    assert r.label in (NEGATIVE, NEUTRAL)


def test_lexicon_negation_flips_negative():
    a = LexiconSentimentAnalyzer()
    r = a.analyze("This is not bad at all actually")
    # Should be positive or neutral after negation
    assert r.label in (POSITIVE, NEUTRAL)


def test_lexicon_result_has_required_fields():
    a = LexiconSentimentAnalyzer()
    r = a.analyze("Good battery")
    assert isinstance(r, SentimentResult)
    assert r.label in {POSITIVE, NEUTRAL, NEGATIVE}
    assert 0.0 <= r.score <= 1.0
    assert 0.0 <= r.confidence <= 1.0


def test_lexicon_range_has_dropped():
    """'range has dropped' must score as negative (multi-word pattern check)."""
    a = LexiconSentimentAnalyzer()
    r = a.analyze("The battery range has dropped significantly after two years")
    assert r.label == NEGATIVE


def test_lexicon_batch():
    a = LexiconSentimentAnalyzer()
    texts = ["Great performance", "Terrible failure", "The car exists"]
    results = a.analyze_batch(texts)
    assert len(results) == 3
    assert results[0].label == POSITIVE
    assert results[1].label == NEGATIVE


# ── TransformerSentimentAnalyzer (model load failure → lexicon fallback) ──────

def test_transformer_falls_back_to_lexicon_on_bad_model():
    """A bad model name must fall back to lexicon, not raise."""
    analyzer = TransformerSentimentAnalyzer("this-model-does-not-exist/nowhere")
    # Should not raise — falls back to lexicon
    r = analyzer.analyze("Great charging speed and excellent reliability")
    assert isinstance(r, SentimentResult)
    assert r.label in {POSITIVE, NEUTRAL, NEGATIVE}


def test_transformer_fallback_gives_sensible_result():
    analyzer = TransformerSentimentAnalyzer("this-model-does-not-exist/nowhere")
    r = analyzer.analyze("Broken charger, failed three times, terrible experience")
    assert r.label in {NEGATIVE, NEUTRAL}   # lexicon fallback


# ── Factory ───────────────────────────────────────────────────────────────────

def test_get_sentiment_analyzer_lexicon():
    a = get_sentiment_analyzer("lexicon")
    assert isinstance(a, LexiconSentimentAnalyzer)


def test_get_sentiment_analyzer_cached():
    a1 = get_sentiment_analyzer("lexicon")
    a2 = get_sentiment_analyzer("lexicon")
    assert a1 is a2


def test_reset_clears_cache():
    a1 = get_sentiment_analyzer("lexicon")
    reset_sentiment_analyzer()
    a2 = get_sentiment_analyzer("lexicon")
    assert a1 is not a2
