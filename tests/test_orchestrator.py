"""
Tests for the collection orchestrator:
  - Idempotency (second run inserts no new rows)
  - Adapter isolation (one failing adapter doesn't stop others)
  - Missing credentials (unavailable adapters skipped cleanly)
  - Duplicate detection and stats
  - collection_runs row created and updated correctly
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import AsyncIterator
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from backend.collectors.base import CollectorConfig, RawRecord, ReviewCollector
from backend.collectors.orchestrator import CollectionOrchestrator, RunStats
from backend.models.collection_run import CollectionRun, RunStatus
from backend.models.raw_review import RawReview


# ── Fake collectors for test isolation ───────────────────────────────────────

class _GoodCollector(ReviewCollector):
    """Always available, yields fixed records."""

    def __init__(self, records: list[RawRecord], name: str = "demo") -> None:
        self._records = records
        self._name = name

    @property
    def source_name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return True

    async def collect(self, config: CollectorConfig) -> AsyncIterator[RawRecord]:
        for r in self._records:
            yield r


class _BrokenCollector(ReviewCollector):
    """Raises an exception mid-collection."""

    @property
    def source_name(self) -> str:
        return "demo"

    def is_available(self) -> bool:
        return True

    async def collect(self, config: CollectorConfig) -> AsyncIterator[RawRecord]:
        raise RuntimeError("Simulated adapter crash")
        yield  # make it a generator


class _UnavailableCollector(ReviewCollector):
    """Credentials missing — is_available() returns False."""

    @property
    def source_name(self) -> str:
        return "reddit"

    def is_available(self) -> bool:
        return False

    async def collect(self, config: CollectorConfig) -> AsyncIterator[RawRecord]:
        yield  # pragma: no cover


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_record(record_id: str, source: str = "demo") -> RawRecord:
    return RawRecord(
        source=source,
        source_record_id=record_id,
        title=f"Test title {record_id}",
        text=f"Test body for record {record_id}",
        metadata={"synthetic": True},
    )


# ── Idempotency tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_idempotency_second_run_inserts_nothing(db_session):
    """Running the same collector twice must not insert duplicates."""
    records = [_make_record("idem_001"), _make_record("idem_002")]
    collector = _GoodCollector(records)
    config = CollectorConfig(max_records=100)

    # First run
    orch1 = CollectionOrchestrator(db_session, [collector])
    stats1 = await orch1.run_all(config)
    assert stats1[0].inserted == 2
    assert stats1[0].duplicates == 0

    # Re-create collector with same records for second run
    collector2 = _GoodCollector(records)
    orch2 = CollectionOrchestrator(db_session, [collector2])
    stats2 = await orch2.run_all(config)

    assert stats2[0].inserted == 0
    assert stats2[0].duplicates == 2

    # Confirm only 2 rows in DB
    result = await db_session.execute(
        select(RawReview).where(RawReview.source == "demo")
    )
    rows = result.scalars().all()
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_idempotency_partial_overlap(db_session):
    """If one record already exists and a new one is added, only the new one is inserted."""
    existing = [_make_record("overlap_001")]
    new_records = [_make_record("overlap_001"), _make_record("overlap_002")]

    orch1 = CollectionOrchestrator(db_session, [_GoodCollector(existing)])
    await orch1.run_all(CollectorConfig(max_records=100))

    orch2 = CollectionOrchestrator(db_session, [_GoodCollector(new_records)])
    stats2 = await orch2.run_all(CollectorConfig(max_records=100))

    assert stats2[0].inserted == 1
    assert stats2[0].duplicates == 1


# ── Adapter isolation ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_failing_adapter_does_not_stop_good_adapter(db_session):
    """A crashing adapter must not prevent other adapters from running."""

    class _AnotherGoodCollector(_GoodCollector):
        @property
        def source_name(self) -> str:
            return "youtube"

    good_record = RawRecord(
        source="youtube",
        source_record_id="yt_good_001",
        title="YouTube comment",
        text="Battery works fine",
        metadata={"synthetic": True},
    )

    # Broken demo adapter first, then good youtube adapter
    collectors = [_BrokenCollector(), _AnotherGoodCollector([good_record], name="youtube")]
    orch = CollectionOrchestrator(db_session, collectors)
    all_stats = await orch.run_all(CollectorConfig(max_records=100))

    # Both adapters ran and produced stats
    sources = {s.source for s in all_stats}
    assert "demo" in sources
    assert "youtube" in sources

    # The broken one shows errors, the good one shows inserted=1
    demo_stats = next(s for s in all_stats if s.source == "demo")
    yt_stats = next(s for s in all_stats if s.source == "youtube")

    assert demo_stats.errors > 0
    assert yt_stats.inserted == 1


@pytest.mark.asyncio
async def test_multiple_adapters_run_independently(db_session):
    """Stats are tracked per-adapter independently."""
    records_a = [_make_record("a_001"), _make_record("a_002")]
    records_b = [
        RawRecord(source="youtube", source_record_id="b_001",
                  title="YT", text="Some comment", metadata={"synthetic": True}),
    ]

    class _YoutubeCollector(_GoodCollector):
        @property
        def source_name(self) -> str:
            return "youtube"

    collectors = [
        _GoodCollector(records_a, name="demo"),
        _YoutubeCollector(records_b, name="youtube"),
    ]
    orch = CollectionOrchestrator(db_session, collectors)
    all_stats = await orch.run_all(CollectorConfig(max_records=100))

    assert len(all_stats) == 2
    demo_stats = next(s for s in all_stats if s.source == "demo")
    yt_stats = next(s for s in all_stats if s.source == "youtube")
    assert demo_stats.inserted == 2
    assert yt_stats.inserted == 1


# ── Unavailable adapter ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unavailable_adapter_is_skipped(db_session):
    """Adapters where is_available() is False must be silently skipped."""
    unavailable = _UnavailableCollector()
    good = _GoodCollector([_make_record("avail_001")])

    orch = CollectionOrchestrator(db_session, [unavailable, good])
    all_stats = await orch.run_all(CollectorConfig(max_records=100))

    # Only the good adapter produced stats
    assert len(all_stats) == 1
    assert all_stats[0].source == "demo"
    assert all_stats[0].inserted == 1


@pytest.mark.asyncio
async def test_all_unavailable_returns_empty_stats(db_session):
    """If all adapters are unavailable, run_all returns an empty list."""
    orch = CollectionOrchestrator(db_session, [_UnavailableCollector()])
    all_stats = await orch.run_all(CollectorConfig(max_records=100))
    assert all_stats == []


# ── collection_runs tracking ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collection_run_row_created(db_session):
    """A collection_runs row is created for every successful run."""
    records = [_make_record("run_track_001")]
    orch = CollectionOrchestrator(db_session, [_GoodCollector(records)])
    await orch.run_all(CollectorConfig(max_records=100))

    result = await db_session.execute(
        select(CollectionRun).where(CollectionRun.source == "demo")
    )
    runs = result.scalars().all()
    assert len(runs) >= 1
    run = runs[-1]
    assert run.records_inserted == 1
    assert run.status == RunStatus.completed.value
    assert run.completed_at is not None


@pytest.mark.asyncio
async def test_collection_run_tracks_duplicates(db_session):
    """Duplicate count is correctly recorded in collection_runs."""
    records = [_make_record("dup_track_001")]

    orch1 = CollectionOrchestrator(db_session, [_GoodCollector(records)])
    await orch1.run_all(CollectorConfig(max_records=100))

    orch2 = CollectionOrchestrator(db_session, [_GoodCollector(records)])
    await orch2.run_all(CollectorConfig(max_records=100))

    result = await db_session.execute(
        select(CollectionRun).where(CollectionRun.source == "demo").order_by(CollectionRun.run_id.desc())
    )
    runs = result.scalars().all()
    second_run = runs[0]
    assert second_run.duplicates == 1
    assert second_run.records_inserted == 0


# ── RunStats helper ───────────────────────────────────────────────────────────

def test_run_stats_status_completed():
    s = RunStats(source="demo", inserted=10, errors=0, rejected=0)
    assert s.status() == RunStatus.completed.value


def test_run_stats_status_partial():
    s = RunStats(source="demo", inserted=5, errors=1, rejected=0)
    assert s.status() == RunStatus.partial.value


def test_run_stats_status_failed():
    s = RunStats(source="demo", inserted=0, errors=3, rejected=0)
    assert s.status() == RunStatus.failed.value


def test_run_stats_summary_line():
    s = RunStats(source="demo", found=10, inserted=8, duplicates=1, rejected=1, errors=0)
    line = s.summary_line()
    assert "demo" in line
    assert "Found=10" in line
    assert "Inserted=8" in line
