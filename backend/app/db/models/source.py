"""News and official information sources."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, CheckConstraint, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerIdMixin, TimestampMixin
from app.db.enums import SourceType, persisted_enum

if TYPE_CHECKING:
    from app.db.models.document import Document
    from app.db.models.feed import RSSFeed


class Source(IntegerIdMixin, TimestampMixin, Base):
    """A licensed feed, publication, official body or structured API."""

    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("name", "country", name="uq_sources_name_country"),
        CheckConstraint(
            "credibility_baseline >= 0 AND credibility_baseline <= 1",
            name="credibility_baseline_range",
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str | None] = mapped_column(String(2))
    language: Mapped[str | None] = mapped_column(String(16))
    source_type: Mapped[SourceType] = mapped_column(
        persisted_enum(SourceType, "source_type"),
        default=SourceType.RSS,
        server_default=text("'rss'"),
        nullable=False,
    )
    ownership: Mapped[str | None] = mapped_column(String(255))
    credibility_baseline: Mapped[Decimal] = mapped_column(
        Numeric(4, 3),
        default=Decimal("0.500"),
        server_default=text("0.500"),
        nullable=False,
    )
    political_bias_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        server_default=text("'{}'"),
        nullable=False,
    )

    documents: Mapped[list[Document]] = relationship(
        back_populates="source",
        passive_deletes=True,
    )
    rss_feeds: Mapped[list[RSSFeed]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
