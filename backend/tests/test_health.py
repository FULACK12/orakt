"""HTTP liveness tests."""

import asyncio

from httpx import ASGITransport, AsyncClient, Response

from app.main import app


def test_health_returns_service_metadata() -> None:
    async def request_health() -> Response:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/health")

    response = asyncio.run(request_health())

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "NEWS App API"
    assert payload["version"] == "0.22.0"
    assert payload["environment"] == "development"
    assert payload["timestamp"].endswith("Z")
