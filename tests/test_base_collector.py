"""
Unit tests for base.py helpers: RawRecord validation, hash_author_id, truncate_text.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.collectors.base import RawRecord, hash_author_id, truncate_text


# ── RawRecord validation ──────────────────────────────────────────────────────

def test_raw_record_valid():
    r = RawRecord(source="demo", source_record_id="abc123", text="Some review text")
    assert r.source == "demo"
    assert r.source_record_id == "abc123"


def test_raw_record_empty_source_raises():
    with pytest.raises(Exception):
        RawRecord(source="", source_record_id="abc123")


def test_raw_record_empty_record_id_raises():
    with pytest.raises(Exception):
        RawRecord(source="demo", source_record_id="")


def test_raw_record_whitespace_record_id_raises():
    with pytest.raises(Exception):
        RawRecord(source="demo", source_record_id="   ")


def test_raw_record_datetime_coercion_from_timestamp():
    r = RawRecord(source="demo", source_record_id="x", published_at=1_700_000_000)
    assert r.published_at is not None
    assert r.published_at.tzinfo is not None


def test_raw_record_datetime_coercion_from_string():
    r = RawRecord(source="demo", source_record_id="x", published_at="2023-06-01T10:00:00+00:00")
    assert r.published_at is not None
    assert r.published_at.year == 2023


def test_raw_record_naive_datetime_gets_utc():
    naive = datetime(2023, 6, 1, 10, 0, 0)
    r = RawRecord(source="demo", source_record_id="x", published_at=naive)
    assert r.published_at.tzinfo is not None


def test_raw_record_metadata_defaults_to_empty_dict():
    r = RawRecord(source="demo", source_record_id="x")
    assert r.metadata == {}


def test_raw_record_raw_payload_defaults_to_empty_dict():
    r = RawRecord(source="demo", source_record_id="x")
    assert r.raw_payload == {}


# ── hash_author_id ────────────────────────────────────────────────────────────

def test_hash_author_id_produces_64_char_hex():
    h = hash_author_id("some_user_123", "my_salt")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_hash_author_id_same_input_same_output():
    h1 = hash_author_id("user_a", "salt_x")
    h2 = hash_author_id("user_a", "salt_x")
    assert h1 == h2


def test_hash_author_id_different_salts_differ():
    h1 = hash_author_id("user_a", "salt_1")
    h2 = hash_author_id("user_a", "salt_2")
    assert h1 != h2


def test_hash_author_id_different_users_differ():
    h1 = hash_author_id("alice", "salt")
    h2 = hash_author_id("bob", "salt")
    assert h1 != h2


def test_hash_does_not_contain_raw_username():
    username = "very_identifiable_username"
    h = hash_author_id(username, "test_salt")
    assert username not in h


# ── truncate_text ─────────────────────────────────────────────────────────────

def test_truncate_text_short_stays_unchanged():
    short = "Hello world"
    assert truncate_text(short) == short


def test_truncate_text_long_is_truncated():
    long_text = "x" * 50_000
    result = truncate_text(long_text, max_chars=40_000)
    assert len(result) == 40_000


def test_truncate_text_exactly_at_limit_unchanged():
    text = "y" * 40_000
    result = truncate_text(text, max_chars=40_000)
    assert result == text
    assert len(result) == 40_000
