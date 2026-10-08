"""
sources table – registry of data sources (reddit, youtube, demo, …).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    raw_reviews: Mapped[list["RawReview"]] = relationship(  # noqa: F821
        "RawReview", back_populates="source_rel", lazy="select"
    )
    collection_runs: Mapped[list["CollectionRun"]] = relationship(  # noqa: F821
        "CollectionRun", back_populates="source_rel", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Source name={self.name!r}>"
