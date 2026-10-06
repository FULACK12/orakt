"""Add auditable controls for safe local task cancellation.

Revision ID: 20260922_0043
Revises: 20260913_0042
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260922_0043"
down_revision: str | None = "20260913_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_control_records",
        sa.Column("task_kind", sa.String(length=32), nullable=False),
        sa.Column(
            "task_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=16), server_default="cancel", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="requested", nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
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
            "task_kind IN ('research_batch_item', 'cluster_job')",
            name=op.f("ck_task_control_records_task_control_record_kind"),
        ),
        sa.CheckConstraint(
            "action = 'cancel'",
            name=op.f("ck_task_control_records_task_control_record_action"),
        ),
        sa.CheckConstraint(
            "status IN ('requested', 'acknowledged', 'rejected')",
            name=op.f("ck_task_control_records_task_control_record_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_control_records")),
        sa.UniqueConstraint(
            "task_kind",
            "task_id",
            "action",
            name="uq_task_control_record_target_action",
        ),
    )
    op.create_index(
        "ix_task_control_records_status_created",
        "task_control_records",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_task_control_records_status_created",
        table_name="task_control_records",
    )
    op.drop_table("task_control_records")
