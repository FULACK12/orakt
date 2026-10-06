"""Contracts for persistent full-corpus clustering jobs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.enums import ClusterJobStatus
from app.schemas.clusters import ClusterPreviewResponse


class ClusterJobCreateRequest(BaseModel):
    """Create a snapshot-backed clustering job."""

    model_config = ConfigDict(extra="forbid")

    document_ids: list[int] | None = Field(
        default=None,
        min_length=2,
        max_length=1_000,
    )
    include_linked_documents: bool = False
    batch_size: int = Field(default=10, ge=1, le=25)
    merge_threshold: float = Field(default=0.86, ge=0.5, le=1)
    time_window_hours: float = Field(default=48, ge=0.1, le=720)
    location_radius_km: float = Field(default=100, ge=1, le=5_000)

    @field_validator("document_ids")
    @classmethod
    def unique_positive_ids(
        cls,
        value: list[int] | None,
    ) -> list[int] | None:
        if value is None:
            return value
        if any(document_id <= 0 for document_id in value):
            raise ValueError("document_ids must be positive")
        if len(set(value)) != len(value):
            raise ValueError("document_ids must be unique")
        return value


class ClusterJobParameters(BaseModel):
    """Immutable parameters and document snapshot stored with a job."""

    model_config = ConfigDict(extra="forbid")

    document_ids: list[int] = Field(min_length=2, max_length=1_000)
    batch_size: int = Field(ge=1, le=25)
    merge_threshold: float = Field(ge=0.5, le=1)
    time_window_hours: float = Field(ge=0.1, le=720)
    location_radius_km: float = Field(ge=1, le=5_000)
    snapshot_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    extractor_name: str | None = Field(default=None, min_length=1, max_length=255)
    embedding_provider: str | None = Field(default=None, min_length=1, max_length=255)


class ClusterLogicGenerationState(BaseModel):
    """Auditable post-cluster logic-generation state retained with a job."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "failed"]
    attempt_count: int = Field(default=0, ge=0)
    attempted_at: datetime | None = None
    hypotheses: int = Field(default=0, ge=0)
    validated: int = Field(default=0, ge=0)
    error: str | None = None
    reconciled_existing: bool = False
    prompt_version: str | None = None


class ClusterJobResult(BaseModel):
    """Signed preview plus mutually exclusive review categories."""

    model_config = ConfigDict(extra="forbid")

    preview: ClusterPreviewResponse
    merge_cluster_ids: list[int]
    review_cluster_ids: list[int]
    independent_cluster_ids: list[int]
    logic_generation: ClusterLogicGenerationState | None = None


class ClusterJobResponse(BaseModel):
    """Observable lifecycle and result of one durable background job."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(gt=0)
    status: ClusterJobStatus
    total_documents: int = Field(ge=0)
    processed_documents: int = Field(ge=0)
    progress_percent: float = Field(ge=0, le=100)
    progress_stage: str
    progress_message: str | None
    heartbeat_at: datetime | None
    attempt_count: int = Field(ge=0)
    max_attempts: int = Field(ge=1)
    parameters: ClusterJobParameters
    result: ClusterJobResult | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ClusterJobListResponse(BaseModel):
    """Newest durable jobs."""

    model_config = ConfigDict(extra="forbid")

    jobs: list[ClusterJobResponse]
