"""Primary-source evidence used to validate market and policy hypotheses."""

# ruff: noqa: RUF001

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from io import BytesIO
from typing import Any
from zipfile import BadZipFile, ZipFile

import httpx

from app.core.config import Settings

TREASURY_FEED_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
)
FED_MONETARY_POLICY_FEED_URL = "https://www.federalreserve.gov/feeds/press_monetary.xml"
FED_POWELL_FEED_URL = "https://www.federalreserve.gov/feeds/s_t_powell.xml"
FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
ATLANTA_FED_MPT_URL = (
    "https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/"
    "cenfis/market-probability-tracker/mpt_histdata.xlsx"
)
ATLANTA_FED_MPT_PAGE_URL = (
    "https://www.atlantafed.org/research-and-data/data/market-probability-tracker"
)

FRED_VALIDATION_SERIES: dict[str, tuple[str, str, str]] = {
    "DFF": ("Effective Federal Funds Rate", "policy_rate", "percent"),
    "EFFR": ("Effective Federal Funds Rate (NY Fed)", "policy_rate", "percent"),
    "DFEDTARU": (
        "Federal Funds Target Range - Upper Limit",
        "policy_target",
        "percent",
    ),
    "DGS2": ("2-Year Treasury Constant Maturity Rate", "treasury_yield", "percent"),
    "DGS10": ("10-Year Treasury Constant Maturity Rate", "treasury_yield", "percent"),
    "SP500": ("S&P 500", "market_index", "index"),
    "NASDAQCOM": ("Nasdaq Composite", "market_index", "index"),
    "CPIAUCSL": ("U.S. Consumer Price Index", "inflation", "index"),
    "PCEPI": ("U.S. Personal Consumption Expenditures Price Index", "inflation", "index"),
    "T10YIE": (
        "10-Year Breakeven Inflation Rate",
        "inflation_expectation",
        "percent",
    ),
    "UNRATE": ("U.S. Unemployment Rate", "labour", "percent"),
    "INDPRO": ("U.S. Industrial Production", "industrial_production", "index"),
    "GDPC1": ("U.S. Real Gross Domestic Product", "real_gdp", "billions_usd"),
    "RSAFS": ("U.S. Advance Retail Sales", "retail_sales", "millions_usd"),
    "DCOILWTICO": ("West Texas Intermediate Crude Oil Price", "commodity_price", "usd"),
    "VIXCLS": ("CBOE Volatility Index", "market_volatility", "index"),
    "DTWEXBGS": (
        "Trade Weighted U.S. Dollar Index",
        "currency_index",
        "index",
    ),
    "BAMLH0A0HYM2": (
        "U.S. High Yield Option-Adjusted Spread",
        "credit_spread",
        "percent",
    ),
    "T10Y2Y": ("10-Year Treasury Minus 2-Year Treasury", "yield_curve", "percent"),
    "USREC": ("NBER Recession Indicator", "business_cycle", "binary"),
    "NFCI": ("Chicago Fed National Financial Conditions Index", "financial_conditions", "index"),
    "PAYEMS": ("U.S. Total Nonfarm Payrolls", "labour", "thousands"),
    "PCEPILFE": ("U.S. Core PCE Price Index", "inflation", "index"),
    "UMCSENT": ("University of Michigan Consumer Sentiment", "sentiment", "index"),
    "HOUST": ("U.S. Housing Starts", "housing", "thousands_annual_rate"),
    "ICSA": ("U.S. Initial Unemployment Claims", "labour", "count"),
    "M2SL": ("U.S. M2 Money Stock", "liquidity", "billions_usd"),
    "SAHMREALTIME": ("Sahm Rule Recession Indicator", "business_cycle", "percentage_points"),
    "PERMIT": ("U.S. New Private Housing Units Authorized", "housing", "thousands"),
    "MORTGAGE30US": ("30-Year Fixed Rate Mortgage Average", "housing_finance", "percent"),
    "BUSINV": ("U.S. Total Business Inventories", "inventory_cycle", "millions_usd"),
    "ISRATIO": ("U.S. Total Business Inventories to Sales Ratio", "inventory_cycle", "ratio"),
    "DGORDER": ("U.S. Manufacturers' New Orders: Durable Goods", "orders", "millions_usd"),
    "GDPPOT": ("U.S. Real Potential Gross Domestic Product", "potential_output", "billions_usd"),
    "NROU": ("U.S. Natural Rate of Unemployment", "labour_equilibrium", "percent"),
    "TDSP": ("Household Debt Service Payments to Disposable Income", "debt_service", "percent"),
    "CFNAI": ("Chicago Fed National Activity Index", "coincident_activity", "index"),
    "TCU": ("U.S. Capacity Utilization: Total Industry", "capacity_utilization", "percent"),
    "PPIACO": ("U.S. Producer Price Index: All Commodities", "producer_inflation", "index"),
}

