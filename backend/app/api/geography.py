"""Zoom-aware administrative areas and regional statistics endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.geography.service import (
    AdministrativeAreaNotFoundError,
    get_area_detail,
    list_areas,
)
from app.schemas.geography import (
    AdministrativeAreaDetailResponse,
    AdministrativeAreaListResponse,
)

router = APIRouter(prefix="/geography", tags=["geography"])


@router.get(
    "/areas",
    response_model=AdministrativeAreaListResponse,
    summary="List subdivisions or cities for one country map layer",
)
def get_areas(
    session: Annotated[Session, Depends(get_db_session)],
    country_iso2: Annotated[str, Query(min_length=2, max_length=2)],
    level: Annotated[Literal["admin1", "admin2", "city"], Query()] = "admin1",
    parent_id: Annotated[int | None, Query(ge=1)] = None,
    minimum_population: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=2_000)] = 500,
) -> AdministrativeAreaListResponse:
    """Return a bounded layer with explicit point-precision metadata."""
    if not country_iso2.isalpha():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="country_iso2 must be a two-letter country code",
        )
    return list_areas(
        session,
        country_iso2=country_iso2,
        level=level,
        parent_id=parent_id,
        minimum_population=minimum_population,
        limit=limit,
    )


@router.get(
    "/areas/{area_id}",
    response_model=AdministrativeAreaDetailResponse,
    summary="Show one subnational area and its latest statistics",
)
def area_detail(
    area_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> AdministrativeAreaDetailResponse:
    """Return source-labelled statistics without mixing provider definitions."""
    try:
        return get_area_detail(session, area_id=area_id)
    except AdministrativeAreaNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"administrative area not found: {exc}",
        ) from exc

