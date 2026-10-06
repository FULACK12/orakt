"""Validated economic collection, persistence and HTTP endpoint tests."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime

import httpx
from httpx import ASGITransport, AsyncClient, Request, Response
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import (
    CountryProfile,
    EconomicIndicator,
    EconomicObservation,
)
from app.db.session import get_db_session
from app.economics.world_bank import (
    ECONOMIC_INDICATORS,
    WorldBankClient,
    sync_world_bank,
)
from app.main import app


def _world_bank_response(request: Request) -> Response:
    metadata = {
        "page": 1,
        "pages": 1,
        "per_page": 20000,
        "total": 2,
    }
    if request.url.path.endswith("/country"):
        return Response(
            200,
            json=[
                metadata,
                [
                    {
                        "id": "CAN",
                        "iso2Code": "CA",
                        "name": "Canada",
                        "region": {
                            "id": "NAC",
                            "value": "North America",
                        },
                        "incomeLevel": {
                            "id": "HIC",
                            "value": "High income",
                        },
                        "capitalCity": "Ottawa",
                        "longitude": "-75.6919",
                        "latitude": "45.4215",
                    },
                    {
                        "id": "WLD",
                        "iso2Code": "1W",
                        "name": "World",
                        "region": {
                            "id": "NA",
                            "value": "Aggregates",
                        },
                        "incomeLevel": {
                            "id": "NA",
                            "value": "Aggregates",
                        },
                        "capitalCity": "",
                        "longitude": "",
                        "latitude": "",
                    },
                ],
            ],
        )
    indicator_code = request.url.path.rsplit("/", 1)[-1]
    return Response(
        200,
        json=[
            metadata,
            [
                {
                    "indicator": {
                        "id": indicator_code,
                        "value": indicator_code,
                    },
                    "country": {"id": "CA", "value": "Canada"},
                    "countryiso3code": "CAN",
                    "date": "2024",
                    "value": 2.4,
                },
                {
                    "indicator": {
                        "id": indicator_code,
                        "value": indicator_code,
                    },
                    "country": {"id": "1W", "value": "World"},
                    "countryiso3code": "WLD",
                    "date": "2024",
                    "value": 3.0,
                },
            ],
        ],
    )


def test_world_bank_sync_is_validated_and_idempotent() -> None:
    async def run() -> tuple[object, object]:
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        transport = httpx.MockTransport(_world_bank_response)
        async with AsyncClient(transport=transport) as http_client:
            client = WorldBankClient(http_client)
            with Session(engine) as session:
                first = await sync_world_bank(
                    session,
                    client,
                    start_year=2024,
                    end_year=2024,
                )
                session.commit()
                second = await sync_world_bank(
                    session,
                    client,
                    start_year=2024,
                    end_year=2024,
                )
                session.commit()

                assert session.scalar(
                    select(func.count()).select_from(CountryProfile)
                ) == 1
                assert session.scalar(
                    select(func.count()).select_from(EconomicIndicator)
                ) == len(ECONOMIC_INDICATORS)
                assert session.scalar(
                    select(func.count()).select_from(EconomicObservation)
                ) == len(ECONOMIC_INDICATORS)
        return first, second

    first, second = asyncio.run(run())

    assert first.observations_upserted == len(ECONOMIC_INDICATORS)
    assert second.observations_upserted == len(ECONOMIC_INDICATORS)


def test_world_bank_sync_isolates_one_indicator_failure() -> None:
    failed_code = ECONOMIC_INDICATORS[0].code

    def handler(request: Request) -> Response:
        if request.url.path.endswith(f"/{failed_code}"):
            return Response(400, json={"message": "temporary provider failure"})
        return _world_bank_response(request)

    async def run() -> object:
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        async with AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with Session(engine) as session:
                result = await sync_world_bank(
                    session,
                    WorldBankClient(client),
                    start_year=2024,
                    end_year=2024,
                )
                session.commit()
                assert session.scalar(
                    select(func.count()).select_from(EconomicObservation)
                ) == len(ECONOMIC_INDICATORS) - 1
        engine.dispose()
        return result

    result = asyncio.run(run())
    assert result.failed_indicators.keys() == {failed_code}


def test_economic_map_endpoint_returns_bilingual_traceable_data() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    async def seed() -> None:
        transport = httpx.MockTransport(_world_bank_response)
        async with AsyncClient(transport=transport) as http_client:
            with Session(engine) as session:
                await sync_world_bank(
                    session,
                    WorldBankClient(http_client),
                    start_year=2024,
                    end_year=2024,
                )
                session.commit()

    asyncio.run(seed())

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    async def request() -> tuple[
        dict[str, object],
        dict[str, object],
        dict[str, object],
        dict[str, object],
    ]:
        app.dependency_overrides[get_db_session] = override_session
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                catalog_response = await client.get("/economics/indicators")
                map_response = await client.get(
                    "/economics/map",
                    params={"indicator_code": "FP.CPI.TOTL.ZG"},
                )
                country_response = await client.get("/economics/countries/ca")
                ranking_response = await client.get(
                    "/economics/rankings",
                    params={"year": 2024, "country_iso2": "CA"},
                )
            assert catalog_response.status_code == 200
            assert map_response.status_code == 200
            assert country_response.status_code == 200
            assert ranking_response.status_code == 200
            return (
                catalog_response.json(),
                map_response.json(),
                country_response.json(),
                ranking_response.json(),
            )
        finally:
            app.dependency_overrides.pop(get_db_session, None)

    catalog, map_payload, country_payload, ranking_payload = asyncio.run(
        request()
    )

    assert len(catalog["indicators"]) == len(ECONOMIC_INDICATORS)
    assert map_payload["selected_year"] == 2024
    assert datetime.now(UTC).year in map_payload["available_years"]
    assert map_payload["country_count"] == 1
    assert map_payload["indicator"]["name_zh"] == "消费者价格通胀率"
    assert map_payload["points"][0]["country_name"] == "Canada"
    assert map_payload["points"][0]["value"] == 2.4
    assert country_payload["iso2"] == "CA"
    assert country_payload["metrics"][0]["year"] == 2024
    assert ranking_payload["year"] == 2024
    assert ranking_payload["countries"][0]["iso2"] == "CA"
    assert ranking_payload["countries"][0]["rank"] == 1
    assert ranking_payload["countries"][0]["metric_ranks"]
    assert ranking_payload["weights"]
    Base.metadata.drop_all(engine)
    engine.dispose()
