"""Thirty-day GDELT metadata discovery tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import httpx
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.collectors.gdelt import (
    RECENT_NEWS_TOPICS,
    GDELTRecentNewsCollector,
    _decode_gdelt_json,
    _gdelt_retry_delay_seconds,
)
from app.collectors.gdelt_cli import _earliest_gdelt_publication
from app.db.base import Base
from app.db.enums import SourceType
from app.db.models import Document, Source


def test_gdelt_discovery_stores_titles_with_provenance_and_deduplicates() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["timespan"] == "1month"
        assert request.url.params["mode"] == "artlist"
        return httpx.Response(
            200,
            json={
                "articles": [
                    {
                        "url": "https://publisher-a.test/economy",
                        "title": "Inflation slows in Exampleland",
                        "seendate": "20260729T120000Z",
                        "domain": "publisher-a.test",
                        "language": "English",
                        "sourcecountry": "Canada",
                    },
                    {
                        "url": "https://publisher-b.test/industry",
                        "title": "Factory output rises",
                        "seendate": "20260728T090000Z",
                        "domain": "publisher-b.test",
                        "language": "English",
                        "sourcecountry": "Japan",
                    },
                ]
            },
        )

    async def collect(session: Session) -> int:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as client:
            result = await GDELTRecentNewsCollector(
                client,
                records_per_topic=25,
                request_interval_seconds=0,
                max_attempts=1,
            ).collect_month(session)
        return result.documents_created

    with Session(engine) as session:
        created = asyncio.run(collect(session))
        documents = list(session.scalars(select(Document).order_by(Document.id)))
        source_count = session.scalar(select(func.count()).select_from(Source))

    assert created == 2
    assert len(RECENT_NEWS_TOPICS) == 12
    assert len(documents) == 2
    assert source_count == 2
    assert documents[0].body is None
    assert documents[0].raw_metadata["metadata_only"] is True
    assert documents[0].raw_metadata["full_text_copied"] is False
    assert documents[0].published_at is not None
    engine.dispose()


def test_gdelt_topic_failure_does_not_stop_the_monthly_pass() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, text="rate limited")
        return httpx.Response(200, json={"articles": []})

    async def collect(session: Session) -> tuple[int, bool]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as client:
            result = await GDELTRecentNewsCollector(
                client,
                records_per_topic=25,
                request_interval_seconds=0,
                max_attempts=1,
            ).collect_month(session)
        return len(result.topics), result.topics[0].error is not None

    with Session(engine) as session:
        topic_count, first_failed = asyncio.run(collect(session))

    assert topic_count == len(RECENT_NEWS_TOPICS)
    assert first_failed is True
    assert calls == len(RECENT_NEWS_TOPICS)
    engine.dispose()


def test_gdelt_invalid_backslash_escape_is_repaired() -> None:
    payload = _decode_gdelt_json(
        '{"articles":[{"title":"Publisher writes \\q in a title"}]}'
    )
    assert payload["articles"][0]["title"] == "Publisher writes \\q in a title"


def test_gdelt_utf8_bytes_preserve_multilingual_titles() -> None:
    payload = _decode_gdelt_json(
        '{"articles":[{"title":"中国经济与الاقتصاد الروسي"}]}'.encode()
    )
    assert payload["articles"][0]["title"] == "中国经济与الاقتصاد الروسي"


def test_gdelt_backfill_checkpoint_uses_only_discovery_documents() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source = Source(
            name="Checkpoint source",
            language="en",
            source_type=SourceType.NEWS,
            credibility_baseline=Decimal("0.5"),
        )
        session.add_all(
            [
                Document(
                    source=source,
                    url="https://example.test/rss",
                    title="Old RSS item",
                    published_at=datetime(2020, 1, 1, tzinfo=UTC),
                    content_hash="a" * 64,
                    raw_metadata={"collector": "rss"},
                ),
                Document(
                    source=source,
                    url="https://example.test/gdelt",
                    title="GDELT item",
                    published_at=datetime(2026, 5, 1, tzinfo=UTC),
                    content_hash="b" * 64,
                    raw_metadata={"collector": "gdelt_doc_discovery"},
                ),
            ]
        )
        session.flush()

        checkpoint = _earliest_gdelt_publication(session)

    assert checkpoint == datetime(2026, 5, 1, tzinfo=UTC)
    engine.dispose()


def test_gdelt_429_retry_uses_exponential_cooldown() -> None:
    request = httpx.Request("GET", "https://api.gdeltproject.org/test")
    response = httpx.Response(
        429,
        headers={"Retry-After": "90"},
        request=request,
    )
    error = httpx.HTTPStatusError(
        "rate limited",
        request=request,
        response=response,
    )

    assert _gdelt_retry_delay_seconds(
        error,
        attempt=0,
        request_interval_seconds=20.5,
    ) == 90
    assert _gdelt_retry_delay_seconds(
        error,
        attempt=1,
        request_interval_seconds=20.5,
    ) == 150
