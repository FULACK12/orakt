"""Major-market catalog and credential-gate tests."""

import asyncio

from app.core.config import Settings
from app.markets import MARKET_INDICES, list_market_indices


def test_market_catalog_is_available_without_exposing_or_requiring_a_key() -> None:
    settings = Settings(twelve_data_api_key=None)

    payload = asyncio.run(list_market_indices(settings, country_iso2="CA"))

    assert payload.quote_status == "credential_required"
    assert payload.fetched_at is None
    assert len(payload.indices) == 1
    assert payload.indices[0].code == "CA-TSX"
    assert payload.indices[0].provider_symbol == "EWC"
    assert payload.indices[0].quote_proxy_en
    assert payload.indices[0].close is None
    assert payload.indices[0].official_url.startswith("https://")
    assert len(MARKET_INDICES) >= 15
