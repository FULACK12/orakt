"""Cold-store the full 1979-2013 GDELT archive and materialize monthly signals."""

from __future__ import annotations

import csv
import hashlib
import io
import os
import shutil
import time
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.models import GdeltArchiveState, GdeltEventAggregate

MASTER_ARCHIVE_KEY = "gdelt_events_1979_2013"
GDELT_ARCHIVE_BASE_URL = (
    "https://storage.googleapis.com/data.gdeltproject.org/events"
)
MASTER_ARCHIVE_URL = (
    f"{GDELT_ARCHIVE_BASE_URL}/"
    "GDELT.MASTERREDUCEDV2.1979-2013.zip"
)
MASTER_START = date(1979, 1, 1)
MASTER_END = date(2013, 12, 31)
DAILY_START = date(2014, 1, 1)
DAILY_STATE_PREFIX = "gdelt_events_daily_"
TERMINAL_DAILY_STATUSES = ("completed", "unavailable")


def sync_gdelt_master_history(
    session: Session,
    *,
    client: httpx.Client,
    cold_root: Path,
    min_free_bytes: int,
) -> GdeltArchiveState:
    """Download once, retain raw ZIP, then rebuild idempotent monthly aggregates."""
    target_dir = cold_root / "raw" / "gdelt" / "events"
    target_dir.mkdir(parents=True, exist_ok=True)
    archive_path = target_dir / "GDELT.MASTERREDUCEDV2.1979-2013.zip"
    state = session.get(GdeltArchiveState, MASTER_ARCHIVE_KEY)
    if state is None:
        state = GdeltArchiveState(
            archive_key=MASTER_ARCHIVE_KEY,
            source_url=MASTER_ARCHIVE_URL,
            status="pending",
            rows_seen=0,
            aggregates_upserted=0,
            archive_bytes=0,
            starts_at=MASTER_START,
            ends_at=MASTER_END,
        )
        session.add(state)
    if (
        state.status == "completed"
        and archive_path.is_file()
        and state.aggregates_upserted > 0
    ):
        return state
    state.last_started_at = datetime.now(UTC)
    state.last_error = None
    session.commit()
    try:
        if not archive_path.is_file():
            state.status = "downloading"
            session.commit()
            _download_archive(
                client,
                archive_path=archive_path,
                min_free_bytes=min_free_bytes,
            )
        state.local_path = str(archive_path.relative_to(cold_root))
        state.archive_bytes = archive_path.stat().st_size
        state.sha256 = _sha256(archive_path)
        state.status = "importing"
        session.commit()
        session.execute(
            delete(GdeltEventAggregate).where(
                GdeltEventAggregate.month >= MASTER_START,
                GdeltEventAggregate.month <= MASTER_END,
            )
        )
        session.commit()
        rows_seen, aggregate_count = _materialize_archive(session, archive_path)
        state.rows_seen = rows_seen
        state.aggregates_upserted = aggregate_count
        state.status = "completed"
        state.last_success_at = datetime.now(UTC)
        state.last_error = None
        session.commit()
    except Exception as exc:
        session.rollback()
        state = session.get(GdeltArchiveState, MASTER_ARCHIVE_KEY) or state
        state.status = "failed"
        state.last_error = f"{type(exc).__name__}: {str(exc)[:1_800]}"
        session.commit()
        raise
    return state


