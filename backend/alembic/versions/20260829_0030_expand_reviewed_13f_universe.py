"""expand reviewed SEC 13F issuer universe

Revision ID: 20260829_0030
Revises: 20260828_0029
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260829_0030"
down_revision: str | None = "20260828_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "institutional_archive_states",
        sa.Column("reviewed_universe_version", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("institutional_archive_states", "reviewed_universe_version")
