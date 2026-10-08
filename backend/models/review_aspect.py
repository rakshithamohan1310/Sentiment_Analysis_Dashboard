"""
review_aspects table — one row per (review × aspect) match.

A single review may yield multiple rows (e.g. charging→positive plus
battery_health→negative). Each row stores the matched text span so downstream
consumers can trace results back to the original quote.

category and aspect strings come entirely from the domain YAML config — never
from code.  Sentiment here is scored on the local sentence/clause that triggered
the match, not on the whole review.
"""
from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class ReviewAspect(Base):
    __tablename__ = "review_aspects"

    # ── Primary key ───────────────────────────────────────────
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ── FK to reviews ─────────────────────────────────────────
    review_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reviews.review_id", ondelete="CASCADE"),
        nullable=False,
    )

    # ── Aspect identity (values come from YAML config) ────────
    category: Mapped[str] = mapped_column(String(64),  nullable=False)
    aspect:   Mapped[str] = mapped_column(String(128), nullable=False)

    # ── Aspect-level sentiment ────────────────────────────────
    sentiment_label: Mapped[str | None]  = mapped_column(String(16), nullable=True)
    sentiment_score: Mapped[float | None]= mapped_column(Float,      nullable=True)
    confidence:      Mapped[float | None]= mapped_column(Float,      nullable=True)

    # ── Evidence ─────────────────────────────────────────────
    # The text span (sentence / clause) that triggered the match. ≤ 500 chars.
    matched_text: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── Relationship ──────────────────────────────────────────
    review: Mapped["Review"] = relationship(  # noqa: F821
        "Review", back_populates="aspects", lazy="select"
    )

    # ── Indexes ───────────────────────────────────────────────
    __table_args__ = (
        Index("ix_review_aspects_review_id",      "review_id"),
        Index("ix_review_aspects_category",       "category"),
        Index("ix_review_aspects_aspect",         "aspect"),
        Index("ix_review_aspects_sentiment",      "sentiment_label"),
        Index("ix_review_aspects_cat_asp",        "category", "aspect"),
    )

    def __repr__(self) -> str:
        return (
            f"<ReviewAspect id={self.id} review_id={self.review_id} "
            f"category={self.category!r} aspect={self.aspect!r} "
            f"sentiment={self.sentiment_label!r}>"
        )
