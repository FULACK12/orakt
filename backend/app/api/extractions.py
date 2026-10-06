"""Document event-extraction API."""

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Document
from app.db.session import get_db_session
from app.extractors import (
    EventExtractor,
    LocalLLMExtractionError,
    build_event_extractor,
)
from app.schemas.extractions import DocumentExtractionInput, EventExtractionResult

router = APIRouter(tags=["extractions"])


@lru_cache
def get_event_extractor() -> EventExtractor:
    """Provide the current extractor implementation."""
    return build_event_extractor()


@router.post(
    "/documents/{document_id}/extract",
    response_model=EventExtractionResult,
    summary="Extract validated event candidates from a document",
)
def extract_document(
    document_id: int,
    session: Annotated[Session, Depends(get_db_session)],
    extractor: Annotated[EventExtractor, Depends(get_event_extractor)],
) -> EventExtractionResult:
    """Run the configured side-effect-free extractor for one stored document."""
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )
    extraction_input = DocumentExtractionInput(
        document_id=document.id,
        title=document.title,
        body=document.body or "",
        published_at=document.published_at,
        language=document.language,
        source_country=document.source.country,
    )
    try:
        return extractor.extract(extraction_input)
    except LocalLLMExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="local LLM failed to return a valid event extraction",
        ) from exc
