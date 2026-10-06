"""Official SEC identity discovery for verified suppliers."""

from __future__ import annotations

import asyncio
from datetime import date

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import CompanyProfile, CompanySupplyChainEdge
from app.supplier_company_discovery import sync_supplier_company_profiles_from_sec


def test_sec_catalog_creates_profile_only_for_matched_verified_supplier() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                _edge("AAPL", "Analog Devices Incorporated", "ADI", "verified"),
                _edge("AAPL", "Private Supplier", "PRIVATE", "verified"),
                _edge("AAPL", "Unreviewed Supplier", "NOPE", "candidate"),
            ]
        )
        session.commit()

        async def run() -> object:
            def handler(_: httpx.Request) -> httpx.Response:
                return httpx.Response(
                    200,
                    json={
                        "0": {
                            "cik_str": 6281,
                            "ticker": "ADI",
                            "title": "ANALOG DEVICES INC",
                        }
                    },
                )

            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                return await sync_supplier_company_profiles_from_sec(
                    session,
                    client=client,
                )

        result = asyncio.run(run())
        session.commit()
        cached_result = asyncio.run(run())
        profile = session.get(CompanyProfile, "ADI")
        unreviewed_profile = session.get(CompanyProfile, "NOPE")

    assert result.candidate_tickers == ["ADI", "PRIVATE"]
    assert result.matched_tickers == ["ADI"]
    assert result.unresolved_tickers == ["PRIVATE"]
    assert cached_result.skipped_recently is True
    assert cached_result.unresolved_tickers == ["PRIVATE"]
    assert profile is not None
    assert profile.cik == "0000006281"
    assert profile.name == "ANALOG DEVICES INC"
    assert profile.industry == "SEC identity resolved; classification pending"
    assert unreviewed_profile is None
    engine.dispose()


def _edge(
    subject: str,
    related_name: str,
    related_ticker: str,
    review_status: str,
) -> CompanySupplyChainEdge:
    return CompanySupplyChainEdge(
        subject_ticker=subject,
        related_company_name=related_name,
        related_ticker=related_ticker,
        relationship_type="supplier",
        product_or_input="supplier relation",
        geography=None,
        dependency_level="unknown",
        review_status=review_status,
        confidence=0.82,
        source_kind="issuer_supplier_list",
        source_ref=f"supplier:{related_ticker}",
        source_url="https://example.test/suppliers.pdf",
        source_excerpt=f"{related_name} is listed as a supplier.",
        observed_at=date(2023, 9, 30),
        available_at=date(2024, 4, 1),
    )
