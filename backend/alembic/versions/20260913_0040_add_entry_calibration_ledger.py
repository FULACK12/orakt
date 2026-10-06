"""Add durable multi-horizon entry calibration ledger.

Revision ID: 20260913_0040
Revises: 20260908_0039
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260913_0040"
down_revision: str | None = "20260908_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "entry_horizon_forecasts",
        sa.Column("source_inquiry_id", sa.BigInteger(), nullable=True),
        sa.Column("market_region", sa.String(length=16), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("series_id", sa.String(length=64), nullable=False),
        sa.Column("report_cutoff", sa.Date(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("horizon_key", sa.String(length=32), nullable=False),
        sa.Column("horizon_sessions", sa.Integer(), nullable=False),
        sa.Column("signal_triggered", sa.Boolean(), nullable=False),
        sa.Column("signal_score", sa.Float(), nullable=True),
        sa.Column("forecast_payload", sa.JSON(), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.CheckConstraint(
            "market_region IN ('us', 'china')",
            name=op.f("ck_entry_horizon_forecasts_entry_forecast_region"),
        ),
        sa.CheckConstraint(
            "horizon_sessions >= 1",
            name=op.f("ck_entry_horizon_forecasts_entry_forecast_horizon_sessions"),
        ),
        sa.ForeignKeyConstraint(
            ["source_inquiry_id"],
            ["research_inquiries.id"],
            name=op.f("fk_entry_horizon_forecasts_source_inquiry_id_research_inquiries"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entry_horizon_forecasts")),
        sa.UniqueConstraint(
            "series_id",
            "report_cutoff",
            "model_version",
            "horizon_key",
            name="uq_entry_forecast_window_version_horizon",
        ),
    )
    op.create_index(
        "ix_entry_forecasts_version_horizon_cutoff",
        "entry_horizon_forecasts",
        ["model_version", "horizon_key", "report_cutoff"],
    )
    op.create_table(
        "entry_horizon_outcomes",
        sa.Column("forecast_id", sa.BigInteger(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("exit_date", sa.Date(), nullable=False),
        sa.Column("entry_close", sa.Float(), nullable=False),
        sa.Column("exit_close", sa.Float(), nullable=False),
        sa.Column("net_return", sa.Float(), nullable=False),
        sa.Column("transaction_cost_bps", sa.Float(), nullable=False),
        sa.Column("target_touched_by_close", sa.Boolean(), nullable=False),
        sa.Column("stop_touched_by_close", sa.Boolean(), nullable=False),
        sa.Column("outcome_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("calculation_policy", sa.String(length=64), nullable=False),
        sa.Column(
            "settled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.CheckConstraint(
            "transaction_cost_bps >= 0", name=op.f("ck_entry_horizon_outcomes_entry_outcome_cost")
        ),
        sa.ForeignKeyConstraint(
            ["forecast_id"],
            ["entry_horizon_forecasts.id"],
            name=op.f("fk_entry_horizon_outcomes_forecast_id_entry_horizon_forecasts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entry_horizon_outcomes")),
        sa.UniqueConstraint("forecast_id", name="uq_entry_outcome_forecast"),
    )
    op.create_index("ix_entry_outcomes_exit_date", "entry_horizon_outcomes", ["exit_date"])
    op.create_table(
        "entry_parameter_candidates",
        sa.Column("base_model_version", sa.String(length=64), nullable=False),
        sa.Column("candidate_version", sa.String(length=96), nullable=False),
        sa.Column("horizon_key", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("sample_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("parameter_changes", sa.JSON(), nullable=False),
        sa.Column("comparison_metrics", sa.JSON(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('ready_for_review', 'baseline_retained', 'accepted', 'rejected')",
            name=op.f("ck_entry_parameter_candidates_entry_candidate_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entry_parameter_candidates")),
        sa.UniqueConstraint("candidate_version", name="uq_entry_candidate_version"),
    )
    op.create_index(
        "ix_entry_candidates_base_horizon_created",
        "entry_parameter_candidates",
        ["base_model_version", "horizon_key", "created_at"],
    )
    op.create_table(
        "entry_calibration_runs",
        sa.Column("status", sa.String(length=32), server_default="running", nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("forecasts_created", sa.Integer(), nullable=False),
        sa.Column("outcomes_settled", sa.Integer(), nullable=False),
        sa.Column("pending_forecasts", sa.Integer(), nullable=False),
        sa.Column("summary", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("archive_status", sa.String(length=32), nullable=False),
        sa.Column("archive_path", sa.Text(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'completed_archive_warning', 'failed')",
            name=op.f("ck_entry_calibration_runs_entry_calibration_run_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entry_calibration_runs")),
    )
    op.create_index("ix_entry_calibration_runs_started", "entry_calibration_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_entry_calibration_runs_started", table_name="entry_calibration_runs")
    op.drop_table("entry_calibration_runs")
    op.drop_index(
        "ix_entry_candidates_base_horizon_created", table_name="entry_parameter_candidates"
    )
    op.drop_table("entry_parameter_candidates")
    op.drop_index("ix_entry_outcomes_exit_date", table_name="entry_horizon_outcomes")
    op.drop_table("entry_horizon_outcomes")
    op.drop_index("ix_entry_forecasts_version_horizon_cutoff", table_name="entry_horizon_forecasts")
    op.drop_table("entry_horizon_forecasts")
