"""Auditable operator control requests for durable background tasks."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class TaskControlRecord(IntegerIdMixin, TimestampMixin, Base):
    """One idempotent operator request and its worker acknowledgement."""

    __tablename__ = "task_control_records"
    __table_args__ = (
        CheckConstraint(
            "task_kind IN ('research_batch_item', 'cluster_job')",
            name="task_control_record_kind",
        ),
        CheckConstraint("action = 'cancel'", name="task_control_record_action"),
        CheckConstraint(
            "status IN ('requested', 'acknowledged', 'rejected')",
            name="task_control_record_status",
        ),
        UniqueConstraint(
            "task_kind",
            "task_id",
            "action",
            name="uq_task_control_record_target_action",
        ),
        Index("ix_task_control_records_status_created", "status", "created_at"),
    )

    task_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    task_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(
        String(16),
        default="cancel",
        server_default=text("'cancel'"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        default="requested",
        server_default=text("'requested'"),
        nullable=False,
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    message: Mapped[str | None] = mapped_column(Text)
