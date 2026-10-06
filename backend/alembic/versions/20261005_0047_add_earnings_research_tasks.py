"""Add isolated earnings-phase preparation queue.

Revision ID: 20261005_0047
Revises: 20260924_0046
"""

import sqlalchemy as sa

from alembic import op

revision = "20261005_0047"
down_revision = "20260924_0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "earnings_research_tasks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("fingerprint", sa.String(71), nullable=False),
        sa.Column("ticker", sa.String(32), nullable=False),
        sa.Column("fiscal_period", sa.String(64), nullable=False),
        sa.Column("phase", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("readiness", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("fingerprint", name="uq_earnings_task_fingerprint"),
        sa.CheckConstraint(
            "status IN ('blocked', 'awaiting_dispatch', 'cancelled')", name="earnings_task_status"
        ),
        sa.CheckConstraint(
            "phase IN ('pre_earnings', 'release', 'post_earnings_validation')",
            name="earnings_task_phase",
        ),
    )
    op.create_index(
        "ix_earnings_tasks_status_created", "earnings_research_tasks", ["status", "created_at"]
    )
    op.create_index(
        "ix_earnings_tasks_ticker_period", "earnings_research_tasks", ["ticker", "fiscal_period"]
    )


def downgrade() -> None:
    op.drop_index("ix_earnings_tasks_ticker_period", table_name="earnings_research_tasks")
    op.drop_index("ix_earnings_tasks_status_created", table_name="earnings_research_tasks")
    op.drop_table("earnings_research_tasks")
