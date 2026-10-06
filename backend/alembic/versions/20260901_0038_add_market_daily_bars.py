"""Retain split-adjusted daily OHLCV bars.

Revision ID: 20260901_0038
Revises: 20260831_0037
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260901_0038"
down_revision: str | None = "20260831_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_daily_bars",
        sa.Column("series_id", sa.String(length=64), nullable=False),
        sa.Column("observed_on", sa.Date(), nullable=False),
        sa.Column("open_price", sa.Float(), nullable=False),
        sa.Column("high_price", sa.Float(), nullable=False),
        sa.Column("low_price", sa.Float(), nullable=False),
        sa.Column("close_price", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column(
            "adjustment",
            sa.String(length=32),
            server_default="splits",
            nullable=False,
        ),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["series_id"],
            ["market_series.series_id"],
            name=op.f("fk_market_daily_bars_series_id_market_series"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "series_id",
            "observed_on",
            name=op.f("pk_market_daily_bars"),
        ),
    )
    op.create_index(
        op.f("ix_market_daily_bars_observed_on"),
        "market_daily_bars",
        ["observed_on"],
        unique=False,
    )
    op.create_index(
        "ix_market_daily_bars_series_date",
        "market_daily_bars",
        ["series_id", "observed_on"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_market_daily_bars_series_date", table_name="market_daily_bars")
    op.drop_index(
        op.f("ix_market_daily_bars_observed_on"),
        table_name="market_daily_bars",
    )
    op.drop_table("market_daily_bars")
