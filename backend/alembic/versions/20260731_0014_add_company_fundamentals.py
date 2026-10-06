"""Add reviewed companies, SEC filings and XBRL financial facts.

Revision ID: 20260731_0014
Revises: 20260731_0013
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_0014"
down_revision: str | None = "20260731_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_profiles",
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("cik", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sector", sa.String(length=128), nullable=False),
        sa.Column("industry", sa.String(length=255), nullable=False),
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
        sa.PrimaryKeyConstraint("ticker", name=op.f("pk_company_profiles")),
        sa.UniqueConstraint("cik", name=op.f("uq_company_profiles_cik")),
    )
    op.create_table(
        "company_filings",
        sa.Column("accession_number", sa.String(length=32), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("form", sa.String(length=32), nullable=False),
        sa.Column("filed_at", sa.Date(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("fiscal_period", sa.String(length=16), nullable=True),
        sa.Column("primary_document", sa.Text(), nullable=True),
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
            name=op.f("fk_company_filings_ticker_company_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "accession_number",
            name=op.f("pk_company_filings"),
        ),
    )
    op.create_index(
        "ix_company_filings_ticker_filed",
        "company_filings",
        ["ticker", "filed_at"],
        unique=False,
    )
    op.create_table(
        "company_financial_facts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("taxonomy", sa.String(length=32), nullable=False),
        sa.Column("concept", sa.String(length=128), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("filed_at", sa.Date(), nullable=False),
        sa.Column("form", sa.String(length=32), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("fiscal_period", sa.String(length=16), nullable=True),
        sa.Column("frame", sa.String(length=32), nullable=True),
        sa.Column("accession_number", sa.String(length=32), nullable=False),
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
            name=op.f("fk_company_financial_facts_ticker_company_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_financial_facts")),
        sa.UniqueConstraint(
            "ticker",
            "taxonomy",
            "concept",
            "unit",
            "period_end",
            "filed_at",
            "accession_number",
            name="uq_company_financial_fact_observation",
        ),
    )
    op.create_index(
        "ix_company_facts_ticker_concept_end",
        "company_financial_facts",
        ["ticker", "concept", "period_end"],
        unique=False,
    )
    op.create_table(
        "company_sync_states",
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("facts_upserted", sa.Integer(), nullable=False),
        sa.Column("filings_upserted", sa.Integer(), nullable=False),
        sa.Column("prices_upserted", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["company_profiles.ticker"],
            name=op.f("fk_company_sync_states_ticker_company_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("ticker", name=op.f("pk_company_sync_states")),
    )


def downgrade() -> None:
    op.drop_table("company_sync_states")
    op.drop_index(
        "ix_company_facts_ticker_concept_end",
        table_name="company_financial_facts",
    )
    op.drop_table("company_financial_facts")
    op.drop_index(
        "ix_company_filings_ticker_filed",
        table_name="company_filings",
    )
    op.drop_table("company_filings")
    op.drop_table("company_profiles")
