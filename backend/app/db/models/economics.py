"""Country profiles and traceable macroeconomic time series."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class EconomicIndicator(TimestampMixin, Base):
    """Operator-reviewed metadata for one official economic indicator."""

    __tablename__ = "economic_indicators"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(128), nullable=False)
    description_en: Mapped[str] = mapped_column(Text, nullable=False)
    description_zh: Mapped[str] = mapped_column(Text, nullable=False)
    frequency: Mapped[str] = mapped_column(
        String(32),
        default="annual",
        server_default=text("'annual'"),
        nullable=False,
    )
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    license_name: Mapped[str] = mapped_column(String(255), nullable=False)
    license_url: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
    )


class CountryProfile(TimestampMixin, Base):
    """A non-aggregate country plus the official capital reference point."""

    __tablename__ = "country_profiles"
    __table_args__ = (
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="country_profile_latitude_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="country_profile_longitude_range",
        ),
        Index("ix_country_profiles_region", "region"),
    )

    iso3: Mapped[str] = mapped_column(String(3), primary_key=True)
    iso2: Mapped[str] = mapped_column(String(2), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    region: Mapped[str] = mapped_column(String(255), nullable=False)
    income_level: Mapped[str | None] = mapped_column(String(255))
    capital_city: Mapped[str | None] = mapped_column(String(255))
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    source_url: Mapped[str] = mapped_column(Text, nullable=False)


class EconomicObservation(Base):
    """One country/indicator/year value from an official structured API."""

    __tablename__ = "economic_observations"
    __table_args__ = (
        Index(
            "ix_economic_observations_indicator_year",
            "indicator_code",
            "year",
        ),
        Index(
            "ix_economic_observations_country_year",
            "country_iso3",
            "year",
        ),
    )

    country_iso3: Mapped[str] = mapped_column(
        ForeignKey("country_profiles.iso3", ondelete="CASCADE"),
        primary_key=True,
    )
    indicator_code: Mapped[str] = mapped_column(
        ForeignKey("economic_indicators.code", ondelete="CASCADE"),
        primary_key=True,
    )
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class EconomicSyncState(Base):
    """Durable status for one economic data provider."""

    __tablename__ = "economic_sync_states"
    __table_args__ = (
        CheckConstraint(
            "consecutive_failures >= 0",
            name="economic_sync_failures_nonnegative",
        ),
        CheckConstraint(
            "rows_upserted >= 0",
            name="economic_sync_rows_nonnegative",
        ),
    )

    source_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    history_start_year: Mapped[int | None] = mapped_column(Integer)
    history_end_year: Mapped[int | None] = mapped_column(Integer)
    rows_upserted: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    last_error: Mapped[str | None] = mapped_column(Text)
