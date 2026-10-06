"""Search and inspect locally archived EIA energy series."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.energy.service import (
    get_energy_series_detail,
    list_dataset_status,
    search_energy_series,
)
from app.schemas.energy import (
    EnergyDatasetStatus,
    EnergySeriesDetail,
    EnergySeriesSummary,
)

router = APIRouter(prefix="/energy", tags=["energy"])


@router.get("/status", response_model=list[EnergyDatasetStatus])
def energy_status(
    session: Annotated[Session, Depends(get_db_session)],
) -> list[EnergyDatasetStatus]:
    """Show archive sizes, row counts and import health by EIA dataset."""
    return list_dataset_status(session)


@router.get("/series", response_model=list[EnergySeriesSummary])
def energy_series(
    session: Annotated[Session, Depends(get_db_session)],
    dataset: str | None = None,
    q: str | None = None,
    materialized: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[EnergySeriesSummary]:
    """Search all archived series metadata or only materialized series."""
    return search_energy_series(
        session,
        dataset=dataset,
        query=q,
        materialized=materialized,
        limit=limit,
    )


@router.get("/series/{series_id}", response_model=EnergySeriesDetail)
def energy_series_detail(
    series_id: str,
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=2, le=2_500)] = 240,
) -> EnergySeriesDetail:
    """Return values plus a transparent trend/anomaly signal."""
    detail = get_energy_series_detail(
        session,
        series_id=series_id,
        limit=limit,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="energy series not found")
    return detail
