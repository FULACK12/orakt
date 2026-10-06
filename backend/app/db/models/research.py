"""Persisted local research questions and optional OpenAI audits."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class ResearchInquiry(IntegerIdMixin, TimestampMixin, Base):
    """One user-directed or autonomous local-AI research run."""

    __tablename__ = "research_inquiries"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('user_question', 'autonomous')",
            name="research_inquiry_mode",
        ),
        CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="research_inquiry_status",
        ),
        Index("ix_research_inquiries_created_at", "created_at"),
    )

    question: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default="running",
        server_default=text("'running'"),
        nullable=False,
    )
    local_model: Mapped[str] = mapped_column(String(255), nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    evidence_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        server_default=text("'{}'"),
        nullable=False,
    )
    chatgpt_review: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    review_signals: Mapped[list[ResearchReviewSignal]] = relationship(
        back_populates="inquiry",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ResearchReviewSignal.created_at",
    )


class ResearchReviewSignal(IntegerIdMixin, TimestampMixin, Base):
    """Append-only human decision over a paper-shaped research report."""

    __tablename__ = "research_review_signals"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('accepted', 'revised_accepted', 'deferred', 'rejected')",
            name="research_review_signal_decision",
        ),
        Index(
            "ix_research_review_signals_inquiry_created",
            "inquiry_id",
            "created_at",
        ),
    )

    inquiry_id: Mapped[int] = mapped_column(
        ForeignKey("research_inquiries.id", ondelete="CASCADE"),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    inquiry: Mapped[ResearchInquiry] = relationship(back_populates="review_signals")


class ResearchBatch(IntegerIdMixin, TimestampMixin, Base):
    """One durable, bounded batch of equity research questions."""

    __tablename__ = "research_batches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'partial_failed', 'failed')",
            name="research_batch_status",
        ),
        CheckConstraint("target_count >= 1", name="research_batch_target_count"),
        CheckConstraint(
            "completed_count >= 0 AND completed_count <= target_count",
            name="research_batch_completed_count",
        ),
        CheckConstraint(
            "failed_count >= 0 AND failed_count <= target_count",
            name="research_batch_failed_count",
        ),
        Index("ix_research_batches_status_created", "status", "created_at"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default="queued",
        server_default=text("'queued'"),
        nullable=False,
    )
    template_version: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    target_count: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    failed_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items: Mapped[list[ResearchBatchItem]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ResearchBatchItem.priority, ResearchBatchItem.id",
    )


class ResearchBatchItem(IntegerIdMixin, TimestampMixin, Base):
    """One recoverable company question within a durable research batch."""

    __tablename__ = "research_batch_items"
    __table_args__ = (
        CheckConstraint(
            "market_region IN ('us', 'china')",
            name="research_batch_item_region",
        ),
        CheckConstraint(
            "research_scope IN ('sec_numeric_evidence', 'market_factor_evidence')",
            name="research_batch_item_scope",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="research_batch_item_status",
        ),
        CheckConstraint("priority >= 0", name="research_batch_item_priority"),
        CheckConstraint("attempt_count >= 0", name="research_batch_item_attempts"),
        CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="research_batch_item_progress_percent",
        ),
        UniqueConstraint(
            "batch_id",
            "market_region",
            "ticker",
            name="uq_research_batch_item_target",
        ),
        Index(
            "ix_research_batch_items_status_priority",
            "status",
            "priority",
            "created_at",
        ),
    )

    batch_id: Mapped[int] = mapped_column(
        ForeignKey("research_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    market_region: Mapped[str] = mapped_column(String(16), nullable=False)
    research_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(128))
    question: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default="queued",
        server_default=text("'queued'"),
        nullable=False,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    progress_percent: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default=text("0"),
        nullable=False,
    )
    progress_stage: Mapped[str] = mapped_column(
        String(64),
        default="queued",
        server_default=text("'queued'"),
        nullable=False,
    )
    progress_message: Mapped[str | None] = mapped_column(String(255))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    inquiry_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_inquiries.id", ondelete="SET NULL")
    )
    data_readiness: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        server_default=text("'{}'"),
        nullable=False,
    )
    audit_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    checkpoint_data: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        server_default=text("'{}'"),
        nullable=False,
    )
    checkpoint_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    batch: Mapped[ResearchBatch] = relationship(back_populates="items")


class ResearchReportAuditJob(IntegerIdMixin, TimestampMixin, Base):
    """Leased, recoverable deterministic audit over one frozen research report."""

    __tablename__ = "research_report_audit_jobs"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('audit_only', 'refresh_and_audit')",
            name="research_report_audit_job_mode",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'superseded')",
            name="research_report_audit_job_status",
        ),
        CheckConstraint("priority >= 0", name="research_report_audit_job_priority"),
        CheckConstraint(
            "attempt_count >= 0 AND max_attempts >= 1",
            name="research_report_audit_job_attempts",
        ),
        UniqueConstraint(
            "inquiry_id",
            "audit_version",
            "source_fingerprint",
            name="uq_research_report_audit_source",
        ),
        Index(
            "ix_research_report_audit_jobs_claim",
            "status",
            "available_at",
            "priority",
        ),
    )

    inquiry_id: Mapped[int] = mapped_column(
        ForeignKey("research_inquiries.id", ondelete="CASCADE"),
        nullable=False,
    )
    audit_version: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default="queued",
        server_default=text("'queued'"),
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        default=3,
        server_default=text("3"),
        nullable=False,
    )
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(String(128))
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    output_fingerprint: Mapped[str | None] = mapped_column(String(64))
    before_result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    before_evidence_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    audit_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
