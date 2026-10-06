"""Embedding provider validation and ordering tests."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.embeddings import (
    EmbeddingError,
    EmbeddingProviderUnavailableError,
    OllamaEmbeddingClient,
    OpenAICompatibleEmbeddingClient,
)


def test_ollama_embedding_client_validates_one_vector_per_text() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        assert request.url.path == "/api/embed"
        return httpx.Response(
            200,
            json={"embeddings": [[1.0, 0.0], [0.0, 1.0]]},
        )

    client = OllamaEmbeddingClient(
        base_url="http://ollama.test:11434",
        model="embedding-test",
        timeout_seconds=3,
        max_attempts=1,
        transport=httpx.MockTransport(handler),
    )

    vectors = client.embed(["first", "second"])

    assert captured["input"] == ["first", "second"]
    assert captured["truncate"] is True
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
    assert client.name == "ollama:embedding-test"


def test_openai_compatible_embeddings_are_sorted_by_index() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ]
            },
        )

    client = OpenAICompatibleEmbeddingClient(
        provider_name="vllm",
        base_url="http://vllm.test:8000",
        model="embedding-test",
        timeout_seconds=3,
        max_attempts=1,
        transport=httpx.MockTransport(handler),
    )

    assert client.embed(["first", "second"]) == [[1.0, 0.0], [0.0, 1.0]]


def test_embedding_count_mismatch_exhausts_retries() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"embeddings": [[1.0, 0.0]]})

    client = OllamaEmbeddingClient(
        base_url="http://ollama.test:11434",
        model="embedding-test",
        timeout_seconds=3,
        max_attempts=2,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(EmbeddingError):
        client.embed(["first", "second"])

    assert calls == 2


def test_offline_embedding_runtime_has_typed_retryable_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("runtime offline", request=request)

    client = OllamaEmbeddingClient(
        base_url="http://ollama.test:11434",
        model="embedding-test",
        timeout_seconds=3,
        max_attempts=2,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(EmbeddingProviderUnavailableError, match="runtime offline"):
        client.embed(["first"])
