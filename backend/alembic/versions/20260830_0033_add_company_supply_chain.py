"""add source-reviewed company supply-chain graph

Revision ID: 20260830_0033
Revises: 20260830_0032
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260830_0033"
down_revision: str | None = "20260830_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_supply_chain_edges",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("subject_ticker", sa.String(length=16), nullable=False),
        sa.Column("related_company_name", sa.String(length=255), nullable=False),
        sa.Column("related_ticker", sa.String(length=32), nullable=True),
        sa.Column("relationship_type", sa.String(length=32), nullable=False),
        sa.Column("product_or_input", sa.String(length=255), nullable=False),
        sa.Column("geography", sa.String(length=255), nullable=True),
        sa.Column("dependency_level", sa.String(length=16), nullable=False),
        sa.Column("review_status", sa.String(length=24), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.Date(), nullable=False),
        sa.Column("available_at", sa.Date(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "relationship_type IN ('supplier', 'customer', 'foundry', 'contract_manufacturer', 'equipment', 'materials', 'logistics', 'energy', 'cloud', 'distributor')",
            name="company_supply_chain_relationship_type",
        ),
        sa.CheckConstraint(
            "dependency_level IN ('unknown', 'low', 'medium', 'high', 'sole_source')",
            name="company_supply_chain_dependency_level",
        ),
        sa.CheckConstraint(
            "review_status IN ('candidate', 'verified', 'rejected', 'expired')",
            name="company_supply_chain_review_status",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="company_supply_chain_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["subject_ticker"],
            ["company_profiles.ticker"],
            name=op.f("fk_company_supply_chain_edges_subject_ticker_company_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_supply_chain_edges")),
        sa.UniqueConstraint(
            "subject_ticker",
            "related_company_name",
            "relationship_type",
            "product_or_input",
            "source_ref",
            name="uq_company_supply_chain_evidence_edge",
        ),
    )
    op.create_index(
        "ix_company_supply_chain_subject_status",
        "company_supply_chain_edges",
        ["subject_ticker", "review_status", "available_at"],
        unique=False,
    )
    op.create_table(
        "company_supply_chain_coverage",
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("candidate_edges", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("verified_edges", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("related_companies_with_market_data", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("latest_available_at", sa.Date(), nullable=True),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gaps", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'discovering', 'needs_review', 'verified_partial', 'verified', 'failed')",
            name="company_supply_chain_coverage_status",
        ),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["company_profiles.ticker"],
            name=op.f("fk_company_supply_chain_coverage_ticker_company_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("ticker", name=op.f("pk_company_supply_chain_coverage")),
    )
    # Populate a transparent coverage row for the current issuer universe. Use
    # SQLAlchemy JSON binding instead of PostgreSQL-specific ``::json`` syntax
    # so a fresh SQLite database can also exercise the complete migration chain.
    bind = op.get_bind()
    coverage = sa.table(
        "company_supply_chain_coverage",
        sa.column("ticker", sa.String(length=16)),
        sa.column("status", sa.String(length=32)),
        sa.column("gaps", sa.JSON()),
    )
    tickers = bind.execute(sa.text("SELECT ticker FROM company_profiles")).scalars()
    rows = [
        {
            "ticker": ticker,
            "status": "pending",
            "gaps": [
                "supplier names",
                "product dependency",
                "facility mapping",
                "point-in-time source excerpts",
            ],
        }
        for ticker in tickers
    ]
    if rows:
        op.bulk_insert(coverage, rows)


def downgrade() -> None:
    op.drop_table("company_supply_chain_coverage")
    op.drop_index("ix_company_supply_chain_subject_status", table_name="company_supply_chain_edges")
    op.drop_table("company_supply_chain_edges")
