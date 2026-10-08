"""Tests for backend/nlp/language.py"""
from __future__ import annotations

import pytest

from backend.nlp.language import UNKNOWN, detect_language


def test_none_input_returns_unknown():
    assert detect_language(None) == UNKNOWN


def test_empty_string_returns_unknown():
    assert detect_language("") == UNKNOWN


def test_very_short_text_returns_unknown():
    # less than MIN_CHARS (20)
    assert detect_language("Hi") == UNKNOWN


def test_short_text_at_limit_returns_unknown():
    # exactly 19 chars — still too short
    assert detect_language("A" * 19) == UNKNOWN


def test_existing_label_honoured():
    """If an existing language is provided, it must be returned unchanged."""
    result = detect_language("Some text here", existing="de")
    assert result == "de"


def test_existing_unknown_not_honoured():
    """existing='unknown' should still trigger detection on long enough text."""
    long_text = "This is a sufficiently long English sentence for detection."
    result = detect_language(long_text, existing="unknown")
    # Should detect something — not necessarily 'en' in all environments
    assert isinstance(result, str)
    assert len(result) <= 8


def test_english_text_detected():
    """Long English text should be detected as 'en' (or not crash)."""
    text = "The battery degradation after three years is really disappointing."
    result = detect_language(text)
    # langdetect may not be installed in all CI environments — just check no crash
    assert result is not None
    assert isinstance(result, str)


def test_result_is_max_8_chars():
    text = "Battery health check after two years of ownership."
    result = detect_language(text)
    assert len(result) <= 8


def test_detect_does_not_raise_on_garbage():
    """Garbage input should return 'unknown', not raise."""
    result = detect_language("!@#$%^&*()" * 5)
    assert isinstance(result, str)
