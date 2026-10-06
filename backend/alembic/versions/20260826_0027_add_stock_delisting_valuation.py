"""add audited stock-acquisition valuation fields

Revision ID: 20260826_0027
Revises: 20260824_0026
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260826_0027"
down_revision: str | None = "20260824_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("market_delisting_evidence_candidates") as batch_op:
        batch_op.add_column(sa.Column("subject_symbol", sa.String(length=64)))
        batch_op.add_column(sa.Column("subject_sec_cik", sa.String(length=16)))
        batch_op.add_column(sa.Column("observed_on", sa.Date()))
    with op.batch_alter_table("market_delisting_outcomes") as batch_op:
        batch_op.add_column(sa.Column("valuation_evidence_key", sa.String(length=64)))
        batch_op.add_column(sa.Column("exchange_ratio", sa.Float()))
        batch_op.add_column(sa.Column("acquirer_symbol", sa.String(length=64)))
        batch_op.add_column(sa.Column("acquirer_price_on_payment", sa.Float()))
        batch_op.add_column(sa.Column("acquirer_price_observed_on", sa.Date()))
        batch_op.create_foreign_key(
            "fk_delisting_outcome_valuation_evidence",
            "market_delisting_evidence_candidates",
            ["valuation_evidence_key"],
            ["evidence_key"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("market_delisting_outcomes") as batch_op:
        batch_op.drop_constraint(
            "fk_delisting_outcome_valuation_evidence",
            type_="foreignkey",
        )
        batch_op.drop_column("acquirer_price_observed_on")
        batch_op.drop_column("acquirer_price_on_payment")
        batch_op.drop_column("acquirer_symbol")
        batch_op.drop_column("exchange_ratio")
        batch_op.drop_column("valuation_evidence_key")
    with op.batch_alter_table("market_delisting_evidence_candidates") as batch_op:
        batch_op.drop_column("observed_on")
        batch_op.drop_column("subject_sec_cik")
        batch_op.drop_column("subject_symbol")
