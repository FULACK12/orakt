"""Add benchmark-relative entry evaluations and imported candidate reviews.

Revision ID: 20260913_0041
Revises: 20260913_0040
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260913_0041"
down_revision: str | None = "20260913_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "entry_outcome_evaluations",
        sa.Column("outcome_id", sa.BigInteger(), nullable=False),
        sa.Column("evaluation_version", sa.String(length=64), nullable=False),
        sa.Column("benchmark_series_id", sa.String(length=64), nullable=False),
        sa.Column("benchmark_entry_date", sa.Date(), nullable=True),
        sa.Column("benchmark_exit_date", sa.Date(), nullable=True),
        sa.Column("benchmark_entry_close", sa.Float(), nullable=True),
        sa.Column("benchmark_exit_close", sa.Float(), nullable=True),
        sa.Column("benchmark_return", sa.Float(), nullable=True),
        sa.Column("excess_net_return", sa.Float(), nullable=True),
        sa.Column("maximum_adverse_excursion", sa.Float(), nullable=False),
        sa.Column("maximum_favorable_excursion", sa.Float(), nullable=False),
        sa.Column("market_regime", sa.String(length=24), nullable=False),
        sa.Column("benchmark_coverage", sa.String(length=32), nullable=False),
        sa.Column("metrics_payload", sa.JSON(), nullable=False),
        sa.Column("evaluation_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.CheckConstraint(
            "market_regime IN ('risk_on', 'risk_off', 'mixed', 'unavailable')",
            name=op.f("ck_entry_outcome_evaluations_entry_evaluation_market_regime"),
        ),
        sa.ForeignKeyConstraint(
            ["outcome_id"],
            ["entry_horizon_outcomes.id"],
            name=op.f("fk_entry_outcome_evaluations_outcome_id_entry_horizon_outcomes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entry_outcome_evaluations")),
        sa.UniqueConstraint(
            "outcome_id",
            "evaluation_version",
            name="uq_entry_outcome_evaluation_version",
        ),
    )
    op.create_index(
        "ix_entry_outcome_evaluations_benchmark",
        "entry_outcome_evaluations",
        ["benchmark_series_id"],
    )
    op.create_table(
        "entry_parameter_candidate_reviews",
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column("source_system", sa.String(length=48), nullable=False),
        sa.Column("external_review_id", sa.String(length=128), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_payload", sa.JSON(), nullable=False),
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.CheckConstraint(
            "decision IN ('accept', 'revise', 'hold', 'reject')",
            name=op.f("ck_entry_parameter_candidate_reviews_entry_candidate_review_decision"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["entry_parameter_candidates.id"],
            name=op.f(
                "fk_entry_parameter_candidate_reviews_candidate_id_entry_parameter_candidates"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entry_parameter_candidate_reviews")),
        sa.UniqueConstraint(
            "source_system",
            "external_review_id",
            name="uq_entry_candidate_review_source_record",
        ),
    )
    op.create_index(
        "ix_entry_candidate_reviews_candidate_created",
        "entry_parameter_candidate_reviews",
        ["candidate_id", "source_created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_entry_candidate_reviews_candidate_created",
        table_name="entry_parameter_candidate_reviews",
    )
    op.drop_table("entry_parameter_candidate_reviews")
    op.drop_index(
        "ix_entry_outcome_evaluations_benchmark",
        table_name="entry_outcome_evaluations",
    )
    op.drop_table("entry_outcome_evaluations")
