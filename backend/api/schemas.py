"""
Request/response Pydantic schemas for the FastAPI layer.
These are separate from the SQLAlchemy ORM models to keep layers decoupled.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── POST /api/collect/{source} ────────────────────────────────────────────────

class CollectRequest(BaseModel):
    """Body for triggering a collection run against a single source."""
    keywords: list[str] = Field(
        default_factory=list,
        description="Keywords to search for. Overrides domain config if provided.",
    )
    subreddits: list[str] = Field(
        default_factory=list,
        description="(Reddit only) Subreddit names to search in.",
    )
    date_from: Optional[datetime] = Field(
        None, description="Only collect items published after this timestamp (UTC)."
    )
    date_to: Optional[datetime] = Field(
        None, description="Only collect items published before this timestamp (UTC)."
    )
    max_records: int = Field(
        500, ge=1, le=10_000, description="Maximum records to collect in this run."
    )
    domain_config: Optional[str] = Field(
        None,
        description=(
            "Domain config name (e.g. 'ev'). Loads keywords/subreddits from "
            "config/domains/<name>.yaml if keywords is empty."
        ),
    )


class CollectResponse(BaseModel):
    run_id: int
    source: str
    status: str
    records_found: int
    records_inserted: int
    duplicates: int
    rejected: int
    errors: int
    started_at: datetime
    completed_at: Optional[datetime]


# ── GET /api/collection/status ────────────────────────────────────────────────

class CollectionRunOut(BaseModel):
    run_id: int
    source: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    records_found: int
    records_inserted: int
    duplicates: int
    rejected: int
    errors: int
    error_detail: Optional[str]

    model_config = {"from_attributes": True}


class CollectionStatusResponse(BaseModel):
    total_runs: int
    runs: list[CollectionRunOut]


# ── GET /api/raw-reviews ──────────────────────────────────────────────────────

class RawReviewOut(BaseModel):
    id: int
    source: str
    source_record_id: str
    source_url: Optional[str]
    collected_at: datetime
    published_at: Optional[datetime]
    author_id_hash: Optional[str]
    title: Optional[str]
    text: Optional[str]
    rating: Optional[float]
    language: Optional[str]
    metadata: Optional[dict[str, Any]]
    ingestion_status: str

    model_config = {"from_attributes": True}


class RawReviewsResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[RawReviewOut]


# ── GET /health ───────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    database: str
    version: str = "1.0.0"


# ═══════════════════════════════════════════════════════════════
# Phase 2 — Processing & Analytics schemas
# ═══════════════════════════════════════════════════════════════

# ── POST /api/process/run ─────────────────────────────────────────────────────

class ProcessRunRequest(BaseModel):
    domain_config: Optional[str] = Field(
        None,
        description="Domain name (e.g. 'ev'). Uses first available domain if omitted.",
    )
    batch_size: int = Field(100, ge=1, le=1000)
    sentiment_model: Optional[str] = Field(
        None,
        description="Override sentiment model. Pass 'lexicon' to skip transformer.",
    )


class ProcessRunResponse(BaseModel):
    processed:  int
    rejected:   int
    duplicates: int
    errors:     int
    skipped:    int
    summary:    str


# ── GET /api/processing/status ────────────────────────────────────────────────

class ProcessingStatusResponse(BaseModel):
    total_raw:       int
    collected:       int   # pending Phase 2
    processing:      int   # in-flight (interrupted runs)
    processed:       int
    rejected:        int
    error:           int


# ── GET /api/reviews ──────────────────────────────────────────────────────────

class ReviewAspectOut(BaseModel):
    id:              int
    category:        str
    aspect:          str
    sentiment_label: Optional[str]
    sentiment_score: Optional[float]
    confidence:      Optional[float]
    matched_text:    Optional[str]

    model_config = {"from_attributes": True}


class ReviewOut(BaseModel):
    review_id:           int
    source:              str
    source_record_id:    str
    published_at:        Optional[datetime]
    title:               Optional[str]
    review_text:         Optional[str]
    language:            Optional[str]
    rating:              Optional[float]
    vehicle_type:        Optional[str]
    manufacturer:        Optional[str]
    vehicle_model:       Optional[str]
    model_year:          Optional[int]
    sentiment_label:     Optional[str]
    sentiment_score:     Optional[float]
    sentiment_confidence:Optional[float]
    relevance_score:     Optional[float]
    completeness_score:  Optional[float]
    is_duplicate:        bool
    processing_status:   str
    reject_reason:       Optional[str]
    synthetic:           bool
    engagement_count:    int
    aspects:             list[ReviewAspectOut] = []

    model_config = {"from_attributes": True}


class ReviewsResponse(BaseModel):
    total:  int
    limit:  int
    offset: int
    items:  list[ReviewOut]


# ── GET /api/sentiment/summary ────────────────────────────────────────────────

class SentimentBreakdown(BaseModel):
    positive_count:  int
    neutral_count:   int
    negative_count:  int
    total:           int
    positive_pct:    float
    neutral_pct:     float
    negative_pct:    float


class SentimentSummaryResponse(BaseModel):
    overall:          SentimentBreakdown
    by_source:        dict[str, SentimentBreakdown]
    synthetic_excluded: bool


# ── GET /api/sentiment/trend ──────────────────────────────────────────────────

class TrendPoint(BaseModel):
    period:          str    # "2024-01", "2024-W03", "2024-01-15"
    total:           int
    positive_count:  int
    neutral_count:   int
    negative_count:  int
    positive_pct:    float
    neutral_pct:     float
    negative_pct:    float


class SentimentTrendResponse(BaseModel):
    granularity:        str   # "day" | "week" | "month"
    points:             list[TrendPoint]
    synthetic_excluded: bool


# ── GET /api/aspects  &  GET /api/aspects/{aspect} ────────────────────────────

class AspectSummary(BaseModel):
    category:        str
    aspect:          str
    mention_count:   int
    positive_count:  int
    neutral_count:   int
    negative_count:  int
    positive_pct:    float
    neutral_pct:     float
    negative_pct:    float
    negative_aspect_pct: float   # negative / total_mentions


class AspectsResponse(BaseModel):
    aspects:            list[AspectSummary]
    synthetic_excluded: bool


class AspectDetailResponse(BaseModel):
    aspect:             str
    summary:            AspectSummary
    recent_examples:    list[dict[str, Any]]   # {matched_text, sentiment_label, source}
    synthetic_excluded: bool
