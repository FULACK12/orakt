"""add resumable research report checkpoints

Revision ID: 20260923_0045
Revises: 20260922_0044
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260923_0045"
down_revision: str | None = "20260922_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "research_batch_items",
        sa.Column("checkpoint_data", sa.JSON(), server_default="{}", nullable=False),
    )
    op.add_column(
        "research_batch_items",
        sa.Column("checkpoint_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("research_batch_items", "checkpoint_at")
    op.drop_column("research_batch_items", "checkpoint_data")
