"""
raw_reviews table – stores every collected review exactly as received.

Privacy rules enforced here:
  - author_id_hash: salted SHA-256 of the original author identifier (never the raw value)
  - No email, phone, token, or private-message columns
  - raw_payload stores the full API response for auditability; PII fields in
    the payload are the responsibility of the enrichment phase to strip.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class IngestionStatus(str, PyEnum):
    collected = "collected"
    processing = "processing"
    processed = "processed"
    rejected = "rejected"
    error = "error"


class RawReview(Base):
    __tablename__ = "raw_reviews"

    # ── Primary key ───────────────────────────────────────────
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ── Source FK ─────────────────────────────────────────────
    source: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("sources.name", ondelete="RESTRICT"),
        nullable=False,
    )

    # ── Deduplication ─────────────────────────────────────────
    # Platform-assigned ID (e.g. Reddit post id, YouTube comment id)
    source_record_id: Mapped[str] = mapped_column(String(256), nullable=False)

    # ── Provenance ────────────────────────────────────────────
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Privacy-safe author reference ─────────────────────────
    # SHA-256(salt + original_author_id) — never the raw username/ID
    author_id_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ── Content ───────────────────────────────────────────────
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # ── Structured extras ─────────────────────────────────────
    # domain-specific or source-specific structured fields
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )
    # Full raw API response for auditability / reprocessing
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Processing state ──────────────────────────────────────
    ingestion_status: Mapped[str] = mapped_column(
        String(32),
        default=IngestionStatus.collected.value,
        nullable=False,
    )

    # ── Relationship ──────────────────────────────────────────
    source_rel: Mapped["Source"] = relationship(  # noqa: F821
        "Source", back_populates="raw_reviews", lazy="select"
    )

    # ── Constraints & indexes ─────────────────────────────────
    __table_args__ = (
        UniqueConstraint("source", "source_record_id", name="uq_raw_reviews_source_record"),
        Index("ix_raw_reviews_source", "source"),
        Index("ix_raw_reviews_published_at", "published_at"),
        Index("ix_raw_reviews_ingestion_status", "ingestion_status"),
        Index("ix_raw_reviews_collected_at", "collected_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<RawReview id={self.id} source={self.source!r} "
            f"record_id={self.source_record_id!r}>"
        )
