"""Validated import of historical or delisted equity price series."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.db.models import MarketSeries
from app.market_history import _dialect_insert, _upsert_observations

REQUIRED_COLUMNS = {
    "series_id",
    "name",
    "observed_on",
    "close",
    "listing_status",
    "source_name",
    "source_url",
}
HISTORICAL_STATUSES = {"delisted", "historical"}


@dataclass(frozen=True, slots=True)
class SurvivorshipImportResult:
    """Auditable counts returned after one validated import."""

    series_upserted: int
    observations_upserted: int
    earliest: date | None
    latest: date | None
    delisting_returns_covered: int
    delisting_returns_missing: int


def import_survivorship_csv(session: Session, path: Path) -> SurvivorshipImportResult:
    """Import point-in-time history without allowing ticker reuse collisions."""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")
        rows = list(reader)
    if not rows:
        raise ValueError("survivorship CSV contains no data rows")

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        series_id = (row.get("series_id") or "").strip()
        if not series_id.startswith("HIST:"):
            raise ValueError("series_id must start with HIST: to prevent ticker reuse collisions")
        grouped.setdefault(series_id, []).append(row)

    fetched_at = datetime.now(UTC)
    observation_rows: list[dict[str, Any]] = []
    earliest: date | None = None
    latest: date | None = None
    covered = 0
    missing_returns = 0
    for series_id, series_rows in grouped.items():
        metadata = _parse_series_metadata(series_id, series_rows)
        observed_values = [_parse_observation(series_id, row, fetched_at) for row in series_rows]
        observed_values.sort(key=lambda row: row["observed_on"])
        first_observed = observed_values[0]["observed_on"]
        last_observed = observed_values[-1]["observed_on"]
        listed_from = metadata["listed_from"] or first_observed
        listed_until = metadata["listed_until"] or last_observed
        if listed_from > first_observed or listed_until < last_observed:
            raise ValueError(f"{series_id}: observations fall outside listing lifecycle")
        if listed_from > listed_until:
            raise ValueError(f"{series_id}: listed_from must not be after listed_until")
        metadata["listed_from"] = listed_from
        metadata["listed_until"] = listed_until
        _upsert_historical_series(session, metadata)
        observation_rows.extend(observed_values)
        earliest = first_observed if earliest is None else min(earliest, first_observed)
        latest = last_observed if latest is None else max(latest, last_observed)
        if metadata["delisting_return"] is None:
            missing_returns += 1
        else:
            covered += 1

    observations_upserted = _upsert_observations(session, observation_rows)
    return SurvivorshipImportResult(
        series_upserted=len(grouped),
        observations_upserted=observations_upserted,
        earliest=earliest,
        latest=latest,
        delisting_returns_covered=covered,
        delisting_returns_missing=missing_returns,
    )


def _parse_series_metadata(
    series_id: str,
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    first = rows[0]
    status = (first.get("listing_status") or "").strip().casefold()
    if status not in HISTORICAL_STATUSES:
        raise ValueError(f"{series_id}: listing_status must be delisted or historical")
    source_url = (first.get("source_url") or "").strip()
    if urlparse(source_url).scheme not in {"http", "https"}:
        raise ValueError(f"{series_id}: source_url must be HTTP(S)")
    name = (first.get("name") or "").strip()
    source_name = (first.get("source_name") or "").strip()
    if not name or not source_name:
        raise ValueError(f"{series_id}: name and source_name are required")
    stable_fields = (
        "name",
        "listing_status",
        "source_name",
        "source_url",
        "sector",
        "region",
        "neutralization_group",
        "listed_from",
        "listed_until",
        "delisting_return",
    )
    expected = {field: (first.get(field) or "").strip() for field in stable_fields}
    for row in rows[1:]:
        actual = {field: (row.get(field) or "").strip() for field in stable_fields}
        if actual != expected:
            raise ValueError(f"{series_id}: lifecycle metadata must be constant across rows")
    delisting_return = _optional_float(first.get("delisting_return"))
    if delisting_return is not None and not -1.0 <= delisting_return <= 10.0:
        raise ValueError(f"{series_id}: delisting_return is outside the accepted range")
    sector = (first.get("sector") or "Unclassified historical equity").strip()
    region = (first.get("region") or "north_america").strip()
    neutralization_group = (first.get("neutralization_group") or f"industry:{sector}").strip()
    return {
        "series_id": series_id,
        "name": name,
        "category": "historical_equity_price",
        "unit": (first.get("currency") or "USD").strip(),
        "frequency": "daily",
        "source_name": source_name,
        "source_url": source_url,
        "listing_status": status,
        "listed_from": _optional_date(first.get("listed_from")),
        "listed_until": _optional_date(first.get("listed_until")),
        "delisting_return": delisting_return,
        "sector": sector,
        "region": region,
        "neutralization_group": neutralization_group,
    }


def _parse_observation(
    series_id: str,
    row: dict[str, str],
    fetched_at: datetime,
) -> dict[str, Any]:
    observed_on = date.fromisoformat((row.get("observed_on") or "").strip())
    value = float((row.get("close") or "").strip())
    if value <= 0:
        raise ValueError(f"{series_id}: close must be positive on {observed_on}")
    return {
        "series_id": series_id,
        "observed_on": observed_on,
        "value": value,
        "fetched_at": fetched_at,
    }


def _upsert_historical_series(session: Session, values: dict[str, Any]) -> None:
    insert = _dialect_insert(session, MarketSeries)
    statement = insert.values(values)
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[MarketSeries.series_id],
            set_={
                field: getattr(statement.excluded, field)
                for field in values
                if field != "series_id"
            },
        )
    )


def _optional_date(value: str | None) -> date | None:
    text = (value or "").strip()
    return date.fromisoformat(text) if text else None


def _optional_float(value: str | None) -> float | None:
    text = (value or "").strip()
    return float(text) if text else None
