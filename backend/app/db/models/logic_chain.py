"""Reviewable local-AI logic hypotheses and append-only human feedback."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class LogicChainHypothesis(IntegerIdMixin, TimestampMixin, Base):
    """A multi-step causal hypothesis proposed by the configured local model."""

    __tablename__ = "logic_chain_hypotheses"
    __table_args__ = (
        UniqueConstraint(
            "cluster_job_id",
            "premise_candidate_id",
            "outcome_candidate_id",
            name="uq_logic_chain_hypotheses_edge",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 0.75",
            name="logic_chain_confidence",
        ),
        CheckConstraint(
            "status IN ('suggested', 'accepted', 'revised_accepted', "
            "'deferred', 'rejected')",
            name="logic_chain_status",
        ),
        Index(
            "ix_logic_chain_hypotheses_job_status",
            "cluster_job_id",
            "status",
        ),
    )

    cluster_job_id: Mapped[int] = mapped_column(
        ForeignKey("cluster_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    premise_candidate_id: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome_candidate_id: Mapped[str] = mapped_column(String(128), nullable=False)
    steps: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_document_ids: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        default="suggested",
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    review_note: Mapped[str | None] = mapped_column(Text)
    suggested_correction: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LogicChainReviewSignal(IntegerIdMixin, Base):
    """One immutable human signal suitable for later local-model tuning."""

    __tablename__ = "logic_chain_review_signals"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('accepted', 'revised_accepted', "
            "'deferred', 'rejected')",
            name="logic_chain_review_signal_decision",
        ),
        Index(
            "ix_logic_chain_review_signals_hypothesis_created",
            "hypothesis_id",
            "created_at",
        ),
    )

    hypothesis_id: Mapped[int] = mapped_column(
        ForeignKey("logic_chain_hypotheses.id", ondelete="CASCADE"),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    suggested_correction: Mapped[str | None] = mapped_column(Text)
    feature_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
