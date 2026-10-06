"""Validated public contracts for official economic map data."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EconomicIndicatorView(BaseModel):
    """Bilingual metadata for one selectable economic series."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    code: str
    name_en: str
    name_zh: str
    unit: str
    description_en: str
    description_zh: str
    frequency: str
    source_name: str
    source_url: str
    license_name: str
    license_url: str


class EconomicIndicatorListResponse(BaseModel):
    """All economic indicators enabled for the map."""

    model_config = ConfigDict(extra="forbid")

    indicators: list[EconomicIndicatorView]


class EconomicCountryPoint(BaseModel):
    """One country value positioned at its capital reference coordinate."""

    model_config = ConfigDict(extra="forbid")

    iso2: str = Field(min_length=2, max_length=2)
    iso3: str = Field(min_length=3, max_length=3)
    country_name: str
    region: str
    capital_city: str | None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    year: int = Field(ge=1960, le=2100)
    value: float


class EconomicMapResponse(BaseModel):
    """One comparable annual indicator layer for the country map."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    indicator: EconomicIndicatorView
    selected_year: int | None
    available_years: list[int]
    country_count: int = Field(ge=0)
    points: list[EconomicCountryPoint]


class EconomicCountryMetric(BaseModel):
    """Latest available value for one indicator within a country panel."""

    model_config = ConfigDict(extra="forbid")

    indicator: EconomicIndicatorView
    year: int = Field(ge=1960, le=2100)
    value: float


class EconomicCountryDetailResponse(BaseModel):
    """Country identity and latest official values for the map drawer."""

    model_config = ConfigDict(extra="forbid")

    iso2: str = Field(min_length=2, max_length=2)
    iso3: str = Field(min_length=3, max_length=3)
    country_name: str
    region: str
    income_level: str | None
    capital_city: str | None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    metrics: list[EconomicCountryMetric]


class EconomicSyncStatusView(BaseModel):
    """Operator-visible status for the official economic collector."""

    model_config = ConfigDict(extra="forbid")

    source_key: str
    last_started_at: datetime | None
    last_success_at: datetime | None
    history_start_year: int | None
    history_end_year: int | None
    rows_upserted: int = Field(ge=0)
    consecutive_failures: int = Field(ge=0)
    last_error: str | None


class EconomicRankingWeight(BaseModel):
    """One operator-adjustable component of the composite country score."""

    model_config = ConfigDict(extra="forbid")

    indicator_code: str
    name_en: str
    name_zh: str
    weight: float = Field(ge=0, le=100)
    direction: str


class EconomicMetricRank(BaseModel):
    """One country's world rank for a component indicator."""

    model_config = ConfigDict(extra="forbid")

    indicator_code: str
    value: float
    year: int
    rank: int = Field(gt=0)
    ranked_country_count: int = Field(gt=0)
    normalized_score: float = Field(ge=0, le=1)


class EconomicCountryRanking(BaseModel):
    """Composite rank and explainable component ranks for one country."""

    model_config = ConfigDict(extra="forbid")

    iso2: str = Field(min_length=2, max_length=2)
    iso3: str = Field(min_length=3, max_length=3)
    country_name: str
    rank: int = Field(gt=0)
    ranked_country_count: int = Field(gt=0)
    composite_score: float = Field(ge=0, le=100)
    data_coverage: float = Field(ge=0, le=1)
    metric_ranks: list[EconomicMetricRank]


class EconomicRankingResponse(BaseModel):
    """Weighted country comparison for one common observation year."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    year: int
    methodology: str
    weights: list[EconomicRankingWeight]
    countries: list[EconomicCountryRanking]
