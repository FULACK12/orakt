"""Validated World Bank Indicators API client and idempotent persistence."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    CountryProfile,
    EconomicIndicator,
    EconomicObservation,
    EconomicSyncState,
)

SOURCE_KEY = "world_bank_indicators"
SOURCE_NAME = "World Bank Open Data"
SOURCE_URL = "https://data.worldbank.org/"
API_DOCUMENTATION_URL = (
    "https://datahelpdesk.worldbank.org/knowledgebase/articles/889392"
)
LICENSE_NAME = "Creative Commons Attribution 4.0"
LICENSE_URL = "https://datacatalog.worldbank.org/public-licenses"


class EconomicIndicatorDefinition(BaseModel):
    """Reviewed bilingual metadata for a supported indicator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=64)
    name_en: str
    name_zh: str
    unit: str
    description_en: str
    description_zh: str


ECONOMIC_INDICATORS = TypeAdapter(
    list[EconomicIndicatorDefinition]
).validate_python(
    [
        {
            "code": "FP.CPI.TOTL.ZG",
            "name_en": "Inflation, consumer prices",
            "name_zh": "消费者价格通胀率",
            "unit": "annual %",
            "description_en": "Annual percentage change in the consumer price index.",
            "description_zh": "消费者价格指数的年度百分比变化。",
        },
        {
            "code": "NY.GDP.MKTP.CD",
            "name_en": "GDP",
            "name_zh": "国内生产总值",
            "unit": "current US$",
            "description_en": "Gross domestic product at current United States dollars.",
            "description_zh": "按现价美元计的国内生产总值。",
        },
        {
            "code": "NY.GDP.MKTP.KD.ZG",
            "name_en": "GDP growth",
            "name_zh": "GDP 增长率",
            "unit": "annual %",
            "description_en": "Annual percentage growth rate of real GDP.",
            "description_zh": "实际国内生产总值的年度增长率。",
        },
        {
            "code": "NY.GDP.PCAP.CD",
            "name_en": "GDP per capita",
            "name_zh": "人均 GDP",
            "unit": "current US$",
            "description_en": "Gross domestic product divided by midyear population.",
            "description_zh": "国内生产总值除以年中人口。",
        },
        {
            "code": "SL.UEM.TOTL.ZS",
            "name_en": "Unemployment",
            "name_zh": "失业率",
            "unit": "% of labor force",
            "description_en": "Modeled ILO estimate of unemployment.",
            "description_zh": "国际劳工组织模型估算的失业率。",
        },
        {
            "code": "NE.TRD.GNFS.ZS",
            "name_en": "Trade openness",
            "name_zh": "贸易开放度",
            "unit": "% of GDP",
            "description_en": "Sum of exports and imports of goods and services.",
            "description_zh": "商品与服务进出口总额占 GDP 的比例。",
        },
        {
            "code": "GC.DOD.TOTL.GD.ZS",
            "name_en": "Central government debt",
            "name_zh": "中央政府债务",
            "unit": "% of GDP",
            "description_en": "Total stock of direct government fixed-term obligations.",
            "description_zh": "中央政府直接固定期限债务存量占 GDP 的比例。",
        },
        {
            "code": "BN.CAB.XOKA.GD.ZS",
            "name_en": "Current account balance",
            "name_zh": "经常账户余额",
            "unit": "% of GDP",
            "description_en": "Current account balance as a share of GDP.",
            "description_zh": "经常账户余额占 GDP 的比例。",
        },
        {
            "code": "FR.INR.RINR",
            "name_en": "Real interest rate",
            "name_zh": "实际利率",
            "unit": "%",
            "description_en": "Lending interest rate adjusted for inflation.",
            "description_zh": "经通胀调整后的贷款利率。",
        },
        {
            "code": "SP.POP.TOTL",
            "name_en": "Population",
            "name_zh": "总人口",
            "unit": "people",
            "description_en": "Total population based on the de facto definition.",
            "description_zh": "按常住人口口径统计的总人口。",
        },
        {
            "code": "FI.RES.TOTL.CD",
            "name_en": "Total reserves",
            "name_zh": "外汇及黄金储备",
            "unit": "current US$",
            "description_en": "Monetary authorities' reserves including gold.",
            "description_zh": "货币当局持有的储备资产并含黄金。",
        },
        {
            "code": "PA.NUS.FCRF",
            "name_en": "Official exchange rate",
            "name_zh": "官方汇率",
            "unit": "local currency per US$",
            "description_en": "Annual average official exchange rate.",
            "description_zh": "本币兑美元的年度平均官方汇率。",
        },
        {
            "code": "NV.AGR.TOTL.CD",
            "name_en": "Agriculture value added",
            "name_zh": "农业、林业和渔业增加值",
            "unit": "current US$",
            "description_en": "Agriculture, forestry and fishing value added.",
            "description_zh": "农业、林业和渔业按现价美元计的增加值。",
        },
        {
            "code": "NV.AGR.TOTL.ZS",
            "name_en": "Agriculture share of GDP",
            "name_zh": "农业、林业和渔业占 GDP 比重",
            "unit": "% of GDP",
            "description_en": "Agriculture, forestry and fishing value added as a share of GDP.",
            "description_zh": "农业、林业和渔业增加值占国内生产总值的比重。",
        },
        {
            "code": "NV.IND.TOTL.CD",
            "name_en": "Industry value added",
            "name_zh": "工业增加值",
            "unit": "current US$",
            "description_en": "Industry including construction value added.",
            "description_zh": "包括建筑业在内的工业增加值。",
        },
        {
            "code": "NV.IND.TOTL.ZS",
            "name_en": "Industry share of GDP",
            "name_zh": "工业占 GDP 比重",
            "unit": "% of GDP",
            "description_en": "Industry including construction value added as a share of GDP.",
            "description_zh": "包括建筑业在内的工业增加值占 GDP 的比重。",
        },
        {
            "code": "NV.IND.MANF.CD",
            "name_en": "Manufacturing value added",
            "name_zh": "制造业增加值",
            "unit": "current US$",
            "description_en": "Manufacturing value added at current United States dollars.",
            "description_zh": "按现价美元计的制造业增加值。",
        },
        {
            "code": "AG.PRD.CROP.XD",
            "name_en": "Crop production index",
            "name_zh": "农作物生产指数",
            "unit": "2014-2016 = 100",
            "description_en": "Agricultural crop production relative to the 2014-2016 base.",
            "description_zh": "相对于 2014—2016 基期的农作物产量指数。",
        },
        {
            "code": "AG.PRD.FOOD.XD",
            "name_en": "Food production index",
            "name_zh": "粮食生产指数",
            "unit": "2014-2016 = 100",
            "description_en": "Food crop production available for human consumption.",
            "description_zh": "可供人类食用的粮食作物生产指数。",
        },
        {
            "code": "AG.PRD.LVSK.XD",
            "name_en": "Livestock production index",
            "name_zh": "畜牧业生产指数",
            "unit": "2014-2016 = 100",
            "description_en": "Livestock production relative to the 2014-2016 base.",
            "description_zh": "相对于 2014—2016 基期的畜牧业生产指数。",
        },
        {
            "code": "IS.AIR.PSGR",
            "name_en": "Air transport passengers",
            "name_zh": "航空运输旅客量",
            "unit": "passengers",
            "description_en": "Passengers carried by registered air carriers.",
            "description_zh": "注册航空承运人运输的旅客总量。",
        },
        {
            "code": "IS.AIR.GOOD.MT.K1",
            "name_en": "Air freight",
            "name_zh": "航空货运量",
            "unit": "million ton-km",
            "description_en": (
                "Freight carried on each flight stage measured in metric "
                "ton-kilometres."
            ),
            "description_zh": "按公吨公里计的航空货运量。",
        },
        {
            "code": "IS.AIR.DPRT",
            "name_en": "Registered carrier departures",
            "name_zh": "注册航空承运人起飞架次",
            "unit": "departures",
            "description_en": "Domestic and international takeoffs made by registered carriers.",
            "description_zh": "注册承运人执行的国内及国际起飞架次。",
        },
        {
            "code": "IS.SHP.GOOD.TU",
            "name_en": "Container port traffic",
            "name_zh": "集装箱港口吞吐量",
            "unit": "TEU",
            "description_en": "Twenty-foot equivalent container units handled by ports.",
            "description_zh": "港口装卸的二十英尺标准箱数量。",
        },
        {
            "code": "IS.SHP.GCNW.XQ",
            "name_en": "Liner shipping connectivity",
            "name_zh": "班轮运输连通度指数",
            "unit": "2004 maximum = 100",
            "description_en": "Country connectivity to global liner shipping networks.",
            "description_zh": "国家接入全球班轮运输网络的程度。",
        },
    ]
)


