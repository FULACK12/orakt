"""Assemble canonical and non-persistent candidate layers for the map UI."""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.cluster_review import verify_cluster_preview
from app.clustering import source_event_anchors
from app.core.text import repair_common_mojibake
from app.db.enums import ClusterJobStatus
from app.db.models import (
    AdministrativeArea,
    ClusterJob,
    CountryProfile,
    Document,
    Event,
    EventDocument,
    LogicChainHypothesis,
)
from app.schemas.cluster_jobs import ClusterJobResult
from app.schemas.extractions import ImpactEstimate
from app.schemas.map_data import (
    ConflictMovementVector,
    ConflictSituationZone,
    EarthquakeWave,
    GeolocationPrecision,
    MapDataResponse,
    MapEventMarker,
    ReviewCategory,
)

EARTHQUAKE_SERIES_WINDOW = timedelta(hours=48)
EARTHQUAKE_SERIES_RADIUS_KM = 120.0
DEFAULT_MAP_HISTORY_WINDOW = timedelta(days=366)
MAP_CANONICAL_MARKER_LIMIT = 2_500
MAP_CANDIDATE_JOB_LIMIT = 8
MAP_CANDIDATE_MARKER_LIMIT = 1_500
EARTHQUAKE_MAGNITUDE_PATTERN = re.compile(
    r"\b(?:M|Magnitude)\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


class MapDataConflictError(RuntimeError):
    """Stored clustering data cannot safely be shown."""


def build_map_data(
    session: Session,
    *,
    review_secret: str,
) -> MapDataResponse:
    """Return canonical events and geolocated, unlinked AI candidates."""
    conflict_area_cache: dict[str, list[AdministrativeArea]] = {}
    canonical_markers = _canonical_markers(
        session,
        conflict_area_cache=conflict_area_cache,
    )
    completed_jobs = (
        ClusterJob.status == ClusterJobStatus.COMPLETED,
        ClusterJob.result.is_not(None),
    )
    jobs = list(
        session.scalars(
            select(ClusterJob)
            .where(*completed_jobs)
            .order_by(
                ClusterJob.completed_at.desc(),
                ClusterJob.id.desc(),
            )
            .limit(MAP_CANDIDATE_JOB_LIMIT)
        )
    )
    latest_job = jobs[0] if jobs else None
    candidate_markers_by_id: dict[str, MapEventMarker] = {}
    for job in jobs:
        if job.result is None:
            continue
        result = ClusterJobResult.model_validate(job.result)
        if not verify_cluster_preview(result.preview, review_secret):
            raise MapDataConflictError(
                "stored cluster preview signature is invalid"
            )
        for marker in _candidate_markers(
            session,
            job.id,
            result,
            conflict_area_cache=conflict_area_cache,
        ):
            # Jobs are newest-first. Stable candidate IDs let a newer rerun
            # replace the same extraction. Unreviewed candidates are bounded
            # to recent batches; accepted events remain in canonical history.
            candidate_markers_by_id.setdefault(marker.id, marker)
    candidate_markers = sorted(
        candidate_markers_by_id.values(),
        key=lambda marker: (
            _utc_timestamp(marker.occurred_at),
            marker.severity,
            marker.confidence,
            marker.id,
        ),
        reverse=True,
    )[:MAP_CANDIDATE_MARKER_LIMIT]
    markers = _aggregate_earthquake_series(
        [*canonical_markers, *candidate_markers]
    )
    _annotate_conflict_theaters(markers)
    conflict_zones, conflict_movements = _build_conflict_situations(markers)
    return MapDataResponse(
        generated_at=datetime.now(UTC),
        latest_cluster_job_id=latest_job.id if latest_job is not None else None,
        latest_logic_job_id=session.scalar(
            select(func.max(LogicChainHypothesis.cluster_job_id))
        ),
        canonical_count=sum(marker.kind == "canonical" for marker in markers),
        candidate_count=sum(marker.kind == "candidate" for marker in markers),
        markers=markers,
        conflict_zones=conflict_zones,
        conflict_movements=conflict_movements,
    )


def _canonical_markers(
    session: Session,
    *,
    conflict_area_cache: dict[str, list[AdministrativeArea]] | None = None,
) -> list[MapEventMarker]:
    country_profiles = _country_profiles_by_iso2(session)
    latest_event_at = session.scalar(select(func.max(Event.start_at)))
    history_cutoff = (
        latest_event_at - DEFAULT_MAP_HISTORY_WINDOW
        if latest_event_at is not None
        else None
    )
    event_query = select(Event).options(
        selectinload(Event.document_links)
        .selectinload(EventDocument.document)
        .selectinload(Document.source)
    )
    if history_cutoff is not None:
        event_query = event_query.where(Event.start_at >= history_cutoff)
    events = list(
        session.scalars(
            event_query.order_by(Event.start_at.desc(), Event.id.desc()).limit(
                MAP_CANONICAL_MARKER_LIMIT
            )
        )
    )
    markers: list[MapEventMarker] = []
    for event in events:
        if not event.document_links:
            continue
        latitude, longitude, precision, resolved_country = _resolve_coordinates(
            latitude=float(event.latitude) if event.latitude is not None else None,
            longitude=float(event.longitude) if event.longitude is not None else None,
            country_code=event.country_code,
            location_name=None,
            country_profiles=country_profiles,
            country_profiles_by_name={},
            administrative_areas_by_name={},
        )
        if latitude is None or longitude is None:
            continue
        link = next(
            (
                item
                for item in event.document_links
                if item.is_primary_source
            ),
            event.document_links[0],
        )
        document = link.document
        precision = _canonical_precision(document, fallback=precision)
        is_conflict = _is_conflict_event(
            event.event_type,
            event.title,
            event.summary,
        )
        if (
            is_conflict
            and precision == "country"
            and resolved_country
            and not _is_ucdp_document(document)
        ):
            inferred_area = _infer_conflict_area_from_text(
                session,
                country_code=resolved_country,
                text=(
                    f"{event.title} {event.summary or ''} "
                    f"{repair_common_mojibake(document.body or '')[:5_000]}"
                ),
                cache=conflict_area_cache,
            )
            if (
                inferred_area is not None
                and inferred_area.latitude is not None
                and inferred_area.longitude is not None
            ):
                latitude = float(inferred_area.latitude)
                longitude = float(inferred_area.longitude)
                precision = (
                    "city" if inferred_area.level == "city" else "admin1"
                )
        markers.append(
            MapEventMarker(
                id=f"canonical:{event.id}",
                kind="canonical",
                event_id=event.id,
                document_id=document.id,
                title=event.title,
                summary=event.summary,
                event_type=event.event_type,
                is_conflict=is_conflict,
                actors=_canonical_actors(document),
                impact=_canonical_impact(document, confidence=float(event.confidence)),
                latitude=latitude,
                longitude=longitude,
                geolocation_precision=precision,
                country_code=resolved_country,
                occurred_at=event.start_at,
                published_at=document.published_at,
                confidence=float(event.confidence),
                severity=float(event.severity),
                status=event.status,
                source_name=document.source.name,
                source_url=_canonical_source_url(document),
            )
        )
    return markers


def _canonical_impact(
    document: Document,
    *,
    confidence: float,
) -> ImpactEstimate | None:
    metadata = document.raw_metadata
    if metadata.get("collector") != "ucdp_gedevents":
        return None
    try:
        return ImpactEstimate(
            fatalities_low=max(0, int(metadata.get("fatalities_low") or 0)),
            fatalities_best=max(0, int(metadata.get("fatalities_best") or 0)),
            fatalities_high=max(0, int(metadata.get("fatalities_high") or 0)),
            confidence=max(0, min(1, confidence)),
        )
    except (TypeError, ValueError):
        return None


def _canonical_actors(document: Document) -> list[str]:
    """Retain named conflict parties from structured source metadata."""
    metadata = document.raw_metadata or {}
    actors: list[str] = []
    for key in ("side_a", "side_b", "actor", "actors"):
        value = metadata.get(key)
        values = value if isinstance(value, list) else [value]
        for item in values:
            actor = repair_common_mojibake(str(item or "")).strip()
            if (
                actor
                and actor.casefold() not in {"unknown", "none", "nan"}
                and actor not in actors
            ):
                actors.append(actor[:255])
    return actors[:12]


def _is_ucdp_document(document: Document) -> bool:
    return document.raw_metadata.get("collector") == "ucdp_gedevents"


def _canonical_source_url(document: Document) -> str:
    """Use a public provenance page instead of a token-protected API URL."""
    if not _is_ucdp_document(document):
        return document.url
    citation_url = document.raw_metadata.get("citation_url")
    return str(citation_url) if citation_url else document.url


def _canonical_precision(
    document: Document,
    *,
    fallback: GeolocationPrecision,
) -> GeolocationPrecision:
    """Preserve UCDP's stated spatial precision for mapped conflict events."""
    if not _is_ucdp_document(document):
        return fallback
    try:
        where_precision = int(str(document.raw_metadata.get("where_prec")))
    except (TypeError, ValueError):
        return fallback
    if where_precision <= 1:
        return "point"
    if where_precision == 2:
        return "city"
    if where_precision <= 4:
        return "admin1"
    return "country"


def _candidate_markers(
    session: Session,
    job_id: int,
    result: ClusterJobResult,
    *,
    conflict_area_cache: dict[str, list[AdministrativeArea]] | None = None,
) -> list[MapEventMarker]:
    country_profiles = _country_profiles_by_iso2(session)
    country_profiles_by_name = _country_profiles_by_name(country_profiles)
    linked_document_ids = set(
        session.scalars(select(EventDocument.document_id))
    )
    document_ids = {
        member.document_id
        for cluster in result.preview.clusters
        for member in cluster.members
        if member.document_id not in linked_document_ids
    }
    documents = list(
        session.scalars(
            select(Document)
            .where(Document.id.in_(document_ids))
            .options(selectinload(Document.source))
        )
    )
    documents_by_id = {document.id: document for document in documents}
    location_names = {
        member.event.location.name
        for cluster in result.preview.clusters
        for member in cluster.members
        if member.event.location is not None
    }
    administrative_areas_by_name = _administrative_areas_by_name(
        session,
        location_names,
    )
    category_by_cluster = _review_categories(result)
    markers: list[MapEventMarker] = []
    for cluster in result.preview.clusters:
        category = category_by_cluster[cluster.cluster_id]
        for candidate in cluster.members:
            document = documents_by_id.get(candidate.document_id)
            if document is None:
                continue
            anchors = source_event_anchors(
                document.title,
                document.body or "",
            )
            location = candidate.event.location
            latitude = (
                anchors[1]
                if anchors[1] is not None
                else location.latitude if location is not None else None
            )
            longitude = (
                anchors[2]
                if anchors[2] is not None
                else location.longitude if location is not None else None
            )
            country_code = (
                location.country_code
                if location is not None
                else None
            )
            inferred_country = _infer_country_from_text(
                repair_common_mojibake(
                    f"{candidate.event.title} {candidate.event.summary}"
                ),
                country_profiles=country_profiles,
            )
            latitude, longitude, precision, country_code = _resolve_coordinates(
                latitude=latitude,
                longitude=longitude,
                country_code=country_code or inferred_country,
                location_name=location.name if location is not None else None,
                country_profiles=country_profiles,
                country_profiles_by_name=country_profiles_by_name,
                administrative_areas_by_name=administrative_areas_by_name,
            )
            if latitude is None or longitude is None:
                continue
            display_title = repair_common_mojibake(candidate.event.title)
            display_summary = repair_common_mojibake(candidate.event.summary)
            is_conflict = _is_conflict_event(
                candidate.event.event_type,
                display_title,
                display_summary,
            )
            if is_conflict and precision == "country" and country_code:
                inferred_area = _infer_conflict_area_from_text(
                    session,
                    country_code=country_code,
                    text=(
                        f"{display_title} {display_summary} "
                        f"{repair_common_mojibake(document.body or '')[:5_000]}"
                    ),
                    cache=conflict_area_cache,
                )
                if (
                    inferred_area is not None
                    and inferred_area.latitude is not None
                    and inferred_area.longitude is not None
                ):
                    latitude = float(inferred_area.latitude)
                    longitude = float(inferred_area.longitude)
                    precision = (
                        "city" if inferred_area.level == "city" else "admin1"
                    )
            occurred_at = (
                anchors[0]
                or candidate.event.occurred_at
                or document.published_at
                or document.fetched_at
            )
            markers.append(
                MapEventMarker(
                    id=f"candidate:{candidate.candidate_id}",
                    kind="candidate",
                    cluster_job_id=job_id,
                    cluster_id=cluster.cluster_id,
                    document_id=document.id,
                    title=display_title,
                    summary=display_summary,
                    event_type=candidate.event.event_type,
                    is_conflict=is_conflict,
                    actors=_canonical_actors(document),
                    impact=candidate.event.impact,
                    latitude=latitude,
                    longitude=longitude,
                    geolocation_precision=precision,
                    country_code=country_code,
                    occurred_at=occurred_at,
                    published_at=document.published_at,
                    confidence=candidate.event.confidence,
                    severity=candidate.event.severity,
                    status=None,
                    review_category=category,
                    source_name=document.source.name,
                    source_url=document.url,
                )
            )
    return markers


def _country_profiles_by_iso2(
    session: Session,
) -> dict[str, CountryProfile]:
    profiles = session.scalars(
        select(CountryProfile).where(
            CountryProfile.latitude.is_not(None),
            CountryProfile.longitude.is_not(None),
        )
    )
    return {profile.iso2.upper(): profile for profile in profiles}


def _resolve_coordinates(
    *,
    latitude: float | None,
    longitude: float | None,
    country_code: str | None,
    location_name: str | None,
    country_profiles: dict[str, CountryProfile],
    country_profiles_by_name: dict[str, CountryProfile],
    administrative_areas_by_name: dict[str, AdministrativeArea],
) -> tuple[
    float | None,
    float | None,
    GeolocationPrecision,
    str | None,
]:
    if latitude is not None and longitude is not None:
        return latitude, longitude, "point", country_code
    profile = (
        country_profiles.get(country_code.upper())
        if country_code
        else None
    )
    if profile is None and location_name:
        profile = country_profiles_by_name.get(
            _normalized_place_name(location_name)
        )
    if (
        profile is not None
        and profile.latitude is not None
        and profile.longitude is not None
    ):
        return (
            float(profile.latitude),
            float(profile.longitude),
            "country",
            profile.iso2,
        )
    if location_name:
        area = administrative_areas_by_name.get(
            _normalized_place_name(location_name)
        )
        if (
            area is not None
            and area.latitude is not None
            and area.longitude is not None
        ):
            precision: GeolocationPrecision = (
                "city" if area.level == "city" else "admin1"
            )
            return (
                float(area.latitude),
                float(area.longitude),
                precision,
                area.country_iso2,
            )
    return None, None, "point", country_code


def _country_profiles_by_name(
    profiles_by_iso2: dict[str, CountryProfile],
) -> dict[str, CountryProfile]:
    profiles = {
        _normalized_place_name(profile.name): profile
        for profile in profiles_by_iso2.values()
    }
    aliases = {
        "bolivia": "BO",
        "democratic republic of the congo": "CD",
        "dr congo": "CD",
        "rdc": "CD",
        "gaza": "PS",
        "gaza strip": "PS",
        "iran": "IR",
        "ivory coast": "CI",
        "laos": "LA",
        "palestine": "PS",
        "russia": "RU",
        "south korea": "KR",
        "syria": "SY",
        "taiwan": "TW",
        "venezuela": "VE",
        "west bank": "PS",
    }
    for name, iso2 in aliases.items():
        profile = profiles_by_iso2.get(iso2)
        if profile is not None:
            profiles[name] = profile
    return profiles


def _administrative_areas_by_name(
    session: Session,
    location_names: set[str],
) -> dict[str, AdministrativeArea]:
    normalized_names = {
        _normalized_place_name(name)
        for name in location_names
        if name.strip()
    }
    if not normalized_names:
        return {}
    rows = list(
        session.scalars(
            select(AdministrativeArea).where(
                AdministrativeArea.latitude.is_not(None),
                AdministrativeArea.longitude.is_not(None),
                or_(
                    func.lower(AdministrativeArea.name).in_(normalized_names),
                    func.lower(AdministrativeArea.ascii_name).in_(
                        normalized_names
                    ),
                ),
            )
        )
    )
    grouped: dict[str, list[AdministrativeArea]] = {}
    for row in rows:
        for name in {row.name, row.ascii_name}:
            if name:
                grouped.setdefault(
                    _normalized_place_name(name),
                    [],
                ).append(row)
    return {
        name: matches[0]
        for name, matches in grouped.items()
        if len({match.id for match in matches}) == 1
    }


def _normalized_place_name(value: str) -> str:
    return " ".join(value.casefold().split())


def _infer_country_from_text(
    text: str,
    *,
    country_profiles: dict[str, CountryProfile],
) -> str | None:
    normalized = f" {_normalized_place_name(text)} "
    aliases = {
        "أوكرانيا": "UA",
        "السودان": "SD",
        "هايتي": "HT",
        "china": "CN",
        "cyprus": "CY",
        "democratic republic of the congo": "CD",
        "dr congo": "CD",
        "haïti": "HT",
        "haití": "HT",
        "gaza": "PS",
        "gaza strip": "PS",
        "iran": "IR",
        "israel": "IL",
        "lebanon": "LB",
        "palestine": "PS",
        "russia": "RU",
        "rdc": "CD",
        "soudan": "SD",
        "sudán": "SD",
        "sudan": "SD",
        "syria": "SY",
        "ukraine": "UA",
        "ucrania": "UA",
        "украина": "UA",
        "west bank": "PS",
        "yemen": "YE",
    }
    scores: dict[str, int] = {}
    stripped = normalized.strip()
    for alias, iso2 in aliases.items():
        if iso2 not in country_profiles:
            continue
        token = f" {alias} "
        if token not in normalized and not stripped.startswith(f"{alias}:"):
            continue
        score = 1
        if stripped.startswith(f"{alias}:"):
            score = 3
        elif any(
            phrase in normalized
            for phrase in (
                f" in {alias} ",
                f" on {alias} ",
                f" across {alias} ",
                f" amid {alias} ",
                f" au {alias} ",
                f" en {alias} ",
                f" à {alias} ",
                f" في {alias} ",
            )
        ):
            score = 2
        scores[iso2] = max(scores.get(iso2, 0), score)
    if not scores:
        return None
    best = max(scores.values())
    winners = [iso2 for iso2, score in scores.items() if score == best]
    return winners[0] if best >= 2 and len(winners) == 1 else None


def _review_categories(
    result: ClusterJobResult,
) -> dict[int, ReviewCategory]:
    merge_ids = set(result.merge_cluster_ids)
    review_ids = set(result.review_cluster_ids)
    return {
        cluster.cluster_id: (
            "merge"
            if cluster.cluster_id in merge_ids
            else "review"
            if cluster.cluster_id in review_ids
            else "independent"
        )
        for cluster in result.preview.clusters
    }


def _is_conflict_event(
    event_type: str,
    title: str,
    summary: str | None,
) -> bool:
    normalized_type = event_type.lower()
    conflict_types = {
        "airstrike",
        "armed_clash",
        "armed_conflict",
        "battle",
        "bombardment",
        "bombing",
        "civil_war",
        "drone_strike",
        "invasion",
        "military_attack",
        "military_operation",
        "missile_strike",
        "non_state_conflict",
        "one_sided_violence",
        "shelling",
        "state_based_conflict",
        "war",
    }
    if normalized_type in conflict_types:
        return True
    text = f"{title} {summary or ''}".lower()
    conflict_phrases = (
        "air strike",
        "airstrike",
        "armed clash",
        "artillery fire",
        "bombardment",
        "drone strike",
        "missile strike",
        "shelling",
        "战区",
        "战争",
        "武装冲突",
        "空袭",
        "轰炸",
        "炮击",
        "导弹袭击",
    )
    return any(phrase in text for phrase in conflict_phrases)


def _infer_conflict_area_from_text(
    session: Session,
    *,
    country_code: str,
    text: str,
    cache: dict[str, list[AdministrativeArea]] | None,
) -> AdministrativeArea | None:
    """Resolve a reported city/admin name before falling back to a country."""
    area_cache = cache if cache is not None else {}
    code = country_code.upper()
    areas = area_cache.get(code)
    if areas is None:
        areas = list(
            session.scalars(
                select(AdministrativeArea)
                .where(
                    AdministrativeArea.country_iso2 == code,
                    AdministrativeArea.latitude.is_not(None),
                    AdministrativeArea.longitude.is_not(None),
                )
                .order_by(
                    AdministrativeArea.population.desc().nullslast(),
                    AdministrativeArea.level.desc(),
                )
            )
        )
        area_cache[code] = areas
    normalized = repair_common_mojibake(text).casefold()
    matches: list[tuple[int, int, AdministrativeArea]] = []
    for area in areas:
        names = {area.name, area.ascii_name}
        for raw_name in names:
            name = (raw_name or "").strip().casefold()
            if len(name) < 4:
                continue
            if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", normalized):
                matches.append(
                    (
                        len(name),
                        int(area.population or 0),
                        area,
                    )
                )
    return max(matches, default=(0, 0, None), key=lambda item: item[:2])[2]


def _annotate_conflict_theaters(markers: list[MapEventMarker]) -> None:
    """Add conservative, explicitly inferred conflict-density annotations."""
    conflicts = [marker for marker in markers if marker.is_conflict]
    for marker in conflicts:
        if marker.geolocation_precision == "country":
            marker.conflict_zone_role = "location_unconfirmed"
            marker.theater_confidence = 0.2
        else:
            marker.conflict_zone_role = "reported_site"
            marker.theater_confidence = min(
                0.75,
                0.35 + marker.confidence * 0.2 + marker.severity * 0.2,
            )

    by_country: dict[str, list[MapEventMarker]] = {}
    for marker in conflicts:
        if (
            marker.country_code
            and marker.geolocation_precision != "country"
        ):
            by_country.setdefault(marker.country_code.upper(), []).append(marker)
    for country_markers in by_country.values():
        density: dict[str, int] = {}
        for marker in country_markers:
            nearby_sources = {
                other.source_name
                for other in country_markers
                if abs(
                    (
                        _utc_timestamp(marker.occurred_at)
                        - _utc_timestamp(other.occurred_at)
                    ).total_seconds()
                ) <= timedelta(days=7).total_seconds()
                and _coordinate_distance_km(
                    marker.latitude,
                    marker.longitude,
                    other.latitude,
                    other.longitude,
                ) <= 250
            }
            density[marker.id] = len(nearby_sources)
        maximum_density = max(density.values(), default=1)
        for marker in country_markers:
            count = density[marker.id]
            if maximum_density >= 3 and count == maximum_density:
                marker.conflict_zone_role = "primary_theater"
            elif count >= 2:
                marker.conflict_zone_role = "secondary_theater"
            marker.theater_confidence = min(
                0.75,
                float(marker.theater_confidence or 0.35) + 0.05 * (count - 1),
            )



def _build_conflict_situations(
    markers: list[MapEventMarker],
) -> tuple[list[ConflictSituationZone], list[ConflictMovementVector]]:
    """Build local theater footprints and cautious reported-activity shifts."""
    by_country: dict[str, list[MapEventMarker]] = {}
    for marker in markers:
        if (
            marker.is_conflict
            and marker.country_code
            and marker.geolocation_precision != "country"
        ):
            by_country.setdefault(
                marker.country_code.upper(),
                [],
            ).append(marker)

    zones: list[ConflictSituationZone] = []
    for country_code, country_markers in sorted(by_country.items()):
        components = _spatiotemporal_conflict_components(country_markers)
        country_zones = [
            _conflict_zone(
                country_code,
                component,
                index=index,
            )
            for index, component in enumerate(components, start=1)
        ]
        ranked = sorted(
            country_zones,
            key=lambda zone: (
                zone.urgency_score,
                zone.event_count,
                zone.source_count,
                zone.end_at,
            ),
            reverse=True,
        )
        for rank, zone in enumerate(ranked):
            role: Literal["primary_theater", "secondary_theater", "reported_site"]
            if rank == 0 and (
                zone.event_count >= 3 or zone.source_count >= 2
            ):
                role = "primary_theater"
            elif zone.event_count >= 2 or zone.source_count >= 2:
                role = "secondary_theater"
            else:
                role = "reported_site"
            zone.role = role
            for marker in country_markers:
                if marker.id not in zone.marker_ids:
                    continue
                marker.conflict_zone_role = role
                marker.theater_confidence = zone.confidence
        zones.extend(country_zones)

    movements = _reported_activity_movements(zones)
    marker_by_id = {marker.id: marker for marker in markers}
    for movement in movements:
        for marker_id in movement.marker_ids:
            movement_marker = marker_by_id.get(marker_id)
            if (
                movement_marker is not None
                and movement_marker.occurred_at == movement.end_at
            ):
                movement_marker.advance_direction = movement.direction
    return zones, movements


def _spatiotemporal_conflict_components(
    markers: list[MapEventMarker],
) -> list[list[MapEventMarker]]:
    """Greedy local clusters bounded by 150 km and a 45-day span.

    A centroid/anchor bound avoids the chaining failure of connected-component
    clustering, where a corridor of reports could color an entire country.
    """
    components: list[list[MapEventMarker]] = []
    for marker in sorted(
        markers,
        key=lambda item: _utc_timestamp(item.occurred_at),
    ):
        eligible: list[tuple[float, list[MapEventMarker]]] = []
        for component in components:
            earliest = _utc_timestamp(component[0].occurred_at)
            if _utc_timestamp(marker.occurred_at) - earliest > timedelta(days=45):
                continue
            latitude = sum(item.latitude for item in component) / len(component)
            longitude = sum(item.longitude for item in component) / len(component)
            centroid_distance = _coordinate_distance_km(
                latitude,
                longitude,
                marker.latitude,
                marker.longitude,
            )
            anchor_distance = _coordinate_distance_km(
                component[0].latitude,
                component[0].longitude,
                marker.latitude,
                marker.longitude,
            )
            if centroid_distance <= 150 and anchor_distance <= 180:
                eligible.append((centroid_distance, component))
        if eligible:
            min(eligible, key=lambda item: item[0])[1].append(marker)
        else:
            components.append([marker])
    return components


def _conflict_zone(
    country_code: str,
    markers: list[MapEventMarker],
    *,
    index: int,
) -> ConflictSituationZone:
    weights = [
        max(0.15, marker.confidence * (0.5 + marker.severity))
        for marker in markers
    ]
    total_weight = sum(weights)
    latitude = sum(
        marker.latitude * weight
        for marker, weight in zip(markers, weights, strict=True)
    ) / total_weight
    longitude = sum(
        marker.longitude * weight
        for marker, weight in zip(markers, weights, strict=True)
    ) / total_weight
    maximum_distance = max(
        _coordinate_distance_km(
            latitude,
            longitude,
            marker.latitude,
            marker.longitude,
        )
        for marker in markers
    )
    source_count = len({marker.source_name for marker in markers})
    actors = sorted(
        {
            actor
            for marker in markers
            for actor in marker.actors
        }
    )[:12]
    fatalities = sum(
        marker.impact.fatalities_best
        for marker in markers
        if marker.impact is not None
        and marker.impact.fatalities_best is not None
    )
    maximum_severity = max(marker.severity for marker in markers)
    urgency = min(
        1,
        maximum_severity * 0.45
        + min(1, len(markers) / 8) * 0.25
        + min(1, source_count / 4) * 0.15
        + min(1, math.log10(fatalities + 1) / 3) * 0.15,
    )
    confidence = min(
        0.75,
        0.28
        + min(0.2, source_count * 0.06)
        + min(0.15, len(markers) * 0.025)
        + sum(marker.confidence for marker in markers)
        / len(markers)
        * 0.12,
    )
    ordered = sorted(
        markers,
        key=lambda marker: _utc_timestamp(marker.occurred_at),
    )
    representative_markers = sorted(
        markers,
        key=lambda marker: (
            marker.severity,
            marker.confidence,
            _utc_timestamp(marker.occurred_at),
            marker.id,
        ),
        reverse=True,
    )[:250]
    representative_ids = {
        marker.id for marker in representative_markers
    }
    return ConflictSituationZone(
        id=f"conflict-zone:{country_code}:{index}",
        country_code=country_code,
        role="reported_site",
        latitude=latitude,
        longitude=longitude,
        radius_km=max(10, min(220, maximum_distance + 24)),
        urgency_score=round(urgency, 4),
        confidence=round(confidence, 4),
        event_count=len(markers),
        source_count=source_count,
        actors=actors,
        fatalities_best=fatalities or None,
        start_at=ordered[0].occurred_at,
        end_at=ordered[-1].occurred_at,
        # The zone retains full aggregate counts, while the browser receives a
        # bounded, deterministic set of representative evidence points.
        marker_ids=[
            marker.id for marker in ordered if marker.id in representative_ids
        ],
    )


def _reported_activity_movements(
    zones: list[ConflictSituationZone],
) -> list[ConflictMovementVector]:
    """Infer only actor-linked shifts between dated report clusters."""
    by_country: dict[str, list[ConflictSituationZone]] = {}
    for zone in zones:
        by_country.setdefault(zone.country_code, []).append(zone)
    movements: list[ConflictMovementVector] = []
    for country_code, country_zones in sorted(by_country.items()):
        ordered = sorted(country_zones, key=lambda zone: zone.end_at)
        for index, (origin, target) in enumerate(pairwise(ordered), start=1):
            gap = _utc_timestamp(target.start_at) - _utc_timestamp(origin.end_at)
            if gap < timedelta(0) or gap > timedelta(days=60):
                continue
            shared_actors = sorted(set(origin.actors) & set(target.actors))
            if not shared_actors:
                continue
            distance = _coordinate_distance_km(
                origin.latitude,
                origin.longitude,
                target.latitude,
                target.longitude,
            )
            if distance < 25 or distance > 600:
                continue
            direction = _compass_direction(
                origin.latitude,
                origin.longitude,
                target.latitude,
                target.longitude,
            )
            movements.append(
                ConflictMovementVector(
                    id=f"conflict-shift:{country_code}:{index}",
                    country_code=country_code,
                    actor=shared_actors[0],
                    from_latitude=origin.latitude,
                    from_longitude=origin.longitude,
                    to_latitude=target.latitude,
                    to_longitude=target.longitude,
                    direction=direction,
                    distance_km=round(distance, 2),
                    start_at=origin.end_at,
                    end_at=target.start_at,
                    confidence=round(
                        min(
                            0.6,
                            0.22
                            + min(origin.confidence, target.confidence) * 0.35
                            + min(0.15, len(shared_actors) * 0.05),
                        ),
                        4,
                    ),
                    evidence_count=origin.event_count + target.event_count,
                    marker_ids=[
                        *origin.marker_ids,
                        *target.marker_ids,
                    ][:250],
                )
            )
    return movements


def _compass_direction(
    origin_latitude: float,
    origin_longitude: float,
    target_latitude: float,
    target_longitude: float,
) -> str:
    north = target_latitude - origin_latitude
    east = (
        (target_longitude - origin_longitude)
        * math.cos(math.radians((origin_latitude + target_latitude) / 2))
    )
    bearing = (math.degrees(math.atan2(east, north)) + 360) % 360
    labels = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    return labels[int((bearing + 22.5) // 45) % 8]


def _aggregate_earthquake_series(
    markers: list[MapEventMarker],
) -> list[MapEventMarker]:
    """Group nearby waves while retaining every distinct source observation."""
    earthquakes = sorted(
        (
            marker
            for marker in markers
            if marker.event_type.casefold() == "earthquake"
        ),
        key=lambda marker: _utc_timestamp(marker.occurred_at),
    )
    other_markers = [
        marker
        for marker in markers
        if marker.event_type.casefold() != "earthquake"
    ]
    groups: list[list[MapEventMarker]] = []
    for marker in earthquakes:
        eligible: list[tuple[float, list[MapEventMarker]]] = []
        for group in groups:
            anchor = group[0]
            last = group[-1]
            if (
                _utc_timestamp(marker.occurred_at)
                - _utc_timestamp(last.occurred_at)
                > EARTHQUAKE_SERIES_WINDOW
            ):
                continue
            distance = _coordinate_distance_km(
                marker.latitude,
                marker.longitude,
                anchor.latitude,
                anchor.longitude,
            )
            if distance <= EARTHQUAKE_SERIES_RADIUS_KM:
                eligible.append((distance, group))
        if eligible:
            min(eligible, key=lambda item: item[0])[1].append(marker)
        else:
            groups.append([marker])

    series_markers = [_earthquake_series_marker(group) for group in groups]
    return sorted(
        [*other_markers, *series_markers],
        key=lambda marker: _utc_timestamp(marker.occurred_at),
        reverse=True,
    )


def _earthquake_series_marker(
    markers: list[MapEventMarker],
) -> MapEventMarker:
    representative = max(
        markers,
        key=lambda marker: (
            _earthquake_magnitude(marker.title) or -1.0,
            marker.severity,
            marker.confidence,
        ),
    )
    waves = [
        EarthquakeWave(
            marker_id=marker.id,
            document_id=marker.document_id,
            title=marker.title,
            occurred_at=marker.occurred_at,
            magnitude=_earthquake_magnitude(marker.title),
            latitude=marker.latitude,
            longitude=marker.longitude,
            source_name=marker.source_name,
            source_url=marker.source_url,
        )
        for marker in sorted(
            markers,
            key=lambda item: _utc_timestamp(item.occurred_at),
        )
    ]
    return representative.model_copy(
        update={
            "series_count": len(waves),
            "series_start_at": waves[0].occurred_at,
            "series_end_at": waves[-1].occurred_at,
            "series_events": waves,
        }
    )


def _earthquake_magnitude(title: str) -> float | None:
    match = EARTHQUAKE_MAGNITUDE_PATTERN.search(title)
    return float(match.group(1)) if match else None


def _utc_timestamp(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=UTC)
        if value.tzinfo is None
        else value.astimezone(UTC)
    )


def _coordinate_distance_km(
    left_latitude: float,
    left_longitude: float,
    right_latitude: float,
    right_longitude: float,
) -> float:
    left_lat = math.radians(left_latitude)
    right_lat = math.radians(right_latitude)
    delta_lat = right_lat - left_lat
    delta_lon = math.radians(right_longitude - left_longitude)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(left_lat)
        * math.cos(right_lat)
        * math.sin(delta_lon / 2) ** 2
    )
    return 6_371 * 2 * math.atan2(
        math.sqrt(haversine),
        math.sqrt(1 - haversine),
    )
