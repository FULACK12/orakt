"""add SEC Form 4 insider transactions

Revision ID: 20260830_0031
Revises: 20260829_0030
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260830_0031"
down_revision: str | None = "20260829_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_insider_filing_states",
        sa.Column("accession_number", sa.String(length=32), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("raw_archive_path", sa.Text(), nullable=True),
        sa.Column("raw_sha256", sa.String(length=64), nullable=True),
        sa.Column("raw_bytes", sa.Integer(), nullable=False),
        sa.Column("transactions_upserted", sa.Integer(), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["accession_number"],
            ["company_filings.accession_number"],
            name=op.f(
                "fk_company_insider_filing_states_accession_number_company_filings"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["company_profiles.ticker"],
            name=op.f("fk_company_insider_filing_states_ticker_company_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "accession_number",
            name=op.f("pk_company_insider_filing_states"),
        ),
    )
    op.create_table(
        "company_insider_transactions",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("accession_number", sa.String(length=32), nullable=False),
        sa.Column("form", sa.String(length=32), nullable=False),
        sa.Column("filed_at", sa.Date(), nullable=False),
        sa.Column("transaction_kind", sa.String(length=32), nullable=False),
        sa.Column("transaction_index", sa.Integer(), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=True),
        sa.Column("deemed_execution_date", sa.Date(), nullable=True),
        sa.Column("security_title", sa.String(length=255), nullable=False),
        sa.Column("transaction_code", sa.String(length=8), nullable=True),
        sa.Column("acquired_disposed", sa.String(length=1), nullable=True),
        sa.Column("shares", sa.Float(), nullable=True),
        sa.Column("price_per_share", sa.Float(), nullable=True),
        sa.Column("shares_owned_following", sa.Float(), nullable=True),
        sa.Column("direct_or_indirect", sa.String(length=1), nullable=True),
        sa.Column("ownership_nature", sa.Text(), nullable=True),
        sa.Column("derivative_exercise_price", sa.Float(), nullable=True),
        sa.Column("derivative_exercise_date", sa.Date(), nullable=True),
        sa.Column("derivative_expiration_date", sa.Date(), nullable=True),
        sa.Column("underlying_security_title", sa.String(length=255), nullable=True),
        sa.Column("underlying_shares", sa.Float(), nullable=True),
        sa.Column("equity_swap_involved", sa.Boolean(), nullable=False),
        sa.Column("is_10b5_1", sa.Boolean(), nullable=False),
        sa.Column("reporting_owners", sa.JSON(), nullable=False),
        sa.Column("footnote_text", sa.Text(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
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
            ["accession_number"],
            ["company_filings.accession_number"],
            name=op.f(
                "fk_company_insider_transactions_accession_number_company_filings"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["company_profiles.ticker"],
            name=op.f("fk_company_insider_transactions_ticker_company_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_insider_transactions")),
        sa.UniqueConstraint(
            "accession_number",
            "transaction_kind",
            "transaction_index",
            name="uq_company_insider_transaction_filing_row",
        ),
    )
    op.create_index(
        "ix_company_insider_ticker_transaction_date",
        "company_insider_transactions",
        ["ticker", "transaction_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_company_insider_ticker_transaction_date",
        table_name="company_insider_transactions",
    )
    op.drop_table("company_insider_transactions")
    op.drop_table("company_insider_filing_states")
