"""
FastAPI route handlers for Phase 1 (data collection only).

Endpoints:
  POST /api/collect/{source}      – trigger a collection run
  GET  /api/collection/status     – list recent collection runs
  GET  /api/raw-reviews           – query raw collected reviews
  GET  /health                    – liveness + DB check
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_session
from backend.api.domain_config import load_collector_config, list_available_domains
from backend.api.schemas import (
    CollectRequest,
    CollectResponse,
    CollectionRunOut,
    CollectionStatusResponse,
    HealthResponse,
    RawReviewOut,
    RawReviewsResponse,
)
from backend.collectors.base import CollectorConfig
from backend.collectors.orchestrator import CollectionOrchestrator, build_collector_registry
from backend.models.collection_run import CollectionRun
from backend.models.raw_review import RawReview

logger = logging.getLogger(__name__)
router = APIRouter()


# ── POST /api/collect/{source} ────────────────────────────────────────────────

@router.post(
    "/collect/{source}",
    response_model=CollectResponse,
    summary="Trigger a collection run for a single source",
    tags=["collection"],
)
async def trigger_collection(
    source: str,
    body: CollectRequest,
    session: AsyncSession = Depends(get_session),
) -> CollectResponse:
    """
    Start a collection run for `source` (reddit | youtube | demo).

    - If `domain_config` is provided, keywords/subreddits are loaded from
      `config/domains/<domain_config>.yaml` (any body overrides take precedence).
    - If `domain_config` is omitted and `keywords` is empty the run proceeds
      with no keyword filter (adapter-dependent behaviour).
    - Demo mode always works; Reddit/YouTube require credentials in env vars.
    """
    source = source.lower().strip()
    valid_sources = {"reddit", "youtube", "demo"}
    if source not in valid_sources:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown source '{source}'. Valid sources: {sorted(valid_sources)}",
        )

    # Build collector config
    if body.domain_config:
        try:
            config = load_collector_config(
                body.domain_config,
                overrides={
                    "keywords": body.keywords or None,
                    "subreddits": body.subreddits or None,
                    "date_from": body.date_from,
                    "date_to": body.date_to,
                    "max_records": body.max_records,
                },
            )
        except FileNotFoundError as exc:
            available = list_available_domains()
            raise HTTPException(
                status_code=404,
                detail=f"{exc}. Available domains: {available}",
            )
    else:
        config = CollectorConfig(
            keywords=body.keywords,
            subreddits=body.subreddits,
            date_from=body.date_from,
            date_to=body.date_to,
            max_records=body.max_records,
        )

    collectors = build_collector_registry(enabled_sources=[source])
    if not collectors:
        raise HTTPException(status_code=404, detail=f"No collector found for source '{source}'")

    orchestrator = CollectionOrchestrator(session, collectors)
    stats_list = await orchestrator.run_all(config)

    if not stats_list:
        # Adapter was unavailable (missing credentials)
        raise HTTPException(
            status_code=503,
            detail=(
                f"Adapter '{source}' is not available. "
                "Check that credentials are configured in environment variables."
            ),
        )

    stats = stats_list[0]

    # Fetch the newly created run record for response
    result = await session.execute(
        select(CollectionRun)
        .where(CollectionRun.source == source)
        .order_by(CollectionRun.run_id.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=500, detail="Collection run record not found after execution")

    return CollectResponse(
        run_id=run.run_id,
        source=run.source,
        status=run.status,
        records_found=run.records_found,
        records_inserted=run.records_inserted,
        duplicates=run.duplicates,
        rejected=run.rejected,
        errors=run.errors,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


# ── GET /api/collection/status ────────────────────────────────────────────────

@router.get(
    "/collection/status",
    response_model=CollectionStatusResponse,
    summary="List recent collection runs",
    tags=["collection"],
)
async def collection_status(
    source: Optional[str] = Query(None, description="Filter by source name"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> CollectionStatusResponse:
    """Returns recent collection runs, newest first."""
    q = select(CollectionRun).order_by(CollectionRun.run_id.desc())
    count_q = select(func.count()).select_from(CollectionRun)

    if source:
        q = q.where(CollectionRun.source == source.lower())
        count_q = count_q.where(CollectionRun.source == source.lower())

    total_result = await session.execute(count_q)
    total = total_result.scalar_one()

    result = await session.execute(q.limit(limit).offset(offset))
    runs = result.scalars().all()

    return CollectionStatusResponse(
        total_runs=total,
        runs=[CollectionRunOut.model_validate(r) for r in runs],
    )


# ── GET /api/raw-reviews ──────────────────────────────────────────────────────

@router.get(
    "/raw-reviews",
    response_model=RawReviewsResponse,
    summary="Query collected raw reviews",
    tags=["reviews"],
)
async def list_raw_reviews(
    source: Optional[str] = Query(None, description="Filter by source (reddit | youtube | demo)"),
    date_from: Optional[datetime] = Query(None, description="Filter: published_at >= date_from"),
    date_to: Optional[datetime] = Query(None, description="Filter: published_at <= date_to"),
    ingestion_status: Optional[str] = Query(None, description="Filter by ingestion_status"),
    language: Optional[str] = Query(None, description="Filter by language code (e.g. 'en')"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> RawReviewsResponse:
    """
    Returns raw reviews with optional filters.
    raw_payload is excluded from the response to avoid leaking large blobs.
    """
    q = select(RawReview).order_by(RawReview.collected_at.desc())
    count_q = select(func.count()).select_from(RawReview)

    filters = []
    if source:
        filters.append(RawReview.source == source.lower())
    if date_from:
        filters.append(RawReview.published_at >= date_from)
    if date_to:
        filters.append(RawReview.published_at <= date_to)
    if ingestion_status:
        filters.append(RawReview.ingestion_status == ingestion_status)
    if language:
        filters.append(RawReview.language == language.lower())

    if filters:
        from sqlalchemy import and_
        q = q.where(and_(*filters))
        count_q = count_q.where(and_(*filters))

    total_result = await session.execute(count_q)
    total = total_result.scalar_one()

    result = await session.execute(q.limit(limit).offset(offset))
    reviews = result.scalars().all()

    return RawReviewsResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[RawReviewOut.model_validate(r) for r in reviews],
    )


# ── GET /health ───────────────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness and DB connectivity check",
    tags=["ops"],
)
async def health(session: AsyncSession = Depends(get_session)) -> HealthResponse:
    """Returns 200 if the API is running and the DB is reachable."""
    db_status = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("Health check DB query failed: %s", exc)
        db_status = f"error: {exc}"

    return HealthResponse(status="ok", database=db_status)
