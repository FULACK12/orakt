"""Add append-only cluster review decisions.

Revision ID: 20260729_0004
Revises: 20260729_0003
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260729_0004"
down_revision: str | None = "20260729_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

id_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    """Create the human-review audit log."""
    op.create_table(
        "cluster_review_decisions",
        sa.Column("id", id_type, autoincrement=True, nullable=False),
        sa.Column("cluster_job_id", id_type, nullable=False),
        sa.Column("review_key", sa.String(length=64), nullable=False),
        sa.Column("left_candidate_id", sa.String(length=64), nullable=False),
        sa.Column("right_candidate_id", sa.String(length=64), nullable=False),
        sa.Column(
            "decision",
            sa.Enum(
                "merge",
                "independent",
                "ignored",
                name="cluster_review_decision",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "applied_event_ids",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column(
            "result_metadata",
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
        sa.ForeignKeyConstraint(
            ["cluster_job_id"],
            ["cluster_jobs.id"],
            name="fk_cluster_review_decisions_cluster_job_id_cluster_jobs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_cluster_review_decisions"),
    )
    op.create_index(
        "ix_cluster_review_decisions_job_key_created",
        "cluster_review_decisions",
        ["cluster_job_id", "review_key", "created_at"],
    )


def downgrade() -> None:
    """Remove the human-review audit log."""
    op.drop_index(
        "ix_cluster_review_decisions_job_key_created",
        table_name="cluster_review_decisions",
    )
    op.drop_table("cluster_review_decisions")
