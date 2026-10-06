"""Shared Twelve Data request pacing and rate-limit recovery."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

TWELVE_EARLIEST_TIMESTAMP_URL = "https://api.twelvedata.com/earliest_timestamp"
TWELVE_TIME_SERIES_URL = "https://api.twelvedata.com/time_series"
TRANSIENT_HTTP_STATUSES = {500, 502, 503, 504, 520, 522, 524}


def _raise_sanitized_http_error(response: httpx.Response) -> None:
    """Raise without including credential-bearing request URLs in logs or UI errors."""
    if response.is_error:
        raise ValueError(f"Twelve Data returned HTTP {response.status_code}")


async def request_twelve_data(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any],
    rate_limit_wait_seconds: float = 75.0,
    transient_wait_seconds: float = 5.0,
    max_attempts: int = 3,
) -> httpx.Response:
    """Retry rate limits and temporary provider/network failures safely."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least one")
    response: httpx.Response | None = None
    for attempt in range(max_attempts):
        try:
            response = await client.get(url, params=params)
        except httpx.TransportError:
            if attempt == max_attempts - 1:
                raise
            await asyncio.sleep(transient_wait_seconds * (2**attempt))
            continue
        if response.status_code == 429 and attempt < max_attempts - 1:
            retry_after = _retry_after_seconds(response)
            await asyncio.sleep(max(rate_limit_wait_seconds, retry_after))
            continue
        if response.status_code in TRANSIENT_HTTP_STATUSES and attempt < max_attempts - 1:
            await asyncio.sleep(transient_wait_seconds * (2**attempt))
            continue
        return response
    if response is None:
        raise RuntimeError("Twelve Data request did not execute")
    return response


def _retry_after_seconds(response: httpx.Response) -> float:
    value = response.headers.get("Retry-After")
    if value is None:
        return 0.0
    try:
        return max(0.0, float(value))
    except ValueError:
        return 0.0


async def get_twelve_earliest_date(
    client: httpx.AsyncClient,
    *,
    symbol: str,
    api_key: str,
) -> date:
    """Ask the provider for the symbol-specific daily-history boundary."""
    response = await request_twelve_data(
        client,
        TWELVE_EARLIEST_TIMESTAMP_URL,
        params={
            "symbol": symbol,
            "interval": "1day",
            "apikey": api_key,
        },
    )
    _raise_sanitized_http_error(response)
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("status") == "error":
        raise ValueError(str(payload.get("message") or "provider error"))
    raw_datetime = payload.get("datetime")
    if isinstance(raw_datetime, str):
        try:
            return date.fromisoformat(raw_datetime[:10])
        except ValueError:
            pass
    raw_unix = payload.get("unix_time")
    if isinstance(raw_unix, (int, float)):
        return datetime.fromtimestamp(raw_unix, tz=UTC).date()
    raise ValueError("Twelve Data earliest timestamp is missing")


async def fetch_twelve_daily_values(
    client: httpx.AsyncClient,
    *,
    symbol: str,
    api_key: str,
    start_date: date,
    end_date: date,
    request_interval_seconds: float = 16.0,
) -> list[dict[str, Any]]:
    """Fetch a long daily range in chunks below the provider's 5,000-row cap."""
    if start_date > end_date:
        return []
    values: list[dict[str, Any]] = []
    chunk_start = start_date
    chunk_index = 0
    while chunk_start <= end_date:
        if chunk_index and request_interval_seconds:
            await asyncio.sleep(request_interval_seconds)
        chunk_end = min(end_date, chunk_start + timedelta(days=3_650))
        response = await request_twelve_data(
            client,
            TWELVE_TIME_SERIES_URL,
            params={
                "symbol": symbol,
                "interval": "1day",
                "start_date": chunk_start.isoformat(),
                "end_date": chunk_end.isoformat(),
                "order": "asc",
                "adjust": "splits",
                "apikey": api_key,
            },
        )
        _raise_sanitized_http_error(response)
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("status") == "error":
            raise ValueError(str(payload.get("message") or "provider error"))
        raw_values = payload.get("values")
        if not isinstance(raw_values, list):
            raise TypeError("Twelve Data observations must be a list")
        values.extend(item for item in raw_values if isinstance(item, dict))
        chunk_start = chunk_end + timedelta(days=1)
        chunk_index += 1
    return values
