"""On-demand, performance-bounded conflict indicator API."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.conflicts.service import get_conflict_indicator
from app.db.session import get_db_session
from app.schemas.conflicts import ConflictIndicatorResponse

router = APIRouter(prefix="/conflicts", tags=["conflicts"])


@router.get("/indicator", response_model=ConflictIndicatorResponse)
def conflict_indicator(
    session: Annotated[Session, Depends(get_db_session)],
    weeks: Annotated[int, Query(ge=1, le=2_000)] = 12,
    west: Annotated[float, Query(ge=-180, le=180)] = -180,
    south: Annotated[float, Query(ge=-90, le=90)] = -90,
    east: Annotated[float, Query(ge=-180, le=180)] = 180,
    north: Annotated[float, Query(ge=-90, le=90)] = 90,
    zoom: Annotated[float, Query(ge=0, le=22)] = 2,
    limit: Annotated[int, Query(ge=1, le=1_200)] = 1_200,
) -> ConflictIndicatorResponse:
    """Load a current conflict footprint only when the map layer is enabled."""
    return get_conflict_indicator(
        session,
        weeks=weeks,
        west=west,
        south=south,
        east=east,
        north=north,
        zoom=zoom,
        limit=limit,
    )
