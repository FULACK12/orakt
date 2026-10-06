"""Add truthful multi-stage progress and watchdog state to cluster jobs.

Revision ID: 20260922_0044
Revises: 20260922_0043
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260922_0044"
down_revision: str | None = "20260922_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cluster_jobs",
        sa.Column("progress_percent", sa.Float(), server_default="0", nullable=False),
    )
    op.add_column(
        "cluster_jobs",
        sa.Column(
            "progress_stage",
            sa.String(length=64),
            server_default="queued",
            nullable=False,
        ),
    )
    op.add_column(
        "cluster_jobs",
        sa.Column("progress_message", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "cluster_jobs",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "cluster_jobs",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "cluster_jobs",
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
    )
    with op.batch_alter_table("cluster_jobs") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_cluster_jobs_cluster_job_progress_percent_range"),
            "progress_percent >= 0 AND progress_percent <= 100",
        )
        batch_op.create_check_constraint(
            op.f("ck_cluster_jobs_cluster_job_attempts_range"),
            "attempt_count >= 0 AND max_attempts >= 1",
        )
    op.execute(
        """
        UPDATE cluster_jobs
        SET progress_percent = CASE
                WHEN status = 'completed' THEN 100
                WHEN total_documents > 0
                    THEN CASE
                        WHEN processed_documents * 75.0 / total_documents > 75
                            THEN 75
                        ELSE processed_documents * 75.0 / total_documents
                    END
                ELSE 0
            END,
            progress_stage = CASE
                WHEN status = 'completed' THEN 'completed'
                WHEN status = 'failed' THEN 'failed'
                WHEN status = 'running' THEN 'analyzing_documents'
                ELSE 'queued'
            END,
            progress_message = CASE
                WHEN status = 'completed' THEN '聚类、事件链和逻辑链处理已完成'
                WHEN status = 'running' THEN '正在分析文档'
                ELSE SUBSTR(error_message, 1, 255)
            END,
            heartbeat_at = updated_at
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("cluster_jobs") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_cluster_jobs_cluster_job_attempts_range"),
            type_="check",
        )
        batch_op.drop_constraint(
            op.f("ck_cluster_jobs_cluster_job_progress_percent_range"),
            type_="check",
        )
        batch_op.drop_column("max_attempts")
        batch_op.drop_column("attempt_count")
        batch_op.drop_column("heartbeat_at")
        batch_op.drop_column("progress_message")
        batch_op.drop_column("progress_stage")
        batch_op.drop_column("progress_percent")
