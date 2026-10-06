"""Alpha Vantage equity lifecycle catalog and survivorship coverage."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
from datetime import UTC, date, datetime
from io import StringIO
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    MarketAssetLifecycle,
    MarketObservation,
    MarketPriceBackfillState,
    MarketSeries,
    MarketSyncState,
)
from app.market_delisting_evidence import market_delisting_evidence_coverage
from app.market_history import _dialect_insert, record_market_sync_start
from app.market_identity import market_identity_coverage

ALPHA_VANTAGE_PROVIDER_KEY = "alpha_vantage_listing_status"
ALPHA_VANTAGE_SOURCE_NAME = "Alpha Vantage"
ALPHA_VANTAGE_SOURCE_URL = "https://www.alphavantage.co/documentation/"
ALPHA_VANTAGE_QUERY_URL = "https://www.alphavantage.co/query"
ALPHA_VANTAGE_POINT_IN_TIME_BOUNDARY = date(2010, 1, 2)
REQUIRED_COLUMNS = {
    "symbol",
    "name",
    "exchange",
    "assetType",
    "ipoDate",
    "delistingDate",
    "status",
}


class AlphaVantageListingError(RuntimeError):
    """A sanitized provider or response failure that never includes credentials."""


class AlphaVantageListingSyncResult(BaseModel):
    """Safe audit result for one lifecycle-catalog refresh."""

    model_config = ConfigDict(extra="forbid")

    provider_key: str = ALPHA_VANTAGE_PROVIDER_KEY
    snapshot_date: date
    active_assets: int = Field(ge=0)
    delisted_assets: int = Field(ge=0)
    total_assets: int = Field(ge=0)
    earliest_ipo_date: date | None = None
    latest_delisting_date: date | None = None
    errors: list[str] = Field(default_factory=list, max_length=4)


async def fetch_alpha_vantage_listing_rows(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    state: Literal["active", "delisted"],
    snapshot_date: date,
    historical_date: date | None = None,
) -> list[dict[str, Any]]:
    """Fetch and validate one CSV listing-status response without leaking its URL."""
    params = {
        "function": "LISTING_STATUS",
        "apikey": api_key,
        "state": state,
    }
    if historical_date is not None:
        if historical_date < ALPHA_VANTAGE_POINT_IN_TIME_BOUNDARY:
            raise ValueError("Alpha Vantage historical dates must be later than 2010-01-01")
        params["date"] = historical_date.isoformat()
    try:
        response = await client.get(ALPHA_VANTAGE_QUERY_URL, params=params)
    except httpx.HTTPError as exc:
        raise AlphaVantageListingError(
            f"Alpha Vantage listing request failed ({type(exc).__name__})"
        ) from None
    if response.status_code != 200:
        raise AlphaVantageListingError(
            f"Alpha Vantage listing endpoint returned HTTP {response.status_code}"
        )
    body = response.text.lstrip("\ufeff \t\r\n")
    if not body:
        raise AlphaVantageListingError("Alpha Vantage listing endpoint returned an empty body")
    if body.startswith("{"):
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {}
        reason = "rate limit or credential rejection"
        if isinstance(payload, dict) and "Error Message" in payload:
            reason = "provider parameter rejection"
        raise AlphaVantageListingError(f"Alpha Vantage listing endpoint reported {reason}")

    reader = csv.DictReader(StringIO(body))
    missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
    if missing:
        raise AlphaVantageListingError(
            "Alpha Vantage listing CSV is missing required columns: "
            + ", ".join(sorted(missing))
        )
    fetched_at = datetime.now(UTC)
    rows: dict[str, dict[str, Any]] = {}
    for raw in reader:
        symbol = (raw.get("symbol") or "").strip().upper()
        name = (raw.get("name") or "").strip()
        exchange = (raw.get("exchange") or "unknown").strip().upper()
        asset_type = (raw.get("assetType") or "unknown").strip()
        listing_status = (raw.get("status") or state).strip().casefold()
        if not symbol or not name or listing_status != state:
            continue
        ipo_date = _optional_date(raw.get("ipoDate"))
        delisting_date = _optional_date(raw.get("delistingDate"))
        if ipo_date is not None and delisting_date is not None and ipo_date > delisting_date:
            continue
        asset_key = _asset_key(
            symbol=symbol,
            exchange=exchange,
            ipo_date=ipo_date,
            delisting_date=delisting_date,
            listing_status=listing_status,
        )
        rows[asset_key] = {
            "asset_key": asset_key,
            "provider_key": ALPHA_VANTAGE_PROVIDER_KEY,
            "symbol": symbol,
            "name": name[:255],
            "exchange": exchange[:64],
            "asset_type": asset_type[:64],
            "ipo_date": ipo_date,
            "delisting_date": delisting_date,
            "listing_status": listing_status,
            "snapshot_date": snapshot_date,
            "fetched_at": fetched_at,
            "source_url": ALPHA_VANTAGE_SOURCE_URL,
        }
    if not rows:
        raise AlphaVantageListingError(
            f"Alpha Vantage returned no valid {state} listing rows"
        )
    return list(rows.values())


async def sync_alpha_vantage_lifecycles(
    session: Session,
    *,
    client: httpx.AsyncClient,
    api_key: str,
    snapshot_date: date | None = None,
    request_interval_seconds: float = 15.0,
) -> AlphaVantageListingSyncResult:
    """Upsert the provider catalog without deleting historical evidence children."""
    selected_date = snapshot_date or datetime.now(UTC).date()
    state = record_market_sync_start(
        session,
        provider_key=ALPHA_VANTAGE_PROVIDER_KEY,
        history_start=ALPHA_VANTAGE_POINT_IN_TIME_BOUNDARY,
        history_end=selected_date,
    )
    rows_by_state: dict[str, list[dict[str, Any]]] = {}
    errors: list[str] = []
    listing_states: tuple[Literal["active", "delisted"], ...] = ("active", "delisted")
    for index, listing_state in enumerate(listing_states):
        if index and request_interval_seconds:
            await asyncio.sleep(request_interval_seconds)
        try:
            rows_by_state[listing_state] = await fetch_alpha_vantage_listing_rows(
                client,
                api_key=api_key,
                state=listing_state,
                snapshot_date=selected_date,
            )
        except (AlphaVantageListingError, ValueError) as exc:
            errors.append(str(exc)[:500])
    if errors:
        state.series_synced = 0
        state.observations_upserted = 0
        state.last_error = "; ".join(errors)[:2_000]
        session.flush()
        return AlphaVantageListingSyncResult(
            snapshot_date=selected_date,
            active_assets=0,
            delisted_assets=0,
            total_assets=0,
            errors=errors,
        )

    active_rows = rows_by_state["active"]
    delisted_rows = rows_by_state["delisted"]
    all_rows = active_rows + delisted_rows
    for start in range(0, len(all_rows), 2_000):
        batch = all_rows[start : start + 2_000]
        statement = _dialect_insert(session, MarketAssetLifecycle).values(batch)
        statement = statement.on_conflict_do_update(
            index_elements=[MarketAssetLifecycle.asset_key],
            set_={
                key: getattr(statement.excluded, key)
                for key in batch[0]
                if key != "asset_key"
            },
        )
        session.execute(statement)

    ipo_dates = [row["ipo_date"] for row in all_rows if row["ipo_date"] is not None]
    delisting_dates = [
        row["delisting_date"] for row in delisted_rows if row["delisting_date"] is not None
    ]
    state.series_synced = len(all_rows)
    state.observations_upserted = 0
    state.last_success_at = datetime.now(UTC)
    state.last_error = None
    session.flush()
    return AlphaVantageListingSyncResult(
        snapshot_date=selected_date,
        active_assets=len(active_rows),
        delisted_assets=len(delisted_rows),
        total_assets=len(all_rows),
        earliest_ipo_date=min(ipo_dates, default=None),
        latest_delisting_date=max(delisting_dates, default=None),
    )


def alpha_vantage_listing_coverage(session: Session) -> dict[str, Any]:
    """Measure discovered lifecycle rows separately from locally priced histories."""
    total, active, delisted, first_ipo, last_delisting, snapshot_date = session.execute(
        select(
            func.count(MarketAssetLifecycle.asset_key),
            func.sum(case((MarketAssetLifecycle.listing_status == "active", 1), else_=0)),
            func.sum(case((MarketAssetLifecycle.listing_status == "delisted", 1), else_=0)),
            func.min(MarketAssetLifecycle.ipo_date),
            func.max(MarketAssetLifecycle.delisting_date),
            func.max(MarketAssetLifecycle.snapshot_date),
        ).where(MarketAssetLifecycle.provider_key == ALPHA_VANTAGE_PROVIDER_KEY)
    ).one()
    delisted_rows = list(
        session.execute(
            select(MarketAssetLifecycle.asset_key, MarketAssetLifecycle.symbol).where(
                MarketAssetLifecycle.provider_key == ALPHA_VANTAGE_PROVIDER_KEY,
                MarketAssetLifecycle.listing_status == "delisted",
            )
        )
    )
    priced_series = list(
        session.scalars(
            select(MarketSeries.series_id)
            .join(MarketObservation, MarketObservation.series_id == MarketSeries.series_id)
            .where(MarketSeries.category == "historical_equity_price")
            .distinct()
        )
    )
    priced_symbols = {
        parts[1].upper()
        for series_id in priced_series
        if len(parts := series_id.split(":")) >= 2 and parts[0] in {"HIST", "HISTSEC"}
    }
    price_covered = sum(1 for _, symbol in delisted_rows if symbol.upper() in priced_symbols)
    price_state_rows = list(
        session.execute(
            select(MarketPriceBackfillState.status, func.count())
            .group_by(MarketPriceBackfillState.status)
        )
    )
    price_status_counts = {str(status): int(count) for status, count in price_state_rows}
    state = session.get(MarketSyncState, ALPHA_VANTAGE_PROVIDER_KEY)
    identity_coverage = market_identity_coverage(session)
    evidence_coverage = market_delisting_evidence_coverage(session)
    return {
        "record_count": int(total or 0),
        "active_assets": int(active or 0),
        "delisted_assets": int(delisted or 0),
        "starts_at": ALPHA_VANTAGE_POINT_IN_TIME_BOUNDARY if total else None,
        "ends_at": snapshot_date or last_delisting,
        "earliest_ipo_date": first_ipo,
        "latest_delisting_date": last_delisting,
        "local_price_covered_delisted_assets": price_covered,
        "missing_price_delisted_assets": max(int(delisted or 0) - price_covered, 0),
        "price_backfill_status_counts": price_status_counts,
        "price_backfill_queued_assets": sum(price_status_counts.values()),
        "price_backfill_pending_assets": price_status_counts.get("pending", 0),
        "price_backfill_factor_ready_assets": price_status_counts.get("synced", 0),
        "price_backfill_partial_assets": price_status_counts.get("partial", 0),
        "price_backfill_unavailable_assets": price_status_counts.get("unavailable", 0),
        "price_backfill_ticker_reused_assets": price_status_counts.get("ticker_reused", 0),
        "point_in_time_boundary": ALPHA_VANTAGE_POINT_IN_TIME_BOUNDARY,
        "last_success_at": state.last_success_at if state else None,
        "last_error": state.last_error if state else None,
        **identity_coverage,
        **evidence_coverage,
    }


def _optional_date(value: str | None) -> date | None:
    text = (value or "").strip()
    if not text or text.casefold() in {"null", "none", "n/a", "na", "0000-00-00"}:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _asset_key(
    *,
    symbol: str,
    exchange: str,
    ipo_date: date | None,
    delisting_date: date | None,
    listing_status: str,
) -> str:
    identity = "|".join(
        (
            symbol,
            exchange,
            ipo_date.isoformat() if ipo_date else "unknown",
            delisting_date.isoformat() if delisting_date else "open",
            listing_status,
        )
    )
    return "av:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()
