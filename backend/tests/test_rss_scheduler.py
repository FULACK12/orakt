"""RSS scheduler query and execution tests."""

import asyncio
from decimal import Decimal

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.collectors.rss import RSSCollector
from app.collectors.scheduler import RSSScheduler
from app.db.base import Base
from app.db.enums import SourceType
from app.db.models import RSSFeed, Source
from tests.test_rss_collector import RSS_BODY


def test_scheduler_only_loads_enabled_feeds() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

    with factory() as session:
        source = Source(
            name="Scheduler source",
            country="US",
            source_type=SourceType.RSS,
        )
        source.rss_feeds.extend(
            [
                RSSFeed(
                    url="https://enabled.test/rss.xml",
                    enabled=True,
                    license_name="Test license",
                    rate_limit_per_minute=Decimal("1"),
                ),
                RSSFeed(
                    url="https://disabled.test/rss.xml",
                    enabled=False,
                    license_name="Test license",
                    rate_limit_per_minute=Decimal("1"),
                ),
            ]
        )
        session.add(source)
        session.commit()

    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, content=RSS_BODY)

    async def run() -> int:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await RSSScheduler(factory, RSSCollector(client)).run_once(force=True)
        return len(result.results)

    assert asyncio.run(run()) == 1
    assert requests == ["https://enabled.test/rss.xml"]
    engine.dispose()
