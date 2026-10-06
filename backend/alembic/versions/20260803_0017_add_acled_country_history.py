"""add ACLED country-period history

Revision ID: 20260803_0017
Revises: 20260802_0016
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_0017"
down_revision: str | None = "20260802_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conflict_country_indicator_observations",
        sa.Column("country", sa.String(length=255), nullable=False),
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column("frequency", sa.String(length=16), nullable=False),
        sa.Column("metric", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("source_file", sa.String(length=512), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.CheckConstraint("value >= 0", name="conflict_country_value_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "country",
            "period",
            "frequency",
            "metric",
            name="uq_conflict_country_indicator_observation",
        ),
    )
    op.create_index(
        "ix_conflict_country_indicator_period",
        "conflict_country_indicator_observations",
        ["metric", "period"],
    )
    op.create_index(
        "ix_conflict_country_indicator_country",
        "conflict_country_indicator_observations",
        ["country", "period"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conflict_country_indicator_country",
        table_name="conflict_country_indicator_observations",
    )
    op.drop_index(
        "ix_conflict_country_indicator_period",
        table_name="conflict_country_indicator_observations",
    )
    op.drop_table("conflict_country_indicator_observations")
