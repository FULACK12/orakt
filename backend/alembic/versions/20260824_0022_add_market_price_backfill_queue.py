"""add historical market price backfill queue

Revision ID: 20260824_0022
Revises: 20260824_0021
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260824_0022"
down_revision: str | None = "20260824_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_price_backfill_states",
        sa.Column("asset_key", sa.String(length=255), nullable=False),
        sa.Column("provider_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("priority_reasons", sa.JSON(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observations_upserted", sa.Integer(), nullable=False),
        sa.Column("observed_start", sa.Date(), nullable=True),
        sa.Column("observed_end", sa.Date(), nullable=True),
        sa.Column("series_id", sa.String(length=64), nullable=True),
        sa.Column("raw_archive_path", sa.Text(), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["asset_key"],
            ["market_asset_lifecycles.asset_key"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["series_id"], ["market_series.series_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("asset_key"),
    )
    op.create_index(
        "ix_market_price_backfill_states_status_priority",
        "market_price_backfill_states",
        ["status", "priority_score"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_price_backfill_states_status_priority",
        table_name="market_price_backfill_states",
    )
    op.drop_table("market_price_backfill_states")
