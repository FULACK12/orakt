"""Download, archive and selectively materialize official EIA bulk data."""

from __future__ import annotations

import hashlib
import heapq
import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zipfile import BadZipFile, ZipFile

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from app.db.models import EnergyObservation, EnergySeries, EnergySyncState
from app.storage.archive import ColdArchive

EIA_BULK_MANIFEST_URL = "https://api.eia.gov/bulk/manifest.txt"
EIA_DOCUMENTATION_URL = "https://www.eia.gov/opendata/documentation.php"
EIA_LICENSE_NAME = "U.S. Government public data"
EIA_LICENSE_URL = "https://www.eia.gov/about/copyrights_reuse.php"

FREQUENCY_NAMES = {
    "A": "annual",
    "Q": "quarterly",
    "M": "monthly",
    "W": "weekly",
    "D": "daily",
    "H": "hourly",
}
FOCUS_TERMS = (
    "capacity",
    "coal",
    "consumption",
    "crude",
    "demand",
    "diesel",
    "electricity",
    "emission",
    "export",
    "gasoline",
    "generation",
    "import",
    "inventory",
    "jet fuel",
    "natural gas",
    "nuclear",
    "petroleum",
    "price",
    "production",
    "refinery",
    "renewable",
    "reserve",
    "solar",
    "stock",
    "storage",
    "supply",
    "wind",
)


class EIABulkDatasetResult(BaseModel):
    """Safe accounting for one EIA bulk archive."""

    model_config = ConfigDict(extra="forbid")

    dataset_key: str
    archive_path: str | None = None
    archive_bytes: int = Field(default=0, ge=0)
    downloaded: bool = False
    series_cataloged: int = Field(default=0, ge=0)
    series_materialized: int = Field(default=0, ge=0)
    observations_upserted: int = Field(default=0, ge=0)
    error: str | None = None


class EIABulkSyncResult(BaseModel):
    """Accounting for one manifest-driven EIA synchronization."""

    model_config = ConfigDict(extra="forbid")

    manifest_updated_at: datetime
    datasets: list[EIABulkDatasetResult]


def sync_eia_bulk(
    session: Session,
    client: httpx.Client,
    *,
    archive: ColdArchive,
    dataset_keys: list[str],
    max_series_per_dataset: int,
    max_observations_per_series: int,
    force_download: bool = False,
) -> EIABulkSyncResult:
    """Synchronize selected public bulk archives without an EIA API key."""
    if not dataset_keys:
        raise ValueError("at least one EIA bulk dataset is required")
    if max_series_per_dataset < 1 or max_observations_per_series < 1:
        raise ValueError("EIA materialization limits must be positive")
    response = client.get(EIA_BULK_MANIFEST_URL)
    response.raise_for_status()
    manifest = response.json()
    datasets = manifest.get("dataset")
    if not isinstance(datasets, dict):
        raise TypeError("EIA manifest must contain a dataset object")
    _archive_manifest(archive.root, response.content)

    results: list[EIABulkDatasetResult] = []
    for requested_key in dataset_keys:
        dataset_key = requested_key.strip().upper()
        if not dataset_key:
            continue
        metadata = datasets.get(dataset_key)
        if not isinstance(metadata, dict):
            results.append(
                EIABulkDatasetResult(
                    dataset_key=dataset_key,
                    error="dataset_not_found_in_manifest",
                )
            )
            continue
        source_url = str(metadata.get("accessURL") or "").strip()
        if not source_url.startswith("https://"):
            results.append(
                EIABulkDatasetResult(
                    dataset_key=dataset_key,
                    error="manifest_has_no_https_archive",
                )
            )
            continue
        state = _get_or_create_state(
            session,
            dataset_key=dataset_key,
            source_url=source_url,
        )
        state.last_started_at = datetime.now(UTC)
        state.last_error = None
        session.commit()
        try:
            archive_path, downloaded = _download_archive(
                client,
                archive=archive,
                source_url=source_url,
                force=force_download,
            )
            digest = _sha256_file(archive_path)
            imported = _import_archive(
                session,
                dataset_key=dataset_key,
                source_url=source_url,
                archive_path=archive_path,
                max_series=max_series_per_dataset,
                max_observations=max_observations_per_series,
            )
            state = _get_or_create_state(
                session,
                dataset_key=dataset_key,
                source_url=source_url,
            )
            state.source_last_updated = _optional_text(metadata.get("last_updated"))
            state.archive_path = archive_path.relative_to(archive.root).as_posix()
            state.archive_sha256 = digest
            state.archive_bytes = archive_path.stat().st_size
            state.series_cataloged = imported["series_cataloged"]
            state.series_materialized = imported["series_materialized"]
            state.observations_upserted = imported["observations_upserted"]
            state.last_success_at = datetime.now(UTC)
            state.last_error = None
            session.commit()
            results.append(
                EIABulkDatasetResult(
                    dataset_key=dataset_key,
                    archive_path=state.archive_path,
                    archive_bytes=state.archive_bytes,
                    downloaded=downloaded,
                    series_cataloged=state.series_cataloged,
                    series_materialized=state.series_materialized,
                    observations_upserted=state.observations_upserted,
                )
            )
        except (BadZipFile, OSError, TypeError, ValueError, httpx.HTTPError) as exc:
            session.rollback()
            state = _get_or_create_state(
                session,
                dataset_key=dataset_key,
                source_url=source_url,
            )
            state.last_error = f"{type(exc).__name__}: {str(exc)[:500]}"
            session.commit()
            results.append(
                EIABulkDatasetResult(
                    dataset_key=dataset_key,
                    error=type(exc).__name__,
                )
            )
    return EIABulkSyncResult(
        manifest_updated_at=datetime.now(UTC),
        datasets=results,
    )