def sync_gdelt_daily_batch(
    session: Session,
    *,
    client: httpx.Client,
    cold_root: Path,
    min_free_bytes: int,
    batch_days: int = 30,
    end_date: date | None = None,
    request_interval_seconds: float = 0.5,
) -> list[GdeltArchiveState]:
    """Backfill restart-safe daily GDELT 1.0 archives from 2014 onward."""
    if batch_days < 1 or batch_days > 366:
        raise ValueError("batch_days must be between 1 and 366")
    target_end = end_date or (datetime.now(UTC).date() - timedelta(days=1))
    latest = session.scalar(
        select(func.max(GdeltArchiveState.ends_at)).where(
            GdeltArchiveState.archive_key.like(f"{DAILY_STATE_PREFIX}%"),
            GdeltArchiveState.status.in_(TERMINAL_DAILY_STATUSES),
        )
    )
    current = max(DAILY_START, (latest + timedelta(days=1)) if latest else DAILY_START)
    completed: list[GdeltArchiveState] = []
    for index in range(batch_days):
        if current > target_end:
            break
        if index and request_interval_seconds:
            time.sleep(request_interval_seconds)
        state = _sync_daily_archive(
            session,
            client=client,
            cold_root=cold_root,
            min_free_bytes=min_free_bytes,
            archive_date=current,
        )
        if state.status not in TERMINAL_DAILY_STATUSES:
            break
        completed.append(state)
        current += timedelta(days=1)
    return completed


def gdelt_history_coverage(session: Session) -> dict[str, Any]:
    count, month_count, start, end, events = session.execute(
        select(
            func.count(GdeltEventAggregate.id),
            func.count(func.distinct(GdeltEventAggregate.month)),
            func.min(GdeltEventAggregate.month),
            func.max(GdeltEventAggregate.month),
            func.sum(GdeltEventAggregate.event_count),
        )
    ).one()
    state = session.scalar(
        select(GdeltArchiveState)
        .where(GdeltArchiveState.last_success_at.is_not(None))
        .order_by(GdeltArchiveState.last_success_at.desc())
        .limit(1)
    )
    master = session.get(GdeltArchiveState, MASTER_ARCHIVE_KEY)
    daily_bytes = int(
        session.scalar(
            select(func.sum(GdeltArchiveState.archive_bytes)).where(
                GdeltArchiveState.archive_key.like(f"{DAILY_STATE_PREFIX}%")
            )
        )
        or 0
    )
    unavailable_days = int(
        session.scalar(
            select(func.count()).select_from(GdeltArchiveState).where(
                GdeltArchiveState.archive_key.like(f"{DAILY_STATE_PREFIX}%"),
                GdeltArchiveState.status == "unavailable",
            )
        )
        or 0
    )
    expected_months = (
        (datetime.now(UTC).year - MASTER_START.year) * 12
        + datetime.now(UTC).month
    )
    return {
        "aggregate_count": int(count or 0),
        "month_count": int(month_count or 0),
        "expected_month_count": expected_months,
        "event_count": int(events or 0),
        "starts_at": start,
        "ends_at": end,
        "last_success_at": state.last_success_at if state else None,
        "status": (
            "completed"
            if int(month_count or 0) >= expected_months - 1
            else "importing"
            if count
            else master.status
            if master
            else "missing"
        ),
        "archive_bytes": (master.archive_bytes if master else 0) + daily_bytes,
        "unavailable_days": unavailable_days,
        "last_error": state.last_error if state else None,
    }


