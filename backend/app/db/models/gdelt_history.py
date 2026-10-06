"""Cold GDELT archive audit state and hot historical event aggregates."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin


class GdeltArchiveState(Base):
    """Download and import state for one official GDELT event archive."""

    __tablename__ = "gdelt_archive_states"

    archive_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    local_path: Mapped[str | None] = mapped_column(Text)
    archive_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    starts_at: Mapped[date | None] = mapped_column(Date)
    ends_at: Mapped[date | None] = mapped_column(Date)
    rows_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    aggregates_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class GdeltEventAggregate(IntegerIdMixin, Base):
    """Monthly CAMEO event counts materialized from the full cold archive."""

    __tablename__ = "gdelt_event_aggregates"
    __table_args__ = (
        UniqueConstraint(
            "month",
            "country_code",
            "event_root_code",
            "quad_class",
            name="uq_gdelt_event_aggregate_bucket",
        ),
        Index(
            "ix_gdelt_event_aggregates_month_country",
            "month",
            "country_code",
        ),
    )

    month: Mapped[date] = mapped_column(Date, nullable=False)
    country_code: Mapped[str] = mapped_column(String(8), nullable=False)
    event_root_code: Mapped[str] = mapped_column(String(8), nullable=False)
    quad_class: Mapped[int] = mapped_column(Integer, nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_mentions: Mapped[int] = mapped_column(Integer, nullable=False)
    total_sources: Mapped[int] = mapped_column(Integer, nullable=False)
    total_articles: Mapped[int] = mapped_column(Integer, nullable=False)
    goldstein_sum: Mapped[float] = mapped_column(Float, nullable=False)
    tone_sum: Mapped[float] = mapped_column(Float, nullable=False)
