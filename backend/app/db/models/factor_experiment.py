"""Append-only factor replication experiments and future outcomes."""

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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class FactorExperiment(IntegerIdMixin, TimestampMixin, Base):
    """One repeated-backtest rule frozen before its prospective outcome exists."""

    __tablename__ = "factor_experiments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'future_validated', 'future_failed')",
            name="factor_experiment_status",
        ),
        CheckConstraint(
            "predicted_position IN (-1, 1)",
            name="factor_experiment_position",
        ),
        CheckConstraint(
            "forecast_horizon_observations >= 1",
            name="factor_experiment_horizon",
        ),
        UniqueConstraint("input_fingerprint", name="uq_factor_experiment_fingerprint"),
        Index(
            "ix_factor_experiments_status_anchor",
            "status",
            "anchor_observed_on",
        ),
        Index(
            "ix_factor_experiments_target_horizon",
            "target_series_id",
            "forecast_horizon_observations",
        ),
    )

    source_inquiry_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_inquiries.id", ondelete="SET NULL")
    )
    target_series_id: Mapped[str] = mapped_column(String(160), nullable=False)
    target_name: Mapped[str] = mapped_column(String(300), nullable=False)
    method_version: Mapped[str] = mapped_column(String(96), nullable=False)
    protocol_version: Mapped[str] = mapped_column(String(96), nullable=False)
    forecast_horizon_observations: Mapped[int] = mapped_column(Integer, nullable=False)
    factor_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    replication_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    anchor_observed_on: Mapped[date] = mapped_column(Date, nullable=False)
    anchor_value: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_position: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_cost_bps: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    frozen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    outcome: Mapped[FactorExperimentOutcome | None] = relationship(
        back_populates="experiment",
        uselist=False,
        cascade="all, delete-orphan",
    )


class FactorExperimentOutcome(IntegerIdMixin, Base):
    """Immutable future result for a previously frozen factor experiment."""

    __tablename__ = "factor_experiment_outcomes"
    __table_args__ = (
        UniqueConstraint("experiment_id", name="uq_factor_experiment_outcome"),
        Index("ix_factor_experiment_outcomes_observed", "outcome_observed_on"),
    )

    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("factor_experiments.id", ondelete="CASCADE"), nullable=False
    )
    outcome_observed_on: Mapped[date] = mapped_column(Date, nullable=False)
    outcome_value: Mapped[float] = mapped_column(Float, nullable=False)
    raw_return: Mapped[float] = mapped_column(Float, nullable=False)
    strategy_return: Mapped[float] = mapped_column(Float, nullable=False)
    prediction_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    outcome_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    settled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    experiment: Mapped[FactorExperiment] = relationship(back_populates="outcome")
