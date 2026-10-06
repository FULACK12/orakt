"""Build and apply the human review queue for durable cluster jobs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.cluster_review import sign_cluster_preview, verify_cluster_preview
from app.db.enums import ClusterJobStatus, ClusterReviewDecision
from app.db.models import (
    ClusterJob,
    ClusterReviewDecisionRecord,
    Document,
)
from app.event_persistence import persist_reviewed_clusters
from app.schemas.cluster_jobs import ClusterJobResult
from app.schemas.cluster_reviews import (
    ClusterReviewCandidate,
    ClusterReviewDecisionRequest,
    ClusterReviewDecisionResponse,
    ClusterReviewDecisionView,
    ClusterReviewDocument,
    ClusterReviewItem,
    ClusterReviewQueueResponse,
    ClusterReviewSummary,
)
from app.schemas.clusters import (
    ClusterCandidate,
    ClusterPreviewResponse,
    EventClusterPreview,
    PairEvaluation,
)


class ClusterReviewUnavailableError(RuntimeError):
    """A job has no completed, signed review result."""


class ClusterReviewItemNotFoundError(LookupError):
    """The requested review key is not present in the job snapshot."""


class ClusterReviewConflictError(RuntimeError):
    """A requested decision conflicts with an already-applied merge."""


@dataclass(frozen=True)
class ReviewContext:
    """Validated job result plus candidate lookup maps."""

    job: ClusterJob
    result: ClusterJobResult
    pairs_by_key: dict[str, PairEvaluation]
    clusters_by_candidate: dict[str, EventClusterPreview]


def make_review_key(left_candidate_id: str, right_candidate_id: str) -> str:
    """Return a stable, order-independent key for one candidate pair."""
    left, right = sorted((left_candidate_id, right_candidate_id))
    return hashlib.sha256(f"{left}\0{right}".encode()).hexdigest()


def build_review_queue(
    session: Session,
    *,
    job_id: int,
    review_secret: str,
) -> ClusterReviewQueueResponse:
    """Return enriched near-match pairs and their latest decisions."""
    context = _load_context(
        session,
        job_id=job_id,
        review_secret=review_secret,
    )
    latest_decisions = _latest_decisions(session, job_id)
    candidate_ids = {
        candidate_id
        for pair in context.result.preview.rejected_near_matches
        for candidate_id in (
            pair.left_candidate_id,
            pair.right_candidate_id,
        )
    }
    candidates = {
        member.candidate_id: member
        for cluster in context.result.preview.clusters
        for member in cluster.members
        if member.candidate_id in candidate_ids
    }
    document_ids = {candidate.document_id for candidate in candidates.values()}
    documents = list(
        session.scalars(
            select(Document)
            .where(Document.id.in_(document_ids))
            .options(selectinload(Document.source))
        )
    )
    documents_by_id = {document.id: document for document in documents}
    if document_ids != set(documents_by_id):
        raise ClusterReviewConflictError(
            "one or more reviewed source documents no longer exist"
        )

    items = [
        _build_review_item(
            pair=pair,
            context=context,
            candidates=candidates,
            documents=documents_by_id,
            decision=latest_decisions.get(
                make_review_key(
                    pair.left_candidate_id,
                    pair.right_candidate_id,
                )
            ),
        )
        for pair in sorted(
            context.result.preview.rejected_near_matches,
            key=lambda item: item.score,
            reverse=True,
        )
    ]
    decisions = [
        item.decision.decision
        for item in items
        if item.decision is not None
    ]
    return ClusterReviewQueueResponse(
        job_id=context.job.id,
        job_status=context.job.status,
        completed_at=context.job.completed_at,
        summary=ClusterReviewSummary(
            total=len(items),
            pending=sum(item.decision is None for item in items),
            merged=decisions.count(ClusterReviewDecision.MERGE),
            independent=decisions.count(ClusterReviewDecision.INDEPENDENT),
            ignored=decisions.count(ClusterReviewDecision.IGNORED),
        ),
        items=items,
    )


def apply_review_decision(
    session: Session,
    *,
    job_id: int,
    review_key: str,
    request: ClusterReviewDecisionRequest,
    review_secret: str,
) -> ClusterReviewDecisionResponse:
    """Apply a review decision and append an audit record."""
    context = _load_context(
        session,
        job_id=job_id,
        review_secret=review_secret,
        lock=True,
    )
    pair = context.pairs_by_key.get(review_key)
    if pair is None:
        raise ClusterReviewItemNotFoundError(review_key)
    latest = _latest_decisions(session, job_id).get(review_key)
    if latest is not None:
        if latest.decision is ClusterReviewDecision.MERGE and (
            request.decision is not ClusterReviewDecision.MERGE
        ):
            raise ClusterReviewConflictError(
                "an applied merge cannot be changed from this review screen"
            )
        if latest.decision is request.decision and latest.note == request.note:
            return ClusterReviewDecisionResponse(
                review_key=review_key,
                decision=_decision_view(latest),
                created_event_count=0,
                linked_document_count=0,
            )

    created_event_count = 0
    linked_document_count = 0
    applied_event_ids: list[int] = []
    if request.decision is ClusterReviewDecision.MERGE:
        preview = _manual_merge_preview(
            context.result.preview,
            pair,
            review_secret,
        )
        applied = persist_reviewed_clusters(
            session,
            preview=preview,
            selected_cluster_ids=[1],
        )
        created_event_count = applied.created_event_count
        linked_document_count = applied.linked_document_count
        applied_event_ids = [
            item.event_id for item in applied.applied_clusters
        ]
    elif request.decision is ClusterReviewDecision.INDEPENDENT:
        cluster_ids = sorted(
            {
                context.clusters_by_candidate[pair.left_candidate_id].cluster_id,
                context.clusters_by_candidate[pair.right_candidate_id].cluster_id,
            }
        )
        applied = persist_reviewed_clusters(
            session,
            preview=context.result.preview,
            selected_cluster_ids=cluster_ids,
        )
        created_event_count = applied.created_event_count
        linked_document_count = applied.linked_document_count
        applied_event_ids = [
            item.event_id for item in applied.applied_clusters
        ]

    record = ClusterReviewDecisionRecord(
        cluster_job_id=job_id,
        review_key=review_key,
        left_candidate_id=pair.left_candidate_id,
        right_candidate_id=pair.right_candidate_id,
        decision=request.decision,
        note=request.note,
        applied_event_ids=applied_event_ids,
        result_metadata={
            "created_event_count": created_event_count,
            "linked_document_count": linked_document_count,
            "deletions_performed": False,
        },
    )
    session.add(record)
    session.flush()
    return ClusterReviewDecisionResponse(
        review_key=review_key,
        decision=_decision_view(record),
        created_event_count=created_event_count,
        linked_document_count=linked_document_count,
    )


def _load_context(
    session: Session,
    *,
    job_id: int,
    review_secret: str,
    lock: bool = False,
) -> ReviewContext:
    statement = select(ClusterJob).where(ClusterJob.id == job_id)
    if lock:
        statement = statement.with_for_update()
    job = session.scalar(statement)
    if job is None:
        raise ClusterReviewItemNotFoundError(f"cluster job {job_id}")
    if job.status is not ClusterJobStatus.COMPLETED or job.result is None:
        raise ClusterReviewUnavailableError(
            "cluster review is available only for a completed job"
        )
    result = ClusterJobResult.model_validate(job.result)
    if not verify_cluster_preview(result.preview, review_secret):
        raise ClusterReviewConflictError(
            "stored cluster preview signature is invalid"
        )
    clusters_by_candidate = {
        member.candidate_id: cluster
        for cluster in result.preview.clusters
        for member in cluster.members
    }
    pairs_by_key = {
        make_review_key(pair.left_candidate_id, pair.right_candidate_id): pair
        for pair in result.preview.rejected_near_matches
    }
    return ReviewContext(
        job=job,
        result=result,
        pairs_by_key=pairs_by_key,
        clusters_by_candidate=clusters_by_candidate,
    )


def _latest_decisions(
    session: Session,
    job_id: int,
) -> dict[str, ClusterReviewDecisionRecord]:
    records = list(
        session.scalars(
            select(ClusterReviewDecisionRecord)
            .where(ClusterReviewDecisionRecord.cluster_job_id == job_id)
            .order_by(
                ClusterReviewDecisionRecord.created_at.desc(),
                ClusterReviewDecisionRecord.id.desc(),
            )
        )
    )
    latest: dict[str, ClusterReviewDecisionRecord] = {}
    for record in records:
        latest.setdefault(record.review_key, record)
    return latest


def _build_review_item(
    *,
    pair: PairEvaluation,
    context: ReviewContext,
    candidates: dict[str, ClusterCandidate],
    documents: dict[int, Document],
    decision: ClusterReviewDecisionRecord | None,
) -> ClusterReviewItem:
    left = candidates[pair.left_candidate_id]
    right = candidates[pair.right_candidate_id]
    return ClusterReviewItem(
        review_key=make_review_key(
            pair.left_candidate_id,
            pair.right_candidate_id,
        ),
        left=_review_candidate(
            context.clusters_by_candidate[pair.left_candidate_id].cluster_id,
            left,
            documents[left.document_id],
        ),
        right=_review_candidate(
            context.clusters_by_candidate[pair.right_candidate_id].cluster_id,
            right,
            documents[right.document_id],
        ),
        score=pair.score,
        signals=pair.signals,
        blocker=pair.blocker,
        reasons=pair.reasons,
        decision=_decision_view(decision) if decision is not None else None,
    )


def _review_candidate(
    cluster_id: int,
    candidate: ClusterCandidate,
    document: Document,
) -> ClusterReviewCandidate:
    return ClusterReviewCandidate(
        cluster_id=cluster_id,
        candidate=candidate,
        document=ClusterReviewDocument(
            document_id=document.id,
            title=document.title,
            url=document.url,
            source_name=document.source.name,
            source_country=document.source.country,
            language=document.language,
            published_at=document.published_at,
            raw_object_path=document.raw_object_path,
        ),
    )


def _decision_view(
    record: ClusterReviewDecisionRecord,
) -> ClusterReviewDecisionView:
    return ClusterReviewDecisionView(
        id=record.id,
        decision=record.decision,
        note=record.note,
        applied_event_ids=record.applied_event_ids,
        created_at=record.created_at,
    )


def _manual_merge_preview(
    source: ClusterPreviewResponse,
    pair: PairEvaluation,
    review_secret: str,
) -> ClusterPreviewResponse:
    candidates = {
        member.candidate_id: member
        for cluster in source.clusters
        for member in cluster.members
    }
    left = candidates[pair.left_candidate_id]
    right = candidates[pair.right_candidate_id]
    document_ids = sorted({left.document_id, right.document_id})
    preview = ClusterPreviewResponse(
        embedding_provider=source.embedding_provider,
        requested_document_ids=document_ids,
        document_fingerprints=[
            fingerprint
            for fingerprint in source.document_fingerprints
            if fingerprint.document_id in document_ids
        ],
        candidate_count=2,
        clusters=[
            EventClusterPreview(
                cluster_id=1,
                representative_candidate_id=left.candidate_id,
                members=[left, right],
            )
        ],
        merge_edges=[
            pair.model_copy(
                update={
                    "merged": True,
                    "blocker": None,
                    "reasons": [
                        *pair.reasons,
                        "human reviewer confirmed merge",
                    ],
                }
            )
        ],
        rejected_near_matches=[],
        potential_duplicate_document_ids=(
            [right.document_id]
            if right.document_id != left.document_id
            else []
        ),
        review_signature="0" * 64,
    )
    return sign_cluster_preview(preview, review_secret)
