"""Source-bounded manufacturing locations and spatial exposure joins."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import and_, case, delete, desc, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    AdministrativeArea,
    CompanySupplyChainEdge,
    CompanySupplyChainSite,
    ConflictAggregateObservation,
    Event,
)

COUNTRY_ISO2 = {
    "austria": "AT",
    "belgium": "BE",
    "brazil": "BR",
    "canada": "CA",
    "china": "CN",
    "china mainland": "CN",
    "czech republic": "CZ",
    "france": "FR",
    "germany": "DE",
    "india": "IN",
    "indonesia": "ID",
    "ireland": "IE",
    "israel": "IL",
    "italy": "IT",
    "japan": "JP",
    "malaysia": "MY",
    "malta": "MT",
    "mexico": "MX",
    "morocco": "MA",
    "netherlands": "NL",
    "philippines": "PH",
    "portugal": "PT",
    "saudi arabia": "SA",
    "singapore": "SG",
    "south korea": "KR",
    "spain": "ES",
    "taiwan": "TW",
    "thailand": "TH",
    "united kingdom": "GB",
    "united states": "US",
    "vietnam": "VN",
}

COUNTRY_ALIASES = {
    "por tugal": "portugal",
    "u k": "united kingdom",
    "uk": "united kingdom",
    "u s": "united states",
    "usa": "united states",
}

PLACE_ALIASES = {
    # OCR artifacts preserved in historical issuer supplier lists.
    "lexilip": "Leixlip",
    "por tugal": "Portugal",
}

DISASTER_PATTERN = re.compile(
    r"earthquake|flood|wildfire|fire|storm|hurricane|typhoon|cyclone|tornado|"
    r"drought|landslide|tsunami|volcan|disaster|extreme weather",
    re.IGNORECASE,
)
POWER_PATTERN = re.compile(
    r"power outage|blackout|electricity shortage|grid constraint|grid emergency|"
    r"power ration|electricity ration",
    re.IGNORECASE,
)


def parse_reported_geography(value: str) -> list[tuple[str, str, str | None]]:
    """Split an issuer's ``place - country`` string without inventing facilities."""
    parsed: list[tuple[str, str, str | None]] = []
    seen: set[tuple[str, str]] = set()
    for group in value.split("|"):
        group = group.strip()
        if " - " not in group:
            continue
        place_text, country_name = group.rsplit(" - ", 1)
        country_name = _clean_country_name(country_name)
        iso2 = COUNTRY_ISO2.get(_normalize(country_name))
        for place in place_text.split(","):
            place = re.sub(r"\s+", " ", place).strip(" .")
            place = PLACE_ALIASES.get(_normalize(place), place)
            if not place:
                continue
            key = (_normalize(place), iso2 or _normalize(country_name))
            if key in seen:
                continue
            seen.add(key)
            parsed.append((place, country_name, iso2))
    return parsed


