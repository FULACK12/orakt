"""Human cluster-review queue, decisions and local web console tests."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Generator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.cluster_review import sign_cluster_preview
from app.cluster_review_service import make_review_key
from app.core.config import get_settings
from app.db.base import Base
from app.db.enums import ClusterJobStatus, SourceType
from app.db.models import (
    ClusterJob,
    ClusterReviewDecisionRecord,
    Document,
    Event,
    EventDocument,
    Source,
)
from app.db.session import get_db_session
from app.main import app
from app.schemas.cluster_jobs import ClusterJobParameters, ClusterJobResult
from app.schemas.clusters import (
    ClusterCandidate,
    ClusterDocumentFingerprint,
    ClusterPreviewResponse,
    EventClusterPreview,
    PairEvaluation,
    SimilaritySignals,
)
from app.schemas.extractions import EvidenceSpan, ExtractedEvent

ReviewAPI = tuple[
    Engine,
    int,
    str,
    Callable[[str, dict[str, object] | None], Response],
]


@pytest.fixture
def review_api() -> Generator[ReviewAPI, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        sources = [
            Source(
                name=f"Review source {index}",
                country="CA",
                language="en",
                source_type=SourceType.OFFICIAL,
            )
            for index in (1, 2)
        ]
        documents = [
            Document(
                source=sources[index - 1],
                url=f"https://example.test/review/{index}",
                title=f"Port Delta closure report {index}",
                body=f"Port Delta closure report {index}",
                language="en",
                published_at=datetime(2026, 7, 29, 12, tzinfo=UTC),
                content_hash=f"{index:x}" * 64,
                raw_object_path=f"F:/News data/{index}.json.gz",
            )
            for index in (1, 2)
        ]
        session.add_all(documents)
        session.flush()
        candidates = [
            ClusterCandidate(
                candidate_id=f"{document.id}:0",
                document_id=document.id,
                event_index=0,
                extractor="review-test",
                event=_event(document.title),
            )
            for document in documents
        ]
        pair = PairEvaluation(
            left_candidate_id=candidates[0].candidate_id,
            right_candidate_id=candidates[1].candidate_id,
            score=0.91,
            signals=SimilaritySignals(
                embedding=0.98,
                title=0.9,
                entities=0.95,
                time=0.2,
                location=0.9,
            ),
            merged=False,
            blocker="event_time_too_far_apart",
            reasons=["high embedding similarity"],
        )
        unsigned = ClusterPreviewResponse(
            embedding_provider="review-test",
            requested_document_ids=[document.id for document in documents],
            document_fingerprints=[
                ClusterDocumentFingerprint(
                    document_id=document.id,
                    content_hash=document.content_hash,
                )
                for document in documents
            ],
            candidate_count=2,
            clusters=[
                EventClusterPreview(
                    cluster_id=index,
                    representative_candidate_id=candidate.candidate_id,
                    members=[candidate],
                )
                for index, candidate in enumerate(candidates, start=1)
            ],
            merge_edges=[],
            rejected_near_matches=[pair],
            potential_duplicate_document_ids=[],
            review_signature="0" * 64,
        )
        preview = sign_cluster_preview(
            unsigned,
            get_settings().cluster_review_secret,
        )
        result = ClusterJobResult(
            preview=preview,
            merge_cluster_ids=[],
            review_cluster_ids=[1, 2],
            independent_cluster_ids=[],
        )
        parameters = ClusterJobParameters(
            document_ids=[document.id for document in documents],
            batch_size=2,
            merge_threshold=0.86,
            time_window_hours=48,
            location_radius_km=100,
        )
        job = ClusterJob(
            status=ClusterJobStatus.COMPLETED,
            total_documents=2,
            processed_documents=2,
            batch_size=2,
            parameters=parameters.model_dump(mode="json"),
            result=result.model_dump(mode="json"),
            started_at=datetime(2026, 7, 29, 12, tzinfo=UTC),
            completed_at=datetime(2026, 7, 29, 12, tzinfo=UTC),
        )
        session.add(job)
        session.commit()
        job_id = job.id
        review_key = make_review_key(
            pair.left_candidate_id,
            pair.right_candidate_id,
        )

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    def request(path: str, payload: dict[str, object] | None = None) -> Response:
        async def send() -> Response:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                if payload is None:
                    return await client.get(path)
                return await client.post(path, json=payload)

        return asyncio.run(send())

    app.dependency_overrides[get_db_session] = override_session
    try:
        yield engine, job_id, review_key, request
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def _event(title: str) -> ExtractedEvent:
    return ExtractedEvent(
        event_type="port_closure",
        title=title,
        summary=title,
        occurred_at=datetime(2026, 7, 29, 12, tzinfo=UTC),
        severity=0.5,
        confidence=0.9,
        evidence_spans=[
            EvidenceSpan(
                field="summary",
                source_field="title",
                start_char=0,
                end_char=len(title),
                quote=title,
            )
        ],
    )


def test_review_queue_enriches_candidates_and_serves_console(
    review_api: ReviewAPI,
) -> None:
    _, job_id, review_key, request = review_api

    queue = request(f"/cluster-jobs/{job_id}/review")
    page = request("/review")
    stylesheet = request("/review-assets/review.css")
    audit_page = request("/research")
    audit_script = request("/review-assets/research.js")
    audit_stylesheet = request("/review-assets/research.css")

    assert queue.status_code == 200
    payload = queue.json()
    assert payload["summary"] == {
        "total": 1,
        "pending": 1,
        "merged": 0,
        "independent": 0,
        "ignored": 0,
    }
    assert payload["items"][0]["review_key"] == review_key
    assert payload["items"][0]["left"]["document"]["source_name"] == (
        "Review source 1"
    )
    assert page.status_code == 200
    assert "聚类复核台" in page.text
    assert audit_page.status_code == 200
    assert "AI 研究报告" in audit_page.text
    assert "查验报告" in audit_page.text
    assert "因子挖掘" in audit_page.text
    assert "证据核验" in audit_page.text
    assert "新闻分析" in audit_page.text
    assert 'id="research-catalog-filters"' in audit_page.text
    assert 'id="catalog-share"' in audit_page.text
    assert audit_script.status_code == 200
    assert "renderCausalValidation" in audit_script.text
    assert audit_stylesheet.status_code == 200
    assert ".audit-main" in audit_stylesheet.text
    assert stylesheet.status_code == 200


def test_merge_requires_confirmation_and_is_idempotent(
    review_api: ReviewAPI,
) -> None:
    engine, job_id, review_key, request = review_api
    path = f"/cluster-jobs/{job_id}/review/{review_key}"

    rejected = request(path, {"decision": "merge"})
    first = request(
        path,
        {
            "decision": "merge",
            "confirm_merge": True,
            "note": "same event",
        },
    )
    second = request(
        path,
        {
            "decision": "merge",
            "confirm_merge": True,
            "note": "same event",
        },
    )

    assert rejected.status_code == 422
    assert first.status_code == 200
    assert first.json()["created_event_count"] == 1
    assert first.json()["linked_document_count"] == 2
    assert first.json()["deletions_performed"] is False
    assert second.status_code == 200
    assert second.json()["created_event_count"] == 0
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 1
        assert session.scalar(
            select(func.count()).select_from(EventDocument)
        ) == 2
        assert session.scalar(
            select(func.count()).select_from(ClusterReviewDecisionRecord)
        ) == 1


def test_independent_decision_creates_two_canonical_events(
    review_api: ReviewAPI,
) -> None:
    engine, job_id, review_key, request = review_api

    response = request(
        f"/cluster-jobs/{job_id}/review/{review_key}",
        {"decision": "independent", "note": "different event times"},
    )
    queue = request(f"/cluster-jobs/{job_id}/review")

    assert response.status_code == 200
    assert response.json()["created_event_count"] == 2
    assert response.json()["linked_document_count"] == 2
    assert len(response.json()["decision"]["applied_event_ids"]) == 2
    assert queue.json()["summary"]["independent"] == 1
    assert queue.json()["summary"]["pending"] == 0
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 2


def test_ignored_decision_only_records_audit(
    review_api: ReviewAPI,
) -> None:
    engine, job_id, review_key, request = review_api

    response = request(
        f"/cluster-jobs/{job_id}/review/{review_key}",
        {"decision": "ignored"},
    )

    assert response.status_code == 200
    assert response.json()["created_event_count"] == 0
    assert response.json()["linked_document_count"] == 0
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 0
        assert session.scalar(
            select(func.count()).select_from(ClusterReviewDecisionRecord)
        ) == 1
