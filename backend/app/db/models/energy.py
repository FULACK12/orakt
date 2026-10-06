"""Traceable EIA bulk-series catalog and materialized observations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class EnergySeries(TimestampMixin, Base):
    """Metadata for one series found in an official EIA bulk archive."""

    __tablename__ = "energy_series"
    __table_args__ = (
        CheckConstraint(
            "observation_count >= 0",
            name="energy_series_observation_count_nonnegative",
        ),
        Index("ix_energy_series_dataset_frequency", "dataset_key", "frequency"),
        Index("ix_energy_series_materialized", "materialized"),
    )

    series_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    dataset_key: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    units: Mapped[str | None] = mapped_column(String(255))
    frequency: Mapped[str | None] = mapped_column(String(32))
    start_period: Mapped[str | None] = mapped_column(String(32))
    end_period: Mapped[str | None] = mapped_column(String(32))
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observation_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    materialized: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    series_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        server_default=text("'{}'"),
        nullable=False,
    )


class EnergyObservation(Base):
    """One selected observation materialized from an archived EIA series."""

    __tablename__ = "energy_observations"
    __table_args__ = (
        Index("ix_energy_observations_period", "period"),
        Index("ix_energy_observations_series_period", "series_id", "period"),
    )

    series_id: Mapped[str] = mapped_column(
        ForeignKey("energy_series.series_id", ondelete="CASCADE"),
        primary_key=True,
    )
    period: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class EnergySyncState(Base):
    """Download, archive and import state for one EIA bulk dataset."""

    __tablename__ = "energy_sync_states"
    __table_args__ = (
        CheckConstraint(
            "archive_bytes >= 0",
            name="energy_sync_archive_bytes_nonnegative",
        ),
        CheckConstraint(
            "series_cataloged >= 0",
            name="energy_sync_series_cataloged_nonnegative",
        ),
        CheckConstraint(
            "series_materialized >= 0",
            name="energy_sync_series_materialized_nonnegative",
        ),
        CheckConstraint(
            "observations_upserted >= 0",
            name="energy_sync_observations_upserted_nonnegative",
        ),
    )

    dataset_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_last_updated: Mapped[str | None] = mapped_column(String(64))
    archive_path: Mapped[str | None] = mapped_column(Text)
    archive_sha256: Mapped[str | None] = mapped_column(String(64))
    archive_bytes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    series_cataloged: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    series_materialized: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    observations_upserted: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
