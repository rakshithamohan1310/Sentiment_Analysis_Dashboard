"""
Phase 2 processing orchestrator.

Reads raw_reviews with ingestion_status='collected', runs each record through
the full NLP pipeline, and writes results to reviews + review_aspects.

Pipeline order per record
--------------------------
1.  Mark raw record as processing   (ingestion_status → 'processing')
2.  Language detection
3.  Text cleaning
4.  Quality / relevance filtering   → reject if fails
5.  Deduplication                   → mark is_duplicate / duplicate_group_id
6.  Entity extraction
7.  Aspect extraction
8.  Review-level sentiment
9.  Aspect-level sentiment          (scored per matched clause, done inside AspectExtractor)
10. Save Review row                 (upsert-safe: skip if already exists)
11. Save ReviewAspect rows
12. Mark raw record as processed    (ingestion_status → 'processed')

Idempotency
-----------
- A raw record already marked 'processing' or 'processed' is skipped.
- Existing text hashes are loaded at start so re-runs don't create duplicate
  Review rows.
- If a Review row for a raw_review_id already exists it is not inserted again.

Isolation
---------
- Any exception for a single record is caught, logged, and the record is
  marked 'error'.  The batch always continues.

Synthetic flag
--------------
Copied from raw_reviews.metadata_["synthetic"].  These records are excluded
from analytics endpoints by default.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.raw_review import IngestionStatus, RawReview
from backend.models.review import ProcessingStatus, Review
from backend.models.review_aspect import ReviewAspect

logger = logging.getLogger(__name__)


# ── Per-run stats ─────────────────────────────────────────────────────────────

@dataclass
class ProcessingStats:
    processed:  int = 0
    rejected:   int = 0
    duplicates: int = 0
    errors:     int = 0
    skipped:    int = 0   # already processed in a previous run

    def summary(self) -> str:
        total = self.processed + self.rejected + self.duplicates + self.errors + self.skipped
        return (
            f"Phase 2 processing summary\n"
            f"  Total examined : {total}\n"
            f"  Processed      : {self.processed}\n"
            f"  Rejected       : {self.rejected}\n"
            f"  Duplicates     : {self.duplicates}\n"
            f"  Errors         : {self.errors}\n"
            f"  Skipped        : {self.skipped}\n"
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _mark_raw(
    session: AsyncSession,
    raw: RawReview,
    status: str,
) -> None:
    raw.ingestion_status = status
    session.add(raw)


async def _load_existing_hashes(session: AsyncSession) -> dict[str, int]:
    """Return {text_hash: raw_review_id} for all rows already in reviews."""
    result = await session.execute(
        select(Review.duplicate_group_id, Review.raw_review_id).where(
            Review.duplicate_group_id.isnot(None)
        )
    )
    return {row[0]: row[1] for row in result.fetchall() if row[0]}


async def _review_exists(session: AsyncSession, raw_review_id: int) -> bool:
    result = await session.execute(
        select(Review.review_id).where(Review.raw_review_id == raw_review_id).limit(1)
    )
    return result.scalar_one_or_none() is not None


# ── Main orchestrator ─────────────────────────────────────────────────────────

class ProcessingOrchestrator:
    """
    Runs the Phase 2 NLP pipeline over pending raw_reviews.

    Parameters
    ----------
    session         : SQLAlchemy async session (committed by this class).
    domain_name     : Name of the domain YAML to load (e.g. ``"ev"``).
                      If None, the first available domain is used.
    batch_size      : How many raw_reviews to load per DB query.
    sentiment_model : Override the model name (pass ``"lexicon"`` in tests).
    """

    def __init__(
        self,
        session: AsyncSession,
        domain_name: Optional[str] = None,
        batch_size: int = 100,
        sentiment_model: Optional[str] = None,
    ) -> None:
        self._session        = session
        self._batch_size     = batch_size
        self._sentiment_model = sentiment_model
        self._domain_config: dict[str, Any] = {}
        self._domain_name    = domain_name

        # Lazy-initialised components
        self._filter      = None
        self._entity_ext  = None
        self._aspect_ext  = None
        self._sentiment   = None

    # ── Lazy component loading ───────────────────────────────

    def _get_domain_config(self) -> dict[str, Any]:
        if not self._domain_config:
            from backend.api.domain_config import _load_yaml, list_available_domains
            name = self._domain_name or (list_available_domains() or [None])[0]
            if name:
                self._domain_config = _load_yaml(name)
        return self._domain_config

    def _get_filter(self):
        if self._filter is None:
            from backend.processing.filter import QualityFilter
            self._filter = QualityFilter(self._get_domain_config())
        return self._filter

    def _get_entity_extractor(self):
        if self._entity_ext is None:
            from backend.processing.entity import EntityExtractor
            gazetteer = self._get_domain_config().get("gazetteer", {})
            self._entity_ext = EntityExtractor(gazetteer)
        return self._entity_ext

    def _get_aspect_extractor(self):
        if self._aspect_ext is None:
            from backend.nlp.aspects import AspectExtractor
            aspect_cfg = self._get_domain_config().get("aspect_config", {})
            self._aspect_ext = AspectExtractor(
                aspect_config      = aspect_cfg,
                sentiment_analyzer = self._get_sentiment(),
            )
        return self._aspect_ext

    def _get_sentiment(self):
        if self._sentiment is None:
            from backend.nlp.sentiment import get_sentiment_analyzer
            self._sentiment = get_sentiment_analyzer(self._sentiment_model)
        return self._sentiment

    # ── Public entry point ───────────────────────────────────

    async def process_pending(self) -> ProcessingStats:
        """
        Process all raw_reviews with ingestion_status='collected' in batches.
        Returns a ProcessingStats summary.
        """
        stats = ProcessingStats()

        # Load existing hashes once for cross-batch idempotency
        existing_hashes = await _load_existing_hashes(self._session)
        from backend.processing.dedup import Deduplicator
        from backend.config.settings import get_settings
        settings   = get_settings()
        dedup      = Deduplicator(
            near_dup_threshold = settings.near_duplicate_threshold,
            existing_hashes    = existing_hashes,
        )

        offset = 0
        while True:
            rows = await self._fetch_batch(offset)
            if not rows:
                break

            for raw in rows:
                await self._process_one(raw, dedup, stats)
                # Commit after each record so partial progress is saved
                try:
                    await self._session.commit()
                except Exception as exc:  # noqa: BLE001
                    logger.error("Commit failed for raw_review_id=%s: %s", raw.id, exc)
                    await self._session.rollback()
                    stats.errors += 1

            offset += self._batch_size

        logger.info(stats.summary())
        return stats

    # ── Batch fetch ──────────────────────────────────────────

    async def _fetch_batch(self, offset: int) -> list[RawReview]:
        result = await self._session.execute(
            select(RawReview)
            .where(RawReview.ingestion_status == IngestionStatus.collected.value)
            .order_by(RawReview.id)
            .limit(self._batch_size)
            .offset(offset)
        )
        return list(result.scalars().all())

    # ── Per-record pipeline ──────────────────────────────────

    async def _process_one(
        self,
        raw: RawReview,
        dedup: "Deduplicator",
        stats: ProcessingStats,
    ) -> None:
        """Run the full pipeline for a single raw record."""

        # Skip if already processed in a previous run
        if await _review_exists(self._session, raw.id):
            await _mark_raw(self._session, raw, IngestionStatus.processed.value)
            stats.skipped += 1
            return

        # Mark as in-flight
        await _mark_raw(self._session, raw, IngestionStatus.processing.value)

        try:
            await self._run_pipeline(raw, dedup, stats)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Unhandled error processing raw_review_id=%s: %s", raw.id, exc
            )
            await _mark_raw(self._session, raw, IngestionStatus.error.value)
            stats.errors += 1

    async def _run_pipeline(
        self,
        raw: RawReview,
        dedup: "Deduplicator",
        stats: ProcessingStats,
    ) -> None:
        from backend.nlp.language import detect_language
        from backend.nlp.cleaner import clean_text, compute_completeness_score
        from backend.processing.dedup import compute_text_hash

        # ── 1. Combine source text ───────────────────────────
        raw_text  = raw.text or ""
        raw_title = raw.title or ""

        # ── 2. Language detection ────────────────────────────
        language = detect_language(raw_text or raw_title, existing=raw.language)

        # ── 3. Text cleaning ─────────────────────────────────
        cleaned_title = clean_text(raw_title) if raw_title else None
        cleaned_text  = clean_text(raw_text)  if raw_text  else None
        combined_clean = " ".join(filter(None, [cleaned_title, cleaned_text]))

        # ── 4. Quality filter ────────────────────────────────
        flt = self._get_filter()
        fr  = flt.filter(cleaned_text, cleaned_title)
        completeness = compute_completeness_score(cleaned_title, cleaned_text)

        if not fr.accepted:
            review = Review(
                raw_review_id      = raw.id,
                source             = raw.source,
                source_record_id   = raw.source_record_id,
                published_at       = raw.published_at,
                title              = cleaned_title,
                review_text        = cleaned_text,
                language           = language,
                rating             = raw.rating,
                relevance_score    = fr.relevance_score,
                completeness_score = completeness,
                processing_status  = ProcessingStatus.rejected.value,
                reject_reason      = fr.reject_reason,
                synthetic          = bool((raw.metadata_ or {}).get("synthetic", False)),
                engagement_count   = int((raw.metadata_ or {}).get("upvotes",
                                    (raw.metadata_ or {}).get("like_count", 0)) or 0),
                duplicate_group_id = compute_text_hash(combined_clean or raw.source_record_id),
                is_duplicate       = False,
            )
            self._session.add(review)
            await _mark_raw(self._session, raw, IngestionStatus.rejected.value)
            stats.rejected += 1
            return

        # ── 5. Deduplication ─────────────────────────────────
        dedup_text = combined_clean or raw.source_record_id
        dup_result = dedup.check(raw.id, dedup_text)

        # ── 6. Entity extraction ──────────────────────────────
        entity = self._get_entity_extractor().extract(cleaned_text, cleaned_title)

        # ── 7+8. Sentiment (review-level) ────────────────────
        sent_result = None
        if combined_clean:
            try:
                sent_result = self._get_sentiment().analyze(combined_clean)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Sentiment failed for raw_id=%s: %s", raw.id, exc)

        # ── 9. Aspect extraction (incl. aspect-level sentiment) ─
        aspect_matches = []
        if combined_clean:
            try:
                aspect_matches = self._get_aspect_extractor().extract(
                    cleaned_text, cleaned_title
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Aspect extraction failed for raw_id=%s: %s", raw.id, exc)

        # ── 10. Build Review row ──────────────────────────────
        review = Review(
            raw_review_id        = raw.id,
            source               = raw.source,
            source_record_id     = raw.source_record_id,
            published_at         = raw.published_at,
            title                = cleaned_title,
            review_text          = cleaned_text,
            language             = language,
            rating               = raw.rating,
            vehicle_type         = entity.vehicle_type,
            manufacturer         = entity.manufacturer,
            vehicle_model        = entity.vehicle_model,
            model_year           = entity.model_year,
            domain               = self._domain_name,
            sentiment_label      = sent_result.label      if sent_result else None,
            sentiment_score      = sent_result.score      if sent_result else None,
            sentiment_confidence = sent_result.confidence if sent_result else None,
            relevance_score      = fr.relevance_score,
            completeness_score   = completeness,
            duplicate_group_id   = dup_result.duplicate_group_id,
            is_duplicate         = dup_result.is_duplicate,
            processing_status    = ProcessingStatus.done.value,
            reject_reason        = None,
            synthetic            = bool((raw.metadata_ or {}).get("synthetic", False)),
            engagement_count     = int((raw.metadata_ or {}).get("upvotes",
                                   (raw.metadata_ or {}).get("like_count", 0)) or 0),
        )
        self._session.add(review)
        # flush to get review_id before inserting aspects
        await self._session.flush()

        # ── 11. Save ReviewAspect rows ────────────────────────
        for am in aspect_matches:
            aspect_row = ReviewAspect(
                review_id       = review.review_id,
                category        = am.category,
                aspect          = am.aspect,
                sentiment_label = am.sentiment_label,
                sentiment_score = am.sentiment_score,
                confidence      = am.confidence,
                matched_text    = am.matched_text,
            )
            self._session.add(aspect_row)

        # ── 12. Mark raw as processed ─────────────────────────
        await _mark_raw(self._session, raw, IngestionStatus.processed.value)

        if dup_result.is_duplicate:
            stats.duplicates += 1
        else:
            stats.processed += 1
