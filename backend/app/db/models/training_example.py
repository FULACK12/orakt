"""Externally supplied examples kept isolated until human approval."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class ExternalTrainingExample(IntegerIdMixin, TimestampMixin, Base):
    """One provenance-bearing example for an eventual local-model dataset."""

    __tablename__ = "external_training_examples"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="external_training_example_status",
        ),
        CheckConstraint(
            "quality_score >= 0 AND quality_score <= 1",
            name="external_training_example_quality_score",
        ),
        Index("ix_external_training_examples_status", "status", "created_at"),
    )

    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    input_context: Mapped[str] = mapped_column(Text, nullable=False)
    ideal_response: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2_000), nullable=False)
    license_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    quality_score: Mapped[float] = mapped_column(
        Numeric(4, 3), default=0, nullable=False
    )
    review_note: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
