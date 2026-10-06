"""Validated contracts for the interactive operator map."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import EventStatus
from app.schemas.extractions import ImpactEstimate

MapMarkerKind = Literal["canonical", "candidate"]
ReviewCategory = Literal["merge", "review", "independent"] | None
GeolocationPrecision = Literal["point", "city", "admin1", "country"]
ConflictZoneRole = Literal[
    "primary_theater",
    "secondary_theater",
    "reported_site",
    "location_unconfirmed",
]


class EarthquakeWave(BaseModel):
    """One distinct wave/event retained inside a displayed earthquake series."""

    model_config = ConfigDict(extra="forbid")

    marker_id: str
    document_id: int = Field(gt=0)
    title: str
    occurred_at: datetime
    magnitude: float | None = Field(default=None, ge=0, le=12)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    source_name: str
    source_url: str


class MapEventMarker(BaseModel):
    """One canonical or AI-candidate point rendered on the map."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    kind: MapMarkerKind
    event_id: int | None = Field(default=None, gt=0)
    cluster_job_id: int | None = Field(default=None, gt=0)
    cluster_id: int | None = Field(default=None, gt=0)
    document_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=2_000)
    summary: str | None = Field(default=None, max_length=4_000)
    event_type: str = Field(min_length=1, max_length=64)
    is_conflict: bool = False
    conflict_zone_role: ConflictZoneRole | None = None
    theater_confidence: float | None = Field(default=None, ge=0, le=0.75)
    advance_direction: str | None = Field(default=None, max_length=64)
    actors: list[str] = Field(default_factory=list, max_length=12)
    impact: ImpactEstimate | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    geolocation_precision: GeolocationPrecision = "point"
    country_code: str | None = None
    occurred_at: datetime
    published_at: datetime | None
    confidence: float = Field(ge=0, le=1)
    severity: float = Field(ge=0, le=1)
    status: EventStatus | None
    review_category: ReviewCategory = None
    source_name: str
    source_url: str
    series_count: int = Field(default=1, ge=1)
    series_start_at: datetime | None = None
    series_end_at: datetime | None = None
    series_events: list[EarthquakeWave] = Field(default_factory=list)


class ConflictSituationZone(BaseModel):
    """A local conflict footprint inferred from clustered, dated reports."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=3, max_length=128)
    country_code: str = Field(min_length=2, max_length=3)
    role: Literal["primary_theater", "secondary_theater", "reported_site"]
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(ge=10, le=220)
    urgency_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=0.75)
    event_count: int = Field(ge=1)
    source_count: int = Field(ge=1)
    actors: list[str] = Field(default_factory=list, max_length=12)
    fatalities_best: int | None = Field(default=None, ge=0)
    start_at: datetime
    end_at: datetime
    marker_ids: list[str] = Field(min_length=1, max_length=250)


class ConflictMovementVector(BaseModel):
    """A cautious shift in reported activity, never a live troop position."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=3, max_length=128)
    country_code: str = Field(min_length=2, max_length=3)
    actor: str | None = Field(default=None, max_length=255)
    from_latitude: float = Field(ge=-90, le=90)
    from_longitude: float = Field(ge=-180, le=180)
    to_latitude: float = Field(ge=-90, le=90)
    to_longitude: float = Field(ge=-180, le=180)
    direction: str = Field(min_length=1, max_length=8)
    distance_km: float = Field(ge=25, le=600)
    start_at: datetime
    end_at: datetime
    confidence: float = Field(ge=0, le=0.6)
    evidence_count: int = Field(ge=2)
    marker_ids: list[str] = Field(min_length=2, max_length=250)
    inference_kind: Literal["reported_activity_shift"] = "reported_activity_shift"


class MapDataResponse(BaseModel):
    """Current canonical and candidate map layers."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    latest_cluster_job_id: int | None = Field(default=None, gt=0)
    latest_logic_job_id: int | None = Field(default=None, gt=0)
    canonical_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    markers: list[MapEventMarker]
    conflict_zones: list[ConflictSituationZone] = Field(default_factory=list)
    conflict_movements: list[ConflictMovementVector] = Field(
        default_factory=list,
    )
