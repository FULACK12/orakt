"""Configuration-driven construction of event extractors."""

from __future__ import annotations

import httpx

from app.core.config import Settings, get_settings
from app.extractors.base import EventExtractor
from app.extractors.llm import (
    FallbackEventExtractor,
    OllamaEventExtractor,
    OpenAICompatibleEventExtractor,
)
from app.extractors.mock import MockEventExtractor


def build_event_extractor(
    settings: Settings | None = None,
    *,
    transport: httpx.BaseTransport | None = None,
) -> EventExtractor:
    """Build the configured provider behind the common extraction protocol."""
    runtime = settings or get_settings()
    if runtime.llm_provider == "mock":
        return MockEventExtractor()

    if runtime.llm_provider == "ollama":
        primary: EventExtractor = OllamaEventExtractor(
            base_url=str(runtime.llm_base_url),
            model=runtime.llm_model,
            timeout_seconds=runtime.llm_timeout_seconds,
            max_attempts=runtime.llm_max_attempts,
            max_input_chars=runtime.llm_max_input_chars,
            transport=transport,
        )
    else:
        primary = OpenAICompatibleEventExtractor(
            provider_name=runtime.llm_provider,
            base_url=str(runtime.llm_base_url),
            model=runtime.llm_model,
            timeout_seconds=runtime.llm_timeout_seconds,
            max_attempts=runtime.llm_max_attempts,
            max_input_chars=runtime.llm_max_input_chars,
            transport=transport,
        )
    if runtime.llm_fallback_to_mock:
        return FallbackEventExtractor(primary, MockEventExtractor())
    return primary