def _download_archive(
    client: httpx.Client,
    *,
    archive: ColdArchive,
    source_url: str,
    force: bool,
) -> tuple[Path, bool]:
    filename = Path(urlparse(source_url).path).name
    if not filename.lower().endswith(".zip") or not filename:
        raise ValueError("EIA archive URL must end in .zip")
    destination = archive.root / "raw" / "eia" / filename
    if destination.is_file() and destination.stat().st_size > 0 and not force:
        return destination, False
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(f"{destination.suffix}.part")
    with client.stream("GET", source_url) as response:
        response.raise_for_status()
        content_length = int(response.headers.get("content-length") or 0)
        archive.ensure_capacity(content_length)
        try:
            with temporary.open("wb") as output:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            if temporary.stat().st_size == 0:
                raise ValueError("EIA archive download was empty")
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()
    return destination, True


def _import_archive(
    session: Session,
    *,
    dataset_key: str,
    source_url: str,
    archive_path: Path,
    max_series: int,
    max_observations: int,
) -> dict[str, int]:
    catalog_count = 0
    catalog_batch: list[dict[str, Any]] = []
    selected: list[tuple[float, str, dict[str, Any]]] = []
    with ZipFile(archive_path) as zipped:
        members = [
            member
            for member in zipped.namelist()
            if member.lower().endswith((".txt", ".json", ".jsonl"))
            and not member.endswith("/")
        ]
        if not members:
            raise ValueError("EIA archive has no JSON-lines member")
        for member in members:
            with zipped.open(member) as lines:
                for raw_line in lines:
                    row = json.loads(raw_line)
                    if not isinstance(row, dict) or not row.get("series_id"):
                        continue
                    series_id = str(row["series_id"])[:255]
                    data = row.get("data")
                    observation_count = len(data) if isinstance(data, list) else 0
                    score = _materialization_score(row)
                    if score > 0:
                        candidate = (score, series_id, row)
                        if len(selected) < max_series:
                            heapq.heappush(selected, candidate)
                        elif candidate[:2] > selected[0][:2]:
                            heapq.heapreplace(selected, candidate)
                    catalog_batch.append(
                        _series_catalog_row(
                            row,
                            dataset_key=dataset_key,
                            source_url=source_url,
                            observation_count=observation_count,
                        )
                    )
                    catalog_count += 1
                    if len(catalog_batch) >= 1_000:
                        _upsert_energy_series(session, catalog_batch)
                        catalog_batch.clear()
        if catalog_batch:
            _upsert_energy_series(session, catalog_batch)
    selected_rows = [row for _, _, row in sorted(selected, reverse=True)]
    selected_ids = [str(row["series_id"])[:255] for row in selected_rows]
    session.execute(
        delete(EnergyObservation).where(
            EnergyObservation.series_id.in_(
                select(EnergySeries.series_id).where(
                    EnergySeries.dataset_key == dataset_key
                )
            )
        )
    )
    session.execute(
        update(EnergySeries)
        .where(EnergySeries.dataset_key == dataset_key)
        .values(materialized=False)
    )
    if selected_ids:
        session.execute(
            update(EnergySeries)
            .where(EnergySeries.series_id.in_(selected_ids))
            .values(materialized=True)
        )
    fetched_at = datetime.now(UTC)
    observation_batch: list[dict[str, Any]] = []
    observations_upserted = 0
    for row in selected_rows:
        series_id = str(row["series_id"])[:255]
        data = row.get("data")
        if not isinstance(data, list):
            continue
        for observation in data[:max_observations]:
            parsed = _observation_row(
                observation,
                series_id=series_id,
                fetched_at=fetched_at,
            )
            if parsed is None:
                continue
            observation_batch.append(parsed)
            observations_upserted += 1
            if len(observation_batch) >= 5_000:
                session.execute(insert(EnergyObservation), observation_batch)
                observation_batch.clear()
    if observation_batch:
        session.execute(insert(EnergyObservation), observation_batch)
    session.commit()
    return {
        "series_cataloged": catalog_count,
        "series_materialized": len(selected_ids),
        "observations_upserted": observations_upserted,
    }


