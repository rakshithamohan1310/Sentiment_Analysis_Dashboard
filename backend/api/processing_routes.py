"""
Phase 2 API routes — processing triggers and analytics endpoints.

All analytics endpoints:
  - exclude is_duplicate=True rows by default
  - exclude synthetic=True rows by default (override with ?include_synthetic=true)
  - never expose raw_payload or PII
  - use SQL aggregations — no in-memory pandas

Endpoints
---------
POST /api/process/run
GET  /api/processing/status
GET  /api/reviews/options
GET  /api/reviews
GET  /api/sentiment/summary
GET  /api/sentiment/trend
GET  /api/aspects
GET  /api/aspects/{aspect}
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from backend.api.dependencies import get_session
from backend.api.schemas import (
    AspectDetailResponse,
    AspectSummary,
    AspectsResponse,
    ProcessRunRequest,
    ProcessRunResponse,
    ProcessingStatusResponse,
    ReviewOut,
    ReviewOptionsResponse,
    ReviewsResponse,
    SentimentBreakdown,
    SentimentSummaryResponse,
    SentimentTrendResponse,
    TrendPoint,
)
from backend.models.raw_review import IngestionStatus, RawReview
from backend.models.review import ProcessingStatus, Review
from backend.models.review_aspect import ReviewAspect

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Shared filter builder ─────────────────────────────────────────────────────

def _base_review_filters(
    include_synthetic: bool,
    exclude_duplicates: bool = True,
) -> list:
    filters = [Review.processing_status == ProcessingStatus.done.value]
    if not include_synthetic:
        filters.append(Review.synthetic.is_(False))
    if exclude_duplicates:
        filters.append(Review.is_duplicate.is_(False))
    return filters


_WHEEL_CATEGORIES = {"2W", "3W", "4W"}


def _text_filter(value: Optional[str]) -> Optional[str]:
    """Blank query text means the filter is unset."""
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _category_filter(value: Optional[str]) -> Optional[str]:
    """Normalize 2W/3W/4W. Any other text stays unmatched and returns no rows."""
    cleaned = _text_filter(value)
    if cleaned is None:
        return None
    upper = cleaned.upper()
    if upper in _WHEEL_CATEGORIES:
        return upper
    return cleaned


def _scoped_filters(
    include_synthetic: bool,
    *,
    source: Optional[str] = None,
    vehicle_type: Optional[str] = None,
    manufacturer: Optional[str] = None,
    vehicle_model: Optional[str] = None,
    vehicle_category: Optional[str] = None,
    sentiment: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    exclude_duplicates: bool = True,
) -> list:
    """Filters already supported by GET /api/reviews, reused by aggregates.

    manufacturer and vehicle_model match the stored review columns.
    vehicle_type remains body style (SUV, Sedan, and so on), not 2W/3W/4W.
    State/UT is not applied: reviews have no location column.
    """
    filters = _base_review_filters(include_synthetic, exclude_duplicates)
    if source:
        filters.append(Review.source == source.lower().strip())
    if vehicle_type:
        filters.append(Review.vehicle_type == vehicle_type.strip())
    manufacturer_name = _text_filter(manufacturer)
    if manufacturer_name:
        filters.append(Review.manufacturer == manufacturer_name)
    model_name = _text_filter(vehicle_model)
    if model_name:
        filters.append(Review.vehicle_model == model_name)
    category_name = _category_filter(vehicle_category)
    if category_name:
        filters.append(Review.vehicle_category == category_name)
    if sentiment:
        filters.append(Review.sentiment_label == sentiment.lower().strip())
    if date_from:
        filters.append(Review.published_at >= date_from)
    if date_to:
        filters.append(Review.published_at <= date_to)
    return filters


async def _distinct_column(session: AsyncSession, column, filters: list) -> list[str]:
    result = await session.execute(
        select(column)
        .where(and_(*filters, column.is_not(None), column != ""))
        .distinct()
        .order_by(column)
    )
    return [row[0] for row in result.fetchall()]


def _sentiment_breakdown(pos: int, neu: int, neg: int) -> "SentimentBreakdown":
    total = pos + neu + neg
    def pct(n: int) -> float:
        return round(100.0 * n / total, 2) if total else 0.0
    return SentimentBreakdown(
        positive_count=pos, neutral_count=neu, negative_count=neg, total=total,
        positive_pct=pct(pos), neutral_pct=pct(neu), negative_pct=pct(neg),
    )


# ── POST /api/process/run ─────────────────────────────────────────────────────

@router.post(
    "/process/run",
    response_model=ProcessRunResponse,
    summary="Run Phase 2 processing pipeline over pending raw reviews",
    tags=["processing"],
)
async def run_processing(
    body: ProcessRunRequest,
    session: AsyncSession = Depends(get_session),
) -> ProcessRunResponse:
    """
    Processes all raw_reviews with ingestion_status='collected'.
    Safe to run multiple times — already-processed records are skipped.
    """
    from backend.processing.orchestrator import ProcessingOrchestrator

    orch = ProcessingOrchestrator(
        session         = session,
        domain_name     = body.domain_config,
        batch_size      = body.batch_size,
        sentiment_model = body.sentiment_model,
    )
    stats = await orch.process_pending()
    return ProcessRunResponse(
        processed  = stats.processed,
        rejected   = stats.rejected,
        duplicates = stats.duplicates,
        errors     = stats.errors,
        skipped    = stats.skipped,
        summary    = stats.summary(),
    )


# ── GET /api/processing/status ────────────────────────────────────────────────

@router.get(
    "/processing/status",
    response_model=ProcessingStatusResponse,
    summary="Count raw reviews by ingestion status",
    tags=["processing"],
)
async def processing_status(
    session: AsyncSession = Depends(get_session),
) -> ProcessingStatusResponse:
    result = await session.execute(
        select(
            RawReview.ingestion_status,
            func.count(RawReview.id).label("cnt"),
        ).group_by(RawReview.ingestion_status)
    )
    counts = {row[0]: row[1] for row in result.fetchall()}
    total  = sum(counts.values())
    return ProcessingStatusResponse(
        total_raw  = total,
        collected  = counts.get(IngestionStatus.collected.value,  0),
        processing = counts.get(IngestionStatus.processing.value, 0),
        processed  = counts.get(IngestionStatus.processed.value,  0),
        rejected   = counts.get(IngestionStatus.rejected.value,   0),
        error      = counts.get(IngestionStatus.error.value,      0),
    )


# ── GET /api/reviews/options ──────────────────────────────────────────────────

@router.get(
    "/reviews/options",
    response_model=ReviewOptionsResponse,
    summary="Distinct stored manufacturers and vehicle models",
    tags=["reviews"],
)
async def review_options(
    include_synthetic: bool               = Query(False),
    source:            Optional[str]      = Query(None),
    manufacturer:      Optional[str]      = Query(None),
    vehicle_model:     Optional[str]      = Query(None),
    vehicle_category:  Optional[str]      = Query(None),
    date_from:         Optional[datetime] = Query(None),
    date_to:           Optional[datetime] = Query(None),
    session:           AsyncSession       = Depends(get_session),
) -> ReviewOptionsResponse:
    """Values the dashboard can offer. Null and blank names are omitted.

    A selected manufacturer narrows the model list. A selected model narrows
    the manufacturer list. Sentiment is not applied, so the dropdowns stay
    stable while the sentiment chart still shows all three classes.
    """
    shared = dict(
        source=source,
        date_from=date_from,
        date_to=date_to,
        vehicle_category=vehicle_category,
    )
    manufacturers = await _distinct_column(
        session,
        Review.manufacturer,
        _scoped_filters(
            include_synthetic,
            vehicle_model=vehicle_model,
            **shared,
        ),
    )
    vehicle_models = await _distinct_column(
        session,
        Review.vehicle_model,
        _scoped_filters(
            include_synthetic,
            manufacturer=manufacturer,
            **shared,
        ),
    )
    return ReviewOptionsResponse(
        manufacturers=manufacturers,
        vehicle_models=vehicle_models,
    )


# ── GET /api/reviews ──────────────────────────────────────────────────────────

@router.get(
    "/reviews",
    response_model=ReviewsResponse,
    summary="Query processed reviews with filters",
    tags=["reviews"],
)
async def list_reviews(
    source:            Optional[str]      = Query(None),
    category:          Optional[str]      = Query(None, description="Aspect category filter"),
    aspect:            Optional[str]      = Query(None, description="Aspect name filter"),
    sentiment:         Optional[str]      = Query(None, description="positive|neutral|negative"),
    manufacturer:      Optional[str]      = Query(None),
    vehicle_model:     Optional[str]      = Query(None),
    vehicle_category:  Optional[str]      = Query(None),
    vehicle_type:      Optional[str]      = Query(None),
    date_from:         Optional[datetime] = Query(None),
    date_to:           Optional[datetime] = Query(None),
    include_synthetic: bool               = Query(False),
    limit:             int                = Query(50, ge=1, le=500),
    offset:            int                = Query(0, ge=0),
    session:           AsyncSession       = Depends(get_session),
) -> ReviewsResponse:
    filters = _scoped_filters(
        include_synthetic,
        source=source,
        vehicle_type=vehicle_type,
        manufacturer=manufacturer,
        vehicle_model=vehicle_model,
        vehicle_category=vehicle_category,
        sentiment=sentiment,
        date_from=date_from,
        date_to=date_to,
    )

    # Aspect filters require a join
    if category or aspect:
        aspect_filters = []
        if category:
            aspect_filters.append(ReviewAspect.category == category)
        if aspect:
            aspect_filters.append(ReviewAspect.aspect == aspect)
        q = (
            select(Review)
            .options(noload(Review.aspects))
            .join(ReviewAspect, ReviewAspect.review_id == Review.review_id)
            .where(and_(*filters, *aspect_filters))
            .distinct()
        )
        count_q = (
            select(func.count(Review.review_id.distinct()))
            .join(ReviewAspect, ReviewAspect.review_id == Review.review_id)
            .where(and_(*filters, *aspect_filters))
        )
    else:
        q       = select(Review).options(noload(Review.aspects)).where(and_(*filters))
        count_q = select(func.count()).select_from(Review).where(and_(*filters))

    total_result = await session.execute(count_q)
    total = total_result.scalar_one()

    q = q.order_by(Review.published_at.desc().nullslast()).limit(limit).offset(offset)
    result = await session.execute(q)
    rows = result.scalars().unique().all()

    # Eager-load aspects for response
    items = []
    for r in rows:
        asp_result = await session.execute(
            select(ReviewAspect).where(ReviewAspect.review_id == r.review_id)
        )
        asps = asp_result.scalars().all()
        out = ReviewOut.model_validate(r)
        out.aspects = [
            __import__("backend.api.schemas", fromlist=["ReviewAspectOut"])
            .ReviewAspectOut.model_validate(a)
            for a in asps
        ]
        items.append(out)

    return ReviewsResponse(total=total, limit=limit, offset=offset, items=items)


# ── GET /api/sentiment/summary ────────────────────────────────────────────────

@router.get(
    "/sentiment/summary",
    response_model=SentimentSummaryResponse,
    summary="Aggregate sentiment counts across all processed reviews",
    tags=["analytics"],
)
async def sentiment_summary(
    include_synthetic: bool               = Query(False),
    source:            Optional[str]      = Query(None),
    vehicle_type:      Optional[str]      = Query(None),
    manufacturer:      Optional[str]      = Query(None),
    vehicle_model:     Optional[str]      = Query(None),
    vehicle_category:  Optional[str]      = Query(None),
    date_from:         Optional[datetime] = Query(None),
    date_to:           Optional[datetime] = Query(None),
    session: AsyncSession   = Depends(get_session),
) -> SentimentSummaryResponse:
    # Sentiment is omitted on purpose: this response is the class breakdown.
    filters = _scoped_filters(
        include_synthetic,
        source=source,
        vehicle_type=vehicle_type,
        manufacturer=manufacturer,
        vehicle_model=vehicle_model,
        vehicle_category=vehicle_category,
        date_from=date_from,
        date_to=date_to,
    )

    result = await session.execute(
        select(
            Review.source,
            Review.sentiment_label,
            func.count(Review.review_id).label("cnt"),
        )
        .where(and_(*filters))
        .group_by(Review.source, Review.sentiment_label)
    )
    rows = result.fetchall()

    # Aggregate
    overall = {"positive": 0, "neutral": 0, "negative": 0}
    by_source: dict[str, dict[str, int]] = {}

    for source, label, cnt in rows:
        l = (label or "neutral").lower()
        if l not in overall:
            l = "neutral"
        overall[l] += cnt
        if source not in by_source:
            by_source[source] = {"positive": 0, "neutral": 0, "negative": 0}
        by_source[source][l] += cnt

    return SentimentSummaryResponse(
        overall=_sentiment_breakdown(
            overall["positive"], overall["neutral"], overall["negative"]
        ),
        by_source={
            s: _sentiment_breakdown(v["positive"], v["neutral"], v["negative"])
            for s, v in by_source.items()
        },
        synthetic_excluded=not include_synthetic,
    )


# ── GET /api/sentiment/trend ──────────────────────────────────────────────────

@router.get(
    "/sentiment/trend",
    response_model=SentimentTrendResponse,
    summary="Sentiment trend over time",
    tags=["analytics"],
)
async def sentiment_trend(
    granularity:       str                = Query("month", pattern="^(day|week|month)$"),
    include_synthetic: bool               = Query(False),
    source:            Optional[str]      = Query(None),
    vehicle_type:      Optional[str]      = Query(None),
    manufacturer:      Optional[str]      = Query(None),
    vehicle_model:     Optional[str]      = Query(None),
    vehicle_category:  Optional[str]      = Query(None),
    date_from:         Optional[datetime] = Query(None),
    date_to:           Optional[datetime] = Query(None),
    session: AsyncSession    = Depends(get_session),
) -> SentimentTrendResponse:
    filters = _scoped_filters(
        include_synthetic,
        source=source,
        vehicle_type=vehicle_type,
        manufacturer=manufacturer,
        vehicle_model=vehicle_model,
        vehicle_category=vehicle_category,
        date_from=date_from,
        date_to=date_to,
    )
    filters.append(Review.published_at.isnot(None))

    # Period expression — database-agnostic via Python formatting after fetch
    result = await session.execute(
        select(
            Review.published_at,
            Review.sentiment_label,
            func.count(Review.review_id).label("cnt"),
        )
        .where(and_(*filters))
        .group_by(Review.published_at, Review.sentiment_label)
        .order_by(Review.published_at)
    )
    rows = result.fetchall()

    # Bucket into periods in Python (works on both SQLite and Postgres)
    from collections import defaultdict
    buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"positive": 0, "neutral": 0, "negative": 0}
    )

    def _period(dt: datetime, gran: str) -> str:
        if gran == "day":
            return dt.strftime("%Y-%m-%d")
        if gran == "week":
            return dt.strftime("%G-W%V")
        return dt.strftime("%Y-%m")

    for pub, label, cnt in rows:
        if pub is None:
            continue
        period = _period(pub, granularity)
        l = (label or "neutral").lower()
        if l not in buckets[period]:
            l = "neutral"
        buckets[period][l] += cnt

    points = []
    for period in sorted(buckets):
        b = buckets[period]
        total = b["positive"] + b["neutral"] + b["negative"]
        def pct(n: int) -> float:
            return round(100.0 * n / total, 2) if total else 0.0
        points.append(TrendPoint(
            period         = period,
            total          = total,
            positive_count = b["positive"],
            neutral_count  = b["neutral"],
            negative_count = b["negative"],
            positive_pct   = pct(b["positive"]),
            neutral_pct    = pct(b["neutral"]),
            negative_pct   = pct(b["negative"]),
        ))

    return SentimentTrendResponse(
        granularity        = granularity,
        points             = points,
        synthetic_excluded = not include_synthetic,
    )


# ── GET /api/aspects ──────────────────────────────────────────────────────────

@router.get(
    "/aspects",
    response_model=AspectsResponse,
    summary="All aspects with mention counts and sentiment breakdown",
    tags=["analytics"],
)
async def list_aspects(
    category:          Optional[str]      = Query(None),
    include_synthetic: bool               = Query(False),
    source:            Optional[str]      = Query(None),
    vehicle_type:      Optional[str]      = Query(None),
    manufacturer:      Optional[str]      = Query(None),
    vehicle_model:     Optional[str]      = Query(None),
    vehicle_category:  Optional[str]      = Query(None),
    sentiment:         Optional[str]      = Query(None, description="positive|neutral|negative"),
    date_from:         Optional[datetime] = Query(None),
    date_to:           Optional[datetime] = Query(None),
    session: AsyncSession            = Depends(get_session),
) -> AspectsResponse:
    review_filters = _scoped_filters(
        include_synthetic,
        source=source,
        vehicle_type=vehicle_type,
        manufacturer=manufacturer,
        vehicle_model=vehicle_model,
        vehicle_category=vehicle_category,
        sentiment=sentiment,
        date_from=date_from,
        date_to=date_to,
    )

    asp_filters = [ReviewAspect.review_id == Review.review_id]
    if category:
        asp_filters.append(ReviewAspect.category == category)

    result = await session.execute(
        select(
            ReviewAspect.category,
            ReviewAspect.aspect,
            ReviewAspect.sentiment_label,
            func.count(ReviewAspect.id).label("cnt"),
        )
        .join(Review, ReviewAspect.review_id == Review.review_id)
        .where(and_(*review_filters, *asp_filters))
        .group_by(
            ReviewAspect.category,
            ReviewAspect.aspect,
            ReviewAspect.sentiment_label,
        )
    )
    rows = result.fetchall()

    # Aggregate per (category, aspect)
    from collections import defaultdict
    agg: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"positive": 0, "neutral": 0, "negative": 0}
    )
    for cat, asp, label, cnt in rows:
        l = (label or "neutral").lower()
        if l not in agg[(cat, asp)]:
            l = "neutral"
        agg[(cat, asp)][l] += cnt

    aspects_out = []
    for (cat, asp), v in sorted(agg.items()):
        total = v["positive"] + v["neutral"] + v["negative"]
        def pct(n: int) -> float:
            return round(100.0 * n / total, 2) if total else 0.0
        aspects_out.append(AspectSummary(
            category          = cat,
            aspect            = asp,
            mention_count     = total,
            positive_count    = v["positive"],
            neutral_count     = v["neutral"],
            negative_count    = v["negative"],
            positive_pct      = pct(v["positive"]),
            neutral_pct       = pct(v["neutral"]),
            negative_pct      = pct(v["negative"]),
            negative_aspect_pct = pct(v["negative"]),
        ))

    return AspectsResponse(aspects=aspects_out, synthetic_excluded=not include_synthetic)


# ── GET /api/aspects/{aspect} ─────────────────────────────────────────────────

@router.get(
    "/aspects/{aspect}",
    response_model=AspectDetailResponse,
    summary="Detail for a specific aspect including recent examples",
    tags=["analytics"],
)
async def aspect_detail(
    aspect:            str,
    include_synthetic: bool               = Query(False),
    source:            Optional[str]      = Query(None),
    vehicle_type:      Optional[str]      = Query(None),
    manufacturer:      Optional[str]      = Query(None),
    vehicle_model:     Optional[str]      = Query(None),
    vehicle_category:  Optional[str]      = Query(None),
    sentiment:         Optional[str]      = Query(None, description="positive|neutral|negative"),
    date_from:         Optional[datetime] = Query(None),
    date_to:           Optional[datetime] = Query(None),
    limit:             int                = Query(10, ge=1, le=50),
    session: AsyncSession   = Depends(get_session),
) -> AspectDetailResponse:
    review_filters = _scoped_filters(
        include_synthetic,
        source=source,
        vehicle_type=vehicle_type,
        manufacturer=manufacturer,
        vehicle_model=vehicle_model,
        vehicle_category=vehicle_category,
        sentiment=sentiment,
        date_from=date_from,
        date_to=date_to,
    )

    result = await session.execute(
        select(
            ReviewAspect.category,
            ReviewAspect.aspect,
            ReviewAspect.sentiment_label,
            func.count(ReviewAspect.id).label("cnt"),
        )
        .join(Review, ReviewAspect.review_id == Review.review_id)
        .where(
            and_(
                *review_filters,
                ReviewAspect.aspect == aspect,
            )
        )
        .group_by(
            ReviewAspect.category,
            ReviewAspect.aspect,
            ReviewAspect.sentiment_label,
        )
    )
    rows = result.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"Aspect {aspect!r} not found.")

    category = rows[0][0]
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    for _, _, label, cnt in rows:
        l = (label or "neutral").lower()
        if l not in counts:
            l = "neutral"
        counts[l] += cnt

    total = sum(counts.values())
    def pct(n: int) -> float:
        return round(100.0 * n / total, 2) if total else 0.0

    summary = AspectSummary(
        category          = category,
        aspect            = aspect,
        mention_count     = total,
        positive_count    = counts["positive"],
        neutral_count     = counts["neutral"],
        negative_count    = counts["negative"],
        positive_pct      = pct(counts["positive"]),
        neutral_pct       = pct(counts["neutral"]),
        negative_pct      = pct(counts["negative"]),
        negative_aspect_pct = pct(counts["negative"]),
    )

    # Recent examples
    ex_result = await session.execute(
        select(
            ReviewAspect.matched_text,
            ReviewAspect.sentiment_label,
            Review.source,
            Review.published_at,
        )
        .join(Review, ReviewAspect.review_id == Review.review_id)
        .where(and_(*review_filters, ReviewAspect.aspect == aspect))
        .order_by(Review.published_at.desc().nullslast())
        .limit(limit)
    )
    examples = [
        {
            "matched_text":    row[0],
            "sentiment_label": row[1],
            "source":          row[2],
            "published_at":    row[3].isoformat() if row[3] else None,
        }
        for row in ex_result.fetchall()
    ]

    return AspectDetailResponse(
        aspect             = aspect,
        summary            = summary,
        recent_examples    = examples,
        synthetic_excluded = not include_synthetic,
    )
