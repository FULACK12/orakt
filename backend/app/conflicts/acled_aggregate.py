"""Stream authenticated ACLED aggregate workbooks into local storage."""

from __future__ import annotations

import hashlib
import re
from calendar import month_name
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.db.models import (
    ConflictAggregateObservation,
    ConflictAggregateSyncState,
    ConflictCountryIndicatorObservation,
)

SHEET_PATH = "xl/worksheets/sheet1.xml"
SHARED_STRINGS_PATH = "xl/sharedStrings.xml"
XML_NAMESPACE = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
EXCEL_EPOCH = date(1899, 12, 30)
POLITICAL_VIOLENCE_EVENT_TYPES = {
    "Battles",
    "Explosions/Remote violence",
    "Violence against civilians",
}
EXPECTED_HEADERS = (
    "WEEK",
    "REGION",
    "COUNTRY",
    "ADMIN1",
    "EVENT_TYPE",
    "SUB_EVENT_TYPE",
    "EVENTS",
    "FATALITIES",
    "POPULATION_EXPOSURE",
    "DISORDER_TYPE",
    "ID",
    "CENTROID_LATITUDE",
    "CENTROID_LONGITUDE",
)
ACLED_COUNTRY_HISTORY_PRODUCTS = 6
COUNTRY_HISTORY_METRICS = {
    "number_of_political_violence_events_by_country-month-year": (
        "political_violence_events",
        "monthly",
    ),
    "number_of_political_violence_events_by_country-year": (
        "political_violence_events",
        "annual",
    ),
    "number_of_demonstration_events_by_country-year": (
        "demonstration_events",
        "annual",
    ),
    "number_of_reported_fatalities_by_country-year": (
        "reported_fatalities",
        "annual",
    ),
    "number_of_reported_civilian_fatalities_from_direct_targeting_by_country-year": (
        "reported_civilian_fatalities_direct_targeting",
        "annual",
    ),
    # The authenticated download page describes the direct-targeting scope,
    # while the published workbook filename omits that phrase.
    "number_of_reported_civilian_fatalities_by_country-year": (
        "reported_civilian_fatalities_direct_targeting",
        "annual",
    ),
    "number_of_events_targeting_civilians_by_country-year": (
        "events_targeting_civilians",
        "annual",
    ),
}


class ACLEDWorkbookImportResult(BaseModel):
    """Safe accounting for one workbook import."""

    model_config = ConfigDict(extra="forbid")

    source_file: str
    skipped_unchanged: bool = False
    rows_seen: int = Field(default=0, ge=0)
    rows_imported: int = Field(default=0, ge=0)
    source_max_week: date | None = None
    error: str | None = None


def import_acled_directory(
    session: Session,
    *,
    directory: Path,
    history_days: int,
) -> list[ACLEDWorkbookImportResult]:
    """Import every authenticated regional workbook in a directory."""
    if history_days < 28:
        raise ValueError("ACLED aggregate history must be at least 28 days")
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    results: list[ACLEDWorkbookImportResult] = []
    for path in sorted(directory.glob("*.xlsx")):
        try:
            results.append(
                import_acled_workbook(
                    session,
                    path=path,
                    history_days=history_days,
                )
            )
        except (BadZipFile, OSError, TypeError, ValueError) as exc:
            session.rollback()
            results.append(
                ACLEDWorkbookImportResult(
                    source_file=path.name,
                    error=f"{type(exc).__name__}: {str(exc)[:300]}",
                )
            )
    history_directory = directory / "history"
    if history_directory.is_dir():
        results.extend(
            import_acled_country_history_directory(
                session,
                directory=history_directory,
            )
        )
    return results


def import_acled_country_history_directory(
    session: Session,
    *,
    directory: Path,
) -> list[ACLEDWorkbookImportResult]:
    """Import every account-authorized ACLED country history workbook."""
    results: list[ACLEDWorkbookImportResult] = []
    for path in sorted(directory.glob("*.xlsx")):
        try:
            results.append(import_acled_country_history_workbook(session, path=path))
        except (BadZipFile, OSError, TypeError, ValueError) as exc:
            session.rollback()
            results.append(
                ACLEDWorkbookImportResult(
                    source_file=path.name,
                    error=f"{type(exc).__name__}: {str(exc)[:300]}",
                )
            )
    return results


