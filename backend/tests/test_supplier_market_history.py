"""Verified-supplier market-history backfill tests."""

from __future__ import annotations

import asyncio
from datetime import date

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import CompanySupplyChainEdge
from app.supplier_market_history import (
    supplier_market_history_status,
    sync_missing_supplier_market_history,
)


def test_verified_supplier_ticker_is_backfilled_and_visible() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            CompanySupplyChainEdge(
                subject_ticker="AAPL",
                related_company_name="Taiwan Semiconductor Manufacturing Company Limited",
                related_ticker="TSM",
                relationship_type="supplier",
                product_or_input="FY2023 direct-spend supplier",
                geography="Taiwan",
                dependency_level="unknown",
                review_status="verified",
                confidence=0.82,
                source_kind="issuer_supplier_list",
                source_ref="apple-supplier-list:FY2023:001",
                source_url="https://example.test/apple-suppliers.pdf",
                source_excerpt="Apple lists TSMC as a supplier.",
                observed_at=date(2023, 9, 30),
                available_at=date(2024, 4, 1),
            )
        )
        session.commit()

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/earliest_timestamp"):
                return httpx.Response(200, json={"datetime": "2026-01-02 09:30:00"})
            return httpx.Response(
                200,
                json={
                    "values": [
                        {"datetime": "2026-01-02", "close": "100.0"},
                        {"datetime": "2026-01-05", "close": "102.5"},
                    ]
                },
            )

        async def run() -> object:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                return await sync_missing_supplier_market_history(
                    session,
                    client=client,
                    api_key="test-key",
                    history_start=date(1900, 1, 1),
                    history_end=date(2026, 1, 5),
                    batch_size=2,
                    request_interval_seconds=0,
                )

        result = asyncio.run(run())
        status = supplier_market_history_status(session)

    assert result.completed_tickers == ["TSM"]
    assert result.observations_upserted == 2
    assert result.errors == []
    assert status["tracked_tickers"] == 1
    assert status["available_tickers"] == 1
    assert status["rows"][0]["observed_start"] == date(2026, 1, 2)
    assert status["rows"][0]["observed_end"] == date(2026, 1, 5)
    engine.dispose()
