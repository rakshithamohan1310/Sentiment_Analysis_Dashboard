"""Tests for backend/processing/dedup.py"""
from __future__ import annotations

import pytest

from backend.processing.dedup import Deduplicator, compute_text_hash


# ── compute_text_hash ─────────────────────────────────────────────────────────

def test_hash_is_64_char_hex():
    h = compute_text_hash("Hello world")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_identical_texts_same_hash():
    assert compute_text_hash("Battery range dropped") == compute_text_hash(
        "Battery range dropped"
    )


def test_different_texts_different_hash():
    assert compute_text_hash("Battery range dropped") != compute_text_hash(
        "Charging speed is fast"
    )


def test_hash_normalises_case():
    assert compute_text_hash("BATTERY RANGE") == compute_text_hash("battery range")


def test_hash_normalises_whitespace():
    assert compute_text_hash("battery  range") == compute_text_hash("battery range")


def test_hash_normalises_leading_trailing():
    assert compute_text_hash("  battery range  ") == compute_text_hash("battery range")


# ── Deduplicator exact matching ───────────────────────────────────────────────

def test_first_record_is_not_duplicate():
    d = Deduplicator()
    r = d.check(1, "Battery range dropped after 2 years")
    assert r.is_duplicate is False
    assert r.canonical_id == 1


def test_identical_second_record_is_duplicate():
    d = Deduplicator()
    d.check(1, "Battery range dropped after 2 years")
    r2 = d.check(2, "Battery range dropped after 2 years")
    assert r2.is_duplicate is True
    assert r2.canonical_id == 1


def test_different_text_not_duplicate():
    d = Deduplicator()
    d.check(1, "Battery range dropped after 2 years")
    r2 = d.check(2, "Charging speed improved significantly this year")
    assert r2.is_duplicate is False


def test_normalised_duplicate_detected():
    """Differently cased / whitespaced texts with same content are duplicates."""
    d = Deduplicator()
    d.check(1, "Battery range dropped")
    r2 = d.check(2, "BATTERY RANGE DROPPED")
    assert r2.is_duplicate is True


def test_duplicate_group_id_matches_canonical():
    d = Deduplicator()
    r1 = d.check(1, "Battery range dropped after 2 years")
    r2 = d.check(2, "Battery range dropped after 2 years")
    assert r1.duplicate_group_id == r2.duplicate_group_id


def test_three_duplicates_same_group():
    d = Deduplicator()
    text = "Same review text for three records"
    r1 = d.check(1, text)
    r2 = d.check(2, text)
    r3 = d.check(3, text)
    assert r1.duplicate_group_id == r2.duplicate_group_id == r3.duplicate_group_id
    assert r1.is_duplicate is False
    assert r2.is_duplicate is True
    assert r3.is_duplicate is True


def test_idempotent_with_existing_hashes():
    """
    If existing_hashes is pre-loaded from a previous run, re-checking the
    same text should be detected as a duplicate of the existing record.
    """
    text = "Battery degradation after three years of ownership"
    h    = compute_text_hash(text)
    d    = Deduplicator(existing_hashes={h: 42})  # record 42 already processed
    r    = d.check(99, text)
    assert r.is_duplicate is True
    assert r.canonical_id == 42


def test_two_separate_groups():
    d = Deduplicator()
    d.check(1, "Text about battery")
    d.check(2, "Text about charging speed")
    r3 = d.check(3, "Text about battery")   # dup of record 1
    r4 = d.check(4, "Text about charging speed")  # dup of record 2
    r5 = d.check(5, "Text about thermal management")  # new group
    assert r3.is_duplicate is True
    assert r4.is_duplicate is True
    assert r5.is_duplicate is False
    assert r3.duplicate_group_id != r4.duplicate_group_id


def test_missing_datasketch_disables_near_dup(monkeypatch):
    """When datasketch is unavailable, near-dup detection should be disabled."""
    import sys
    orig = sys.modules.get("datasketch")
    sys.modules["datasketch"] = None  # simulate import failure
    try:
        d = Deduplicator(near_dup_threshold=0.9)
        # Should not raise — just silently disable near-dup
        r = d.check(1, "Some text about charging speed and range")
        assert r.is_duplicate is False
    finally:
        if orig is None:
            sys.modules.pop("datasketch", None)
        else:
            sys.modules["datasketch"] = orig
