"""Add sector-relative fields to append-only entry evaluations.

Revision ID: 20260913_0042
Revises: 20260913_0041
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260913_0042"
down_revision: str | None = "20260913_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "entry_outcome_evaluations",
        sa.Column("sector_benchmark_series_id", sa.String(length=96), nullable=True),
    )
    op.add_column(
        "entry_outcome_evaluations",
        sa.Column("sector_benchmark_entry_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "entry_outcome_evaluations",
        sa.Column("sector_benchmark_exit_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "entry_outcome_evaluations",
        sa.Column("sector_benchmark_return", sa.Float(), nullable=True),
    )
    op.add_column(
        "entry_outcome_evaluations",
        sa.Column("sector_excess_net_return", sa.Float(), nullable=True),
    )
    op.add_column(
        "entry_outcome_evaluations",
        sa.Column(
            "sector_benchmark_coverage",
            sa.String(length=32),
            server_default="unavailable",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("entry_outcome_evaluations", "sector_benchmark_coverage")
    op.drop_column("entry_outcome_evaluations", "sector_excess_net_return")
    op.drop_column("entry_outcome_evaluations", "sector_benchmark_return")
    op.drop_column("entry_outcome_evaluations", "sector_benchmark_exit_date")
    op.drop_column("entry_outcome_evaluations", "sector_benchmark_entry_date")
    op.drop_column("entry_outcome_evaluations", "sector_benchmark_series_id")
