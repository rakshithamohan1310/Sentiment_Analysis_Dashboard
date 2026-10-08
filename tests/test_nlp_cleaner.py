"""Tests for backend/nlp/cleaner.py"""
from __future__ import annotations

import pytest

from backend.nlp.cleaner import clean_text, compute_completeness_score


# ── clean_text ────────────────────────────────────────────────────────────────

def test_none_returns_empty():
    assert clean_text(None) == ""


def test_empty_returns_empty():
    assert clean_text("") == ""


def test_html_stripped():
    assert clean_text("<b>Great</b> battery") == "Great battery"


def test_html_anchor_stripped():
    result = clean_text('<a href="http://example.com">link text</a>')
    assert "<a" not in result
    assert "link text" in result


def test_url_removed():
    result = clean_text("Read more at https://example.com/article today")
    assert "https://" not in result
    assert "example.com" not in result


def test_www_url_removed():
    result = clean_text("Check www.example.com for details")
    assert "www.example.com" not in result


def test_email_masked():
    result = clean_text("Contact me at user@example.com for details")
    assert "user@example.com" not in result
    assert "<EMAIL>" in result


def test_phone_masked_us():
    result = clean_text("Call 555-867-5309 to reach me")
    assert "555-867-5309" not in result
    assert "<PHONE>" in result


def test_emoji_preserved():
    result = clean_text("Great battery life! 😊🔋")
    assert "😊" in result
    assert "🔋" in result


def test_numbers_preserved():
    result = clean_text("Battery at 87% after 45000 miles")
    assert "87" in result
    assert "45000" in result


def test_markdown_bold_stripped():
    result = clean_text("**excellent** charging speed")
    assert "**" not in result
    assert "excellent" in result


def test_markdown_italic_stripped():
    result = clean_text("*great* battery performance")
    assert result.startswith("great") or "great" in result
    assert "*" not in result


def test_markdown_heading_stripped():
    result = clean_text("## Battery Review\nGreat performance")
    assert "##" not in result
    assert "Battery Review" in result


def test_markdown_code_block_stripped():
    result = clean_text("Here is `some code` inline")
    assert "`" not in result


def test_quoted_lines_removed():
    result = clean_text("Normal text\n> This is a quote\nMore text")
    assert "> This is a quote" not in result


def test_whitespace_collapsed():
    result = clean_text("Too   many    spaces")
    assert "  " not in result


def test_unicode_normalised():
    # Fullwidth characters should be normalised
    result = clean_text("ｅｘｃｅｌｌｅｎｔ")
    assert result == "excellent"


def test_markdown_link_keeps_anchor():
    result = clean_text("See [battery guide](http://example.com/guide) for details")
    assert "battery guide" in result
    assert "http://example.com" not in result


# ── compute_completeness_score ────────────────────────────────────────────────

def test_completeness_empty_text():
    assert compute_completeness_score(None, None) == 0.0


def test_completeness_short_text():
    score = compute_completeness_score(None, "short")
    assert 0.0 < score < 1.0


def test_completeness_medium_text():
    score = compute_completeness_score(None, "x" * 60)
    assert score >= 0.6


def test_completeness_long_text_with_title():
    score = compute_completeness_score("A title", "x" * 250)
    assert score >= 0.9


def test_completeness_with_pii_penalty():
    score_no_pii  = compute_completeness_score("Title", "Normal text without PII " * 10)
    score_with_pii = compute_completeness_score("Title", "<EMAIL> some text " * 10)
    assert score_no_pii > score_with_pii


def test_completeness_max_one():
    score = compute_completeness_score("Long title", "x" * 5000)
    assert score <= 1.0
