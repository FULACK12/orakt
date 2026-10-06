"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.routes import router
from app.api.web import WEB_ROOT
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Configure process-wide services at application startup."""
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger(__name__)
    logger.info(
        "service_started",
        extra={
            "environment": settings.environment,
            "hot_data_root": str(settings.hot_data_root),
            "cold_data_root": str(settings.cold_data_root),
        },
    )
    yield
    logger.info("service_stopped")


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="API for geolocated, traceable global event intelligence.",
        lifespan=lifespan,
    )
    app.include_router(router)
    app.mount(
        "/review-assets",
        StaticFiles(directory=WEB_ROOT),
        name="review-assets",
    )
    return app


app = create_app()
