"""Locally materialized ACLED conflict aggregates."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin


class ConflictAggregateObservation(IntegerIdMixin, Base):
    """One weekly ACLED Admin1/event-type aggregate."""

    __tablename__ = "conflict_aggregate_observations"
    __table_args__ = (
        UniqueConstraint(
            "week",
            "country",
            "admin1",
            "event_type",
            "sub_event_type",
            name="uq_conflict_aggregate_observation",
        ),
        CheckConstraint("events >= 0", name="conflict_events_nonnegative"),
        CheckConstraint("fatalities >= 0", name="conflict_fatalities_nonnegative"),
        CheckConstraint(
            "latitude >= -90 AND latitude <= 90",
            name="conflict_latitude_range",
        ),
        CheckConstraint(
            "longitude >= -180 AND longitude <= 180",
            name="conflict_longitude_range",
        ),
        Index("ix_conflict_aggregate_week", "week"),
        Index(
            "ix_conflict_aggregate_country_admin1_week",
            "country",
            "admin1",
            "week",
        ),
        Index(
            "ix_conflict_aggregate_coordinates",
            "latitude",
            "longitude",
        ),
    )

    week: Mapped[date] = mapped_column(Date, nullable=False)
    region: Mapped[str] = mapped_column(String(128), nullable=False)
    country: Mapped[str] = mapped_column(String(255), nullable=False)
    admin1: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    sub_event_type: Mapped[str] = mapped_column(String(255), nullable=False)
    events: Mapped[int] = mapped_column(Integer, nullable=False)
    fatalities: Mapped[int] = mapped_column(Integer, nullable=False)
    population_exposure: Mapped[float | None] = mapped_column(Float)
    disorder_type: Mapped[str] = mapped_column(String(128), nullable=False)
    area_external_id: Mapped[str | None] = mapped_column(String(64))
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    source_file: Mapped[str] = mapped_column(String(512), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConflictAggregateSyncState(Base):
    """Import status for one authenticated ACLED workbook."""

    __tablename__ = "conflict_aggregate_sync_states"
    __table_args__ = (
        CheckConstraint("rows_seen >= 0", name="conflict_sync_rows_seen_nonnegative"),
        CheckConstraint(
            "rows_imported >= 0",
            name="conflict_sync_rows_imported_nonnegative",
        ),
    )

    source_file: Mapped[str] = mapped_column(String(512), primary_key=True)
    archive_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_max_week: Mapped[date | None] = mapped_column(Date)
    rows_seen: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    rows_imported: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class ConflictCountryIndicatorObservation(IntegerIdMixin, Base):
    """One licensed ACLED country-period aggregate retained for long history."""

    __tablename__ = "conflict_country_indicator_observations"
    __table_args__ = (
        UniqueConstraint(
            "country",
            "period",
            "frequency",
            "metric",
            name="uq_conflict_country_indicator_observation",
        ),
        CheckConstraint("value >= 0", name="conflict_country_value_nonnegative"),
        Index(
            "ix_conflict_country_indicator_period",
            "metric",
            "period",
        ),
        Index(
            "ix_conflict_country_indicator_country",
            "country",
            "period",
        ),
    )

    country: Mapped[str] = mapped_column(String(255), nullable=False)
    period: Mapped[date] = mapped_column(Date, nullable=False)
    frequency: Mapped[str] = mapped_column(String(16), nullable=False)
    metric: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    source_file: Mapped[str] = mapped_column(String(512), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
