"""Top-level HTTP routes."""

from datetime import UTC, datetime

from fastapi import APIRouter

from app import __version__
from app.api.cluster_jobs import router as cluster_jobs_router
from app.api.cluster_reviews import router as cluster_reviews_router
from app.api.clusters import router as clusters_router
from app.api.companies import router as companies_router
from app.api.conflicts import router as conflicts_router
from app.api.coverage import router as coverage_router
from app.api.economics import router as economics_router
from app.api.energy import router as energy_router
from app.api.event_chains import router as event_chains_router
from app.api.events import router as events_router
from app.api.extractions import router as extractions_router
from app.api.geography import router as geography_router
from app.api.integrations import router as integrations_router
from app.api.logic_chains import router as logic_chains_router
from app.api.map_data import router as map_data_router
from app.api.markets import router as markets_router
from app.api.pipeline import router as pipeline_router
from app.api.provenance import router as provenance_router
from app.api.research import router as research_router
from app.api.tasks import router as tasks_router
from app.api.web import router as web_router
from app.core.config import get_settings
from app.schemas.health import HealthResponse

router = APIRouter()
router.include_router(cluster_jobs_router)
router.include_router(companies_router)
router.include_router(cluster_reviews_router)
router.include_router(conflicts_router)
router.include_router(coverage_router)
router.include_router(clusters_router)
router.include_router(events_router)
router.include_router(event_chains_router)
router.include_router(economics_router)
router.include_router(energy_router)
router.include_router(extractions_router)
router.include_router(geography_router)
router.include_router(integrations_router)
router.include_router(logic_chains_router)
router.include_router(map_data_router)
router.include_router(markets_router)
router.include_router(pipeline_router)
router.include_router(provenance_router)
router.include_router(research_router)
router.include_router(tasks_router)
router.include_router(web_router)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service liveness check",
    tags=["operations"],
)
async def health() -> HealthResponse:
    """Return process liveness without depending on external services."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=__version__,
        environment=settings.environment,
        timestamp=datetime.now(UTC),
    )
