"""Operational contracts for collection and local-AI pipeline status."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PipelineFeedStatus(BaseModel):
    """One configured feed and its latest collection state."""

    model_config = ConfigDict(extra="forbid")

    source_name: str
    country: str | None
    language: str | None
    url: str
    enabled: bool
    license_name: str
    last_fetched_at: datetime | None
    last_success_at: datetime | None
    consecutive_failures: int = Field(ge=0)
    last_error: str | None


class PipelineSourceStatus(BaseModel):
    """One configured publisher and its current stored-document count."""

    model_config = ConfigDict(extra="forbid")

    source_name: str
    country: str | None
    language: str | None
    source_type: str
    ownership: str | None
    credibility_baseline: float = Field(ge=0, le=1)
    document_count: int = Field(ge=0)
    total_feeds: int = Field(ge=0)
    enabled_feeds: int = Field(ge=0)


class PipelineStatusResponse(BaseModel):
    """Live ingestion, archive and local-AI processing summary."""

    model_config = ConfigDict(extra="forbid")

    total_documents: int = Field(ge=0)
    cold_archived_documents: int = Field(ge=0)
    linked_documents: int = Field(ge=0)
    analyzed_documents: int = Field(ge=0)
    pending_analysis_documents: int = Field(ge=0)
    analysis_extractor: str
    embedding_provider: str
    active_cluster_jobs: int = Field(ge=0)
    latest_completed_job_id: int | None = Field(default=None, gt=0)
    configured_sources: int = Field(ge=0)
    configured_countries: list[str]
    global_sources: int = Field(ge=0)
    enabled_feeds: int = Field(ge=0)
    healthy_feeds: int = Field(ge=0)
    pending_feeds: int = Field(ge=0)
    failing_feeds: int = Field(ge=0)
    sources: list[PipelineSourceStatus]
    feeds: list[PipelineFeedStatus]
