"""Configurable RSS/Atom feed endpoints and fetch state."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerIdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.source import Source


class RSSFeed(IntegerIdMixin, TimestampMixin, Base):
    """One RSS or Atom URL plus licensing, rate limit and HTTP cache state."""

    __tablename__ = "rss_feeds"
    __table_args__ = (
        CheckConstraint(
            "rate_limit_per_minute > 0 AND rate_limit_per_minute <= 60",
            name="rate_limit_per_minute_range",
        ),
        CheckConstraint(
            "fetch_interval_seconds >= 60",
            name="fetch_interval_seconds_minimum",
        ),
        CheckConstraint(
            "request_timeout_seconds >= 1 AND request_timeout_seconds <= 120",
            name="request_timeout_seconds_range",
        ),
        CheckConstraint(
            "consecutive_failures >= 0",
            name="consecutive_failures_nonnegative",
        ),
        Index("ix_rss_feeds_enabled_last_fetched_at", "enabled", "last_fetched_at"),
    )

    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )
    license_name: Mapped[str] = mapped_column(String(255), nullable=False)
    license_url: Mapped[str | None] = mapped_column(Text)
    rate_limit_per_minute: Mapped[Decimal] = mapped_column(
        Numeric(8, 3),
        default=Decimal("1.000"),
        server_default=text("1.000"),
        nullable=False,
    )
    fetch_interval_seconds: Mapped[int] = mapped_column(
        Integer,
        default=900,
        server_default=text("900"),
        nullable=False,
    )
    request_timeout_seconds: Mapped[Decimal] = mapped_column(
        Numeric(6, 2),
        default=Decimal("30.00"),
        server_default=text("30.00"),
        nullable=False,
    )
    user_agent: Mapped[str] = mapped_column(
        String(255),
        default="NEWS-App/0.3",
        server_default=text("'NEWS-App/0.3'"),
        nullable=False,
    )
    etag: Mapped[str | None] = mapped_column(String(512))
    last_modified: Mapped[str | None] = mapped_column(String(255))
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    last_error: Mapped[str | None] = mapped_column(Text)

    source: Mapped[Source] = relationship(back_populates="rss_feeds")

    def is_due(self, now: datetime) -> bool:
        """Return whether both schedule and recorded rate limit permit a fetch."""
        if not self.enabled:
            return False
        if self.last_fetched_at is None:
            return True

        fetched_at = self.last_fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)

        rate_limit_seconds = 60 / float(self.rate_limit_per_minute)
        wait_seconds = max(float(self.fetch_interval_seconds), rate_limit_seconds)
        return now >= fetched_at + timedelta(seconds=wait_seconds)

