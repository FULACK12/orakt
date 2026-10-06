"""Publisher-page full-text expansion for short RSS/news documents."""

from __future__ import annotations

import asyncio
import json
import re
from collections import deque
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.orm import Session

from app.collectors.rss import clean_feed_text, document_hash
from app.db.enums import SourceType
from app.db.models import Document, EventDocument, Source
from app.storage.archive import ArchiveCapacityError, ColdArchive
from app.storage.document_tiering import STORAGE_POLICY

ARTICLE_BODY_PATTERN = re.compile(
    r'"articleBody"\s*:\s*("(?:\\.|[^"\\])*")',
    re.IGNORECASE | re.DOTALL,
)
CONTENT_HINT_PATTERN = re.compile(
    r"(?:article|story|post|entry|main)[-_ ]?(?:body|content|text)?|body[-_ ]?content",
    re.IGNORECASE,
)
BLOCKED_TAGS = {"script", "style", "svg", "nav", "header", "footer", "form", "aside"}
VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
PUBLISHER_CONTENT_HINTS: dict[str, tuple[str, ...]] = {
    "africanews.com": ("article__body", "article-content__text"),
    "antaranews.com": ("article__entry", "wrap__article-detail-content"),
    "bbc.com": ("text-block", "article-body", "story-body"),
    "france24.com": ("t-content__body", "article__content", "m-item-content"),
    "news.ltn.com.tw": ("boxtext",),
    "news.un.org": ("field--name-field-text-column", "field--name-body", "node__content"),
    "sina.com.cn": ("artibody", "article_content"),
}
NON_ARTICLE_DOMAINS = {"earthquake.usgs.gov"}
PERMANENT_FULLTEXT_STATUSES = {
    "non_article_source",
    "robots_disallowed",
    "unsupported_response",
    "http_400",
    "http_401",
    "http_403",
    "http_404",
    "http_406",
    "http_407",
    "http_410",
    "http_451",
}


class FullTextExpansionResult(BaseModel):
    """Auditable outcome for one bounded publisher-page expansion pass."""

    model_config = ConfigDict(extra="forbid")

    scanned: int = Field(ge=0)
    expanded: int = Field(ge=0)
    insufficient: int = Field(ge=0)
    blocked: int = Field(ge=0)
    failed: int = Field(ge=0)
    duplicate: int = Field(ge=0)
    retryable: int = Field(ge=0)
    permanent: int = Field(ge=0)
    archived_characters: int = Field(ge=0)


class _DomainThrottle:
    """Bound total concurrency and serialize requests to each publisher origin."""

    def __init__(self, *, max_concurrency: int, domain_delay_seconds: float) -> None:
        self._global = asyncio.Semaphore(max_concurrency)
        self._domain_delay_seconds = domain_delay_seconds
        self._locks: dict[str, asyncio.Lock] = {}
        self._next_allowed: dict[str, float] = {}

    async def get(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        headers: dict[str, str],
    ) -> httpx.Response:
        parts = urlsplit(url)
        origin = f"{parts.scheme.casefold()}://{parts.netloc.casefold()}"
        lock = self._locks.setdefault(origin, asyncio.Lock())
        async with lock:
            loop = asyncio.get_running_loop()
            wait_seconds = self._next_allowed.get(origin, 0.0) - loop.time()
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            async with self._global:
                response = await client.get(url, headers=headers)
            self._next_allowed[origin] = loop.time() + self._domain_delay_seconds
            return response