class WorldBankNamedValue(BaseModel):
    """Nested code and display value in World Bank responses."""

    model_config = ConfigDict(extra="ignore")

    id: str
    value: str


class WorldBankPage(BaseModel):
    """Pagination metadata returned as the first array item."""

    model_config = ConfigDict(extra="ignore")

    page: int = Field(ge=1)
    pages: int = Field(ge=0)
    per_page: int = Field(ge=1)
    total: int = Field(ge=0)


class WorldBankCountry(BaseModel):
    """Validated country catalog row."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=3, max_length=3)
    iso2Code: str
    name: str
    region: WorldBankNamedValue
    incomeLevel: WorldBankNamedValue
    capitalCity: str
    longitude: str
    latitude: str


class WorldBankIndicatorRef(BaseModel):
    """Indicator identity nested in an observation."""

    model_config = ConfigDict(extra="ignore")

    id: str
    value: str


class WorldBankObservation(BaseModel):
    """Validated annual observation row."""

    model_config = ConfigDict(extra="ignore")

    indicator: WorldBankIndicatorRef
    country: WorldBankNamedValue
    countryiso3code: str
    date: str
    value: float | None


class EconomicSyncResult(BaseModel):
    """Counts produced by one complete provider synchronization."""

    model_config = ConfigDict(extra="forbid")

    source_key: str
    start_year: int
    end_year: int
    countries_upserted: int = Field(ge=0)
    indicators_upserted: int = Field(ge=0)
    observations_upserted: int = Field(ge=0)
    failed_indicators: dict[str, str] = Field(default_factory=dict)


class WorldBankClient:
    """Small, paginated client with validation at the HTTP boundary."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        base_url: str = "https://api.worldbank.org/v2",
    ) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/")

    async def fetch_countries(self) -> list[WorldBankCountry]:
        """Return the complete World Bank country catalog."""
        payload = await self._get_json(
            "/country",
            params={"format": "json", "per_page": "400"},
        )
        _, rows = _validate_country_page(payload)
        return rows

    async def fetch_indicator(
        self,
        indicator_code: str,
        *,
        start_year: int,
        end_year: int,
    ) -> list[WorldBankObservation]:
        """Return all annual values for one indicator and date range."""
        rows: list[WorldBankObservation] = []
        chunk_start = start_year
        while chunk_start <= end_year:
            chunk_end = min(end_year, chunk_start + 19)
            rows.extend(
                await self._fetch_indicator_span(
                    indicator_code,
                    start_year=chunk_start,
                    end_year=chunk_end,
                )
            )
            chunk_start = chunk_end + 1
        return rows

    async def _fetch_indicator_span(
        self,
        indicator_code: str,
        *,
        start_year: int,
        end_year: int,
    ) -> list[WorldBankObservation]:
        payload = await self._get_json(
            f"/country/all/indicator/{indicator_code}",
            params={
                "format": "json",
                "date": f"{start_year}:{end_year}",
                "per_page": "20000",
                "source": "2",
            },
        )
        page, rows = _validate_observation_page(payload)
        for page_number in range(2, page.pages + 1):
            next_payload = await self._get_json(
                f"/country/all/indicator/{indicator_code}",
                params={
                    "format": "json",
                    "date": f"{start_year}:{end_year}",
                    "per_page": "20000",
                    "source": "2",
                    "page": str(page_number),
                },
            )
            _, next_rows = _validate_observation_page(next_payload)
            rows.extend(next_rows)
        return rows

    async def _get_json(
        self,
        path: str,
        *,
        params: dict[str, str],
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = await self.client.get(
                    f"{self.base_url}{path}",
                    params=params,
                )
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt == 2:
                    break
                await asyncio.sleep(1.5 * (attempt + 1))
        if last_error is None:
            raise RuntimeError("World Bank request failed without an error")
        raise last_error


def _validate_country_page(
    payload: Any,
) -> tuple[WorldBankPage, list[WorldBankCountry]]:
    if not isinstance(payload, list) or len(payload) != 2:
        raise ValueError("World Bank country response must contain metadata and rows")
    page = WorldBankPage.model_validate(payload[0])
    rows = TypeAdapter(list[WorldBankCountry]).validate_python(payload[1] or [])
    return page, rows


def _validate_observation_page(
    payload: Any,
) -> tuple[WorldBankPage, list[WorldBankObservation]]:
    if not isinstance(payload, list) or len(payload) != 2:
        raise ValueError("World Bank observation response must contain metadata and rows")
    page = WorldBankPage.model_validate(payload[0])
    rows = TypeAdapter(list[WorldBankObservation]).validate_python(payload[1] or [])
    return page, rows


async def sync_world_bank(
    session: Session,
    client: WorldBankClient,
    *,
    start_year: int,
    end_year: int,
) -> EconomicSyncResult:
    """Upsert a validated country catalog and selected economic series."""
    if start_year > end_year:
        raise ValueError("start_year must not exceed end_year")

    now = datetime.now(UTC)
    sync_state = session.get(EconomicSyncState, SOURCE_KEY)
    if sync_state is None:
        sync_state = EconomicSyncState(source_key=SOURCE_KEY)
        session.add(sync_state)
    sync_state.last_started_at = now
    sync_state.history_start_year = start_year
    sync_state.history_end_year = end_year

    indicator_rows = _upsert_indicator_catalog(session)
    country_payload = await client.fetch_countries()
    country_rows = _upsert_country_catalog(session, country_payload)
    session.flush()

    valid_iso3 = set(session.scalars(select(CountryProfile.iso3)))
    observation_rows = 0
    failed_indicators: dict[str, str] = {}
    for definition in ECONOMIC_INDICATORS:
        try:
            observations = await client.fetch_indicator(
                definition.code,
                start_year=start_year,
                end_year=end_year,
            )
        except (httpx.HTTPError, ValueError) as exc:
            failed_indicators[definition.code] = str(exc)[:500]
            continue
        observation_rows += _upsert_observations(
            session,
            definition.code,
            observations,
            valid_iso3=valid_iso3,
            fetched_at=now,
            start_year=start_year,
            end_year=end_year,
        )

    if len(failed_indicators) == len(ECONOMIC_INDICATORS):
        raise RuntimeError("every World Bank indicator request failed")
    sync_state.last_success_at = datetime.now(UTC)
    sync_state.rows_upserted = observation_rows
    sync_state.consecutive_failures = 1 if failed_indicators else 0
    sync_state.last_error = (
        f"partial indicator failures: {json.dumps(failed_indicators, sort_keys=True)}"[
            :4_000
        ]
        if failed_indicators
        else None
    )
    session.flush()
    return EconomicSyncResult(
        source_key=SOURCE_KEY,
        start_year=start_year,
        end_year=end_year,
        countries_upserted=country_rows,
        indicators_upserted=indicator_rows,
        observations_upserted=observation_rows,
        failed_indicators=failed_indicators,
    )


def record_sync_failure(
    session: Session,
    *,
    start_year: int,
    end_year: int,
    error: Exception,
) -> None:
    """Persist a bounded provider error after the caller rolls back."""
    sync_state = session.get(EconomicSyncState, SOURCE_KEY)
    if sync_state is None:
        sync_state = EconomicSyncState(source_key=SOURCE_KEY)
        session.add(sync_state)
    sync_state.last_started_at = datetime.now(UTC)
    sync_state.history_start_year = start_year
    sync_state.history_end_year = end_year
    sync_state.consecutive_failures += 1
    sync_state.last_error = str(error)[:4_000]
    session.flush()


def _upsert_indicator_catalog(session: Session) -> int:
    existing = {
        row.code: row
        for row in session.scalars(
            select(EconomicIndicator).where(
                EconomicIndicator.code.in_(
                    definition.code for definition in ECONOMIC_INDICATORS
                )
            )
        )
    }
    for definition in ECONOMIC_INDICATORS:
        row = existing.get(definition.code)
        if row is None:
            row = EconomicIndicator(code=definition.code)
            session.add(row)
        row.name_en = definition.name_en
        row.name_zh = definition.name_zh
        row.unit = definition.unit
        row.description_en = definition.description_en
        row.description_zh = definition.description_zh
        row.frequency = "annual"
        row.source_name = SOURCE_NAME
        row.source_url = SOURCE_URL
        row.license_name = LICENSE_NAME
        row.license_url = LICENSE_URL
        row.enabled = True
    return len(ECONOMIC_INDICATORS)


def _upsert_country_catalog(
    session: Session,
    payload: list[WorldBankCountry],
) -> int:
    countries = [
        country
        for country in payload
        if country.region.value.strip() != "Aggregates"
        and len(country.iso2Code) == 2
        and country.iso2Code.isalpha()
    ]
    existing = {
        row.iso3: row
        for row in session.scalars(
            select(CountryProfile).where(
                CountryProfile.iso3.in_(country.id for country in countries)
            )
        )
    }
    for country in countries:
        row = existing.get(country.id)
        if row is None:
            row = CountryProfile(iso3=country.id)
            session.add(row)
        row.iso2 = country.iso2Code.upper()
        row.name = country.name
        row.region = country.region.value.strip()
        row.income_level = country.incomeLevel.value.strip() or None
        row.capital_city = country.capitalCity.strip() or None
        row.longitude = _optional_coordinate(country.longitude)
        row.latitude = _optional_coordinate(country.latitude)
        row.source_url = f"{SOURCE_URL}country/{country.iso2Code.lower()}"
    return len(countries)


def _optional_coordinate(value: str) -> float | None:
    return float(value) if value.strip() else None


def _upsert_observations(
    session: Session,
    indicator_code: str,
    payload: list[WorldBankObservation],
    *,
    valid_iso3: set[str],
    fetched_at: datetime,
    start_year: int,
    end_year: int,
) -> int:
    existing = {
        (row.country_iso3, row.year): row
        for row in session.scalars(
            select(EconomicObservation).where(
                EconomicObservation.indicator_code == indicator_code,
                EconomicObservation.year.between(start_year, end_year),
            )
        )
    }
    upserted = 0
    for observation in payload:
        if (
            observation.value is None
            or observation.countryiso3code not in valid_iso3
            or not observation.date.isdigit()
        ):
            continue
        year = int(observation.date)
        if year < start_year or year > end_year:
            continue
        key = (observation.countryiso3code, year)
        row = existing.get(key)
        if row is None:
            row = EconomicObservation(
                country_iso3=observation.countryiso3code,
                indicator_code=indicator_code,
                year=year,
            )
            session.add(row)
            existing[key] = row
        row.value = observation.value
        row.fetched_at = fetched_at
        upserted += 1
    return upserted
