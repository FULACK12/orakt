"""Add EIA bulk energy series, observations and synchronization state.

Revision ID: 20260730_0011
Revises: 20260729_0010
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260730_0011"
down_revision: str | None = "20260729_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the EIA series catalog, observations and durable sync state."""
    op.create_table(
        "energy_series",
        sa.Column("series_id", sa.String(length=255), nullable=False),
        sa.Column("dataset_key", sa.String(length=32), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("units", sa.String(length=255), nullable=True),
        sa.Column("frequency", sa.String(length=32), nullable=True),
        sa.Column("start_period", sa.String(length=32), nullable=True),
        sa.Column("end_period", sa.String(length=32), nullable=True),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "observation_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "materialized",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column(
            "series_metadata",
            sa.JSON(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
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
            "observation_count >= 0",
            name="ck_energy_series_energy_series_observation_count_nonnegative",
        ),
        sa.PrimaryKeyConstraint("series_id", name="pk_energy_series"),
    )
    op.create_index(
        "ix_energy_series_dataset_frequency",
        "energy_series",
        ["dataset_key", "frequency"],
    )
    op.create_index(
        "ix_energy_series_materialized",
        "energy_series",
        ["materialized"],
    )
    op.create_table(
        "energy_observations",
        sa.Column("series_id", sa.String(length=255), nullable=False),
        sa.Column("period", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["series_id"],
            ["energy_series.series_id"],
            name="fk_energy_observations_series_id_energy_series",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "series_id",
            "period",
            name="pk_energy_observations",
        ),
    )
    op.create_index(
        "ix_energy_observations_period",
        "energy_observations",
        ["period"],
    )
    op.create_index(
        "ix_energy_observations_series_period",
        "energy_observations",
        ["series_id", "period"],
    )
    op.create_table(
        "energy_sync_states",
        sa.Column("dataset_key", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_last_updated", sa.String(length=64), nullable=True),
        sa.Column("archive_path", sa.Text(), nullable=True),
        sa.Column("archive_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "archive_bytes",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "series_cataloged",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "series_materialized",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "observations_upserted",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "archive_bytes >= 0",
            name="ck_energy_sync_states_energy_sync_archive_bytes_nonnegative",
        ),
        sa.CheckConstraint(
            "series_cataloged >= 0",
            name="ck_energy_sync_states_energy_sync_series_cataloged_nonnegative",
        ),
        sa.CheckConstraint(
            "series_materialized >= 0",
            name="ck_energy_sync_states_energy_sync_series_materialized_nonnegative",
        ),
        sa.CheckConstraint(
            "observations_upserted >= 0",
            name="ck_energy_sync_states_energy_sync_observations_upserted_nonnegative",
        ),
        sa.PrimaryKeyConstraint("dataset_key", name="pk_energy_sync_states"),
    )


def downgrade() -> None:
    """Remove all EIA bulk-data tables."""
    op.drop_table("energy_sync_states")
    op.drop_index(
        "ix_energy_observations_series_period",
        table_name="energy_observations",
    )
    op.drop_index(
        "ix_energy_observations_period",
        table_name="energy_observations",
    )
    op.drop_table("energy_observations")
    op.drop_index("ix_energy_series_materialized", table_name="energy_series")
    op.drop_index(
        "ix_energy_series_dataset_frequency",
        table_name="energy_series",
    )
    op.drop_table("energy_series")
