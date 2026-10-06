"""SEC company fundamentals and reviewed price history tests."""

from __future__ import annotations

import asyncio
from datetime import date

import httpx
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.companies import (
    COMPANY_CATALOG,
    company_coverage,
    sync_company_price_history,
    sync_sec_company_history,
)
from app.db.base import Base
from app.db.models import (
    CompanyFiling,
    CompanyFinancialFact,
    CompanyProfile,
    MarketDailyBar,
    MarketObservation,
)


def test_lululemon_official_identity_is_in_reviewed_catalog() -> None:
    profile = next(item for item in COMPANY_CATALOG if item[0] == "LULU")

    assert profile == (
        "LULU",
        "0001397187",
        "lululemon athletica inc.",
        "Consumer",
        "Athletic apparel and footwear",
    )


def test_sec_facts_filings_and_prices_are_retained() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    def sec_handler(request: httpx.Request) -> httpx.Response:
        cik = request.url.path.rsplit("CIK", 1)[-1].removesuffix(".json")
        accession_number = f"{cik}-26-000001"
        if "/submissions/" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "filings": {
                        "recent": {
                            "accessionNumber": [accession_number],
                            "filingDate": ["2026-07-20"],
                            "reportDate": ["2026-06-30"],
                            "form": ["10-Q"],
                            "primaryDocument": ["quarterly.htm"],
                        }
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "facts": {
                    "us-gaap": {
                        "Revenues": {
                            "label": "Revenue",
                            "description": "Quarterly revenue",
                            "units": {
                                "USD": [
                                    {
                                        "start": "2026-04-01",
                                        "end": "2026-06-30",
                                        "val": 1000000000,
                                        "accn": accession_number,
                                        "fy": 2026,
                                        "fp": "Q2",
                                        "form": "10-Q",
                                        "filed": "2026-07-20",
                                        "frame": "CY2026Q2",
                                    },
                                    {
                                        "start": "2026-04-01",
                                        "end": "2026-06-30",
                                        "val": 1000000000,
                                        "accn": accession_number,
                                        "fy": 2026,
                                        "fp": "Q2",
                                        "form": "10-Q",
                                        "filed": "2026-07-20",
                                        "frame": None,
                                    },
                                ]
                            },
                        }
                    }
                }
            },
        )

    def price_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/earliest_timestamp"):
            return httpx.Response(200, json={"datetime": "2026-01-01 00:00:00"})
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "values": [
                    {"datetime": "2026-07-29", "open": "99", "high": "102", "low": "98", "close": "100", "volume": "1200000"},
                    {"datetime": "2026-07-29", "open": "99", "high": "102", "low": "98", "close": "100", "volume": "1200000"},
                    {"datetime": "2026-07-30", "open": "100", "high": "103", "low": "99", "close": "101", "volume": "1500000"},
                ],
            },
        )

    async def synchronize(session: Session) -> None:
        async with httpx.AsyncClient(
            base_url="https://data.sec.gov",
            transport=httpx.MockTransport(sec_handler),
        ) as client:
            result = await sync_sec_company_history(
                session,
                client=client,
                request_interval_seconds=0,
            )
        assert result.companies_synced == len(COMPANY_CATALOG)
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(price_handler),
        ) as client:
            prices = await sync_company_price_history(
                session,
                client=client,
                api_key="test",
                history_start=date(2026, 1, 1),
                history_end=date(2026, 7, 31),
                request_interval_seconds=0,
            )
        assert prices.companies_synced == len(COMPANY_CATALOG)

    with Session(engine) as session:
        asyncio.run(synchronize(session))
        session.commit()
        assert session.scalar(select(func.count()).select_from(CompanyProfile)) == len(
            COMPANY_CATALOG
        )
        assert session.scalar(select(func.count()).select_from(CompanyFiling)) == len(
            COMPANY_CATALOG
        )
        assert session.scalar(
            select(func.count()).select_from(CompanyFinancialFact)
        ) == len(COMPANY_CATALOG)
        assert session.scalar(
            select(func.count()).select_from(MarketObservation)
        ) == len(COMPANY_CATALOG) * 2
        assert session.scalar(
            select(func.count()).select_from(MarketDailyBar)
        ) == len(COMPANY_CATALOG) * 2
        coverage = company_coverage(session)
        assert coverage["priced_companies"] == len(COMPANY_CATALOG)
        assert coverage["fact_count"] == len(COMPANY_CATALOG)
    engine.dispose()


def test_sec_history_can_be_limited_to_requested_tickers() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    requested_ciks: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cik = request.url.path.rsplit("CIK", 1)[-1].removesuffix(".json")
        requested_ciks.append(cik)
        if "/submissions/" in request.url.path:
            return httpx.Response(200, json={"filings": {"recent": {"form": []}}})
        return httpx.Response(200, json={"facts": {}})

    async def run(session: Session) -> object:
        async with httpx.AsyncClient(
            base_url="https://data.sec.gov",
            transport=httpx.MockTransport(handler),
        ) as client:
            return await sync_sec_company_history(
                session,
                client=client,
                request_interval_seconds=0,
                tickers={"AAPL", "MU"},
            )

    with Session(engine) as session:
        result = asyncio.run(run(session))

    assert result.companies_synced == 2
    assert len(requested_ciks) == 4
    assert set(requested_ciks) == {"0000320193", "0000723125"}
    engine.dispose()


def test_ifrs_full_core_financial_facts_are_retained() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    def handler(request: httpx.Request) -> httpx.Response:
        if "/submissions/" in request.url.path:
            return httpx.Response(200, json={"filings": {"recent": {"form": []}}})
        return httpx.Response(
            200,
            json={
                "facts": {
                    "ifrs-full": {
                        "Revenue": {
                            "label": "Revenue",
                            "description": "Revenue under IFRS",
                            "units": {
                                "USD": [
                                    {
                                        "start": "2025-01-01",
                                        "end": "2025-12-31",
                                        "val": 10_000_000,
                                        "accn": "0000320193-26-000001",
                                        "fy": 2025,
                                        "fp": "FY",
                                        "form": "20-F",
                                        "filed": "2026-02-01",
                                    }
                                ]
                            },
                        },
                        "UnreviewedCustomMetric": {
                            "label": "Custom",
                            "units": {},
                        },
                    }
                }
            },
        )

    async def run(session: Session) -> object:
        async with httpx.AsyncClient(
            base_url="https://data.sec.gov",
            transport=httpx.MockTransport(handler),
        ) as client:
            return await sync_sec_company_history(
                session,
                client=client,
                request_interval_seconds=0,
                tickers={"AAPL"},
            )

    with Session(engine) as session:
        result = asyncio.run(run(session))
        fact = session.scalar(select(CompanyFinancialFact))

    assert result.companies_synced == 1
    assert fact is not None
    assert fact.taxonomy == "ifrs-full"
    assert fact.concept == "Revenue"
    assert fact.value == 10_000_000
    engine.dispose()
