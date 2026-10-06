"""Add GDELT cold-archive state and monthly event aggregates.

Revision ID: 20260731_0015
Revises: 20260731_0014
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_0015"
down_revision: str | None = "20260731_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gdelt_archive_states",
        sa.Column("archive_key", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("local_path", sa.Text(), nullable=True),
        sa.Column("archive_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("starts_at", sa.Date(), nullable=True),
        sa.Column("ends_at", sa.Date(), nullable=True),
        sa.Column("rows_seen", sa.Integer(), nullable=False),
        sa.Column("aggregates_upserted", sa.Integer(), nullable=False),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint(
            "archive_key",
            name=op.f("pk_gdelt_archive_states"),
        ),
    )
    op.create_table(
        "gdelt_event_aggregates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("country_code", sa.String(length=8), nullable=False),
        sa.Column("event_root_code", sa.String(length=8), nullable=False),
        sa.Column("quad_class", sa.Integer(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("total_mentions", sa.Integer(), nullable=False),
        sa.Column("total_sources", sa.Integer(), nullable=False),
        sa.Column("total_articles", sa.Integer(), nullable=False),
        sa.Column("goldstein_sum", sa.Float(), nullable=False),
        sa.Column("tone_sum", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gdelt_event_aggregates")),
        sa.UniqueConstraint(
            "month",
            "country_code",
            "event_root_code",
            "quad_class",
            name="uq_gdelt_event_aggregate_bucket",
        ),
    )
    op.create_index(
        "ix_gdelt_event_aggregates_month_country",
        "gdelt_event_aggregates",
        ["month", "country_code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_gdelt_event_aggregates_month_country",
        table_name="gdelt_event_aggregates",
    )
    op.drop_table("gdelt_event_aggregates")
    op.drop_table("gdelt_archive_states")
