"""Persistence of explicitly reviewed event clusters."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.enums import DocumentStance, EventStatus
from app.db.models import Document, Event, EventDocument
from app.schemas.clusters import (
    AppliedEventCluster,
    ClusterApplyResponse,
    ClusterPreviewResponse,
    EventClusterPreview,
)


class ClusterPersistenceConflict(RuntimeError):
    """Reviewed state conflicts with current database state."""


@dataclass(frozen=True)
class PersistenceContext:
    documents: dict[int, Document]
    selected_clusters: list[EventClusterPreview]


def persist_reviewed_clusters(
    session: Session,
    *,
    preview: ClusterPreviewResponse,
    selected_cluster_ids: list[int],
) -> ClusterApplyResponse:
    """Create or idempotently reuse canonical events for signed clusters."""
    context = _validate_current_state(
        session,
        preview=preview,
        selected_cluster_ids=selected_cluster_ids,
    )
    applied: list[AppliedEventCluster] = []
    linked_documents: set[int] = set()

    for cluster in context.selected_clusters:
        event, created = _get_or_create_event(
            session,
            cluster=cluster,
            documents=context.documents,
        )
        member_document_ids = sorted(
            {member.document_id for member in cluster.members}
        )
        existing_document_ids = set(
            session.scalars(
                select(EventDocument.document_id).where(
                    EventDocument.event_id == event.id
                )
            )
        )
        representative = next(
            member
            for member in cluster.members
            if member.candidate_id == cluster.representative_candidate_id
        )
        for member in cluster.members:
            if member.document_id in existing_document_ids:
                continue
            session.add(
                EventDocument(
                    event_id=event.id,
                    document_id=member.document_id,
                    relevance_score=_decimal_score(member.event.confidence),
                    stance=DocumentStance.SUPPORTS,
                    is_primary_source=(
                        member.candidate_id == representative.candidate_id
                    ),
                )
            )
        session.flush()
        linked_documents.update(member_document_ids)
        applied.append(
            AppliedEventCluster(
                cluster_id=cluster.cluster_id,
                event_id=event.id,
                created=created,
                document_ids=member_document_ids,
            )
        )

    review_candidates = _cold_archive_review_candidates(
        preview=preview,
        selected_cluster_ids=set(selected_cluster_ids),
        documents=context.documents,
    )
    return ClusterApplyResponse(
        applied_clusters=applied,
        created_event_count=sum(item.created for item in applied),
        linked_document_count=len(linked_documents),
        cold_archive_review_candidates=review_candidates,
    )


def _validate_current_state(
    session: Session,
    *,
    preview: ClusterPreviewResponse,
    selected_cluster_ids: list[int],
) -> PersistenceContext:
    clusters_by_id = {cluster.cluster_id: cluster for cluster in preview.clusters}
    missing_cluster_ids = sorted(set(selected_cluster_ids) - clusters_by_id.keys())
    if missing_cluster_ids:
        raise ClusterPersistenceConflict(
            f"unknown selected cluster ids: {missing_cluster_ids}"
        )
    fingerprints = {
        item.document_id: item.content_hash
        for item in preview.document_fingerprints
    }
    documents = list(
        session.scalars(
            select(Document)
            .where(Document.id.in_(fingerprints))
            .options(selectinload(Document.source))
        )
    )
    documents_by_id = {document.id: document for document in documents}
    missing_document_ids = sorted(set(fingerprints) - documents_by_id.keys())
    if missing_document_ids:
        raise ClusterPersistenceConflict(
            f"reviewed documents no longer exist: {missing_document_ids}"
        )
    changed_document_ids = sorted(
        document_id
        for document_id, expected_hash in fingerprints.items()
        if documents_by_id[document_id].content_hash != expected_hash
    )
    if changed_document_ids:
        raise ClusterPersistenceConflict(
            f"reviewed documents changed: {changed_document_ids}"
        )
    selected_clusters = [
        clusters_by_id[cluster_id] for cluster_id in selected_cluster_ids
    ]
    selected_document_ids = {
        member.document_id
        for cluster in selected_clusters
        for member in cluster.members
    }
    if not selected_document_ids <= documents_by_id.keys():
        raise ClusterPersistenceConflict(
            "selected cluster contains an unsigned document"
        )
    return PersistenceContext(
        documents=documents_by_id,
        selected_clusters=selected_clusters,
    )


def _get_or_create_event(
    session: Session,
    *,
    cluster: EventClusterPreview,
    documents: dict[int, Document],
) -> tuple[Event, bool]:
    representative = next(
        member
        for member in cluster.members
        if member.candidate_id == cluster.representative_candidate_id
    )
    document_ids = {member.document_id for member in cluster.members}
    existing_event_ids = set(
        session.scalars(
            select(EventDocument.event_id)
            .join(Event, Event.id == EventDocument.event_id)
            .where(
                EventDocument.document_id.in_(document_ids),
                Event.event_type == representative.event.event_type,
            )
        )
    )
    if len(existing_event_ids) > 1:
        raise ClusterPersistenceConflict(
            "cluster documents already belong to different canonical events"
        )
    if existing_event_ids:
        event_id = existing_event_ids.pop()
        event = session.get(Event, event_id)
        if event is None:
            raise ClusterPersistenceConflict("linked canonical event no longer exists")
        return event, False

    source_ids = {documents[document_id].source_id for document_id in document_ids}
    event_data = representative.event
    start_at = event_data.occurred_at
    if start_at is None:
        representative_document = documents[representative.document_id]
        start_at = (
            representative_document.published_at
            or representative_document.fetched_at
        )
    location = event_data.location
    average_confidence = sum(
        member.event.confidence for member in cluster.members
    ) / len(cluster.members)
    corroboration_bonus = min(0.1, 0.025 * (len(source_ids) - 1))
    event = Event(
        event_type=event_data.event_type,
        title=event_data.title,
        summary=event_data.summary,
        status=(
            EventStatus.CONFIRMED
            if len(source_ids) > 1
            else EventStatus.PARTIALLY_CONFIRMED
        ),
        severity=_decimal_score(event_data.severity),
        novelty=Decimal("1.000"),
        confidence=_decimal_score(
            min(1.0, average_confidence + corroboration_bonus)
        ),
        start_at=start_at,
        latitude=(
            Decimal(str(location.latitude))
            if location is not None and location.latitude is not None
            else None
        ),
        longitude=(
            Decimal(str(location.longitude))
            if location is not None and location.longitude is not None
            else None
        ),
        country_code=location.country_code if location is not None else None,
    )
    session.add(event)
    session.flush()
    return event, True


def _cold_archive_review_candidates(
    *,
    preview: ClusterPreviewResponse,
    selected_cluster_ids: set[int],
    documents: dict[int, Document],
) -> list[int]:
    clusters_by_document: dict[int, set[int]] = {}
    for cluster in preview.clusters:
        for member in cluster.members:
            clusters_by_document.setdefault(member.document_id, set()).add(
                cluster.cluster_id
            )
    return sorted(
        document_id
        for document_id in preview.potential_duplicate_document_ids
        if clusters_by_document.get(document_id, set()) <= selected_cluster_ids
        and documents[document_id].raw_object_path is not None
    )


def _decimal_score(value: float) -> Decimal:
    return Decimal(f"{value:.3f}")
