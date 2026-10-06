"""Contracts for the on-demand conflict indicator layer."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ConflictIndicatorPoint(BaseModel):
    """One recent Admin1 conflict footprint."""

    model_config = ConfigDict(extra="forbid")

    country: str
    admin1: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    events: int = Field(ge=0)
    fatalities: int = Field(ge=0)
    population_exposure: float | None = Field(default=None, ge=0)
    urgency_score: float = Field(ge=0, le=1)
    role: str
    event_types: list[str]
    period_start: date
    period_end: date


class ConflictIndicatorResponse(BaseModel):
    """A bounded conflict layer independent from the news timeline."""

    model_config = ConfigDict(extra="forbid")

    source: str = "ACLED authenticated aggregate data"
    source_url: str = "https://acleddata.com/"
    weeks: int
    latest_week: date | None
    point_count: int
    truncated: bool
    points: list[ConflictIndicatorPoint]
