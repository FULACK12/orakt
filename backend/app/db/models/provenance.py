"""Immutable off-chain commitments and recoverable devnet publishing attempts."""

from __future__ import annotations

from sqlalchemy import JSON, CheckConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class ProvenanceRecord(IntegerIdMixin, TimestampMixin, Base):
    __tablename__ = "provenance_records"
    __table_args__ = (
        UniqueConstraint("object_key", "revision", name="uq_provenance_revision"),
        UniqueConstraint("object_key", "payload_hash", name="uq_provenance_payload"),
        CheckConstraint("revision >= 1", name="provenance_revision_positive"),
        CheckConstraint("status IN ('prepared','submitted','finalized')", name="provenance_status"),
    )
    object_key: Mapped[str] = mapped_column(String(64), nullable=False)
    object_type: Mapped[str] = mapped_column(String(16), nullable=False)
    object_id: Mapped[str] = mapped_column(String(32), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_set_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    canonical_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    memo: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="prepared")
    publisher: Mapped[str | None] = mapped_column(String(64))
    unsigned_transaction: Mapped[str | None] = mapped_column(Text)
    signed_transaction: Mapped[str | None] = mapped_column(Text)
    signature: Mapped[str | None] = mapped_column(String(100), unique=True)
    last_valid_block_height: Mapped[int | None] = mapped_column(Integer)
    receipt: Mapped[dict | None] = mapped_column(JSON)
