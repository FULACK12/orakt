"""Append-only timing observations, separate from issuer earnings announcements."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin


class FilingTimingObservation(IntegerIdMixin, Base):
    __tablename__ = "filing_timing_observations"
    __table_args__ = (
        UniqueConstraint("accession_number", "payload_sha256", name="uq_filing_timing_version"),
        Index("ix_filing_timing_accession_observed", "accession_number", "observed_at"),
    )
    accession_number: Mapped[str] = mapped_column(
        ForeignKey("company_filings.accession_number", ondelete="RESTRICT"),
        nullable=False,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_timestamp: Mapped[str | None] = mapped_column(String(128))
    timestamp_status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    archive_path: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
