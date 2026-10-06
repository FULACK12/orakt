"""Raw and cleaned source documents."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerIdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.event import EventDocument
    from app.db.models.source import Source


class Document(IntegerIdMixin, TimestampMixin, Base):
    """One fetched article, announcement or licensed API document."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "credibility_score IS NULL OR "
            "(credibility_score >= 0 AND credibility_score <= 1)",
            name="credibility_score_range",
        ),
        Index("ix_documents_source_published_at", "source_id", "published_at"),
        Index("ix_documents_published_at", "published_at"),
    )

    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(16))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    credibility_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    raw_object_path: Mapped[str | None] = mapped_column(Text)
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        server_default=text("'{}'"),
        nullable=False,
    )

    source: Mapped[Source] = relationship(back_populates="documents")
    event_links: Mapped[list[EventDocument]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
