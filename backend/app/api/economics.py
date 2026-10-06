"""Official economic indicator catalog, map and collector status endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.economics.service import (
    EconomicCountryNotFoundError,
    EconomicIndicatorNotFoundError,
    build_country_detail,
    build_economic_map,
    build_economic_rankings,
    get_sync_status,
    list_indicators,
)
from app.schemas.economics import (
    EconomicCountryDetailResponse,
    EconomicIndicatorListResponse,
    EconomicMapResponse,
    EconomicRankingResponse,
    EconomicSyncStatusView,
)

router = APIRouter(prefix="/economics", tags=["economics"])


@router.get(
    "/indicators",
    response_model=EconomicIndicatorListResponse,
    summary="List supported official economic indicators",
)
def get_indicators(
    session: Annotated[Session, Depends(get_db_session)],
) -> EconomicIndicatorListResponse:
    """Return bilingual indicator metadata and source/license provenance."""
    return list_indicators(session)


@router.get(
    "/map",
    response_model=EconomicMapResponse,
    summary="Map one economic indicator for a comparable year",
)
def get_economic_map(
    session: Annotated[Session, Depends(get_db_session)],
    indicator_code: Annotated[
        str,
        Query(min_length=1, max_length=64),
    ] = "FP.CPI.TOTL.ZG",
    year: Annotated[int | None, Query(ge=1960, le=2100)] = None,
) -> EconomicMapResponse:
    """Return country values located at capital reference coordinates."""
    try:
        return build_economic_map(
            session,
            indicator_code=indicator_code,
            year=year,
        )
    except EconomicIndicatorNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"economic indicator not found: {exc}",
        ) from exc


@router.get(
    "/countries/{iso2}",
    response_model=EconomicCountryDetailResponse,
    summary="Show one country's latest official economic values",
)
def get_country_detail(
    iso2: str,
    session: Annotated[Session, Depends(get_db_session)],
) -> EconomicCountryDetailResponse:
    """Return the country panel used by polygon and marker clicks."""
    if len(iso2) != 2 or not iso2.isalpha():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="iso2 must be a two-letter country code",
        )
    try:
        return build_country_detail(session, iso2=iso2)
    except EconomicCountryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"economic country not found: {exc}",
        ) from exc


@router.get(
    "/status",
    response_model=EconomicSyncStatusView | None,
    summary="Show official economic collector status",
)
def economic_status(
    session: Annotated[Session, Depends(get_db_session)],
) -> EconomicSyncStatusView | None:
    """Return backfill years, row count and last provider error."""
    return get_sync_status(session)


@router.get(
    "/rankings",
    response_model=EconomicRankingResponse,
    summary="Rank countries with transparent operator-adjustable weights",
)
def get_economic_rankings(
    session: Annotated[Session, Depends(get_db_session)],
    year: Annotated[int | None, Query(ge=1960, le=2100)] = None,
    country_iso2: Annotated[
        str | None,
        Query(min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$"),
    ] = None,
    weight: Annotated[list[str] | None, Query()] = None,
    top_limit: Annotated[int, Query(ge=5, le=100)] = 20,
) -> EconomicRankingResponse:
    """Return a reproducible composite plus every component world rank."""
    overrides: dict[str, float] = {}
    for item in weight or []:
        code, separator, raw_value = item.rpartition(":")
        if not separator:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="weight values must use INDICATOR_CODE:number",
            )
        try:
            value = float(raw_value)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"invalid weight value: {item}",
            ) from exc
        if not 0 <= value <= 100:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"weight must be between 0 and 100: {item}",
            )
        overrides[code] = value
    try:
        return build_economic_rankings(
            session,
            year=year,
            weight_overrides=overrides,
            country_iso2=country_iso2,
            top_limit=top_limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
