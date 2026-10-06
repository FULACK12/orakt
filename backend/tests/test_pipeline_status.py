"""Live pipeline-status API tests."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.enums import ClusterJobStatus, SourceType
from app.db.models import (
    ClusterJob,
    Document,
    DocumentAnalysis,
    RSSFeed,
    Source,
)
from app.db.session import get_db_session
from app.embeddings import build_embedding_client
from app.extractors import build_event_extractor
from app.main import app
from app.schemas.cluster_jobs import ClusterJobParameters

TEST_ANALYSIS_EXTRACTOR = build_event_extractor().name
TEST_EMBEDDING_PROVIDER = build_embedding_client().name


@pytest.fixture
def pipeline_engine() -> Generator[object, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with Session(engine) as session:
        canada = Source(
            name="Canada source",
            country="CA",
            language="en",
            source_type=SourceType.RSS,
        )
        canada.rss_feeds.append(
            RSSFeed(
                url="https://canada.test/feed",
                enabled=True,
                license_name="Attribution",
                rate_limit_per_minute=Decimal("1"),
                last_fetched_at=now,
                last_success_at=now,
            )
        )
        global_source = Source(
            name="Global source",
            country=None,
            language="en",
            source_type=SourceType.RSS,
        )
        global_source.rss_feeds.append(
            RSSFeed(
                url="https://global.test/feed",
                enabled=True,
                license_name="Attribution",
                rate_limit_per_minute=Decimal("1"),
            )
        )
        document = Document(
            source=canada,
            url="https://canada.test/story",
            title="A local report",
            body="A local report body",
            content_hash="a" * 64,
            raw_object_path="raw/documents/aa/aa/story.json.gz",
        )
        session.add_all([canada, global_source, document])
        session.flush()
        parameters = ClusterJobParameters(
            document_ids=[document.id, document.id + 1],
            batch_size=1,
            merge_threshold=0.86,
            time_window_hours=48,
            location_radius_km=100,
        )
        job = ClusterJob(
            status=ClusterJobStatus.COMPLETED,
            total_documents=2,
            processed_documents=2,
            batch_size=1,
            parameters=parameters.model_dump(mode="json"),
            completed_at=now,
        )
        session.add(job)
        session.flush()
        session.add(
            DocumentAnalysis(
                document_id=document.id,
                content_hash=document.content_hash,
                extractor_name=TEST_ANALYSIS_EXTRACTOR,
                extraction={
                    "extractor": "test",
                    "document_id": document.id,
                    "events": [],
                },
                embedding_provider=TEST_EMBEDDING_PROVIDER,
                embeddings={"vectors": []},
                last_cluster_job_id=job.id,
            )
        )
        session.commit()

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        yield engine
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_pipeline_status_reports_ingestion_and_analysis(
    pipeline_engine: object,
) -> None:
    async def get_status() -> dict[str, object]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/pipeline/status")
        assert response.status_code == 200
        return response.json()

    payload = asyncio.run(get_status())

    assert payload["total_documents"] == 1
    assert payload["cold_archived_documents"] == 1
    assert payload["analyzed_documents"] == 1
    assert payload["pending_analysis_documents"] == 0
    assert payload["analysis_extractor"] == TEST_ANALYSIS_EXTRACTOR
    assert payload["embedding_provider"] == TEST_EMBEDDING_PROVIDER
    assert payload["active_cluster_jobs"] == 0
    assert payload["latest_completed_job_id"] == 1
    assert payload["configured_sources"] == 2
    assert payload["configured_countries"] == ["CA"]
    assert payload["global_sources"] == 1
    assert payload["enabled_feeds"] == 2
    assert payload["healthy_feeds"] == 1
    assert payload["pending_feeds"] == 1
    assert payload["failing_feeds"] == 0
    assert payload["sources"] == [
        {
            "source_name": "Canada source",
            "country": "CA",
            "language": "en",
            "source_type": "rss",
            "ownership": None,
            "credibility_baseline": 0.5,
            "document_count": 1,
            "total_feeds": 1,
            "enabled_feeds": 1,
        },
        {
            "source_name": "Global source",
            "country": None,
            "language": "en",
            "source_type": "rss",
            "ownership": None,
            "credibility_baseline": 0.5,
            "document_count": 0,
            "total_feeds": 1,
            "enabled_feeds": 1,
        },
    ]
