"""retain raw price lineage for SEC-anchored lifecycle segments

Revision ID: 20260824_0026
Revises: 20260824_0025
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260824_0026"
down_revision: str | None = "20260824_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("market_price_backfill_states") as batch_op:
        batch_op.add_column(sa.Column("source_series_id", sa.String(length=64)))
        batch_op.add_column(sa.Column("lifecycle_evidence_key", sa.String(length=64)))
        batch_op.add_column(sa.Column("provider_delisting_date", sa.Date()))
        batch_op.add_column(sa.Column("lifecycle_terminal_date", sa.Date()))
        batch_op.add_column(sa.Column("lifecycle_segment_method", sa.String(length=64)))
        batch_op.add_column(sa.Column("lifecycle_segmented_at", sa.DateTime(timezone=True)))
        batch_op.create_foreign_key(
            "fk_price_state_source_series",
            "market_series",
            ["source_series_id"],
            ["series_id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_price_state_lifecycle_evidence",
            "market_delisting_evidence_candidates",
            ["lifecycle_evidence_key"],
            ["evidence_key"],
            ondelete="SET NULL",
        )
    with op.batch_alter_table("market_delisting_outcomes") as batch_op:
        batch_op.add_column(sa.Column("evidence_key", sa.String(length=64)))
        batch_op.create_foreign_key(
            "fk_delisting_outcome_evidence",
            "market_delisting_evidence_candidates",
            ["evidence_key"],
            ["evidence_key"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("market_delisting_outcomes") as batch_op:
        batch_op.drop_constraint("fk_delisting_outcome_evidence", type_="foreignkey")
        batch_op.drop_column("evidence_key")
    with op.batch_alter_table("market_price_backfill_states") as batch_op:
        batch_op.drop_constraint("fk_price_state_lifecycle_evidence", type_="foreignkey")
        batch_op.drop_constraint("fk_price_state_source_series", type_="foreignkey")
        batch_op.drop_column("lifecycle_segmented_at")
        batch_op.drop_column("lifecycle_segment_method")
        batch_op.drop_column("lifecycle_terminal_date")
        batch_op.drop_column("provider_delisting_date")
        batch_op.drop_column("lifecycle_evidence_key")
        batch_op.drop_column("source_series_id")
