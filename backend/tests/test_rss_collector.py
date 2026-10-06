"""RSS fetch, deduplication, scheduling and failure-isolation tests."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.collectors.rss import RSSCollector, clean_feed_text, document_hash
from app.db.base import Base
from app.db.enums import SourceType
from app.db.models import Document, RSSFeed, Source
from app.storage.archive import ColdArchive

RSS_BODY = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://feeds.test/</link>
    <description>Test feed</description>
    <item>
      <title>Bank raises policy rate</title>
      <link>https://feeds.test/articles/rate-decision</link>
      <guid>rate-decision-1</guid>
      <pubDate>Wed, 29 Jul 2026 12:00:00 GMT</pubDate>
      <description><![CDATA[<p>The rate increased by 25 basis points.</p>]]></description>
    </item>
  </channel>
</rss>
"""


def test_feed_text_repairs_common_utf8_mojibake() -> None:
    assert clean_feed_text("SudÃ¡n") == "Sudán"
    assert clean_feed_text("HaÃ¯ti") == "Haïti"
    assert clean_feed_text("SudÃ¡n â€“ alert") == "Sudán \u2013 alert"
    assert clean_feed_text("plain text") == "plain text"


def add_feed(
    session: Session,
    *,
    name: str = "Test source",
    url: str = "https://feeds.test/rss.xml",
    enabled: bool = True,
) -> RSSFeed:
    source = Source(
        name=name,
        country="JP",
        language="en",
        source_type=SourceType.RSS,
        credibility_baseline=Decimal("0.900"),
    )
    feed = RSSFeed(
        source=source,
        url=url,
        enabled=enabled,
        license_name="Test license",
        license_url="https://feeds.test/terms",
        rate_limit_per_minute=Decimal("1.000"),
        fetch_interval_seconds=900,
        request_timeout_seconds=Decimal("10.00"),
        user_agent="NEWS-App-Test/0.3",
    )
    session.add(feed)
    session.commit()
    return feed


def test_rss_collection_uses_cache_headers_and_deduplicates() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 3:
            return httpx.Response(304)
        return httpx.Response(
            200,
            content=RSS_BODY,
            headers={
                "Content-Type": "application/rss+xml",
                "ETag": '"feed-v1"',
                "Last-Modified": "Wed, 29 Jul 2026 12:00:00 GMT",
            },
        )

    async def collect_three_times(
        session: Session,
        feed: RSSFeed,
    ) -> tuple[int, int, str]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            collector = RSSCollector(client)
            first = await collector.collect_many(session, [feed], force=True)
            second = await collector.collect_many(session, [feed], force=True)
            third = await collector.collect_many(session, [feed], force=True)
        return (
            first.results[0].documents_created,
            second.results[0].duplicates_skipped,
            third.results[0].status,
        )

    with Session(engine) as session:
        feed = add_feed(session)
        created, duplicate, third_status = asyncio.run(
            collect_three_times(session, feed)
        )
        document = session.scalar(select(Document))
        document_count = session.scalar(select(func.count()).select_from(Document))

    assert created == 1
    assert duplicate == 1
    assert third_status == "not_modified"
    assert document_count == 1
    assert document is not None
    assert document.body == "The rate increased by 25 basis points."
    assert document.raw_metadata["license_name"] == "Test license"
    assert requests[1].headers["if-none-match"] == '"feed-v1"'
    assert requests[1].headers["if-modified-since"] == (
        "Wed, 29 Jul 2026 12:00:00 GMT"
    )
    engine.dispose()


