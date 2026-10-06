"""add Alpha Vantage equity lifecycle catalog

Revision ID: 20260824_0021
Revises: 20260824_0020
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260824_0021"
down_revision: str | None = "20260824_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_asset_lifecycles",
        sa.Column("asset_key", sa.String(length=255), nullable=False),
        sa.Column("provider_key", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("exchange", sa.String(length=64), nullable=False),
        sa.Column("asset_type", sa.String(length=64), nullable=False),
        sa.Column("ipo_date", sa.Date(), nullable=True),
        sa.Column("delisting_date", sa.Date(), nullable=True),
        sa.Column("listing_status", sa.String(length=32), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("asset_key"),
    )
    op.create_index(
        "ix_market_asset_lifecycles_provider_status_dates",
        "market_asset_lifecycles",
        ["provider_key", "listing_status", "ipo_date", "delisting_date"],
    )
    op.create_index(
        "ix_market_asset_lifecycles_symbol_exchange",
        "market_asset_lifecycles",
        ["symbol", "exchange"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_asset_lifecycles_symbol_exchange",
        table_name="market_asset_lifecycles",
    )
    op.drop_index(
        "ix_market_asset_lifecycles_provider_status_dates",
        table_name="market_asset_lifecycles",
    )
    op.drop_table("market_asset_lifecycles")
