"""Public contracts for archived EIA energy time series."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EnergyDatasetStatus(BaseModel):
    """Download and materialization status for one EIA dataset."""

    model_config = ConfigDict(extra="forbid")

    dataset_key: str
    source_url: str
    source_last_updated: str | None
    archive_path: str | None
    archive_bytes: int = Field(ge=0)
    series_cataloged: int = Field(ge=0)
    series_materialized: int = Field(ge=0)
    observations_upserted: int = Field(ge=0)
    last_success_at: datetime | None
    last_error: str | None


class EnergySeriesSummary(BaseModel):
    """Searchable metadata for one official EIA series."""

    model_config = ConfigDict(extra="forbid")

    series_id: str
    dataset_key: str
    name: str
    units: str | None
    frequency: str | None
    start_period: str | None
    end_period: str | None
    observation_count: int = Field(ge=0)
    materialized: bool
    source_url: str


class EnergyObservationView(BaseModel):
    """One timestamp/value pair from a materialized EIA series."""

    model_config = ConfigDict(extra="forbid")

    period: str
    value: float


class EnergySeriesModel(BaseModel):
    """Transparent deterministic signal model for one energy series."""

    model_config = ConfigDict(extra="forbid")

    latest_period: str | None
    latest_value: float | None
    previous_value: float | None
    period_change_percent: float | None
    year_change_percent: float | None
    rolling_mean: float | None
    rolling_z_score: float | None
    anomaly_score: float = Field(ge=0, le=1)
    trend: str
    method: str


class EnergySeriesDetail(BaseModel):
    """Metadata, values and transparent model output for one EIA series."""

    model_config = ConfigDict(extra="forbid")

    series: EnergySeriesSummary
    observations: list[EnergyObservationView]
    model: EnergySeriesModel
