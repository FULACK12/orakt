"""add auditable supply-chain review metadata

Revision ID: 20260830_0035
Revises: 20260830_0034
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260830_0035"
down_revision: str | None = "20260830_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("company_supply_chain_edges") as batch_op:
        batch_op.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True)))
        batch_op.add_column(sa.Column("reviewed_by", sa.String(64)))
        batch_op.add_column(sa.Column("review_note", sa.Text()))


def downgrade() -> None:
    with op.batch_alter_table("company_supply_chain_edges") as batch_op:
        batch_op.drop_column("review_note")
        batch_op.drop_column("reviewed_by")
        batch_op.drop_column("reviewed_at")
