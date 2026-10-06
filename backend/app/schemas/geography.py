"""Validated contracts for hierarchical places and regional statistics."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AdministrativeLevel = Literal["admin1", "admin2", "city"]


class RegionalMetricView(BaseModel):
    """One traceable subnational observation."""

    model_config = ConfigDict(extra="forbid")

    indicator_code: str
    name_en: str
    name_zh: str
    unit: str
    period: str
    value: float
    source_name: str
    source_url: str
    license_name: str
    license_url: str


class AdministrativeAreaView(BaseModel):
    """A subdivision or populated place usable at an appropriate zoom."""

    model_config = ConfigDict(extra="forbid")

    id: int
    parent_id: int | None
    country_iso2: str = Field(min_length=2, max_length=2)
    level: AdministrativeLevel
    code: str
    name: str
    ascii_name: str | None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    coordinate_precision: str
    population: int | None = Field(default=None, ge=0)
    source_name: str
    source_url: str
    license_name: str
    license_url: str


class AdministrativeAreaListResponse(BaseModel):
    """A bounded map layer for one country and administrative level."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    country_iso2: str = Field(min_length=2, max_length=2)
    level: AdministrativeLevel
    count: int = Field(ge=0)
    areas: list[AdministrativeAreaView]


class AdministrativeAreaDetailResponse(BaseModel):
    """One regional panel with its latest available official observations."""

    model_config = ConfigDict(extra="forbid")

    area: AdministrativeAreaView
    metrics: list[RegionalMetricView]
    child_count: int = Field(ge=0)
