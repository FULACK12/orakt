"""Conservative event-chain suggestions with an explicit human decision gate."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import ClusterJobStatus
from app.db.models import ClusterJob, Document, EventRelationCandidate
from app.schemas.cluster_jobs import ClusterJobResult
from app.schemas.clusters import ClusterCandidate
from app.schemas.event_chains import (
    EventChainGenerationResponse,
    EventChainResponse,
    EventRelationStatus,
    EventRelationType,
    EventRelationView,
)

_FOLLOW_UP_CUES = (
    "in response to",
    "following the",
    "following an",
    "after the",
    "as a result of",
    "because of",
    "responded to",
    "回应",
    "作为回应",
    "在此之后",
    "由于",
    " בעקבות ",
)


class EventChainJobNotFoundError(LookupError):
    """Raised when the immutable clustering snapshot is unavailable."""


class EventRelationNotFoundError(LookupError):
    """Raised when a proposed relation does not exist."""


def generate_event_chain(
    session: Session,
    *,
    job_id: int,
    max_relations: int = 500,
) -> EventChainGenerationResponse:
    """Suggest time-ordered links without asserting unreported causality."""
    job, result = _validated_job(session, job_id)
    document_ids = {
        member.document_id
        for cluster in result.preview.clusters
        for member in cluster.members
    }
    document_times = {
        document.id: document.published_at or document.fetched_at
        for document in session.scalars(
            select(Document).where(Document.id.in_(document_ids))
        )
    }
    candidates = [
        _TimedCandidate(
            candidate=representative,
            occurred_at=(
                representative.event.occurred_at
                or document_times[representative.document_id]
            ),
        )
        for cluster in result.preview.clusters
        if (
            representative := next(
                (
                    member
                    for member in cluster.members
                    if member.candidate_id
                    == cluster.representative_candidate_id
                ),
                cluster.members[0],
            )
        ).document_id
        in document_times
    ]
    candidates.sort(key=lambda item: item.occurred_at)

    existing = {
        (
            relation.source_candidate_id,
            relation.target_candidate_id,
            relation.relation_type,
        ): relation
        for relation in session.scalars(
            select(EventRelationCandidate).where(
                EventRelationCandidate.cluster_job_id == job_id
            )
        )
    }
    candidate_document_ids = {
        candidate.candidate.candidate_id: candidate.candidate.document_id
        for candidate in candidates
    }
    now = datetime.now(UTC)
    for existing_relation in existing.values():
        source_document_id = candidate_document_ids.get(
            existing_relation.source_candidate_id
        )
        target_document_id = candidate_document_ids.get(
            existing_relation.target_candidate_id
        )
        if (
            existing_relation.status == "suggested"
            and source_document_id is not None
            and source_document_id == target_document_id
        ):
            existing_relation.status = "rejected"
            existing_relation.pinned = False
            existing_relation.review_note = (
                "Automatically rejected: both candidates came from the same "
                "source document, so this is not an independent evidence link."
            )
            existing_relation.decided_at = now
    generated_count = 0
    edge_count = 0
    for source_index, source in enumerate(candidates):
        for target in candidates[source_index + 1 : source_index + 7]:
            gap = target.occurred_at - source.occurred_at
            if gap > timedelta(days=14):
                break
            if source.candidate.document_id == target.candidate.document_id:
                continue
            relationship = _relationship(source, target)
            if relationship is None:
                continue
            relation_type, confidence, rationale = relationship
            key = (
                source.candidate.candidate_id,
                target.candidate.candidate_id,
                relation_type,
            )
            relation = existing.get(key)
            if relation is None:
                relation = EventRelationCandidate(
                    cluster_job_id=job.id,
                    source_candidate_id=source.candidate.candidate_id,
                    target_candidate_id=target.candidate.candidate_id,
                    relation_type=relation_type,
                    status="suggested",
                )
                session.add(relation)
                existing[key] = relation
                generated_count += 1
            relation.confidence = confidence
            relation.rationale = rationale
            relation.evidence_document_ids = json.dumps(
                sorted(
                    {
                        source.candidate.document_id,
                        target.candidate.document_id,
                    }
                )
            )
            edge_count += 1
            if edge_count >= max_relations:
                break
        if edge_count >= max_relations:
            break
    session.flush()
    response = list_event_chain(session, job_id=job_id)
    return EventChainGenerationResponse(
        **response.model_dump(),
        generated_count=generated_count,
    )


def list_event_chain(
    session: Session,
    *,
    job_id: int,
) -> EventChainResponse:
    """Return proposed edges and the candidate titles they connect."""
    _, result = _validated_job(session, job_id)
    candidates = {
        member.candidate_id: member
        for cluster in result.preview.clusters
        for member in cluster.members
    }
    document_ids = {candidate.document_id for candidate in candidates.values()}
    document_times = {
        document.id: document.published_at or document.fetched_at
        for document in session.scalars(
            select(Document).where(Document.id.in_(document_ids))
        )
    }
    relations = list(
        session.scalars(
            select(EventRelationCandidate)
            .where(EventRelationCandidate.cluster_job_id == job_id)
            .order_by(
                EventRelationCandidate.confidence.desc(),
                EventRelationCandidate.id,
            )
        )
    )
    views = [
        _relation_view(
            relation,
            source=candidates[relation.source_candidate_id],
            target=candidates[relation.target_candidate_id],
            document_times=document_times,
        )
        for relation in relations
        if relation.source_candidate_id in candidates
        and relation.target_candidate_id in candidates
    ]
    return EventChainResponse(
        cluster_job_id=job_id,
        relation_count=len(views),
        fixed_relation_count=sum(view.pinned for view in views),
        relations=views,
    )


def decide_relation(
    session: Session,
    *,
    relation_id: int,
    decision: str,
    pinned: bool = False,
    review_note: str | None = None,
) -> EventRelationCandidate:
    """Store an explicit human accept/reject decision."""
    relation = session.get(EventRelationCandidate, relation_id)
    if relation is None:
        raise EventRelationNotFoundError(str(relation_id))
    relation.status = decision
    relation.pinned = pinned
    relation.review_note = review_note.strip() if review_note else None
    relation.decided_at = datetime.now(UTC)
    session.flush()
    return relation


class _TimedCandidate:
    def __init__(
        self,
        *,
        candidate: ClusterCandidate,
        occurred_at: datetime,
    ) -> None:
        self.candidate = candidate
        self.occurred_at = (
            occurred_at.replace(tzinfo=UTC)
            if occurred_at.tzinfo is None
            else occurred_at.astimezone(UTC)
        )


def _relationship(
    source: _TimedCandidate,
    target: _TimedCandidate,
) -> tuple[str, float, str] | None:
    source_event = source.candidate.event
    target_event = target.candidate.event
    source_entities = {
        entity.name.casefold()
        for entity in source_event.entities
        if len(entity.name.strip()) >= 3
    }
    target_entities = {
        entity.name.casefold()
        for entity in target_event.entities
        if len(entity.name.strip()) >= 3
    }
    shared_entities = sorted(source_entities & target_entities)
    source_location = source_event.location
    target_location = target_event.location
    same_country = bool(
        source_location
        and target_location
        and source_location.country_code
        and source_location.country_code == target_location.country_code
    )
    same_named_location = bool(
        source_location
        and target_location
        and source_location.name.casefold() == target_location.name.casefold()
    )
    if not same_named_location and not (
        same_country and shared_entities
    ) and len(shared_entities) < 2:
        return None

    target_text = f"{target_event.title} {target_event.summary}".casefold()
    has_reported_cue = any(cue.casefold() in target_text for cue in _FOLLOW_UP_CUES)
    relation_type = (
        "reported_follow_up" if has_reported_cue else "temporal_follow_up"
    )
    confidence = 0.44
    reasons = ["time ordered within 14 days"]
    if same_country:
        confidence += 0.12
        reasons.append("same country")
    if same_named_location:
        confidence += 0.12
        reasons.append("same named location")
    if shared_entities:
        confidence += min(0.14, 0.07 * len(shared_entities))
        reasons.append(f"{len(shared_entities)} shared named entity/entities")
    if source_event.event_type == target_event.event_type:
        confidence += 0.05
        reasons.append("same event type")
    if has_reported_cue:
        confidence += 0.08
        reasons.append("target text contains a follow-up cue")
    confidence = min(confidence, 0.85)
    disclaimer = (
        "This is a review suggestion, not a confirmed causal claim."
    )
    return relation_type, confidence, f"{'; '.join(reasons)}. {disclaimer}"


def _validated_job(
    session: Session,
    job_id: int,
) -> tuple[ClusterJob, ClusterJobResult]:
    job = session.get(ClusterJob, job_id)
    if (
        job is None
        or job.status not in {ClusterJobStatus.RUNNING, ClusterJobStatus.COMPLETED}
        or job.result is None
    ):
        raise EventChainJobNotFoundError(str(job_id))
    return job, ClusterJobResult.model_validate(job.result)


def _relation_view(
    relation: EventRelationCandidate,
    *,
    source: ClusterCandidate,
    target: ClusterCandidate,
    document_times: dict[int, datetime],
) -> EventRelationView:
    return EventRelationView(
        id=relation.id,
        cluster_job_id=relation.cluster_job_id,
        source_candidate_id=relation.source_candidate_id,
        source_title=source.event.title,
        source_occurred_at=(
            source.event.occurred_at or document_times[source.document_id]
        ),
        target_candidate_id=relation.target_candidate_id,
        target_title=target.event.title,
        target_occurred_at=(
            target.event.occurred_at or document_times[target.document_id]
        ),
        relation_type=cast(EventRelationType, relation.relation_type),
        confidence=float(relation.confidence),
        rationale=relation.rationale,
        evidence_document_ids=json.loads(relation.evidence_document_ids),
        status=cast(EventRelationStatus, relation.status),
        pinned=relation.pinned,
        review_note=relation.review_note,
        decided_at=relation.decided_at,
    )
