"""Phase 2 schema: reviews + review_aspects tables.

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-02 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── reviews ───────────────────────────────────────────────
    op.create_table(
        "reviews",
        sa.Column("review_id",        sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("raw_review_id",     sa.Integer(), nullable=False),
        sa.Column("source",            sa.String(64),  nullable=False),
        sa.Column("source_record_id",  sa.String(256), nullable=False),
        sa.Column("published_at",      sa.DateTime(timezone=True), nullable=True),
        sa.Column("title",             sa.Text(), nullable=True),
        sa.Column("review_text",       sa.Text(), nullable=True),
        sa.Column("language",          sa.String(8),  nullable=True),
        sa.Column("rating",            sa.Float(), nullable=True),
        sa.Column("vehicle_type",      sa.String(64),  nullable=True),
        sa.Column("manufacturer",      sa.String(128), nullable=True),
        sa.Column("vehicle_model",     sa.String(128), nullable=True),
        sa.Column("model_year",        sa.Integer(), nullable=True),
        sa.Column("domain",            sa.String(64),  nullable=True),
        sa.Column("sentiment_label",      sa.String(16), nullable=True),
        sa.Column("sentiment_score",      sa.Float(), nullable=True),
        sa.Column("sentiment_confidence", sa.Float(), nullable=True),
        sa.Column("relevance_score",      sa.Float(), nullable=True),
        sa.Column("completeness_score",   sa.Float(), nullable=True),
        sa.Column("duplicate_group_id",   sa.String(64), nullable=True),
        sa.Column("is_duplicate",  sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("processing_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("reject_reason",  sa.Text(), nullable=True),
        sa.Column("synthetic",      sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("engagement_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["raw_review_id"], ["raw_reviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("review_id"),
        sa.UniqueConstraint("raw_review_id", name="uq_reviews_raw_review_id"),
    )
    op.create_index("ix_reviews_published_at",      "reviews", ["published_at"])
    op.create_index("ix_reviews_source",             "reviews", ["source"])
    op.create_index("ix_reviews_sentiment_label",    "reviews", ["sentiment_label"])
    op.create_index("ix_reviews_manufacturer",       "reviews", ["manufacturer"])
    op.create_index("ix_reviews_vehicle_model",      "reviews", ["vehicle_model"])
    op.create_index("ix_reviews_is_duplicate",       "reviews", ["is_duplicate"])
    op.create_index("ix_reviews_synthetic",          "reviews", ["synthetic"])
    op.create_index("ix_reviews_processing_status",  "reviews", ["processing_status"])
    op.create_index("ix_reviews_language",           "reviews", ["language"])

    # ── review_aspects ────────────────────────────────────────
    op.create_table(
        "review_aspects",
        sa.Column("id",        sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("category",  sa.String(64),  nullable=False),
        sa.Column("aspect",    sa.String(128), nullable=False),
        sa.Column("sentiment_label", sa.String(16), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("confidence",      sa.Float(), nullable=True),
        sa.Column("matched_text",    sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.review_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_aspects_review_id", "review_aspects", ["review_id"])
    op.create_index("ix_review_aspects_category",  "review_aspects", ["category"])
    op.create_index("ix_review_aspects_aspect",    "review_aspects", ["aspect"])
    op.create_index("ix_review_aspects_sentiment", "review_aspects", ["sentiment_label"])
    op.create_index("ix_review_aspects_cat_asp",   "review_aspects", ["category", "aspect"])


def downgrade() -> None:
    op.drop_table("review_aspects")
    op.drop_table("reviews")