def _sync_daily_archive(
    session: Session,
    *,
    client: httpx.Client,
    cold_root: Path,
    min_free_bytes: int,
    archive_date: date,
) -> GdeltArchiveState:
    archive_key = f"{DAILY_STATE_PREFIX}{archive_date:%Y%m%d}"
    archive_url = _daily_archive_url(archive_date)
    archive_path = (
        cold_root
        / "raw"
        / "gdelt"
        / "events"
        / f"{archive_date:%Y}"
        / f"{archive_date:%Y%m%d}.export.CSV.zip"
    )
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    state = session.get(GdeltArchiveState, archive_key)
    if state is not None and state.status in TERMINAL_DAILY_STATUSES:
        return state
    if state is None:
        state = GdeltArchiveState(
            archive_key=archive_key,
            source_url=archive_url,
            status="pending",
            starts_at=archive_date,
            ends_at=archive_date,
            rows_seen=0,
            aggregates_upserted=0,
            archive_bytes=0,
        )
        session.add(state)
    state.last_started_at = datetime.now(UTC)
    state.last_error = None
    session.commit()
    try:
        if not archive_path.is_file():
            state.status = "downloading"
            session.commit()
            _download_url(
                client,
                archive_url=archive_url,
                archive_path=archive_path,
                min_free_bytes=min_free_bytes,
            )
        state.local_path = str(archive_path.relative_to(cold_root))
        state.archive_bytes = archive_path.stat().st_size
        state.sha256 = _sha256(archive_path)
        state.status = "importing"
        session.commit()
        rows_seen, aggregate_count = _materialize_daily_archive(session, archive_path)
        state.rows_seen = rows_seen
        state.aggregates_upserted = aggregate_count
        state.status = "completed"
        state.last_success_at = datetime.now(UTC)
        state.last_error = None
        session.commit()
    except httpx.HTTPStatusError as exc:
        session.rollback()
        state = session.get(GdeltArchiveState, archive_key) or state
        if exc.response.status_code == 404:
            state.status = "unavailable"
            state.last_error = (
                "Official GDELT archive returned HTTP 404 for this date; "
                "the gap is retained in the audit trail."
            )
            session.commit()
            return state
        state.status = "failed"
        state.last_error = f"{type(exc).__name__}: {str(exc)[:1_800]}"
        session.commit()
    except Exception as exc:
        session.rollback()
        state = session.get(GdeltArchiveState, archive_key) or state
        state.status = "failed"
        state.last_error = f"{type(exc).__name__}: {str(exc)[:1_800]}"
        session.commit()
    return state


def _download_archive(
    client: httpx.Client,
    *,
    archive_path: Path,
    min_free_bytes: int,
) -> None:
    _download_url(
        client,
        archive_url=MASTER_ARCHIVE_URL,
        archive_path=archive_path,
        min_free_bytes=min_free_bytes,
    )


