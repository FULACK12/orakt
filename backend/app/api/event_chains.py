"""Generate, inspect and decide reviewable event-chain suggestions."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.event_chains import (
    EventChainJobNotFoundError,
    EventRelationNotFoundError,
    decide_relation,
    generate_event_chain,
    list_event_chain,
)
from app.schemas.event_chains import (
    EventChainGenerationResponse,
    EventChainResponse,
    EventRelationDecisionRequest,
)

router = APIRouter(prefix="/event-chains", tags=["event-chains"])


@router.post(
    "/{job_id}/generate",
    response_model=EventChainGenerationResponse,
    summary="Generate conservative event-chain suggestions",
)
def generate_chain(
    job_id: int,
    session: Annotated[Session, Depends(get_db_session)],
    max_relations: Annotated[int, Query(ge=1, le=2_000)] = 500,
) -> EventChainGenerationResponse:
    """Create review suggestions while leaving causal status unconfirmed."""
    try:
        response = generate_event_chain(
            session,
            job_id=job_id,
            max_relations=max_relations,
        )
        session.commit()
        return response
    except EventChainJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"completed cluster job not found: {exc}",
        ) from exc


@router.get(
    "/{job_id}",
    response_model=EventChainResponse,
    summary="List reviewable event-chain suggestions",
)
def get_chain(
    job_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> EventChainResponse:
    """Return candidate edges with a mandatory unconfirmed-causality flag."""
    try:
        return list_event_chain(session, job_id=job_id)
    except EventChainJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"completed cluster job not found: {exc}",
        ) from exc


@router.patch(
    "/relations/{relation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Accept or reject one event relation suggestion",
)
def set_relation_decision(
    relation_id: int,
    request: EventRelationDecisionRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> None:
    """Persist an explicit human review decision."""
    try:
        decide_relation(
            session,
            relation_id=relation_id,
            decision=request.status,
            pinned=request.pinned,
            review_note=request.review_note,
        )
        session.commit()
    except EventRelationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"event relation not found: {exc}",
        ) from exc
