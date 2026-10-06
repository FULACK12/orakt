"""Verified cold-full/hot-excerpt storage for source documents."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import SourceType
from app.db.models import Document, Source
from app.storage.archive import ArchiveReadError, ColdArchive

STORAGE_POLICY = "cold_full_hot_excerpt_v1"


class DocumentTieringResult(BaseModel):
    """Auditable outcome for one bounded document-tiering batch."""

    model_config = ConfigDict(extra="forbid")

    dry_run: bool
    scanned: int = Field(ge=0)
    archived: int = Field(ge=0)
    verified_existing: int = Field(ge=0)
    hot_bodies_trimmed: int = Field(ge=0)
    hot_characters_released: int = Field(ge=0)
    failures: int = Field(ge=0)
    last_document_id: int | None = None


def tier_document_batch(
    session: Session,
    archive: ColdArchive,
    *,
    after_id: int = 0,
    batch_size: int = 500,
    hot_body_chars: int = 2_000,
    apply: bool = False,
    source_types: tuple[SourceType, ...] = (SourceType.RSS, SourceType.NEWS),
) -> DocumentTieringResult:
    """Archive full bodies first, verify them, then retain a bounded hot excerpt."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if hot_body_chars < 256:
        raise ValueError("hot_body_chars must be at least 256")
    rows = list(
        session.scalars(
            select(Document)
            .join(Source, Source.id == Document.source_id)
            .where(Document.id > after_id, Document.body.is_not(None))
            .where(Source.source_type.in_(source_types))
            .order_by(Document.id)
            .limit(batch_size)
        )
    )
    archived = 0
    verified_existing = 0
    trimmed = 0
    released = 0
    failures = 0
    verified_at = datetime.now(UTC).isoformat()

    for document in rows:
        hot_body = document.body or ""
        if not hot_body:
            continue
        metadata = dict(document.raw_metadata or {})
        already_tiered = metadata.get("storage_policy") == STORAGE_POLICY
        archive_path = document.raw_object_path
        archived_body: str | None = None
        if archive_path:
            try:
                archived_body = str(
                    archive.load_entry(
                        archive_path,
                        expected_content_hash=document.content_hash,
                    )["body"]
                )
            except ArchiveReadError:
                failures += 1
                continue
            expected_full_chars = int(metadata.get("full_body_chars") or len(hot_body))
            if len(archived_body) < expected_full_chars:
                failures += 1
                continue
            verified_existing += 1

        if archived_body is None:
            if not apply:
                archived += 1
                if len(hot_body) > hot_body_chars:
                    trimmed += 1
                    released += len(hot_body) - hot_body_chars
                continue
            archive_path = archive.store_entry(
                content_hash=document.content_hash,
                source_id=document.source_id,
                url=document.url,
                title=document.title,
                body=hot_body,
                published_at=document.published_at,
                metadata={**metadata, "tiered_from_document_id": document.id},
            )
            try:
                archived_body = str(
                    archive.load_entry(
                        archive_path,
                        expected_content_hash=document.content_hash,
                    )["body"]
                )
            except ArchiveReadError:
                failures += 1
                continue
            if archived_body != hot_body:
                failures += 1
                continue
            archived += 1

        full_body_chars = len(archived_body)
        should_trim = len(hot_body) > hot_body_chars
        if should_trim:
            trimmed += 1
            released += len(hot_body) - hot_body_chars
        if not apply:
            continue
        document.raw_object_path = archive_path
        if should_trim:
            document.body = hot_body[:hot_body_chars]
        document.raw_metadata = {
            **metadata,
            "storage_policy": STORAGE_POLICY,
            "storage_tier": (
                "cold_full_hot_excerpt"
                if full_body_chars > hot_body_chars
                else "cold_full_hot_full"
            ),
            "full_body_chars": full_body_chars,
            "hot_body_chars": min(full_body_chars, hot_body_chars),
            "body_hot_truncated": full_body_chars > hot_body_chars,
            "cold_archive_verified_at": verified_at,
        }
        if already_tiered and not should_trim:
            document.raw_metadata["cold_archive_verified_at"] = verified_at

    return DocumentTieringResult(
        dry_run=not apply,
        scanned=len(rows),
        archived=archived,
        verified_existing=verified_existing,
        hot_bodies_trimmed=trimmed,
        hot_characters_released=released,
        failures=failures,
        last_document_id=rows[-1].id if rows else None,
    )


def document_body_for_research(
    document: Document,
    archive: ColdArchive,
) -> tuple[str, str]:
    """Return full retained text when cold storage is required and available."""
    hot_body = document.body or ""
    metadata: dict[str, Any] = document.raw_metadata or {}
    if not metadata.get("body_hot_truncated") or not document.raw_object_path:
        return hot_body, "hot"
    try:
        payload = archive.load_entry(
            document.raw_object_path,
            expected_content_hash=document.content_hash,
        )
    except ArchiveReadError:
        return hot_body, "hot_fallback"
    return str(payload["body"]), "cold"