def test_one_feed_failure_does_not_block_other_sources() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "bad.test":
            return httpx.Response(503, text="unavailable")
        return httpx.Response(200, content=RSS_BODY)

    async def collect(session: Session, feeds: list[RSSFeed]) -> tuple[str, str]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await RSSCollector(client).collect_many(session, feeds, force=True)
        return result.results[0].status, result.results[1].status

    with Session(engine) as session:
        bad_feed = add_feed(
            session,
            name="Unavailable source",
            url="https://bad.test/rss.xml",
        )
        good_feed = add_feed(
            session,
            name="Available source",
            url="https://good.test/rss.xml",
        )
        bad_status, good_status = asyncio.run(collect(session, [bad_feed, good_feed]))
        session.refresh(bad_feed)
        document_count = session.scalar(select(func.count()).select_from(Document))

    assert bad_status == "error"
    assert good_status == "success"
    assert bad_feed.consecutive_failures == 1
    assert document_count == 1
    engine.dispose()


def test_feed_schedule_skips_recent_attempt_without_http_request() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)

    def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP request should not run before the feed is due")

    async def collect(session: Session, feed: RSSFeed) -> str:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await RSSCollector(client, clock=lambda: now).collect_feed(
                session,
                feed,
            )
        return result.status

    with Session(engine) as session:
        feed = add_feed(session)
        feed.last_fetched_at = now
        session.commit()
        status = asyncio.run(collect(session, feed))

    assert status == "skipped_not_due"
    engine.dispose()


def test_rss_collection_archives_only_the_unique_document(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=RSS_BODY)

    archive = ColdArchive(
        tmp_path,
        min_free_bytes=0,
        max_used_percent=99,
        disk_usage_provider=lambda _: (10_000_000, 0, 10_000_000),
    )

    async def collect_twice(session: Session, feed: RSSFeed) -> tuple[int, int]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            collector = RSSCollector(client, archive=archive)
            first = await collector.collect_many(session, [feed], force=True)
            second = await collector.collect_many(session, [feed], force=True)
        return first.documents_created, second.results[0].duplicates_skipped

    with Session(engine) as session:
        feed = add_feed(session)
        created, duplicates = asyncio.run(collect_twice(session, feed))
        document = session.scalar(select(Document))

    assert created == 1
    assert duplicates == 1
    assert document is not None
    assert document.raw_object_path is not None
    assert (tmp_path / document.raw_object_path).is_file()
    assert len(list((tmp_path / "raw" / "documents").rglob("*.json.gz"))) == 1
    engine.dispose()


def test_rss_enriches_matching_gdelt_headline_instead_of_skipping() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=RSS_BODY)

    async def collect(session: Session, feed: RSSFeed) -> tuple[int, int]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await RSSCollector(client).collect_many(
                session,
                [feed],
                force=True,
            )
        return (
            result.results[0].documents_created,
            result.results[0].documents_enriched,
        )

    with Session(engine) as session:
        feed = add_feed(session)
        discovery_source = Source(
            name="GDELT discovery · feeds.test",
            language="en",
            source_type=SourceType.NEWS,
            credibility_baseline=Decimal("0.500"),
        )
        headline_hash = document_hash("Bank raises policy rate", "")
        session.add(
            Document(
                source=discovery_source,
                url="https://feeds.test/articles/rate-decision",
                title="Bank raises policy rate",
                body=None,
                language="en",
                published_at=datetime(2026, 7, 29, 12, 0, tzinfo=UTC),
                content_hash=headline_hash,
                raw_metadata={
                    "collector": "gdelt_doc_discovery",
                    "metadata_only": True,
                },
            )
        )
        session.commit()

        created, enriched = asyncio.run(collect(session, feed))
        document = session.scalar(select(Document))
        count = session.scalar(select(func.count()).select_from(Document))
        feed_source_id = feed.source_id

    assert created == 0
    assert enriched == 1
    assert count == 1
    assert document is not None
    assert document.body == "The rate increased by 25 basis points."
    assert document.source_id == feed_source_id
    assert document.raw_metadata["collector"] == "gdelt_doc_discovery"
    assert document.raw_metadata["content_collector"] == "rss"
    assert document.raw_metadata["metadata_only"] is False
    engine.dispose()
