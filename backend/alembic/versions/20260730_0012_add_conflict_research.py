"""Add ACLED aggregates and local research inquiries.

Revision ID: 20260730_0012
Revises: 20260730_0011
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260730_0012"
down_revision: str | None = "20260730_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create conflict aggregate and research workflow tables."""
    op.create_table(
        "conflict_aggregate_observations",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("week", sa.Date(), nullable=False),
        sa.Column("region", sa.String(length=128), nullable=False),
        sa.Column("country", sa.String(length=255), nullable=False),
        sa.Column("admin1", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("sub_event_type", sa.String(length=255), nullable=False),
        sa.Column("events", sa.Integer(), nullable=False),
        sa.Column("fatalities", sa.Integer(), nullable=False),
        sa.Column("population_exposure", sa.Float(), nullable=True),
        sa.Column("disorder_type", sa.String(length=128), nullable=False),
        sa.Column("area_external_id", sa.String(length=64), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("source_file", sa.String(length=512), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "events >= 0",
            name="ck_conflict_aggregate_observations_conflict_events_nonnegative",
        ),
        sa.CheckConstraint(
            "fatalities >= 0",
            name="ck_conflict_aggregate_observations_conflict_fatalities_nonnegative",
        ),
        sa.CheckConstraint(
            "latitude >= -90 AND latitude <= 90",
            name="ck_conflict_aggregate_observations_conflict_latitude_range",
        ),
        sa.CheckConstraint(
            "longitude >= -180 AND longitude <= 180",
            name="ck_conflict_aggregate_observations_conflict_longitude_range",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_conflict_aggregate_observations"),
        sa.UniqueConstraint(
            "week",
            "country",
            "admin1",
            "event_type",
            "sub_event_type",
            name="uq_conflict_aggregate_observation",
        ),
    )
    op.create_index(
        "ix_conflict_aggregate_week",
        "conflict_aggregate_observations",
        ["week"],
    )
    op.create_index(
        "ix_conflict_aggregate_country_admin1_week",
        "conflict_aggregate_observations",
        ["country", "admin1", "week"],
    )
    op.create_index(
        "ix_conflict_aggregate_coordinates",
        "conflict_aggregate_observations",
        ["latitude", "longitude"],
    )
    op.create_table(
        "conflict_aggregate_sync_states",
        sa.Column("source_file", sa.String(length=512), nullable=False),
        sa.Column("archive_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_max_week", sa.Date(), nullable=True),
        sa.Column("rows_seen", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "rows_imported",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "rows_seen >= 0",
            name="ck_conflict_aggregate_sync_states_conflict_sync_rows_seen_nonnegative",
        ),
        sa.CheckConstraint(
            "rows_imported >= 0",
            name="ck_conflict_aggregate_sync_states_conflict_sync_rows_imported_nonnegative",
        ),
        sa.PrimaryKeyConstraint(
            "source_file",
            name="pk_conflict_aggregate_sync_states",
        ),
    )
    op.create_table(
        "research_inquiries",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'running'"),
            nullable=False,
        ),
        sa.Column("local_model", sa.String(length=255), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column(
            "evidence_snapshot",
            sa.JSON(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("chatgpt_review", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "mode IN ('user_question', 'autonomous')",
            name="ck_research_inquiries_research_inquiry_mode",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="ck_research_inquiries_research_inquiry_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_research_inquiries"),
    )
    op.create_index(
        "ix_research_inquiries_created_at",
        "research_inquiries",
        ["created_at"],
    )


def downgrade() -> None:
    """Remove local research and conflict aggregate storage."""
    op.drop_index("ix_research_inquiries_created_at", table_name="research_inquiries")
    op.drop_table("research_inquiries")
    op.drop_table("conflict_aggregate_sync_states")
    op.drop_index(
        "ix_conflict_aggregate_coordinates",
        table_name="conflict_aggregate_observations",
    )
    op.drop_index(
        "ix_conflict_aggregate_country_admin1_week",
        table_name="conflict_aggregate_observations",
    )
    op.drop_index(
        "ix_conflict_aggregate_week",
        table_name="conflict_aggregate_observations",
    )
    op.drop_table("conflict_aggregate_observations")
