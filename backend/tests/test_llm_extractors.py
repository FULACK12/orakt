"""Local-LLM provider adapter, retry and fallback tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.extractors.factory import build_event_extractor
from app.extractors.llm import (
    FallbackEventExtractor,
    LocalLLMExtractionError,
    OllamaEventExtractor,
    OpenAICompatibleEventExtractor,
)
from app.extractors.mock import MockEventExtractor
from app.schemas.extractions import DocumentExtractionInput


def document_input() -> DocumentExtractionInput:
    return DocumentExtractionInput(
        document_id=77,
        title="Government announces clean energy agreement",
        body="Ministers signed a clean energy agreement in Ottawa.",
        language="en",
        source_country="CA",
    )


def valid_model_json(*, start_char: int = 0, end_char: int = 10) -> str:
    return json.dumps(
        {
            "events": [
                {
                    "event_type": "energy_agreement",
                    "title": "Clean energy agreement announced",
                    "summary": "Ministers signed a clean energy agreement.",
                    "entities": [
                        {
                            "name": "Ministers",
                            "entity_type": "person",
                            "confidence": 0.7,
                        }
                    ],
                    "location": {
                        "name": "Ottawa",
                        "country_code": "CA",
                        "latitude": None,
                        "longitude": None,
                        "confidence": 0.8,
                    },
                    "occurred_at": None,
                    "severity": 0.3,
                    "confidence": 0.85,
                    "evidence_spans": [
                        {
                            "field": "event_type",
                            "source_field": "title",
                            "start_char": start_char,
                            "end_char": end_char,
                            "quote": "Government announces clean energy agreement",
                        }
                    ],
                }
            ]
        }
    )


def ollama_extractor(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    max_attempts: int = 1,
) -> OllamaEventExtractor:
    return OllamaEventExtractor(
        base_url="http://ollama.test:11434",
        model="qwen-test",
        timeout_seconds=3,
        max_attempts=max_attempts,
        max_input_chars=8_000,
        transport=httpx.MockTransport(handler),
    )


def test_ollama_uses_json_schema_and_grounds_evidence_offsets() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        assert request.url.path == "/api/chat"
        return httpx.Response(
            200,
            json={"message": {"content": valid_model_json(start_char=50, end_char=60)}},
        )

    result = ollama_extractor(handler).extract(document_input())

    assert captured["model"] == "qwen-test"
    assert captured["stream"] is False
    assert captured["think"] is False
    assert captured["format"]["additionalProperties"] is False
    assert '"pattern"' not in json.dumps(captured["format"])
    user_source = json.loads(captured["messages"][1]["content"])
    assert user_source["evidence_anchor"]["quote"] == document_input().title
    assert result.extractor == "ollama:qwen-test+repair-v1"
    span = result.events[0].evidence_spans[0]
    assert span.start_char == 0
    assert span.end_char == len(document_input().title)


def test_ollama_retries_after_invalid_model_json() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        content = (
            "not JSON" if calls == 1 else valid_model_json(end_char=len(document_input().title))
        )
        return httpx.Response(200, json={"message": {"content": content}})

    result = ollama_extractor(handler, max_attempts=2).extract(document_input())

    assert calls == 2
    assert result.events[0].event_type == "energy_agreement"


def test_ollama_repairs_wrapped_schema_defects_without_retry() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        content = """```json
        {
          "events": [{
            "event_type": "Energy Agreement!",
            "title": "",
            "summary": null,
            "entities": [{
              "name": "Ministers",
              "entity_type": "cabinet",
              "confidence": 4
            }],
            "location": {
              "name": "Ottawa",
              "country_code": "can",
              "latitude": 45.42,
              "confidence": -1
            },
            "occurred_at": "not-a-date",
            "severity": 5,
            "confidence": -2,
            "evidence_spans": [{
              "field": "summary",
              "source_field": "body",
              "start_char": 999,
              "end_char": 1005,
              "quote": "clean energy agreement"
            }]
          }],
        }
        ```"""
        return httpx.Response(200, json={"message": {"content": content}})

    result = ollama_extractor(handler, max_attempts=2).extract(document_input())

    assert calls == 1
    assert result.extractor == "ollama:qwen-test+repair-v1"
    event = result.events[0]
    assert event.event_type == "energy_agreement"
    assert event.title == document_input().title
    assert event.summary == document_input().title
    assert event.entities[0].entity_type == "other"
    assert event.entities[0].confidence == 1
    assert event.location is not None
    assert event.location.country_code is None
    assert event.location.latitude is None
    assert event.location.longitude is None
    assert event.occurred_at is None
    assert event.severity == 1
    assert event.confidence == 0
    assert event.evidence_spans[0].quote == document_input().title
    assert event.evidence_spans[1].quote == "clean energy agreement"
    assert event.evidence_spans[1].start_char == 19


def test_ollama_drops_ungrounded_impact_without_fallback() -> None:
    payload = json.loads(valid_model_json(end_char=len(document_input().title)))
    event = payload["events"][0]
    event["impact"] = {
        "fatalities_low": 2,
        "fatalities_best": 2,
        "fatalities_high": 2,
        "injured_low": None,
        "injured_high": None,
        "displaced_low": None,
        "displaced_high": None,
        "economic_loss_low": None,
        "economic_loss_high": None,
        "economic_loss_currency": None,
        "confidence": 0.7,
    }
    event["evidence_spans"].append(
        {
            "field": "impact",
            "source_field": "body",
            "start_char": 0,
            "end_char": 21,
            "quote": "two people were killed",
        }
    )

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"message": {"content": json.dumps(payload)}},
        )

    result = ollama_extractor(handler).extract(document_input())

    assert result.extractor == "ollama:qwen-test+repair-v1"
    assert result.events[0].impact is None
    assert not any(span.field == "impact" for span in result.events[0].evidence_spans)


def test_failed_ollama_activates_deterministic_fallback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    extractor = FallbackEventExtractor(
        ollama_extractor(handler),
        MockEventExtractor(),
    )

    result = extractor.extract(document_input())

    assert result.extractor == "mock-v1"
    assert result.events[0].event_type == "official_announcement"


def test_openai_compatible_adapter_supports_vllm_json_schema() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": valid_model_json(end_char=len(document_input().title))}}
                ]
            },
        )

    extractor = OpenAICompatibleEventExtractor(
        provider_name="vllm",
        base_url="http://vllm.test:8000",
        model="local-model",
        timeout_seconds=3,
        max_attempts=1,
        max_input_chars=8_000,
        transport=httpx.MockTransport(handler),
    )

    result = extractor.extract(document_input())

    assert captured["response_format"]["type"] == "json_schema"
    assert captured["response_format"]["json_schema"]["strict"] is True
    assert result.extractor == "vllm:local-model"


def test_factory_can_disable_fallback_and_surface_provider_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    settings = Settings(
        llm_provider="llama_cpp",
        llm_base_url="http://llama.test:8080",
        llm_model="gguf-model",
        llm_max_attempts=1,
        llm_fallback_to_mock=False,
    )
    extractor = build_event_extractor(
        settings,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LocalLLMExtractionError):
        extractor.extract(document_input())


def test_factory_mock_mode_makes_no_provider_calls() -> None:
    settings = Settings(llm_provider="mock")

    extractor = build_event_extractor(settings)

    assert isinstance(extractor, MockEventExtractor)
