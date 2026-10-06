"""Validated embedding clients used by event clustering."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.core.config import Settings, get_settings

TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


class EmbeddingError(RuntimeError):
    """The configured embedding provider exhausted its valid attempts."""


class EmbeddingProviderUnavailableError(EmbeddingError):
    """The embedding runtime cannot currently be reached."""


class EmbeddingClient(Protocol):
    """Provider-neutral batch embedding interface."""

    @property
    def name(self) -> str:
        """Stable provider and model identifier."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one validated vector per input text."""
        ...


class OllamaEmbeddingResponse(BaseModel):
    """Validated subset of an Ollama `/api/embed` response."""

    model_config = ConfigDict(extra="ignore")

    embeddings: list[list[float]] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_matrix(self) -> OllamaEmbeddingResponse:
        _validate_matrix(self.embeddings)
        return self


class OpenAIEmbeddingDatum(BaseModel):
    """One indexed vector from an OpenAI-compatible embedding response."""

    model_config = ConfigDict(extra="ignore")

    index: int = Field(ge=0)
    embedding: list[float] = Field(min_length=1)


class OpenAIEmbeddingResponse(BaseModel):
    """Validated subset of an OpenAI-compatible embedding response."""

    model_config = ConfigDict(extra="ignore")

    data: list[OpenAIEmbeddingDatum] = Field(min_length=1)


def _validate_matrix(matrix: list[list[float]]) -> None:
    dimensions = {len(vector) for vector in matrix}
    if dimensions == {0} or len(dimensions) != 1:
        raise ValueError("embedding vectors must have one non-zero dimension")
    if any(not math.isfinite(value) for vector in matrix for value in vector):
        raise ValueError("embedding vectors must contain only finite values")


class BaseHTTPEmbeddingClient:
    """Shared batch request, retry and count validation."""

    endpoint_path: str
    provider_name: str

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_attempts: int,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._transport = transport

    @property
    def name(self) -> str:
        return f"{self.provider_name}:{self._model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        last_error: Exception | None = None
        for _ in range(self._max_attempts):
            try:
                vectors = self._embed_once(texts)
                if len(vectors) != len(texts):
                    raise ValueError("embedding count does not match input count")
                _validate_matrix(vectors)
                return vectors
            except (httpx.HTTPError, ValidationError, ValueError) as exc:
                last_error = exc
        detail = (
            f": {type(last_error).__name__}: {str(last_error)[:240]}"
            if last_error is not None
            else ""
        )
        error_type = (
            EmbeddingProviderUnavailableError
            if isinstance(
                last_error,
                (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError),
            )
            else EmbeddingError
        )
        raise error_type(
            f"{self.name} failed after {self._max_attempts} attempt(s){detail}"
        ) from last_error

    def _embed_once(self, texts: list[str]) -> list[list[float]]:
        with httpx.Client(
            base_url=self._base_url,
            timeout=self._timeout_seconds,
            transport=self._transport,
        ) as client:
            response = client.post(
                self.endpoint_path,
                json=self._request_payload(texts),
            )
            response.raise_for_status()
        return self._response_vectors(response)

    def _request_payload(self, texts: list[str]) -> dict[str, object]:
        raise NotImplementedError

    def _response_vectors(self, response: httpx.Response) -> list[list[float]]:
        raise NotImplementedError


class OllamaEmbeddingClient(BaseHTTPEmbeddingClient):
    """Ollama native batch embedding adapter."""

    endpoint_path = "/api/embed"
    provider_name = "ollama"

    def _request_payload(self, texts: list[str]) -> dict[str, object]:
        return {
            "model": self._model,
            "input": texts,
            "truncate": True,
        }

    def _response_vectors(self, response: httpx.Response) -> list[list[float]]:
        parsed = OllamaEmbeddingResponse.model_validate(response.json())
        return parsed.embeddings


class OpenAICompatibleEmbeddingClient(BaseHTTPEmbeddingClient):
    """Embedding adapter shared by llama.cpp and vLLM servers."""

    endpoint_path = "/v1/embeddings"

    def __init__(
        self,
        *,
        provider_name: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_attempts: int,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if provider_name not in {"llama_cpp", "vllm"}:
            raise ValueError("provider_name must be llama_cpp or vllm")
        self.provider_name = provider_name
        super().__init__(
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            transport=transport,
        )

    def _request_payload(self, texts: list[str]) -> dict[str, object]:
        return {"model": self._model, "input": texts}

    def _response_vectors(self, response: httpx.Response) -> list[list[float]]:
        parsed = OpenAIEmbeddingResponse.model_validate(response.json())
        ordered = sorted(parsed.data, key=lambda item: item.index)
        return [item.embedding for item in ordered]


class HashEmbeddingClient:
    """Small deterministic offline embedding used only with mock extraction."""

    name = "hash-embedding-v1"

    def __init__(self, dimensions: int = 64) -> None:
        self._dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self._dimensions
            for token in TOKEN_PATTERN.findall(text.casefold()):
                digest = hashlib.blake2b(
                    token.encode("utf-8"),
                    digest_size=8,
                ).digest()
                number = int.from_bytes(digest)
                index = number % self._dimensions
                vector[index] += -1.0 if number & 1 else 1.0
            norm = math.sqrt(sum(value * value for value in vector))
            vectors.append(
                [value / norm for value in vector]
                if norm
                else [0.0] * self._dimensions
            )
        return vectors


def build_embedding_client(
    settings: Settings | None = None,
    *,
    transport: httpx.BaseTransport | None = None,
) -> EmbeddingClient:
    """Build the embedding implementation aligned with the LLM provider."""
    runtime = settings or get_settings()
    if runtime.llm_provider == "mock":
        return HashEmbeddingClient()
    if runtime.llm_provider == "ollama":
        return OllamaEmbeddingClient(
            base_url=str(runtime.llm_base_url),
            model=runtime.embedding_model,
            timeout_seconds=runtime.llm_timeout_seconds,
            max_attempts=runtime.llm_max_attempts,
            transport=transport,
        )
    return OpenAICompatibleEmbeddingClient(
        provider_name=runtime.llm_provider,
        base_url=str(runtime.llm_base_url),
        model=runtime.embedding_model,
        timeout_seconds=runtime.llm_timeout_seconds,
        max_attempts=runtime.llm_max_attempts,
        transport=transport,
    )
