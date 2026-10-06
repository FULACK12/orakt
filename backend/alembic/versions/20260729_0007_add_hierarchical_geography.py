"""Add hierarchical places, regional metrics and event relation candidates.

Revision ID: 20260729_0007
Revises: 20260729_0006
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260729_0007"
down_revision: str | None = "20260729_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

id_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    """Create place hierarchy, regional observation and relation tables."""
    op.create_table(
        "administrative_areas",
        sa.Column("id", id_type, autoincrement=True, nullable=False),
        sa.Column("parent_id", id_type, nullable=True),
        sa.Column("country_iso2", sa.String(length=2), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("ascii_name", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column(
            "coordinate_precision",
            sa.String(length=32),
            server_default=sa.text("'reference_point'"),
            nullable=False,
        ),
        sa.Column("population", sa.BigInteger(), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("license_name", sa.String(length=255), nullable=False),
        sa.Column("license_url", sa.Text(), nullable=False),
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
            "level IN ('admin1', 'admin2', 'city')",
            name="ck_administrative_areas_administrative_area_level",
        ),
        sa.CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="ck_administrative_areas_administrative_area_latitude",
        ),
        sa.CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="ck_administrative_areas_administrative_area_longitude",
        ),
        sa.CheckConstraint(
            "population IS NULL OR population >= 0",
            name="ck_administrative_areas_administrative_area_population",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["administrative_areas.id"],
            name="fk_administrative_areas_parent_id_administrative_areas",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_administrative_areas"),
        sa.UniqueConstraint(
            "source_name",
            "external_id",
            name="uq_administrative_areas_source_external_id",
        ),
    )
    op.create_index(
        "ix_administrative_areas_country_level",
        "administrative_areas",
        ["country_iso2", "level"],
    )
    op.create_index(
        "ix_administrative_areas_parent_id",
        "administrative_areas",
        ["parent_id"],
    )
    op.create_table(
        "regional_indicators",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False),
        sa.Column("name_zh", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=128), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("license_name", sa.String(length=255), nullable=False),
        sa.Column("license_url", sa.Text(), nullable=False),
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
        sa.PrimaryKeyConstraint("code", name="pk_regional_indicators"),
    )
    op.create_table(
        "regional_observations",
        sa.Column("area_id", id_type, nullable=False),
        sa.Column("indicator_code", sa.String(length=64), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["area_id"],
            ["administrative_areas.id"],
            name="fk_regional_observations_area_id_administrative_areas",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["indicator_code"],
            ["regional_indicators.code"],
            name="fk_regional_observations_indicator_code_regional_indicators",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "area_id",
            "indicator_code",
            "period",
            name="pk_regional_observations",
        ),
    )
    op.create_index(
        "ix_regional_observations_indicator_period",
        "regional_observations",
        ["indicator_code", "period"],
    )
    op.create_table(
        "event_relation_candidates",
        sa.Column("id", id_type, autoincrement=True, nullable=False),
        sa.Column("cluster_job_id", id_type, nullable=False),
        sa.Column("source_candidate_id", sa.String(length=128), nullable=False),
        sa.Column("target_candidate_id", sa.String(length=128), nullable=False),
        sa.Column("relation_type", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("evidence_document_ids", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'suggested'"),
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
            "confidence >= 0 AND confidence <= 1",
            name="ck_event_relation_candidates_event_relation_confidence",
        ),
        sa.CheckConstraint(
            "status IN ('suggested', 'accepted', 'rejected')",
            name="ck_event_relation_candidates_event_relation_status",
        ),
        sa.ForeignKeyConstraint(
            ["cluster_job_id"],
            ["cluster_jobs.id"],
            name="fk_event_relation_candidates_cluster_job_id_cluster_jobs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_event_relation_candidates"),
        sa.UniqueConstraint(
            "cluster_job_id",
            "source_candidate_id",
            "target_candidate_id",
            "relation_type",
            name="uq_event_relation_candidates_edge",
        ),
    )
    op.create_index(
        "ix_event_relation_candidates_job_status",
        "event_relation_candidates",
        ["cluster_job_id", "status"],
    )


def downgrade() -> None:
    """Remove hierarchical geography and chain-candidate storage."""
    op.drop_index(
        "ix_event_relation_candidates_job_status",
        table_name="event_relation_candidates",
    )
    op.drop_table("event_relation_candidates")
    op.drop_index(
        "ix_regional_observations_indicator_period",
        table_name="regional_observations",
    )
    op.drop_table("regional_observations")
    op.drop_table("regional_indicators")
    op.drop_index(
        "ix_administrative_areas_parent_id",
        table_name="administrative_areas",
    )
    op.drop_index(
        "ix_administrative_areas_country_level",
        table_name="administrative_areas",
    )
    op.drop_table("administrative_areas")
