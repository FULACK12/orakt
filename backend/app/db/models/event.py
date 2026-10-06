"""Canonical events and links back to their supporting documents."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerIdMixin, TimestampMixin
from app.db.enums import DocumentStance, EventStatus, persisted_enum

if TYPE_CHECKING:
    from app.db.models.document import Document


class Event(IntegerIdMixin, TimestampMixin, Base):
    """One canonical real-world event merged from one or more documents."""

    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("severity >= 0 AND severity <= 1", name="severity_range"),
        CheckConstraint("novelty >= 0 AND novelty <= 1", name="novelty_range"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="latitude_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="longitude_range",
        ),
        CheckConstraint(
            "end_at IS NULL OR end_at >= start_at",
            name="time_range",
        ),
        Index("ix_events_country_start_at", "country_code", "start_at"),
        Index("ix_events_type_start_at", "event_type", "start_at"),
        Index("ix_events_status_updated_at", "status", "updated_at"),
    )

    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[EventStatus] = mapped_column(
        persisted_enum(EventStatus, "event_status"),
        default=EventStatus.PARTIALLY_CONFIRMED,
        server_default=text("'partially_confirmed'"),
        nullable=False,
    )
    severity: Mapped[Decimal] = mapped_column(
        Numeric(4, 3),
        default=Decimal("0.000"),
        server_default=text("0.000"),
        nullable=False,
    )
    novelty: Mapped[Decimal] = mapped_column(
        Numeric(4, 3),
        default=Decimal("0.000"),
        server_default=text("0.000"),
        nullable=False,
    )
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(4, 3),
        default=Decimal("0.000"),
        server_default=text("0.000"),
        nullable=False,
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    country_code: Mapped[str | None] = mapped_column(String(2))

    document_links: Mapped[list[EventDocument]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class EventDocument(Base):
    """Evidence link joining one canonical event to one source document."""

    __tablename__ = "event_documents"
    __table_args__ = (
        CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1",
            name="relevance_score_range",
        ),
        Index("ix_event_documents_document_id", "document_id"),
    )

    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        primary_key=True,
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    relevance_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 3),
        default=Decimal("1.000"),
        server_default=text("1.000"),
        nullable=False,
    )
    stance: Mapped[DocumentStance] = mapped_column(
        persisted_enum(DocumentStance, "document_stance"),
        default=DocumentStance.NEUTRAL,
        server_default=text("'neutral'"),
        nullable=False,
    )
    is_primary_source: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )

    event: Mapped[Event] = relationship(back_populates="document_links")
    document: Mapped[Document] = relationship(back_populates="event_links")

