"""Validated GeoJSON contracts for the event map API."""

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.enums import EventStatus


class EventQuery(BaseModel):
    """Supported filters for the event map."""

    model_config = ConfigDict(extra="forbid")

    start: datetime | None = Field(
        default=None,
        description="Inclusive event start time in an offset-aware ISO 8601 format.",
    )
    end: datetime | None = Field(
        default=None,
        description="Inclusive event end time in an offset-aware ISO 8601 format.",
    )
    country: str | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        pattern=r"^[A-Z]{2}$",
        description="ISO 3166-1 alpha-2 country code.",
    )
    event_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Exact canonical event type.",
    )
    limit: int = Field(default=500, ge=1, le=1000)

    @field_validator("start", "end")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        """Reject ambiguous timestamps without an explicit UTC offset."""
        if value is not None and value.utcoffset() is None:
            raise ValueError("timestamp must include a UTC offset")
        return value

    @field_validator("country", mode="before")
    @classmethod
    def normalize_country(cls, value: object) -> object:
        """Normalize human-entered country codes before validation."""
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("event_type", mode="before")
    @classmethod
    def normalize_event_type(cls, value: object) -> object:
        """Ignore accidental surrounding whitespace."""
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        """Require a forward-moving inclusive time window."""
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError("start must be earlier than or equal to end")
        return self


class GeoJSONPoint(BaseModel):
    """A GeoJSON point using longitude-first coordinate order."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float]


class EventProperties(BaseModel):
    """Map-facing event metadata carried by a GeoJSON feature."""

    model_config = ConfigDict(extra="forbid")

    event_type: str
    title: str
    summary: str | None
    status: EventStatus
    severity: float
    novelty: float
    confidence: float
    start_at: datetime
    end_at: datetime | None
    country_code: str | None


class EventFeature(BaseModel):
    """One canonical event encoded as a GeoJSON feature."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["Feature"] = "Feature"
    id: int
    geometry: GeoJSONPoint
    properties: EventProperties


class EventFeatureCollection(BaseModel):
    """GeoJSON collection returned by the map endpoint."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[EventFeature]