def materialize_supply_chain_sites(
    session: Session,
    *,
    ticker: str | None = None,
) -> dict[str, int]:
    """Materialize verified issuer-reported regions using existing local geography."""
    statement = select(CompanySupplyChainEdge).where(
        CompanySupplyChainEdge.review_status == "verified",
        CompanySupplyChainEdge.geography.is_not(None),
    )
    if ticker:
        statement = statement.where(CompanySupplyChainEdge.subject_ticker == ticker.upper())
    edges = list(session.scalars(statement.order_by(CompanySupplyChainEdge.id)))
    area_cache: dict[str, list[AdministrativeArea]] = {}
    inserted = 0
    mapped = 0
    unresolved = 0
    removed = 0
    for edge in edges:
        existing_count = int(
            session.scalar(
                select(func.count())
                .select_from(CompanySupplyChainSite)
                .where(
                    CompanySupplyChainSite.edge_id == edge.id,
                    CompanySupplyChainSite.site_kind == "manufacturing_region",
                    CompanySupplyChainSite.verification_status == "verified_region",
                )
            )
            or 0
        )
        if existing_count:
            session.execute(
                delete(CompanySupplyChainSite).where(
                    CompanySupplyChainSite.edge_id == edge.id,
                    CompanySupplyChainSite.site_kind == "manufacturing_region",
                    CompanySupplyChainSite.verification_status == "verified_region",
                )
            )
            removed += existing_count
        for place, country_name, iso2 in parse_reported_geography(edge.geography or ""):
            area = _resolve_area(session, place=place, iso2=iso2, cache=area_cache)
            latitude = float(area.latitude) if area and area.latitude is not None else None
            longitude = float(area.longitude) if area and area.longitude is not None else None
            if area is not None:
                precision = "admin1_centroid" if area.level == "admin1" else "city_centroid"
                admin1_name = area.name if area.level == "admin1" else None
                mapped += 1
            else:
                precision = "unresolved"
                admin1_name = place
                unresolved += 1
            session.add(
                CompanySupplyChainSite(
                    edge_id=edge.id,
                    subject_ticker=edge.subject_ticker,
                    related_company_name=edge.related_company_name,
                    related_ticker=edge.related_ticker,
                    site_kind="manufacturing_region",
                    site_name=place,
                    country_name=country_name,
                    country_iso2=iso2,
                    admin1_name=admin1_name,
                    latitude=latitude,
                    longitude=longitude,
                    coordinate_precision=precision,
                    verification_status="verified_region",
                    association_scope="issuer_reported_manufacturing_region",
                    source_kind=edge.source_kind,
                    source_ref=edge.source_ref,
                    source_url=edge.source_url,
                    source_excerpt=(
                        f"Issuer source reports {place}, {country_name} as a manufacturing "
                        "location. This verifies a region, not an exact factory coordinate."
                    ),
                    observed_at=edge.observed_at,
                    available_at=edge.available_at,
                )
            )
            inserted += 1
    session.flush()
    return {
        "edges_scanned": len(edges),
        "sites_replaced": removed,
        "sites_inserted": inserted,
        "coordinate_mapped": mapped,
        "coordinate_unresolved": unresolved,
    }


