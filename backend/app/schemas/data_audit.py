"""Contracts for deterministic evidence completion and market-data audits."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.coverage import DatasetCoverage


class SeriesQualityView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: str
    name: str
    category: str
    source_name: str
    unit: str | None = None
    frequency: str | None = None
    window_start: date
    window_end: date
    first_observed_on: date | None = None
    last_observed_on: date | None = None
    observation_count: int = Field(ge=0)
    expected_observations: int = Field(ge=0)
    coverage_ratio: float = Field(ge=0, le=1)
    invalid_value_count: int = Field(ge=0)
    zero_value_count: int = Field(ge=0)
    unique_value_count: int = Field(ge=0)
    maximum_absolute_change_ratio: float | None = Field(default=None, ge=0)
    quality_score: float = Field(ge=0, le=1)
    can_verify_claims: bool
    flags: list[str] = Field(max_length=20)


class BridgeEvidenceCandidateView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: str
    name: str
    relevance_score: float = Field(ge=0)
    evidence_refs: list[str] = Field(max_length=12)
    quality: SeriesQualityView


class BridgeEvidenceSegmentView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_index: int = Field(ge=1)
    sequence: int = Field(ge=1, le=8)
    source: str
    target: str
    search_terms: list[str] = Field(max_length=24)
    status: Literal[
        "candidate_data_found",
        "partial_data",
        "missing_data",
        "rejected_anomaly",
    ]
    candidates: list[BridgeEvidenceCandidateView] = Field(max_length=6)
    missing_data: list[str] = Field(max_length=12)


class EvidenceCompletionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    window_start: date
    window_end: date
    segment_count: int = Field(ge=0)
    candidate_data_segments: int = Field(ge=0)
    rejected_anomaly_segments: int = Field(ge=0)
    missing_segments: int = Field(ge=0)
    added_evidence_refs: list[str] = Field(max_length=200)
    segments: list[BridgeEvidenceSegmentView] = Field(max_length=32)


class EquityLeaderView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market: Literal["CN", "US"]
    symbol: str
    name: str
    sector: str
    rank: int = Field(ge=1, le=100)
    ranking_metric: str
    ranking_value: float | None = None
    price_series_id: str
    price_start: date | None = None
    price_end: date | None = None
    observation_count: int = Field(ge=0)
    quality_score: float = Field(ge=0, le=1)
    flags: list[str] = Field(max_length=20)


class FullTextBacklogView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline_only_count: int = Field(ge=0)
    never_attempted_count: int = Field(ge=0)
    retryable_now_count: int = Field(ge=0)
    scheduled_retry_count: int = Field(ge=0)
    permanent_block_count: int = Field(ge=0)
    completed_expansion_count: int = Field(ge=0)
    by_collector: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)


class DataAuditReportView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    status: Literal["healthy", "warning", "critical"]
    market_series_count: int = Field(ge=0)
    market_observation_count: int = Field(ge=0)
    company_count: int = Field(ge=0)
    company_price_coverage: float = Field(ge=0, le=1)
    china_leader_count: int = Field(ge=0)
    us_equity_count: int = Field(ge=0)
    suspicious_series_count: int = Field(ge=0)
    unusable_series_count: int = Field(ge=0)
    abnormal_series: list[SeriesQualityView] = Field(max_length=200)
    china_sector_leaders: dict[str, list[EquityLeaderView]]
    us_sector_equities: dict[str, list[EquityLeaderView]]
    latest_evidence_completion: EvidenceCompletionView | None = None
    fulltext_backlog: FullTextBacklogView
    dataset_coverage: list[DatasetCoverage] = Field(default_factory=list)
    source_coverage: list[DatasetCoverage] = Field(default_factory=list)
    provider_findings: list[str] = Field(max_length=30)
    report_findings: list[str] = Field(max_length=50)
    archive_path: str | None = None
    archive_status: Literal["stored", "not_configured", "write_failed"]
