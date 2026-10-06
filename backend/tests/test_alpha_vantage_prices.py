"""Lifecycle-safe adjusted price backfill tests."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.alpha_vantage_listings import ALPHA_VANTAGE_PROVIDER_KEY
from app.alpha_vantage_prices import (
    AlphaVantagePriceError,
    fetch_alpha_vantage_weekly_adjusted,
    rank_price_backfill_candidates,
    sync_alpha_vantage_price_backfill,
)
from app.db.base import Base
from app.db.models import (
    MarketAssetLifecycle,
    MarketObservation,
    MarketPriceBackfillState,
    MarketSeries,
)
from app.storage.archive import ColdArchive


class UnavailableArchive(ColdArchive):
    """Archive test double that simulates an unavailable mounted disk."""

    def store_bytes(self, relative_path: str | Path, payload: bytes) -> str:
        raise FileNotFoundError("simulated missing archive mount")


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    engine.dispose()


def test_priority_queue_penalizes_warrants(session: Session) -> None:
    session.add_all(
        [
            _lifecycle("PLAIN", "Plain Operating Company", asset_type="Stock"),
            _lifecycle("SHELLW", "Shell Acquisition Corp - Warrants", asset_type="Stock"),
        ]
    )
    session.flush()

    ranked = rank_price_backfill_candidates(
        session,
        limit=2,
        as_of=date(2026, 8, 24),
    )

    assert [row.lifecycle.symbol for row in ranked] == ["PLAIN", "SHELLW"]
    assert "derivative_or_shell_penalty" in ranked[1].priority_reasons


def test_adjusted_history_is_archived_and_guarded_against_ticker_reuse(
    session: Session,
    tmp_path: Path,
) -> None:
    session.add_all(
        [
            _lifecycle("GOOD", "Good Operating Company", asset_type="Stock"),
            _lifecycle("REUSE", "Reused Symbol Company", asset_type="Stock"),
        ]
    )
    session.flush()

    def handler(request: httpx.Request) -> httpx.Response:
        symbol = request.url.params["symbol"]
        if symbol == "GOOD":
            rows = [
                f"{date(2026, 8, 21) - timedelta(days=index * 7)},1,2,1,2,{100 - index / 10},1000,0"
                for index in range(70)
            ]
        else:
            rows = ["2026-09-18,1,2,1,2,10,1000,0"]
        return httpx.Response(
            200,
            text=(
                "timestamp,open,high,low,close,adjusted close,volume,dividend amount\n"
                + "\n".join(rows)
            ),
        )

    async def synchronize() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await sync_alpha_vantage_price_backfill(
                session,
                client=client,
                api_key="test-secret",
                archive=ColdArchive(
                    tmp_path,
                    min_free_bytes=0,
                    max_used_percent=99,
                ),
                max_assets=2,
                queue_size=20,
                request_interval_seconds=0,
                now=datetime(2026, 8, 24, tzinfo=UTC),
            )
        assert result.attempted_assets == 2
        assert result.synced_assets == 1
        assert result.ticker_reused_assets == 1
        assert result.observations_upserted == 70

    asyncio.run(synchronize())
    session.commit()

    states = {
        row.asset_key: row for row in session.scalars(select(MarketPriceBackfillState))
    }
    good = next(row for row in states.values() if row.series_id is not None)
    reused = next(row for row in states.values() if row.status == "ticker_reused")
    assert good.status == "synced"
    assert good.raw_archive_path is not None
    assert (tmp_path / good.raw_archive_path).is_file()
    assert reused.series_id is None
    assert session.scalar(select(func.count()).select_from(MarketSeries)) == 1
    assert session.scalar(select(func.count()).select_from(MarketObservation)) == 70


def test_price_provider_error_never_echoes_api_key() -> None:
    secret = "do-not-print-price-key"

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"Information": "25 requests per day rate limit"})

    async def request() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await fetch_alpha_vantage_weekly_adjusted(
                client,
                api_key=secret,
                symbol="TEST",
            )

    with pytest.raises(AlphaVantagePriceError) as error:
        asyncio.run(request())
    assert error.value.code == "rate_limited"
    assert secret not in str(error.value)


def test_missing_cold_archive_is_recorded_without_crashing(
    session: Session,
    tmp_path: Path,
) -> None:
    session.add(_lifecycle("NODISK", "No Disk Company", asset_type="Stock"))
    session.flush()

    def handler(_: httpx.Request) -> httpx.Response:
        rows = [
            f"{date(2026, 8, 21) - timedelta(days=index * 7)},1,2,1,2,{100 - index / 10},1000,0"
            for index in range(70)
        ]
        return httpx.Response(
            200,
            text=(
                "timestamp,open,high,low,close,adjusted close,volume,dividend amount\n"
                + "\n".join(rows)
            ),
        )

    async def synchronize() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await sync_alpha_vantage_price_backfill(
                session,
                client=client,
                api_key="test-secret",
                archive=UnavailableArchive(tmp_path, min_free_bytes=0, max_used_percent=99),
                max_assets=1,
                queue_size=20,
                request_interval_seconds=0,
                now=datetime(2026, 8, 24, tzinfo=UTC),
            )
        assert result.errors == ["NODISK: cold_archive_io"]

    asyncio.run(synchronize())
    state = session.scalar(select(MarketPriceBackfillState))
    assert state is not None
    assert state.status == "failed"
    assert state.last_error_code == "cold_archive_io"


def _lifecycle(symbol: str, name: str, *, asset_type: str) -> MarketAssetLifecycle:
    return MarketAssetLifecycle(
        asset_key=f"av:test:{symbol}",
        provider_key=ALPHA_VANTAGE_PROVIDER_KEY,
        symbol=symbol,
        name=name,
        exchange="NASDAQ",
        asset_type=asset_type,
        ipo_date=date(2015, 1, 2),
        delisting_date=date(2026, 8, 21),
        listing_status="delisted",
        snapshot_date=date(2026, 8, 24),
        fetched_at=datetime(2026, 8, 24, tzinfo=UTC),
        source_url="https://www.alphavantage.co/documentation/",
    )
