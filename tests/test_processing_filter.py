"""Tests for backend/processing/filter.py"""
from __future__ import annotations

import pytest

from backend.processing.filter import FilterResult, QualityFilter

# Minimal domain config for tests — no YAML I/O
DOMAIN_CFG = {
    "keyword_groups": {
        "battery": ["battery health", "battery degradation"],
        "charging": ["fast charging", "charging speed"],
    },
    "quality": {
        "min_text_length": 20,
        "min_relevance_score": 0.0,
        "spam_patterns": [
            r"\bclick here\b",
            r"\bvisit our website\b",
            r"\bfree.*?trial\b",
            r"^\[deleted\]$",
            r"^\[removed\]$",
        ],
    },
}


@pytest.fixture()
def flt():
    return QualityFilter(DOMAIN_CFG)


# ── Rejection reasons ─────────────────────────────────────────────────────────

def test_empty_text_rejected(flt):
    r = flt.filter(None)
    assert r.accepted is False
    assert r.reject_reason == "empty_text"


def test_whitespace_only_rejected(flt):
    r = flt.filter("   ")
    assert r.accepted is False
    assert r.reject_reason == "empty_text"


def test_too_short_rejected(flt):
    r = flt.filter("Short")
    assert r.accepted is False
    assert r.reject_reason == "too_short"


def test_spam_click_here_rejected(flt):
    r = flt.filter("Click here to get your free battery replacement today!")
    assert r.accepted is False
    assert r.reject_reason == "spam"


def test_spam_free_trial_rejected(flt):
    r = flt.filter("Get a free trial of our battery management system now!")
    assert r.accepted is False
    assert r.reject_reason == "spam"


def test_deleted_post_rejected(flt):
    r = flt.filter("[deleted]")
    assert r.accepted is False
    assert r.reject_reason in ("too_short", "spam")


def test_removed_post_rejected(flt):
    r = flt.filter("[removed]")
    assert r.accepted is False
    assert r.reject_reason in ("too_short", "spam")


# ── Acceptance ────────────────────────────────────────────────────────────────

def test_valid_review_accepted(flt):
    r = flt.filter("Battery health dropped to 90% after 2 years and 25000 miles.")
    assert r.accepted is True
    assert r.reject_reason is None


def test_title_supplements_text(flt):
    """Title alone (without text) can pass quality check."""
    r = flt.filter(text=None, title="Battery degradation after 3 years of ownership")
    assert r.accepted is True


# ── Relevance score ───────────────────────────────────────────────────────────

def test_relevance_score_increases_with_keywords(flt):
    r_none    = flt.filter("The sky is blue and the weather is nice today here")
    r_battery = flt.filter("Battery degradation and battery health after 2 years")
    assert r_battery.relevance_score >= r_none.relevance_score


def test_relevance_is_zero_to_one(flt):
    r = flt.filter("Battery health and fast charging are important to me")
    assert 0.0 <= r.relevance_score <= 1.0


def test_no_keywords_config_returns_one():
    """When no keywords are configured, relevance should default to 1.0."""
    flt_empty = QualityFilter({"quality": {"min_text_length": 5}})
    r = flt_empty.filter("Some text here for testing purposes in the review")
    assert r.relevance_score == 1.0


# ── Relevance threshold ───────────────────────────────────────────────────────

def test_low_relevance_rejected_when_threshold_set():
    cfg = dict(DOMAIN_CFG)
    cfg["quality"] = dict(cfg["quality"])
    cfg["quality"]["min_relevance_score"] = 0.5
    flt_strict = QualityFilter(cfg)
    r = flt_strict.filter("The weather is nice and sunny today in the afternoon")
    assert r.accepted is False
    assert r.reject_reason == "low_relevance"


def test_high_relevance_passes_threshold():
    cfg = dict(DOMAIN_CFG)
    cfg["quality"] = dict(cfg["quality"])
    cfg["quality"]["min_relevance_score"] = 0.01
    flt_strict = QualityFilter(cfg)
    r = flt_strict.filter("Battery degradation and battery health are critical topics")
    assert r.accepted is True
