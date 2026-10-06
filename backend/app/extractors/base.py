"""Extractor interface shared by mock and future local-LLM adapters."""

from typing import Protocol

from app.schemas.extractions import DocumentExtractionInput, EventExtractionResult


class EventExtractor(Protocol):
    """Structural interface for a validated event extractor."""

    @property
    def name(self) -> str:
        """Stable identifier for the concrete extractor."""
        ...

    def extract(self, document: DocumentExtractionInput) -> EventExtractionResult:
        """Return Pydantic-validated candidates for one document."""
        ...
