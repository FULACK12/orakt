"""Measured time coverage and completeness for connected datasets."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.data_coverage import build_coverage_report
from app.db.session import get_db_session
from app.schemas.coverage import CoverageResponse

router = APIRouter(prefix="/coverage", tags=["data coverage"])


@router.get(
    "/status",
    response_model=CoverageResponse,
    summary="Audit retained time ranges and completeness by provider",
)
def coverage_status(
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CoverageResponse:
    """Report what is really stored, including explicit gaps and timestamps."""
    return build_coverage_report(session, settings=settings)
