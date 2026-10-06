"""add SEC delisting evidence discovery state and candidates

Revision ID: 20260824_0024
Revises: 20260824_0023
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260824_0024"
down_revision: str | None = "20260824_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_delisting_evidence_states",
        sa.Column("asset_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("sec_cik", sa.String(length=16), nullable=True),
        sa.Column("cik_name", sa.String(length=255), nullable=True),
        sa.Column("cik_name_similarity", sa.Float(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("filing_count", sa.Integer(), nullable=False),
        sa.Column("extracted_candidate_count", sa.Integer(), nullable=False),
        sa.Column("body_access_status", sa.String(length=32), nullable=False),
        sa.Column("search_start", sa.Date(), nullable=True),
        sa.Column("search_end", sa.Date(), nullable=True),
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
        "ix_market_delisting_evidence_states_status",
        "market_delisting_evidence_states",
        ["status"],
    )
    op.create_table(
        "market_delisting_evidence_candidates",
        sa.Column("evidence_key", sa.String(length=64), nullable=False),
        sa.Column("asset_key", sa.String(length=255), nullable=False),
        sa.Column("sec_cik", sa.String(length=16), nullable=False),
        sa.Column("accession_number", sa.String(length=40), nullable=False),
        sa.Column("document_name", sa.String(length=255), nullable=False),
        sa.Column("form", sa.String(length=32), nullable=False),
        sa.Column("filed_on", sa.Date(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_basis", sa.String(length=32), nullable=False),
        sa.Column("candidate_value", sa.Float(), nullable=True),
        sa.Column("value_unit", sa.String(length=32), nullable=True),
        sa.Column("evidence_excerpt", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("body_status", sa.String(length=32), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_archive_path", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("evidence_key"),
    )
    op.create_index(
        "ix_market_delisting_evidence_candidates_asset_review",
        "market_delisting_evidence_candidates",
        ["asset_key", "review_status"],
    )
    op.create_index(
        "ix_market_delisting_evidence_candidates_accession",
        "market_delisting_evidence_candidates",
        ["accession_number"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_delisting_evidence_candidates_accession",
        table_name="market_delisting_evidence_candidates",
    )
    op.drop_index(
        "ix_market_delisting_evidence_candidates_asset_review",
        table_name="market_delisting_evidence_candidates",
    )
    op.drop_table("market_delisting_evidence_candidates")
    op.drop_index(
        "ix_market_delisting_evidence_states_status",
        table_name="market_delisting_evidence_states",
    )
    op.drop_table("market_delisting_evidence_states")