def import_acled_country_history_workbook(
    session: Session,
    *,
    path: Path,
) -> ACLEDWorkbookImportResult:
    """Stream one country-year or country-month workbook into local history."""
    metric, frequency = _country_history_definition(path.name)
    digest = _sha256_file(path)
    state = session.get(ConflictAggregateSyncState, path.name)
    if state is not None and state.archive_sha256 == digest and state.last_success_at:
        return ACLEDWorkbookImportResult(
            source_file=path.name,
            skipped_unchanged=True,
            rows_seen=state.rows_seen,
            rows_imported=state.rows_imported,
            source_max_week=state.source_max_week,
        )
    started_at = datetime.now(UTC)
    if state is None:
        state = ConflictAggregateSyncState(
            source_file=path.name,
            archive_sha256=digest,
        )
        session.add(state)
    state.archive_sha256 = digest
    state.last_started_at = started_at
    state.last_error = None
    session.flush()

    rows_seen = 0
    rows_imported = 0
    max_period: date | None = None
    batch: list[dict[str, Any]] = []
    with ZipFile(path) as zipped:
        if SHEET_PATH not in zipped.namelist() or SHARED_STRINGS_PATH not in zipped.namelist():
            raise ValueError("ACLED history workbook is missing worksheet or shared strings")
        strings = _read_shared_strings(zipped)
        row_iterator = _iter_sheet_rows(zipped, strings)
        raw_headers = next(row_iterator, None)
        headers = tuple(value for value in (raw_headers or []) if value is not None)
        value_header = "FATALITIES" if "fatalities" in metric else "EVENTS"
        expected_headers = (
            ("COUNTRY", "MONTH", "YEAR", value_header)
            if frequency == "monthly"
            else ("COUNTRY", "YEAR", value_header)
        )
        if headers[: len(expected_headers)] != expected_headers:
            raise ValueError("unexpected ACLED country history workbook schema")
        for values in row_iterator:
            rows_seen += 1
            parsed = _parse_country_history_row(
                values,
                metric=metric,
                frequency=frequency,
                source_file=path.name,
                imported_at=started_at,
            )
            if parsed is None:
                continue
            max_period = max(max_period or parsed["period"], parsed["period"])
            batch.append(parsed)
            rows_imported += 1
            if len(batch) >= 2_000:
                _upsert_country_history_rows(session, batch)
                batch.clear()
        if batch:
            _upsert_country_history_rows(session, batch)
    state.rows_seen = rows_seen
    state.rows_imported = rows_imported
    state.source_max_week = max_period
    state.last_success_at = datetime.now(UTC)
    state.last_error = None
    session.commit()
    return ACLEDWorkbookImportResult(
        source_file=path.name,
        rows_seen=rows_seen,
        rows_imported=rows_imported,
        source_max_week=max_period,
    )