def supply_chain_site_exposure(
    session: Session,
    *,
    ticker: str,
    as_of: date,
    weeks: int = 12,
    limit: int = 500,
) -> dict[str, Any]:
    """Join reviewed locations to nearby conflict, disaster, power and port signals."""
    normalized_ticker = ticker.strip().upper()
    all_sites = list(
        session.scalars(
            select(CompanySupplyChainSite)
            .where(
                or_(
                    CompanySupplyChainSite.subject_ticker == normalized_ticker,
                    and_(
                        CompanySupplyChainSite.related_ticker == normalized_ticker,
                        CompanySupplyChainSite.verification_status == "verified_exact",
                    ),
                ),
                CompanySupplyChainSite.verification_status.in_(
                    ("verified_exact", "verified_region")
                ),
                CompanySupplyChainSite.available_at <= as_of,
            )
            .order_by(
                case(
                    (CompanySupplyChainSite.coordinate_precision == "exact_facility", 0),
                    (CompanySupplyChainSite.coordinate_precision == "city_centroid", 1),
                    (CompanySupplyChainSite.coordinate_precision == "admin1_centroid", 2),
                    else_=3,
                ),
                CompanySupplyChainSite.related_company_name,
                CompanySupplyChainSite.site_name,
            )
        )
    )
    sites = all_sites[:limit]
    period_start = as_of - timedelta(days=weeks * 7 - 1)
    geocoded = [
        item for item in sites if item.latitude is not None and item.longitude is not None
    ]
    country_codes = {item.country_iso2 for item in geocoded if item.country_iso2}
    conflicts = list(
        session.scalars(
            select(ConflictAggregateObservation).where(
                ConflictAggregateObservation.week >= period_start,
                ConflictAggregateObservation.week <= as_of,
            )
        )
    )
    conflicts_by_area: dict[tuple[str, str], list[ConflictAggregateObservation]] = (
        defaultdict(list)
    )
    for item in conflicts:
        conflict_iso2 = COUNTRY_ISO2.get(_normalize(item.country))
        conflicts_by_area[(conflict_iso2 or "", _normalize(item.admin1))].append(item)
    start_at = datetime.combine(period_start, time.min, tzinfo=UTC)
    end_at = datetime.combine(as_of + timedelta(days=1), time.min, tzinfo=UTC)
    event_conditions = [
        Event.start_at >= start_at,
        Event.start_at < end_at,
        Event.latitude.is_not(None),
        Event.longitude.is_not(None),
    ]
    if country_codes:
        event_conditions.append(
            or_(Event.country_code.in_(country_codes), Event.country_code.is_(None))
        )
    events = list(
        session.scalars(
            select(Event)
            .where(*event_conditions)
            .order_by(desc(Event.severity), desc(Event.start_at))
            .limit(5_000)
        )
    )
    events_by_country: dict[str | None, list[Event]] = defaultdict(list)
    for event in events:
        events_by_country[event.country_code].append(event)
    rows = [
        _site_exposure_row(
            site,
            context_ticker=normalized_ticker,
            conflicts=conflicts,
            conflicts_by_area=conflicts_by_area,
            events=events,
            events_by_country=events_by_country,
            period_start=period_start,
            period_end=as_of,
        )
        for site in sites
    ]
    rows.sort(
        key=lambda item: (
            item["exposure_attention_score"],
            item["coordinate_precision"] == "exact_facility",
        ),
        reverse=True,
    )
    return {
        "ticker": normalized_ticker,
        "as_of": as_of,
        "weeks": weeks,
        "period_start": period_start,
        "site_count": len(all_sites),
        "returned_site_count": len(sites),
        "geocoded_site_count": sum(
            item.latitude is not None and item.longitude is not None for item in all_sites
        ),
        "exact_facility_count": sum(
            item.coordinate_precision == "exact_facility" for item in all_sites
        ),
        "regional_location_count": sum(
            item.verification_status == "verified_region" for item in all_sites
        ),
        "company_facility_count": sum(
            item.related_ticker == normalized_ticker
            and item.verification_status == "verified_exact"
            for item in all_sites
        ),
        "supplier_location_count": sum(
            not (
                item.related_ticker == normalized_ticker
                and item.verification_status == "verified_exact"
            )
            for item in all_sites
        ),
        "conflict_exposed_count": sum(item["conflict_events"] > 0 for item in rows),
        "disaster_exposed_count": sum(item["disaster_event_count"] > 0 for item in rows),
        "power_signal_count": sum(item["power_signal_count"] > 0 for item in rows),
        "truncated": len(all_sites) > len(sites),
        "sites": rows,
        "methodology": (
            "The requested company receives its own source-reviewed exact facilities plus "
            "source-reviewed upstream supplier locations. Issuer-reported manufacturing "
            "regions are geocoded to local admin/city reference points. Conflict, disaster "
            "and power signals are proximity joins; the nearest port is a cartographic "
            "reference and not a confirmed route."
        ),
        "limitations": [
            "A region centroid is not an exact factory coordinate.",
            "Proximity does not prove operational disruption, dependency or lost output.",
            "Port proximity does not prove that the company uses that port.",
            "Power capacity, production volume, inventory buffers and alternate "
            "routes remain gaps.",
        ],
    }


