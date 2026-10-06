"""Append-only audit records for human clustering decisions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin, TimestampMixin
from app.db.enums import ClusterReviewDecision, persisted_enum


class ClusterReviewDecisionRecord(IntegerIdMixin, TimestampMixin, Base):
    """One review action over a signed rejected near-match pair."""

    __tablename__ = "cluster_review_decisions"
    __table_args__ = (
        Index(
            "ix_cluster_review_decisions_job_key_created",
            "cluster_job_id",
            "review_key",
            "created_at",
        ),
    )

    cluster_job_id: Mapped[int] = mapped_column(
        ForeignKey("cluster_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    review_key: Mapped[str] = mapped_column(String(64), nullable=False)
    left_candidate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    right_candidate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[ClusterReviewDecision] = mapped_column(
        persisted_enum(ClusterReviewDecision, "cluster_review_decision"),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(Text)
    applied_event_ids: Mapped[list[int]] = mapped_column(
        JSON,
        default=list,
        server_default=text("'[]'"),
        nullable=False,
    )
    result_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        server_default=text("'{}'"),
        nullable=False,
    )
