"""Local task-console API and safe cancellation endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.tasks import (
    ResearchCheckpointResponse,
    TaskCancelRequest,
    TaskCancelResponse,
    TaskConsoleResponse,
    TaskKind,
)
from app.task_controls import (
    TaskConfirmationError,
    TaskNotCancellableError,
    TaskNotFoundError,
    build_task_console,
    request_task_cancellation,
    research_checkpoint_response,
    task_from_console,
)

router = APIRouter(prefix="/operations/tasks", tags=["operations"])


@router.get("", response_model=TaskConsoleResponse)
def task_console(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=10, le=300)] = 120,
) -> TaskConsoleResponse:
    """Return a two-second polling snapshot for local operators."""
    return build_task_console(session, limit=limit)


@router.get(
    "/research_batch_item/{item_id}/checkpoints",
    response_model=ResearchCheckpointResponse,
)
def research_checkpoints(
    item_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> ResearchCheckpointResponse:
    """Return compact report checkpoints without transferring the full evidence pack."""
    try:
        return research_checkpoint_response(session, item_id=item_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail="research task not found") from exc


@router.post(
    "/{task_kind}/{task_id}/cancel",
    response_model=TaskCancelResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def cancel_task(
    task_kind: TaskKind,
    task_id: int,
    cancellation: TaskCancelRequest,
    http_request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> TaskCancelResponse:
    """Request cooperative cancellation without killing shared services."""
    if http_request.url.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise HTTPException(
            status_code=403,
            detail="task cancellation is available only from the local console",
        )
    try:
        accepted, safe_checkpoint = request_task_cancellation(
            session,
            task_kind=task_kind,
            task_id=task_id,
            confirmation=cancellation.confirmation,
        )
        console = build_task_console(session)
        task = task_from_console(console, task_kind=task_kind, task_id=task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc
    except TaskConfirmationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TaskNotCancellableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return TaskCancelResponse(
        accepted=accepted,
        safe_checkpoint=safe_checkpoint,
        task=task,
    )