def _download_url(
    client: httpx.Client,
    *,
    archive_url: str,
    archive_path: Path,
    min_free_bytes: int,
) -> None:
    free = shutil.disk_usage(archive_path.parent).free
    if free < min_free_bytes:
        raise OSError(
            f"cold storage free bytes {free} below configured reserve "
            f"{min_free_bytes}"
        )
    temporary = archive_path.with_suffix(".zip.part")
    try:
        with client.stream("GET", archive_url) as response:
            response.raise_for_status()
            with temporary.open("wb") as handle:
                for chunk in response.iter_bytes(1024 * 1024):
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
        temporary.replace(archive_path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _materialize_daily_archive(
    session: Session,
    archive_path: Path,
) -> tuple[int, int]:
    rows_seen = 0
    buckets: dict[tuple[date, str, str, int], list[float]] = defaultdict(
        lambda: [0.0] * 6
    )
    with ZipFile(archive_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            with archive.open(member) as binary:
                text = io.TextIOWrapper(binary, encoding="utf-8", errors="replace")
                for row in csv.reader(text, delimiter="\t"):
                    parsed = _parse_event_row(row)
                    if parsed is None:
                        continue
                    rows_seen += 1
                    metrics = buckets[parsed[:4]]
                    for index, value in enumerate(parsed[4:]):
                        metrics[index] += value
    return rows_seen, _flush_buckets(session, buckets)


def _materialize_archive(
    session: Session,
    archive_path: Path,
) -> tuple[int, int]:
    rows_seen = 0
    aggregate_count = 0
    active_month: date | None = None
    buckets: dict[tuple[date, str, str, int], list[float]] = defaultdict(
        lambda: [0.0] * 6
    )
    with ZipFile(archive_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            with archive.open(member) as binary:
                text = io.TextIOWrapper(binary, encoding="utf-8", errors="replace")
                reader = csv.reader(text, delimiter="\t")
                for row in reader:
                    parsed = _parse_event_row(row)
                    if parsed is None:
                        continue
                    rows_seen += 1
                    month = parsed[0]
                    if active_month is not None and month != active_month:
                        aggregate_count += _flush_buckets(session, buckets)
                        session.commit()
                        buckets.clear()
                    active_month = month
                    key = parsed[:4]
                    metrics = buckets[key]
                    for index, value in enumerate(parsed[4:]):
                        metrics[index] += value
    aggregate_count += _flush_buckets(session, buckets)
    session.commit()
    return rows_seen, aggregate_count


def _parse_event_row(
    row: list[str],
) -> tuple[date, str, str, int, float, float, float, float, float, float] | None:
    if len(row) == 17:
        return _parse_master_reduced_row(row)
    if len(row) < 35:
        return None
    month = _month(row[2] or row[1][:6])
    if month is None:
        return None
    country = (
        row[51].strip()
        if len(row) > 51 and row[51].strip()
        else row[7].strip() or row[17].strip() or "UNK"
    )
    root_code = row[28].strip() or "UNK"
    quad_class = _int(row[29])
    if quad_class is None:
        return None
    return (
        month,
        country[:8],
        root_code[:8],
        quad_class,
        1.0,
        float(_int(row[31]) or 0),
        float(_int(row[32]) or 0),
        float(_int(row[33]) or 0),
        _float(row[30]) or 0.0,
        _float(row[34]) or 0.0,
    )


def _parse_master_reduced_row(
    row: list[str],
) -> tuple[date, str, str, int, float, float, float, float, float, float] | None:
    if not row[0].isdigit():
        return None
    month = _month(row[0][:6])
    quad_class = _int(row[6])
    event_count = _float(row[4])
    if month is None or quad_class is None or event_count is None:
        return None
    actor_code = (row[2].strip() or row[1].strip() or "UNK")[:3]
    cameo_code = row[3].strip()
    root_code = cameo_code[:2] if len(cameo_code) >= 2 else "UNK"
    articles = _float(row[5]) or 0.0
    goldstein = _float(row[7]) or 0.0
    return (
        month,
        actor_code,
        root_code,
        quad_class,
        event_count,
        0.0,
        0.0,
        articles,
        goldstein * event_count,
        0.0,
    )


def _flush_buckets(
    session: Session,
    buckets: dict[tuple[date, str, str, int], list[float]],
) -> int:
    rows = [
        {
            "month": key[0],
            "country_code": key[1],
            "event_root_code": key[2],
            "quad_class": key[3],
            "event_count": int(values[0]),
            "total_mentions": int(values[1]),
            "total_sources": int(values[2]),
            "total_articles": int(values[3]),
            "goldstein_sum": values[4],
            "tone_sum": values[5],
        }
        for key, values in buckets.items()
    ]
    for start in range(0, len(rows), 5_000):
        batch = rows[start : start + 5_000]
        if not batch:
            continue
        insert = _dialect_insert(session, GdeltEventAggregate)
        statement = insert.values(batch)
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[
                    GdeltEventAggregate.month,
                    GdeltEventAggregate.country_code,
                    GdeltEventAggregate.event_root_code,
                    GdeltEventAggregate.quad_class,
                ],
                set_={
                    "event_count": (
                        GdeltEventAggregate.event_count
                        + statement.excluded.event_count
                    ),
                    "total_mentions": (
                        GdeltEventAggregate.total_mentions
                        + statement.excluded.total_mentions
                    ),
                    "total_sources": (
                        GdeltEventAggregate.total_sources
                        + statement.excluded.total_sources
                    ),
                    "total_articles": (
                        GdeltEventAggregate.total_articles
                        + statement.excluded.total_articles
                    ),
                    "goldstein_sum": (
                        GdeltEventAggregate.goldstein_sum
                        + statement.excluded.goldstein_sum
                    ),
                    "tone_sum": (
                        GdeltEventAggregate.tone_sum + statement.excluded.tone_sum
                    ),
                },
            )
        )
    return len(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _daily_archive_url(archive_date: date) -> str:
    return f"{GDELT_ARCHIVE_BASE_URL}/{archive_date:%Y%m%d}.export.CSV.zip"


def _month(value: str) -> date | None:
    value = value.strip()
    if len(value) < 6 or not value[:6].isdigit():
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), 1)
    except ValueError:
        return None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dialect_insert(session: Session, model: type[Any]) -> Any:
    if session.get_bind().dialect.name == "sqlite":
        return sqlite_insert(model)
    return postgresql_insert(model)
