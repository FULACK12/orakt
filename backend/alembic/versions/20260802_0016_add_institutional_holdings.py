"""Add SEC Form 13F institutional holdings and archive checkpoints.

Revision ID: 20260802_0016
Revises: 20260731_0015
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260802_0016"
down_revision: str | None = "20260731_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_institutional_holdings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("cusip", sa.String(length=9), nullable=False),
        sa.Column("accession_number", sa.String(length=32), nullable=False),
        sa.Column("info_table_key", sa.String(length=64), nullable=False),
        sa.Column("report_period", sa.Date(), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("manager_cik", sa.String(length=16), nullable=False),
        sa.Column("manager_name", sa.String(length=255), nullable=False),
        sa.Column("issuer_name", sa.String(length=255), nullable=False),
        sa.Column("title_of_class", sa.String(length=128), nullable=False),
        sa.Column("value_thousands", sa.Float(), nullable=False),
        sa.Column("shares_or_principal", sa.Float(), nullable=False),
        sa.Column("shares_type", sa.String(length=16), nullable=False),
        sa.Column("put_call", sa.String(length=16), nullable=True),
        sa.Column("investment_discretion", sa.String(length=32), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["company_profiles.ticker"],
            name=op.f(
                "fk_company_institutional_holdings_ticker_company_profiles"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_company_institutional_holdings"),
        ),
        sa.UniqueConstraint(
            "ticker",
            "accession_number",
            "info_table_key",
            name="uq_company_institutional_holding_filing_row",
        ),
    )
    op.create_index(
        "ix_company_institutional_ticker_period",
        "company_institutional_holdings",
        ["ticker", "report_period"],
        unique=False,
    )
    op.create_table(
        "institutional_archive_states",
        sa.Column("archive_key", sa.String(length=128), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("local_path", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("archive_bytes", sa.Integer(), nullable=False),
        sa.Column("rows_seen", sa.Integer(), nullable=False),
        sa.Column("holdings_upserted", sa.Integer(), nullable=False),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint(
            "archive_key",
            name=op.f("pk_institutional_archive_states"),
        ),
    )


def downgrade() -> None:
    op.drop_table("institutional_archive_states")
    op.drop_index(
        "ix_company_institutional_ticker_period",
        table_name="company_institutional_holdings",
    )
    op.drop_table("company_institutional_holdings")
