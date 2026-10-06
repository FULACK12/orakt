"""Rate-aware RSS/Atom collection with conditional requests and deduplication."""

from __future__ import annotations

import calendar
import hashlib
import re
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import feedparser  # type: ignore[import-untyped]
import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.collectors.schemas import (
    BatchCollectionResult,
    CollectionStatus,
    FeedCollectionResult,
)
from app.core.text import repair_common_mojibake
from app.db.base import utc_now
from app.db.models import Document, RSSFeed
from app.storage.archive import ColdArchive

MAX_FEED_BYTES = 5 * 1024 * 1024
WHITESPACE = re.compile(r"\s+")


class _HTMLTextExtractor(HTMLParser):
    """Extract visible text from short RSS summaries without extra dependencies."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def clean_feed_text(value: str | None) -> str:
    """Convert a small HTML fragment to normalized plain text."""
    if not value:
        return ""
    value = repair_common_mojibake(value)
    parser = _HTMLTextExtractor()
    parser.feed(unescape(value))
    parser.close()
    return WHITESPACE.sub(" ", " ".join(parser.parts)).strip()


def document_hash(title: str, body: str) -> str:
    """Return a stable SHA-256 hash for normalized feed content."""
    canonical = f"{clean_feed_text(title)}\n{clean_feed_text(body)}".encode()
    return hashlib.sha256(canonical).hexdigest()


def _valid_http_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    return value


def _literal_entry_value(
    entry: Mapping[str, Any],
    key: str,
    default: Any = None,
) -> Any:
    # feedparser's .get() emits a deprecation warning for fallback aliases.
    return entry[key] if key in entry else default  # noqa: SIM401


def _entry_datetime(entry: Mapping[str, Any]) -> datetime | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = _literal_entry_value(entry, key)
        if parsed:
            return datetime.fromtimestamp(calendar.timegm(parsed), tz=UTC)
    return None


def _entry_body(entry: Mapping[str, Any]) -> str:
    content = entry.get("content")
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, Mapping):
            return clean_feed_text(str(first.get("value") or ""))
    return clean_feed_text(
        str(entry.get("summary") or entry.get("description") or "")
    )


def _entry_metadata(entry: Mapping[str, Any], feed: RSSFeed) -> dict[str, Any]:
    authors = [
        str(author.get("name") or "")
        for author in entry.get("authors", [])
        if isinstance(author, Mapping) and author.get("name")
    ]
    tags = [
        str(tag.get("term") or "")
        for tag in entry.get("tags", [])
        if isinstance(tag, Mapping) and tag.get("term")
    ]
    return {
        "collector": "rss",
        "feed_id": feed.id,
        "feed_url": feed.url,
        "entry_id": str(entry.get("id") or entry.get("guid") or ""),
        "published": str(_literal_entry_value(entry, "published", "")),
        "updated": str(_literal_entry_value(entry, "updated", "")),
        "authors": authors,
        "tags": tags,
        "license_name": feed.license_name,
        "license_url": feed.license_url,
    }


class RSSCollector:
    """Collect configured feeds while isolating source-level failures."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        clock: Callable[[], datetime] = utc_now,
        max_feed_bytes: int = MAX_FEED_BYTES,
        archive: ColdArchive | None = None,
        hot_body_chars: int = 2_000,
    ) -> None:
        self.client = client
        self.clock = clock
        self.max_feed_bytes = max_feed_bytes
        self.archive = archive
        self.hot_body_chars = hot_body_chars

    async def collect_feed(
        self,
        session: Session,
        feed: RSSFeed,
        *,
        force: bool = False,
    ) -> FeedCollectionResult:
        """Fetch and persist one feed without committing the transaction."""
        now = self.clock()
        if not feed.enabled:
            return self._result(feed, "skipped_disabled")
        if not force and not feed.is_due(now):
            return self._result(feed, "skipped_not_due")

        headers = {
            "Accept": (
                "application/atom+xml, application/rss+xml, "
                "application/xml;q=0.9, text/xml;q=0.8"
            ),
            "User-Agent": feed.user_agent,
        }
        if feed.etag:
            headers["If-None-Match"] = feed.etag
        if feed.last_modified:
            headers["If-Modified-Since"] = feed.last_modified

        try:
            response = await self.client.get(
                feed.url,
                headers=headers,
                timeout=float(feed.request_timeout_seconds),
            )
        except httpx.HTTPError as exc:
            return self._failed_result(session, feed, now, f"HTTP request failed: {exc}")

        feed.last_fetched_at = now
        if response.status_code == httpx.codes.NOT_MODIFIED:
            self._record_success(feed, now)
            session.flush()
            return self._result(feed, "not_modified", http_status=response.status_code)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            return self._failed_result(
                session,
                feed,
                now,
                f"HTTP status {exc.response.status_code}",
                http_status=exc.response.status_code,
            )

        if len(response.content) > self.max_feed_bytes:
            return self._failed_result(
                session,
                feed,
                now,
                f"Feed exceeds {self.max_feed_bytes} byte limit",
                http_status=response.status_code,
            )

        parsed: Mapping[str, Any] = feedparser.parse(response.content)
        entries = list(parsed.get("entries", []))
        if parsed.get("bozo") and not entries:
            parse_error = parsed.get("bozo_exception")
            return self._failed_result(
                session,
                feed,
                now,
                f"Feed parse failed: {parse_error}",
                http_status=response.status_code,
            )

        candidates: list[tuple[Mapping[str, Any], str, str, str, str]] = []
        invalid_entries = 0
        for raw_entry in entries:
            if not isinstance(raw_entry, Mapping):
                invalid_entries += 1
                continue
            url = _valid_http_url(str(raw_entry.get("link") or ""))
            title = clean_feed_text(str(raw_entry.get("title") or ""))
            body = _entry_body(raw_entry)
            if url is None or not title:
                invalid_entries += 1
                continue
            content_hash = document_hash(title, body)
            candidates.append((raw_entry, url, title, body, content_hash))

        existing_urls: set[str] = set()
        existing_hashes: set[str] = set()
        existing_by_url: dict[str, Document] = {}
        existing_by_hash: dict[str, Document] = {}
        if candidates:
            urls = [candidate[1] for candidate in candidates]
            hashes = [candidate[4] for candidate in candidates]
            rows = session.scalars(
                select(Document).where(
                    or_(Document.url.in_(urls), Document.content_hash.in_(hashes))
                )
            )
            for document in rows:
                existing_urls.add(document.url)
                existing_hashes.add(document.content_hash)
                existing_by_url[document.url] = document
                existing_by_hash[document.content_hash] = document

        documents_created = 0
        documents_enriched = 0
        duplicates_skipped = 0
        for entry, url, title, body, content_hash in candidates:
            existing = existing_by_url.get(url)
            if existing is not None:
                if _should_enrich_document(existing, body):
                    metadata = _entry_metadata(entry, feed)
                    conflicting = existing_by_hash.get(content_hash)
                    if conflicting is not None and conflicting.id != existing.id:
                        content_hash = document_hash(title, f"{body}\nsource-url:{url}")
                    raw_object_path = None
                    if self.archive is not None:
                        raw_object_path = self.archive.store_entry(
                            content_hash=content_hash,
                            source_id=feed.source_id,
                            url=url,
                            title=title,
                            body=body,
                            published_at=_entry_datetime(entry),
                            metadata=metadata,
                        )
                    existing.title = title
                    existing.body = self._hot_body(body)
                    existing.source_id = feed.source_id
                    existing.language = (
                        str(entry.get("language") or feed.source.language or "") or None
                    )
                    existing.published_at = _entry_datetime(entry) or existing.published_at
                    existing.content_hash = content_hash
                    existing.credibility_score = feed.source.credibility_baseline
                    existing.raw_object_path = raw_object_path or existing.raw_object_path
                    existing.raw_metadata = {
                        **(existing.raw_metadata or {}),
                        "content_collector": "rss",
                        "rss_feed_id": feed.id,
                        "rss_feed_url": feed.url,
                        "license_name": feed.license_name,
                        "license_url": feed.license_url,
                        "metadata_only": False,
                        "body_is_feed_supplied": True,
                        "evidence_tier": (
                            "feed_content" if len(body) >= 100 else "feed_snippet"
                        ),
                        **self._storage_metadata(body, raw_object_path),
                    }
                    existing_hashes.add(content_hash)
                    existing_by_hash[content_hash] = existing
                    documents_enriched += 1
                else:
                    duplicates_skipped += 1
                continue
            if content_hash in existing_hashes:
                duplicates_skipped += 1
                continue
            published_at = _entry_datetime(entry)
            metadata = _entry_metadata(entry, feed)
            raw_object_path = None
            if self.archive is not None:
                raw_object_path = self.archive.store_entry(
                    content_hash=content_hash,
                    source_id=feed.source_id,
                    url=url,
                    title=title,
                    body=body,
                    published_at=published_at,
                    metadata=metadata,
                )
            session.add(
                Document(
                    source_id=feed.source_id,
                    url=url,
                    title=title,
                    body=self._hot_body(body) or None,
                    language=str(entry.get("language") or feed.source.language or "") or None,
                    published_at=published_at,
                    content_hash=content_hash,
                    credibility_score=feed.source.credibility_baseline,
                    raw_object_path=raw_object_path,
                    raw_metadata={
                        **metadata,
                        **self._storage_metadata(body, raw_object_path),
                    },
                )
            )
            existing_urls.add(url)
            existing_hashes.add(content_hash)
            documents_created += 1

        feed.etag = response.headers.get("etag", "")[:512] or None
        feed.last_modified = response.headers.get("last-modified", "")[:255] or None
        self._record_success(feed, now)
        session.flush()
        return self._result(
            feed,
            "success",
            http_status=response.status_code,
            entries_seen=len(entries),
            documents_created=documents_created,
            documents_enriched=documents_enriched,
            duplicates_skipped=duplicates_skipped,
            invalid_entries=invalid_entries,
        )

    def _hot_body(self, body: str) -> str:
        if self.archive is None or len(body) <= self.hot_body_chars:
            return body
        return body[: self.hot_body_chars]

    def _storage_metadata(
        self,
        body: str,
        raw_object_path: str | None,
    ) -> dict[str, Any]:
        if raw_object_path is None:
            return {}
        return {
            "storage_policy": "cold_full_hot_excerpt_v1",
            "storage_tier": (
                "cold_full_hot_excerpt"
                if len(body) > self.hot_body_chars
                else "cold_full_hot_full"
            ),
            "full_body_chars": len(body),
            "hot_body_chars": min(len(body), self.hot_body_chars),
            "body_hot_truncated": len(body) > self.hot_body_chars,
        }

    async def collect_many(
        self,
        session: Session,
        feeds: Iterable[RSSFeed],
        *,
        force: bool = False,
    ) -> BatchCollectionResult:
        """Collect feeds sequentially and commit/rollback each one independently."""
        results: list[FeedCollectionResult] = []
        for feed in feeds:
            try:
                result = await self.collect_feed(session, feed, force=force)
                session.commit()
            except Exception as exc:
                session.rollback()
                result = self._result(
                    feed,
                    "error",
                    error=f"Unexpected collector failure: {exc}",
                )
            results.append(result)
        return BatchCollectionResult(results=results)

    @staticmethod
    def _record_success(feed: RSSFeed, now: datetime) -> None:
        feed.last_success_at = now
        feed.consecutive_failures = 0
        feed.last_error = None

    def _failed_result(
        self,
        session: Session,
        feed: RSSFeed,
        now: datetime,
        error: str,
        *,
        http_status: int | None = None,
    ) -> FeedCollectionResult:
        feed.last_fetched_at = now
        feed.consecutive_failures += 1
        feed.last_error = error[:2000]
        session.flush()
        return self._result(
            feed,
            "error",
            http_status=http_status,
            error=feed.last_error,
        )

    @staticmethod
    def _result(
        feed: RSSFeed,
        status: CollectionStatus,
        *,
        http_status: int | None = None,
        entries_seen: int = 0,
        documents_created: int = 0,
        documents_enriched: int = 0,
        duplicates_skipped: int = 0,
        invalid_entries: int = 0,
        error: str | None = None,
    ) -> FeedCollectionResult:
        return FeedCollectionResult(
            feed_id=feed.id,
            feed_url=feed.url,
            status=status,
            http_status=http_status,
            entries_seen=entries_seen,
            documents_created=documents_created,
            documents_enriched=documents_enriched,
            duplicates_skipped=duplicates_skipped,
            invalid_entries=invalid_entries,
            error=error,
        )


def _should_enrich_document(document: Document, body: str) -> bool:
    """Upgrade a discovery-only row when a configured feed supplies more text."""
    existing_body = (document.body or "").strip()
    metadata = document.raw_metadata or {}
    return bool(body.strip()) and (
        bool(metadata.get("metadata_only"))
        or len(body.strip()) > len(existing_body) + 40
    )
