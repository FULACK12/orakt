"""Simple local scheduler for configured RSS feeds."""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.cluster_queue import ensure_incremental_cluster_job
from app.collectors.rss import RSSCollector
from app.collectors.schemas import BatchCollectionResult
from app.db.models import RSSFeed


class RSSScheduler:
    """Run due feeds once or on a stoppable polling loop."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        collector: RSSCollector,
        *,
        analysis_extractor_name: str | None = None,
        analysis_embedding_provider: str | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.collector = collector
        self.analysis_extractor_name = analysis_extractor_name
        self.analysis_embedding_provider = analysis_embedding_provider

    async def run_once(self, *, force: bool = False) -> BatchCollectionResult:
        """Load enabled feeds and run one isolated collection pass."""
        with self.session_factory() as session:
            feeds = list(
                session.scalars(
                    select(RSSFeed)
                    .options(selectinload(RSSFeed.source))
                    .where(RSSFeed.enabled.is_(True))
                    .order_by(RSSFeed.id)
                )
            )
            result = await self.collector.collect_many(
                session,
                feeds,
                force=force,
            )
            ensure_incremental_cluster_job(
                session,
                extractor_name=self.analysis_extractor_name,
                embedding_provider=self.analysis_embedding_provider,
            )
            session.commit()
            return result

    async def run_forever(
        self,
        stop_event: asyncio.Event,
        *,
        poll_seconds: float = 30,
    ) -> None:
        """Poll until the supplied event requests a graceful stop."""
        if poll_seconds < 1:
            raise ValueError("poll_seconds must be at least 1")
        while not stop_event.is_set():
            await self.run_once()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=poll_seconds)
            except TimeoutError:
                continue
