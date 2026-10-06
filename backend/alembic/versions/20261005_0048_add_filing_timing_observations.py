"""Retain immutable SEC acceptance timestamp observations.

Revision ID: 20261005_0048
Revises: 20261005_0047
"""

import sqlalchemy as sa

from alembic import op

revision = "20261005_0048"
down_revision = "20261005_0047"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "filing_timing_observations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("accession_number", sa.String(32), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("raw_timestamp", sa.String(128)),
        sa.Column("timestamp_status", sa.String(32), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("archive_path", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["accession_number"], ["company_filings.accession_number"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("accession_number", "payload_sha256", name="uq_filing_timing_version"),
    )
    op.create_index(
        "ix_filing_timing_accession_observed",
        "filing_timing_observations",
        ["accession_number", "observed_at"],
    )


def downgrade():
    op.drop_index("ix_filing_timing_accession_observed", table_name="filing_timing_observations")
    op.drop_table("filing_timing_observations")