_TAG_RE = re.compile(r"<[^>]+>")
_OFFICIAL_CACHE: (
    tuple[
        datetime,
        tuple[tuple[int, ...], str, str, bool],
        dict[str, Any],
    ]
    | None
) = None


def official_source_catalog() -> list[dict[str, Any]]:
    """Describe available primary sources without exposing credentials."""
    return [
        {
            "key": "us_treasury",
            "name": "U.S. Treasury Daily Interest Rate XML Feed",
            "credential_required": False,
            "documentation_url": (
                "https://home.treasury.gov/treasury-daily-interest-rate-xml-feed"
            ),
            "categories": ["2-year yield", "10-year yield", "yield curve"],
        },
        {
            "key": "federal_reserve",
            "name": "Federal Reserve Board official feeds",
            "credential_required": False,
            "documentation_url": "https://www.federalreserve.gov/feeds/feeds.htm",
            "categories": [
                "FOMC releases",
                "monetary-policy releases",
                "Powell speeches",
            ],
        },
        {
            "key": "atlanta_fed_mpt",
            "name": "Atlanta Fed Market Probability Tracker",
            "credential_required": False,
            "documentation_url": ATLANTA_FED_MPT_PAGE_URL,
            "categories": [
                "market-implied rate path",
                "cut and hike probabilities",
                "SOFR expectation distribution",
            ],
        },
        {
            "key": "fred",
            "name": "Federal Reserve Economic Data",
            "credential_required": True,
            "documentation_url": (
                "https://fred.stlouisfed.org/docs/api/fred/series_observations.html"
            ),
            "categories": [
                "policy rates",
                "Treasury yields",
                "market indices",
                "inflation",
                "inflation expectations",
                "employment",
                "industrial production",
                "GDP and retail sales",
                "oil, dollar, volatility and credit spreads",
            ],
        },
    ]


