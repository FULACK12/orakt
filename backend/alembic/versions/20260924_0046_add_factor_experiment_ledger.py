"""add durable factor replication and prospective validation ledger

Revision ID: 20260924_0046
Revises: 20260923_0045
Create Date: 2026-09-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260924_0046"
down_revision: str | None = "20260923_0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "factor_experiments",
        sa.Column("source_inquiry_id", sa.BigInteger(), nullable=True),
        sa.Column("target_series_id", sa.String(length=160), nullable=False),
        sa.Column("target_name", sa.String(length=300), nullable=False),
        sa.Column("method_version", sa.String(length=96), nullable=False),
        sa.Column("protocol_version", sa.String(length=96), nullable=False),
        sa.Column("forecast_horizon_observations", sa.Integer(), nullable=False),
        sa.Column("factor_ids", sa.JSON(), nullable=False),
        sa.Column("replication_summary", sa.JSON(), nullable=False),
        sa.Column("anchor_observed_on", sa.Date(), nullable=False),
        sa.Column("anchor_value", sa.Float(), nullable=False),
        sa.Column("predicted_position", sa.Integer(), nullable=False),
        sa.Column("transaction_cost_bps", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "frozen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'future_validated', 'future_failed')",
            name=op.f("ck_factor_experiments_factor_experiment_status"),
        ),
        sa.CheckConstraint(
            "predicted_position IN (-1, 1)",
            name=op.f("ck_factor_experiments_factor_experiment_position"),
        ),
        sa.CheckConstraint(
            "forecast_horizon_observations >= 1",
            name=op.f("ck_factor_experiments_factor_experiment_horizon"),
        ),
        sa.ForeignKeyConstraint(
            ["source_inquiry_id"],
            ["research_inquiries.id"],
            name=op.f("fk_factor_experiments_source_inquiry_id_research_inquiries"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_factor_experiments")),
        sa.UniqueConstraint(
            "input_fingerprint",
            name="uq_factor_experiment_fingerprint",
        ),
    )
    op.create_index(
        "ix_factor_experiments_status_anchor",
        "factor_experiments",
        ["status", "anchor_observed_on"],
    )
    op.create_index(
        "ix_factor_experiments_target_horizon",
        "factor_experiments",
        ["target_series_id", "forecast_horizon_observations"],
    )
    op.create_table(
        "factor_experiment_outcomes",
        sa.Column("experiment_id", sa.BigInteger(), nullable=False),
        sa.Column("outcome_observed_on", sa.Date(), nullable=False),
        sa.Column("outcome_value", sa.Float(), nullable=False),
        sa.Column("raw_return", sa.Float(), nullable=False),
        sa.Column("strategy_return", sa.Float(), nullable=False),
        sa.Column("prediction_correct", sa.Boolean(), nullable=False),
        sa.Column("outcome_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "settled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["experiment_id"],
            ["factor_experiments.id"],
            name=op.f("fk_factor_experiment_outcomes_experiment_id_factor_experiments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_factor_experiment_outcomes")),
        sa.UniqueConstraint("experiment_id", name="uq_factor_experiment_outcome"),
    )
    op.create_index(
        "ix_factor_experiment_outcomes_observed",
        "factor_experiment_outcomes",
        ["outcome_observed_on"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_factor_experiment_outcomes_observed",
        table_name="factor_experiment_outcomes",
    )
    op.drop_table("factor_experiment_outcomes")
    op.drop_index(
        "ix_factor_experiments_target_horizon",
        table_name="factor_experiments",
    )
    op.drop_index(
        "ix_factor_experiments_status_anchor",
        table_name="factor_experiments",
    )
    op.drop_table("factor_experiments")
