"""initial schema: sources, raw_reviews, collection_runs

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── sources ───────────────────────────────────────────────
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sources_name", "sources", ["name"], unique=True)

    # ── raw_reviews ───────────────────────────────────────────
    op.create_table(
        "raw_reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_record_id", sa.String(length=256), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("author_id_hash", sa.String(length=64), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "ingestion_status",
            sa.String(length=32),
            nullable=False,
            server_default="collected",
        ),
        sa.ForeignKeyConstraint(["source"], ["sources.name"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "source_record_id", name="uq_raw_reviews_source_record"),
    )
    op.create_index("ix_raw_reviews_source", "raw_reviews", ["source"])
    op.create_index("ix_raw_reviews_published_at", "raw_reviews", ["published_at"])
    op.create_index("ix_raw_reviews_ingestion_status", "raw_reviews", ["ingestion_status"])
    op.create_index("ix_raw_reviews_collected_at", "raw_reviews", ["collected_at"])

    # ── collection_runs ───────────────────────────────────────
    op.create_table(
        "collection_runs",
        sa.Column("run_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="running",
        ),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["source"], ["sources.name"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_collection_runs_source", "collection_runs", ["source"])
    op.create_index("ix_collection_runs_status", "collection_runs", ["status"])

    # ── Seed well-known sources ───────────────────────────────
    op.execute(
        """
        INSERT INTO sources (name, display_name, description, is_active)
        VALUES
          ('reddit',  'Reddit',   'Reddit posts and comments via official API', true),
          ('youtube', 'YouTube',  'YouTube video comments via Data API v3',     true),
          ('demo',    'Demo',     'Synthetic data for local testing (never real)', true)
        ON CONFLICT (name) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_table("collection_runs")
    op.drop_table("raw_reviews")
    op.drop_index("ix_sources_name", table_name="sources")
    op.drop_table("sources")
