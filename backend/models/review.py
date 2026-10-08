"""
reviews table — one processed record per raw_review.

Raw records are never modified or deleted.  This table is the output of the
processing pipeline and holds: cleaned text, entity extraction, NLP results.

Processing status flow (in sync with raw_reviews.ingestion_status):
    raw_reviews.ingestion_status:  collected → processing → processed | rejected | error
    reviews.processing_status:    pending   → done      | rejected  | error
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class ProcessingStatus(str, PyEnum):
    pending  = "pending"
    done     = "done"
    rejected = "rejected"
    error    = "error"


class Review(Base):
    __tablename__ = "reviews"

    # ── Primary key ───────────────────────────────────────────
    review_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ── Link to raw record (1-to-1) ───────────────────────────
    raw_review_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("raw_reviews.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # ── Denormalised provenance (avoids joins in most queries) ─
    source: Mapped[str]            = mapped_column(String(64),  nullable=False)
    source_record_id: Mapped[str]  = mapped_column(String(256), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Cleaned content ───────────────────────────────────────
    title: Mapped[str | None]       = mapped_column(Text,       nullable=True)
    review_text: Mapped[str | None] = mapped_column(Text,       nullable=True)
    language: Mapped[str | None]    = mapped_column(String(8),  nullable=True)
    rating: Mapped[float | None]    = mapped_column(Float,      nullable=True)

    # ── Entity extraction (NULL when unknown — never guessed) ─
    vehicle_type: Mapped[str | None]  = mapped_column(String(64),  nullable=True)
    manufacturer: Mapped[str | None]  = mapped_column(String(128), nullable=True)
    vehicle_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_year: Mapped[int | None]    = mapped_column(Integer,     nullable=True)
    domain: Mapped[str | None]        = mapped_column(String(64),  nullable=True)

    # ── Review-level sentiment ────────────────────────────────
    sentiment_label: Mapped[str | None]      = mapped_column(String(16), nullable=True)
    sentiment_score: Mapped[float | None]    = mapped_column(Float,      nullable=True)
    sentiment_confidence: Mapped[float | None] = mapped_column(Float,    nullable=True)

    # ── Quality scores ────────────────────────────────────────
    relevance_score:    Mapped[float | None] = mapped_column(Float, nullable=True)
    completeness_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Deduplication ─────────────────────────────────────────
    # SHA-256 of normalised text used as exact-duplicate key.
    duplicate_group_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Processing state & rejection ─────────────────────────
    processing_status: Mapped[str] = mapped_column(
        String(32),
        default=ProcessingStatus.pending.value,
        nullable=False,
    )
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Synthetic flag (copied from raw_reviews.metadata["synthetic"]) ───
    # Excluded from all aggregate endpoints by default (include_synthetic=true to opt-in).
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Engagement signal (upvotes / likes) ───────────────────
    engagement_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ── Timestamps ────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────
    aspects: Mapped[list["ReviewAspect"]] = relationship(  # noqa: F821
        "ReviewAspect",
        back_populates="review",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # ── Indexes ───────────────────────────────────────────────
    __table_args__ = (
        Index("ix_reviews_published_at",     "published_at"),
        Index("ix_reviews_source",           "source"),
        Index("ix_reviews_sentiment_label",  "sentiment_label"),
        Index("ix_reviews_manufacturer",     "manufacturer"),
        Index("ix_reviews_vehicle_model",    "vehicle_model"),
        Index("ix_reviews_is_duplicate",     "is_duplicate"),
        Index("ix_reviews_synthetic",        "synthetic"),
        Index("ix_reviews_processing_status","processing_status"),
        Index("ix_reviews_language",         "language"),
    )

    def __repr__(self) -> str:
        return (
            f"<Review review_id={self.review_id} source={self.source!r} "
            f"status={self.processing_status!r}>"
        )
