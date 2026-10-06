"""Versioned UCDP conflict collector tests."""

from __future__ import annotations

import asyncio
from datetime import date

import httpx
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.collectors.ucdp import UCDPConflictCollector
from app.db.base import Base
from app.db.models import CountryProfile, Document, Event, EventDocument


def test_ucdp_collector_authenticates_persists_and_deduplicates() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    token = "test-token-not-for-production"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-ucdp-access-token"] == token
        assert request.url.params["StartDate"] == "2026-06-01"
        assert request.url.params["EndDate"] == "2026-06-30"
        return httpx.Response(
            200,
            json={
                "TotalCount": 1,
                "TotalPages": 1,
                "Result": [
                    {
                        "id": 630513,
                        "relid": "UKR-2026-1-1",
                        "type_of_violence": 1,
                        "conflict_name": "Ukraine: Government",
                        "dyad_name": "Government of Ukraine - Russian forces",
                        "side_a": "Government of Ukraine",
                        "side_b": "Russian forces",
                        "code_status": "Clear",
                        "where_prec": 1,
                        "where_coordinates": "Kharkiv",
                        "where_description": "Kharkiv city",
                        "adm_1": "Kharkiv",
                        "adm_2": None,
                        "latitude": 49.9935,
                        "longitude": 36.2304,
                        "country": "Ukraine",
                        "country_id": 369,
                        "region": "Europe",
                        "event_clarity": 1,
                        "date_prec": 1,
                        "date_start": "2026-06-01",
                        "date_end": "2026-06-01",
                        "deaths_a": 1,
                        "deaths_b": 2,
                        "deaths_civilians": 3,
                        "deaths_unknown": 0,
                        "best": 6,
                        "high": 8,
                        "low": 5,
                        "number_of_sources": 2,
                        "source_article": "Example source",
                        "source_original": "Official statement",
                    }
                ],
            },
        )

    async def collect(session: Session) -> tuple[int, int]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as client:
            collector = UCDPConflictCollector(
                client,
                access_token=token,
                dataset_version="26.0.6",
            )
            first = await collector.collect(
                session,
                start_date=date(2026, 6, 1),
                end_date=date(2026, 6, 30),
            )
            second = await collector.collect(
                session,
                start_date=date(2026, 6, 1),
                end_date=date(2026, 6, 30),
            )
        return first.events_created, second.duplicates_skipped

    with Session(engine) as session:
        session.add(
            CountryProfile(
                iso3="UKR",
                iso2="UA",
                name="Ukraine",
                region="Europe & Central Asia",
                source_url="https://data.worldbank.org/country/ukraine",
            )
        )
        session.commit()
        created, duplicate = asyncio.run(collect(session))
        event = session.scalar(select(Event))
        document = session.scalar(select(Document))
        links = session.scalar(select(func.count()).select_from(EventDocument))

    assert created == 1
    assert duplicate == 1
    assert event is not None
    assert event.country_code == "UA"
    assert event.event_type == "state_based_conflict"
    assert float(event.confidence) == 0.97
    assert document is not None
    assert document.raw_metadata["fatalities_best"] == 6
    assert document.raw_metadata["dataset_version"] == "26.0.6"
    assert token not in str(document.raw_metadata)
    assert links == 1
    engine.dispose()
