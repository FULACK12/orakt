"""Hierarchical administrative places and subnational observations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class AdministrativeArea(IntegerIdMixin, TimestampMixin, Base):
    """A country subdivision or populated place with a reference point."""

    __tablename__ = "administrative_areas"
    __table_args__ = (
        UniqueConstraint(
            "source_name",
            "external_id",
            name="uq_administrative_areas_source_external_id",
        ),
        CheckConstraint(
            "level IN ('admin1', 'admin2', 'city')",
            name="administrative_area_level",
        ),
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="administrative_area_latitude",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="administrative_area_longitude",
        ),
        CheckConstraint(
            "population IS NULL OR population >= 0",
            name="administrative_area_population",
        ),
        Index(
            "ix_administrative_areas_country_level",
            "country_iso2",
            "level",
        ),
        Index("ix_administrative_areas_parent_id", "parent_id"),
    )

    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("administrative_areas.id", ondelete="SET NULL")
    )
    country_iso2: Mapped[str] = mapped_column(String(2), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ascii_name: Mapped[str | None] = mapped_column(String(255))
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    coordinate_precision: Mapped[str] = mapped_column(
        String(32),
        default="reference_point",
        nullable=False,
    )
    population: Mapped[int | None] = mapped_column(BigInteger)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    license_name: Mapped[str] = mapped_column(String(255), nullable=False)
    license_url: Mapped[str] = mapped_column(Text, nullable=False)


class RegionalIndicator(TimestampMixin, Base):
    """Metadata for a metric whose geography is below country level."""

    __tablename__ = "regional_indicators"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(128), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    license_name: Mapped[str] = mapped_column(String(255), nullable=False)
    license_url: Mapped[str] = mapped_column(Text, nullable=False)


class RegionalObservation(Base):
    """One traceable metric for an administrative area and source period."""

    __tablename__ = "regional_observations"
    __table_args__ = (
        Index(
            "ix_regional_observations_indicator_period",
            "indicator_code",
            "period",
        ),
    )

    area_id: Mapped[int] = mapped_column(
        ForeignKey("administrative_areas.id", ondelete="CASCADE"),
        primary_key=True,
    )
    indicator_code: Mapped[str] = mapped_column(
        ForeignKey("regional_indicators.code", ondelete="CASCADE"),
        primary_key=True,
    )
    period: Mapped[str] = mapped_column(String(16), primary_key=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class EventRelationCandidate(IntegerIdMixin, TimestampMixin, Base):
    """A proposed event-to-event relationship requiring human confirmation."""

    __tablename__ = "event_relation_candidates"
    __table_args__ = (
        UniqueConstraint(
            "cluster_job_id",
            "source_candidate_id",
            "target_candidate_id",
            "relation_type",
            name="uq_event_relation_candidates_edge",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="event_relation_confidence",
        ),
        CheckConstraint(
            "status IN ('suggested', 'accepted', 'rejected')",
            name="event_relation_status",
        ),
        Index(
            "ix_event_relation_candidates_job_status",
            "cluster_job_id",
            "status",
        ),
    )

    cluster_job_id: Mapped[int] = mapped_column(
        ForeignKey("cluster_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_candidate_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_candidate_id: Mapped[str] = mapped_column(String(128), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_document_ids: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        default="suggested",
        nullable=False,
    )
    pinned: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )
    review_note: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
