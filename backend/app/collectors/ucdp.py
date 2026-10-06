"""Versioned UCDP conflict-event collection and canonical persistence."""

from __future__ import annotations

import math
import re
import unicodedata
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors.rss import document_hash
from app.db.enums import DocumentStance, EventStatus, SourceType
from app.db.models import CountryProfile, Document, Event, EventDocument, Source
from app.storage.archive import ColdArchive

UCDP_API_BASE = "https://ucdpapi.pcr.uu.se/api/gedevents"
UCDP_DOCUMENTATION_URL = "https://ucdp.uu.se/apidocs/"
UCDP_DOWNLOADS_URL = "https://ucdp.uu.se/downloads/"
UCDP_LICENSE_NAME = "Creative Commons Attribution 4.0"
UCDP_LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"

VIOLENCE_TYPES = {
    1: "state_based_conflict",
    2: "non_state_conflict",
    3: "one_sided_violence",
}

COUNTRY_ALIASES = {
    "bolivia": "BO",
    "bosnia herzegovina": "BA",
    "central african republic": "CF",
    "china": "CN",
    "congo": "CG",
    "democratic republic of congo": "CD",
    "dr congo": "CD",
    "egypt": "EG",
    "gambia": "GM",
    "iran": "IR",
    "ivory coast": "CI",
    "kyrgyzstan": "KG",
    "laos": "LA",
    "north korea": "KP",
    "palestine": "PS",
    "republic of congo": "CG",
    "russia": "RU",
    "slovakia": "SK",
    "somalia": "SO",
    "south korea": "KR",
    "syria": "SY",
    "turkey": "TR",
    "venezuela": "VE",
    "vietnam": "VN",
    "yemen": "YE",
}


class UCDPCollectionResult(BaseModel):
    """Safe accounting for one versioned UCDP synchronization pass."""

    model_config = ConfigDict(extra="forbid")

    dataset_version: str
    start_date: date
    end_date: date
    pages_fetched: int = Field(default=0, ge=0)
    events_seen: int = Field(default=0, ge=0)
    events_created: int = Field(default=0, ge=0)
    documents_created: int = Field(default=0, ge=0)
    duplicates_skipped: int = Field(default=0, ge=0)
    invalid_events: int = Field(default=0, ge=0)
    unresolved_countries: int = Field(default=0, ge=0)


