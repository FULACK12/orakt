"""Backfill market history for source-verified public suppliers."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.models import (
    CompanyFiling,
    CompanyFinancialFact,
    CompanyProfile,
    CompanySupplyChainEdge,
    MarketObservation,
    MarketSeries,
    MarketSyncState,
)
from app.twelve_data_client import fetch_twelve_daily_values, get_twelve_earliest_date

SUPPLIER_MARKET_PROVIDER_PREFIX = "twelve_supplier:"
SUPPLIER_MARKET_SOURCE_URL = "https://twelvedata.com/docs"


class SupplierMarketHistorySyncResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_tickers: list[str] = Field(default_factory=list)
    completed_tickers: list[str] = Field(default_factory=list)
    observations_upserted: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)


def supplier_market_history_status(session: Session) -> dict[str, Any]:
    """Describe market coverage for every verified, ticker-resolved relation."""
    relations: dict[str, dict[str, Any]] = {}
    for ticker, company_name in session.execute(
        select(
            CompanySupplyChainEdge.related_ticker,
            CompanySupplyChainEdge.related_company_name,
        )
        .where(
            CompanySupplyChainEdge.review_status == "verified",
            CompanySupplyChainEdge.related_ticker.is_not(None),
        )
        .order_by(CompanySupplyChainEdge.related_ticker)
    ):
        if not ticker:
            continue
        normalized = str(ticker).strip().upper()
        item = relations.setdefault(
            normalized,
            {
                "ticker": normalized,
                "company_name": company_name,
                "verified_relation_count": 0,
            },
        )
        item["verified_relation_count"] += 1

    rows: list[dict[str, Any]] = []
    for ticker, item in sorted(relations.items()):
        series_id = f"EQ:{ticker}"
        observation_count, observed_start, observed_end = session.execute(
            select(
                func.count(MarketObservation.observed_on),
                func.min(MarketObservation.observed_on),
                func.max(MarketObservation.observed_on),
            ).where(MarketObservation.series_id == series_id)
        ).one()
        state = session.get(MarketSyncState, _provider_key(ticker))
        company_profile_available = session.get(CompanyProfile, ticker) is not None
        filing_count = int(
            session.scalar(
                select(func.count())
                .select_from(CompanyFiling)
                .where(CompanyFiling.ticker == ticker)
            )
            or 0
        )
        financial_fact_count = int(
            session.scalar(
                select(func.count())
                .select_from(CompanyFinancialFact)
                .where(CompanyFinancialFact.ticker == ticker)
            )
            or 0
        )
        status = "available" if observation_count else "pending"
        if not observation_count and state is not None and state.last_error:
            status = "retry_wait"
        rows.append(
            {
                **item,
                "series_id": series_id,
                "status": status,
                "observation_count": int(observation_count or 0),
                "observed_start": observed_start,
                "observed_end": observed_end,
                "last_started_at": state.last_started_at if state else None,
                "last_success_at": state.last_success_at if state else None,
                "last_error": state.last_error if state else None,
                "company_profile_available": company_profile_available,
                "filing_count": filing_count,
                "financial_fact_count": financial_fact_count,
            }
        )
    available = sum(row["status"] == "available" for row in rows)
    return {
        "tracked_tickers": len(rows),
        "available_tickers": available,
        "pending_tickers": len(rows) - available,
        "profiled_tickers": sum(row["company_profile_available"] for row in rows),
        "filing_tickers": sum(row["filing_count"] > 0 for row in rows),
        "fundamental_tickers": sum(row["financial_fact_count"] > 0 for row in rows),
        "rows": rows,
    }


async def sync_missing_supplier_market_history(
    session: Session,
    *,
    client: httpx.AsyncClient,
    api_key: str,
    history_start: date,
    history_end: date,
    batch_size: int = 2,
    request_interval_seconds: float = 16.0,
    retry_after: timedelta = timedelta(hours=24),
    commit_each_ticker: bool = False,
) -> SupplierMarketHistorySyncResult:
    """Fill a small restart-safe batch without treating prices as operating data."""
    if history_start > history_end:
        raise ValueError("history_start must not be after history_end")
    if batch_size < 1:
        raise ValueError("batch_size must be at least one")
    now = datetime.now(UTC)
    status = supplier_market_history_status(session)
    candidates = []
    for row in status["rows"]:
        if row["observation_count"]:
            continue
        last_started_at = row["last_started_at"]
        if (
            last_started_at is not None
            and _as_utc(last_started_at) > now - retry_after
        ):
            continue
        candidates.append(row)
    candidates.sort(
        key=lambda row: (-row["verified_relation_count"], row["ticker"])
    )
    candidates = candidates[:batch_size]

    selected = [str(row["ticker"]) for row in candidates]
    completed: list[str] = []
    errors: list[str] = []
    observations_upserted = 0
    for index, row in enumerate(candidates):
        if index and request_interval_seconds:
            await asyncio.sleep(request_interval_seconds)
        ticker = str(row["ticker"])
        state = _sync_state(
            session,
            ticker=ticker,
            history_start=history_start,
            history_end=history_end,
        )
        _upsert_series(
            session,
            ticker=ticker,
            company_name=str(row["company_name"]),
        )
        if commit_each_ticker:
            session.commit()
        try:
            provider_earliest = await get_twelve_earliest_date(
                client,
                symbol=ticker,
                api_key=api_key,
            )
            if request_interval_seconds:
                await asyncio.sleep(max(request_interval_seconds / 2, 0.0))
            raw_values = await fetch_twelve_daily_values(
                client,
                symbol=ticker,
                api_key=api_key,
                start_date=max(provider_earliest, history_start),
                end_date=history_end,
                request_interval_seconds=request_interval_seconds,
            )
            fetched_at = datetime.now(UTC)
            values = []
            for value in raw_values:
                observed_on = _parse_date(value.get("datetime"))
                close = _parse_float(value.get("close"))
                if observed_on is None or close is None or close <= 0:
                    continue
                values.append(
                    {
                        "series_id": f"EQ:{ticker}",
                        "observed_on": observed_on,
                        "value": close,
                        "fetched_at": fetched_at,
                    }
                )
            if not values:
                raise ValueError("provider returned no valid daily closes")
            upserted = _upsert_observations(session, values)
            state.series_synced = 1
            state.observations_upserted = upserted
            state.history_start = min(item["observed_on"] for item in values)
            state.history_end = max(item["observed_on"] for item in values)
            state.last_success_at = fetched_at
            state.last_error = None
            observations_upserted += upserted
            completed.append(ticker)
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            message = f"{ticker}: {type(exc).__name__}: {str(exc)[:180]}"
            state.last_error = message
            errors.append(message)
        session.flush()
        if commit_each_ticker:
            session.commit()
    return SupplierMarketHistorySyncResult(
        selected_tickers=selected,
        completed_tickers=completed,
        observations_upserted=observations_upserted,
        errors=errors,
    )


def _provider_key(ticker: str) -> str:
    return f"{SUPPLIER_MARKET_PROVIDER_PREFIX}{ticker}"[:64]


def _sync_state(
    session: Session,
    *,
    ticker: str,
    history_start: date,
    history_end: date,
) -> MarketSyncState:
    state = session.get(MarketSyncState, _provider_key(ticker))
    if state is None:
        state = MarketSyncState(
            provider_key=_provider_key(ticker),
            series_synced=0,
            observations_upserted=0,
        )
        session.add(state)
    state.last_started_at = datetime.now(UTC)
    state.history_start = history_start
    state.history_end = history_end
    state.last_error = None
    session.flush()
    return state


def _upsert_series(session: Session, *, ticker: str, company_name: str) -> None:
    insert = _dialect_insert(session, MarketSeries)
    statement = insert.values(
        series_id=f"EQ:{ticker}",
        name=f"{company_name} split-adjusted close",
        category="equity_price",
        unit="USD",
        frequency="daily",
        source_name="Twelve Data",
        source_url=SUPPLIER_MARKET_SOURCE_URL,
        listing_status="unknown",
        region="global_supplier",
        neutralization_group="supply_chain_supplier",
    )
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[MarketSeries.series_id],
            set_={
                "name": statement.excluded.name,
                "category": statement.excluded.category,
                "unit": statement.excluded.unit,
                "frequency": statement.excluded.frequency,
                "source_name": statement.excluded.source_name,
                "source_url": statement.excluded.source_url,
            },
        )
    )


def _upsert_observations(session: Session, rows: list[dict[str, Any]]) -> int:
    deduplicated = list(
        {
            (row["series_id"], row["observed_on"]): row
            for row in rows
        }.values()
    )
    for start in range(0, len(deduplicated), 5_000):
        batch = deduplicated[start : start + 5_000]
        insert = _dialect_insert(session, MarketObservation)
        statement = insert.values(batch)
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[
                    MarketObservation.series_id,
                    MarketObservation.observed_on,
                ],
                set_={
                    "value": statement.excluded.value,
                    "fetched_at": statement.excluded.fetched_at,
                },
            )
        )
    return len(deduplicated)


def _dialect_insert(session: Session, model: type[Any]) -> Any:
    if session.get_bind().dialect.name == "sqlite":
        return sqlite_insert(model)
    return postgresql_insert(model)


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _parse_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
