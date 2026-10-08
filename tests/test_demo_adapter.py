"""
Unit tests for the Demo adapter.
No real DB, no network calls.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.collectors.base import CollectorConfig
from backend.collectors.demo.adapter import DemoCollector


@pytest.fixture()
def collector(demo_data_dir: Path) -> DemoCollector:
    return DemoCollector(data_dir=demo_data_dir)


# ── Basic collection ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_demo_yields_all_records(demo_data_dir: Path):
    """All 3 test records are yielded with no keyword filter."""
    collector = DemoCollector(data_dir=demo_data_dir)
    config = CollectorConfig(max_records=100)
    records = [r async for r in collector.collect(config)]
    assert len(records) == 3


@pytest.mark.asyncio
async def test_demo_source_is_always_demo(demo_data_dir: Path):
    collector = DemoCollector(data_dir=demo_data_dir)
    config = CollectorConfig(max_records=100)
    records = [r async for r in collector.collect(config)]
    assert all(r.source == "demo" for r in records)


@pytest.mark.asyncio
async def test_demo_metadata_always_synthetic(demo_data_dir: Path):
    """metadata must always carry {"synthetic": True}."""
    collector = DemoCollector(data_dir=demo_data_dir)
    config = CollectorConfig(max_records=100)
    records = [r async for r in collector.collect(config)]
    assert all(r.metadata.get("synthetic") is True for r in records)


@pytest.mark.asyncio
async def test_demo_author_is_hashed(demo_data_dir: Path):
    """Author IDs are hashed, not stored raw."""
    collector = DemoCollector(data_dir=demo_data_dir)
    config = CollectorConfig(max_records=100)
    records = [r async for r in collector.collect(config)]
    # None of the raw author names should appear in the hash
    for r in records:
        if r.author_id_hash is not None:
            assert "test_user" not in r.author_id_hash
            assert len(r.author_id_hash) == 64  # SHA-256 hex


# ── Keyword filtering ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_demo_keyword_filter(demo_data_dir: Path):
    """Only records matching the keyword should be returned."""
    collector = DemoCollector(data_dir=demo_data_dir)
    config = CollectorConfig(keywords=["battery"], max_records=100)
    records = [r async for r in collector.collect(config)]
    assert len(records) == 1
    assert records[0].source_record_id == "test_001"


@pytest.mark.asyncio
async def test_demo_keyword_no_match(demo_data_dir: Path):
    """A keyword that matches nothing yields an empty result."""
    collector = DemoCollector(data_dir=demo_data_dir)
    config = CollectorConfig(keywords=["this_keyword_matches_nothing_xyz"], max_records=100)
    records = [r async for r in collector.collect(config)]
    assert records == []


# ── max_records limit ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_demo_max_records_respected(demo_data_dir: Path):
    collector = DemoCollector(data_dir=demo_data_dir)
    config = CollectorConfig(max_records=2)
    records = [r async for r in collector.collect(config)]
    assert len(records) == 2


# ── Availability ──────────────────────────────────────────────────────────────

def test_demo_unavailable_when_dir_missing(tmp_path: Path):
    missing = tmp_path / "nonexistent_subdir"
    collector = DemoCollector(data_dir=missing)
    assert collector.is_available() is False


@pytest.mark.asyncio
async def test_demo_collect_yields_nothing_when_unavailable(tmp_path: Path):
    missing = tmp_path / "nonexistent_subdir"
    collector = DemoCollector(data_dir=missing)
    config = CollectorConfig(max_records=100)
    records = [r async for r in collector.collect(config)]
    assert records == []


# ── Malformed records ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_demo_skips_malformed_record(tmp_path: Path):
    """A record missing 'id' should be skipped, not abort the batch."""
    records = [
        {"id": "good_001", "title": "Good record", "text": "Valid content.", "language": "en",
         "metadata": {"synthetic": True}},
        {"title": "No ID record", "text": "Missing id field."},  # bad record
        {"id": "good_002", "title": "Another good record", "text": "Also valid.", "language": "en",
         "metadata": {"synthetic": True}},
    ]
    (tmp_path / "mixed.json").write_text(json.dumps(records))
    collector = DemoCollector(data_dir=tmp_path)
    config = CollectorConfig(max_records=100)
    results = [r async for r in collector.collect(config)]
    ids = [r.source_record_id for r in results]
    assert "good_001" in ids
    assert "good_002" in ids
    # The bad record should not crash the run
    assert len(results) == 2


@pytest.mark.asyncio
async def test_demo_skips_invalid_json_file(tmp_path: Path):
    """A file with invalid JSON should be skipped, not crash the run."""
    (tmp_path / "bad.json").write_text("not json {{{{")
    (tmp_path / "good.json").write_text(json.dumps([
        {"id": "ok_001", "title": "Fine", "text": "OK", "metadata": {"synthetic": True}}
    ]))
    collector = DemoCollector(data_dir=tmp_path)
    config = CollectorConfig(max_records=100)
    results = [r async for r in collector.collect(config)]
    assert len(results) == 1
    assert results[0].source_record_id == "ok_001"
