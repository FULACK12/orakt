"""Strict contracts for document-to-event extraction."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EntityType = Literal[
    "person",
    "organization",
    "location",
    "country",
    "asset",
    "other",
]
EvidenceField = Literal[
    "event_type",
    "entities",
    "location",
    "severity",
    "time",
    "summary",
    "impact",
]
SourceField = Literal["title", "body"]


class DocumentExtractionInput(BaseModel):
    """Normalized document supplied to any extractor implementation."""

    model_config = ConfigDict(extra="forbid")

    document_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=2000)
    body: str = Field(default="", max_length=1_000_000)
    published_at: datetime | None = None
    language: str | None = Field(default=None, max_length=16)
    source_country: str | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        pattern=r"^[A-Z]{2}$",
    )

    @field_validator("source_country", mode="before")
    @classmethod
    def normalize_country(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value


class ExtractedEntity(BaseModel):
    """One named entity mentioned by the candidate event."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=500)
    entity_type: EntityType
    confidence: float = Field(ge=0, le=1)


class ExtractedLocation(BaseModel):
    """Normalized event location with optional point coordinates."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=500)
    country_code: str | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        pattern=r"^[A-Z]{2}$",
    )
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    confidence: float = Field(ge=0, le=1)

    @field_validator("country_code", mode="before")
    @classmethod
    def normalize_country(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @model_validator(mode="after")
    def coordinates_are_paired(self) -> Self:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class ImpactEstimate(BaseModel):
    """Explicitly reported human or economic impact with uncertainty bounds."""

    model_config = ConfigDict(extra="forbid")

    fatalities_low: int | None = Field(default=None, ge=0)
    fatalities_best: int | None = Field(default=None, ge=0)
    fatalities_high: int | None = Field(default=None, ge=0)
    injured_low: int | None = Field(default=None, ge=0)
    injured_high: int | None = Field(default=None, ge=0)
    displaced_low: int | None = Field(default=None, ge=0)
    displaced_high: int | None = Field(default=None, ge=0)
    economic_loss_low: float | None = Field(default=None, ge=0)
    economic_loss_high: float | None = Field(default=None, ge=0)
    economic_loss_currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
    )
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def ranges_are_ordered(self) -> Self:
        range_pairs = (
            (self.fatalities_low, self.fatalities_high),
            (self.injured_low, self.injured_high),
            (self.displaced_low, self.displaced_high),
            (self.economic_loss_low, self.economic_loss_high),
        )
        if any(
            low is not None and high is not None and low > high
            for low, high in range_pairs
        ):
            raise ValueError("impact lower bounds must not exceed upper bounds")
        if (
            self.fatalities_best is not None
            and self.fatalities_low is not None
            and self.fatalities_best < self.fatalities_low
        ):
            raise ValueError("fatalities_best must not be below fatalities_low")
        if (
            self.fatalities_best is not None
            and self.fatalities_high is not None
            and self.fatalities_best > self.fatalities_high
        ):
            raise ValueError("fatalities_best must not exceed fatalities_high")
        has_loss = (
            self.economic_loss_low is not None
            or self.economic_loss_high is not None
        )
        if has_loss != (self.economic_loss_currency is not None):
            raise ValueError(
                "economic loss values and currency must be supplied together"
            )
        return self


class EvidenceSpan(BaseModel):
    """Verbatim evidence with offsets into one source field."""

    model_config = ConfigDict(extra="forbid")

    field: EvidenceField
    source_field: SourceField
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    quote: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def end_follows_start(self) -> Self:
        if self.end_char <= self.start_char:
            raise ValueError("end_char must be greater than start_char")
        return self


class ExtractedEvent(BaseModel):
    """One validated event candidate emitted by an extractor."""

    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    title: str = Field(min_length=1, max_length=2000)
    summary: str = Field(min_length=1, max_length=4000)
    entities: list[ExtractedEntity] = Field(default_factory=list)
    location: ExtractedLocation | None = None
    impact: ImpactEstimate | None = None
    occurred_at: datetime | None = None
    severity: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    evidence_spans: list[EvidenceSpan] = Field(min_length=1)

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        """Treat provider timestamps without an offset as UTC."""
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def impact_requires_evidence(self) -> Self:
        if (
            self.impact is not None
            and not any(
                span.field == "impact"
                for span in self.evidence_spans
            )
        ):
            raise ValueError("impact requires a verbatim impact evidence span")
        return self


class ModelEventBatch(BaseModel):
    """The only JSON shape accepted directly from a language model."""

    model_config = ConfigDict(extra="forbid")

    events: list[ExtractedEvent] = Field(default_factory=list, max_length=10)


class EventExtractionResult(BaseModel):
    """Versioned, fully validated output for one source document."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    extractor: str = Field(min_length=1, max_length=255)
    document_id: int = Field(gt=0)
    events: list[ExtractedEvent] = Field(default_factory=list)
