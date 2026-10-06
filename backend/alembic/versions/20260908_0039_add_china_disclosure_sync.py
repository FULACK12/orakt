"""Add restart-safe A-share disclosure archive coverage.

Revision ID: 20260908_0039
Revises: 20260901_0038
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260908_0039"
down_revision: str | None = "20260901_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "china_disclosure_sync_states",
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("org_id", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("announcements_seen", sa.Integer(), nullable=False),
        sa.Column("documents_upserted", sa.Integer(), nullable=False),
        sa.Column("documents_archived", sa.Integer(), nullable=False),
        sa.Column("periodic_reports", sa.Integer(), nullable=False),
        sa.Column("shareholder_documents", sa.Integer(), nullable=False),
        sa.Column("operating_documents", sa.Integer(), nullable=False),
        sa.Column("supply_chain_documents", sa.Integer(), nullable=False),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('pending', 'discovering', 'completed', 'partial', 'failed')",
            name=op.f("ck_china_disclosure_sync_states_china_disclosure_sync_status"),
        ),
        sa.PrimaryKeyConstraint(
            "ticker",
            name=op.f("pk_china_disclosure_sync_states"),
        ),
    )
    op.create_index(
        "ix_china_disclosure_sync_status_success",
        "china_disclosure_sync_states",
        ["status", "last_success_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_china_disclosure_sync_status_success",
        table_name="china_disclosure_sync_states",
    )
    op.drop_table("china_disclosure_sync_states")
