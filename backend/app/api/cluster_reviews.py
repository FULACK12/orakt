"""Human-review endpoints for completed durable clustering jobs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.cluster_review_service import (
    ClusterReviewConflictError,
    ClusterReviewItemNotFoundError,
    ClusterReviewUnavailableError,
    apply_review_decision,
    build_review_queue,
)
from app.core.config import get_settings
from app.db.session import get_db_session
from app.event_persistence import ClusterPersistenceConflict
from app.schemas.cluster_reviews import (
    ClusterReviewDecisionRequest,
    ClusterReviewDecisionResponse,
    ClusterReviewQueueResponse,
)

router = APIRouter(prefix="/cluster-jobs", tags=["cluster-reviews"])


@router.get(
    "/{job_id}/review",
    response_model=ClusterReviewQueueResponse,
    summary="List enriched rejected near matches awaiting review",
)
def get_cluster_review_queue(
    job_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> ClusterReviewQueueResponse:
    """Return pair comparisons with source metadata and saved decisions."""
    try:
        return build_review_queue(
            session,
            job_id=job_id,
            review_secret=get_settings().cluster_review_secret,
        )
    except ClusterReviewItemNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="cluster job not found",
        ) from exc
    except ClusterReviewUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ClusterReviewConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/{job_id}/review/{review_key}",
    response_model=ClusterReviewDecisionResponse,
    summary="Persist one explicit review decision",
)
def decide_cluster_review_item(
    job_id: int,
    review_key: str,
    request: ClusterReviewDecisionRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> ClusterReviewDecisionResponse:
    """Apply a merge/independent decision or record an ignored pair."""
    try:
        response = apply_review_decision(
            session,
            job_id=job_id,
            review_key=review_key,
            request=request,
            review_secret=get_settings().cluster_review_secret,
        )
        session.commit()
        return response
    except ClusterReviewItemNotFoundError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="review item not found",
        ) from exc
    except (
        ClusterReviewUnavailableError,
        ClusterReviewConflictError,
        ClusterPersistenceConflict,
    ) as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