def build_supply_chain_site_evidence(
    session: Session,
    *,
    ticker: str,
    as_of: date,
    weeks: int = 12,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Return bounded location evidence suitable for the local report context."""
    payload = supply_chain_site_exposure(
        session,
        ticker=ticker,
        as_of=as_of,
        weeks=weeks,
        limit=500,
    )
    result: list[dict[str, Any]] = []
    for item in payload["sites"][:limit]:
        result.append(
            {
                "evidence_id": f"supply-site:{item['site_id']}:{as_of.isoformat()}",
                "category": "supply_chain_site_exposure",
                **item,
                "as_of": as_of.isoformat(),
                "period_start": payload["period_start"].isoformat(),
                "methodology": payload["methodology"],
                "can_verify_claims": True,
            }
        )
    return result


def _site_exposure_row(
    site: CompanySupplyChainSite,
    *,
    context_ticker: str,
    conflicts: list[ConflictAggregateObservation],
    conflicts_by_area: dict[tuple[str, str], list[ConflictAggregateObservation]],
    events: list[Event],
    events_by_country: dict[str | None, list[Event]],
    period_start: date,
    period_end: date,
) -> dict[str, Any]:
    latitude = float(site.latitude) if site.latitude is not None else None
    longitude = float(site.longitude) if site.longitude is not None else None
    radius_km = 75.0 if site.coordinate_precision in {"exact_facility", "city_centroid"} else 250.0
    matched_conflicts: list[ConflictAggregateObservation] = []
    nearby_disasters: list[Event] = []
    nearby_power: list[Event] = []
    if latitude is not None and longitude is not None:
        site_admin = _normalize(site.admin1_name or site.site_name)
        exact_conflicts = conflicts_by_area.get((site.country_iso2 or "", site_admin), [])
        if exact_conflicts:
            matched_conflicts.extend(exact_conflicts)
        else:
            for item in conflicts:
                distance = _haversine_km(
                    latitude,
                    longitude,
                    float(item.latitude),
                    float(item.longitude),
                )
                if distance <= radius_km:
                    matched_conflicts.append(item)
        candidate_events = [
            *events_by_country.get(site.country_iso2, []),
            *events_by_country.get(None, []),
        ]
        if not candidate_events and site.country_iso2 is None:
            candidate_events = events
        for event in candidate_events:
            if event.latitude is None or event.longitude is None:
                continue
            distance = _haversine_km(
                latitude,
                longitude,
                float(event.latitude),
                float(event.longitude),
            )
            if distance > radius_km:
                continue
            searchable = f"{event.event_type} {event.title} {event.summary or ''}"
            if DISASTER_PATTERN.search(searchable):
                nearby_disasters.append(event)
            if POWER_PATTERN.search(searchable):
                nearby_power.append(event)
    conflict_events = sum(item.events for item in matched_conflicts)
    conflict_fatalities = sum(item.fatalities for item in matched_conflicts)
    disaster_severity = max((float(item.severity) for item in nearby_disasters), default=0.0)
    conflict_score = min(
        1.0,
        math.log1p(conflict_events) / math.log(101) * 0.45
        + math.log1p(conflict_fatalities) / math.log(251) * 0.55,
    )
    attention = min(
        1.0,
        conflict_score * 0.65
        + disaster_severity * 0.25
        + min(0.1, len(nearby_power) * 0.05),
    )
    port = (
        _nearest_port(latitude, longitude)
        if latitude is not None and longitude is not None
        else None
    )
    return {
        "site_id": site.id,
        "edge_id": site.edge_id,
        "context_ticker": context_ticker,
        "facility_role": (
            "company_facility"
            if site.related_ticker == context_ticker
            and site.verification_status == "verified_exact"
            else "upstream_supplier_location"
        ),
        "subject_ticker": site.subject_ticker,
        "related_company_name": site.related_company_name,
        "related_ticker": site.related_ticker,
        "site_kind": site.site_kind,
        "site_name": site.site_name,
        "country_name": site.country_name,
        "country_iso2": site.country_iso2,
        "admin1_name": site.admin1_name,
        "latitude": latitude,
        "longitude": longitude,
        "coordinate_precision": site.coordinate_precision,
        "verification_status": site.verification_status,
        "association_scope": site.association_scope,
        "source_ref": site.source_ref,
        "source_url": site.source_url,
        "source_excerpt": site.source_excerpt,
        "available_at": site.available_at.isoformat(),
        "exposure_radius_km": radius_km,
        "conflict_events": conflict_events,
        "conflict_fatalities": conflict_fatalities,
        "disaster_event_count": len(nearby_disasters),
        "disaster_events": [
            {
                "event_id": event.id,
                "title": event.title,
                "event_type": event.event_type,
                "start_at": event.start_at.isoformat(),
                "severity": float(event.severity),
            }
            for event in nearby_disasters[:3]
        ],
        "power_signal_count": len(nearby_power),
        "power_signals": [
            {
                "event_id": event.id,
                "title": event.title,
                "start_at": event.start_at.isoformat(),
            }
            for event in nearby_power[:3]
        ],
        "nearest_port": port,
        "port_route_status": "nearest_reference_not_confirmed" if port else "unavailable",
        "exposure_attention_score": round(attention, 4),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
    }


def _resolve_area(
    session: Session,
    *,
    place: str,
    iso2: str | None,
    cache: dict[str, list[AdministrativeArea]],
) -> AdministrativeArea | None:
    if not iso2 or _normalize(place) in {_normalize(name) for name in COUNTRY_ISO2}:
        return None
    if iso2 not in cache:
        cache[iso2] = list(
            session.scalars(
                select(AdministrativeArea).where(
                    AdministrativeArea.country_iso2 == iso2,
                    AdministrativeArea.latitude.is_not(None),
                    AdministrativeArea.longitude.is_not(None),
                )
            )
        )
    needle = _normalize(place)
    matches = [
        area
        for area in cache[iso2]
        if needle in {_normalize(area.name), _normalize(area.ascii_name or "")}
    ]
    if not matches:
        return None
    matches.sort(key=lambda area: (area.level != "admin1", -(area.population or 0)))
    return matches[0]


def _clean_country_name(value: str) -> str:
    normalized = _normalize(value)
    canonical = COUNTRY_ALIASES.get(normalized, normalized)
    return " ".join(part.capitalize() for part in canonical.split())


def _normalize(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value or "")
    ascii_value = "".join(character for character in folded if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", ascii_value.casefold()).strip()


@lru_cache(maxsize=1)
def _port_points() -> tuple[dict[str, Any], ...]:
    path = Path(__file__).resolve().parent / "web" / "data" / "ports.geojson"
    payload = json.loads(path.read_text(encoding="utf-8"))
    points: list[dict[str, Any]] = []
    for feature in payload.get("features", []):
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if geometry.get("type") != "Point" or len(coordinates) < 2:
            continue
        properties = feature.get("properties") or {}
        points.append(
            {
                "name": properties.get("name") or "Unnamed port",
                "longitude": float(coordinates[0]),
                "latitude": float(coordinates[1]),
                "website": properties.get("website"),
            }
        )
    return tuple(points)


def _nearest_port(latitude: float, longitude: float) -> dict[str, Any] | None:
    nearest: dict[str, Any] | None = None
    nearest_distance = math.inf
    for port in _port_points():
        distance = _haversine_km(
            latitude,
            longitude,
            port["latitude"],
            port["longitude"],
        )
        if distance < nearest_distance:
            nearest = port
            nearest_distance = distance
    if nearest is None or nearest_distance > 500:
        return None
    return {
        "name": nearest["name"],
        "latitude": nearest["latitude"],
        "longitude": nearest["longitude"],
        "distance_km": round(nearest_distance, 1),
        "website": nearest["website"],
    }


def _haversine_km(
    left_latitude: float,
    left_longitude: float,
    right_latitude: float,
    right_longitude: float,
) -> float:
    left_lat = math.radians(left_latitude)
    right_lat = math.radians(right_latitude)
    delta_lat = math.radians(right_latitude - left_latitude)
    delta_lon = math.radians(right_longitude - left_longitude)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(left_lat) * math.cos(right_lat) * math.sin(delta_lon / 2) ** 2
    )
    return 6371.0088 * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))
