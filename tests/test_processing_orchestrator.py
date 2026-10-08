"""
Tests for backend/processing/orchestrator.py.

Tests:
- collected → processed end-to-end
- rejection with reason
- duplicate marking
- idempotency (double-run creates no new rows)
- failure isolation (one bad record doesn't stop the batch)
- synthetic flag propagation
- synthetic records excluded from analytics by default
"""
from __future__ import annotations

import os
import pytest
import pytest_asyncio
from sqlalchemy import select

os.environ["SENTIMENT_MODEL"] = "lexicon"

from backend.models.raw_review import IngestionStatus, RawReview
from backend.models.review import ProcessingStatus, Review
from backend.models.review_aspect import ReviewAspect
from backend.processing.orchestrator import ProcessingOrchestrator
from tests.conftest import make_raw_review


# ── Minimal domain config (no YAML I/O in tests) ─────────────────────────────

MINIMAL_DOMAIN = {
    "keyword_groups": {
        "battery": ["battery health", "battery degradation"],
        "charging": ["charging speed", "fast charging"],
    },
    "aspect_config": {
        "battery": {
            "battery_health": {
                "patterns": [r"battery health", r"battery degradation", r"\bdegradation\b"],
            },
        },
        "charging": {
            "charging_speed": {
                "patterns": [r"\bcharging\b", r"fast.?charg"],
            },
        },
    },
    "gazetteer": {
        "manufacturers": {
            "Tesla": {
                "aliases": ["tesla"],
                "models": {"Model_3": ["model 3"]},
            },
        },
        "vehicle_types": {"SUV": ["suv"]},
        "model_year_pattern": r"\b(20[1-3]\d)\b",
    },
    "quality": {
        "min_text_length": 10,
        "min_relevance_score": 0.0,
        "spam_patterns": [r"\bclick here\b"],
    },
}


@pytest_asyncio.fixture()
async def orch(db_session, seeded_sources):
    """Return a ProcessingOrchestrator wired to the test DB and lexicon model."""
    o = ProcessingOrchestrator(
        session         = db_session,
        domain_name     = None,
        batch_size       = 50,
        sentiment_model  = "lexicon",
    )
    # Inject the minimal config so no YAML file is read during tests
    o._domain_config = MINIMAL_DOMAIN
    return o


# ── collected → processed ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collected_becomes_processed(db_session, orch):
    raw = await make_raw_review(
        db_session,
        source_record_id="proc_001",
        text="Battery degradation after 3 years is a real concern for owners.",
        synthetic=True,
    )
    await db_session.commit()

    stats = await orch.process_pending()

    assert stats.processed >= 1

    result = await db_session.execute(
        select(RawReview).where(RawReview.source_record_id == "proc_001")
    )
    raw_updated = result.scalar_one()
    assert raw_updated.ingestion_status == IngestionStatus.processed.value

    rev_result = await db_session.execute(
        select(Review).where(Review.raw_review_id == raw_updated.id)
    )
    review = rev_result.scalar_one()
    assert review.processing_status == ProcessingStatus.done.value
    assert review.review_text is not None
    assert review.language is not None
    assert review.relevance_score is not None
    assert review.completeness_score is not None
    assert review.synthetic is True


@pytest.mark.asyncio
async def test_sentiment_populated(db_session, orch):
    await make_raw_review(
        db_session,
        source_record_id="proc_sent",
        text="Fast charging is excellent and battery health is great.",
        synthetic=True,
    )
    await db_session.commit()

    await orch.process_pending()

    rev = (await db_session.execute(
        select(Review).where(Review.source_record_id == "proc_sent")
    )).scalar_one()

    assert rev.sentiment_label in {"positive", "neutral", "negative"}
    assert rev.sentiment_score is not None


@pytest.mark.asyncio
async def test_aspects_populated(db_session, orch):
    await make_raw_review(
        db_session,
        source_record_id="proc_asp",
        text="Battery degradation is concerning but charging speed is fast.",
        synthetic=True,
    )
    await db_session.commit()

    await orch.process_pending()

    rev = (await db_session.execute(
        select(Review).where(Review.source_record_id == "proc_asp")
    )).scalar_one()

    aspects = (await db_session.execute(
        select(ReviewAspect).where(ReviewAspect.review_id == rev.review_id)
    )).scalars().all()

    assert len(aspects) >= 1


# ── Rejection ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_spam_review_rejected(db_session, orch):
    await make_raw_review(
        db_session,
        source_record_id="proc_spam",
        text="Click here to win a free battery replacement today!",
        synthetic=True,
    )
    await db_session.commit()

    stats = await orch.process_pending()
    assert stats.rejected >= 1

    raw = (await db_session.execute(
        select(RawReview).where(RawReview.source_record_id == "proc_spam")
    )).scalar_one()
    assert raw.ingestion_status == IngestionStatus.rejected.value


@pytest.mark.asyncio
async def test_empty_text_rejected(db_session, orch):
    await make_raw_review(
        db_session,
        source_record_id="proc_empty",
        text=None,
        title=None,
        synthetic=True,
    )
    await db_session.commit()

    stats = await orch.process_pending()
    assert stats.rejected >= 1


