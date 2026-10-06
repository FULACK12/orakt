"""add lifecycle resolutions and multi-stage terminal cashflows

Revision ID: 20260826_0028
Revises: 20260826_0027
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260826_0028"
down_revision: str | None = "20260826_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "market_delisting_outcomes",
        sa.Column("resolution_method", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "market_delisting_outcomes",
        sa.Column("cashflow_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "market_delisting_outcomes",
        sa.Column(
            "terminal_is_final",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.execute(
        sa.text(
            "UPDATE market_delisting_outcomes "
            "SET resolution_method = 'single_terminal_value_v1', "
            "cashflow_count = 1, terminal_is_final = true "
            "WHERE status = 'verified'"
        )
    )
    op.create_table(
        "market_lifecycle_resolutions",
        sa.Column("asset_key", sa.String(length=255), nullable=False),
        sa.Column("resolution_type", sa.String(length=64), nullable=False),
        sa.Column("authoritative_status", sa.String(length=32), nullable=False),
        sa.Column("authoritative_delisting_date", sa.Date(), nullable=True),
        sa.Column("evidence_url", sa.Text(), nullable=False),
        sa.Column("evidence_note", sa.Text(), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_key"],
            ["market_asset_lifecycles.asset_key"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("asset_key"),
    )
    op.create_index(
        "ix_market_lifecycle_resolutions_type",
        "market_lifecycle_resolutions",
        ["resolution_type"],
    )
    op.create_index(
        "ix_market_lifecycle_resolutions_status",
        "market_lifecycle_resolutions",
        ["authoritative_status"],
    )
    op.create_table(
        "market_terminal_cashflows",
        sa.Column("cashflow_key", sa.String(length=64), nullable=False),
        sa.Column("asset_key", sa.String(length=255), nullable=False),
        sa.Column("evidence_key", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("cashflow_type", sa.String(length=64), nullable=False),
        sa.Column("amount_per_share", sa.Float(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "is_final",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("evidence_url", sa.Text(), nullable=False),
        sa.Column("evidence_note", sa.Text(), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_key"],
            ["market_asset_lifecycles.asset_key"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_key"],
            ["market_delisting_evidence_candidates.evidence_key"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("cashflow_key"),
    )
    op.create_index(
        "ix_market_terminal_cashflows_asset_date",
        "market_terminal_cashflows",
        ["asset_key", "payment_date"],
    )
    op.create_index(
        "ix_market_terminal_cashflows_status",
        "market_terminal_cashflows",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_terminal_cashflows_status",
        table_name="market_terminal_cashflows",
    )
    op.drop_index(
        "ix_market_terminal_cashflows_asset_date",
        table_name="market_terminal_cashflows",
    )
    op.drop_table("market_terminal_cashflows")
    op.drop_index(
        "ix_market_lifecycle_resolutions_status",
        table_name="market_lifecycle_resolutions",
    )
    op.drop_index(
        "ix_market_lifecycle_resolutions_type",
        table_name="market_lifecycle_resolutions",
    )
    op.drop_table("market_lifecycle_resolutions")
    op.drop_column("market_delisting_outcomes", "terminal_is_final")
    op.drop_column("market_delisting_outcomes", "cashflow_count")
    op.drop_column("market_delisting_outcomes", "resolution_method")
