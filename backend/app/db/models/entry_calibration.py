"""Durable, append-only entry-scenario forecasts and realized outcomes."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class EntryHorizonForecast(IntegerIdMixin, Base):
    """One frozen point-in-time horizon forecast for a company/date window."""

    __tablename__ = "entry_horizon_forecasts"
    __table_args__ = (
        CheckConstraint("market_region IN ('us', 'china')", name="entry_forecast_region"),
        CheckConstraint("horizon_sessions >= 1", name="entry_forecast_horizon_sessions"),
        UniqueConstraint(
            "series_id",
            "report_cutoff",
            "model_version",
            "horizon_key",
            name="uq_entry_forecast_window_version_horizon",
        ),
        Index(
            "ix_entry_forecasts_version_horizon_cutoff",
            "model_version",
            "horizon_key",
            "report_cutoff",
        ),
    )

    source_inquiry_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_inquiries.id", ondelete="SET NULL")
    )
    market_region: Mapped[str] = mapped_column(String(16), nullable=False)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    series_id: Mapped[str] = mapped_column(String(64), nullable=False)
    report_cutoff: Mapped[date] = mapped_column(Date, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    horizon_key: Mapped[str] = mapped_column(String(32), nullable=False)
    horizon_sessions: Mapped[int] = mapped_column(Integer, nullable=False)
    signal_triggered: Mapped[bool] = mapped_column(Boolean, nullable=False)
    signal_score: Mapped[float | None] = mapped_column(Float)
    forecast_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    outcome: Mapped[EntryHorizonOutcome | None] = relationship(
        back_populates="forecast", uselist=False, cascade="all, delete-orphan"
    )


class EntryHorizonOutcome(IntegerIdMixin, Base):
    """Immutable result inserted only after a forecast horizon has matured."""

    __tablename__ = "entry_horizon_outcomes"
    __table_args__ = (
        UniqueConstraint("forecast_id", name="uq_entry_outcome_forecast"),
        CheckConstraint("transaction_cost_bps >= 0", name="entry_outcome_cost"),
        Index("ix_entry_outcomes_exit_date", "exit_date"),
    )

    forecast_id: Mapped[int] = mapped_column(
        ForeignKey("entry_horizon_forecasts.id", ondelete="CASCADE"), nullable=False
    )
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    exit_date: Mapped[date] = mapped_column(Date, nullable=False)
    entry_close: Mapped[float] = mapped_column(Float, nullable=False)
    exit_close: Mapped[float] = mapped_column(Float, nullable=False)
    net_return: Mapped[float] = mapped_column(Float, nullable=False)
    transaction_cost_bps: Mapped[float] = mapped_column(Float, nullable=False)
    target_touched_by_close: Mapped[bool] = mapped_column(Boolean, nullable=False)
    stop_touched_by_close: Mapped[bool] = mapped_column(Boolean, nullable=False)
    outcome_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    calculation_policy: Mapped[str] = mapped_column(String(64), nullable=False)
    settled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    forecast: Mapped[EntryHorizonForecast] = relationship(back_populates="outcome")
    evaluations: Mapped[list[EntryOutcomeEvaluation]] = relationship(
        back_populates="outcome", cascade="all, delete-orphan"
    )


class EntryOutcomeEvaluation(IntegerIdMixin, Base):
    """Append-only benchmark and path-risk evaluation of one immutable outcome."""

    __tablename__ = "entry_outcome_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "outcome_id",
            "evaluation_version",
            name="uq_entry_outcome_evaluation_version",
        ),
        CheckConstraint(
            "market_regime IN ('risk_on', 'risk_off', 'mixed', 'unavailable')",
            name="entry_evaluation_market_regime",
        ),
        Index("ix_entry_outcome_evaluations_benchmark", "benchmark_series_id"),
    )

    outcome_id: Mapped[int] = mapped_column(
        ForeignKey("entry_horizon_outcomes.id", ondelete="CASCADE"), nullable=False
    )
    evaluation_version: Mapped[str] = mapped_column(String(64), nullable=False)
    benchmark_series_id: Mapped[str] = mapped_column(String(64), nullable=False)
    benchmark_entry_date: Mapped[date | None] = mapped_column(Date)
    benchmark_exit_date: Mapped[date | None] = mapped_column(Date)
    benchmark_entry_close: Mapped[float | None] = mapped_column(Float)
    benchmark_exit_close: Mapped[float | None] = mapped_column(Float)
    benchmark_return: Mapped[float | None] = mapped_column(Float)
    excess_net_return: Mapped[float | None] = mapped_column(Float)
    sector_benchmark_series_id: Mapped[str | None] = mapped_column(String(96))
    sector_benchmark_entry_date: Mapped[date | None] = mapped_column(Date)
    sector_benchmark_exit_date: Mapped[date | None] = mapped_column(Date)
    sector_benchmark_return: Mapped[float | None] = mapped_column(Float)
    sector_excess_net_return: Mapped[float | None] = mapped_column(Float)
    sector_benchmark_coverage: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'unavailable'")
    )
    maximum_adverse_excursion: Mapped[float] = mapped_column(Float, nullable=False)
    maximum_favorable_excursion: Mapped[float] = mapped_column(Float, nullable=False)
    market_regime: Mapped[str] = mapped_column(String(24), nullable=False)
    benchmark_coverage: Mapped[str] = mapped_column(String(32), nullable=False)
    metrics_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evaluation_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    outcome: Mapped[EntryHorizonOutcome] = relationship(back_populates="evaluations")


class EntryParameterCandidate(IntegerIdMixin, TimestampMixin, Base):
    """Review-gated parameter candidate; never replaces production automatically."""

    __tablename__ = "entry_parameter_candidates"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ready_for_review', 'baseline_retained', 'accepted', 'rejected')",
            name="entry_candidate_status",
        ),
        UniqueConstraint("candidate_version", name="uq_entry_candidate_version"),
        Index(
            "ix_entry_candidates_base_horizon_created",
            "base_model_version",
            "horizon_key",
            "created_at",
        ),
    )

    base_model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_version: Mapped[str] = mapped_column(String(96), nullable=False)
    horizon_key: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    sample_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    parameter_changes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    comparison_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    reviews: Mapped[list[EntryParameterCandidateReview]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )


class EntryParameterCandidateReview(IntegerIdMixin, Base):
    """Idempotently imported human review; never promotes production by itself."""

    __tablename__ = "entry_parameter_candidate_reviews"
    __table_args__ = (
        UniqueConstraint(
            "source_system",
            "external_review_id",
            name="uq_entry_candidate_review_source_record",
        ),
        CheckConstraint(
            "decision IN ('accept', 'revise', 'hold', 'reject')",
            name="entry_candidate_review_decision",
        ),
        Index(
            "ix_entry_candidate_reviews_candidate_created",
            "candidate_id",
            "source_created_at",
        ),
    )

    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("entry_parameter_candidates.id", ondelete="CASCADE"), nullable=False
    )
    source_system: Mapped[str] = mapped_column(String(48), nullable=False)
    external_review_id: Mapped[str] = mapped_column(String(128), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    source_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    payload_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    candidate: Mapped[EntryParameterCandidate] = relationship(back_populates="reviews")


class EntryCalibrationRun(IntegerIdMixin, TimestampMixin, Base):
    """One scheduled reconciliation and archive attempt."""

    __tablename__ = "entry_calibration_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'completed_archive_warning', 'failed')",
            name="entry_calibration_run_status",
        ),
        Index("ix_entry_calibration_runs_started", "started_at"),
    )

    status: Mapped[str] = mapped_column(
        String(32), default="running", server_default=text("'running'"), nullable=False
    )
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    forecasts_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    outcomes_settled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pending_forecasts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )
    archive_status: Mapped[str] = mapped_column(String(32), default="not_attempted", nullable=False)
    archive_path: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
