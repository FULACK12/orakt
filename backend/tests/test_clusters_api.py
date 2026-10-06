"""Side-effect-free cluster preview API tests."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Generator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.clusters import get_embedding_client
from app.api.extractions import get_event_extractor
from app.db.base import Base
from app.db.enums import SourceType
from app.db.models import Document, Event, EventDocument, Source
from app.db.session import get_db_session
from app.main import app
from app.schemas.extractions import (
    DocumentExtractionInput,
    EventExtractionResult,
    EvidenceSpan,
    ExtractedEntity,
    ExtractedEvent,
    ExtractedLocation,
)

ClusterAPI = tuple[
    list[int],
    Engine,
    Callable[[str, dict[str, object]], Response],
]


class StaticEmbeddingClient:
    name = "static-test"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


class StaticExtractor:
    name = "static-test"

    def extract(
        self,
        document: DocumentExtractionInput,
    ) -> EventExtractionResult:
        event = ExtractedEvent(
            event_type="port_closure",
            title=document.title,
            summary=document.title,
            entities=[
                ExtractedEntity(
                    name="Port Delta",
                    entity_type="asset",
                    confidence=0.95,
                )
            ],
            location=ExtractedLocation(
                name="Port Delta",
                country_code="CA",
                latitude=49.0,
                longitude=-123.0,
                confidence=0.9,
            ),
            occurred_at=datetime(2026, 7, 29, 12, tzinfo=UTC),
            severity=0.6,
            confidence=0.9,
            evidence_spans=[
                EvidenceSpan(
                    field="summary",
                    source_field="title",
                    start_char=0,
                    end_char=len(document.title),
                    quote=document.title,
                )
            ],
        )
        return EventExtractionResult(
            extractor=self.name,
            document_id=document.document_id,
            events=[event],
        )


@pytest.fixture
def cluster_api() -> Generator[ClusterAPI, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source = Source(
            name="Cluster test source",
            country="CA",
            language="en",
            source_type=SourceType.OFFICIAL,
        )
        documents = [
            Document(
                source=source,
                url=f"https://example.test/{index}",
                title=title,
                body=title,
                language="en",
                published_at=datetime(2026, 7, 29, 12, tzinfo=UTC),
                content_hash=str(index) * 64,
                raw_object_path=f"F:/News data/{index}.json.gz",
            )
            for index, title in (
                (1, "Agency A reports major Port Delta closure"),
                (2, "Major Port Delta closure reported by Agency B"),
            )
        ]
        session.add_all(documents)
        session.commit()
        document_ids = [document.id for document in documents]

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    def post(path: str, payload: dict[str, object]) -> Response:
        async def send() -> Response:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.post(path, json=payload)

        return asyncio.run(send())

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_event_extractor] = StaticExtractor
    app.dependency_overrides[get_embedding_client] = StaticEmbeddingClient
    try:
        yield document_ids, engine, post
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_event_extractor, None)
        app.dependency_overrides.pop(get_embedding_client, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_cluster_preview_merges_reports_without_deleting(
    cluster_api: ClusterAPI,
) -> None:
    document_ids, _, post = cluster_api

    response = post(
        "/event-clusters/preview",
        {"document_ids": document_ids, "merge_threshold": 0.8},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["embedding_provider"] == "static-test"
    assert payload["candidate_count"] == 2
    assert len(payload["clusters"]) == 1
    assert len(payload["clusters"][0]["members"]) == 2
    assert payload["potential_duplicate_document_ids"] == [document_ids[1]]
    assert payload["safe_to_delete_document_ids"] == []
    assert payload["deletions_performed"] is False
    assert len(payload["review_signature"]) == 64
    assert [item["document_id"] for item in payload["document_fingerprints"]] == (
        document_ids
    )


def test_cluster_preview_reports_missing_documents(
    cluster_api: ClusterAPI,
) -> None:
    document_ids, _, post = cluster_api

    response = post(
        "/event-clusters/preview",
        {"document_ids": [document_ids[0], 999999]},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["missing_document_ids"] == [999999]


def test_signed_cluster_apply_is_persistent_and_idempotent(
    cluster_api: ClusterAPI,
) -> None:
    document_ids, engine, post = cluster_api
    preview = post(
        "/event-clusters/preview",
        {"document_ids": document_ids, "merge_threshold": 0.8},
    ).json()
    request = {
        "preview": preview,
        "selected_cluster_ids": [1],
        "confirm_persistence": True,
    }

    first = post("/event-clusters/apply", request)
    second = post("/event-clusters/apply", request)

    assert first.status_code == 200
    assert first.json()["created_event_count"] == 1
    assert first.json()["linked_document_count"] == 2
    assert first.json()["cold_archive_review_candidates"] == [document_ids[1]]
    assert first.json()["deletions_performed"] is False
    assert second.status_code == 200
    assert second.json()["created_event_count"] == 0
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 1
        assert session.scalar(select(func.count()).select_from(EventDocument)) == 2


def test_cluster_apply_rejects_tampered_preview(
    cluster_api: ClusterAPI,
) -> None:
    document_ids, engine, post = cluster_api
    preview = post(
        "/event-clusters/preview",
        {"document_ids": document_ids, "merge_threshold": 0.8},
    ).json()
    preview["clusters"][0]["members"][0]["event"]["title"] = "tampered title"

    response = post(
        "/event-clusters/apply",
        {
            "preview": preview,
            "selected_cluster_ids": [1],
            "confirm_persistence": True,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "cluster preview signature is invalid"
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 0


def test_cluster_apply_rejects_documents_changed_after_review(
    cluster_api: ClusterAPI,
) -> None:
    document_ids, engine, post = cluster_api
    preview = post(
        "/event-clusters/preview",
        {"document_ids": document_ids, "merge_threshold": 0.8},
    ).json()
    with Session(engine) as session:
        document = session.get(Document, document_ids[0])
        assert document is not None
        document.content_hash = "f" * 64
        session.commit()

    response = post(
        "/event-clusters/apply",
        {
            "preview": preview,
            "selected_cluster_ids": [1],
            "confirm_persistence": True,
        },
    )

    assert response.status_code == 409
    assert "reviewed documents changed" in response.json()["detail"]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 0
