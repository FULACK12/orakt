"""Side-effect-free event clustering preview API."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.extractions import get_event_extractor
from app.cluster_review import verify_cluster_preview
from app.cluster_service import (
    MissingClusterDocumentsError,
    build_cluster_preview,
)
from app.core.config import get_settings
from app.db.session import get_db_session
from app.embeddings import (
    EmbeddingClient,
    EmbeddingError,
    build_embedding_client,
)
from app.event_persistence import (
    ClusterPersistenceConflict,
    persist_reviewed_clusters,
)
from app.extractors import EventExtractor, LocalLLMExtractionError
from app.schemas.clusters import (
    ClusterApplyRequest,
    ClusterApplyResponse,
    ClusterPreviewRequest,
    ClusterPreviewResponse,
)

router = APIRouter(tags=["clustering"])


@lru_cache
def get_embedding_client() -> EmbeddingClient:
    """Provide the embedding client aligned with runtime configuration."""
    return build_embedding_client()


@router.post(
    "/event-clusters/preview",
    response_model=ClusterPreviewResponse,
    summary="Preview explainable event deduplication without deleting data",
)
def preview_event_clusters(
    request: ClusterPreviewRequest,
    session: Annotated[Session, Depends(get_db_session)],
    extractor: Annotated[EventExtractor, Depends(get_event_extractor)],
    embedding_client: Annotated[
        EmbeddingClient,
        Depends(get_embedding_client),
    ],
) -> ClusterPreviewResponse:
    """Extract, embed and cluster stored documents without persisting changes."""
    try:
        return build_cluster_preview(
            session,
            request=request,
            extractor=extractor,
            embedding_client=embedding_client,
            review_secret=get_settings().cluster_review_secret,
        )
    except MissingClusterDocumentsError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"missing_document_ids": exc.document_ids},
        ) from exc
    except LocalLLMExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="local LLM failed during cluster preview",
        ) from exc
    except EmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="embedding provider failed during cluster preview",
        ) from exc


@router.post(
    "/event-clusters/apply",
    response_model=ClusterApplyResponse,
    summary="Persist explicitly reviewed and signed event clusters",
)
def apply_reviewed_event_clusters(
    request: ClusterApplyRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> ClusterApplyResponse:
    """Persist selected clusters only when the exact preview is still valid."""
    settings = get_settings()
    if not verify_cluster_preview(
        request.preview,
        settings.cluster_review_secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="cluster preview signature is invalid",
        )
    try:
        response = persist_reviewed_clusters(
            session,
            preview=request.preview,
            selected_cluster_ids=request.selected_cluster_ids,
        )
        session.commit()
        return response
    except ClusterPersistenceConflict as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
