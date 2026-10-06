"""Automatic clustering-job creation for newly collected documents."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import and_, case, exists, or_, select
from sqlalchemy.orm import Session

from app.db.enums import ClusterJobStatus
from app.db.models import (
    ClusterJob,
    Document,
    DocumentAnalysis,
    EventDocument,
)
from app.queue_locks import CLUSTER_QUEUE_LOCK_ID, acquire_queue_transaction_lock
from app.schemas.cluster_jobs import ClusterJobParameters

MAX_JOB_DOCUMENTS = 1_000
COMPARISON_CONTEXT_DOCUMENTS = 100


def ensure_incremental_cluster_job(
    session: Session,
    *,
    batch_size: int = 10,
    extractor_name: str | None = None,
    embedding_provider: str | None = None,
) -> int | None:
    """Queue one snapshot when unprocessed documents exist and no job is active."""
    # RSS, GDELT and full-text services can all reach this function at nearly
    # the same time. A row lock cannot protect the empty-active-queue case, so
    # use one transaction advisory lock around the whole check-and-create path.
    acquire_queue_transaction_lock(session, CLUSTER_QUEUE_LOCK_ID)
    active_job_id = session.scalar(
        select(ClusterJob.id)
        .where(ClusterJob.status.in_([ClusterJobStatus.QUEUED, ClusterJobStatus.RUNNING]))
        .order_by(ClusterJob.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if active_job_id is not None:
        return None

    pending_conditions = [
        DocumentAnalysis.document_id.is_(None),
        DocumentAnalysis.content_hash != Document.content_hash,
        DocumentAnalysis.last_cluster_job_id.is_(None),
    ]
    if extractor_name is not None:
        pending_conditions.append(DocumentAnalysis.extractor_name != extractor_name)
    if embedding_provider is not None:
        pending_conditions.append(DocumentAnalysis.embedding_provider != embedding_provider)
    linked_to_event = exists().where(EventDocument.document_id == Document.id)
    fulltext_complete = Document.raw_metadata["full_text_status"].as_string() == "complete"
    pending_document_ids = list(
        session.scalars(
            select(Document.id)
            .outerjoin(
                DocumentAnalysis,
                DocumentAnalysis.document_id == Document.id,
            )
            .where(
                or_(
                    and_(~linked_to_event, or_(*pending_conditions)),
                    and_(linked_to_event, fulltext_complete, or_(*pending_conditions)),
                )
            )
            .order_by(
                case(
                    (and_(linked_to_event, fulltext_complete), 0),
                    else_=1,
                ),
                Document.published_at.desc().nulls_last(),
                Document.id.desc(),
            )
            .limit(MAX_JOB_DOCUMENTS)
        )
    )
    if not pending_document_ids:
        return None

    all_eligible_document_ids = list(
        session.scalars(
            select(Document.id)
            .where(~exists().where(EventDocument.document_id == Document.id))
            .order_by(
                Document.published_at.desc().nulls_last(),
                Document.id.desc(),
            )
            .limit(MAX_JOB_DOCUMENTS + 1)
        )
    )
    if len(all_eligible_document_ids) <= MAX_JOB_DOCUMENTS:
        pending_set = set(pending_document_ids)
        document_ids = (
            pending_document_ids
            + [
                document_id
                for document_id in all_eligible_document_ids
                if document_id not in pending_set
            ]
        )[:MAX_JOB_DOCUMENTS]
    else:
        context_limit = min(
            COMPARISON_CONTEXT_DOCUMENTS,
            MAX_JOB_DOCUMENTS - len(pending_document_ids),
        )
        comparison_document_ids = list(
            session.scalars(
                select(Document.id)
                .join(
                    DocumentAnalysis,
                    DocumentAnalysis.document_id == Document.id,
                )
                .where(
                    ~exists().where(EventDocument.document_id == Document.id),
                    Document.id.not_in(pending_document_ids),
                    DocumentAnalysis.content_hash == Document.content_hash,
                    DocumentAnalysis.last_cluster_job_id.is_not(None),
                    *(
                        [DocumentAnalysis.extractor_name == extractor_name]
                        if extractor_name is not None
                        else []
                    ),
                    *(
                        [DocumentAnalysis.embedding_provider == embedding_provider]
                        if embedding_provider is not None
                        else []
                    ),
                )
                .order_by(
                    Document.published_at.desc().nulls_last(),
                    Document.id.desc(),
                )
                .limit(context_limit)
            )
        )
        document_ids = pending_document_ids + comparison_document_ids
    if len(document_ids) < 2:
        return None

    snapshot_fingerprint = _snapshot_fingerprint(
        session,
        document_ids=document_ids,
        extractor_name=extractor_name,
        embedding_provider=embedding_provider,
        batch_size=batch_size,
    )
    parameters = ClusterJobParameters(
        document_ids=document_ids,
        batch_size=batch_size,
        merge_threshold=0.86,
        time_window_hours=48,
        location_radius_km=100,
        snapshot_fingerprint=snapshot_fingerprint,
        extractor_name=extractor_name,
        embedding_provider=embedding_provider,
    )
    serialized_parameters = parameters.model_dump(mode="json")
    previous = next(
        (
            job
            for job in session.scalars(
                select(ClusterJob).order_by(ClusterJob.id.desc()).limit(100)
            )
            if isinstance(job.parameters, dict)
            and job.parameters.get("snapshot_fingerprint") == snapshot_fingerprint
        ),
        None,
    )
    if previous is not None:
        if previous.status in {
            ClusterJobStatus.QUEUED,
            ClusterJobStatus.RUNNING,
            ClusterJobStatus.COMPLETED,
        }:
            return None
        if previous.progress_stage == "cancelled" or (
            previous.error_message == "cancelled_by_local_operator_at_safe_checkpoint"
        ):
            return None
        if previous.attempt_count >= previous.max_attempts:
            return None
        previous.status = ClusterJobStatus.QUEUED
        previous.started_at = None
        previous.completed_at = None
        previous.progress_stage = "retrying_same_snapshot"
        previous.progress_message = (
            "复用相同新闻快照继续重试, 不创建重复任务记录"
        )
        previous.heartbeat_at = datetime.now(UTC)
        previous.parameters = serialized_parameters
        session.flush()
        return previous.id
    job = ClusterJob(
        status=ClusterJobStatus.QUEUED,
        total_documents=len(document_ids),
        processed_documents=0,
        batch_size=batch_size,
        parameters=serialized_parameters,
    )
    session.add(job)
    session.flush()
    return job.id


def _snapshot_fingerprint(
    session: Session,
    *,
    document_ids: list[int],
    extractor_name: str | None,
    embedding_provider: str | None,
    batch_size: int,
) -> str:
    """Hash the exact retained contents and model versions, not just row IDs."""
    hashes = {
        document_id: content_hash
        for document_id, content_hash in session.execute(
            select(Document.id, Document.content_hash).where(Document.id.in_(document_ids))
        )
    }
    payload = {
        "documents": [
            [document_id, hashes.get(document_id)] for document_id in document_ids
        ],
        "extractor_name": extractor_name,
        "embedding_provider": embedding_provider,
        "batch_size": batch_size,
        "merge_threshold": 0.86,
        "time_window_hours": 48,
        "location_radius_km": 100,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
