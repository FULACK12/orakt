"""Interactive map data endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.map_service import MapDataConflictError, build_map_data
from app.schemas.map_data import MapDataResponse

router = APIRouter(tags=["map"])


@router.get(
    "/map-data",
    response_model=MapDataResponse,
    summary="List canonical and AI-candidate map markers",
)
def get_map_data(
    session: Annotated[Session, Depends(get_db_session)],
) -> MapDataResponse:
    """Return clearly separated persisted and non-persisted map layers."""
    try:
        return build_map_data(
            session,
            review_secret=get_settings().cluster_review_secret,
        )
    except MapDataConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