def _series_catalog_row(
    row: dict[str, Any],
    *,
    dataset_key: str,
    source_url: str,
    observation_count: int,
) -> dict[str, Any]:
    return {
        "series_id": str(row["series_id"])[:255],
        "dataset_key": dataset_key,
        "name": str(row.get("name") or row["series_id"])[:4_000],
        "units": _optional_text(row.get("units"), limit=255),
        "frequency": FREQUENCY_NAMES.get(
            str(row.get("f") or "").upper(),
            _optional_text(row.get("f"), limit=32),
        ),
        "start_period": _optional_text(row.get("start"), limit=32),
        "end_period": _optional_text(row.get("end"), limit=32),
        "last_updated_at": _parse_datetime(row.get("last_updated")),
        "observation_count": observation_count,
        "materialized": False,
        "source_url": source_url,
        "series_metadata": {
            "dataset": dataset_key,
            "eia_frequency_code": row.get("f"),
            "copyright": row.get("copyright"),
            "iso3166": row.get("iso3166"),
            "geography": row.get("geography"),
            "license_name": EIA_LICENSE_NAME,
            "license_url": EIA_LICENSE_URL,
            "documentation_url": EIA_DOCUMENTATION_URL,
        },
    }


def _upsert_energy_series(
    session: Session,
    rows: list[dict[str, Any]],
) -> None:
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as postgresql_insert

        statement: Any = postgresql_insert(EnergySeries).values(rows)
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        statement = sqlite_insert(EnergySeries).values(rows)
    else:
        for row in rows:
            session.merge(EnergySeries(**row))
        return
    update_values = {
        column: getattr(statement.excluded, column)
        for column in (
            "dataset_key",
            "name",
            "units",
            "frequency",
            "start_period",
            "end_period",
            "last_updated_at",
            "observation_count",
            "source_url",
            "series_metadata",
        )
    }
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[EnergySeries.series_id],
            set_=update_values,
        )
    )


def _materialization_score(row: dict[str, Any]) -> float:
    name = str(row.get("name") or "").casefold()
    data = row.get("data")
    if not isinstance(data, list) or len(data) < 2:
        return 0
    score = min(8, sum(term in name for term in FOCUS_TERMS)) * 2.0
    frequency = str(row.get("f") or "").upper()
    score += {"D": 2.0, "W": 2.0, "M": 2.5, "Q": 1.5, "A": 1.0}.get(
        frequency,
        0.0,
    )
    if any(term in name for term in ("total", "world", "united states")):
        score += 1.0
    if any(term in name for term in ("forecast", "projection", "outlook")):
        score += 0.5
    score += min(2.0, math.log10(max(10, len(data))) / 2)
    return score


def _observation_row(
    observation: Any,
    *,
    series_id: str,
    fetched_at: datetime,
) -> dict[str, Any] | None:
    if not isinstance(observation, list | tuple) or len(observation) < 2:
        return None
    period = str(observation[0]).strip()[:32]
    if not period:
        return None
    try:
        value = float(observation[1])
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return {
        "series_id": series_id,
        "period": period,
        "value": value,
        "fetched_at": fetched_at,
    }


def _get_or_create_state(
    session: Session,
    *,
    dataset_key: str,
    source_url: str,
) -> EnergySyncState:
    state = session.get(EnergySyncState, dataset_key)
    if state is None:
        state = EnergySyncState(dataset_key=dataset_key, source_url=source_url)
        session.add(state)
        session.flush()
    else:
        state.source_url = source_url
    return state


def _archive_manifest(root: Path, payload: bytes) -> None:
    destination = root / "raw" / "eia" / "manifest.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.part")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_datetime(value: Any) -> datetime | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _optional_text(value: Any, *, limit: int = 4_000) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized[:limit] if normalized else None
