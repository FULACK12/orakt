"""Transparent multi-model economic-cycle research outputs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CycleSignalView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: str
    label: str
    value: float | None
    change: float | None = None
    score: float = Field(ge=-1, le=1)
    observed_on: str | None = None


class CycleModelView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    theory: str
    horizon: str
    regime: str
    score: float = Field(ge=-1, le=1)
    confidence: float = Field(ge=0, le=1)
    signals: list[CycleSignalView]
    missing_series: list[str]
    caveats: list[str]


class CycleModelSuiteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    as_of: str | None
    models: list[CycleModelView]
