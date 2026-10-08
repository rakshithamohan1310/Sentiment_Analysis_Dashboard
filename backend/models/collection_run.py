"""
collection_runs table – one row per collector invocation.
Tracks stats and status for observability and re-run safety.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class RunStatus(str, PyEnum):
    running = "running"
    completed = "completed"
    partial = "partial"   # some records failed but run finished
    failed = "failed"


class CollectionRun(Base):
    __tablename__ = "collection_runs"

    run_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ── Source ────────────────────────────────────────────────
    source: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("sources.name", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── Timing ────────────────────────────────────────────────
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Stats ─────────────────────────────────────────────────
    records_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicates: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ── Outcome ───────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(32), default=RunStatus.running.value, nullable=False, index=True
    )
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationship ──────────────────────────────────────────
    source_rel: Mapped["Source"] = relationship(  # noqa: F821
        "Source", back_populates="collection_runs", lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<CollectionRun run_id={self.run_id} source={self.source!r} "
            f"status={self.status!r}>"
        )
