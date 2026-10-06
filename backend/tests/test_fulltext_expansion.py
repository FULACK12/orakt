"""Publisher full-text expansion tests."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.collectors.fulltext import expand_full_text_batch, extract_article_text
from app.db.base import Base
from app.db.enums import SourceType
from app.db.models import Document, Source
from app.storage.archive import ColdArchive


def _roomy_usage(_: Path) -> tuple[int, int, int]:
    tebibyte = 1024**4
    return 10 * tebibyte, 1 * tebibyte, 9 * tebibyte


def test_short_feed_body_is_expanded_and_archived(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source = Source(
            name="Publisher",
            country="US",
            language="en",
            source_type=SourceType.NEWS,
            credibility_baseline=Decimal("0.800"),
        )
        document = Document(
            source=source,
            url="https://publisher.test/news/1",
            title="A material economic development",
            body="Short RSS summary.",
            published_at=datetime.now(UTC),
            content_hash="a" * 64,
        )
        session.add(document)
        session.flush()
        paragraph = "This is retained publisher article evidence with economic context. " * 35
        html = (
            f"<html><main><article><h1>{document.title}</h1>"
            f"<p>{paragraph}</p></article></main></html>"
        )

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text="User-agent: *\nAllow: /")
            return httpx.Response(
                200,
                text=html,
                headers={"content-type": "text/html; charset=utf-8"},
            )

        archive = ColdArchive(
            tmp_path,
            min_free_bytes=0,
            max_used_percent=99,
            disk_usage_provider=_roomy_usage,
        )

        async def run() -> None:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                follow_redirects=True,
            ) as client:
                result = await expand_full_text_batch(
                    session,
                    client=client,
                    archive=archive,
                    batch_size=1,
                    min_full_text_chars=600,
                    hot_body_chars=800,
                )
                assert result.expanded == 1
                assert result.archived_characters > 1_200

        asyncio.run(run())
        assert document.raw_object_path is not None
        assert document.raw_metadata["full_text_status"] == "complete"
        assert document.raw_metadata["full_body_chars"] > len(document.body or "")
        payload = archive.load_entry(
            document.raw_object_path,
            expected_content_hash=document.content_hash,
        )
        assert len(payload["body"]) > 1_200
    engine.dispose()


def test_permanent_publisher_failure_is_not_selected_again(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        document = Document(
            source=Source(
                name="Restricted Publisher",
                country="US",
                language="en",
                source_type=SourceType.NEWS,
                credibility_baseline=Decimal("0.800"),
            ),
            url="https://restricted.test/news/1",
            title="Restricted article",
            body="Short summary.",
            published_at=datetime.now(UTC),
            content_hash="b" * 64,
        )
        session.add(document)
        session.flush()

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text="User-agent: *\nAllow: /")
            return httpx.Response(403, text="forbidden")

        archive = ColdArchive(
            tmp_path,
            min_free_bytes=0,
            max_used_percent=99,
            disk_usage_provider=_roomy_usage,
        )

        async def run() -> None:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                first = await expand_full_text_batch(
                    session,
                    client=client,
                    archive=archive,
                    batch_size=1,
                    min_full_text_chars=600,
                    domain_delay_seconds=0,
                )
                second = await expand_full_text_batch(
                    session,
                    client=client,
                    archive=archive,
                    batch_size=1,
                    min_full_text_chars=600,
                    domain_delay_seconds=0,
                )
                assert first.blocked == 1
                assert first.permanent == 1
                assert second.scanned == 0

        asyncio.run(run())
        assert document.raw_metadata["full_text_status"] == "http_403"
        assert document.raw_metadata["full_text_retry_class"] == "permanent"
        assert document.raw_metadata["full_text_retry_after"] is None
        assert document.raw_metadata["full_text_attempt_count"] == 1
    engine.dispose()


def test_network_failure_records_exponential_retry_window(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        document = Document(
            source=Source(
                name="Unavailable Publisher",
                country="CA",
                language="en",
                source_type=SourceType.RSS,
                credibility_baseline=Decimal("0.800"),
            ),
            url="https://offline.test/news/1",
            title="Temporarily unavailable article",
            body="Short summary.",
            published_at=datetime.now(UTC),
            content_hash="c" * 64,
        )
        session.add(document)
        session.flush()

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text="User-agent: *\nAllow: /")
            raise httpx.ConnectError("offline", request=request)

        archive = ColdArchive(
            tmp_path,
            min_free_bytes=0,
            max_used_percent=99,
            disk_usage_provider=_roomy_usage,
        )
        before = datetime.now(UTC)

        async def run() -> None:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                result = await expand_full_text_batch(
                    session,
                    client=client,
                    archive=archive,
                    batch_size=1,
                    min_full_text_chars=600,
                    retry_after_days=2,
                    domain_delay_seconds=0,
                )
                assert result.failed == 1
                assert result.retryable == 1
                assert result.permanent == 0

        asyncio.run(run())
        retry_at = datetime.fromisoformat(document.raw_metadata["full_text_retry_after"])
        assert retry_at >= before + timedelta(days=2)
        assert document.raw_metadata["full_text_retry_class"] == "transient"
    engine.dispose()


def test_batch_selection_is_balanced_across_publisher_domains(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source = Source(
            name="Discovery",
            country=None,
            language="en",
            source_type=SourceType.NEWS,
            credibility_baseline=Decimal("0.500"),
        )
        now = datetime.now(UTC)
        first_a = Document(
            source=source,
            url="https://a.test/news/1",
            title="First A article",
            body="Short.",
            published_at=now - timedelta(days=3),
            content_hash="d" * 64,
        )
        second_a = Document(
            source=source,
            url="https://a.test/news/2",
            title="Second A article",
            body="Short.",
            published_at=now - timedelta(days=2),
            content_hash="e" * 64,
        )
        first_b = Document(
            source=source,
            url="https://b.test/news/1",
            title="First B article",
            body="Short.",
            published_at=now - timedelta(days=1),
            content_hash="f" * 64,
        )
        session.add_all([first_a, second_a, first_b])
        session.flush()

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text="User-agent: *\nAllow: /")
            publisher = request.url.host or "unknown"
            paragraph = f"Evidence retained from {publisher}. " * 80
            return httpx.Response(
                200,
                text=f"<html><article><p>{paragraph}</p></article></html>",
                headers={"content-type": "text/html"},
            )

        archive = ColdArchive(
            tmp_path,
            min_free_bytes=0,
            max_used_percent=99,
            disk_usage_provider=_roomy_usage,
        )

        async def run() -> None:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                result = await expand_full_text_batch(
                    session,
                    client=client,
                    archive=archive,
                    batch_size=2,
                    min_full_text_chars=600,
                    domain_delay_seconds=0,
                )
                assert result.expanded == 2

        asyncio.run(run())
        assert first_a.raw_metadata["full_text_status"] == "complete"
        assert first_b.raw_metadata["full_text_status"] == "complete"
        assert not (second_a.raw_metadata or {}).get("full_text_status")
    engine.dispose()


def test_bounded_repair_selects_only_requested_document_ids(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source = Source(
            name="Targeted repair publisher",
            country="US",
            language="en",
            source_type=SourceType.NEWS,
            credibility_baseline=Decimal("0.800"),
        )
        requested = Document(
            source=source,
            url="https://targeted.test/news/requested",
            title="Requested repair article",
            body="Short.",
            published_at=datetime.now(UTC),
            content_hash="7" * 64,
        )
        unrequested = Document(
            source=source,
            url="https://targeted.test/news/unrequested",
            title="Unrequested repair article",
            body="Short.",
            published_at=datetime.now(UTC) + timedelta(minutes=1),
            content_hash="8" * 64,
        )
        complete = Document(
            source=source,
            url="https://targeted.test/news/complete",
            title="Already complete article",
            body="Already retained full text. " * 40,
            published_at=datetime.now(UTC) + timedelta(minutes=2),
            content_hash="9" * 64,
            raw_metadata={"full_text_status": "complete"},
        )
        session.add_all([requested, unrequested, complete])
        session.flush()

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text="User-agent: *\nAllow: /")
            article = "Targeted publisher evidence retained for audit. " * 40
            return httpx.Response(
                200,
                text=f"<article><p>{article}</p></article>",
                headers={"content-type": "text/html"},
            )

        archive = ColdArchive(
            tmp_path,
            min_free_bytes=0,
            max_used_percent=99,
            disk_usage_provider=_roomy_usage,
        )

        async def run() -> None:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                result = await expand_full_text_batch(
                    session,
                    client=client,
                    archive=archive,
                    batch_size=3,
                    min_full_text_chars=600,
                    domain_delay_seconds=0,
                    document_ids=(requested.id, complete.id),
                    force=True,
                )
                assert result.scanned == 1
                assert result.expanded == 1

        asyncio.run(run())
        assert requested.raw_metadata["full_text_status"] == "complete"
        assert not (unrequested.raw_metadata or {}).get("full_text_status")
        assert complete.raw_metadata["full_text_status"] == "complete"
    engine.dispose()


def test_same_batch_duplicate_full_text_does_not_rollback_expansion(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source = Source(
            name="Duplicate Discovery",
            country=None,
            language="en",
            source_type=SourceType.NEWS,
            credibility_baseline=Decimal("0.500"),
        )
        now = datetime.now(UTC)
        documents = [
            Document(
                source=source,
                url=f"https://publisher{index}.test/story",
                title="Syndicated article",
                body="Short.",
                published_at=now - timedelta(minutes=index),
                content_hash=str(index + 1) * 64,
            )
            for index in range(2)
        ]
        session.add_all(documents)
        session.flush()

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text="User-agent: *\nAllow: /")
            article = "The same syndicated evidence body is retained. " * 30
            return httpx.Response(
                200,
                text=f"<article><p>{article}</p></article>",
                headers={"content-type": "text/html"},
            )

        archive = ColdArchive(
            tmp_path,
            min_free_bytes=0,
            max_used_percent=99,
            disk_usage_provider=_roomy_usage,
        )

        async def run() -> None:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                result = await expand_full_text_batch(
                    session,
                    client=client,
                    archive=archive,
                    batch_size=2,
                    min_full_text_chars=600,
                    domain_delay_seconds=0,
                )
                assert result.expanded == 1
                assert result.duplicate == 1
                session.flush()

        asyncio.run(run())
        assert sum(
            document.raw_metadata.get("full_text_status") == "complete"
            for document in documents
        ) == 1
        assert sum(
            document.raw_metadata.get("full_text_status") == "duplicate_full_text"
            for document in documents
        ) == 1
    engine.dispose()


def test_publisher_container_extracts_sina_style_body() -> None:
    paragraph = "这是经过媒体正文容器验证的财经报道, 包含公司经营、产业链和市场背景。" * 35
    html = (
        "<html><head><meta name='config' content='articleID=artibody'>"
        "<script>window.noise = '<p>not evidence</p>';</script></head>"
        "<body><div>global navigation visible noise</div>"
        f"<body><div id='artibody'><p>{paragraph}</p></div>"
        "<aside><p>recommended story noise</p></aside></body></html>"
    )
    body, method = extract_article_text(html, publisher_domain="finance.sina.com.cn")
    assert len(body) > 600
    assert "财经报道" in body
    assert "global navigation visible noise" not in body
    assert "recommended story noise" not in body
    assert method == "publisher_container:finance.sina.com.cn"


def test_nested_json_ld_article_body_is_extracted() -> None:
    article = "Verified structured article evidence with market and policy context. " * 20
    payload = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebSite", "name": "Publisher"},
            {"@type": "NewsArticle", "articleBody": article},
        ],
    }
    html = f"<script type='application/ld+json'>{json.dumps(payload)}</script>"
    body, method = extract_article_text(html, publisher_domain="publisher.test")
    assert len(body) > 600
    assert method == "json_ld_article_body"


def test_verified_short_publisher_article_is_archived_once(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        document = Document(
            source=Source(
                name="UN News",
                country=None,
                language="zh",
                source_type=SourceType.NEWS,
                credibility_baseline=Decimal("0.950"),
            ),
            url="https://news.un.org/zh/story/1",
            title="联合国新闻短篇报道",
            body="简短摘要。",
            published_at=datetime.now(UTC),
            content_hash="1" * 64,
        )
        session.add(document)
        session.flush()
        paragraph = (
            "这是一篇经过联合国新闻正文容器确认的短篇报道, 包含事件背景、时间和公开证据。" * 18
        )
        html = f"<html><div class='field--name-body'><p>{paragraph}</p></div></html>"

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text="User-agent: *\nAllow: /")
            return httpx.Response(200, text=html, headers={"content-type": "text/html"})

        archive = ColdArchive(
            tmp_path,
            min_free_bytes=0,
            max_used_percent=99,
            disk_usage_provider=_roomy_usage,
        )

        async def run() -> None:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                first = await expand_full_text_batch(
                    session,
                    client=client,
                    archive=archive,
                    batch_size=1,
                    min_full_text_chars=1_200,
                    verified_short_min_chars=600,
                    domain_delay_seconds=0,
                )
                second = await expand_full_text_batch(
                    session,
                    client=client,
                    archive=archive,
                    batch_size=1,
                    min_full_text_chars=1_200,
                    verified_short_min_chars=600,
                    domain_delay_seconds=0,
                    force=True,
                )
                assert first.expanded == 1
                assert second.scanned == 0

        asyncio.run(run())
        assert document.raw_metadata["full_text_quality"] == "verified_short"
        assert document.raw_metadata["full_text_status"] == "complete"
    engine.dispose()


def test_structured_hazard_page_is_not_fetched_as_article(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        document = Document(
            source=Source(
                name="USGS",
                country="US",
                language="en",
                source_type=SourceType.NEWS,
                credibility_baseline=Decimal("0.990"),
            ),
            url="https://earthquake.usgs.gov/earthquakes/eventpage/test",
            title="Earthquake event record",
            body="Magnitude and coordinates.",
            published_at=datetime.now(UTC),
            content_hash="2" * 64,
        )
        session.add(document)
        session.flush()
        requests: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(str(request.url))
            return httpx.Response(500)

        archive = ColdArchive(
            tmp_path,
            min_free_bytes=0,
            max_used_percent=99,
            disk_usage_provider=_roomy_usage,
        )

        async def run() -> None:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                result = await expand_full_text_batch(
                    session,
                    client=client,
                    archive=archive,
                    batch_size=1,
                    min_full_text_chars=600,
                    verified_short_min_chars=600,
                    domain_delay_seconds=0,
                )
                assert result.insufficient == 1
                assert result.permanent == 1

        asyncio.run(run())
        assert requests == []
        assert document.raw_metadata["full_text_status"] == "non_article_source"
        assert document.raw_metadata["full_text_retry_class"] == "permanent"
    engine.dispose()
