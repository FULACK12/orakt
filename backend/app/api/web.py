"""Local operator web pages."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(include_in_schema=False)
WEB_ROOT = Path(__file__).resolve().parents[1] / "web"


@router.get("/provenance-console", response_class=FileResponse)
def provenance_page() -> FileResponse:
    """Local devnet operator panel; publication API independently requires authorization."""
    return FileResponse(WEB_ROOT / "provenance.html")


@router.get("/review", response_class=FileResponse)
def cluster_review_page() -> FileResponse:
    """Serve the local clustering review console."""
    return FileResponse(WEB_ROOT / "review.html")


@router.get("/map", response_class=FileResponse)
def event_map_page() -> FileResponse:
    """Serve the bilingual local event map."""
    return FileResponse(WEB_ROOT / "map.html")


@router.get("/research", response_class=FileResponse)
def ai_research_page() -> FileResponse:
    """Serve the local AI research and causal-audit workspace."""
    return FileResponse(WEB_ROOT / "research.html")


@router.get("/tasks", response_class=FileResponse)
def task_console_page() -> FileResponse:
    """Serve the local real-time task and cancellation console."""
    return FileResponse(WEB_ROOT / "tasks.html")