class UCDPConflictCollector:
    """Fetch a pinned UCDP Candidate release without exposing its token."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        access_token: str,
        dataset_version: str,
        page_size: int = 1_000,
        archive: ColdArchive | None = None,
    ) -> None:
        if not access_token.strip():
            raise ValueError("UCDP access token is required")
        if not re.fullmatch(r"\d+(?:\.\d+){1,4}", dataset_version):
            raise ValueError("invalid UCDP dataset version")
        if not 1 <= page_size <= 1_000:
            raise ValueError("UCDP page size must be between 1 and 1000")
        self.client = client
        self.access_token = access_token
        self.dataset_version = dataset_version
        self.page_size = page_size
        self.archive = archive

    async def collect(
        self,
        session: Session,
        *,
        start_date: date,
        end_date: date,
    ) -> UCDPCollectionResult:
        """Fetch a bounded interval and persist traceable canonical events."""
        if start_date > end_date:
            raise ValueError("UCDP start_date must not be after end_date")
        raw_events, pages_fetched = await self._fetch_pages(
            start_date=start_date,
            end_date=end_date,
        )
        result = UCDPCollectionResult(
            dataset_version=self.dataset_version,
            start_date=start_date,
            end_date=end_date,
            pages_fetched=pages_fetched,
            events_seen=len(raw_events),
        )
        source = _get_or_create_source(session, self.dataset_version)
        country_names = _country_name_map(session)
        for raw in raw_events:
            if not _valid_event(raw):
                result.invalid_events += 1
                continue
            event_id = int(raw["id"])
            url = (
                f"{UCDP_API_BASE}/{self.dataset_version}"
                f"?Id={event_id}"
            )
            if session.scalar(select(Document.id).where(Document.url == url)) is not None:
                result.duplicates_skipped += 1
                continue
            country_code = _resolve_country_iso2(
                str(raw.get("country") or ""),
                country_names,
            )
            if country_code is None:
                result.unresolved_countries += 1
            document, event = _build_records(
                raw,
                source=source,
                url=url,
                dataset_version=self.dataset_version,
                country_code=country_code,
                archive=self.archive,
            )
            session.add(document)
            session.flush()
            session.add(event)
            session.flush()
            session.add(
                EventDocument(
                    event_id=event.id,
                    document_id=document.id,
                    relevance_score=Decimal("1.000"),
                    stance=DocumentStance.SUPPORTS,
                    is_primary_source=True,
                )
            )
            result.documents_created += 1
            result.events_created += 1
        session.commit()
        return result

    async def _fetch_pages(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> tuple[list[dict[str, Any]], int]:
        events: list[dict[str, Any]] = []
        page = 1
        total_pages = 1
        while page <= total_pages:
            response = await self.client.get(
                f"{UCDP_API_BASE}/{self.dataset_version}",
                headers={"x-ucdp-access-token": self.access_token},
                params={
                    "pagesize": self.page_size,
                    "page": page,
                    "StartDate": start_date.isoformat(),
                    "EndDate": end_date.isoformat(),
                },
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("Result"), list):
                raise TypeError("UCDP response must contain a Result list")
            raw_total_pages = payload.get("TotalPages", 1)
            if not isinstance(raw_total_pages, int) or raw_total_pages < 0:
                raise TypeError("UCDP TotalPages must be a non-negative integer")
            total_pages = raw_total_pages
            events.extend(item for item in payload["Result"] if isinstance(item, dict))
            page += 1
        return events, total_pages


def _get_or_create_source(session: Session, version: str) -> Source:
    name = f"UCDP Candidate Events {version}"
    source = session.scalar(
        select(Source).where(Source.name == name, Source.country.is_(None))
    )
    if source is not None:
        return source
    source = Source(
        name=name,
        country=None,
        language="en",
        source_type=SourceType.API,
        ownership="Uppsala University",
        credibility_baseline=Decimal("0.920"),
        political_bias_metadata={
            "kind": "structured_conflict_event_api",
            "dataset": "UCDP Candidate Events",
            "version": version,
            "license_name": UCDP_LICENSE_NAME,
            "license_url": UCDP_LICENSE_URL,
            "documentation_url": UCDP_DOCUMENTATION_URL,
            "citation_required": True,
        },
    )
    session.add(source)
    session.flush()
    return source


def _build_records(
    raw: dict[str, Any],
    *,
    source: Source,
    url: str,
    dataset_version: str,
    country_code: str | None,
    archive: ColdArchive | None,
) -> tuple[Document, Event]:
    event_id = int(raw["id"])
    start_at = _parse_ucdp_date(raw["date_start"])
    if start_at is None:
        raise ValueError("valid UCDP event has no start date")
    end_at = _parse_ucdp_date(raw.get("date_end")) or start_at
    violence_type = int(raw.get("type_of_violence") or 1)
    event_type = VIOLENCE_TYPES.get(violence_type, "armed_conflict")
    dyad = str(raw.get("dyad_name") or raw.get("conflict_name") or "Organized violence")
    location = str(
        raw.get("where_coordinates")
        or raw.get("where_description")
        or raw.get("adm_1")
        or raw.get("country")
        or "location not specified"
    )
    title = f"{dyad} · {location}"[:2_000]
    fatalities_low = _nonnegative_int(raw.get("low"))
    fatalities_best = _nonnegative_int(raw.get("best"))
    fatalities_high = _nonnegative_int(raw.get("high"))
    summary = (
        f"UCDP {event_type.replace('_', ' ')} event at {location}. "
        f"Reported fatality estimate: best {fatalities_best}, "
        f"range {fatalities_low} to {fatalities_high}. "
        f"{str(raw.get('where_description') or '').strip()}"
    ).strip()[:4_000]
    metadata = {
        "collector": "ucdp_gedevents",
        "dataset": "UCDP Candidate Events",
        "dataset_version": dataset_version,
        "ucdp_event_id": event_id,
        "ucdp_relid": raw.get("relid"),
        "type_of_violence": violence_type,
        "conflict_name": raw.get("conflict_name"),
        "dyad_name": raw.get("dyad_name"),
        "side_a": raw.get("side_a"),
        "side_b": raw.get("side_b"),
        "country": raw.get("country"),
        "country_id": raw.get("country_id"),
        "region": raw.get("region"),
        "adm_1": raw.get("adm_1"),
        "adm_2": raw.get("adm_2"),
        "where_coordinates": raw.get("where_coordinates"),
        "where_description": raw.get("where_description"),
        "where_prec": raw.get("where_prec"),
        "date_prec": raw.get("date_prec"),
        "event_clarity": raw.get("event_clarity"),
        "code_status": raw.get("code_status"),
        "fatalities_low": fatalities_low,
        "fatalities_best": fatalities_best,
        "fatalities_high": fatalities_high,
        "deaths_a": _nonnegative_int(raw.get("deaths_a")),
        "deaths_b": _nonnegative_int(raw.get("deaths_b")),
        "deaths_civilians": _nonnegative_int(raw.get("deaths_civilians")),
        "deaths_unknown": _nonnegative_int(raw.get("deaths_unknown")),
        "number_of_sources": raw.get("number_of_sources"),
        "source_article": raw.get("source_article"),
        "source_original": raw.get("source_original"),
        "license_name": UCDP_LICENSE_NAME,
        "license_url": UCDP_LICENSE_URL,
        "citation_url": UCDP_DOWNLOADS_URL,
    }
    body = (
        f"{summary}\n"
        f"Actors: {(raw.get('side_a') or 'unknown')!s} — "
        f"{(raw.get('side_b') or 'unknown')!s}.\n"
        f"UCDP event ID: {event_id}; dataset version: {dataset_version}."
    )
    content_hash = document_hash(title, body)
    raw_object_path = None
    if archive is not None:
        raw_object_path = archive.store_entry(
            content_hash=content_hash,
            source_id=source.id,
            url=url,
            title=title,
            body=body,
            published_at=None,
            metadata=metadata,
        )
    document = Document(
        source_id=source.id,
        url=url,
        title=title,
        body=body,
        language="en",
        published_at=None,
        content_hash=content_hash,
        credibility_score=source.credibility_baseline,
        raw_object_path=raw_object_path,
        raw_metadata=metadata,
    )
    event = Event(
        event_type=event_type,
        title=title,
        summary=summary,
        status=(
            EventStatus.CONFIRMED
            if str(raw.get("code_status") or "").casefold() == "clear"
            else EventStatus.PARTIALLY_CONFIRMED
        ),
        severity=Decimal(str(_severity(fatalities_best))),
        novelty=Decimal("0.500"),
        confidence=Decimal(str(_confidence(raw))),
        start_at=start_at,
        end_at=end_at,
        latitude=Decimal(str(float(raw["latitude"]))),
        longitude=Decimal(str(float(raw["longitude"]))),
        country_code=country_code,
    )
    return document, event


def _valid_event(raw: dict[str, Any]) -> bool:
    try:
        event_id = int(str(raw.get("id")))
        latitude = float(str(raw.get("latitude")))
        longitude = float(str(raw.get("longitude")))
        start_at = _parse_ucdp_date(raw.get("date_start"))
    except (TypeError, ValueError):
        return False
    return (
        event_id > 0
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
        and start_at is not None
    )


def _country_name_map(session: Session) -> dict[str, str]:
    names = {
        _normalize_country_name(profile.name): profile.iso2.upper()
        for profile in session.scalars(select(CountryProfile))
    }
    names.update(COUNTRY_ALIASES)
    return names


def _resolve_country_iso2(
    country_name: str,
    names: dict[str, str],
) -> str | None:
    normalized = _normalize_country_name(country_name)
    candidates = [
        normalized,
        _normalize_country_name(re.sub(r"\([^)]*\)", "", country_name)),
    ]
    for candidate in candidates:
        if candidate in names:
            return names[candidate]
    for alias, iso2 in COUNTRY_ALIASES.items():
        if normalized.startswith(f"{alias} ") or normalized == alias:
            return iso2
    return None


def _normalize_country_name(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(
        character
        for character in ascii_value
        if not unicodedata.combining(character)
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", ascii_value.casefold()).split())


def _parse_ucdp_date(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
    return datetime(parsed.year, parsed.month, parsed.day, tzinfo=UTC)


def _nonnegative_int(value: object) -> int:
    try:
        if not isinstance(value, (str, bytes, bytearray, int, float)):
            return 0
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _severity(fatalities_best: int) -> float:
    if fatalities_best <= 0:
        return 0.25
    return round(min(1, 0.25 + math.log10(fatalities_best + 1) / 4), 3)


def _confidence(raw: dict[str, Any]) -> float:
    where_precision = max(1, _nonnegative_int(raw.get("where_prec")))
    date_precision = max(1, _nonnegative_int(raw.get("date_prec")))
    score = 0.97 - min(where_precision - 1, 6) * 0.035
    score -= min(date_precision - 1, 4) * 0.025
    if str(raw.get("code_status") or "").casefold() != "clear":
        score -= 0.08
    return round(max(0.62, min(0.98, score)), 3)