class _ArticleParser(HTMLParser):
    def __init__(self, *, publisher_hints: tuple[str, ...] = ()) -> None:
        super().__init__(convert_charrefs=True)
        self.publisher_hints = tuple(value.casefold() for value in publisher_hints)
        self.frames: list[tuple[str, bool, bool, bool, bool]] = []
        self.blocked_level = 0
        self.content_level = 0
        self.publisher_level = 0
        self.paragraph_level = 0
        self.content_chunks: list[str] = []
        self.publisher_chunks: list[str] = []
        self.paragraph_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.casefold()
        attributes = {key.casefold(): value or "" for key, value in attrs}
        descriptor = " ".join(f"{key}={value}" for key, value in attributes.items()).casefold()
        if normalized in VOID_TAGS:
            return
        blocked = normalized in BLOCKED_TAGS
        publisher = bool(self.publisher_hints) and any(
            hint in descriptor for hint in self.publisher_hints
        )
        content = (
            normalized in {"article", "main"}
            or bool(CONTENT_HINT_PATTERN.search(descriptor))
            or publisher
        )
        paragraph = normalized == "p"
        if blocked:
            self.blocked_level += 1
        if content:
            self.content_level += 1
        if publisher:
            self.publisher_level += 1
        if paragraph:
            self.paragraph_level += 1
        self.frames.append((normalized, blocked, content, publisher, paragraph))

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        match_index = next(
            (
                index
                for index in range(len(self.frames) - 1, -1, -1)
                if self.frames[index][0] == normalized
            ),
            None,
        )
        if match_index is None:
            return
        for _, blocked, content, publisher, paragraph in self.frames[match_index:]:
            self.blocked_level -= int(blocked)
            self.content_level -= int(content)
            self.publisher_level -= int(publisher)
            self.paragraph_level -= int(paragraph)
        del self.frames[match_index:]

    def handle_data(self, data: str) -> None:
        if self.blocked_level > 0:
            return
        text = clean_feed_text(data)
        if len(text) < 2:
            return
        if self.content_level > 0:
            self.content_chunks.append(text)
        if self.publisher_level > 0:
            self.publisher_chunks.append(text)
        if self.paragraph_level > 0:
            self.paragraph_chunks.append(text)


class _JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_json_ld = False
        self.current: list[str] = []
        self.payloads: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "script":
            return
        attributes = {key.casefold(): value or "" for key, value in attrs}
        if "ld+json" in attributes.get("type", "").casefold():
            self.in_json_ld = True
            self.current = []

    def handle_data(self, data: str) -> None:
        if self.in_json_ld:
            self.current.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self.in_json_ld:
            self.payloads.append("".join(self.current))
            self.in_json_ld = False
            self.current = []


def extract_article_text(html: str, *, publisher_domain: str | None = None) -> tuple[str, str]:
    """Extract the most likely article body without executing page scripts."""
    structured_body = _structured_article_body(html)
    if len(structured_body) >= 600:
        return structured_body, "json_ld_article_body"
    json_ld_match = ARTICLE_BODY_PATTERN.search(html)
    if json_ld_match:
        try:
            body = clean_feed_text(str(json.loads(json_ld_match.group(1))))
        except (json.JSONDecodeError, TypeError):
            body = ""
        if len(body) >= 600:
            return body, "json_ld_article_body"

    normalized_domain = (publisher_domain or "").casefold().removeprefix("www.")
    parser = _ArticleParser(publisher_hints=_publisher_hints(normalized_domain))
    try:
        parser.feed(html)
    except (ValueError, AssertionError):
        return "", "html_parse_failed"
    publisher_content = clean_feed_text("\n".join(parser.publisher_chunks))
    content = clean_feed_text("\n".join(parser.content_chunks))
    paragraphs = clean_feed_text("\n".join(parser.paragraph_chunks))
    if len(publisher_content) >= 600:
        return publisher_content, f"publisher_container:{normalized_domain}"
    if len(content) >= 600:
        return content, "semantic_article_container"
    return paragraphs, "paragraph_fallback"


def _publisher_hints(domain: str) -> tuple[str, ...]:
    for suffix, hints in PUBLISHER_CONTENT_HINTS.items():
        if domain == suffix or domain.endswith(f".{suffix}"):
            return hints
    return ()


def _is_trusted_publisher_domain(domain: str) -> bool:
    return bool(_publisher_hints(domain))


def _structured_article_body(html: str) -> str:
    parser = _JsonLdParser()
    try:
        parser.feed(html)
    except (ValueError, AssertionError):
        return ""
    candidates: list[str] = []
    for payload in parser.payloads:
        try:
            value = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            continue
        candidates.extend(_article_body_values(value))
    return max((clean_feed_text(value) for value in candidates), key=len, default="")


