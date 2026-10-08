"""
Collection orchestrator – runs one or more collectors against a domain config,
persists results to raw_reviews, and tracks every run in collection_runs.

Design rules:
  - One failing adapter never stops others.
  - Exact duplicate by (source, source_record_id) → counted as duplicate, not error.
  - A single bad record → logged and skipped, batch continues.
  - collection_runs row is created at start (status="running") and updated at end.
  - Prints a human-readable summary after each run.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.collectors.base import CollectorConfig, RawRecord, ReviewCollector
from backend.models.collection_run import CollectionRun, RunStatus
from backend.models.raw_review import IngestionStatus, RawReview

logger = logging.getLogger(__name__)


# ── Per-run statistics ────────────────────────────────────────────────────────

@dataclass
class RunStats:
    source: str
    found: int = 0
    inserted: int = 0
    duplicates: int = 0
    rejected: int = 0
    errors: int = 0

    def status(self) -> str:
        if self.errors > 0 and self.inserted == 0:
            return RunStatus.failed.value
        if self.errors > 0 or self.rejected > 0:
            return RunStatus.partial.value
        return RunStatus.completed.value

    def summary_line(self) -> str:
        return (
            f"[{self.source}] "
            f"Found={self.found} | Inserted={self.inserted} | "
            f"Duplicates={self.duplicates} | Rejected={self.rejected} | "
            f"Errors={self.errors} | Status={self.status()}"
        )


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _open_run(session: AsyncSession, source: str) -> CollectionRun:
    run = CollectionRun(
        source=source,
        started_at=datetime.now(timezone.utc),
        status=RunStatus.running.value,
    )
    session.add(run)
    await session.flush()  # get run_id
    return run


async def _close_run(
    session: AsyncSession, run: CollectionRun, stats: RunStats, error_detail: Optional[str] = None
) -> None:
    run.completed_at = datetime.now(timezone.utc)
    run.records_found = stats.found
    run.records_inserted = stats.inserted
    run.duplicates = stats.duplicates
    run.rejected = stats.rejected
    run.errors = stats.errors
    run.status = stats.status()
    if error_detail:
        run.error_detail = error_detail
    session.add(run)


async def _save_record(
    session: AsyncSession, record: RawRecord, stats: RunStats
) -> None:
    """
    Insert a RawRecord into raw_reviews.
    ON CONFLICT (source, source_record_id) → skip (idempotent).
    """
    stmt = (
        pg_insert(RawReview)
        .values(
            source=record.source,
            source_record_id=record.source_record_id,
            source_url=record.source_url,
            published_at=record.published_at,
            author_id_hash=record.author_id_hash,
            title=record.title,
            text=record.text,
            rating=record.rating,
            language=record.language,
            metadata=record.metadata,
            raw_payload=record.raw_payload,
            ingestion_status=IngestionStatus.collected.value,
            collected_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_nothing(constraint="uq_raw_reviews_source_record")
    )
    result = await session.execute(stmt)
    if result.rowcount == 0:
        stats.duplicates += 1
    else:
        stats.inserted += 1


# ── Orchestrator ──────────────────────────────────────────────────────────────

class CollectionOrchestrator:
    """
    Runs a list of ReviewCollector adapters and persists results.

    Usage::

        orchestrator = CollectionOrchestrator(session, [demo_adapter, reddit_adapter])
        summaries = await orchestrator.run_all(config)
    """

    def __init__(
        self,
        session: AsyncSession,
        collectors: list[ReviewCollector],
    ) -> None:
        self._session = session
        self._collectors = collectors

    async def run_all(self, config: CollectorConfig) -> list[RunStats]:
        """
        Run every collector independently.  One failure never stops the others.
        Returns a list of RunStats (one per collector attempted).
        """
        all_stats: list[RunStats] = []

        for collector in self._collectors:
            if not collector.is_available():
                logger.info("[orchestrator] Skipping unavailable adapter: %s", collector.source_name)
                continue

            stats = await self._run_one(collector, config)
            all_stats.append(stats)
            print(stats.summary_line())  # human-readable per-source summary

        if all_stats:
            self._print_aggregate(all_stats)

        return all_stats

    async def _run_one(
        self, collector: ReviewCollector, config: CollectorConfig
    ) -> RunStats:
        """Run a single collector; catch all errors so others are not affected."""
        stats = RunStats(source=collector.source_name)
        run: Optional[CollectionRun] = None

        try:
            run = await _open_run(self._session, collector.source_name)
            await self._session.commit()

            async for record in collector.collect(config):
                stats.found += 1
                try:
                    self._validate_record(record)
                except ValueError as exc:
                    logger.warning(
                        "[orchestrator] Record rejected (source=%s id=%s): %s",
                        record.source,
                        record.source_record_id,
                        exc,
                    )
                    stats.rejected += 1
                    continue

                try:
                    await _save_record(self._session, record, stats)
                    # Flush periodically to avoid huge in-memory transactions
                    if (stats.inserted + stats.duplicates) % 100 == 0:
                        await self._session.flush()
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "[orchestrator] DB error saving record (source=%s id=%s): %s",
                        record.source,
                        record.source_record_id,
                        exc,
                    )
                    stats.errors += 1
                    await self._session.rollback()

        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "[orchestrator] Unhandled error in adapter %s: %s",
                collector.source_name,
                exc,
            )
            stats.errors += 1
            if run is not None:
                try:
                    await _close_run(self._session, run, stats, error_detail=str(exc))
                    await self._session.commit()
                except Exception:
                    pass
            return stats

        if run is not None:
            try:
                await _close_run(self._session, run, stats)
                await self._session.commit()
            except Exception as exc:  # noqa: BLE001
                logger.error("[orchestrator] Failed to close run for %s: %s", collector.source_name, exc)

        return stats

    @staticmethod
    def _validate_record(record: RawRecord) -> None:
        """Basic validation before DB insert. Raises ValueError to reject a record."""
        if not record.source_record_id.strip():
            raise ValueError("Empty source_record_id")
        if record.text is None and record.title is None:
            raise ValueError("Both text and title are None — nothing to store")
        if record.text and len(record.text) > 100_000:
            raise ValueError(f"Text too long: {len(record.text)} chars")

    @staticmethod
    def _print_aggregate(all_stats: list[RunStats]) -> None:
        total_found = sum(s.found for s in all_stats)
        total_inserted = sum(s.inserted for s in all_stats)
        total_dupes = sum(s.duplicates for s in all_stats)
        total_rejected = sum(s.rejected for s in all_stats)
        total_errors = sum(s.errors for s in all_stats)
        any_failed = any(s.status() == RunStatus.failed.value for s in all_stats)
        overall = RunStatus.failed.value if any_failed else RunStatus.completed.value
        print(
            f"\n── Collection summary ──────────────────────────────────\n"
            f"  Sources run : {len(all_stats)}\n"
            f"  Found       : {total_found}\n"
            f"  Inserted    : {total_inserted}\n"
            f"  Duplicates  : {total_dupes}\n"
            f"  Rejected    : {total_rejected}\n"
            f"  Errors      : {total_errors}\n"
            f"  Overall     : {overall}\n"
            f"────────────────────────────────────────────────────────"
        )


# ── Registry factory ──────────────────────────────────────────────────────────

def build_collector_registry(enabled_sources: list[str] | None = None) -> list[ReviewCollector]:
    """
    Instantiate all known collectors. Returns only those whose source_name
    appears in enabled_sources (or all, if enabled_sources is None).
    Import errors for optional packages (praw) are caught gracefully.
    """
    from backend.collectors.demo.adapter import DemoCollector
    from backend.collectors.reddit.adapter import RedditCollector
    from backend.collectors.youtube.adapter import YouTubeCollector

    all_collectors: list[ReviewCollector] = [
        DemoCollector(),
        RedditCollector(),
        YouTubeCollector(),
    ]

    if enabled_sources is None:
        return all_collectors

    return [c for c in all_collectors if c.source_name in enabled_sources]
