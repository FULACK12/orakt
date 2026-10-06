"""Isolated preparation queue; never consumed by the legacy research worker."""

from typing import Any

from sqlalchemy import JSON, CheckConstraint, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class EarningsResearchTask(IntegerIdMixin, TimestampMixin, Base):
    __tablename__ = "earnings_research_tasks"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_earnings_task_fingerprint"),
        CheckConstraint(
            "status IN ('blocked', 'awaiting_dispatch', 'cancelled')",
            name="earnings_task_status",
        ),
        CheckConstraint(
            "phase IN ('pre_earnings', 'release', 'post_earnings_validation')",
            name="earnings_task_phase",
        ),
        Index("ix_earnings_tasks_status_created", "status", "created_at"),
        Index("ix_earnings_tasks_ticker_period", "ticker", "fiscal_period"),
    )

    fingerprint: Mapped[str] = mapped_column(String(71), nullable=False)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    fiscal_period: Mapped[str] = mapped_column(String(64), nullable=False)
    phase: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    readiness: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
