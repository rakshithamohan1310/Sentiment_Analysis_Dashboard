"""
Tests for backend/nlp/aspects.py.

Includes the required regression test for the canonical mixed-sentiment example.
"""
from __future__ import annotations

import os
import pytest

os.environ["SENTIMENT_MODEL"] = "lexicon"

from backend.nlp.sentiment import LexiconSentimentAnalyzer, reset_sentiment_analyzer
from backend.nlp.aspects import AspectExtractor, reset_aspect_extractor


@pytest.fixture(autouse=True)
def reset_singletons():
    reset_sentiment_analyzer()
    reset_aspect_extractor()
    yield
    reset_sentiment_analyzer()
    reset_aspect_extractor()


# ── Minimal aspect config for unit tests (no YAML I/O) ───────────────────────

MINIMAL_CONFIG = {
    "charging": {
        "charging_speed": {
            "patterns": [r"\bcharging\b", r"fast.?charg", r"charg.{0,20}fast"],
        },
        "charging_reliability": {
            "patterns": [r"charging.{0,15}broken", r"charging.{0,15}failed"],
        },
    },
    "range": {
        "range_general": {
            "patterns": [r"\brange\b"],
        },
        "range_loss": {
            "patterns": [r"range has dropped", r"range.{0,10}dropped", r"range loss"],
        },
    },
    "battery": {
        "battery_health": {
            "patterns": [
                r"battery health",
                r"battery.{0,10}range",
                r"range has dropped",
                r"battery degradation",
                r"\bdegradation\b",
            ],
        },
    },
}


def make_extractor(config=None):
    analyzer = LexiconSentimentAnalyzer()
    return AspectExtractor(
        aspect_config=config or MINIMAL_CONFIG,
        sentiment_analyzer=analyzer,
    )


# ── Canonical mixed-sentiment regression test (REQUIRED) ─────────────────────

def test_canonical_mixed_sentiment():
    """
    'Charging is extremely fast but the battery range has dropped after two years'

    Must yield:
      charging  → positive
      range     → negative  (range_general or range_loss)
      battery   → negative  (battery_health)

    This is a mandatory regression test. If it fails, the clause-splitting or
    pattern config is broken.
    """
    text = "Charging is extremely fast but the battery range has dropped after two years"
    extractor = make_extractor()
    matches = extractor.extract(text)

    by_category = {m.category: m for m in matches}
    by_aspect   = {m.aspect:   m for m in matches}

    # Charging must be detected and positive
    assert "charging" in by_category, (
        f"No charging aspect detected. Got categories: {list(by_category)}"
    )
    charging = by_category["charging"]
    assert charging.sentiment_label == "positive", (
        f"Charging sentiment expected=positive, got={charging.sentiment_label!r}\n"
        f"Matched text: {charging.matched_text!r}"
    )

    # Range must be detected and negative
    assert "range" in by_category, (
        f"No range aspect detected. Got categories: {list(by_category)}"
    )
    range_match = by_category["range"]
    assert range_match.sentiment_label == "negative", (
        f"Range sentiment expected=negative, got={range_match.sentiment_label!r}\n"
        f"Matched text: {range_match.matched_text!r}"
    )

    # Battery health must be detected and negative
    assert "battery" in by_category, (
        f"No battery aspect detected. Got categories: {list(by_category)}"
    )
    battery = by_category["battery"]
    assert battery.sentiment_label == "negative", (
        f"Battery sentiment expected=negative, got={battery.sentiment_label!r}\n"
        f"Matched text: {battery.matched_text!r}"
    )


# ── Basic extraction ──────────────────────────────────────────────────────────

def test_no_text_returns_empty():
    extractor = make_extractor()
    assert extractor.extract(None) == []


def test_empty_text_returns_empty():
    extractor = make_extractor()
    assert extractor.extract("") == []


def test_no_match_returns_empty():
    extractor = make_extractor()
    results = extractor.extract("The sky is blue and clouds are white today.")
    assert results == []


def test_single_aspect_matched():
    extractor = make_extractor()
    results = extractor.extract("The charging failed this morning completely")
    aspects = [m.aspect for m in results]
    assert "charging_reliability" in aspects


def test_multiple_aspects_in_one_review():
    extractor = make_extractor()
    results = extractor.extract(
        "Charging speed is fast but I noticed range loss over time"
    )
    aspects = {m.aspect for m in results}
    assert len(aspects) >= 2


def test_aspect_deduplication_within_review():
    """Same aspect should appear at most once per review."""
    extractor = make_extractor()
    results = extractor.extract(
        "charging charging charging fast charging fast charging"
    )
    aspects = [m.aspect for m in results]
    assert len(aspects) == len(set(aspects))


def test_title_contributes_to_extraction():
    extractor = make_extractor()
    results = extractor.extract(text=None, title="Range anxiety issue")
    aspects = [m.aspect for m in results]
    assert any("range" in a for a in aspects)


def test_matched_text_stored():
    extractor = make_extractor()
    results = extractor.extract("Charging speed is extremely fast")
    for m in results:
        if m.category == "charging":
            assert m.matched_text is not None
            assert len(m.matched_text) > 0


def test_positive_only_sentence():
    extractor = make_extractor()
    results = extractor.extract("The charging speed is excellent and reliable")
    for m in results:
        if m.category == "charging":
            assert m.sentiment_label == "positive"


def test_negative_only_sentence():
    extractor = make_extractor()
    results = extractor.extract("The range has dropped dramatically and it is terrible")
    for m in results:
        if m.category == "range":
            assert m.sentiment_label == "negative"


def test_empty_config_returns_no_matches():
    extractor = make_extractor(config={})
    results = extractor.extract("Charging range battery thermal management")
    assert results == []


def test_bad_regex_pattern_skipped_gracefully():
    """A bad regex in config should be skipped, not crash."""
    bad_config = {
        "test_cat": {
            "test_asp": {
                "patterns": [r"[invalid regex (", r"\bcharging\b"],
            }
        }
    }
    extractor = make_extractor(config=bad_config)
    # Only the valid pattern should produce results
    results = extractor.extract("The charging speed is good")
    # Should not raise regardless
    assert isinstance(results, list)
