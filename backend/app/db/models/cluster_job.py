"""Persistent background jobs for full-corpus event clustering."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, Float, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin, TimestampMixin
from app.db.enums import ClusterJobStatus, persisted_enum


class ClusterJob(IntegerIdMixin, TimestampMixin, Base):
    """One immutable document snapshot processed by a background worker."""

    __tablename__ = "cluster_jobs"
    __table_args__ = (
        CheckConstraint(
            "total_documents >= 0",
            name="total_documents_nonnegative",
        ),
        CheckConstraint(
            "processed_documents >= 0 AND "
            "processed_documents <= total_documents",
            name="processed_documents_range",
        ),
        CheckConstraint(
            "batch_size >= 1 AND batch_size <= 25",
            name="batch_size_range",
        ),
        CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="cluster_job_progress_percent_range",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND max_attempts >= 1",
            name="cluster_job_attempts_range",
        ),
        Index("ix_cluster_jobs_status_created_at", "status", "created_at"),
    )

    status: Mapped[ClusterJobStatus] = mapped_column(
        persisted_enum(ClusterJobStatus, "cluster_job_status"),
        default=ClusterJobStatus.QUEUED,
        server_default=text("'queued'"),
        nullable=False,
    )
    total_documents: Mapped[int] = mapped_column(Integer, nullable=False)
    processed_documents: Mapped[int] = mapped_column(
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
    batch_size: Mapped[int] = mapped_column(Integer, nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
