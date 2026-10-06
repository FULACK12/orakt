"""Create and inspect durable full-corpus clustering jobs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.db.enums import ClusterJobStatus
from app.db.models import ClusterJob, Document, EventDocument
from app.db.session import get_db_session
from app.schemas.cluster_jobs import (
    ClusterJobCreateRequest,
    ClusterJobListResponse,
    ClusterJobParameters,
    ClusterJobResponse,
    ClusterJobResult,
)

router = APIRouter(prefix="/cluster-jobs", tags=["cluster-jobs"])


@router.post(
    "",
    response_model=ClusterJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Queue a durable full-snapshot clustering job",
)
def create_cluster_job(
    request: ClusterJobCreateRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> ClusterJobResponse:
    """Snapshot document IDs so later collection cannot change job scope."""
    if request.document_ids is not None:
        document_ids = list(
            session.scalars(
                select(Document.id)
                .where(Document.id.in_(request.document_ids))
                .order_by(Document.id)
            )
        )
        missing_ids = sorted(set(request.document_ids) - set(document_ids))
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"missing_document_ids": missing_ids},
            )
    else:
        statement = select(Document.id).order_by(Document.id)
        if not request.include_linked_documents:
            statement = statement.where(
                ~exists().where(EventDocument.document_id == Document.id)
            )
        document_ids = list(session.scalars(statement))

    if len(document_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="at least two eligible documents are required",
        )
    parameters = ClusterJobParameters(
        document_ids=document_ids,
        batch_size=request.batch_size,
        merge_threshold=request.merge_threshold,
        time_window_hours=request.time_window_hours,
        location_radius_km=request.location_radius_km,
    )
    job = ClusterJob(
        status=ClusterJobStatus.QUEUED,
        total_documents=len(document_ids),
        processed_documents=0,
        batch_size=request.batch_size,
        parameters=parameters.model_dump(mode="json"),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return _job_response(job)


@router.get(
    "/{job_id}",
    response_model=ClusterJobResponse,
    summary="Inspect clustering job progress and result",
)
def get_cluster_job(
    job_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> ClusterJobResponse:
    job = session.get(ClusterJob, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="cluster job not found",
        )
    return _job_response(job)


@router.get(
    "",
    response_model=ClusterJobListResponse,
    summary="List recent clustering jobs",
)
def list_cluster_jobs(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ClusterJobListResponse:
    jobs = list(
        session.scalars(
            select(ClusterJob)
            .order_by(ClusterJob.created_at.desc(), ClusterJob.id.desc())
            .limit(limit)
        )
    )
    return ClusterJobListResponse(jobs=[_job_response(job) for job in jobs])


def _job_response(job: ClusterJob) -> ClusterJobResponse:
    return ClusterJobResponse(
        id=job.id,
        status=job.status,
        total_documents=job.total_documents,
        processed_documents=job.processed_documents,
        progress_percent=round(job.progress_percent, 2),
        progress_stage=job.progress_stage,
        progress_message=job.progress_message,
        heartbeat_at=job.heartbeat_at,
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
        parameters=ClusterJobParameters.model_validate(job.parameters),
        result=(
            ClusterJobResult.model_validate(job.result)
            if job.result is not None
            else None
        ),
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )
