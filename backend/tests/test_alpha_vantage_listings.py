"""Alpha Vantage lifecycle catalog and price-coverage tests."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from datetime import UTC, date, datetime

import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.alpha_vantage_listings import (
    AlphaVantageListingError,
    alpha_vantage_listing_coverage,
    fetch_alpha_vantage_listing_rows,
    sync_alpha_vantage_lifecycles,
)
from app.db.base import Base
from app.db.models import (
    MarketAssetLifecycle,
    MarketDelistingEvidenceCandidate,
    MarketObservation,
    MarketSeries,
)


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    engine.dispose()


def test_listing_catalog_sync_separates_discovery_from_price_coverage(
    session: Session,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["state"] == "active":
            return httpx.Response(
                200,
                text=(
                    "symbol,name,exchange,assetType,ipoDate,delistingDate,status\n"
                    "LIVE,Live Corp,NASDAQ,Stock,2019-01-02,null,Active\n"
                ),
            )
        return httpx.Response(
            200,
            text=(
                "symbol,name,exchange,assetType,ipoDate,delistingDate,status\n"
                "OLD,Old Corp,NYSE,Stock,2011-02-03,2018-04-05,Delisted\n"
                "NOPRICE,No Price Inc,NASDAQ,Stock,2012-01-01,2020-06-01,Delisted\n"
            ),
        )

    async def synchronize() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await sync_alpha_vantage_lifecycles(
                session,
                client=client,
                api_key="test-secret",
                snapshot_date=date(2026, 8, 24),
                request_interval_seconds=0,
            )
        assert result.active_assets == 1
        assert result.delisted_assets == 2
        assert result.total_assets == 3

    asyncio.run(synchronize())
    session.add(
        MarketSeries(
            series_id="HIST:OLD:NYSE:2011-02-03:2018-04-05",
            name="Old Corp",
            category="historical_equity_price",
            unit="USD",
            frequency="daily",
            source_name="Licensed test source",
            source_url="https://example.test/old",
            listing_status="delisted",
            listed_from=date(2011, 2, 3),
            listed_until=date(2018, 4, 5),
        )
    )
    session.add(
        MarketObservation(
            series_id="HIST:OLD:NYSE:2011-02-03:2018-04-05",
            observed_on=date(2018, 4, 4),
            value=12.5,
            fetched_at=datetime(2026, 8, 24, tzinfo=UTC),
        )
    )
    session.commit()

    assert session.scalar(select(func.count()).select_from(MarketAssetLifecycle)) == 3
    coverage = alpha_vantage_listing_coverage(session)
    assert coverage["active_assets"] == 1
    assert coverage["delisted_assets"] == 2
    assert coverage["local_price_covered_delisted_assets"] == 1
    assert coverage["missing_price_delisted_assets"] == 1
    assert coverage["point_in_time_boundary"] == date(2010, 1, 2)


def test_listing_error_is_sanitized_and_does_not_echo_api_key() -> None:
    secret = "never-print-this-key"

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"Information": "rate limit"})

    async def request() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await fetch_alpha_vantage_listing_rows(
                client,
                api_key=secret,
                state="active",
                snapshot_date=date(2026, 8, 24),
            )

    with pytest.raises(AlphaVantageListingError) as error:
        asyncio.run(request())
    assert secret not in str(error.value)
    assert "credential" in str(error.value)


def test_invalid_lifecycle_rows_are_not_retained(session: Session) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        status = "Active" if request.url.params["state"] == "active" else "Delisted"
        delisted = "null" if status == "Active" else "2010-01-01"
        return httpx.Response(
            200,
            text=(
                "symbol,name,exchange,assetType,ipoDate,delistingDate,status\n"
                f"VALID,Valid Corp,NASDAQ,Stock,2001-01-01,{delisted},{status}\n"
                f"BAD,Bad Dates,NYSE,Stock,2020-01-01,2010-01-01,{status}\n"
            ),
        )

    async def synchronize() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await sync_alpha_vantage_lifecycles(
                session,
                client=client,
                api_key="test-secret",
                snapshot_date=date(2026, 8, 24),
                request_interval_seconds=0,
            )

    asyncio.run(synchronize())
    session.commit()
    assert session.scalar(select(func.count()).select_from(MarketAssetLifecycle)) == 2


def test_catalog_refresh_preserves_historical_lifecycle_evidence(session: Session) -> None:
    legacy_key = "av:legacy-with-sec-evidence"
    session.add(
        MarketAssetLifecycle(
            asset_key=legacy_key,
            provider_key="alpha_vantage_listing_status",
            symbol="LEGACY",
            name="Legacy Corp",
            exchange="NASDAQ",
            asset_type="Stock",
            ipo_date=date(2010, 1, 4),
            delisting_date=date(2020, 1, 2),
            listing_status="delisted",
            snapshot_date=date(2026, 8, 30),
            fetched_at=datetime(2026, 8, 30, tzinfo=UTC),
            source_url="https://www.alphavantage.co/documentation/",
        )
    )
    session.add(
        MarketDelistingEvidenceCandidate(
            evidence_key="legacy-sec-evidence",
            asset_key=legacy_key,
            sec_cik="0000000001",
            subject_symbol="LEGACY",
            subject_sec_cik="0000000001",
            accession_number="0000000001-20-000001",
            document_name="legacy-8k.htm",
            form="8-K",
            filed_on=date(2020, 1, 2),
            observed_on=date(2020, 1, 2),
            source_url="https://www.sec.gov/Archives/legacy-8k.htm",
            evidence_type="cash_consideration_per_share",
            evidence_basis="filing_body_extract",
            candidate_value=10.0,
            value_unit="USD_per_share",
            evidence_excerpt="$10.00 per share",
            confidence=0.9,
            body_status="available",
            review_status="candidate",
        )
    )
    session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["state"] == "active":
            row = "LIVE,Live Corp,NASDAQ,Stock,2019-01-02,null,Active"
        else:
            row = "OLD,Old Corp,NYSE,Stock,2011-02-03,2018-04-05,Delisted"
        return httpx.Response(
            200,
            text=(
                "symbol,name,exchange,assetType,ipoDate,delistingDate,status\n"
                f"{row}\n"
            ),
        )

    async def synchronize() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await sync_alpha_vantage_lifecycles(
                session,
                client=client,
                api_key="test-secret",
                snapshot_date=date(2026, 9, 1),
                request_interval_seconds=0,
            )

    asyncio.run(synchronize())
    session.commit()

    assert session.get(MarketAssetLifecycle, legacy_key) is not None
    assert (
        session.get(MarketDelistingEvidenceCandidate, "legacy-sec-evidence")
        is not None
    )
