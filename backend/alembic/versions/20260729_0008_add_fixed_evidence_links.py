"""Add review metadata for fixed evidence and logic links.

Revision ID: 20260729_0008
Revises: 20260729_0007
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260729_0008"
down_revision: str | None = "20260729_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow reviewed relation suggestions to become fixed evidence links."""
    op.add_column(
        "event_relation_candidates",
        sa.Column(
            "pinned",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "event_relation_candidates",
        sa.Column("review_note", sa.Text(), nullable=True),
    )
    op.add_column(
        "event_relation_candidates",
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Remove fixed-link review metadata."""
    op.drop_column("event_relation_candidates", "decided_at")
    op.drop_column("event_relation_candidates", "review_note")
    op.drop_column("event_relation_candidates", "pinned")
