"""add source-bounded supply-chain sites

Revision ID: 20260831_0036
Revises: 20260830_0035
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260831_0036"
down_revision: str | None = "20260830_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_supply_chain_sites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "edge_id",
            sa.Integer(),
            sa.ForeignKey("company_supply_chain_edges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subject_ticker",
            sa.String(16),
            sa.ForeignKey("company_profiles.ticker", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("related_company_name", sa.String(255), nullable=False),
        sa.Column("related_ticker", sa.String(32)),
        sa.Column("site_kind", sa.String(32), nullable=False),
        sa.Column("site_name", sa.String(255), nullable=False),
        sa.Column("country_name", sa.String(128), nullable=False),
        sa.Column("country_iso2", sa.String(2)),
        sa.Column("admin1_name", sa.String(255)),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("coordinate_precision", sa.String(32), nullable=False),
        sa.Column("verification_status", sa.String(32), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("source_ref", sa.String(255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.Date(), nullable=False),
        sa.Column("available_at", sa.Date(), nullable=False),
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
            "site_kind IN ('facility', 'manufacturing_region', 'port', "
            "'airport', 'power_asset')",
            name="company_supply_chain_site_kind",
        ),
        sa.CheckConstraint(
            "coordinate_precision IN ('exact_facility', 'city_centroid', "
            "'admin1_centroid', 'country_centroid', 'unresolved')",
            name="company_supply_chain_site_coordinate_precision",
        ),
        sa.CheckConstraint(
            "verification_status IN ('verified_exact', 'verified_region', "
            "'derived_proximity', 'candidate', 'rejected')",
            name="company_supply_chain_site_verification_status",
        ),
        sa.CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="company_supply_chain_site_latitude",
        ),
        sa.CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="company_supply_chain_site_longitude",
        ),
        sa.UniqueConstraint(
            "edge_id",
            "site_kind",
            "site_name",
            "country_iso2",
            name="uq_company_supply_chain_site",
        ),
    )
    op.create_index(
        "ix_company_supply_chain_site_subject",
        "company_supply_chain_sites",
        ["subject_ticker", "verification_status"],
    )
    op.create_index(
        "ix_company_supply_chain_site_coordinates",
        "company_supply_chain_sites",
        ["latitude", "longitude"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_company_supply_chain_site_coordinates",
        table_name="company_supply_chain_sites",
    )
    op.drop_index(
        "ix_company_supply_chain_site_subject",
        table_name="company_supply_chain_sites",
    )
    op.drop_table("company_supply_chain_sites")
