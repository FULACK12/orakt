"""add append-only research report reviews

Revision ID: 20260814_0019
Revises: 20260812_0018
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260814_0019"
down_revision: str | None = "20260812_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_review_signals",
        sa.Column("inquiry_id", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=24), nullable=False),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('accepted', 'revised_accepted', 'deferred', 'rejected')",
            name="research_review_signal_decision",
        ),
        sa.ForeignKeyConstraint(
            ["inquiry_id"],
            ["research_inquiries.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_research_review_signals_inquiry_created",
        "research_review_signals",
        ["inquiry_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_review_signals_inquiry_created",
        table_name="research_review_signals",
    )
    op.drop_table("research_review_signals")
