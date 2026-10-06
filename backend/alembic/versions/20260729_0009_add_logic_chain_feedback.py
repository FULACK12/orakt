"""Add local-AI logic hypotheses and append-only review signals.

Revision ID: 20260729_0009
Revises: 20260729_0008
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260729_0009"
down_revision: str | None = "20260729_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create reviewable hypotheses and immutable human-training signals."""
    op.create_table(
        "logic_chain_hypotheses",
        sa.Column("cluster_job_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("premise_candidate_id", sa.String(length=128), nullable=False),
        sa.Column("outcome_candidate_id", sa.String(length=128), nullable=False),
        sa.Column("steps", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("evidence_document_ids", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("suggested_correction", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 0.75",
            name=op.f("ck_logic_chain_hypotheses_logic_chain_confidence"),
        ),
        sa.CheckConstraint(
            "status IN ('suggested', 'accepted', 'rejected')",
            name=op.f("ck_logic_chain_hypotheses_logic_chain_status"),
        ),
        sa.ForeignKeyConstraint(
            ["cluster_job_id"],
            ["cluster_jobs.id"],
            name=op.f("fk_logic_chain_hypotheses_cluster_job_id_cluster_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_logic_chain_hypotheses")),
        sa.UniqueConstraint(
            "cluster_job_id",
            "premise_candidate_id",
            "outcome_candidate_id",
            name="uq_logic_chain_hypotheses_edge",
        ),
    )
    op.create_index(
        "ix_logic_chain_hypotheses_job_status",
        "logic_chain_hypotheses",
        ["cluster_job_id", "status"],
    )
    op.create_table(
        "logic_chain_review_signals",
        sa.Column("hypothesis_id", sa.BigInteger(), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("suggested_correction", sa.Text(), nullable=True),
        sa.Column("feature_snapshot", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.CheckConstraint(
            "decision IN ('accepted', 'rejected')",
            name=op.f(
                "ck_logic_chain_review_signals_logic_chain_review_signal_decision"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["hypothesis_id"],
            ["logic_chain_hypotheses.id"],
            name=op.f(
                "fk_logic_chain_review_signals_hypothesis_id_logic_chain_hypotheses"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_logic_chain_review_signals"),
        ),
    )
    op.create_index(
        "ix_logic_chain_review_signals_hypothesis_created",
        "logic_chain_review_signals",
        ["hypothesis_id", "created_at"],
    )


def downgrade() -> None:
    """Remove local-AI logic hypotheses and feedback history."""
    op.drop_index(
        "ix_logic_chain_review_signals_hypothesis_created",
        table_name="logic_chain_review_signals",
    )
    op.drop_table("logic_chain_review_signals")
    op.drop_index(
        "ix_logic_chain_hypotheses_job_status",
        table_name="logic_chain_hypotheses",
    )
    op.drop_table("logic_chain_hypotheses")
