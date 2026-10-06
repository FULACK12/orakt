"""Historical FRED synchronization and transparent US cycle classification."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.models import MarketObservation, MarketSeries, MarketSyncState
from app.evidence_sources import FRED_OBSERVATIONS_URL, FRED_VALIDATION_SERIES
from app.factor_assets import FACTOR_ASSETS
from app.markets import MARKET_INDICES
from app.schemas.markets import MarketIndexResponse
from app.twelve_data_client import fetch_twelve_daily_values, get_twelve_earliest_date

FRED_PROVIDER_KEY = "fred_history"
TWELVE_DATA_PROVIDER_KEY = "twelve_data_history"
TWELVE_HISTORY_DEFINITIONS = (*MARKET_INDICES, *FACTOR_ASSETS)
FRED_SERIES_FREQUENCIES: dict[str, str] = {
    "DFF": "daily",
    "EFFR": "daily",
    "DFEDTARU": "daily",
    "DGS2": "daily",
    "DGS10": "daily",
    "SP500": "daily",
    "NASDAQCOM": "daily",
    "CPIAUCSL": "monthly",
    "PCEPI": "monthly",
    "T10YIE": "daily",
    "UNRATE": "monthly",
    "INDPRO": "monthly",
    "GDPC1": "quarterly",
    "RSAFS": "monthly",
    "DCOILWTICO": "daily",
    "VIXCLS": "daily",
    "DTWEXBGS": "daily",
    "BAMLH0A0HYM2": "daily",
    "T10Y2Y": "daily",
    "USREC": "monthly",
    "NFCI": "weekly",
    "PAYEMS": "monthly",
    "PCEPILFE": "monthly",
    "UMCSENT": "monthly",
    "HOUST": "monthly",
    "ICSA": "weekly",
    "M2SL": "monthly",
    "SAHMREALTIME": "monthly",
    "PERMIT": "monthly",
    "MORTGAGE30US": "weekly",
    "BUSINV": "monthly",
    "ISRATIO": "monthly",
    "DGORDER": "monthly",
    "GDPPOT": "quarterly",
    "NROU": "quarterly",
    "TDSP": "quarterly",
    "CFNAI": "monthly",
    "TCU": "monthly",
    "PPIACO": "monthly",
}


class MarketHistorySyncResult(BaseModel):
    """Summary of one provider synchronization."""

    model_config = ConfigDict(extra="forbid")

    provider_key: str = FRED_PROVIDER_KEY
    history_start: date
    history_end: date
    series_synced: int = Field(ge=0)
    observations_upserted: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)


def record_market_sync_start(
    session: Session,
    *,
    provider_key: str = FRED_PROVIDER_KEY,
    history_start: date,
    history_end: date,
) -> MarketSyncState:
    """Create or reset the provider audit row."""
    state = session.get(MarketSyncState, provider_key)
    if state is None:
        state = MarketSyncState(
            provider_key=provider_key,
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


async def sync_fred_history(
    session: Session,
    *,
    client: httpx.AsyncClient,
    api_key: str,
    history_start: date,
    history_end: date,
    request_interval_seconds: float = 0.55,
) -> MarketHistorySyncResult:
    """Retain a reviewed macro-financial catalog and all valid dated values."""
    if history_start > history_end:
        raise ValueError("history_start must not be after history_end")
    state = record_market_sync_start(
        session,
        provider_key=FRED_PROVIDER_KEY,
        history_start=history_start,
        history_end=history_end,
    )
    _upsert_series_catalog(session)
    fetched_at = datetime.now(UTC)
    errors: list[str] = []
    series_synced = 0
    observations_upserted = 0
    for index, series_id in enumerate(FRED_VALIDATION_SERIES):
        if index and request_interval_seconds:
            await asyncio.sleep(request_interval_seconds)
        try:
            response = await client.get(
                FRED_OBSERVATIONS_URL,
                params={
                    "series_id": series_id,
                    "api_key": api_key,
                    "file_type": "json",
                    "observation_start": history_start.isoformat(),
                    "observation_end": history_end.isoformat(),
                    "sort_order": "asc",
                    "limit": 100000,
                },
            )
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("observations")
            if not isinstance(rows, list):
                raise TypeError("FRED observations must be a list")
            values: list[dict[str, Any]] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                observed_on = _parse_date(row.get("date"))
                value = _parse_float(row.get("value"))
                if observed_on is None or value is None:
                    continue
                values.append(
                    {
                        "series_id": series_id,
                        "observed_on": observed_on,
                        "value": value,
                        "fetched_at": fetched_at,
                    }
                )
            observations_upserted += _upsert_observations(session, values)
            series_synced += 1
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            errors.append(f"{series_id}: {type(exc).__name__}")
    state.series_synced = series_synced
    state.observations_upserted = observations_upserted
    state.last_success_at = datetime.now(UTC) if series_synced else None
    state.last_error = "; ".join(errors)[:2_000] if errors else None
    session.flush()
    return MarketHistorySyncResult(
        provider_key=FRED_PROVIDER_KEY,
        history_start=history_start,
        history_end=history_end,
        series_synced=series_synced,
        observations_upserted=observations_upserted,
        errors=errors,
    )


async def sync_twelve_data_history(
    session: Session,
    *,
    client: httpx.AsyncClient,
    api_key: str,
    history_start: date,
    history_end: date,
    request_interval_seconds: float = 16.0,
    only_missing: bool = False,
    commit_each_series: bool = False,
) -> MarketHistorySyncResult:
    """Retain daily history for reviewed global proxies and factor assets."""
    if history_start > history_end:
        raise ValueError("history_start must not be after history_end")
    state = record_market_sync_start(
        session,
        provider_key=TWELVE_DATA_PROVIDER_KEY,
        history_start=history_start,
        history_end=history_end,
    )
    _upsert_twelve_series_catalog(session)
    if commit_each_series:
        session.commit()
    fetched_at = datetime.now(UTC)
    errors: list[str] = []
    series_synced = 0
    observations_upserted = 0
    requested_series = 0
    for definition in TWELVE_HISTORY_DEFINITIONS:
        series_id = f"TD:{definition.provider_symbol}"
        try:
            local_start, local_end = session.execute(
                select(
                    func.min(MarketObservation.observed_on),
                    func.max(MarketObservation.observed_on),
                ).where(MarketObservation.series_id == series_id)
            ).one()
            if only_missing and local_start is not None:
                continue
            if requested_series and request_interval_seconds:
                await asyncio.sleep(request_interval_seconds)
            requested_series += 1
            if local_start is None:
                provider_earliest = await get_twelve_earliest_date(
                    client,
                    symbol=definition.provider_symbol,
                    api_key=api_key,
                )
                if request_interval_seconds:
                    await asyncio.sleep(max(request_interval_seconds / 2, 0.0))
            else:
                provider_earliest = local_start
            selected_start = max(provider_earliest, history_start)
            if local_start is not None and local_end is not None and local_start <= selected_start:
                selected_start = max(
                    selected_start,
                    local_end - timedelta(days=10),
                )
            raw_values = await fetch_twelve_daily_values(
                client,
                symbol=definition.provider_symbol,
                api_key=api_key,
                start_date=selected_start,
                end_date=history_end,
                request_interval_seconds=request_interval_seconds,
            )
            values: list[dict[str, Any]] = []
            for row in raw_values:
                observed_on = _parse_date(row.get("datetime"))
                close = _parse_float(row.get("close"))
                if observed_on is None or close is None:
                    continue
                values.append(
                    {
                        "series_id": series_id,
                        "observed_on": observed_on,
                        "value": close,
                        "fetched_at": fetched_at,
                    }
                )
            observations_upserted += _upsert_observations(session, values)
            series_synced += 1
            if commit_each_series:
                state.series_synced = series_synced
                state.observations_upserted = observations_upserted
                state.last_success_at = datetime.now(UTC)
                session.commit()
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            errors.append(f"{definition.provider_symbol}: {type(exc).__name__}: {str(exc)[:120]}")
            if commit_each_series:
                state.last_error = "; ".join(errors)[-2_000:]
                session.commit()
    state.series_synced = series_synced
    state.observations_upserted = observations_upserted
    state.last_success_at = datetime.now(UTC) if series_synced else None
    state.last_error = "; ".join(errors)[:2_000] if errors else None
    session.flush()
    return MarketHistorySyncResult(
        provider_key=TWELVE_DATA_PROVIDER_KEY,
        history_start=history_start,
        history_end=history_end,
        series_synced=series_synced,
        observations_upserted=observations_upserted,
        errors=errors,
    )


def persist_twelve_market_snapshot(
    session: Session,
    response: MarketIndexResponse,
) -> int:
    """Retain validated daily closes returned by the live global panel."""
    _upsert_twelve_series_catalog(session)
    fetched_at = response.fetched_at or datetime.now(UTC)
    rows = [
        {
            "series_id": f"TD:{item.provider_symbol}",
            "observed_on": item.observed_on,
            "value": item.close,
            "fetched_at": fetched_at,
        }
        for item in response.indices
        if item.observed_on is not None and item.close is not None
    ]
    upserted = _upsert_observations(session, rows)
    state = session.get(MarketSyncState, TWELVE_DATA_PROVIDER_KEY)
    if state is None:
        state = MarketSyncState(
            provider_key=TWELVE_DATA_PROVIDER_KEY,
            series_synced=0,
            observations_upserted=0,
        )
        session.add(state)
    observed_dates: list[date] = [
        item.observed_on
        for item in response.indices
        if item.observed_on is not None and item.close is not None
    ]
    state.last_started_at = fetched_at
    state.last_success_at = fetched_at if rows else state.last_success_at
    state.history_start = min(observed_dates) if observed_dates else state.history_start
    state.history_end = max(observed_dates) if observed_dates else state.history_end
    state.series_synced = upserted
    state.observations_upserted = upserted
    missing = len(MARKET_INDICES) - upserted
    state.last_error = (
        f"live snapshot partial: {missing} of {len(MARKET_INDICES)} proxies unavailable"
        if missing
        else None
    )
    session.flush()
    return upserted


def build_cycle_snapshot(session: Session) -> dict[str, Any]:
    """Classify the current US cycle from explicit, auditable components."""
    series = {
        series_id: _series_values(session, series_id, limit=18)
        for series_id in (
            "USREC",
            "INDPRO",
            "GDPC1",
            "UNRATE",
            "T10Y2Y",
            "BAMLH0A0HYM2",
            "NFCI",
            "UMCSENT",
        )
    }
    components: list[dict[str, Any]] = []
    recession_value = _latest(series["USREC"])
    components.append(
        _component(
            "official_recession",
            "NBER recession indicator",
            -1.0 if recession_value is not None and recession_value >= 0.5 else 0.35,
            recession_value,
            "USREC",
        )
    )
    industrial_growth = _year_over_year(series["INDPRO"], periods=12)
    components.append(
        _component(
            "industrial_growth",
            "Industrial production year-over-year",
            _bounded((industrial_growth or 0.0) / 4.0),
            industrial_growth,
            "INDPRO",
        )
    )
    gdp_growth = _year_over_year(series["GDPC1"], periods=4)
    components.append(
        _component(
            "real_growth",
            "Real GDP year-over-year",
            _bounded((gdp_growth or 0.0) / 4.0),
            gdp_growth,
            "GDPC1",
        )
    )
    unemployment_change = _change(series["UNRATE"], periods=6)
    components.append(
        _component(
            "labour",
            "Six-month unemployment-rate change",
            _bounded(-(unemployment_change or 0.0) / 0.8),
            unemployment_change,
            "UNRATE",
        )
    )
    curve = _latest(series["T10Y2Y"])
    components.append(
        _component(
            "yield_curve",
            "10-year minus 2-year Treasury yield",
            _bounded((curve or 0.0) / 1.5),
            curve,
            "T10Y2Y",
        )
    )
    credit = _latest(series["BAMLH0A0HYM2"])
    components.append(
        _component(
            "credit",
            "High-yield option-adjusted spread",
            _bounded((4.5 - credit) / 2.5) if credit is not None else 0.0,
            credit,
            "BAMLH0A0HYM2",
        )
    )
    financial_conditions = _latest(series["NFCI"])
    components.append(
        _component(
            "financial_conditions",
            "Chicago Fed financial conditions",
            _bounded(-financial_conditions) if financial_conditions is not None else 0.0,
            financial_conditions,
            "NFCI",
        )
    )
    valid_components = [row for row in components if row["value"] is not None]
    score = (
        sum(float(row["score"]) for row in valid_components) / len(valid_components)
        if valid_components
        else 0.0
    )
    recession = recession_value is not None and recession_value >= 0.5
    if not valid_components:
        regime = "insufficient_data"
    elif recession or score <= -0.55:
        regime = "contraction"
    elif score <= -0.15:
        regime = "slowdown"
    elif score >= 0.45:
        regime = "expansion"
    elif (
        industrial_growth is not None
        and industrial_growth > 0
        and (unemployment_change is None or unemployment_change <= 0)
    ):
        regime = "recovery"
    else:
        regime = "late_cycle"
    observed_dates = [row["observed_on"] for values in series.values() for row in values[-1:]]
    return {
        "regime": regime,
        "score": round(score, 4),
        "as_of": max(observed_dates).isoformat() if observed_dates else None,
        "component_count": len(valid_components),
        "expected_component_count": len(components),
        "components": components,
        "methodology": (
            "Equal-weight directional score across recession, real activity, labour, "
            "yield curve, credit and financial conditions. This is a research regime "
            "classifier, not an investment recommendation."
        ),
    }


def _upsert_series_catalog(session: Session) -> None:
    rows = [
        {
            "series_id": series_id,
            "name": values[0],
            "category": values[1],
            "unit": values[2],
            "frequency": FRED_SERIES_FREQUENCIES.get(series_id, "unknown"),
            "source_name": "Federal Reserve Bank of St. Louis",
            "source_url": f"https://fred.stlouisfed.org/series/{series_id}",
        }
        for series_id, values in FRED_VALIDATION_SERIES.items()
    ]
    insert = _dialect_insert(session, MarketSeries)
    statement = insert.values(rows)
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


def _upsert_twelve_series_catalog(session: Session) -> None:
    rows = [
        {
            "series_id": f"TD:{definition.provider_symbol}",
            "name": (
                f"{definition.name_en} ({definition.provider_symbol} proxy)"
                if not hasattr(definition, "category")
                else definition.name_en
            ),
            "category": getattr(definition, "category", "global_market_proxy"),
            "unit": definition.currency,
            "frequency": "daily",
            "source_name": "Twelve Data",
            "source_url": "https://twelvedata.com/docs",
            "listing_status": "active",
            "sector": getattr(definition, "sector", None),
            "region": getattr(definition, "region", None),
            "neutralization_group": getattr(definition, "neutralization_group", None),
        }
        for definition in TWELVE_HISTORY_DEFINITIONS
    ]
    insert = _dialect_insert(session, MarketSeries)
    statement = insert.values(rows)
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
                "listing_status": statement.excluded.listing_status,
                "sector": statement.excluded.sector,
                "region": statement.excluded.region,
                "neutralization_group": statement.excluded.neutralization_group,
            },
        )
    )


def _upsert_observations(
    session: Session,
    rows: list[dict[str, Any]],
) -> int:
    deduplicated = list({(row["series_id"], row["observed_on"]): row for row in rows}.values())
    for start in range(0, len(deduplicated), 5_000):
        batch = deduplicated[start : start + 5_000]
        if not batch:
            continue
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


def _series_values(
    session: Session,
    series_id: str,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    rows = list(
        session.execute(
            select(MarketObservation.observed_on, MarketObservation.value)
            .where(MarketObservation.series_id == series_id)
            .order_by(desc(MarketObservation.observed_on))
            .limit(limit)
        )
    )
    rows.reverse()
    return [{"observed_on": observed_on, "value": float(value)} for observed_on, value in rows]


def market_history_coverage(session: Session) -> dict[str, Any]:
    """Return provider-level coverage for the source audit."""
    count, first_at, last_at, series_count = session.execute(
        select(
            func.count(MarketObservation.observed_on),
            func.min(MarketObservation.observed_on),
            func.max(MarketObservation.observed_on),
            func.count(func.distinct(MarketObservation.series_id)),
        )
        .select_from(MarketObservation)
        .join(MarketSeries, MarketSeries.series_id == MarketObservation.series_id)
        .where(MarketSeries.source_name == "Federal Reserve Bank of St. Louis")
    ).one()
    state = session.get(MarketSyncState, FRED_PROVIDER_KEY)
    return {
        "record_count": int(count or 0),
        "starts_at": first_at,
        "ends_at": last_at,
        "series_count": int(series_count or 0),
        "expected_series_count": len(FRED_VALIDATION_SERIES),
        "last_success_at": state.last_success_at if state else None,
        "last_error": state.last_error if state else None,
        "requested_history_start": state.history_start if state else None,
        "requested_history_end": state.history_end if state else None,
    }


def twelve_data_history_coverage(session: Session) -> dict[str, Any]:
    """Return measured local history for the reviewed Twelve Data asset panel."""
    count, first_at, last_at, series_count = session.execute(
        select(
            func.count(MarketObservation.observed_on),
            func.min(MarketObservation.observed_on),
            func.max(MarketObservation.observed_on),
            func.count(func.distinct(MarketObservation.series_id)),
        )
        .select_from(MarketObservation)
        .join(MarketSeries, MarketSeries.series_id == MarketObservation.series_id)
        .where(
            MarketObservation.series_id.in_(
                [f"TD:{definition.provider_symbol}" for definition in TWELVE_HISTORY_DEFINITIONS]
            )
        )
    ).one()
    state = session.get(MarketSyncState, TWELVE_DATA_PROVIDER_KEY)
    return {
        "record_count": int(count or 0),
        "starts_at": first_at,
        "ends_at": last_at,
        "series_count": int(series_count or 0),
        "expected_series_count": len(TWELVE_HISTORY_DEFINITIONS),
        "last_success_at": state.last_success_at if state else None,
        "last_error": state.last_error if state else None,
        "requested_history_start": state.history_start if state else None,
        "requested_history_end": state.history_end if state else None,
    }


def _component(
    key: str,
    label: str,
    score: float,
    value: float | None,
    series_id: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "series_id": series_id,
        "value": round(value, 4) if value is not None else None,
        "score": round(score, 4) if value is not None else 0.0,
    }


def _latest(values: list[dict[str, Any]]) -> float | None:
    return float(values[-1]["value"]) if values else None


def _change(values: list[dict[str, Any]], *, periods: int) -> float | None:
    if len(values) <= periods:
        return None
    return float(values[-1]["value"]) - float(values[-periods - 1]["value"])


def _year_over_year(values: list[dict[str, Any]], *, periods: int) -> float | None:
    if len(values) <= periods:
        return None
    latest = float(values[-1]["value"])
    previous = float(values[-periods - 1]["value"])
    if previous == 0:
        return None
    return ((latest / previous) - 1) * 100


def _bounded(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _parse_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed
