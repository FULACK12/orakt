"""Conservative event-chain generation tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.enums import ClusterJobStatus, SourceType
from app.db.models import ClusterJob, Document, EventRelationCandidate, Source
from app.event_chains import decide_relation, generate_event_chain, list_event_chain
from app.schemas.cluster_jobs import ClusterJobResult
from app.schemas.clusters import (
    ClusterCandidate,
    ClusterDocumentFingerprint,
    ClusterPreviewResponse,
    EventClusterPreview,
)
from app.schemas.extractions import (
    EvidenceSpan,
    ExtractedEntity,
    ExtractedEvent,
    ExtractedLocation,
)


def _candidate(
    *,
    candidate_id: str,
    document_id: int,
    title: str,
    occurred_at: datetime,
) -> ClusterCandidate:
    return ClusterCandidate(
        candidate_id=candidate_id,
        document_id=document_id,
        event_index=0,
        extractor="test",
        event=ExtractedEvent(
            event_type="policy_announcement",
            title=title,
            summary=title,
            entities=[
                ExtractedEntity(
                    name="Example Organization",
                    entity_type="organization",
                    confidence=0.9,
                )
            ],
            location=ExtractedLocation(
                name="Ottawa",
                country_code="CA",
                confidence=0.9,
            ),
            occurred_at=occurred_at,
            severity=0.4,
            confidence=0.8,
            evidence_spans=[
                EvidenceSpan(
                    field="summary",
                    source_field="title",
                    start_char=0,
                    end_char=len(title),
                    quote=title,
                )
            ],
        ),
    )


def test_event_chain_generation_never_confirms_causality() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with Session(engine) as session:
        source = Source(
            name="Test source",
            language="en",
            source_type=SourceType.RSS,
            credibility_baseline=Decimal("0.800"),
        )
        documents = [
            Document(
                source=source,
                url=f"https://example.test/{index}",
                title=title,
                body=title,
                language="en",
                published_at=now + timedelta(days=index),
                content_hash=str(index) * 64,
            )
            for index, title in enumerate(
                ["Example announces policy", "Following the policy, Example responds"],
                start=1,
            )
        ]
        session.add_all(documents)
        session.flush()
        candidates = [
            _candidate(
                candidate_id=f"candidate-{index}",
                document_id=document.id,
                title=document.title,
                occurred_at=document.published_at,
            )
            for index, document in enumerate(documents, start=1)
        ]
        preview = ClusterPreviewResponse(
            embedding_provider="test",
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
            rejected_near_matches=[],
            potential_duplicate_document_ids=[],
            review_signature="a" * 64,
        )
        result = ClusterJobResult(
            preview=preview,
            merge_cluster_ids=[],
            review_cluster_ids=[],
            independent_cluster_ids=[1, 2],
        )
        job = ClusterJob(
            status=ClusterJobStatus.COMPLETED,
            total_documents=2,
            processed_documents=2,
            batch_size=2,
            parameters={
                "document_ids": [document.id for document in documents],
                "batch_size": 2,
                "merge_threshold": 0.86,
                "time_window_hours": 48,
                "location_radius_km": 100,
            },
            result=result.model_dump(mode="json"),
            completed_at=now,
        )
        session.add(job)
        session.flush()

        generated = generate_event_chain(session, job_id=job.id)
        session.commit()

        assert generated.generated_count == 1
        assert generated.causality_is_confirmed is False
        assert generated.relations[0].relation_type == "reported_follow_up"
        assert generated.relations[0].status == "suggested"
        relation = decide_relation(
            session,
            relation_id=generated.relations[0].id,
            decision="accepted",
            pinned=True,
            review_note="Reviewed against both source documents.",
        )
        session.commit()
        reviewed = list_event_chain(session, job_id=job.id)
        assert relation.pinned is True
        assert reviewed.fixed_relation_count == 1
        assert reviewed.relations[0].review_note is not None
        assert reviewed.causality_is_confirmed is False
        assert session.scalar(
            select(func.count()).select_from(EventRelationCandidate)
        ) == 1

    engine.dispose()


def test_event_chain_does_not_link_two_candidates_from_one_document() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with Session(engine) as session:
        source = Source(
            name="One document source",
            language="en",
            source_type=SourceType.RSS,
            credibility_baseline=Decimal("0.800"),
        )
        document = Document(
            source=source,
            url="https://example.test/one-document",
            title="Example policy and response",
            body="Example policy and response",
            language="en",
            published_at=now,
            content_hash="c" * 64,
        )
        session.add(document)
        session.flush()
        candidates = [
            _candidate(
                candidate_id=f"same-document-{index}",
                document_id=document.id,
                title=f"Example response {index}",
                occurred_at=now + timedelta(minutes=index),
            )
            for index in range(2)
        ]
        preview = ClusterPreviewResponse(
            embedding_provider="test",
            requested_document_ids=[document.id],
            document_fingerprints=[
                ClusterDocumentFingerprint(
                    document_id=document.id,
                    content_hash=document.content_hash,
                )
            ],
            candidate_count=2,
            clusters=[
                EventClusterPreview(
                    cluster_id=index + 1,
                    representative_candidate_id=candidate.candidate_id,
                    members=[candidate],
                )
                for index, candidate in enumerate(candidates)
            ],
            merge_edges=[],
            rejected_near_matches=[],
            potential_duplicate_document_ids=[],
            review_signature="d" * 64,
        )
        job = ClusterJob(
            status=ClusterJobStatus.COMPLETED,
            total_documents=1,
            processed_documents=1,
            batch_size=1,
            parameters={
                "document_ids": [document.id],
                "batch_size": 1,
                "merge_threshold": 0.86,
                "time_window_hours": 48,
                "location_radius_km": 100,
            },
            result=ClusterJobResult(
                preview=preview,
                merge_cluster_ids=[],
                review_cluster_ids=[],
                independent_cluster_ids=[1, 2],
            ).model_dump(mode="json"),
            completed_at=now,
        )
        session.add(job)
        session.flush()

        generated = generate_event_chain(session, job_id=job.id)

        assert generated.generated_count == 0
        assert generated.relation_count == 0
    engine.dispose()
