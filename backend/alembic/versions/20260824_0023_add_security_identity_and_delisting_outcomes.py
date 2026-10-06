"""add security identity and delisting outcome audit

Revision ID: 20260824_0023
Revises: 20260824_0022
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260824_0023"
down_revision: str | None = "20260824_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_asset_identifiers",
        sa.Column("asset_key", sa.String(length=255), nullable=False),
        sa.Column("identity_status", sa.String(length=32), nullable=False),
        sa.Column("mapping_method", sa.String(length=64), nullable=True),
        sa.Column("figi", sa.String(length=32), nullable=True),
        sa.Column("composite_figi", sa.String(length=32), nullable=True),
        sa.Column("share_class_figi", sa.String(length=32), nullable=True),
        sa.Column("sec_cik", sa.String(length=16), nullable=True),
        sa.Column("mapped_ticker", sa.String(length=64), nullable=True),
        sa.Column("mapped_name", sa.String(length=255), nullable=True),
        sa.Column("mapped_exchange", sa.String(length=64), nullable=True),
        sa.Column("security_type", sa.String(length=64), nullable=True),
        sa.Column("name_similarity", sa.Float(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("asset_key"),
    )
    op.create_index(
        "ix_market_asset_identifiers_status",
        "market_asset_identifiers",
        ["identity_status"],
    )
    op.create_index(
        "ix_market_asset_identifiers_figi",
        "market_asset_identifiers",
        ["composite_figi"],
    )
    op.create_table(
        "market_delisting_outcomes",
        sa.Column("asset_key", sa.String(length=255), nullable=False),
        sa.Column("series_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("outcome_type", sa.String(length=32), nullable=False),
        sa.Column("last_trade_date", sa.Date(), nullable=True),
        sa.Column("last_trade_price", sa.Float(), nullable=True),
        sa.Column("terminal_value_per_share", sa.Float(), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("delisting_return", sa.Float(), nullable=True),
        sa.Column("evidence_url", sa.Text(), nullable=True),
        sa.Column("evidence_note", sa.Text(), nullable=True),
        sa.Column("evidence_hash", sa.String(length=64), nullable=True),
        sa.Column("verification_method", sa.String(length=64), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
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
        "ix_market_delisting_outcomes_status",
        "market_delisting_outcomes",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_delisting_outcomes_status",
        table_name="market_delisting_outcomes",
    )
    op.drop_table("market_delisting_outcomes")
    op.drop_index(
        "ix_market_asset_identifiers_figi",
        table_name="market_asset_identifiers",
    )
    op.drop_index(
        "ix_market_asset_identifiers_status",
        table_name="market_asset_identifiers",
    )
    op.drop_table("market_asset_identifiers")