def _article_body_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        bodies = [
            child
            for key, child in value.items()
            if key.casefold() == "articlebody" and isinstance(child, str)
        ]
        for child in value.values():
            bodies.extend(_article_body_values(child))
        return bodies
    if isinstance(value, list):
        nested_bodies: list[str] = []
        for child in value:
            nested_bodies.extend(_article_body_values(child))
        return nested_bodies
    return []


async def expand_full_text_batch(
    session: Session,
    *,
    client: httpx.AsyncClient,
    archive: ColdArchive,
    batch_size: int = 20,
    min_full_text_chars: int = 1_200,
    verified_short_min_chars: int = 600,
    hot_body_chars: int = 2_000,
    user_agent: str = "NEWS-Map/0.18 personal research full-text archiver",
    max_response_bytes: int = 4_000_000,
    retry_after_days: int = 7,
    max_concurrency: int = 8,
    domain_delay_seconds: float = 0.75,
    publisher_domains: tuple[str, ...] | None = None,
    document_ids: tuple[int, ...] | None = None,
    force: bool = False,
) -> FullTextExpansionResult:
    """Expand short documents from ordinary publisher pages and archive them on F."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if min_full_text_chars < 600:
        raise ValueError("min_full_text_chars must be at least 600")
    if not 600 <= verified_short_min_chars <= min_full_text_chars:
        raise ValueError("verified_short_min_chars must be between 600 and min_full_text_chars")
    if max_concurrency < 1:
        raise ValueError("max_concurrency must be positive")
    if domain_delay_seconds < 0:
        raise ValueError("domain_delay_seconds cannot be negative")
    now = datetime.now(UTC)
    status_field = Document.raw_metadata["full_text_status"].as_string()
    statement = (
        select(Document)
        .join(Source, Source.id == Document.source_id)
        .where(Source.source_type.in_((SourceType.RSS, SourceType.NEWS)))
        .where(or_(Document.body.is_(None), func.length(Document.body) < min_full_text_chars))
        .where(or_(status_field.is_(None), status_field != "complete"))
    )
    normalized_domains = tuple(
        sorted({value.casefold().strip().removeprefix("www.") for value in publisher_domains or ()})
    )
    normalized_document_ids = tuple(
        dict.fromkeys(value for value in document_ids or () if value > 0)
    )
    if normalized_document_ids:
        statement = statement.where(Document.id.in_(normalized_document_ids))
    if normalized_domains:
        statement = statement.where(
            or_(*(Document.url.ilike(f"%{domain}%") for domain in normalized_domains))
        )
    if not force:
        attempted_field = Document.raw_metadata["full_text_attempted_at"].as_string()
        retry_class_field = Document.raw_metadata["full_text_retry_class"].as_string()
        retry_at_field = Document.raw_metadata["full_text_retry_after"].as_string()
        retry_before = (now - timedelta(days=retry_after_days)).isoformat()
        statement = statement.where(
            or_(
                status_field.is_(None),
                and_(
                    status_field != "complete",
                    or_(
                        retry_class_field.is_(None),
                        retry_class_field != "permanent",
                    ),
                    or_(
                        and_(retry_at_field.is_not(None), retry_at_field <= now.isoformat()),
                        and_(
                            retry_at_field.is_(None),
                            or_(
                                attempted_field.is_(None),
                                attempted_field < retry_before,
                            ),
                        ),
                    ),
                ),
            )
        )
    candidate_limit = min(max(batch_size * 10, batch_size), 5_000)
    linked_to_event = exists(
        select(EventDocument.document_id).where(
            EventDocument.document_id == Document.id
        )
    )
    collector_field = Document.raw_metadata["collector"].as_string()
    priority = case(
        (linked_to_event, 0),
        (collector_field == "rss", 1),
        else_=2,
    )
    recent_rows = list(
        session.scalars(
            statement.order_by(
                priority.asc(),
                Document.published_at.desc(),
                Document.id.desc(),
            ).limit(candidate_limit)
        )
    )
    oldest_rows = list(
        session.scalars(
            statement.order_by(Document.published_at.asc(), Document.id.asc()).limit(
                candidate_limit
            )
        )
    )
    recent_eligible = [
        document
        for document in recent_rows
        if force or _eligible_for_retry(document, now=now, retry_after_days=retry_after_days)
    ]
    recent_quota = max(1, round(batch_size * 0.7))
    selected = _domain_balanced(recent_eligible, limit=recent_quota)
    selected_ids = {document.id for document in selected}
    oldest_eligible = [
        document
        for document in oldest_rows
        if document.id not in selected_ids
        and (force or _eligible_for_retry(document, now=now, retry_after_days=retry_after_days))
    ]
    selected.extend(
        _domain_balanced(oldest_eligible, limit=max(batch_size - len(selected), 0))
    )
    selected_ids = {document.id for document in selected}
    if len(selected) < batch_size:
        overflow = [
            document for document in recent_eligible if document.id not in selected_ids
        ]
        selected.extend(_domain_balanced(overflow, limit=batch_size - len(selected)))
    expanded = insufficient = blocked = failed = duplicate = 0
    retryable = permanent = archived_characters = 0
    robots_cache: dict[str, RobotFileParser | None] = {}
    headers = {"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"}
    throttle = _DomainThrottle(
        max_concurrency=max_concurrency,
        domain_delay_seconds=domain_delay_seconds,
    )

    fetches = await asyncio.gather(
        *(
            _fetch_candidate(
                client,
                document.url,
                user_agent=user_agent,
                headers=headers,
                robots_cache=robots_cache,
                max_response_bytes=max_response_bytes,
                throttle=throttle,
            )
            for document in selected
        )
    )

    accepted_content_hashes: set[str] = set()
    for document, fetch in zip(selected, fetches, strict=True):
        fetch_status, full_body, extraction_method, http_status, retry_after_seconds = fetch
        if fetch_status != "complete":
            retry_class = _record_attempt(
                document,
                fetch_status,
                now=now,
                base_retry_days=retry_after_days,
                retry_after_seconds=retry_after_seconds,
                extra={
                    "extracted_chars": len(full_body),
                    "extraction_method": extraction_method,
                    "publisher_http_status": http_status,
                },
            )
            if retry_class == "permanent":
                permanent += 1
            else:
                retryable += 1
            if fetch_status in {
                "robots_disallowed",
                "http_401",
                "http_403",
                "http_407",
                "http_429",
                "http_451",
            }:
                blocked += 1
            elif fetch_status in {"unsupported_response", "non_article_source"}:
                insufficient += 1
            else:
                failed += 1
            continue

        current_body = document.body or ""
        document_domain = _publisher_domain(document.url)
        trusted_extraction = (
            extraction_method == "json_ld_article_body"
            or extraction_method.startswith("publisher_container:")
            or (
                extraction_method == "semantic_article_container"
                and _is_trusted_publisher_domain(document_domain)
            )
        )
        required_chars = verified_short_min_chars if trusted_extraction else min_full_text_chars
        if len(full_body) < required_chars or len(full_body) <= len(current_body) * 1.2:
            retry_class = _record_attempt(
                document,
                "insufficient_extraction",
                now=now,
                base_retry_days=retry_after_days,
                extra={"extracted_chars": len(full_body), "extraction_method": extraction_method},
            )
            retryable += int(retry_class != "permanent")
            permanent += int(retry_class == "permanent")
            insufficient += 1
            continue
        content_hash = document_hash(document.title, full_body)
        conflict_id = None
        if content_hash not in accepted_content_hashes:
            conflict_id = session.scalar(
                select(Document.id).where(
                    Document.content_hash == content_hash,
                    Document.id != document.id,
                )
            )
        if content_hash in accepted_content_hashes or conflict_id is not None:
            retry_class = _record_attempt(
                document,
                "duplicate_full_text",
                now=now,
                base_retry_days=retry_after_days,
                extra={
                    "duplicate_document_id": (
                        conflict_id if conflict_id is not None else "same_batch"
                    )
                },
            )
            retryable += int(retry_class != "permanent")
            permanent += int(retry_class == "permanent")
            duplicate += 1
            continue
        accepted_content_hashes.add(content_hash)
        metadata: dict[str, Any] = dict(document.raw_metadata or {})
        try:
            archive_path = archive.store_entry(
                content_hash=content_hash,
                source_id=document.source_id,
                url=document.url,
                title=document.title,
                body=full_body,
                published_at=document.published_at,
                metadata={
                    **metadata,
                    "full_text_document_id": document.id,
                    "full_text_extraction_method": extraction_method,
                },
            )
        except (ArchiveCapacityError, OSError, ValueError):
            retry_class = _record_attempt(
                document,
                "archive_write_failed",
                now=now,
                base_retry_days=retry_after_days,
            )
            retryable += int(retry_class != "permanent")
            permanent += int(retry_class == "permanent")
            failed += 1
            continue
        attempt_count = _attempt_count(metadata) + 1
        document.content_hash = content_hash
        document.raw_object_path = archive_path
        document.body = full_body[:hot_body_chars]
        document.raw_metadata = {
            **metadata,
            "storage_policy": STORAGE_POLICY,
            "storage_tier": (
                "cold_full_hot_excerpt" if len(full_body) > hot_body_chars else "cold_full_hot_full"
            ),
            "full_body_chars": len(full_body),
            "hot_body_chars": min(len(full_body), hot_body_chars),
            "body_hot_truncated": len(full_body) > hot_body_chars,
            "cold_archive_verified_at": now.isoformat(),
            "full_text_status": "complete",
            "full_text_retry_class": "complete",
            "full_text_retry_after": None,
            "full_text_attempt_count": attempt_count,
            "full_text_retrieved_at": now.isoformat(),
            "full_text_extraction_method": extraction_method,
            "full_text_quality": (
                "verified_short" if len(full_body) < min_full_text_chars else "full"
            ),
            "publisher_http_status": http_status,
            "feed_body_chars_before_expansion": len(current_body),
        }
        expanded += 1
        archived_characters += len(full_body)

    session.flush()
    return FullTextExpansionResult(
        scanned=len(selected),
        expanded=expanded,
        insufficient=insufficient,
        blocked=blocked,
        failed=failed,
        duplicate=duplicate,
        retryable=retryable,
        permanent=permanent,
        archived_characters=archived_characters,
    )


async def _fetch_candidate(
    client: httpx.AsyncClient,
    url: str,
    *,
    user_agent: str,
    headers: dict[str, str],
    robots_cache: dict[str, RobotFileParser | None],
    max_response_bytes: int,
    throttle: _DomainThrottle,
) -> tuple[str, str, str, int | None, float | None]:
    publisher_domain = _publisher_domain(url)
    if publisher_domain in NON_ARTICLE_DOMAINS:
        return "non_article_source", "", "none", None, None
    if not await _robots_allowed(
        client,
        url,
        user_agent=user_agent,
        cache=robots_cache,
        throttle=throttle,
    ):
        return "robots_disallowed", "", "none", None, None
    try:
        response = await throttle.get(client, url, headers=headers)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return (
            f"http_{exc.response.status_code}",
            "",
            "none",
            exc.response.status_code,
            _parse_retry_after(exc.response, now=datetime.now(UTC)),
        )
    except httpx.HTTPError:
        return "network_error", "", "none", None, None
    content_type = response.headers.get("content-type", "").casefold()
    if "html" not in content_type or len(response.content) > max_response_bytes:
        return "unsupported_response", "", "none", response.status_code, None
    full_body, extraction_method = extract_article_text(
        response.text,
        publisher_domain=publisher_domain,
    )
    return "complete", full_body, extraction_method, response.status_code, None


def _eligible_for_retry(document: Document, *, now: datetime, retry_after_days: int) -> bool:
    metadata: dict[str, Any] = document.raw_metadata or {}
    if metadata.get("full_text_status") == "complete":
        return False
    if metadata.get("full_text_retry_class") == "permanent":
        return False
    retry_after = metadata.get("full_text_retry_after")
    if isinstance(retry_after, str):
        try:
            retry_at = datetime.fromisoformat(retry_after.replace("Z", "+00:00"))
        except ValueError:
            retry_at = None
        if retry_at is not None:
            return retry_at <= now
    attempted = metadata.get("full_text_attempted_at")
    if not isinstance(attempted, str):
        return True
    try:
        attempted_at = datetime.fromisoformat(attempted.replace("Z", "+00:00"))
    except ValueError:
        return True
    return attempted_at <= now - timedelta(days=retry_after_days)


def _record_attempt(
    document: Document,
    status: str,
    *,
    now: datetime,
    base_retry_days: int,
    retry_after_seconds: float | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    metadata = dict(document.raw_metadata or {})
    attempt_count = _attempt_count(metadata) + 1
    retry_class, retry_at = _retry_decision(
        status,
        attempt_count=attempt_count,
        now=now,
        base_retry_days=base_retry_days,
        retry_after_seconds=retry_after_seconds,
    )
    document.raw_metadata = {
        **metadata,
        "full_text_status": status,
        "full_text_attempted_at": now.isoformat(),
        "full_text_attempt_count": attempt_count,
        "full_text_retry_class": retry_class,
        "full_text_retry_after": retry_at.isoformat() if retry_at else None,
        "full_text_publisher_domain": _publisher_domain(document.url),
        **(extra or {}),
    }
    return retry_class


async def _robots_allowed(
    client: httpx.AsyncClient,
    url: str,
    *,
    user_agent: str,
    cache: dict[str, RobotFileParser | None],
    throttle: _DomainThrottle,
) -> bool:
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    if origin in cache:
        parser = cache[origin]
        return True if parser is None else parser.can_fetch(user_agent, url)
    robots_url = f"{origin}/robots.txt"
    try:
        response = await throttle.get(
            client,
            robots_url,
            headers={"User-Agent": user_agent},
        )
        if response.status_code >= 400:
            cache[origin] = None
            return True
        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(response.text.splitlines())
        cache[origin] = parser
        return parser.can_fetch(user_agent, url)
    except httpx.HTTPError:
        cache[origin] = None
        return True


def _publisher_domain(url: str) -> str:
    hostname = (urlsplit(url).hostname or "unknown").casefold()
    return hostname.removeprefix("www.")


def _domain_balanced(documents: list[Document], *, limit: int) -> list[Document]:
    """Round-robin candidates so one prolific publisher cannot consume a batch."""
    queues: dict[str, deque[Document]] = {}
    for document in documents:
        queues.setdefault(_publisher_domain(document.url), deque()).append(document)
    selected: list[Document] = []
    active = deque(queues.values())
    while active and len(selected) < limit:
        queue = active.popleft()
        selected.append(queue.popleft())
        if queue:
            active.append(queue)
    return selected


def _attempt_count(metadata: dict[str, Any]) -> int:
    try:
        return max(0, int(metadata.get("full_text_attempt_count") or 0))
    except (TypeError, ValueError):
        return 0


def _retry_decision(
    status: str,
    *,
    attempt_count: int,
    now: datetime,
    base_retry_days: int,
    retry_after_seconds: float | None,
) -> tuple[str, datetime | None]:
    if status in PERMANENT_FULLTEXT_STATUSES or status == "duplicate_full_text":
        return "permanent", None
    if status == "insufficient_extraction":
        return "content_retry", now + timedelta(days=max(30, base_retry_days))
    if status == "http_429":
        backoff = max(
            retry_after_seconds or 0,
            timedelta(
                days=min(30, base_retry_days * (2 ** min(attempt_count - 1, 4)))
            ).total_seconds(),
        )
        return "rate_limited", now + timedelta(seconds=backoff)
    backoff_days = min(30, base_retry_days * (2 ** min(attempt_count - 1, 4)))
    return "transient", now + timedelta(days=backoff_days)


def _parse_retry_after(response: httpx.Response, *, now: datetime) -> float | None:
    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=UTC)
    return max(0.0, (retry_at - now).total_seconds())