def import_acled_workbook(
    session: Session,
    *,
    path: Path,
    history_days: int,
    since_date: date | None = None,
) -> ACLEDWorkbookImportResult:
    """Import recent political-violence aggregates without loading XLSX into RAM."""
    digest = _sha256_file(path)
    state = session.get(ConflictAggregateSyncState, path.name)
    if state is not None and state.archive_sha256 == digest and state.last_success_at:
        return ACLEDWorkbookImportResult(
            source_file=path.name,
            skipped_unchanged=True,
            rows_seen=state.rows_seen,
            rows_imported=state.rows_imported,
            source_max_week=state.source_max_week,
        )
    started_at = datetime.now(UTC)
    if state is None:
        state = ConflictAggregateSyncState(
            source_file=path.name,
            archive_sha256=digest,
        )
        session.add(state)
    state.archive_sha256 = digest
    state.last_started_at = started_at
    state.last_error = None
    session.flush()

    workbook_date = _date_from_filename(path.name)
    cutoff = since_date or ((workbook_date or date.today()) - timedelta(days=history_days))
    rows_seen = 0
    rows_imported = 0
    source_max_week: date | None = None
    batch: list[dict[str, Any]] = []
    with ZipFile(path) as zipped:
        if SHEET_PATH not in zipped.namelist() or SHARED_STRINGS_PATH not in zipped.namelist():
            raise ValueError("ACLED workbook is missing worksheet or shared strings")
        strings = _read_shared_strings(zipped)
        row_iterator = _iter_sheet_rows(zipped, strings)
        headers = next(row_iterator, None)
        if headers is None or tuple(headers[: len(EXPECTED_HEADERS)]) != EXPECTED_HEADERS:
            raise ValueError("unexpected ACLED aggregate workbook schema")
        for values in row_iterator:
            rows_seen += 1
            parsed = _parse_conflict_row(values, source_file=path.name, imported_at=started_at)
            if parsed is None:
                continue
            source_max_week = max(source_max_week or parsed["week"], parsed["week"])
            if parsed["week"] < cutoff:
                continue
            if parsed["disorder_type"] != "Political violence":
                continue
            if parsed["event_type"] not in POLITICAL_VIOLENCE_EVENT_TYPES:
                continue
            batch.append(parsed)
            rows_imported += 1
            if len(batch) >= 1_000:
                _upsert_conflict_rows(session, batch)
                batch.clear()
        if batch:
            _upsert_conflict_rows(session, batch)
    state.rows_seen = rows_seen
    state.rows_imported = rows_imported
    state.source_max_week = source_max_week
    state.last_success_at = datetime.now(UTC)
    state.last_error = None
    session.commit()
    return ACLEDWorkbookImportResult(
        source_file=path.name,
        rows_seen=rows_seen,
        rows_imported=rows_imported,
        source_max_week=source_max_week,
    )


def _read_shared_strings(zipped: ZipFile) -> list[str]:
    strings: list[str] = []
    with zipped.open(SHARED_STRINGS_PATH) as stream:
        for _, element in ElementTree.iterparse(stream, events=("end",)):
            if element.tag == f"{{{XML_NAMESPACE}}}si":
                strings.append(
                    "".join(
                        node.text or ""
                        for node in element.iter(f"{{{XML_NAMESPACE}}}t")
                    )
                )
                element.clear()
    return strings


def _iter_sheet_rows(zipped: ZipFile, strings: list[str]) -> Iterator[list[str | None]]:
    with zipped.open(SHEET_PATH) as stream:
        for _, element in ElementTree.iterparse(stream, events=("end",)):
            if element.tag != f"{{{XML_NAMESPACE}}}row":
                continue
            values: list[str | None] = [None] * len(EXPECTED_HEADERS)
            for cell in element.findall(f"{{{XML_NAMESPACE}}}c"):
                reference = cell.attrib.get("r", "")
                match = re.match(r"([A-Z]+)", reference)
                if match is None:
                    continue
                index = _column_index(match.group(1))
                if index >= len(values):
                    continue
                value_element = cell.find(f"{{{XML_NAMESPACE}}}v")
                if value_element is None or value_element.text is None:
                    continue
                raw = value_element.text
                if cell.attrib.get("t") == "s":
                    shared_index = int(raw)
                    values[index] = (
                        strings[shared_index] if shared_index < len(strings) else None
                    )
                else:
                    values[index] = raw
            yield values
            element.clear()


