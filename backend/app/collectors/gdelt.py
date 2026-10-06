"""Thirty-day global news discovery using GDELT article metadata."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.collectors.rss import clean_feed_text, document_hash
from app.core.text import repair_common_mojibake
from app.db.enums import SourceType
from app.db.models import Document, Source
from app.storage.archive import ColdArchive

GDELT_DOC_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_DOC_SOURCE_BOUNDARY = date(2017, 1, 1)
GDELT_DOC_BACKFILL_STATE_KEY = "gdelt_doc_discovery_backfill"
RECENT_NEWS_TOPICS = {
    "conflict_politics": (
        '"armed conflict" OR "military strike" OR "peace talks" '
        "OR election OR sanctions"
    ),
    "disaster_weather": (
        'earthquake OR hurricane OR wildfire OR "flash flood"'
    ),
    "agriculture_food": (
        'agriculture OR crop OR "food production" OR drought OR livestock'
    ),
    "economy_markets": (
        'economy OR inflation OR "interest rate" OR "stock market" OR trade'
    ),
    "industry_energy_technology": (
        'industry OR manufacturing OR energy OR mining OR technology'
    ),
    "society_health_crime": (
        'health OR disease OR education OR crime OR migration'
    ),
    "transport_logistics": (
        'aviation OR airport OR shipping OR port OR logistics'
    ),
    "climate_environment": (
        'climate OR environment OR water OR pollution'
    ),
    "monetary_policy_liquidity": (
        '"central bank" OR "interest rate decision" OR "bond yield" '
        'OR liquidity OR "money supply"'
    ),
    "equities_earnings_valuation": (
        '"corporate earnings" OR "profit warning" OR valuation '
        'OR "equity market" OR "share buyback"'
    ),
    "debt_credit_currency": (
        '"sovereign debt" OR "credit spread" OR default OR '
        '"foreign exchange" OR currency'
    ),
    "commodities_supply_chain": (
        '"commodity price" OR oil OR gas OR copper OR wheat '
        'OR "supply chain disruption"'
    ),
}
HISTORICAL_NEWS_TOPICS = {
    "geopolitics_conflict": (
        '"armed conflict" OR "military strike" OR election OR sanctions '
        'OR diplomacy OR government'
    ),
    "disaster_climate_agriculture": (
        'earthquake OR hurricane OR wildfire OR flood OR drought OR crop '
        'OR agriculture OR climate'
    ),
    "economy_policy_debt": (
        'inflation OR "central bank" OR "interest rate" OR economy '
        'OR debt OR credit OR currency OR trade'
    ),
    "markets_earnings_commodities": (
        '"stock market" OR "corporate earnings" OR valuation OR oil OR gas '
        'OR copper OR wheat OR "commodity price"'
    ),
    "industry_energy_technology_logistics": (
        'manufacturing OR industry OR energy OR mining OR technology '
        'OR shipping OR aviation OR port OR logistics'
    ),
    "society_health_crime": (
        'health OR disease OR education OR crime OR migration OR employment'
    ),
}
LANGUAGE_CODES = {
    "Arabic": "ar",
    "Chinese": "zh",
    "English": "en",
    "French": "fr",
    "German": "de",
    "Japanese": "ja",
    "Korean": "ko",
    "Portuguese": "pt",
    "Russian": "ru",
    "Spanish": "es",
}


class GDELTTopicResult(BaseModel):
    """One topic request with isolated success/failure accounting."""

    model_config = ConfigDict(extra="forbid")

    topic: str
    articles_seen: int = Field(default=0, ge=0)
    documents_created: int = Field(default=0, ge=0)
    duplicates_skipped: int = Field(default=0, ge=0)
    invalid_articles: int = Field(default=0, ge=0)
    error: str | None = None


class GDELTCollectionResult(BaseModel):
    """Summary for one thirty-day discovery pass."""

    model_config = ConfigDict(extra="forbid")

    timespan: str = "1month"
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    metadata_only: bool = True
    topics: list[GDELTTopicResult]

    @property
    def documents_created(self) -> int:
        return sum(topic.documents_created for topic in self.topics)


class GDELTRecentNewsCollector:
    """Import attributed article metadata without copying publisher full text."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        archive: ColdArchive | None = None,
        records_per_topic: int = 125,
        request_interval_seconds: float = 20.5,
        max_attempts: int = 3,
        progress_callback: Callable[[GDELTTopicResult], None] | None = None,
    ) -> None:
        if not 10 <= records_per_topic <= 250:
            raise ValueError("records_per_topic must be between 10 and 250")
        if request_interval_seconds < 0:
            raise ValueError("request_interval_seconds must be non-negative")
        if not 1 <= max_attempts <= 5:
            raise ValueError("max_attempts must be between one and five")
        self.client = client
        self.archive = archive
        self.records_per_topic = records_per_topic
        self.request_interval_seconds = request_interval_seconds
        self.max_attempts = max_attempts
        self.progress_callback = progress_callback

    async def collect_month(self, session: Session) -> GDELTCollectionResult:
        """Query broad news domains, isolating failures by topic."""
        return await self.collect_range(session)

    async def collect_range(
        self,
        session: Session,
        *,
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
    ) -> GDELTCollectionResult:
        """Query one explicit time segment so historical depth is measurable."""
        if (starts_at is None) != (ends_at is None):
            raise ValueError("starts_at and ends_at must be supplied together")
        if starts_at is not None and ends_at is not None and starts_at > ends_at:
            raise ValueError("starts_at must not be after ends_at")
        topics = (
            HISTORICAL_NEWS_TOPICS
            if starts_at is not None
            else RECENT_NEWS_TOPICS
        )
        results: list[GDELTTopicResult] = []
        for index, (topic, query) in enumerate(topics.items()):
            if index and self.request_interval_seconds:
                await asyncio.sleep(self.request_interval_seconds)
            try:
                payload = await self._request_topic(
                    query,
                    starts_at=starts_at,
                    ends_at=ends_at,
                )
                articles = payload.get("articles", [])
                if not isinstance(articles, list):
                    raise ValueError("GDELT response has no article list")
                result = self._store_articles(session, topic, articles)
                session.commit()
            except Exception as exc:
                session.rollback()
                result = GDELTTopicResult(
                    topic=topic,
                    error=f"{type(exc).__name__}: {str(exc)[:500]}",
                )
            results.append(result)
            if self.progress_callback is not None:
                self.progress_callback(result)
        return GDELTCollectionResult(
            timespan=(
                f"{starts_at.isoformat()}/{ends_at.isoformat()}"
                if starts_at is not None and ends_at is not None
                else "1month"
            ),
            starts_at=starts_at,
            ends_at=ends_at,
            topics=results,
        )

    async def _request_topic(
        self,
        query: str,
        *,
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                params: dict[str, str | int] = {
                    "query": f"({query})",
                    "mode": "artlist",
                    "maxrecords": self.records_per_topic,
                    "sort": (
                        "hybridrel"
                        if starts_at is not None and ends_at is not None
                        else "datedesc"
                    ),
                    "format": "json",
                }
                if starts_at is None or ends_at is None:
                    params["timespan"] = "1month"
                else:
                    params["startdatetime"] = _gdelt_datetime(starts_at)
                    params["enddatetime"] = _gdelt_datetime(
                        ends_at + timedelta(seconds=1)
                    )
                response = await self.client.get(
                    GDELT_DOC_ENDPOINT,
                    params=params,
                )
                response.raise_for_status()
                payload = _decode_gdelt_json(response.content)
                if not isinstance(payload, dict):
                    raise ValueError("GDELT response must be an object")
                return payload
            except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                if attempt + 1 >= self.max_attempts:
                    break
                await asyncio.sleep(
                    _gdelt_retry_delay_seconds(
                        exc,
                        attempt=attempt,
                        request_interval_seconds=self.request_interval_seconds,
                    )
                )
        raise RuntimeError(
            f"GDELT topic request exhausted retries: {last_error}"
        ) from last_error

    def _store_articles(
        self,
        session: Session,
        topic: str,
        articles: list[Any],
    ) -> GDELTTopicResult:
        candidates: list[tuple[dict[str, Any], str, str, str]] = []
        invalid_articles = 0
        for raw in articles:
            if not isinstance(raw, dict):
                invalid_articles += 1
                continue
            url = _valid_url(raw.get("url"))
            title = repair_common_mojibake(
                clean_feed_text(str(raw.get("title") or ""))
            )
            if url is None or not title:
                invalid_articles += 1
                continue
            candidates.append((raw, url, title, document_hash(title, "")))

        existing_urls: set[str] = set()
        existing_hashes: set[str] = set()
        if candidates:
            rows = session.execute(
                select(Document.url, Document.content_hash).where(
                    or_(
                        Document.url.in_([row[1] for row in candidates]),
                        Document.content_hash.in_([row[3] for row in candidates]),
                    )
                )
            )
            for url, content_hash in rows:
                existing_urls.add(url)
                existing_hashes.add(content_hash)

        source_cache: dict[str, Source] = {}
        documents_created = 0
        duplicates_skipped = 0
        for raw, url, title, content_hash in candidates:
            if url in existing_urls or content_hash in existing_hashes:
                duplicates_skipped += 1
                continue
            domain = str(raw.get("domain") or urlparse(url).hostname or "unknown")
            source = source_cache.get(domain)
            if source is None:
                source_name = f"GDELT discovery · {domain}"[:255]
                source = session.scalar(
                    select(Source).where(
                        Source.name == source_name,
                        Source.country.is_(None),
                    )
                )
                if source is None:
                    source = Source(
                        name=source_name,
                        country=None,
                        language=_language_code(raw.get("language")),
                        source_type=SourceType.NEWS,
                        ownership=domain[:255],
                        credibility_baseline=Decimal("0.500"),
                        political_bias_metadata={
                            "kind": "publisher_discovered_via_gdelt",
                            "discovery_provider": "GDELT DOC 2.0",
                            "credibility_unassessed": True,
                        },
                    )
                    session.add(source)
                    session.flush()
                source_cache[domain] = source
            published_at = _seen_datetime(raw.get("seendate"))
            metadata = {
                "collector": "gdelt_doc_discovery",
                "discovery_topic": topic,
                "metadata_only": True,
                "full_text_copied": False,
                "gdelt_seen_date": raw.get("seendate"),
                "gdelt_domain": domain,
                "gdelt_language": raw.get("language"),
                "gdelt_source_country": raw.get("sourcecountry"),
                "social_image": raw.get("socialimage"),
                "mobile_url": raw.get("url_mobile"),
                "attribution": "Publisher title and URL discovered via GDELT",
            }
            raw_object_path = None
            if self.archive is not None:
                raw_object_path = self.archive.store_entry(
                    content_hash=content_hash,
                    source_id=source.id,
                    url=url,
                    title=title,
                    body="",
                    published_at=published_at,
                    metadata=metadata,
                )
            session.add(
                Document(
                    source_id=source.id,
                    url=url,
                    title=title,
                    body=None,
                    language=_language_code(raw.get("language")),
                    published_at=published_at,
                    content_hash=content_hash,
                    credibility_score=source.credibility_baseline,
                    raw_object_path=raw_object_path,
                    raw_metadata=metadata,
                )
            )
            existing_urls.add(url)
            existing_hashes.add(content_hash)
            documents_created += 1
        session.flush()
        return GDELTTopicResult(
            topic=topic,
            articles_seen=len(articles),
            documents_created=documents_created,
            duplicates_skipped=duplicates_skipped,
            invalid_articles=invalid_articles,
        )


def _valid_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    return value


def _seen_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    for pattern in ("%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(value, pattern).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _language_code(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return LANGUAGE_CODES.get(value, value.casefold()[:16])


def _decode_gdelt_json(value: str | bytes) -> Any:
    """Repair only invalid JSON backslash escapes seen in article metadata."""
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        repaired = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", value)
        return json.loads(repaired)


def _gdelt_datetime(value: datetime) -> str:
    """Format an explicit UTC DOC API boundary."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y%m%d%H%M%S")


def _gdelt_retry_delay_seconds(
    error: Exception,
    *,
    attempt: int,
    request_interval_seconds: float,
) -> float:
    """Use a longer exponential cooldown when the public DOC API returns 429."""
    if not isinstance(error, httpx.HTTPStatusError):
        return request_interval_seconds
    if error.response.status_code != 429:
        return request_interval_seconds
    retry_after = 0.0
    try:
        retry_after = float(error.response.headers.get("Retry-After", "0"))
    except ValueError:
        retry_after = 0.0
    return float(
        max(request_interval_seconds, retry_after, 75.0 * (2**attempt))
    )
