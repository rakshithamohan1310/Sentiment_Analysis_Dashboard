"""Add nullable reviews.vehicle_category.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-11 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reviews",
        sa.Column("vehicle_category", sa.String(length=8), nullable=True),
    )
    op.create_check_constraint(
        "ck_reviews_vehicle_category",
        "reviews",
        "vehicle_category IS NULL OR vehicle_category IN ('2W', '3W', '4W')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_reviews_vehicle_category", "reviews", type_="check")
    op.drop_column("reviews", "vehicle_category")
