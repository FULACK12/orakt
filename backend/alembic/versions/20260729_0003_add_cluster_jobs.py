"""Add persistent background event-clustering jobs.

Revision ID: 20260729_0003
Revises: 20260729_0002
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260729_0003"
down_revision: str | None = "20260729_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

id_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    """Create the durable clustering job queue."""
    op.create_table(
        "cluster_jobs",
        sa.Column("id", id_type, autoincrement=True, nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "completed",
                "failed",
                name="cluster_job_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column("total_documents", sa.Integer(), nullable=False),
        sa.Column(
            "processed_documents",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("batch_size", sa.Integer(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            "batch_size >= 1 AND batch_size <= 25",
            name="batch_size_range",
        ),
        sa.CheckConstraint(
            "processed_documents >= 0 AND "
            "processed_documents <= total_documents",
            name="processed_documents_range",
        ),
        sa.CheckConstraint(
            "total_documents >= 0",
            name="total_documents_nonnegative",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_cluster_jobs"),
    )
    op.create_index(
        "ix_cluster_jobs_status_created_at",
        "cluster_jobs",
        ["status", "created_at"],
    )


def downgrade() -> None:
    """Remove the durable clustering job queue."""
    op.drop_index(
        "ix_cluster_jobs_status_created_at",
        table_name="cluster_jobs",
    )
    op.drop_table("cluster_jobs")