def fetch_validation_evidence(
    settings: Settings,
    *,
    occurred_at: list[datetime],
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """Fetch a small, time-bounded evidence panel from official providers."""
    global _OFFICIAL_CACHE
    normalized_times = [_as_utc(value) for value in occurred_at]
    years = tuple(sorted({value.year for value in normalized_times}))
    if not years:
        years = (datetime.now(UTC).year,)
    scope_start = min(normalized_times).date().isoformat() if normalized_times else ""
    scope_end = max(normalized_times).date().isoformat() if normalized_times else ""
    cache_scope = (
        years,
        scope_start,
        scope_end,
        settings.fred_api_key is not None,
    )
    now = datetime.now(UTC)
    if (
        transport is None
        and _OFFICIAL_CACHE is not None
        and _OFFICIAL_CACHE[1] == cache_scope
        and now - _OFFICIAL_CACHE[0] < timedelta(minutes=15)
    ):
        return _OFFICIAL_CACHE[2]

    treasury_yields: list[dict[str, Any]] = []
    federal_reserve_items: list[dict[str, Any]] = []
    market_expectations: list[dict[str, Any]] = []
    fred_observations: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    timeout = settings.official_evidence_timeout_seconds
    with httpx.Client(timeout=timeout, transport=transport) as client:
        for year in years[-2:]:
            try:
                response = client.get(
                    TREASURY_FEED_URL,
                    params={
                        "data": "daily_treasury_yield_curve",
                        "field_tdr_date_value": str(year),
                    },
                )
                response.raise_for_status()
                treasury_yields.extend(parse_treasury_yield_xml(response.content))
            except (httpx.HTTPError, ET.ParseError, TypeError, ValueError) as exc:
                errors.append(
                    {
                        "source": "us_treasury",
                        "error": type(exc).__name__,
                    }
                )
        for feed_key, feed_url in (
            ("fed_monetary_policy", FED_MONETARY_POLICY_FEED_URL),
            ("fed_powell", FED_POWELL_FEED_URL),
        ):
            try:
                response = client.get(feed_url)
                response.raise_for_status()
                federal_reserve_items.extend(
                    parse_federal_reserve_feed(
                        response.content,
                        feed_key=feed_key,
                    )
                )
            except (httpx.HTTPError, ET.ParseError, TypeError, ValueError) as exc:
                errors.append(
                    {
                        "source": feed_key,
                        "error": type(exc).__name__,
                    }
                )
        try:
            response = client.get(ATLANTA_FED_MPT_URL)
            response.raise_for_status()
            market_expectations.extend(
                parse_atlanta_fed_mpt_xlsx(response.content)
            )
        except (
            BadZipFile,
            httpx.HTTPError,
            ET.ParseError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            errors.append(
                {
                    "source": "atlanta_fed_mpt",
                    "error": type(exc).__name__,
                }
            )
        if settings.fred_api_key is not None:
            fred_observations.extend(
                _fetch_fred_observations(
                    client,
                    api_key=settings.fred_api_key.get_secret_value(),
                    occurred_at=normalized_times,
                    errors=errors,
                )
            )

    result = {
        "treasury_yields": _select_nearby(
            treasury_yields,
            occurred_at=normalized_times,
            date_key="observed_on",
            pad_days=7,
            latest_limit=15,
        ),
        "federal_reserve_items": _select_nearby(
            federal_reserve_items,
            occurred_at=normalized_times,
            date_key="published_at",
            pad_days=14,
            latest_limit=20,
        ),
        "market_expectations": _select_nearby(
            market_expectations,
            occurred_at=normalized_times,
            date_key="observed_on",
            pad_days=7,
            latest_limit=48,
        ),
        "fred_observations": fred_observations,
        "source_catalog": official_source_catalog(),
        "fetch_errors": errors,
        "source_health": [
            _source_health(
                key="us_treasury",
                name="U.S. Treasury",
                observation_count=len(treasury_yields),
                error_count=sum(error["source"] == "us_treasury" for error in errors),
                configured=True,
                source_url=("https://home.treasury.gov/treasury-daily-interest-rate-xml-feed"),
            ),
            _source_health(
                key="federal_reserve",
                name="Federal Reserve Board",
                observation_count=len(federal_reserve_items),
                error_count=sum(error["source"].startswith("fed_") for error in errors),
                configured=True,
                source_url="https://www.federalreserve.gov/feeds/feeds.htm",
            ),
            _source_health(
                key="atlanta_fed_mpt",
                name="Atlanta Fed Market Probability Tracker",
                observation_count=len(market_expectations),
                error_count=sum(
                    error["source"] == "atlanta_fed_mpt"
                    for error in errors
                ),
                configured=True,
                source_url=ATLANTA_FED_MPT_PAGE_URL,
            ),
            _source_health(
                key="fred",
                name="Federal Reserve Economic Data",
                observation_count=len(fred_observations),
                error_count=sum(error["source"].startswith("fred:") for error in errors),
                configured=settings.fred_api_key is not None,
                source_url="https://fred.stlouisfed.org/",
            ),
        ],
    }
    if transport is None:
        _OFFICIAL_CACHE = (now, cache_scope, result)
    return result


def parse_atlanta_fed_mpt_xlsx(payload: bytes) -> list[dict[str, Any]]:
    """Parse the Atlanta Fed's public MPT workbook without an Excel dependency."""
    with ZipFile(BytesIO(payload)) as archive:
        shared_strings = _xlsx_shared_strings(archive)
        worksheet = ET.fromstring(_xlsx_data_sheet(archive))
    namespace = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows = worksheet.findall(".//m:sheetData/m:row", namespace)
    if not rows:
        return []
    header = _xlsx_row_values(rows[0], shared_strings)
    columns = {column: value for column, value in header.items()}
    expected = {"date", "reference_start", "target_range", "field", "value"}
    if not expected.issubset(set(columns.values())):
        raise ValueError("Atlanta Fed MPT DATA sheet has unexpected columns")
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows[1:]:
        cells = _xlsx_row_values(row, shared_strings)
        values = {columns[column]: value for column, value in cells.items() if column in columns}
        observed_on = str(values.get("date") or "").strip()
        reference_start = _excel_date(values.get("reference_start"))
        field = str(values.get("field") or "").strip()
        value = _optional_float(values.get("value"))
        if not observed_on or reference_start is None or not field or value is None:
            continue
        key = (observed_on, reference_start.isoformat())
        record = grouped.setdefault(
            key,
            {
                "evidence_id": (
                    f"atlanta-fed-mpt:{observed_on}:{reference_start.isoformat()}"
                ),
                "category": "market_expectation",
                "observed_on": observed_on,
                "reference_start": reference_start.isoformat(),
                "target_range": str(values.get("target_range") or "").strip(),
                "source": "Federal Reserve Bank of Atlanta",
                "source_url": ATLANTA_FED_MPT_PAGE_URL,
                "download_url": ATLANTA_FED_MPT_URL,
                "method": "SOFR options-implied probability distribution",
                "probability_distribution": {},
            },
        )
        field_map = {
            "Rate: 25th percentile": "rate_25th_bps",
            "Rate: mean": "mean_rate_bps",
            "Rate: mode": "mode_rate_bps",
            "Rate: 75th percentile": "rate_75th_bps",
            "Prob: cut": "cut_probability",
            "Prob: hike": "hike_probability",
        }
        key_name = field_map.get(field)
        if key_name is not None:
            record[key_name] = value
        elif field.startswith("Prob: "):
            record["probability_distribution"][field.removeprefix("Prob: ")] = value
    records = [
        record
        for record in grouped.values()
        if record.get("mean_rate_bps") is not None
        or record.get("cut_probability") is not None
        or record.get("hike_probability") is not None
    ]
    records.sort(
        key=lambda item: (
            str(item["observed_on"]),
            str(item["reference_start"]),
        )
    )
    return records


def _xlsx_shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    namespace = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return [
        "".join(text.text or "" for text in item.iterfind(".//m:t", namespace))
        for item in root.findall("m:si", namespace)
    ]


def _xlsx_data_sheet(archive: ZipFile) -> bytes:
    main_namespace = {
        "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    package_namespace = {
        "p": "http://schemas.openxmlformats.org/package/2006/relationships"
    }
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        relation.attrib["Id"]: relation.attrib["Target"]
        for relation in relationships.findall("p:Relationship", package_namespace)
    }
    relationship_key = (
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    )
    for sheet in workbook.findall("m:sheets/m:sheet", main_namespace):
        if sheet.attrib.get("name") != "DATA":
            continue
        target = targets[sheet.attrib[relationship_key]].lstrip("/")
        if not target.startswith("xl/"):
            target = f"xl/{target}"
        return archive.read(target)
    raise KeyError("Atlanta Fed MPT workbook has no DATA sheet")


def _xlsx_row_values(
    row: ET.Element,
    shared_strings: list[str],
) -> dict[str, str]:
    namespace = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    values: dict[str, str] = {}
    for cell in row.findall("m:c", namespace):
        reference = str(cell.attrib.get("r") or "")
        match = re.match(r"([A-Z]+)", reference)
        if match is None:
            continue
        value_node = cell.find("m:v", namespace)
        inline_node = cell.find("m:is/m:t", namespace)
        raw = (
            value_node.text
            if value_node is not None
            else inline_node.text if inline_node is not None else ""
        ) or ""
        if cell.attrib.get("t") == "s" and raw:
            raw = shared_strings[int(raw)]
        values[match.group(1)] = raw
    return values


def _excel_date(value: object) -> date | None:
    number = _optional_float(value)
    if number is None:
        return _date(value)
    return date(1899, 12, 30) + timedelta(days=int(number))


def parse_treasury_yield_xml(payload: bytes | str) -> list[dict[str, Any]]:
    """Parse 2Y and 10Y observations from the Treasury OData Atom feed."""
    root = ET.fromstring(payload)
    observations: list[dict[str, Any]] = []
    for entry in root.iter():
        if _local_name(entry.tag) != "properties":
            continue
        values = {_local_name(child.tag): (child.text or "").strip() for child in list(entry)}
        observed_at = _parse_datetime(values.get("NEW_DATE"))
        if observed_at is None:
            continue
        two_year = _optional_float(values.get("BC_2YEAR"))
        ten_year = _optional_float(values.get("BC_10YEAR"))
        if two_year is None and ten_year is None:
            continue
        observed_on = observed_at.date().isoformat()
        observations.append(
            {
                "evidence_id": f"treasury-yields:{observed_on}",
                "category": "treasury_yield",
                "observed_on": observed_on,
                "two_year": two_year,
                "ten_year": ten_year,
                "unit": "percent",
                "source": "U.S. Department of the Treasury",
                "source_url": (
                    "https://home.treasury.gov/resource-center/"
                    "data-chart-center/interest-rates/"
                    "TextView?type=daily_treasury_yield_curve"
                ),
            }
        )
    observations.sort(key=lambda item: str(item["observed_on"]))
    return observations


def parse_federal_reserve_feed(
    payload: bytes | str,
    *,
    feed_key: str,
) -> list[dict[str, Any]]:
    """Parse official Federal Reserve RSS items into traceable evidence."""
    root = ET.fromstring(payload)
    items: list[dict[str, Any]] = []
    for item in root.iter():
        if _local_name(item.tag) != "item":
            continue
        values: dict[str, str] = {}
        for child in list(item):
            values[_local_name(child.tag)] = (child.text or "").strip()
        title = _clean_html(values.get("title", ""))
        link = values.get("link", "").strip()
        published_at = _parse_datetime(values.get("pubDate"))
        if not title or not link or published_at is None:
            continue
        digest = hashlib.sha256(link.encode("utf-8")).hexdigest()[:16]
        items.append(
            {
                "evidence_id": f"{feed_key}:{digest}",
                "category": "official_policy_communication",
                "title": title,
                "summary": _clean_html(values.get("description", ""))[:1_000],
                "published_at": published_at.isoformat(),
                "source": "Board of Governors of the Federal Reserve System",
                "source_url": link,
                "feed_url": (
                    FED_MONETARY_POLICY_FEED_URL
                    if feed_key == "fed_monetary_policy"
                    else FED_POWELL_FEED_URL
                ),
            }
        )
    items.sort(key=lambda row: str(row["published_at"]), reverse=True)
    return items


def _fetch_fred_observations(
    client: httpx.Client,
    *,
    api_key: str,
    occurred_at: list[datetime],
    errors: list[dict[str, str]],
) -> list[dict[str, Any]]:
    if occurred_at:
        start = min(occurred_at).date() - timedelta(days=14)
        end = max(occurred_at).date() + timedelta(days=14)
    else:
        end = datetime.now(UTC).date()
        start = end - timedelta(days=45)
    observations: list[dict[str, Any]] = []
    for series_id, (label, category, unit) in FRED_VALIDATION_SERIES.items():
        try:
            response = client.get(
                FRED_OBSERVATIONS_URL,
                params={
                    "series_id": series_id,
                    "api_key": api_key,
                    "file_type": "json",
                    "observation_start": start.isoformat(),
                    "observation_end": end.isoformat(),
                    "sort_order": "asc",
                },
            )
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("observations", [])
            if not isinstance(rows, list):
                raise TypeError("FRED observations must be a list")
            for row in _select_fred_rows(rows, occurred_at=occurred_at):
                if not isinstance(row, dict):
                    continue
                value = _optional_float(row.get("value"))
                observed_on = str(row.get("date") or "")
                if value is None or not observed_on:
                    continue
                observations.append(
                    {
                        "evidence_id": f"fred:{series_id}:{observed_on}",
                        "category": category,
                        "series_id": series_id,
                        "label": label,
                        "observed_on": observed_on,
                        "value": value,
                        "unit": unit,
                        "source": "Federal Reserve Bank of St. Louis",
                        "source_url": (f"https://fred.stlouisfed.org/series/{series_id}"),
                    }
                )
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            errors.append(
                {
                    "source": f"fred:{series_id}",
                    "error": type(exc).__name__,
                }
            )
    return observations


def _select_nearby(
    rows: list[dict[str, Any]],
    *,
    occurred_at: list[datetime],
    date_key: str,
    pad_days: int,
    latest_limit: int,
) -> list[dict[str, Any]]:
    if not rows:
        return []
    ordered = sorted(
        rows,
        key=lambda row: _parse_datetime(row.get(date_key)) or datetime.min.replace(tzinfo=UTC),
    )
    if not occurred_at:
        return ordered[-latest_limit:]
    start = min(occurred_at) - timedelta(days=pad_days)
    end = max(occurred_at) + timedelta(days=pad_days)
    selected = []
    for row in ordered:
        observed_at = _parse_datetime(row.get(date_key))
        if observed_at is not None and start <= observed_at <= end:
            selected.append(row)
    return selected[-latest_limit:]


def _select_fred_rows(
    rows: list[Any],
    *,
    occurred_at: list[datetime],
    limit: int = 12,
) -> list[Any]:
    valid = [
        row
        for row in rows
        if isinstance(row, dict)
        and _parse_datetime(row.get("date")) is not None
        and _optional_float(row.get("value")) is not None
    ]
    if not occurred_at:
        return valid[-limit:]
    target_dates = [value.date() for value in occurred_at]
    ranked = sorted(
        valid,
        key=lambda row: _fred_date_distance(row, target_dates),
    )
    selected_ids = {str(row.get("date")) for row in ranked[:limit] if isinstance(row, dict)}
    selected = [
        row for row in valid if isinstance(row, dict) and str(row.get("date")) in selected_ids
    ]
    return selected


def _fred_date_distance(
    row: dict[str, Any],
    target_dates: list[date],
) -> int:
    observed = _date(row.get("date"))
    if observed is None:
        return 10**9
    return min(abs((observed - target).days) for target in target_dates)


def _source_health(
    *,
    key: str,
    name: str,
    observation_count: int,
    error_count: int,
    configured: bool,
    source_url: str,
) -> dict[str, Any]:
    if not configured:
        status = "not_configured"
        message_en = "Credential not configured."
        message_zh = "尚未配置访问凭证。"
    elif observation_count > 0 and error_count == 0:
        status = "ready"
        message_en = "The provider returned usable evidence."
        message_zh = "该来源已返回可用证据。"
    elif observation_count > 0:
        status = "partial"
        message_en = "Some observations were returned, with partial source errors."
        message_zh = "已返回部分观测，但部分请求存在错误。"
    else:
        status = "unavailable"
        message_en = "No usable observation was returned for this time range."
        message_zh = "该时间范围内未返回可用观测。"
    return {
        "key": key,
        "name": name,
        "status": status,
        "observation_count": observation_count,
        "message_en": message_en,
        "message_zh": message_zh,
        "source_url": source_url,
    }


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
    return _as_utc(parsed)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _optional_float(value: object) -> float | None:
    try:
        if value in (None, "", "."):
            return None
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]


def _clean_html(value: str) -> str:
    return " ".join(unescape(_TAG_RE.sub(" ", value)).split())


def _date(value: object) -> date | None:
    parsed = _parse_datetime(value)
    return parsed.date() if parsed is not None else None
