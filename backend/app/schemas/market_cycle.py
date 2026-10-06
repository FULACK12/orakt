"""Transparent economic-cycle model output."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CycleRegime = Literal[
    "expansion",
    "late_cycle",
    "slowdown",
    "contraction",
    "recovery",
    "insufficient_data",
]


class CycleComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    series_id: str
    value: float | None = None
    score: float = Field(ge=-1, le=1)


class MarketCycleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    regime: CycleRegime
    score: float = Field(ge=-1, le=1)
    as_of: str | None = None
    component_count: int = Field(ge=0)
    expected_component_count: int = Field(ge=1)
    components: list[CycleComponent]
    methodology: str

