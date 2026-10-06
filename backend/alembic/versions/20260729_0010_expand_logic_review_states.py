"""Expand logic-chain review states for research workflows.

Revision ID: 20260729_0010
Revises: 20260729_0009
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260729_0010"
down_revision: str | None = "20260729_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow revised acceptance and evidence-waiting decisions."""
    with op.batch_alter_table("logic_chain_hypotheses") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_logic_chain_hypotheses_logic_chain_status"),
            type_="check",
        )
        batch_op.create_check_constraint(
            "logic_chain_status",
            sa.text(
                "status IN "
                "('suggested', 'accepted', 'revised_accepted', "
                "'deferred', 'rejected')"
            ),
        )
    with op.batch_alter_table("logic_chain_review_signals") as batch_op:
        batch_op.drop_constraint(
            op.f(
                "ck_logic_chain_review_signals_"
                "logic_chain_review_signal_decision"
            ),
            type_="check",
        )
        batch_op.create_check_constraint(
            "logic_chain_review_signal_decision",
            sa.text(
                "decision IN "
                "('accepted', 'revised_accepted', 'deferred', 'rejected')"
            ),
        )


def downgrade() -> None:
    """Return to binary accept/reject review states."""
    op.execute(
        sa.text(
            "UPDATE logic_chain_hypotheses SET status = 'accepted' "
            "WHERE status = 'revised_accepted'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE logic_chain_hypotheses SET status = 'rejected' "
            "WHERE status = 'deferred'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE logic_chain_review_signals SET decision = 'accepted' "
            "WHERE decision = 'revised_accepted'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE logic_chain_review_signals SET decision = 'rejected' "
            "WHERE decision = 'deferred'"
        )
    )
    with op.batch_alter_table("logic_chain_hypotheses") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_logic_chain_hypotheses_logic_chain_status"),
            type_="check",
        )
        batch_op.create_check_constraint(
            "logic_chain_status",
            sa.text("status IN ('suggested', 'accepted', 'rejected')"),
        )
    with op.batch_alter_table("logic_chain_review_signals") as batch_op:
        batch_op.drop_constraint(
            op.f(
                "ck_logic_chain_review_signals_"
                "logic_chain_review_signal_decision"
            ),
            type_="check",
        )
        batch_op.create_check_constraint(
            "logic_chain_review_signal_decision",
            sa.text("decision IN ('accepted', 'rejected')"),
        )