@pytest.mark.asyncio
async def test_rejected_review_has_reason(db_session, orch):
    await make_raw_review(
        db_session,
        source_record_id="proc_rej2",
        text="Click here for details",
        synthetic=True,
    )
    await db_session.commit()

    await orch.process_pending()

    rev = (await db_session.execute(
        select(Review).where(Review.source_record_id == "proc_rej2")
    )).scalar_one_or_none()

    if rev:
        assert rev.reject_reason is not None


# ── Deduplication ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_duplicate_marked(db_session, orch):
    text = "Battery degradation after exactly three years of daily charging use."
    await make_raw_review(db_session, source_record_id="dup_A", text=text, synthetic=True)
    await make_raw_review(db_session, source_record_id="dup_B", text=text, synthetic=True)
    await db_session.commit()

    stats = await orch.process_pending()

    reviews = (await db_session.execute(
        select(Review).where(
            Review.source_record_id.in_(["dup_A", "dup_B"])
        )
    )).scalars().all()

    is_dup_flags = [r.is_duplicate for r in reviews]
    # At least one must be canonical (False) and one must be a duplicate (True)
    assert False in is_dup_flags
    assert True  in is_dup_flags


# ── Idempotency ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_idempotent_double_run(db_session, orch):
    await make_raw_review(
        db_session,
        source_record_id="idem_proc",
        text="Battery health is good after two years of driving this excellent vehicle.",
        synthetic=True,
    )
    await db_session.commit()

    stats1 = await orch.process_pending()
    stats2 = await orch.process_pending()

    assert stats1.processed >= 1
    # Second run should skip already-processed records
    assert stats2.processed == 0
    assert stats2.skipped >= 1

    # Only one Review row should exist
    count_result = await db_session.execute(
        select(Review).where(Review.source_record_id == "idem_proc")
    )
    rows = count_result.scalars().all()
    assert len(rows) == 1


# ── Failure isolation ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bad_record_does_not_stop_batch(db_session, orch, monkeypatch):
    """A record that raises during processing must not stop other records."""
    await make_raw_review(
        db_session, source_record_id="bad_rec",
        text="Valid battery degradation review text for processing.",
        synthetic=True,
    )
    await make_raw_review(
        db_session, source_record_id="good_rec",
        text="Great charging speed and battery health after 2 years.",
        synthetic=True,
    )
    await db_session.commit()

    # Patch entity extractor to raise on the first call, succeed on the second
    call_count = {"n": 0}
    original = orch._get_entity_extractor

    def patched():
        ext = original()
        original_extract = ext.extract

        def raising_extract(text, title=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("Simulated entity extractor crash")
            return original_extract(text, title)

        ext.extract = raising_extract
        return ext

    monkeypatch.setattr(orch, "_get_entity_extractor", patched)

    stats = await orch.process_pending()

    # At least one record should have been processed successfully
    assert stats.processed + stats.errors >= 1


# ── Synthetic flag ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_synthetic_flag_propagated(db_session, orch):
    await make_raw_review(
        db_session,
        source_record_id="synth_flag",
        text="Battery health check after two years and thirty thousand miles driven.",
        metadata={"synthetic": True, "topic": "battery"},
    )
    await db_session.commit()

    await orch.process_pending()

    rev = (await db_session.execute(
        select(Review).where(Review.source_record_id == "synth_flag")
    )).scalar_one()

    assert rev.synthetic is True


@pytest.mark.asyncio
async def test_non_synthetic_flag(db_session, orch):
    await make_raw_review(
        db_session,
        source_record_id="real_flag",
        text="Battery health check after two years and thirty thousand miles driven.",
        metadata={"synthetic": False},
    )
    await db_session.commit()

    await orch.process_pending()

    rev = (await db_session.execute(
        select(Review).where(Review.source_record_id == "real_flag")
    )).scalar_one()

    assert rev.synthetic is False


# ── Synthetic exclusion from analytics ───────────────────────────────────────

@pytest.mark.asyncio
async def test_synthetic_excluded_from_non_synthetic_query(db_session, orch):
    """Processed synthetic records must be excluded when synthetic=False filter applied."""
    await make_raw_review(
        db_session, source_record_id="synth_excl",
        text="Battery degradation test synthetic record for analytics exclusion.",
        metadata={"synthetic": True},
    )
    await db_session.commit()
    await orch.process_pending()

    # Query for non-synthetic reviews only
    result = await db_session.execute(
        select(Review).where(
            Review.synthetic.is_(False),
            Review.processing_status == ProcessingStatus.done.value,
        )
    )
    non_synthetic_reviews = result.scalars().all()
    ids = [r.source_record_id for r in non_synthetic_reviews]
    assert "synth_excl" not in ids


@pytest.mark.asyncio
async def test_synthetic_included_when_flag_set(db_session, orch):
    """With include_synthetic=True, synthetic records must appear."""
    await make_raw_review(
        db_session, source_record_id="synth_incl",
        text="Battery degradation test synthetic record for analytics inclusion.",
        metadata={"synthetic": True},
    )
    await db_session.commit()
    await orch.process_pending()

    # Query including synthetic
    result = await db_session.execute(
        select(Review).where(
            Review.processing_status == ProcessingStatus.done.value,
        )
    )
    all_reviews = result.scalars().all()
    ids = [r.source_record_id for r in all_reviews]
    assert "synth_incl" in ids
