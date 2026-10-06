"""GeoJSON event map API tests."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Generator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.enums import EventStatus
from app.db.models import Event
from app.db.session import get_db_session
from app.main import app

EventAPI = tuple[Engine, Callable[[str], Response]]


@pytest.fixture
def event_api() -> Generator[EventAPI, None, None]:
    """Provide a shared in-memory database behind the real FastAPI route."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    def request(path: str) -> Response:
        async def send() -> Response:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.get(path)

        return asyncio.run(send())

    app.dependency_overrides[get_db_session] = override_session
    try:
        yield engine, request
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def seed_events(engine: Engine) -> None:
    """Insert located and unlocated events for filtering tests."""
    with Session(engine) as session:
        session.add_all(
            [
                Event(
                    event_type="interest_rate_change",
                    title="Bank of Japan raises its policy rate",
                    summary="A confirmed monetary-policy decision.",
                    status=EventStatus.CONFIRMED,
                    severity=Decimal("0.700"),
                    novelty=Decimal("0.600"),
                    confidence=Decimal("0.950"),
                    start_at=datetime(2026, 7, 29, 6, tzinfo=UTC),
                    latitude=Decimal("35.676200"),
                    longitude=Decimal("139.650300"),
                    country_code="JP",
                ),
                Event(
                    event_type="wildfire",
                    title="Wildfire expands in Alberta",
                    status=EventStatus.PARTIALLY_CONFIRMED,
                    severity=Decimal("0.800"),
                    novelty=Decimal("0.400"),
                    confidence=Decimal("0.750"),
                    start_at=datetime(2026, 7, 30, 12, tzinfo=UTC),
                    latitude=Decimal("53.933300"),
                    longitude=Decimal("-116.576500"),
                    country_code="CA",
                ),
                Event(
                    event_type="unlocated",
                    title="Event without map coordinates",
                    start_at=datetime(2026, 7, 31, tzinfo=UTC),
                    country_code="US",
                ),
            ]
        )
        session.commit()


def test_events_returns_geojson_points_newest_first(event_api: EventAPI) -> None:
    engine, request = event_api
    seed_events(engine)

    response = request("/events")

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == 2
    newest, oldest = payload["features"]
    assert newest["properties"]["title"] == "Wildfire expands in Alberta"
    assert newest["geometry"] == {
        "type": "Point",
        "coordinates": [-116.5765, 53.9333],
    }
    assert oldest["properties"]["severity"] == 0.7
    assert oldest["properties"]["status"] == "confirmed"
    assert isinstance(oldest["id"], int)


def test_events_filters_by_time_country_and_type(event_api: EventAPI) -> None:
    engine, request = event_api
    seed_events(engine)

    response = request(
        "/events?start=2026-07-29T00:00:00Z"
        "&end=2026-07-29T23:59:59Z"
        "&country=jp"
        "&event_type=interest_rate_change"
    )

    assert response.status_code == 200
    features = response.json()["features"]
    assert len(features) == 1
    assert features[0]["properties"]["country_code"] == "JP"


@pytest.mark.parametrize(
    "query",
    [
        "country=JPN",
        "country=1p",
        "start=2026-07-30T00:00:00Z&end=2026-07-29T00:00:00Z",
        "start=2026-07-29T00:00:00",
        "limit=0",
        "limit=1001",
        "unsupported=value",
    ],
)
def test_events_rejects_invalid_filters(event_api: EventAPI, query: str) -> None:
    _, request = event_api

    response = request(f"/events?{query}")

    assert response.status_code == 422


def test_events_honours_limit(event_api: EventAPI) -> None:
    engine, request = event_api
    seed_events(engine)

    response = request("/events?limit=1")

    assert response.status_code == 200
    assert len(response.json()["features"]) == 1
