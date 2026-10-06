"""Reviewed global index catalog with an optional Twelve Data quote adapter."""

# ruff: noqa: RUF001

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.core.config import Settings
from app.schemas.markets import MarketIndexResponse, MarketIndexView

PROVIDER_NAME = "Twelve Data"
PROVIDER_URL = "https://twelvedata.com/indices"


class MarketIndexDefinition(BaseModel):
    """Reviewed identity and provenance for a headline trading index."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    provider_symbol: str
    name_en: str
    name_zh: str
    country_iso2: str = Field(min_length=2, max_length=2)
    exchange: str
    currency: str
    official_url: str
    quote_proxy_en: str | None = None
    quote_proxy_zh: str | None = None


MARKET_INDICES = TypeAdapter(list[MarketIndexDefinition]).validate_python(
    [
        {
            "code": "US-SPX",
            "provider_symbol": "SPY",
            "name_en": "S&P 500",
            "name_zh": "标普 500 指数",
            "country_iso2": "US",
            "exchange": "S&P Dow Jones Indices",
            "currency": "USD",
            "official_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
            "quote_proxy_en": "SPY ETF proxy; not the index itself",
            "quote_proxy_zh": "使用 SPY ETF 代理行情，并非指数本身",
        },
        {
            "code": "US-DJI",
            "provider_symbol": "DIA",
            "name_en": "Dow Jones Industrial Average",
            "name_zh": "道琼斯工业平均指数",
            "country_iso2": "US",
            "exchange": "S&P Dow Jones Indices",
            "currency": "USD",
            "official_url": "https://www.spglobal.com/spdji/en/indices/equity/dow-jones-industrial-average/",
            "quote_proxy_en": "DIA ETF proxy; not the index itself",
            "quote_proxy_zh": "使用 DIA ETF 代理行情，并非指数本身",
        },
        {
            "code": "US-IXIC",
            "provider_symbol": "QQQ",
            "name_en": "Nasdaq Composite",
            "name_zh": "纳斯达克综合指数",
            "country_iso2": "US",
            "exchange": "Nasdaq",
            "currency": "USD",
            "official_url": "https://indexes.nasdaqomx.com/Index/Overview/COMP",
            "quote_proxy_en": "QQQ (Nasdaq-100) ETF proxy; not the Composite index",
            "quote_proxy_zh": "使用 QQQ（纳斯达克 100）ETF 代理，并非综合指数本身",
        },
        {
            "code": "CA-TSX",
            "provider_symbol": "EWC",
            "name_en": "S&P/TSX Composite",
            "name_zh": "标普/多伦多证交所综合指数",
            "country_iso2": "CA",
            "exchange": "Toronto Stock Exchange",
            "currency": "USD",
            "official_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-tsx-composite-index/",
            "quote_proxy_en": "EWC broad-Canada ETF proxy; not the index itself",
            "quote_proxy_zh": "使用 EWC 加拿大市场 ETF 代理行情，并非指数本身",
        },
        {
            "code": "GB-FTSE",
            "provider_symbol": "EWU",
            "name_en": "FTSE 100",
            "name_zh": "富时 100 指数",
            "country_iso2": "GB",
            "exchange": "London Stock Exchange",
            "currency": "GBP",
            "official_url": "https://www.lseg.com/en/ftse-russell/indices/uk",
            "quote_proxy_en": "EWU ETF proxy; not the index itself",
            "quote_proxy_zh": "使用 EWU ETF 代理行情，并非指数本身",
        },
        {
            "code": "DE-DAX",
            "provider_symbol": "EWG",
            "name_en": "DAX",
            "name_zh": "德国 DAX 指数",
            "country_iso2": "DE",
            "exchange": "Frankfurt Stock Exchange",
            "currency": "EUR",
            "official_url": "https://www.dax-indices.com/",
            "quote_proxy_en": "EWG ETF proxy; not the index itself",
            "quote_proxy_zh": "使用 EWG ETF 代理行情，并非指数本身",
        },
        {
            "code": "FR-CAC40",
            "provider_symbol": "EWQ",
            "name_en": "CAC 40",
            "name_zh": "法国 CAC 40 指数",
            "country_iso2": "FR",
            "exchange": "Euronext Paris",
            "currency": "EUR",
            "official_url": "https://live.euronext.com/en/product/indices/FR0003500008-XPAR",
            "quote_proxy_en": "EWQ ETF proxy; not the index itself",
            "quote_proxy_zh": "使用 EWQ ETF 代理行情，并非指数本身",
        },
        {
            "code": "JP-N225",
            "provider_symbol": "EWJ",
            "name_en": "Nikkei 225",
            "name_zh": "日经 225 指数",
            "country_iso2": "JP",
            "exchange": "Japan Exchange Group",
            "currency": "JPY",
            "official_url": "https://indexes.nikkei.co.jp/en/nkave",
            "quote_proxy_en": "EWJ ETF proxy; not the index itself",
            "quote_proxy_zh": "使用 EWJ ETF 代理行情，并非指数本身",
        },
        {
            "code": "CN-SSE",
            "provider_symbol": "MCHI",
            "name_en": "SSE Composite",
            "name_zh": "上证综合指数",
            "country_iso2": "CN",
            "exchange": "Shanghai Stock Exchange",
            "currency": "CNY",
            "official_url": "https://english.sse.com.cn/markets/indices/overview/",
            "quote_proxy_en": "MCHI broad-China ETF proxy; not the SSE index",
            "quote_proxy_zh": "使用 MCHI 中国股票 ETF 代理，并非上证指数本身",
        },
        {
            "code": "HK-HSI",
            "provider_symbol": "EWH",
            "name_en": "Hang Seng Index",
            "name_zh": "恒生指数",
            "country_iso2": "HK",
            "exchange": "Hong Kong Exchanges",
            "currency": "HKD",
            "official_url": "https://www.hsi.com.hk/eng/indexes/all-indexes/hsi",
            "quote_proxy_en": "EWH ETF proxy; not the index itself",
            "quote_proxy_zh": "使用 EWH ETF 代理行情，并非指数本身",
        },
        {
            "code": "KR-KS11",
            "provider_symbol": "EWY",
            "name_en": "KOSPI",
            "name_zh": "韩国综合股价指数",
            "country_iso2": "KR",
            "exchange": "Korea Exchange",
            "currency": "KRW",
            "official_url": "https://global.krx.co.kr/",
            "quote_proxy_en": "EWY ETF proxy; not the index itself",
            "quote_proxy_zh": "使用 EWY ETF 代理行情，并非指数本身",
        },
        {
            "code": "IN-SENSEX",
            "provider_symbol": "INDA",
            "name_en": "BSE Sensex",
            "name_zh": "印度孟买 SENSEX 指数",
            "country_iso2": "IN",
            "exchange": "BSE",
            "currency": "INR",
            "official_url": "https://www.bseindices.com/",
            "quote_proxy_en": "INDA ETF proxy; not the index itself",
            "quote_proxy_zh": "使用 INDA ETF 代理行情，并非指数本身",
        },
        {
            "code": "BR-IBOV",
            "provider_symbol": "EWZ",
            "name_en": "Ibovespa",
            "name_zh": "巴西 Ibovespa 指数",
            "country_iso2": "BR",
            "exchange": "B3",
            "currency": "BRL",
            "official_url": "https://www.b3.com.br/en_us/market-data-and-indices/indices/",
            "quote_proxy_en": "EWZ ETF proxy; not the index itself",
            "quote_proxy_zh": "使用 EWZ ETF 代理行情，并非指数本身",
        },
        {
            "code": "AU-ASX200",
            "provider_symbol": "EWA",
            "name_en": "S&P/ASX 200",
            "name_zh": "标普/澳证 200 指数",
            "country_iso2": "AU",
            "exchange": "Australian Securities Exchange",
            "currency": "AUD",
            "official_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-asx-200/",
            "quote_proxy_en": "EWA ETF proxy; not the index itself",
            "quote_proxy_zh": "使用 EWA ETF 代理行情，并非指数本身",
        },
        {
            "code": "ZA-JTOPI",
            "provider_symbol": "EZA",
            "name_en": "FTSE/JSE All Share",
            "name_zh": "富时/JSE 全股指数",
            "country_iso2": "ZA",
            "exchange": "Johannesburg Stock Exchange",
            "currency": "ZAR",
            "official_url": "https://www.jse.co.za/services/market-data/indices",
            "quote_proxy_en": "EZA ETF proxy; not the index itself",
            "quote_proxy_zh": "使用 EZA ETF 代理行情，并非指数本身",
        },
    ]
)


class TwelveDataPoint(BaseModel):
    """One validated daily price bar."""

    model_config = ConfigDict(extra="ignore")

    datetime: date
    close: float


class TwelveDataPayload(BaseModel):
    """Validated successful response from the time-series endpoint."""

    model_config = ConfigDict(extra="ignore")

    values: list[TwelveDataPoint]
    status: str


class MarketProviderError(RuntimeError):
    """Raised for a credential or provider payload failure."""


_CACHE: dict[str, tuple[datetime, list[TwelveDataPoint]]] = {}
_CACHE_TTL = timedelta(minutes=15)


async def list_market_indices(
    settings: Settings,
    *,
    country_iso2: str | None = None,
) -> MarketIndexResponse:
    """Return index definitions and quote data when a provider key is configured."""
    definitions = [
        row
        for row in MARKET_INDICES
        if country_iso2 is None or row.country_iso2 == country_iso2.upper()
    ]
    api_key = (
        settings.twelve_data_api_key.get_secret_value()
        if settings.twelve_data_api_key
        else None
    )
    if not api_key:
        return _response(
            definitions,
            {},
            quote_status="credential_required",
            fetched_at=None,
        )

    fetched_at = datetime.now(UTC)
    quotes: dict[str, list[TwelveDataPoint]] = {}
    failed_count = 0
    async with httpx.AsyncClient(
        timeout=settings.market_request_timeout_seconds,
    ) as client:
        for definition in definitions:
            try:
                quotes[definition.code] = await _fetch_points(
                    client,
                    definition=definition,
                    api_key=api_key,
                )
            except (httpx.HTTPError, ValueError, MarketProviderError):
                failed_count += 1
    quote_status: Literal["ready", "partial", "provider_error"]
    if failed_count == 0:
        quote_status = "ready"
    elif quotes:
        quote_status = "partial"
    else:
        quote_status = "provider_error"
    return _response(
        definitions,
        quotes,
        quote_status=quote_status,
        fetched_at=fetched_at,
    )


async def _fetch_points(
    client: httpx.AsyncClient,
    *,
    definition: MarketIndexDefinition,
    api_key: str,
) -> list[TwelveDataPoint]:
    cached = _CACHE.get(definition.code)
    now = datetime.now(UTC)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]
    response = await client.get(
        "https://api.twelvedata.com/time_series",
        params={
            "symbol": definition.provider_symbol,
            "interval": "1day",
            "outputsize": "2",
            "apikey": api_key,
        },
    )
    response.raise_for_status()
    raw: Any = response.json()
    if not isinstance(raw, dict) or raw.get("status") == "error":
        raise MarketProviderError(str(raw.get("message", "invalid response")))
    payload = TwelveDataPayload.model_validate(raw)
    points = sorted(payload.values, key=lambda point: point.datetime, reverse=True)
    if not points:
        raise MarketProviderError("empty market series")
    _CACHE[definition.code] = (now, points)
    return points


def _response(
    definitions: list[MarketIndexDefinition],
    quotes: dict[str, list[TwelveDataPoint]],
    *,
    quote_status: Literal[
        "ready",
        "partial",
        "credential_required",
        "provider_error",
    ],
    fetched_at: datetime | None,
) -> MarketIndexResponse:
    rows: list[MarketIndexView] = []
    for definition in definitions:
        points = quotes.get(definition.code, [])
        latest = points[0] if points else None
        previous = points[1] if len(points) > 1 else None
        change_percent = None
        if latest and previous and previous.close:
            change_percent = ((latest.close - previous.close) / previous.close) * 100
        rows.append(
            MarketIndexView(
                **definition.model_dump(),
                observed_on=latest.datetime if latest else None,
                close=latest.close if latest else None,
                change_percent=change_percent,
            )
        )
    return MarketIndexResponse(
        provider=PROVIDER_NAME,
        provider_url=PROVIDER_URL,
        quote_status=quote_status,
        delay_notice_en=(
            "Quote freshness depends on the provider plan and exchange licensing."
        ),
        delay_notice_zh="行情时效取决于数据套餐及交易所授权。",
        fetched_at=fetched_at,
        indices=rows,
    )
