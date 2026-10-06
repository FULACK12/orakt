"""Strict persisted shapes for local-AI analysis caching."""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CachedEmbeddingBatch(BaseModel):
    """Finite embedding vectors stored for one document's event list."""

    model_config = ConfigDict(extra="forbid")

    vectors: list[list[float]] = Field(default_factory=list)

    @model_validator(mode="after")
    def vectors_are_finite_and_rectangular(self) -> CachedEmbeddingBatch:
        if not self.vectors:
            return self
        dimensions = {len(vector) for vector in self.vectors}
        if dimensions == {0} or len(dimensions) != 1:
            raise ValueError("cached embeddings must be rectangular")
        if any(
            not math.isfinite(value)
            for vector in self.vectors
            for value in vector
        ):
            raise ValueError("cached embeddings must be finite")
        return self
