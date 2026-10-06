"""separate terminal delisting evidence from supporting evidence

Revision ID: 20260824_0025
Revises: 20260824_0024
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260824_0025"
down_revision: str | None = "20260824_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "market_delisting_evidence_candidates",
        sa.Column("review_role", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("market_delisting_evidence_candidates", "review_role")
