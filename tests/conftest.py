"""
Shared pytest fixtures.

All tests run against an in-memory SQLite database so no real Postgres is needed.
The SQLAlchemy models work with both Postgres (production) and SQLite (tests)
because we avoid Postgres-only features in the ORM layer (JSONB columns are
mapped to JSON for SQLite via the fixture override).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# ── Force test settings before any backend import ────────────────────────────
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("AUTHOR_HASH_SALT", "test_salt_fixed")
os.environ.setdefault("REDDIT_CLIENT_ID", "")
os.environ.setdefault("REDDIT_CLIENT_SECRET", "")
os.environ.setdefault("YOUTUBE_API_KEY", "")
os.environ.setdefault("APP_ENV", "test")
# Use lexicon-only sentiment in tests — never download a transformer model
os.environ.setdefault("SENTIMENT_MODEL", "lexicon")

from backend.models.base import Base  # noqa: E402
from backend.models import source, raw_review, collection_run  # noqa: E402, F401
from backend.models import review, review_aspect  # noqa: E402, F401  — Phase 2 tables


# ── SQLite async engine for tests ─────────────────────────────────────────────
@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture()
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a fresh in-memory SQLite session for each test.
    Tables are created and dropped around each test (not each session)
    so tests are fully isolated.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    # SQLite doesn't support JSONB — patch column types for test schema creation
    # by creating tables using the ORM metadata which already has JSON fallback
    async with engine.begin() as conn:
        # Remap postgres JSONB to plain JSON for SQLite
        await conn.run_sync(_create_tables_sqlite)

    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    async with factory() as session:
        # Seed the three known source rows so FK constraints pass for all tests
        from backend.models.source import Source as _Source
        for _name, _display in [("demo", "Demo"), ("reddit", "Reddit"), ("youtube", "YouTube")]:
            session.add(_Source(name=_name, display_name=_display))
        await session.commit()
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def _create_tables_sqlite(conn):
    """Create all tables, replacing JSONB with TEXT for SQLite compatibility."""
    from sqlalchemy.dialects import sqlite as sqlite_dialect
    from sqlalchemy import JSON
    # Remap JSONB columns to JSON (SQLAlchemy maps JSON → TEXT on SQLite)
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if hasattr(col.type, "__class__") and "JSONB" in type(col.type).__name__:
                col.type = JSON()
    Base.metadata.create_all(conn)


# ── Demo data fixture ─────────────────────────────────────────────────────────
@pytest.fixture()
def demo_data_dir(tmp_path: Path) -> Path:
    """Create a temp directory with 3 synthetic demo JSON records."""
    records = [
        {
            "id": "test_001",
            "title": "Battery degradation after 2 years",
            "text": "Battery health dropped to 90% after 2 years and 25k miles.",
            "source_url": "https://example-demo.invalid/test/1",
            "published_at": "2023-06-01T10:00:00+00:00",
            "author_id": "test_user_001",
            "rating": 3.5,
            "language": "en",
            "metadata": {"synthetic": True, "topic": "battery"},
        },
        {
            "id": "test_002",
            "title": "EV charging problem in winter",
            "text": "Charging failed twice in cold weather. Very frustrating.",
            "source_url": "https://example-demo.invalid/test/2",
            "published_at": "2023-12-15T08:00:00+00:00",
            "author_id": "test_user_002",
            "rating": 2.0,
            "language": "en",
            "metadata": {"synthetic": True, "topic": "charging"},
        },
        {
            "id": "test_003",
            "title": "Thermal management works great",
            "text": "Battery thermal management kept temps perfect all summer.",
            "source_url": "https://example-demo.invalid/test/3",
            "published_at": "2024-08-01T12:00:00+00:00",
            "author_id": "test_user_003",
            "rating": 5.0,
            "language": "en",
            "metadata": {"synthetic": True, "topic": "thermal"},
        },
    ]
    demo_file = tmp_path / "test_reviews.json"
    demo_file.write_text(json.dumps(records), encoding="utf-8")
    return tmp_path


# ── Phase 2 fixtures ──────────────────────────────────────────────────────────

from backend.models.source import Source           # noqa: E402
from backend.models.raw_review import RawReview, IngestionStatus  # noqa: E402


@pytest_asyncio.fixture()
async def seeded_sources(db_session: AsyncSession) -> None:
    """No-op: sources are now seeded inside db_session fixture for all tests."""
    pass  # sources seeded in db_session above


async def make_raw_review(
    session: AsyncSession,
    *,
    source: str = "demo",
    source_record_id: str = "test_rec_001",
    title: str | None = "Test review title",
    text: str | None = "This is a test review text with enough content.",
    language: str | None = "en",
    rating: float | None = 4.0,
    synthetic: bool = True,
    ingestion_status: str = IngestionStatus.collected.value,
    metadata: dict | None = None,
) -> RawReview:
    """Helper to create and flush a RawReview row for Phase 2 tests."""
    raw = RawReview(
        source            = source,
        source_record_id  = source_record_id,
        title             = title,
        text              = text,
        language          = language,
        rating            = rating,
        ingestion_status  = ingestion_status,
        metadata_         = metadata if metadata is not None else {"synthetic": synthetic},
    )
    session.add(raw)
    await session.flush()
    return raw


# ── SQLite compatibility patch for collection orchestrator ────────────────────
# The Phase 1 collection orchestrator uses pg_insert (PostgreSQL dialect) for
# ON CONFLICT DO NOTHING.  SQLite doesn't support this.  We patch _save_record
# at test time to use a plain INSERT with IntegrityError catch instead.

from sqlalchemy import insert as _sa_insert
from sqlalchemy.exc import IntegrityError as _IntegrityError
from backend.models.raw_review import IngestionStatus as _IngestionStatus


async def _sqlite_save_record(session, record, stats):
    """SQLite-compatible replacement for collectors.orchestrator._save_record."""
    from datetime import datetime, timezone
    from backend.models.raw_review import RawReview as _RawReview

    # Check for existing record first (idempotent)
    from sqlalchemy import select as _select
    existing = await session.execute(
        _select(_RawReview.id).where(
            _RawReview.source == record.source,
            _RawReview.source_record_id == record.source_record_id,
        ).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        stats.duplicates += 1
        return

    raw = _RawReview(
        source            = record.source,
        source_record_id  = record.source_record_id,
        source_url        = record.source_url,
        published_at      = record.published_at,
        author_id_hash    = record.author_id_hash,
        title             = record.title,
        text              = record.text,
        rating            = record.rating,
        language          = record.language,
        metadata_         = record.metadata,
        raw_payload       = record.raw_payload,
        ingestion_status  = _IngestionStatus.collected.value,
        collected_at      = datetime.now(timezone.utc),
    )
    session.add(raw)
    stats.inserted += 1


@pytest.fixture(autouse=True)
def patch_pg_insert_for_sqlite(monkeypatch):
    """
    Replace _save_record in the collection orchestrator with a SQLite-compatible
    version.  This allows Phase 1 tests to run against the in-memory SQLite DB.
    """
    monkeypatch.setattr(
        "backend.collectors.orchestrator._save_record",
        _sqlite_save_record,
    )
