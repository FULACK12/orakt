"""Durable cluster-job API and worker tests."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Generator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.cluster_jobs import ClusterJobWorker
from app.cluster_queue import ensure_incremental_cluster_job
from app.db.base import Base
from app.db.enums import ClusterJobStatus, SourceType
from app.db.models import (
    ClusterJob,
    Document,
    DocumentAnalysis,
    Event,
    EventDocument,
    ResearchBatch,
    ResearchBatchItem,
    Source,
)
from app.db.session import get_db_session
from app.embeddings import EmbeddingProviderUnavailableError
from app.main import app
from app.schemas.cluster_jobs import ClusterJobParameters, ClusterJobResult
from app.schemas.extractions import (
    DocumentExtractionInput,
    EventExtractionResult,
    EvidenceSpan,
    ExtractedEntity,
    ExtractedEvent,
)

JobAPI = tuple[Engine, list[int], Callable[[str, dict[str, object] | None], Response]]


class WorkerExtractor:
    name = "worker-test"

    def __init__(self) -> None:
        self.calls = 0

    def extract(
        self,
        document: DocumentExtractionInput,
    ) -> EventExtractionResult:
        self.calls += 1
        event = ExtractedEvent(
            event_type="port_closure",
            title="Port Delta closed after storm",
            summary=document.title,
            entities=[
                ExtractedEntity(
                    name="Port Delta",
                    entity_type="asset",
                    confidence=0.9,
                )
            ],
            occurred_at=datetime(2026, 7, 29, 12, tzinfo=UTC),
            severity=0.5,
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


class WorkerEmbeddingClient:
    name = "worker-embedding-test"

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[1.0, 0.0] for _ in texts]


class FailingSecondExtractor(WorkerExtractor):
    def extract(
        self,
        document: DocumentExtractionInput,
    ) -> EventExtractionResult:
        if self.calls == 1:
            raise RuntimeError("simulated extraction failure")
        return super().extract(document)


@pytest.fixture
def job_api() -> Generator[JobAPI, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source = Source(
            name="Job test source",
            country="CA",
            language="en",
            source_type=SourceType.OFFICIAL,
        )
        documents = [
            Document(
                source=source,
                url=f"https://example.test/job/{index}",
                title=f"Report {index} about Port Delta",
                body=f"Report {index} about Port Delta",
                language="en",
                published_at=datetime(2026, 7, 29, 12, tzinfo=UTC),
                content_hash=f"{index:x}" * 64,
            )
            for index in range(1, 4)
        ]
        session.add_all(documents)
        session.commit()
        document_ids = [document.id for document in documents]

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    def request(path: str, payload: dict[str, object] | None = None) -> Response:
        async def send() -> Response:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                if payload is None:
                    return await client.get(path)
                return await client.post(path, json=payload)

        return asyncio.run(send())

    app.dependency_overrides[get_db_session] = override_session
    try:
        yield engine, document_ids, request
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_cluster_job_api_snapshots_documents_and_lists_job(
    job_api: JobAPI,
) -> None:
    _, document_ids, request = job_api

    created = request(
        "/cluster-jobs",
        {"document_ids": document_ids, "batch_size": 2},
    )
    listed = request("/cluster-jobs")

    assert created.status_code == 201
    payload = created.json()
    assert payload["status"] == "queued"
    assert payload["total_documents"] == 3
    assert payload["parameters"]["document_ids"] == document_ids
    assert payload["progress_percent"] == 0
    assert listed.status_code == 200
    assert listed.json()["jobs"][0]["id"] == payload["id"]


def test_worker_completes_job_and_classifies_merge_cluster(
    job_api: JobAPI,
) -> None:
    engine, document_ids, request = job_api
    created = request(
        "/cluster-jobs",
        {"document_ids": document_ids[:2], "batch_size": 1},
    ).json()
    factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )
    worker = ClusterJobWorker(
        factory,
        WorkerExtractor(),
        WorkerEmbeddingClient(),
        "test-review-secret-that-is-at-least-32-bytes",
    )

    assert worker.run_next() is True
    assert worker.run_next() is False

    response = request(f"/cluster-jobs/{created['id']}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["processed_documents"] == 2
    assert payload["progress_percent"] == 100
    result = ClusterJobResult.model_validate(payload["result"])
    assert result.merge_cluster_ids == [1]
    assert result.review_cluster_ids == []
    assert result.independent_cluster_ids == []
    assert len(result.preview.review_signature) == 64


def test_worker_recovers_interrupted_jobs(job_api: JobAPI) -> None:
    engine, document_ids, _ = job_api
    parameters = ClusterJobParameters(
        document_ids=document_ids[:2],
        batch_size=1,
        merge_threshold=0.86,
        time_window_hours=48,
        location_radius_km=100,
    )
    with Session(engine) as session:
        session.add(
            ClusterJob(
                status=ClusterJobStatus.RUNNING,
                total_documents=2,
                processed_documents=1,
                batch_size=1,
                parameters=parameters.model_dump(mode="json"),
                started_at=datetime.now(UTC),
            )
        )
        session.commit()
    factory = sessionmaker(bind=engine, class_=Session)
    worker = ClusterJobWorker(
        factory,
        WorkerExtractor(),
        WorkerEmbeddingClient(),
        "test-review-secret-that-is-at-least-32-bytes",
    )

    assert worker.recover_interrupted_jobs() == 1

    with Session(engine) as session:
        job = session.query(ClusterJob).one()
        assert job.status == ClusterJobStatus.QUEUED
        assert job.processed_documents == 1
        assert job.progress_stage == "recovered_after_restart"
        assert job.started_at is None


def test_worker_pauses_without_spending_attempt_when_embedding_runtime_is_offline(
    job_api: JobAPI,
) -> None:
    engine, document_ids, request = job_api
    created = request(
        "/cluster-jobs",
        {"document_ids": document_ids[:2], "batch_size": 1},
    ).json()
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    worker = ClusterJobWorker(
        factory,
        WorkerExtractor(),
        WorkerEmbeddingClient(),
        "test-review-secret-that-is-at-least-32-bytes",
    )
    with Session(engine) as session:
        job = session.get(ClusterJob, created["id"])
        assert job is not None
        job.status = ClusterJobStatus.RUNNING
        job.attempt_count = 1
        job.progress_percent = 75
        job.progress_stage = "embedding_events"
        session.commit()

    worker._fail_job(
        created["id"],
        EmbeddingProviderUnavailableError("ollama offline"),
    )

    with Session(engine) as session:
        job = session.get(ClusterJob, created["id"])
        assert job is not None
        assert job.status == ClusterJobStatus.QUEUED
        assert job.attempt_count == 0
        assert job.progress_percent == 75
        assert job.progress_stage == "waiting_for_model"
        assert job.completed_at is None


def test_worker_reuses_validated_analysis_cache(job_api: JobAPI) -> None:
    engine, document_ids, request = job_api
    extractor = WorkerExtractor()
    embedding_client = WorkerEmbeddingClient()
    factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )
    worker = ClusterJobWorker(
        factory,
        extractor,
        embedding_client,
        "test-review-secret-that-is-at-least-32-bytes",
    )
    first_job = request(
        "/cluster-jobs",
        {"document_ids": document_ids[:2], "batch_size": 1},
    ).json()

    assert worker.run_next() is True
    assert extractor.calls == 2
    assert embedding_client.calls == 2

    second_job = request(
        "/cluster-jobs",
        {"document_ids": document_ids[:2], "batch_size": 1},
    ).json()
    assert worker.run_next() is True
    assert extractor.calls == 2
    assert embedding_client.calls == 2

    with Session(engine) as session:
        analyses = list(session.query(DocumentAnalysis).order_by(DocumentAnalysis.document_id))
        assert len(analyses) == 2
        assert all(analysis.last_cluster_job_id == second_job["id"] for analysis in analyses)
        assert first_job["id"] != second_job["id"]


def test_worker_keeps_analysis_cache_when_clustering_fails(
    job_api: JobAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, document_ids, request = job_api
    factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )
    worker = ClusterJobWorker(
        factory,
        WorkerExtractor(),
        WorkerEmbeddingClient(),
        "test-review-secret-that-is-at-least-32-bytes",
    )
    created = request(
        "/cluster-jobs",
        {"document_ids": document_ids[:2], "batch_size": 1},
    ).json()

    def fail_clustering(*_args: object, **_kwargs: object) -> None:
        raise TypeError("simulated clustering failure")

    monkeypatch.setattr(
        "app.cluster_service.EventClusterer.cluster",
        fail_clustering,
    )

    assert worker.run_next() is True

    with Session(engine) as session:
        job = session.get(ClusterJob, created["id"])
        analyses = list(session.query(DocumentAnalysis))
        assert job is not None
        assert job.status == ClusterJobStatus.FAILED
        assert len(analyses) == 2
        assert all(analysis.last_cluster_job_id is None for analysis in analyses)


def test_worker_commits_each_completed_extraction_batch(
    job_api: JobAPI,
) -> None:
    engine, document_ids, request = job_api
    factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )
    worker = ClusterJobWorker(
        factory,
        FailingSecondExtractor(),
        WorkerEmbeddingClient(),
        "test-review-secret-that-is-at-least-32-bytes",
    )
    created = request(
        "/cluster-jobs",
        {"document_ids": document_ids[:2], "batch_size": 1},
    ).json()

    assert worker.run_next() is True

    with Session(engine) as session:
        job = session.get(ClusterJob, created["id"])
        analyses = list(session.query(DocumentAnalysis))
        assert job is not None
        assert job.status == ClusterJobStatus.FAILED
        assert len(analyses) == 1
        assert analyses[0].document_id == document_ids[0]
        assert analyses[0].last_cluster_job_id is None


def test_worker_yields_after_cached_batch_when_research_report_waits(
    job_api: JobAPI,
) -> None:
    engine, document_ids, request = job_api
    extractor = WorkerExtractor()
    factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )
    worker = ClusterJobWorker(
        factory,
        extractor,
        WorkerEmbeddingClient(),
        "test-review-secret-that-is-at-least-32-bytes",
    )
    created = request(
        "/cluster-jobs",
        {"document_ids": document_ids[:2], "batch_size": 1},
    ).json()
    with Session(engine) as session:
        batch = ResearchBatch(
            name="Priority report",
            status="running",
            template_version="test-v1",
            parameters={},
            target_count=1,
        )
        batch.items.append(
            ResearchBatchItem(
                market_region="us",
                research_scope="sec_numeric_evidence",
                ticker="NVDA",
                company_name="NVIDIA Corp.",
                question="Test priority research report",
                priority=1,
                status="queued",
                data_readiness={},
            )
        )
        session.add(batch)
        session.commit()

    assert worker.run_next() is False

    with Session(engine) as session:
        job = session.get(ClusterJob, created["id"])
        item = session.query(ResearchBatchItem).one()
        analyses = list(session.query(DocumentAnalysis))
        assert job is not None
        assert job.status == ClusterJobStatus.QUEUED
        assert job.processed_documents == 1
        assert job.error_message is not None
        assert "Yielded" in job.error_message
        assert job.attempt_count == 1
        assert len(analyses) == 1
        job.processed_documents = 2
        session.commit()

    # Replaying the cached first document while another report is waiting must
    # not make a resumed job's visible progress jump backwards.
    assert worker.run_next() is False
    with Session(engine) as session:
        job = session.get(ClusterJob, created["id"])
        item = session.query(ResearchBatchItem).one()
        assert job is not None
        assert job.processed_documents == 2
        assert job.attempt_count == 1
        item.status = "completed"
        session.commit()

    assert worker.run_next() is True
    assert extractor.calls == 2

    with Session(engine) as session:
        job = session.get(ClusterJob, created["id"])
        assert job is not None
        assert job.status == ClusterJobStatus.COMPLETED
        assert job.processed_documents == 2
        assert job.attempt_count == 1


def test_incremental_queue_skips_active_and_fully_processed_corpus(
    job_api: JobAPI,
) -> None:
    engine, document_ids, _ = job_api
    with Session(engine) as session:
        first_job_id = ensure_incremental_cluster_job(session)
        session.commit()
        assert first_job_id is not None
        assert ensure_incremental_cluster_job(session) is None

        job = session.get(ClusterJob, first_job_id)
        assert job is not None
        job.status = ClusterJobStatus.COMPLETED
        job.processed_documents = job.total_documents
        job.completed_at = datetime.now(UTC)
        documents = list(session.query(Document).filter(Document.id.in_(document_ids)))
        session.add_all(
            [
                DocumentAnalysis(
                    document_id=document.id,
                    content_hash=document.content_hash,
                    extractor_name="worker-test",
                    extraction={
                        "extractor": "worker-test",
                        "document_id": document.id,
                        "events": [],
                    },
                    embedding_provider="worker-embedding-test",
                    embeddings={"vectors": []},
                    last_cluster_job_id=first_job_id,
                )
                for document in documents
            ]
        )
        session.commit()

        assert ensure_incremental_cluster_job(session) is None

        new_document = Document(
            source_id=documents[0].source_id,
            url="https://example.test/job/new",
            title="A newly collected report",
            body="A newly collected report",
            language="en",
            published_at=datetime.now(UTC),
            content_hash="f" * 64,
        )
        session.add(new_document)
        session.commit()

        second_job_id = ensure_incremental_cluster_job(session)
        session.commit()
        assert second_job_id is not None
        second_job = session.get(ClusterJob, second_job_id)
        assert second_job is not None
        second_parameters = ClusterJobParameters.model_validate(second_job.parameters)
        assert set(second_parameters.document_ids) == {
            *document_ids,
            new_document.id,
        }


def test_incremental_queue_reuses_failed_snapshot_instead_of_creating_duplicates(
    job_api: JobAPI,
) -> None:
    engine, _, _ = job_api
    with Session(engine) as session:
        first_job_id = ensure_incremental_cluster_job(
            session,
            extractor_name="worker-test",
            embedding_provider="worker-embedding-test",
        )
        session.commit()
        assert first_job_id is not None
        job = session.get(ClusterJob, first_job_id)
        assert job is not None
        assert job.parameters["snapshot_fingerprint"]
        job.status = ClusterJobStatus.FAILED
        job.attempt_count = 1
        job.progress_stage = "failed"
        job.error_message = "temporary embedding failure"
        session.commit()

        retried_job_id = ensure_incremental_cluster_job(
            session,
            extractor_name="worker-test",
            embedding_provider="worker-embedding-test",
        )
        session.commit()

        assert retried_job_id == first_job_id
        assert session.query(ClusterJob).count() == 1
        assert job.status == ClusterJobStatus.QUEUED
        assert job.progress_stage == "retrying_same_snapshot"
        assert ensure_incremental_cluster_job(
            session,
            extractor_name="worker-test",
            embedding_provider="worker-embedding-test",
        ) is None


def test_incremental_queue_stops_recreating_exhausted_snapshot(
    job_api: JobAPI,
) -> None:
    engine, _, _ = job_api
    with Session(engine) as session:
        job_id = ensure_incremental_cluster_job(
            session,
            extractor_name="worker-test",
            embedding_provider="worker-embedding-test",
        )
        session.commit()
        assert job_id is not None
        job = session.get(ClusterJob, job_id)
        assert job is not None
        job.status = ClusterJobStatus.FAILED
        job.attempt_count = job.max_attempts
        job.progress_stage = "failed"
        session.commit()

        assert ensure_incremental_cluster_job(
            session,
            extractor_name="worker-test",
            embedding_provider="worker-embedding-test",
        ) is None
        assert session.query(ClusterJob).count() == 1


def test_incremental_queue_reanalyzes_linked_document_after_fulltext_change(
    job_api: JobAPI,
) -> None:
    engine, document_ids, _ = job_api
    with Session(engine) as session:
        initial_job_id = ensure_incremental_cluster_job(session)
        assert initial_job_id is not None
        initial_job = session.get(ClusterJob, initial_job_id)
        assert initial_job is not None
        initial_job.status = ClusterJobStatus.COMPLETED
        initial_job.processed_documents = initial_job.total_documents
        initial_job.completed_at = datetime.now(UTC)
        documents = list(session.query(Document).filter(Document.id.in_(document_ids)))
        session.add_all(
            [
                DocumentAnalysis(
                    document_id=document.id,
                    content_hash=document.content_hash,
                    extractor_name="worker-test",
                    extraction={
                        "extractor": "worker-test",
                        "document_id": document.id,
                        "events": [],
                    },
                    embedding_provider="worker-embedding-test",
                    embeddings={"vectors": []},
                    last_cluster_job_id=initial_job_id,
                )
                for document in documents
            ]
        )
        event = Event(
            event_type="market_news",
            title="Existing canonical event",
            summary="Originally linked from a short feed record.",
            start_at=datetime.now(UTC),
        )
        session.add(event)
        session.flush()
        session.add(
            EventDocument(
                event_id=event.id,
                document_id=documents[0].id,
            )
        )
        session.commit()

        documents[0].raw_metadata = {"full_text_status": "complete"}
        documents[0].content_hash = "f" * 64
        newer_unlinked = Document(
            source_id=documents[0].source_id,
            url="https://example.test/job/newer-unlinked",
            title="A newer unlinked document",
            body="New unlinked evidence.",
            language="en",
            published_at=datetime.now(UTC),
            content_hash="e" * 64,
        )
        session.add(newer_unlinked)
        session.commit()
        refresh_job_id = ensure_incremental_cluster_job(session)
        session.commit()

        assert refresh_job_id is not None
        refresh_job = session.get(ClusterJob, refresh_job_id)
        assert refresh_job is not None
        parameters = ClusterJobParameters.model_validate(refresh_job.parameters)
        assert documents[0].id in parameters.document_ids
        assert parameters.document_ids[0] == documents[0].id
