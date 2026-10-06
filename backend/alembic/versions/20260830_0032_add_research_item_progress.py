"""add observable research batch item progress

Revision ID: 20260830_0032
Revises: 20260830_0031
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260830_0032"
down_revision: str | None = "20260830_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Batch mode keeps this migration portable to SQLite, which is used by the
    # migration regression test and cannot ALTER an existing table constraint.
    with op.batch_alter_table("research_batch_items") as batch_op:
        batch_op.add_column(
            sa.Column(
                "progress_percent",
                sa.Float(),
                server_default=sa.text("0"),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "progress_stage",
                sa.String(length=64),
                server_default=sa.text("'queued'"),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column("progress_message", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_check_constraint(
            "research_batch_item_progress_percent",
            "progress_percent >= 0 AND progress_percent <= 100",
        )
    # Existing terminal items predate observable progress. Backfill them to a
    # terminal UI state instead of presenting completed reports as queued at 0%.
    op.execute(
        sa.text(
            """
            UPDATE research_batch_items
            SET progress_percent = 100,
                progress_stage = 'completed',
                progress_message = '报告和本地审计已完成',
                heartbeat_at = COALESCE(completed_at, updated_at)
            WHERE status = 'completed'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE research_batch_items
            SET progress_percent = 100,
                progress_stage = 'failed',
                progress_message = '历史任务失败，可查看错误并重试',
                heartbeat_at = COALESCE(completed_at, updated_at)
            WHERE status = 'failed'
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("research_batch_items") as batch_op:
        batch_op.drop_constraint(
            "research_batch_item_progress_percent",
            type_="check",
        )
        batch_op.drop_column("heartbeat_at")
        batch_op.drop_column("progress_message")
        batch_op.drop_column("progress_stage")
        batch_op.drop_column("progress_percent")