def _parse_conflict_row(
    values: list[str | None],
    *,
    source_file: str,
    imported_at: datetime,
) -> dict[str, Any] | None:
    try:
        week = EXCEL_EPOCH + timedelta(days=int(float(values[0] or "")))
        latitude = float(values[11] or "")
        longitude = float(values[12] or "")
        events = max(0, int(float(values[6] or 0)))
        fatalities = max(0, int(float(values[7] or 0)))
    except (TypeError, ValueError, OverflowError):
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    population_exposure = _optional_float(values[8])
    return {
        "week": week,
        "region": str(values[1] or "Unknown")[:128],
        "country": str(values[2] or "Unknown")[:255],
        "admin1": str(values[3] or "Unknown")[:255],
        "event_type": str(values[4] or "Unknown")[:128],
        "sub_event_type": str(values[5] or "Unknown")[:255],
        "events": events,
        "fatalities": fatalities,
        "population_exposure": population_exposure,
        "disorder_type": str(values[9] or "Unknown")[:128],
        "area_external_id": str(values[10])[:64] if values[10] else None,
        "latitude": latitude,
        "longitude": longitude,
        "source_file": source_file[:512],
        "imported_at": imported_at,
    }


def _country_history_definition(filename: str) -> tuple[str, str]:
    normalized = filename.casefold()
    for prefix, definition in COUNTRY_HISTORY_METRICS.items():
        if normalized.startswith(prefix.casefold()):
            return definition
    raise ValueError("unrecognized ACLED country history filename")


def _parse_country_history_row(
    values: list[str | None],
    *,
    metric: str,
    frequency: str,
    source_file: str,
    imported_at: datetime,
) -> dict[str, Any] | None:
    try:
        country = str(values[0] or "").strip()
        if frequency == "monthly":
            month_value = str(values[1] or "").strip().casefold()
            month = next(
                index
                for index, label in enumerate(month_name)
                if label and label.casefold() == month_value
            )
            year = int(float(values[2] or ""))
            value = max(0, int(float(values[3] or 0)))
        else:
            month = 1
            year = int(float(values[1] or ""))
            value = max(0, int(float(values[2] or 0)))
        period = date(year, month, 1)
    except (StopIteration, TypeError, ValueError, OverflowError):
        return None
    if not country:
        return None
    return {
        "country": country[:255],
        "period": period,
        "frequency": frequency,
        "metric": metric,
        "value": value,
        "source_file": source_file[:512],
        "imported_at": imported_at,
    }


def _upsert_conflict_rows(session: Session, rows: list[dict[str, Any]]) -> None:
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as dialect_insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as dialect_insert  # type: ignore[assignment]
    else:
        for row in rows:
            session.merge(ConflictAggregateObservation(**row))
        return
    statement = dialect_insert(ConflictAggregateObservation).values(rows)
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[
                ConflictAggregateObservation.week,
                ConflictAggregateObservation.country,
                ConflictAggregateObservation.admin1,
                ConflictAggregateObservation.event_type,
                ConflictAggregateObservation.sub_event_type,
            ],
            set_={
                key: getattr(statement.excluded, key)
                for key in (
                    "region",
                    "events",
                    "fatalities",
                    "population_exposure",
                    "disorder_type",
                    "area_external_id",
                    "latitude",
                    "longitude",
                    "source_file",
                    "imported_at",
                )
            },
        )
    )


def _upsert_country_history_rows(
    session: Session,
    rows: list[dict[str, Any]],
) -> None:
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as dialect_insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as dialect_insert  # type: ignore[assignment]
    else:
        for row in rows:
            session.merge(ConflictCountryIndicatorObservation(**row))
        return
    statement = dialect_insert(ConflictCountryIndicatorObservation).values(rows)
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[
                ConflictCountryIndicatorObservation.country,
                ConflictCountryIndicatorObservation.period,
                ConflictCountryIndicatorObservation.frequency,
                ConflictCountryIndicatorObservation.metric,
            ],
            set_={
                "value": statement.excluded.value,
                "source_file": statement.excluded.source_file,
                "imported_at": statement.excluded.imported_at,
            },
        )
    )


def _column_index(column_name: str) -> int:
    value = 0
    for character in column_name:
        value = value * 26 + ord(character) - ord("A") + 1
    return value - 1


def _optional_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date_from_filename(filename: str) -> date | None:
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", filename)
    if match is None:
        return None
    try:
        return date(*(int(item) for item in match.groups()))
    except ValueError:
        return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
