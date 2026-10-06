"""Pluggable document-to-event extractors."""

from app.extractors.base import EventExtractor
from app.extractors.factory import build_event_extractor
from app.extractors.llm import (
    FallbackEventExtractor,
    LocalLLMExtractionError,
    OllamaEventExtractor,
    OpenAICompatibleEventExtractor,
)
from app.extractors.mock import MockEventExtractor

__all__ = [
    "EventExtractor",
    "FallbackEventExtractor",
    "LocalLLMExtractionError",
    "MockEventExtractor",
    "OllamaEventExtractor",
    "OpenAICompatibleEventExtractor",
    "build_event_extractor",
]
