"""Cached local-AI extraction and embedding results per document."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class DocumentAnalysis(TimestampMixin, Base):
    """Validated analysis cache keyed by immutable document content."""

    __tablename__ = "document_analyses"
    __table_args__ = (
        Index(
            "ix_document_analyses_last_cluster_job_id",
            "last_cluster_job_id",
        ),
    )

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    extractor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    extraction: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    embedding_provider: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    embeddings: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_cluster_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("cluster_jobs.id", ondelete="SET NULL"),
    )
