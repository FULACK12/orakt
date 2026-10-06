"""Lifecycle-safe Alpha Vantage weekly adjusted price backfill."""

from __future__ import annotations

import asyncio
import csv
import gzip
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from io import StringIO
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.alpha_vantage_listings import (
    ALPHA_VANTAGE_PROVIDER_KEY,
    ALPHA_VANTAGE_QUERY_URL,
    ALPHA_VANTAGE_SOURCE_URL,
)
from app.db.models import (
    CompanyProfile,
    MarketAssetLifecycle,
    MarketPriceBackfillState,
    MarketSeries,
)
from app.market_history import _dialect_insert, _upsert_observations
from app.storage.archive import ArchiveCapacityError, ColdArchive

ALPHA_VANTAGE_PRICE_PROVIDER_KEY = "alpha_vantage_weekly_adjusted"
PRICE_REQUIRED_COLUMNS = {"timestamp", "adjusted close"}
TERMINAL_PRICE_STATUSES = {"synced", "partial", "unavailable", "ticker_reused"}
DERIVATIVE_MARKERS = (
    "warrant",
    "warrants",
    "units (",
    "unit (",
    "rights",
    "acquisition corp",
    "2x long",
    "2x short",
    "3x long",
    "3x short",
)


class AlphaVantagePriceError(RuntimeError):
    """A sanitized price-provider failure with a stable machine code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class AlphaVantagePriceBackfillResult(BaseModel):
    """Auditable accounting for one bounded daily price backfill."""

    model_config = ConfigDict(extra="forbid")

    queued_assets: int = Field(ge=0)
    attempted_assets: int = Field(ge=0)
    synced_assets: int = Field(ge=0)
    partial_assets: int = Field(ge=0)
    unavailable_assets: int = Field(ge=0)
    ticker_reused_assets: int = Field(ge=0)
    rate_limited: bool = False
    observations_upserted: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list, max_length=20)


@dataclass(slots=True)
class RankedPriceCandidate:
    """One lifecycle plus its deterministic local priority and attempt state."""

    lifecycle: MarketAssetLifecycle
    priority_score: float
    priority_reasons: list[str]
    state: MarketPriceBackfillState | None


def rank_price_backfill_candidates(
    session: Session,
    *,
    limit: int = 500,
    as_of: date | None = None,
    include_terminal: bool = False,
) -> list[RankedPriceCandidate]:
    """Rank missing delisted histories without claiming that discovery is price coverage."""
    selected_date = as_of or datetime.now(UTC).date()
    lifecycles = list(
        session.scalars(
            select(MarketAssetLifecycle).where(
                MarketAssetLifecycle.provider_key == ALPHA_VANTAGE_PROVIDER_KEY,
                MarketAssetLifecycle.listing_status == "delisted",
                MarketAssetLifecycle.delisting_date.is_not(None),
            )
        )
    )
    states = {
        row.asset_key: row
        for row in session.scalars(select(MarketPriceBackfillState))
    }
    reviewed_tickers = {
        value.upper() for value in session.scalars(select(CompanyProfile.ticker))
    }
    ranked: list[RankedPriceCandidate] = []
    for lifecycle in lifecycles:
        state = states.get(lifecycle.asset_key)
        if not include_terminal and state is not None:
            if state.status in TERMINAL_PRICE_STATUSES:
                continue
            if state.status == "rate_limited" and state.last_attempt_at is not None:
                attempted_on = state.last_attempt_at.date()
                if attempted_on >= selected_date:
                    continue
            if (
                state.status == "failed"
                and state.last_attempt_at is not None
                and (
                    state.attempt_count >= 3
                    or state.last_attempt_at.date() > selected_date - timedelta(days=7)
                )
            ):
                continue
        score, reasons = _priority_score(
            lifecycle,
            selected_date=selected_date,
            reviewed=lifecycle.symbol.upper() in reviewed_tickers,
        )
        if state is not None and state.status == "failed":
            score -= state.attempt_count * 5
            reasons.append("retry_after_failure")
        ranked.append(
            RankedPriceCandidate(
                lifecycle=lifecycle,
                priority_score=round(score, 3),
                priority_reasons=reasons,
                state=state,
            )
        )
    ranked.sort(
        key=lambda item: (
            -item.priority_score,
            -(item.lifecycle.delisting_date or date.min).toordinal(),
            item.lifecycle.symbol,
        )
    )
    return ranked[:limit]


def materialize_price_backfill_queue(
    session: Session,
    *,
    limit: int = 500,
    as_of: date | None = None,
) -> int:
    """Persist a bounded, explainable queue for scheduler and UI inspection."""
    candidates = rank_price_backfill_candidates(
        session,
        limit=limit,
        as_of=as_of,
        include_terminal=False,
    )
    for candidate in candidates:
        state = candidate.state
        if state is None:
            state = MarketPriceBackfillState(
                asset_key=candidate.lifecycle.asset_key,
                provider_key=ALPHA_VANTAGE_PRICE_PROVIDER_KEY,
                status="pending",
                priority_score=candidate.priority_score,
                priority_reasons=candidate.priority_reasons,
                attempt_count=0,
                observations_upserted=0,
            )
            session.add(state)
        else:
            state.priority_score = candidate.priority_score
            state.priority_reasons = candidate.priority_reasons
            if state.status in {"failed", "rate_limited"}:
                state.status = "pending"
    session.flush()
    return len(candidates)


async def fetch_alpha_vantage_weekly_adjusted(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    symbol: str,
) -> tuple[list[tuple[date, float]], bytes]:
    """Fetch full weekly adjusted history while keeping credentials out of errors."""
    try:
        response = await client.get(
            ALPHA_VANTAGE_QUERY_URL,
            params={
                "function": "TIME_SERIES_WEEKLY_ADJUSTED",
                "symbol": symbol,
                "datatype": "csv",
                "apikey": api_key,
            },
        )
    except httpx.HTTPError as exc:
        raise AlphaVantagePriceError(
            "request_failed",
            f"weekly adjusted request failed ({type(exc).__name__})",
        ) from None
    if response.status_code != 200:
        raise AlphaVantagePriceError(
            "provider_http",
            f"weekly adjusted endpoint returned HTTP {response.status_code}",
        )
    body = response.text.lstrip("\ufeff \t\r\n")
    if not body:
        raise AlphaVantagePriceError("unavailable", "provider returned an empty price body")
    if body.startswith("{"):
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {}
        rendered = " ".join(str(value) for value in payload.values()).casefold()
        if "rate limit" in rendered or "25 requests" in rendered:
            raise AlphaVantagePriceError("rate_limited", "daily provider request limit reached")
        if "premium" in rendered:
            raise AlphaVantagePriceError("premium_required", "provider requires a premium plan")
        raise AlphaVantagePriceError("unavailable", "provider has no usable history for symbol")

    reader = csv.DictReader(StringIO(body))
    normalized_fields = {str(value).strip().casefold() for value in (reader.fieldnames or [])}
    if not PRICE_REQUIRED_COLUMNS.issubset(normalized_fields):
        raise AlphaVantagePriceError(
            "invalid_csv",
            "weekly adjusted CSV is missing timestamp or adjusted close",
        )
    rows: dict[date, float] = {}
    for raw in reader:
        normalized = {str(key).strip().casefold(): value for key, value in raw.items()}
        observed_on = _optional_date(normalized.get("timestamp"))
        adjusted_close = _optional_positive_float(normalized.get("adjusted close"))
        if observed_on is not None and adjusted_close is not None:
            rows[observed_on] = adjusted_close
    if not rows:
        raise AlphaVantagePriceError("unavailable", "provider returned no valid adjusted prices")
    return sorted(rows.items()), response.content


async def sync_alpha_vantage_price_backfill(
    session: Session,
    *,
    client: httpx.AsyncClient,
    api_key: str,
    archive: ColdArchive,
    max_assets: int = 10,
    queue_size: int = 500,
    request_interval_seconds: float = 15.0,
    now: datetime | None = None,
    commit_each_asset: bool = False,
) -> AlphaVantagePriceBackfillResult:
    """Backfill a bounded number of adjusted histories with ticker-reuse guards."""
    generated_at = now or datetime.now(UTC)
    queued = materialize_price_backfill_queue(
        session,
        limit=queue_size,
        as_of=generated_at.date(),
    )
    if commit_each_asset:
        session.commit()
    pending = list(
        session.execute(
            select(MarketPriceBackfillState, MarketAssetLifecycle)
            .join(
                MarketAssetLifecycle,
                MarketAssetLifecycle.asset_key == MarketPriceBackfillState.asset_key,
            )
            .where(MarketPriceBackfillState.status == "pending")
            .order_by(
                MarketPriceBackfillState.priority_score.desc(),
                MarketAssetLifecycle.delisting_date.desc(),
            )
            .limit(max_assets)
        )
    )
    attempted = synced = partial = unavailable = reused = observations = 0
    rate_limited = False
    errors: list[str] = []
    for index, (state, lifecycle) in enumerate(pending):
        if index and request_interval_seconds:
            await asyncio.sleep(request_interval_seconds)
        attempted += 1
        state.attempt_count += 1
        state.last_attempt_at = generated_at
        state.last_error_code = None
        state.last_error_message = None
        try:
            provider_rows, raw_payload = await fetch_alpha_vantage_weekly_adjusted(
                client,
                api_key=api_key,
                symbol=lifecycle.symbol,
            )
            accepted = _validate_lifecycle_prices(lifecycle, provider_rows)
            archive_path = _archive_price_payload(
                archive,
                lifecycle=lifecycle,
                fetched_on=generated_at.date(),
                payload=raw_payload,
            )
            series_id = _historical_series_id(lifecycle)
            _upsert_historical_market_series(session, lifecycle=lifecycle, series_id=series_id)
            fetched_at = generated_at
            upserted = _upsert_observations(
                session,
                [
                    {
                        "series_id": series_id,
                        "observed_on": observed_on,
                        "value": value,
                        "fetched_at": fetched_at,
                    }
                    for observed_on, value in accepted
                ],
            )
            state.status = "synced" if len(accepted) >= 60 else "partial"
            state.last_success_at = generated_at
            state.observations_upserted = upserted
            state.observed_start = accepted[0][0]
            state.observed_end = accepted[-1][0]
            state.series_id = series_id
            state.raw_archive_path = archive_path
            observations += upserted
            synced += int(state.status == "synced")
            partial += int(state.status == "partial")
        except AlphaVantagePriceError as exc:
            state.last_error_code = exc.code
            state.last_error_message = str(exc)[:500]
            if exc.code == "ticker_reused":
                state.status = "ticker_reused"
                reused += 1
            elif exc.code in {"unavailable", "premium_required", "invalid_csv"}:
                state.status = "unavailable"
                unavailable += 1
            elif exc.code == "rate_limited":
                state.status = "rate_limited"
                rate_limited = True
            else:
                state.status = "failed"
            errors.append(f"{lifecycle.symbol}: {exc.code}")
        except ArchiveCapacityError:
            state.status = "failed"
            state.last_error_code = "cold_archive_capacity"
            state.last_error_message = "cold archive reserve prevented the raw price write"
            errors.append(f"{lifecycle.symbol}: cold_archive_capacity")
        except OSError:
            state.status = "failed"
            state.last_error_code = "cold_archive_io"
            state.last_error_message = "cold archive path is unavailable or not writable"
            errors.append(f"{lifecycle.symbol}: cold_archive_io")
        if commit_each_asset:
            session.commit()
        if rate_limited:
            break
    session.flush()
    return AlphaVantagePriceBackfillResult(
        queued_assets=queued,
        attempted_assets=attempted,
        synced_assets=synced,
        partial_assets=partial,
        unavailable_assets=unavailable,
        ticker_reused_assets=reused,
        rate_limited=rate_limited,
        observations_upserted=observations,
        errors=errors[:20],
    )


def price_backfill_coverage(session: Session) -> dict[str, Any]:
    """Return queue, terminal-state and factor-readiness counts."""
    rows = list(
        session.execute(
            select(MarketPriceBackfillState.status, func.count())
            .group_by(MarketPriceBackfillState.status)
        )
    )
    status_counts = {str(status): int(count) for status, count in rows}
    factor_ready = int(
        session.scalar(
            select(func.count())
            .select_from(MarketPriceBackfillState)
            .where(MarketPriceBackfillState.status == "synced")
        )
        or 0
    )
    latest_attempt = session.scalar(select(func.max(MarketPriceBackfillState.last_attempt_at)))
    latest_success = session.scalar(select(func.max(MarketPriceBackfillState.last_success_at)))
    return {
        "status_counts": status_counts,
        "queued_assets": sum(status_counts.values()),
        "pending_assets": status_counts.get("pending", 0),
        "synced_assets": status_counts.get("synced", 0),
        "partial_assets": status_counts.get("partial", 0),
        "unavailable_assets": status_counts.get("unavailable", 0),
        "ticker_reused_assets": status_counts.get("ticker_reused", 0),
        "failed_assets": status_counts.get("failed", 0),
        "rate_limited_assets": status_counts.get("rate_limited", 0),
        "factor_ready_assets": factor_ready,
        "latest_attempt_at": latest_attempt,
        "latest_success_at": latest_success,
    }


def _priority_score(
    lifecycle: MarketAssetLifecycle,
    *,
    selected_date: date,
    reviewed: bool,
) -> tuple[float, list[str]]:
    delisted_on = lifecycle.delisting_date or date.min
    days_since = max((selected_date - delisted_on).days, 0)
    score = max(0.0, 120.0 - days_since / 7)
    reasons = ["recent_delisting"] if days_since <= 365 else ["historical_universe_gap"]
    if lifecycle.asset_type.casefold() == "stock":
        score += 25
        reasons.append("ordinary_equity_priority")
    elif lifecycle.asset_type.casefold() == "etf":
        score += 8
        reasons.append("etf_secondary_priority")
    if lifecycle.ipo_date is not None and lifecycle.delisting_date is not None:
        years_listed = max((lifecycle.delisting_date - lifecycle.ipo_date).days / 365.25, 0)
        score += min(years_listed, 20)
        if years_listed >= 5:
            reasons.append("long_lifecycle")
    if reviewed:
        score += 40
        reasons.append("reviewed_company_ticker")
    identity = f"{lifecycle.symbol} {lifecycle.name}".casefold()
    if any(marker in identity for marker in DERIVATIVE_MARKERS) or re.search(
        r"(?:^|[-.])[wru]$",
        lifecycle.symbol.casefold(),
    ):
        score -= 100
        reasons.append("derivative_or_shell_penalty")
    return score, reasons


def _validate_lifecycle_prices(
    lifecycle: MarketAssetLifecycle,
    rows: list[tuple[date, float]],
) -> list[tuple[date, float]]:
    listed_from = lifecycle.ipo_date or date.min
    listed_until = lifecycle.delisting_date
    if listed_until is None:
        raise AlphaVantagePriceError("invalid_lifecycle", "delisting date is missing")
    if any(observed_on > listed_until + timedelta(days=7) for observed_on, _ in rows):
        raise AlphaVantagePriceError(
            "ticker_reused",
            "provider history continues after the recorded delisting lifecycle",
        )
    accepted = [
        (observed_on, value)
        for observed_on, value in rows
        if listed_from <= observed_on <= listed_until
    ]
    if not accepted:
        raise AlphaVantagePriceError(
            "unavailable",
            "provider history has no observations inside the recorded lifecycle",
        )
    return accepted


def _upsert_historical_market_series(
    session: Session,
    *,
    lifecycle: MarketAssetLifecycle,
    series_id: str,
) -> None:
    sector = "Unclassified historical equity"
    neutralization_group = (
        "historical_etf" if lifecycle.asset_type.casefold() == "etf" else "historical_equity"
    )
    values = {
        "series_id": series_id,
        "name": lifecycle.name,
        "category": "historical_equity_price",
        "unit": "USD",
        "frequency": "weekly",
        "source_name": "Alpha Vantage weekly adjusted",
        "source_url": ALPHA_VANTAGE_SOURCE_URL,
        "listing_status": "delisted",
        "listed_from": lifecycle.ipo_date,
        "listed_until": lifecycle.delisting_date,
        "delisting_return": None,
        "sector": sector,
        "region": "north_america",
        "neutralization_group": neutralization_group,
    }
    insert = _dialect_insert(session, MarketSeries)
    statement = insert.values(values)
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[MarketSeries.series_id],
            set_={
                key: getattr(statement.excluded, key)
                for key in values
                if key != "series_id"
            },
        )
    )


def _archive_price_payload(
    archive: ColdArchive,
    *,
    lifecycle: MarketAssetLifecycle,
    fetched_on: date,
    payload: bytes,
) -> str:
    archive_key = hashlib.sha256(lifecycle.asset_key.encode("utf-8")).hexdigest()
    relative = (
        "raw/alpha-vantage/weekly-adjusted/"
        f"{fetched_on:%Y/%m/%d}/{archive_key}.csv.gz"
    )
    return archive.store_bytes(relative, gzip.compress(payload, compresslevel=6, mtime=0))


def _historical_series_id(lifecycle: MarketAssetLifecycle) -> str:
    symbol = re.sub(r"[^A-Z0-9.-]+", "_", lifecycle.symbol.upper())[:32]
    return f"HIST:{symbol}:{lifecycle.asset_key[-16:]}"


def _optional_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return None


def _optional_positive_float(value: str | None) -> float | None:
    try:
        parsed = float((value or "").strip())
    except ValueError:
        return None
    return parsed if parsed > 0 else None
