"""Add locally retained market and macro-financial history.

Revision ID: 20260731_0013
Revises: 20260730_0012
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_0013"
down_revision: str | None = "20260730_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create reviewed series metadata, observations and sync state."""
    op.create_table(
        "market_series",
        sa.Column("series_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=False),
        sa.Column("frequency", sa.String(length=32), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("series_id", name=op.f("pk_market_series")),
    )
    op.create_table(
        "market_sync_states",
        sa.Column("provider_key", sa.String(length=64), nullable=False),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("history_start", sa.Date(), nullable=True),
        sa.Column("history_end", sa.Date(), nullable=True),
        sa.Column("series_synced", sa.Integer(), nullable=False),
        sa.Column("observations_upserted", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("provider_key", name=op.f("pk_market_sync_states")),
    )
    op.create_table(
        "market_observations",
        sa.Column("series_id", sa.String(length=64), nullable=False),
        sa.Column("observed_on", sa.Date(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["series_id"],
            ["market_series.series_id"],
            name=op.f("fk_market_observations_series_id_market_series"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "series_id",
            "observed_on",
            name=op.f("pk_market_observations"),
        ),
    )
    op.create_index(
        op.f("ix_market_observations_observed_on"),
        "market_observations",
        ["observed_on"],
        unique=False,
    )
    op.create_index(
        "ix_market_observations_series_date",
        "market_observations",
        ["series_id", "observed_on"],
        unique=False,
    )


def downgrade() -> None:
    """Remove market history tables."""
    op.drop_index(
        "ix_market_observations_series_date",
        table_name="market_observations",
    )
    op.drop_index(
        op.f("ix_market_observations_observed_on"),
        table_name="market_observations",
    )
    op.drop_table("market_observations")
    op.drop_table("market_sync_states")
    op.drop_table("market_series")

