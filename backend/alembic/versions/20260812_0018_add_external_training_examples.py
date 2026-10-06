"""add isolated external training examples

Revision ID: 20260812_0018
Revises: 20260803_0017
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260812_0018"
down_revision: str | None = "20260803_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_training_examples",
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("input_context", sa.Text(), nullable=False),
        sa.Column("ideal_response", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=2_000), nullable=False),
        sa.Column("license_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("quality_score", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "quality_score >= 0 AND quality_score <= 1",
            name="external_training_example_quality_score",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="external_training_example_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint"),
    )
    op.create_index(
        "ix_external_training_examples_status",
        "external_training_examples",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_external_training_examples_status",
        table_name="external_training_examples",
    )
    op.drop_table("external_training_examples")
