"""Deterministic mock extractor used before local-LLM integration."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from app.schemas.extractions import (
    DocumentExtractionInput,
    EventExtractionResult,
    EvidenceField,
    EvidenceSpan,
    ExtractedEntity,
    ExtractedEvent,
    ExtractedLocation,
    SourceField,
)

MAGNITUDE_PATTERN = re.compile(r"\bM\s+(?P<magnitude>\d+(?:\.\d+)?)")
EARTHQUAKE_LOCATION_PATTERN = re.compile(
    r"Location\s+"
    r"(?P<latitude>\d+(?:\.\d+)?)°(?P<latitude_direction>[NS])\s+"
    r"(?P<longitude>\d+(?:\.\d+)?)°(?P<longitude_direction>[EW])"
)
UTC_TIME_PATTERN = re.compile(
    r"Time\s+(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) UTC"
)

KEYWORD_TYPES: tuple[tuple[str, str, float], ...] = (
    ("wildfire", "wildfire", 0.70),
    ("earthquake", "earthquake", 0.65),
    ("sanction", "sanctions", 0.55),
    ("appoint", "appointment", 0.25),
    ("climate", "climate_policy", 0.40),
    ("launch", "space_mission", 0.45),
)


class MockEventExtractor:
    """Parse known structured feeds and classify other documents predictably."""

    name = "mock-v1"

    def extract(self, document: DocumentExtractionInput) -> EventExtractionResult:
        """Return one deterministic candidate for every valid document."""
        if magnitude_match := MAGNITUDE_PATTERN.search(document.title):
            event = self._earthquake_event(document, magnitude_match)
        else:
            event = self._generic_event(document)
        return EventExtractionResult(
            extractor=self.name,
            document_id=document.document_id,
            events=[event],
        )

    def _earthquake_event(
        self,
        document: DocumentExtractionInput,
        magnitude_match: re.Match[str],
    ) -> ExtractedEvent:
        magnitude = float(magnitude_match.group("magnitude"))
        place = document.title.partition(" - ")[2].strip() or document.title
        coordinates_match = EARTHQUAKE_LOCATION_PATTERN.search(document.body)
        time_match = UTC_TIME_PATTERN.search(document.body)
        location = self._earthquake_location(place, coordinates_match)
        evidence = [
            self._span(
                field="severity",
                source_field="title",
                text=document.title,
                match=magnitude_match,
            )
        ]
        if coordinates_match is not None:
            evidence.append(
                self._span(
                    field="location",
                    source_field="body",
                    text=document.body,
                    match=coordinates_match,
                )
            )
        if time_match is not None:
            evidence.append(
                self._span(
                    field="time",
                    source_field="body",
                    text=document.body,
                    match=time_match,
                )
            )

        occurred_at = document.published_at
        if time_match is not None:
            occurred_at = datetime.strptime(
                time_match.group("timestamp"),
                "%Y-%m-%d %H:%M:%S",
            ).replace(tzinfo=UTC)

        return ExtractedEvent(
            event_type="earthquake",
            title=document.title,
            summary=self._summary(document),
            entities=[
                ExtractedEntity(
                    name=place,
                    entity_type="location",
                    confidence=0.95,
                )
            ],
            location=location,
            occurred_at=occurred_at,
            severity=min(1.0, magnitude / 10.0),
            confidence=0.98 if coordinates_match is not None else 0.85,
            evidence_spans=evidence,
        )

    def _generic_event(self, document: DocumentExtractionInput) -> ExtractedEvent:
        combined = f"{document.title}\n{document.body}".lower()
        event_type = "official_announcement"
        severity = 0.30
        for keyword, candidate_type, candidate_severity in KEYWORD_TYPES:
            if keyword in combined:
                event_type = candidate_type
                severity = candidate_severity
                break

        return ExtractedEvent(
            event_type=event_type,
            title=document.title,
            summary=self._summary(document),
            occurred_at=document.published_at,
            severity=severity,
            confidence=0.55,
            evidence_spans=[
                EvidenceSpan(
                    field="event_type",
                    source_field="title",
                    start_char=0,
                    end_char=len(document.title),
                    quote=document.title,
                )
            ],
        )

    @staticmethod
    def _earthquake_location(
        place: str,
        match: re.Match[str] | None,
    ) -> ExtractedLocation:
        country_code = MockEventExtractor._country_for_place(place)
        if match is None:
            return ExtractedLocation(
                name=place,
                country_code=country_code,
                confidence=0.60,
            )
        latitude = float(match.group("latitude"))
        longitude = float(match.group("longitude"))
        if match.group("latitude_direction") == "S":
            latitude *= -1
        if match.group("longitude_direction") == "W":
            longitude *= -1
        return ExtractedLocation(
            name=place,
            country_code=country_code,
            latitude=latitude,
            longitude=longitude,
            confidence=0.98,
        )

    @staticmethod
    def _country_for_place(place: str) -> str | None:
        normalized = place.casefold()
        if "japan" in normalized:
            return "JP"
        if any(
            marker in normalized
            for marker in ("alaska", "hawaii", ", ca", "california")
        ):
            return "US"
        return None

    @staticmethod
    def _summary(document: DocumentExtractionInput) -> str:
        body = document.body.strip()
        return (body[:1000] if body else document.title).strip()

    @staticmethod
    def _span(
        *,
        field: EvidenceField,
        source_field: SourceField,
        text: str,
        match: re.Match[str],
    ) -> EvidenceSpan:
        return EvidenceSpan(
            field=field,
            source_field=source_field,
            start_char=match.start(),
            end_char=match.end(),
            quote=text[match.start() : match.end()],
        )
