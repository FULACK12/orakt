"""Auditable time coverage for connected data sources."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CoverageStatus = Literal["complete", "partial", "stale", "missing"]
CoverageCategory = Literal["news", "market", "economics", "energy", "conflict"]


class DatasetCoverage(BaseModel):
    """One provider or feed with explicit temporal and quality boundaries."""

    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    provider: str
    category: CoverageCategory
    starts_at: str | None = None
    ends_at: str | None = None
    record_count: int = Field(default=0, ge=0)
    distinct_periods: int | None = Field(default=None, ge=0)
    expected_periods: int | None = Field(default=None, ge=0)
    completeness_ratio: float | None = Field(default=None, ge=0, le=1)
    timestamp_ratio: float | None = Field(default=None, ge=0, le=1)
    content_ratio: float | None = Field(default=None, ge=0, le=1)
    headline_only_count: int | None = Field(default=None, ge=0)
    last_success_at: datetime | None = None
    status: CoverageStatus
    notes: list[str] = Field(default_factory=list)


class CoverageResponse(BaseModel):
    """Coverage report used by both the UI and local research agents."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    target_starts_at: str
    target_ends_at: str
    datasets: list[DatasetCoverage]
    sources: list[DatasetCoverage]
