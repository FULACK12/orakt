"""Add official country profiles and macroeconomic time series.

Revision ID: 20260729_0006
Revises: 20260729_0005
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260729_0006"
down_revision: str | None = "20260729_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the economic indicator, country, observation and sync tables."""
    op.create_table(
        "economic_indicators",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False),
        sa.Column("name_zh", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=128), nullable=False),
        sa.Column("description_en", sa.Text(), nullable=False),
        sa.Column("description_zh", sa.Text(), nullable=False),
        sa.Column(
            "frequency",
            sa.String(length=32),
            server_default=sa.text("'annual'"),
            nullable=False,
        ),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("license_name", sa.String(length=255), nullable=False),
        sa.Column("license_url", sa.Text(), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
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
        sa.PrimaryKeyConstraint("code", name="pk_economic_indicators"),
    )
    op.create_table(
        "country_profiles",
        sa.Column("iso3", sa.String(length=3), nullable=False),
        sa.Column("iso2", sa.String(length=2), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("region", sa.String(length=255), nullable=False),
        sa.Column("income_level", sa.String(length=255), nullable=True),
        sa.Column("capital_city", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
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
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="ck_country_profiles_country_profile_latitude_range",
        ),
        sa.CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="ck_country_profiles_country_profile_longitude_range",
        ),
        sa.PrimaryKeyConstraint("iso3", name="pk_country_profiles"),
        sa.UniqueConstraint("iso2", name="uq_country_profiles_iso2"),
    )
    op.create_index(
        "ix_country_profiles_region",
        "country_profiles",
        ["region"],
    )
    op.create_table(
        "economic_observations",
        sa.Column("country_iso3", sa.String(length=3), nullable=False),
        sa.Column("indicator_code", sa.String(length=64), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["country_iso3"],
            ["country_profiles.iso3"],
            name="fk_economic_observations_country_iso3_country_profiles",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["indicator_code"],
            ["economic_indicators.code"],
            name="fk_economic_observations_indicator_code_economic_indicators",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "country_iso3",
            "indicator_code",
            "year",
            name="pk_economic_observations",
        ),
    )
    op.create_index(
        "ix_economic_observations_indicator_year",
        "economic_observations",
        ["indicator_code", "year"],
    )
    op.create_index(
        "ix_economic_observations_country_year",
        "economic_observations",
        ["country_iso3", "year"],
    )
    op.create_table(
        "economic_sync_states",
        sa.Column("source_key", sa.String(length=64), nullable=False),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("history_start_year", sa.Integer(), nullable=True),
        sa.Column("history_end_year", sa.Integer(), nullable=True),
        sa.Column(
            "rows_upserted",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "consecutive_failures",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "consecutive_failures >= 0",
            name="ck_economic_sync_states_economic_sync_failures_nonnegative",
        ),
        sa.CheckConstraint(
            "rows_upserted >= 0",
            name="ck_economic_sync_states_economic_sync_rows_nonnegative",
        ),
        sa.PrimaryKeyConstraint(
            "source_key",
            name="pk_economic_sync_states",
        ),
    )


def downgrade() -> None:
    """Remove official economic data tables."""
    op.drop_table("economic_sync_states")
    op.drop_index(
        "ix_economic_observations_country_year",
        table_name="economic_observations",
    )
    op.drop_index(
        "ix_economic_observations_indicator_year",
        table_name="economic_observations",
    )
    op.drop_table("economic_observations")
    op.drop_index("ix_country_profiles_region", table_name="country_profiles")
    op.drop_table("country_profiles")
    op.drop_table("economic_indicators")
