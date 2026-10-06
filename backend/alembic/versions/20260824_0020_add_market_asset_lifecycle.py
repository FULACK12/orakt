"""add point-in-time market asset lifecycle metadata

Revision ID: 20260824_0020
Revises: 20260814_0019
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260824_0020"
down_revision: str | None = "20260814_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "market_series",
        sa.Column(
            "listing_status",
            sa.String(length=32),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column("market_series", sa.Column("listed_from", sa.Date(), nullable=True))
    op.add_column("market_series", sa.Column("listed_until", sa.Date(), nullable=True))
    op.add_column("market_series", sa.Column("delisting_return", sa.Float(), nullable=True))
    op.add_column("market_series", sa.Column("sector", sa.String(length=100), nullable=True))
    op.add_column("market_series", sa.Column("region", sa.String(length=100), nullable=True))
    op.add_column(
        "market_series",
        sa.Column("neutralization_group", sa.String(length=160), nullable=True),
    )
    op.create_index(
        "ix_market_series_listing_status_dates",
        "market_series",
        ["listing_status", "listed_from", "listed_until"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_series_listing_status_dates", table_name="market_series")
    op.drop_column("market_series", "neutralization_group")
    op.drop_column("market_series", "region")
    op.drop_column("market_series", "sector")
    op.drop_column("market_series", "delisting_return")
    op.drop_column("market_series", "listed_until")
    op.drop_column("market_series", "listed_from")
    op.drop_column("market_series", "listing_status")
