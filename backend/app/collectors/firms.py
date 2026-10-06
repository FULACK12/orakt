"""NASA FIRMS thermal-anomaly collection and map-safe aggregation."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import math
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors.rss import document_hash
from app.db.enums import DocumentStance, EventStatus, SourceType
from app.db.models import Document, Event, EventDocument, Source
from app.storage.archive import ColdArchive

FIRMS_API_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
FIRMS_DOCUMENTATION_URL = (
    "https://firms.modaps.eosdis.nasa.gov/content/academy/"
    "data_api/firms_api_use.html"
)
FIRMS_MAP_URL = "https://firms.modaps.eosdis.nasa.gov/map/"
FIRMS_LICENSE_NAME = "NASA Earth Science Data and Information Policy"
FIRMS_LICENSE_URL = "https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-information-policy"


class FIRMSCollectionResult(BaseModel):
    """Safe accounting for one NASA FIRMS collection pass."""

    model_config = ConfigDict(extra="forbid")

    source: str
    area: str
    history_days: int = Field(ge=1, le=5)
    detections_seen: int = Field(default=0, ge=0)
    invalid_detections: int = Field(default=0, ge=0)
    clusters_built: int = Field(default=0, ge=0)
    events_created: int = Field(default=0, ge=0)
    events_updated: int = Field(default=0, ge=0)
    raw_archive_path: str | None = None


class FIRMSCollector:
    """Collect FIRMS observations without logging or persisting the map key."""

    def __init__(
        self,
        client: httpx.Client,
        *,
        map_key: str,
        source: str,
        area: str = "world",
        history_days: int = 1,
        grid_degrees: float = 0.25,
        max_clusters: int = 1_500,
        archive: ColdArchive | None = None,
    ) -> None:
        if not map_key.strip():
            raise ValueError("NASA FIRMS map key is required")
        if not source.strip():
            raise ValueError("NASA FIRMS source is required")
        if not 1 <= history_days <= 5:
            raise ValueError("NASA FIRMS history_days must be between 1 and 5")
        if not 0.05 <= grid_degrees <= 2:
            raise ValueError("NASA FIRMS grid_degrees must be between 0.05 and 2")
        if max_clusters < 1:
            raise ValueError("NASA FIRMS max_clusters must be positive")
        self.client = client
        self.map_key = map_key
        self.source = source.strip()
        self.area = area.strip()
        self.history_days = history_days
        self.grid_degrees = grid_degrees
        self.max_clusters = max_clusters
        self.archive = archive

    def collect(self, session: Session) -> FIRMSCollectionResult:
        """Fetch, archive, aggregate and persist map-ready thermal anomalies."""
        response = self.client.get(
            f"{FIRMS_API_BASE}/{quote(self.map_key, safe='')}/"
            f"{quote(self.source, safe='')}/{quote(self.area, safe=',-')}/"
            f"{self.history_days}"
        )
        response.raise_for_status()
        detections, invalid = parse_firms_csv(response.text)
        result = FIRMSCollectionResult(
            source=self.source,
            area=self.area,
            history_days=self.history_days,
            detections_seen=len(detections),
            invalid_detections=invalid,
        )
        if self.archive is not None and response.content:
            result.raw_archive_path = _archive_response(
                self.archive,
                source=self.source,
                payload=response.content,
            )
        clusters = aggregate_detections(
            detections,
            grid_degrees=self.grid_degrees,
            limit=self.max_clusters,
        )
        result.clusters_built = len(clusters)
        source_record = _get_or_create_source(session, self.source)
        for cluster in clusters:
            created = _upsert_cluster(
                session,
                source=source_record,
                dataset=self.source,
                cluster=cluster,
                raw_archive_path=result.raw_archive_path,
            )
            if created:
                result.events_created += 1
            else:
                result.events_updated += 1
        session.commit()
        return result


def parse_firms_csv(payload: str) -> tuple[list[dict[str, Any]], int]:
    """Parse FIRMS CSV while retaining only defensible numeric fields."""
    reader = csv.DictReader(io.StringIO(payload.lstrip("\ufeff")))
    required = {"latitude", "longitude", "acq_date"}
    if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
        raise ValueError("NASA FIRMS CSV is missing required columns")
    detections: list[dict[str, Any]] = []
    invalid = 0
    for row in reader:
        try:
            latitude = float(row["latitude"])
            longitude = float(row["longitude"])
            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                raise ValueError("coordinate out of range")
            observed_at = _acquisition_datetime(
                row["acq_date"],
                row.get("acq_time"),
            )
        except (TypeError, ValueError):
            invalid += 1
            continue
        detections.append(
            {
                "latitude": latitude,
                "longitude": longitude,
                "observed_at": observed_at,
                "frp": _optional_float(row.get("frp")) or 0.0,
                "confidence": _confidence(row.get("confidence")),
                "satellite": _text(row.get("satellite")),
                "instrument": _text(row.get("instrument")),
                "daynight": _text(row.get("daynight")),
                "type": _text(row.get("type")),
            }
        )
    return detections, invalid


def aggregate_detections(
    detections: list[dict[str, Any]],
    *,
    grid_degrees: float,
    limit: int,
) -> list[dict[str, Any]]:
    """Aggregate dense points into dated grid cells suitable for a world map."""
    grouped: dict[tuple[date, int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in detections:
        observed_at = row["observed_at"]
        lat_cell = math.floor((row["latitude"] + 90) / grid_degrees)
        lon_cell = math.floor((row["longitude"] + 180) / grid_degrees)
        grouped[(observed_at.date(), lat_cell, lon_cell)].append(row)
    clusters: list[dict[str, Any]] = []
    for (observed_on, _, _), rows in grouped.items():
        count = len(rows)
        total_weight = sum(max(1.0, row["frp"]) for row in rows)
        latitude = sum(
            row["latitude"] * max(1.0, row["frp"]) for row in rows
        ) / total_weight
        longitude = sum(
            row["longitude"] * max(1.0, row["frp"]) for row in rows
        ) / total_weight
        max_frp = max(row["frp"] for row in rows)
        mean_frp = sum(row["frp"] for row in rows) / count
        confidence = sum(row["confidence"] for row in rows) / count
        severity = min(
            1.0,
            0.12
            + math.log1p(count) / 10
            + math.log1p(max_frp) / 12,
        )
        clusters.append(
            {
                "observed_on": observed_on,
                "lat_cell": lat_cell,
                "lon_cell": lon_cell,
                "grid_degrees": grid_degrees,
                "start_at": min(row["observed_at"] for row in rows),
                "end_at": max(row["observed_at"] for row in rows),
                "latitude": latitude,
                "longitude": longitude,
                "detection_count": count,
                "max_frp": max_frp,
                "mean_frp": mean_frp,
                "confidence": min(0.95, max(0.35, confidence)),
                "severity": severity,
                "satellites": sorted(
                    {row["satellite"] for row in rows if row["satellite"]}
                ),
                "instruments": sorted(
                    {row["instrument"] for row in rows if row["instrument"]}
                ),
            }
        )
    clusters.sort(
        key=lambda row: (
            row["severity"],
            row["detection_count"],
            row["max_frp"],
        ),
        reverse=True,
    )
    return clusters[:limit]


def _upsert_cluster(
    session: Session,
    *,
    source: Source,
    dataset: str,
    cluster: dict[str, Any],
    raw_archive_path: str | None,
) -> bool:
    observed_on = cluster["observed_on"].isoformat()
    latitude = float(cluster["latitude"])
    longitude = float(cluster["longitude"])
    map_latitude = (
        -90
        + (int(cluster["lat_cell"]) + 0.5)
        * float(cluster["grid_degrees"])
    )
    map_longitude = (
        -180
        + (int(cluster["lon_cell"]) + 0.5)
        * float(cluster["grid_degrees"])
    )
    grid_key = (
        f"{int(cluster['lat_cell'])}:{int(cluster['lon_cell'])}:"
        f"{float(cluster['grid_degrees']):.3f}"
    )
    url = (
        f"{FIRMS_MAP_URL}#d:{observed_on};@{map_longitude:.4f},"
        f"{map_latitude:.4f},10z;g:{quote(grid_key, safe='')}"
    )
    count = int(cluster["detection_count"])
    max_frp = float(cluster["max_frp"])
    title = (
        f"NASA FIRMS thermal-anomaly cluster · {count} detections · "
        f"{grid_key}"
    )
    summary = (
        f"Satellite instruments reported {count} thermal-anomaly detections "
        f"in this {observed_on} grid cell. Maximum fire radiative power was "
        f"{max_frp:.2f} MW. A FIRMS thermal anomaly is not, by itself, proof "
        "of a wildfire, attack, industrial accident or damage."
    )
    body = (
        f"{summary}\nDataset: {dataset}. Instruments: "
        f"{', '.join(cluster['instruments']) or 'not specified'}."
    )
    metadata = {
        "collector": "nasa_firms_area",
        "dataset": dataset,
        "classification": "satellite_thermal_anomaly",
        "interpretation_limit": "not_confirmed_fire_or_damage",
        "detection_count": count,
        "max_frp_mw": max_frp,
        "mean_frp_mw": float(cluster["mean_frp"]),
        "satellites": cluster["satellites"],
        "instruments": cluster["instruments"],
        "grid_degrees": float(cluster["grid_degrees"]),
        "raw_archive_path": raw_archive_path,
        "documentation_url": FIRMS_DOCUMENTATION_URL,
        "license_name": FIRMS_LICENSE_NAME,
        "license_url": FIRMS_LICENSE_URL,
    }
    digest = document_hash(title, body)
    document = session.scalar(select(Document).where(Document.url == url))
    created = document is None
    if document is None:
        document = Document(
            source=source,
            url=url,
            title=title,
            body=body,
            language="en",
            published_at=cluster["end_at"],
            content_hash=digest,
            credibility_score=Decimal("0.900"),
            raw_object_path=raw_archive_path,
            raw_metadata=metadata,
        )
        session.add(document)
        session.flush()
        event = Event(
            event_type="thermal_anomaly",
            title=title,
            summary=summary,
            status=EventStatus.PARTIALLY_CONFIRMED,
            severity=Decimal(f"{cluster['severity']:.3f}"),
            novelty=Decimal("0.500"),
            confidence=Decimal(f"{cluster['confidence']:.3f}"),
            start_at=cluster["start_at"],
            end_at=cluster["end_at"],
            latitude=Decimal(f"{latitude:.6f}"),
            longitude=Decimal(f"{longitude:.6f}"),
            country_code=None,
        )
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
        return True
    document.title = title
    document.body = body
    document.published_at = cluster["end_at"]
    document.content_hash = digest
    document.raw_object_path = raw_archive_path
    document.raw_metadata = metadata
    existing_event = session.scalar(
        select(Event)
        .join(EventDocument)
        .where(EventDocument.document_id == document.id)
        .limit(1)
    )
    if existing_event is not None:
        existing_event.title = title
        existing_event.summary = summary
        existing_event.severity = Decimal(f"{cluster['severity']:.3f}")
        existing_event.confidence = Decimal(f"{cluster['confidence']:.3f}")
        existing_event.start_at = cluster["start_at"]
        existing_event.end_at = cluster["end_at"]
        existing_event.latitude = Decimal(f"{latitude:.6f}")
        existing_event.longitude = Decimal(f"{longitude:.6f}")
    return created


def _get_or_create_source(session: Session, dataset: str) -> Source:
    name = f"NASA FIRMS {dataset}"
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
        ownership="NASA / U.S. Forest Service",
        credibility_baseline=Decimal("0.900"),
        political_bias_metadata={
            "kind": "satellite_thermal_anomaly_api",
            "dataset": dataset,
            "documentation_url": FIRMS_DOCUMENTATION_URL,
            "license_name": FIRMS_LICENSE_NAME,
            "license_url": FIRMS_LICENSE_URL,
            "interpretation_limit": "thermal_anomaly_not_confirmed_fire",
        },
    )
    session.add(source)
    session.flush()
    return source


def _archive_response(
    archive: ColdArchive,
    *,
    source: str,
    payload: bytes,
) -> str:
    digest = hashlib.sha256(payload).hexdigest()
    observed_on = datetime.now(UTC)
    relative = (
        f"raw/firms/{observed_on:%Y/%m/%d}/"
        f"{source}-{digest[:20]}.csv.gz"
    )
    return archive.store_bytes(
        relative,
        gzip.compress(payload, compresslevel=6, mtime=0),
    )


def _acquisition_datetime(date_value: str, time_value: str | None) -> datetime:
    observed_on = date.fromisoformat(str(date_value).strip())
    digits = "".join(character for character in str(time_value or "0000") if character.isdigit())
    digits = digits.zfill(4)[-4:]
    hour = int(digits[:2])
    minute = int(digits[2:])
    if hour > 23 or minute > 59:
        raise ValueError("invalid FIRMS acquisition time")
    return datetime(
        observed_on.year,
        observed_on.month,
        observed_on.day,
        hour,
        minute,
        tzinfo=UTC,
    )


def _confidence(value: Any) -> float:
    normalized = str(value or "").strip().casefold()
    if normalized in {"h", "high"}:
        return 0.90
    if normalized in {"n", "nominal"}:
        return 0.72
    if normalized in {"l", "low"}:
        return 0.45
    numeric = _optional_float(value)
    if numeric is None:
        return 0.60
    return min(0.95, max(0.35, numeric / 100))


def _optional_float(value: Any) -> float | None:
    try:
        parsed = float(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _text(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None
