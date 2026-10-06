"""Historical market materialization, cycle model and coverage audit tests."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from datetime import UTC, date, datetime

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.cycle_models import build_cycle_model_suite
from app.data_coverage import build_coverage_report
from app.db.base import Base
from app.db.models import MarketObservation, MarketSeries
from app.factor_assets import FACTOR_ASSETS
from app.market_history import (
    FRED_SERIES_FREQUENCIES,
    build_cycle_snapshot,
    persist_twelve_market_snapshot,
    sync_fred_history,
    sync_twelve_data_history,
)
from app.markets import MARKET_INDICES
from app.schemas.markets import MarketIndexResponse
from app.twelve_data_client import fetch_twelve_daily_values, request_twelve_data


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    engine.dispose()


def test_empty_coverage_report_exposes_missing_datasets(session: Session) -> None:
    report = build_coverage_report(
        session,
        settings=Settings(_env_file=None),
        now=datetime(2026, 7, 31, tzinfo=UTC),
    )

    assert report.target_starts_at == "2025-08-01"
    assert report.target_ends_at == "2026-07-31"
    assert next(row for row in report.datasets if row.key == "news_gdelt").status == "missing"
    assert next(row for row in report.datasets if row.key == "market_fred").status == "missing"


def test_fred_history_is_retained_and_drives_cycle_model(session: Session) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        series_id = request.url.params["series_id"]
        observations = []
        for index in range(18):
            month = (index % 12) + 1
            year = 2025 + (index // 12)
            observations.append(
                {
                    "date": date(year, month, 1).isoformat(),
                    "value": str(_series_value(series_id, index)),
                }
            )
        return httpx.Response(200, json={"observations": observations})

    async def synchronize() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as client:
            await sync_fred_history(
                session,
                client=client,
                api_key="test-key",
                history_start=date(1776, 7, 4),
                history_end=date(2026, 7, 31),
                request_interval_seconds=0,
            )

    asyncio.run(synchronize())
    session.commit()

    assert session.scalar(select(func.count()).select_from(MarketSeries)) == len(
        FRED_SERIES_FREQUENCIES
    )
    assert session.scalar(select(func.count()).select_from(MarketObservation)) == (
        len(FRED_SERIES_FREQUENCIES) * 18
    )
    cycle = build_cycle_snapshot(session)
    assert cycle["regime"] in {"expansion", "recovery", "late_cycle"}
    assert cycle["component_count"] == cycle["expected_component_count"]
    model_suite = build_cycle_model_suite(session)
    assert len(model_suite.models) == 8
    assert {model.key for model in model_suite.models} >= {
        "sahm_rule",
        "kitchin_inventory",
        "housing_leading",
        "taylor_policy_gap",
    }

    coverage = build_coverage_report(
        session,
        settings=Settings(
            _env_file=None,
            fred_api_key=SecretStr("test-key"),
        ),
        now=datetime(2026, 7, 31, tzinfo=UTC),
    )
    fred = next(row for row in coverage.datasets if row.key == "market_fred")
    assert fred.status == "complete"
    assert fred.record_count == len(FRED_SERIES_FREQUENCIES) * 18


def test_twelve_data_global_history_is_retained_with_proxy_labels(
    session: Session,
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if request.url.path.endswith("/earliest_timestamp"):
            return httpx.Response(200, json={"datetime": "2026-01-01 00:00:00"})
        assert request.url.params["interval"] == "1day"
        assert request.url.params["adjust"] == "splits"
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "values": [
                    {"datetime": "2026-07-29", "close": "100.5"},
                    {"datetime": "2026-07-29", "close": "100.5"},
                    {"datetime": "2026-07-30", "close": "101.25"},
                ],
            },
        )

    async def synchronize() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as client:
            await sync_twelve_data_history(
                session,
                client=client,
                api_key="test-key",
                history_start=date(1776, 7, 4),
                history_end=date(2026, 7, 31),
                request_interval_seconds=0,
            )
            await sync_twelve_data_history(
                session,
                client=client,
                api_key="test-key",
                history_start=date(1776, 7, 4),
                history_end=date(2026, 7, 31),
                request_interval_seconds=0,
                only_missing=True,
            )

    asyncio.run(synchronize())
    session.commit()

    twelve_series = list(
        session.scalars(select(MarketSeries).where(MarketSeries.source_name == "Twelve Data"))
    )
    assert len(twelve_series) == len(MARKET_INDICES) + len(FACTOR_ASSETS)
    assert calls == (len(MARKET_INDICES) + len(FACTOR_ASSETS)) * 2
    index_ids = {f"TD:{definition.provider_symbol}" for definition in MARKET_INDICES}
    assert all("proxy" in row.name for row in twelve_series if row.series_id in index_ids)

    coverage = build_coverage_report(
        session,
        settings=Settings(
            _env_file=None,
            twelve_data_api_key=SecretStr("test-key"),
        ),
        now=datetime(2026, 7, 31, tzinfo=UTC),
    )
    twelve = next(row for row in coverage.datasets if row.key == "market_twelve_data")
    assert twelve.status == "complete"
    assert twelve.record_count == (len(MARKET_INDICES) + len(FACTOR_ASSETS)) * 2


def test_factor_asset_catalog_covers_five_cross_asset_groups() -> None:
    assert len({definition.provider_symbol for definition in FACTOR_ASSETS}) == len(FACTOR_ASSETS)
    assert {definition.category for definition in FACTOR_ASSETS} == {
        "sector_etf",
        "bond_proxy",
        "commodity_proxy",
        "currency_proxy",
        "global_equity_price",
    }
    assert len({definition.neutralization_group for definition in FACTOR_ASSETS}) >= 10


def test_twelve_long_history_is_split_below_provider_row_cap() -> None:
    requested_ranges: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_ranges.append((request.url.params["start_date"], request.url.params["end_date"]))
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "values": [
                    {
                        "datetime": request.url.params["start_date"],
                        "close": "100",
                    }
                ],
            },
        )

    async def run() -> list[dict[str, object]]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_twelve_daily_values(
                client,
                symbol="MU",
                api_key="test",
                start_date=date(1984, 6, 1),
                end_date=date(2026, 8, 2),
                request_interval_seconds=0,
            )

    values = asyncio.run(run())
    assert len(values) == len(requested_ranges) == 5
    assert requested_ranges[0][0] == "1984-06-01"
    assert requested_ranges[-1][1] == "2026-08-02"


def test_twelve_http_error_does_not_expose_api_key() -> None:
    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(404))
        ) as client:
            await fetch_twelve_daily_values(
                client,
                symbol="OLD",
                api_key="secret-provider-key",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 2),
                request_interval_seconds=0,
            )

    with pytest.raises(ValueError, match="Twelve Data returned HTTP 404") as exc_info:
        asyncio.run(run())
    assert "secret-provider-key" not in str(exc_info.value)


def test_live_twelve_snapshot_is_retained(session: Session) -> None:
    response = MarketIndexResponse(
        provider="Twelve Data",
        provider_url="https://twelvedata.com/indices",
        quote_status="partial",
        delay_notice_en="Plan dependent.",
        delay_notice_zh="取决于套餐。",
        fetched_at=datetime(2026, 7, 31, tzinfo=UTC),
        indices=[
            {
                **definition.model_dump(),
                "observed_on": date(2026, 7, 30) if index < 2 else None,
                "close": 100.0 + index if index < 2 else None,
                "change_percent": None,
            }
            for index, definition in enumerate(MARKET_INDICES)
        ],
    )

    assert persist_twelve_market_snapshot(session, response) == 2
    session.commit()
    assert (
        session.scalar(
            select(func.count())
            .select_from(MarketObservation)
            .where(MarketObservation.series_id.like("TD:%"))
        )
        == 2
    )


def test_twelve_data_rate_limit_is_retried() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"status": "ok", "values": []})

    async def request() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as client:
            return await request_twelve_data(
                client,
                "https://api.twelvedata.com/time_series",
                params={"symbol": "SPY"},
                rate_limit_wait_seconds=0,
            )

    response = asyncio.run(request())

    assert response.status_code == 200
    assert calls == 2


def test_twelve_data_transient_provider_error_is_retried() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(502)
        return httpx.Response(200, json={"status": "ok", "values": []})

    async def request() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as client:
            return await request_twelve_data(
                client,
                "https://api.twelvedata.com/time_series",
                params={"symbol": "MU"},
                transient_wait_seconds=0,
            )

    response = asyncio.run(request())

    assert response.status_code == 200
    assert calls == 2


def _series_value(series_id: str, index: int) -> float:
    if series_id == "USREC":
        return 0
    if series_id in {"INDPRO", "GDPC1", "UMCSENT"}:
        return 100 + index
    if series_id == "UNRATE":
        return 5 - (index * 0.04)
    if series_id == "T10Y2Y":
        return 0.6
    if series_id == "BAMLH0A0HYM2":
        return 3.2
    if series_id == "NFCI":
        return -0.2
    return 10 + index
