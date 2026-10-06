"""add SEC supplier-discovery checkpoints

Revision ID: 20260830_0034
Revises: 20260830_0033
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260830_0034"
down_revision: str | None = "20260830_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("company_supply_chain_coverage") as batch_op:
        batch_op.add_column(sa.Column("latest_filing_accession", sa.String(32)))
        batch_op.add_column(sa.Column("latest_filing_date", sa.Date()))
        batch_op.add_column(sa.Column("latest_raw_archive_path", sa.Text()))
        batch_op.add_column(sa.Column("last_parser_version", sa.String(64)))


def downgrade() -> None:
    with op.batch_alter_table("company_supply_chain_coverage") as batch_op:
        batch_op.drop_column("last_parser_version")
        batch_op.drop_column("latest_raw_archive_path")
        batch_op.drop_column("latest_filing_date")
        batch_op.drop_column("latest_filing_accession")
