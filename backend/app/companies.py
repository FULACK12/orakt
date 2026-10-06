"""SEC fundamentals and market-price history for reviewed US large caps."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.models import (
    CompanyFiling,
    CompanyFinancialFact,
    CompanyProfile,
    CompanySyncState,
    MarketDailyBar,
    MarketObservation,
    MarketSeries,
)
from app.twelve_data_client import fetch_twelve_daily_values, get_twelve_earliest_date

SEC_BASE_URL = "https://data.sec.gov"
COMPANY_CATALOG = (
    ("AAPL", "0000320193", "Apple Inc.", "Technology", "Consumer electronics"),
    ("MSFT", "0000789019", "Microsoft Corp.", "Technology", "Software and cloud"),
    ("NVDA", "0001045810", "NVIDIA Corp.", "Technology", "Semiconductors"),
    ("AMZN", "0001018724", "Amazon.com Inc.", "Consumer", "E-commerce and cloud"),
    ("GOOGL", "0001652044", "Alphabet Inc.", "Communication", "Internet services"),
    ("META", "0001326801", "Meta Platforms Inc.", "Communication", "Digital platforms"),
    ("BRK.B", "0001067983", "Berkshire Hathaway Inc.", "Financials", "Conglomerate"),
    ("TSLA", "0001318605", "Tesla Inc.", "Consumer", "Automobiles and energy"),
    ("AVGO", "0001730168", "Broadcom Inc.", "Technology", "Semiconductors"),
    ("JPM", "0000019617", "JPMorgan Chase & Co.", "Financials", "Banking"),
    ("WMT", "0000104169", "Walmart Inc.", "Consumer staples", "Retail"),
    ("LLY", "0000059478", "Eli Lilly and Co.", "Health care", "Pharmaceuticals"),
    ("V", "0001403161", "Visa Inc.", "Financials", "Payment networks"),
    ("MA", "0001141391", "Mastercard Inc.", "Financials", "Payment networks"),
    ("XOM", "0000034088", "Exxon Mobil Corp.", "Energy", "Integrated energy"),
    ("JNJ", "0000200406", "Johnson & Johnson", "Health care", "Pharmaceuticals"),
    ("ORCL", "0001341439", "Oracle Corp.", "Technology", "Enterprise software"),
    ("NFLX", "0001065280", "Netflix Inc.", "Communication", "Streaming media"),
    ("COST", "0000909832", "Costco Wholesale Corp.", "Consumer staples", "Retail"),
    ("HD", "0000354950", "Home Depot Inc.", "Consumer", "Home improvement retail"),
    ("MU", "0000723125", "Micron Technology Inc.", "Technology", "Memory semiconductors"),
    ("AMD", "0000002488", "Advanced Micro Devices Inc.", "Technology", "Semiconductors"),
    ("AMAT", "0000006951", "Applied Materials Inc.", "Technology", "Semiconductor equipment"),
    ("CRM", "0001108524", "Salesforce Inc.", "Technology", "Enterprise software"),
    ("BAC", "0000070858", "Bank of America Corp.", "Financials", "Banking"),
    ("KO", "0000021344", "Coca-Cola Co.", "Consumer staples", "Beverages"),
    ("PEP", "0000077476", "PepsiCo Inc.", "Consumer staples", "Food and beverages"),
    ("PG", "0000080424", "Procter & Gamble Co.", "Consumer staples", "Household products"),
    ("MCD", "0000063908", "McDonald's Corp.", "Consumer", "Restaurants"),
    ("DIS", "0001744489", "Walt Disney Co.", "Communication", "Media and entertainment"),
    ("ABBV", "0001551152", "AbbVie Inc.", "Health care", "Pharmaceuticals"),
    ("MRK", "0000310158", "Merck & Co. Inc.", "Health care", "Pharmaceuticals"),
    ("UNH", "0000731766", "UnitedHealth Group Inc.", "Health care", "Managed care"),
    ("CVX", "0000093410", "Chevron Corp.", "Energy", "Integrated energy"),
    ("CAT", "0000018230", "Caterpillar Inc.", "Industrials", "Machinery"),
    ("GE", "0000040545", "GE Aerospace", "Industrials", "Aerospace"),
    ("HON", "0000773840", "Honeywell International Inc.", "Industrials", "Industrial systems"),
    ("RTX", "0000101829", "RTX Corp.", "Industrials", "Aerospace and defense"),
    ("LIN", "0001707925", "Linde plc", "Materials", "Industrial gases"),
    ("NEE", "0000753308", "NextEra Energy Inc.", "Utilities", "Electric utilities"),
    ("PLD", "0001045609", "Prologis Inc.", "Real estate", "Industrial REIT"),
    # Reviewed semiconductor, component and manufacturing leaders already linked
    # by the supplier graph.  Promote them into the primary company universe so
    # SEC filings, prices, ownership and reports use normal sector comparisons.
    ("ADI", "0000006281", "Analog Devices Inc.", "Technology", "Semiconductors"),
    (
        "AMKR",
        "0001047127",
        "Amkor Technology Inc.",
        "Technology",
        "Semiconductor packaging and test",
    ),
    ("ASML", "0000937966", "ASML Holding N.V.", "Technology", "Semiconductor equipment"),
    (
        "ASX",
        "0001122411",
        "ASE Technology Holding Co.",
        "Technology",
        "Semiconductor packaging and test",
    ),
    ("CRUS", "0000772406", "Cirrus Logic Inc.", "Technology", "Audio semiconductors"),
    ("GFS", "0001709048", "GlobalFoundries Inc.", "Technology", "Semiconductor foundry"),
    ("GLW", "0000024741", "Corning Inc.", "Technology", "Electronic materials and components"),
    ("INTC", "0000050863", "Intel Corp.", "Technology", "Semiconductors"),
    ("JBL", "0000898293", "Jabil Inc.", "Technology", "Electronics manufacturing services"),
    ("LITE", "0001633978", "Lumentum Holdings Inc.", "Technology", "Optical components"),
    ("MCHP", "0000827054", "Microchip Technology Inc.", "Technology", "Semiconductors"),
    ("NXPI", "0001413447", "NXP Semiconductors N.V.", "Technology", "Semiconductors"),
    ("ON", "0001097864", "ON Semiconductor Corp.", "Technology", "Semiconductors"),
    ("QCOM", "0000804328", "Qualcomm Inc.", "Technology", "Semiconductors"),
    ("STM", "0000932787", "STMicroelectronics N.V.", "Technology", "Semiconductors"),
    ("SWKS", "0000004127", "Skyworks Solutions Inc.", "Technology", "Semiconductors"),
    ("SYNA", "0000817720", "Synaptics Inc.", "Technology", "Semiconductors"),
    (
        "TSM",
        "0001046179",
        "Taiwan Semiconductor Manufacturing Co.",
        "Technology",
        "Semiconductor foundry",
    ),
    ("TXN", "0000097476", "Texas Instruments Inc.", "Technology", "Semiconductors"),
    ("UMC", "0001033767", "United Microelectronics Corp.", "Technology", "Semiconductor foundry"),
    ("VIAV", "0000912093", "Viavi Solutions Inc.", "Technology", "Optical and network test"),
    ("WDC", "0000106040", "Western Digital Corp.", "Technology", "Data storage"),
    # Additional cross-sector US leaders, with identities resolved against the
    # SEC's official company_tickers.json file on 2026-09-08.
    ("ADBE", "0000796343", "Adobe Inc.", "Technology", "Application software"),
    ("NOW", "0001373715", "ServiceNow Inc.", "Technology", "Enterprise software"),
    (
        "IBM",
        "0000051143",
        "International Business Machines Corp.",
        "Technology",
        "IT services and software",
    ),
    ("TMUS", "0001283699", "T-Mobile US Inc.", "Communication", "Wireless telecommunications"),
    ("VZ", "0000732712", "Verizon Communications Inc.", "Communication", "Telecommunications"),
    ("T", "0000732717", "AT&T Inc.", "Communication", "Telecommunications"),
    ("CMCSA", "0001166691", "Comcast Corp.", "Communication", "Media and telecommunications"),
    ("NKE", "0000320187", "Nike Inc.", "Consumer", "Apparel and footwear"),
    (
        "LULU",
        "0001397187",
        "lululemon athletica inc.",
        "Consumer",
        "Athletic apparel and footwear",
    ),
    ("LOW", "0000060667", "Lowe's Companies Inc.", "Consumer", "Home improvement retail"),
    ("BKNG", "0001075531", "Booking Holdings Inc.", "Consumer", "Online travel"),
    ("SBUX", "0000829224", "Starbucks Corp.", "Consumer", "Restaurants"),
    ("PM", "0001413329", "Philip Morris International Inc.", "Consumer staples", "Tobacco"),
    ("MDLZ", "0001103982", "Mondelez International Inc.", "Consumer staples", "Packaged food"),
    (
        "CL",
        "0000021665",
        "Colgate-Palmolive Co.",
        "Consumer staples",
        "Household and personal products",
    ),
    ("TMO", "0000097745", "Thermo Fisher Scientific Inc.", "Health care", "Life-science tools"),
    ("ABT", "0000001800", "Abbott Laboratories", "Health care", "Medical devices and diagnostics"),
    ("PFE", "0000078003", "Pfizer Inc.", "Health care", "Pharmaceuticals"),
    ("AMGN", "0000318154", "Amgen Inc.", "Health care", "Biotechnology"),
    ("GILD", "0000882095", "Gilead Sciences Inc.", "Health care", "Biotechnology"),
    ("ISRG", "0001035267", "Intuitive Surgical Inc.", "Health care", "Medical devices"),
    ("GS", "0000886982", "Goldman Sachs Group Inc.", "Financials", "Investment banking"),
    ("MS", "0000895421", "Morgan Stanley", "Financials", "Investment banking"),
    ("WFC", "0000072971", "Wells Fargo & Co.", "Financials", "Banking"),
    ("BLK", "0002012383", "BlackRock Inc.", "Financials", "Asset management"),
    ("SPGI", "0000064040", "S&P Global Inc.", "Financials", "Financial data and ratings"),
    ("AXP", "0000004962", "American Express Co.", "Financials", "Consumer finance"),
    ("BA", "0000012927", "Boeing Co.", "Industrials", "Aerospace"),
    ("DE", "0000315189", "Deere & Co.", "Industrials", "Agricultural machinery"),
    ("UPS", "0001090727", "United Parcel Service Inc.", "Industrials", "Air freight and logistics"),
    ("UNP", "0000100885", "Union Pacific Corp.", "Industrials", "Rail transportation"),
    ("LMT", "0000936468", "Lockheed Martin Corp.", "Industrials", "Aerospace and defense"),
    ("COP", "0001163165", "ConocoPhillips", "Energy", "Oil and gas exploration"),
    ("SLB", "0000087347", "SLB Ltd.", "Energy", "Oilfield services"),
    ("EOG", "0000821189", "EOG Resources Inc.", "Energy", "Oil and gas exploration"),
    ("SHW", "0000089800", "Sherwin-Williams Co.", "Materials", "Specialty chemicals"),
    ("APD", "0000002969", "Air Products and Chemicals Inc.", "Materials", "Industrial gases"),
    ("FCX", "0000831259", "Freeport-McMoRan Inc.", "Materials", "Copper mining"),
    ("NEM", "0001164727", "Newmont Corp.", "Materials", "Gold mining"),
    ("SO", "0000092122", "Southern Co.", "Utilities", "Electric utilities"),
    ("DUK", "0001326160", "Duke Energy Corp.", "Utilities", "Electric utilities"),
    ("AEP", "0000004904", "American Electric Power Co.", "Utilities", "Electric utilities"),
    ("AMT", "0001053507", "American Tower Corp.", "Real estate", "Communications REIT"),
    ("EQIX", "0001101239", "Equinix Inc.", "Real estate", "Data-center REIT"),
    ("WELL", "0000766704", "Welltower Inc.", "Real estate", "Health-care REIT"),
)
SEC_CONCEPTS = {
    "Assets",
    "CashAndCashEquivalentsAtCarryingValue",
    "CommonStockSharesOutstanding",
    "EarningsPerShareDiluted",
    "GrossProfit",
    "InventoryNet",
    "Liabilities",
    "LongTermDebtCurrent",
    "LongTermDebtNoncurrent",
    "NetCashProvidedByUsedInOperatingActivities",
    "NetIncomeLoss",
    "OperatingIncomeLoss",
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "ResearchAndDevelopmentExpense",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "ShareBasedCompensation",
    "StockholdersEquity",
    # Foreign private issuers commonly expose the same core statements under
    # the SEC's ifrs-full taxonomy rather than us-gaap.  Keep the original
    # taxonomy and concept names so downstream research cannot silently mix
    # accounting definitions.
    "AssetsCurrent",
    "BasicEarningsLossPerShare",
    "CashAndCashEquivalents",
    "CashFlowsFromUsedInOperatingActivities",
    "CostOfSales",
    "CurrentBorrowings",
    "DilutedEarningsLossPerShare",
    "Equity",
    "EquityAttributableToOwnersOfParent",
    "FinanceCosts",
    "IncomeTaxExpenseContinuingOperations",
    "Inventories",
    "LiabilitiesCurrent",
    "LongtermBorrowings",
    "ProfitLoss",
    "ProfitLossFromOperatingActivities",
    "PropertyPlantAndEquipment",
    "PurchaseOfPropertyPlantAndEquipment",
    "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
    "Revenue",
}
SEC_FACT_FORMS = {
    "10-K",
    "10-K/A",
    "10-Q",
    "10-Q/A",
    "8-K",
    "8-K/A",
    "20-F",
    "20-F/A",
    "6-K",
    "6-K/A",
}
SEC_FILING_FORMS = SEC_FACT_FORMS | {
    "3",
    "3/A",
    "4",
    "4/A",
    "5",
    "5/A",
    "DEF 14A",
    "DEFA14A",
    "S-3",
    "S-3ASR",
}
COMPANY_FACT_KEY_FIELDS = (
    "ticker",
    "taxonomy",
    "concept",
    "unit",
    "period_end",
    "filed_at",
    "accession_number",
)


class CompanySyncResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    companies_synced: int = Field(ge=0)
    filings_upserted: int = Field(ge=0)
    facts_upserted: int = Field(ge=0)
    prices_upserted: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)


def seed_company_catalog(session: Session) -> None:
    """Upsert the reviewed company universe before provider synchronization."""
    rows = [
        {
            "ticker": ticker,
            "cik": cik,
            "name": name,
            "sector": sector,
            "industry": industry,
            "source_url": f"https://www.sec.gov/edgar/browse/?CIK={int(cik)}",
        }
        for ticker, cik, name, sector, industry in COMPANY_CATALOG
    ]
    insert = _dialect_insert(session, CompanyProfile)
    statement = insert.values(rows)
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[CompanyProfile.ticker],
            set_={
                "cik": statement.excluded.cik,
                "name": statement.excluded.name,
                "sector": statement.excluded.sector,
                "industry": statement.excluded.industry,
                "source_url": statement.excluded.source_url,
            },
        )
    )
    session.flush()


async def sync_sec_company_history(
    session: Session,
    *,
    client: httpx.AsyncClient,
    request_interval_seconds: float = 0.25,
    commit_each_company: bool = False,
    tickers: set[str] | None = None,
) -> CompanySyncResult:
    """Fetch public submissions and standardized XBRL facts from data.sec.gov."""
    seed_company_catalog(session)
    errors: list[str] = []
    filings_total = 0
    facts_total = 0
    companies_synced = 0
    selected_tickers = {ticker.strip().upper() for ticker in (tickers or set()) if ticker.strip()}
    profiles = list(session.scalars(select(CompanyProfile).order_by(CompanyProfile.ticker)))
    if selected_tickers:
        profiles = [profile for profile in profiles if profile.ticker in selected_tickers]
    for index, profile in enumerate(profiles):
        if index and request_interval_seconds:
            await asyncio.sleep(request_interval_seconds)
        state = _sync_state(session, profile.ticker)
        state.last_started_at = datetime.now(UTC)
        try:
            submissions_response, facts_response = await asyncio.gather(
                client.get(f"/submissions/CIK{profile.cik}.json"),
                client.get(f"/api/xbrl/companyfacts/CIK{profile.cik}.json"),
            )
            submissions_response.raise_for_status()
            facts_response.raise_for_status()
            filing_rows = _submission_rows(
                profile,
                submissions_response.json(),
            )
            for historical_file in _historical_submission_files(submissions_response.json()):
                await asyncio.sleep(max(request_interval_seconds / 2, 0.12))
                historical_response = await client.get(f"/submissions/{historical_file}")
                historical_response.raise_for_status()
                filing_rows.extend(
                    _submission_rows_from_columns(
                        profile,
                        historical_response.json(),
                    )
                )
            fact_rows = _company_fact_rows(profile, facts_response.json())
            _upsert_filings(session, filing_rows)
            _upsert_facts(session, fact_rows)
            state.filings_upserted = len(filing_rows)
            state.facts_upserted = len(fact_rows)
            state.last_success_at = datetime.now(UTC)
            state.last_error = None
            filings_total += len(filing_rows)
            facts_total += len(fact_rows)
            companies_synced += 1
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            message = f"{profile.ticker}: {type(exc).__name__}: {str(exc)[:180]}"
            state.last_error = message
            errors.append(message)
        session.flush()
        if commit_each_company:
            session.commit()
    return CompanySyncResult(
        companies_synced=companies_synced,
        filings_upserted=filings_total,
        facts_upserted=facts_total,
        prices_upserted=0,
        errors=errors,
    )


async def sync_company_price_history(
    session: Session,
    *,
    client: httpx.AsyncClient,
    api_key: str,
    history_start: date,
    history_end: date,
    request_interval_seconds: float = 16.0,
    commit_each_company: bool = False,
    tickers: set[str] | None = None,
) -> CompanySyncResult:
    """Retain split-adjusted closes and complete daily OHLCV when provided."""
    seed_company_catalog(session)
    _upsert_price_catalog(session)
    errors: list[str] = []
    prices_total = 0
    companies_synced = 0
    fetched_at = datetime.now(UTC)
    priced_series = set(
        session.scalars(
            select(MarketObservation.series_id)
            .where(MarketObservation.series_id.like("EQ:%"))
            .distinct()
        )
    )
    selected_tickers = {ticker.strip().upper() for ticker in (tickers or set()) if ticker.strip()}
    profiles = list(session.scalars(select(CompanyProfile)))
    if selected_tickers:
        profiles = [profile for profile in profiles if profile.ticker in selected_tickers]
    profiles.sort(
        key=lambda profile: (
            f"EQ:{profile.ticker}" in priced_series,
            profile.ticker,
        )
    )
    for index, profile in enumerate(profiles):
        if index and request_interval_seconds:
            await asyncio.sleep(request_interval_seconds)
        provider_symbol = profile.ticker
        try:
            provider_earliest = await get_twelve_earliest_date(
                client,
                symbol=provider_symbol,
                api_key=api_key,
            )
            if request_interval_seconds:
                await asyncio.sleep(max(request_interval_seconds / 2, 0.0))
            selected_start = max(provider_earliest, history_start)
            local_start, local_end = session.execute(
                select(
                    func.min(MarketDailyBar.observed_on),
                    func.max(MarketDailyBar.observed_on),
                ).where(MarketDailyBar.series_id == f"EQ:{profile.ticker}")
            ).one()
            if local_start is not None and local_end is not None and local_start <= selected_start:
                selected_start = max(
                    selected_start,
                    local_end - timedelta(days=10),
                )
            values = await fetch_twelve_daily_values(
                client,
                symbol=provider_symbol,
                api_key=api_key,
                start_date=selected_start,
                end_date=history_end,
                request_interval_seconds=request_interval_seconds,
            )
            rows = []
            bar_rows = []
            for item in values:
                observed_on = _parse_date(item.get("datetime"))
                close = _parse_float(item.get("close"))
                if observed_on is None or close is None:
                    continue
                rows.append(
                    {
                        "series_id": f"EQ:{profile.ticker}",
                        "observed_on": observed_on,
                        "value": close,
                        "fetched_at": fetched_at,
                    }
                )
                open_price = _parse_float(item.get("open"))
                high_price = _parse_float(item.get("high"))
                low_price = _parse_float(item.get("low"))
                volume = _parse_float(item.get("volume"))
                if (
                    open_price is not None
                    and high_price is not None
                    and low_price is not None
                    and min(open_price, high_price, low_price, close) > 0
                    and high_price >= max(open_price, low_price, close)
                    and low_price <= min(open_price, high_price, close)
                ):
                    bar_rows.append(
                        {
                            "series_id": f"EQ:{profile.ticker}",
                            "observed_on": observed_on,
                            "open_price": open_price,
                            "high_price": high_price,
                            "low_price": low_price,
                            "close_price": close,
                            "volume": volume if volume is not None and volume >= 0 else None,
                            "adjustment": "splits",
                            "source_name": "Twelve Data",
                            "source_url": "https://twelvedata.com/docs",
                            "fetched_at": fetched_at,
                        }
                    )
            upserted = _upsert_prices(session, rows)
            _upsert_daily_bars(session, bar_rows)
            state = _sync_state(session, profile.ticker)
            state.prices_upserted = upserted
            state.last_success_at = datetime.now(UTC)
            state.last_error = None
            prices_total += upserted
            companies_synced += 1
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            message = f"{profile.ticker}: {type(exc).__name__}: {str(exc)[:180]}"
            _sync_state(session, profile.ticker).last_error = message
            errors.append(message)
        session.flush()
        if commit_each_company:
            session.commit()
    return CompanySyncResult(
        companies_synced=companies_synced,
        filings_upserted=0,
        facts_upserted=0,
        prices_upserted=prices_total,
        errors=errors,
    )


def company_coverage(session: Session) -> dict[str, Any]:
    """Return measured SEC and price history for the coverage audit."""
    company_count = int(session.scalar(select(func.count()).select_from(CompanyProfile)) or 0)
    facts, first_fact, last_fact = session.execute(
        select(
            func.count(CompanyFinancialFact.id),
            func.min(CompanyFinancialFact.period_end),
            func.max(CompanyFinancialFact.period_end),
        )
    ).one()
    filings = int(session.scalar(select(func.count()).select_from(CompanyFiling)) or 0)
    price_count, price_start, price_end, priced_companies = session.execute(
        select(
            func.count(MarketObservation.observed_on),
            func.min(MarketObservation.observed_on),
            func.max(MarketObservation.observed_on),
            func.count(func.distinct(MarketObservation.series_id)),
        )
        .select_from(MarketObservation)
        .where(MarketObservation.series_id.like("EQ:%"))
    ).one()
    return {
        "company_count": company_count,
        "expected_company_count": len(COMPANY_CATALOG),
        "filing_count": filings,
        "fact_count": int(facts or 0),
        "fact_start": first_fact,
        "fact_end": last_fact,
        "price_count": int(price_count or 0),
        "price_start": price_start,
        "price_end": price_end,
        "priced_companies": int(priced_companies or 0),
        "last_success_at": session.scalar(select(func.max(CompanySyncState.last_success_at))),
    }


def latest_company_facts(
    session: Session,
    *,
    ticker: str,
    limit: int = 80,
) -> list[CompanyFinancialFact]:
    return list(
        session.scalars(
            select(CompanyFinancialFact)
            .where(CompanyFinancialFact.ticker == ticker.upper())
            .order_by(
                desc(CompanyFinancialFact.period_end),
                desc(CompanyFinancialFact.filed_at),
            )
            .limit(limit)
        )
    )


def _submission_rows(
    profile: CompanyProfile,
    payload: Any,
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise TypeError("SEC submissions payload must be an object")
    recent = payload.get("filings", {}).get("recent", {})
    return _submission_rows_from_columns(profile, recent)


def _submission_rows_from_columns(
    profile: CompanyProfile,
    recent: Any,
) -> list[dict[str, Any]]:
    if not isinstance(recent, dict):
        raise TypeError("SEC recent filings must be an object")
    forms = recent.get("form")
    if not isinstance(forms, list):
        raise TypeError("SEC recent forms must be a list")
    rows = []
    for index, form in enumerate(forms):
        if str(form) not in SEC_FILING_FORMS:
            continue
        accession = str(_at(recent, "accessionNumber", index) or "")
        filed_at = _parse_date(_at(recent, "filingDate", index))
        if not accession or filed_at is None:
            continue
        primary = str(_at(recent, "primaryDocument", index) or "") or None
        compact_accession = accession.replace("-", "")
        rows.append(
            {
                "accession_number": accession,
                "ticker": profile.ticker,
                "form": str(form),
                "filed_at": filed_at,
                "report_date": _parse_date(_at(recent, "reportDate", index)),
                "fiscal_year": None,
                "fiscal_period": None,
                "primary_document": primary,
                "source_url": (
                    f"https://www.sec.gov/Archives/edgar/data/{int(profile.cik)}/"
                    f"{compact_accession}/{primary or ''}"
                ),
            }
        )
    return rows


def _historical_submission_files(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    files = payload.get("filings", {}).get("files", [])
    if not isinstance(files, list):
        return []
    return [
        str(item["name"])
        for item in files
        if isinstance(item, dict)
        and isinstance(item.get("name"), str)
        and str(item["name"]).endswith(".json")
    ]


def _company_fact_rows(
    profile: CompanyProfile,
    payload: Any,
    *,
    retain_period_variants: bool = False,
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise TypeError("SEC company facts payload must be an object")
    facts = payload.get("facts", {})
    if not isinstance(facts, dict):
        raise TypeError("SEC facts must be an object")
    rows: list[dict[str, Any]] = []
    for taxonomy, concepts in facts.items():
        if not isinstance(concepts, dict):
            continue
        for concept, details in concepts.items():
            if concept not in SEC_CONCEPTS or not isinstance(details, dict):
                continue
            units = details.get("units", {})
            if not isinstance(units, dict):
                continue
            for unit, observations in units.items():
                if not isinstance(observations, list):
                    continue
                for item in observations:
                    if not isinstance(item, dict) or item.get("form") not in SEC_FACT_FORMS:
                        continue
                    period_end = _parse_date(item.get("end"))
                    filed_at = _parse_date(item.get("filed"))
                    value = _parse_float(item.get("val"))
                    accession = str(item.get("accn") or "")
                    if period_end is None or filed_at is None or value is None or not accession:
                        continue
                    compact_accession = accession.replace("-", "")
                    rows.append(
                        {
                            "ticker": profile.ticker,
                            "taxonomy": str(taxonomy),
                            "concept": str(concept),
                            "label": str(details.get("label") or concept)[:255],
                            "description": str(details.get("description") or "") or None,
                            "unit": str(unit)[:64],
                            "value": value,
                            "period_start": _parse_date(item.get("start")),
                            "period_end": period_end,
                            "filed_at": filed_at,
                            "form": str(item.get("form")),
                            "fiscal_year": _parse_int(item.get("fy")),
                            "fiscal_period": str(item.get("fp") or "")[:16] or None,
                            "frame": str(item.get("frame") or "")[:32] or None,
                            "accession_number": accession,
                            "source_url": (
                                "https://www.sec.gov/Archives/edgar/data/"
                                f"{int(profile.cik)}/{compact_accession}/"
                            ),
                        }
                    )
    return rows if retain_period_variants else _deduplicate_fact_rows(rows)


def _upsert_filings(session: Session, rows: list[dict[str, Any]]) -> None:
    deduplicated = list({str(row["accession_number"]): row for row in rows}.values())
    # PostgreSQL's extended protocol caps a statement at 65,535 parameters.
    # High-volume issuers can have thousands of retained filings, so batch the
    # insert well below that limit instead of restarting the whole sync loop.
    for start in range(0, len(deduplicated), 3_000):
        batch = deduplicated[start : start + 3_000]
        if not batch:
            continue
        insert = _dialect_insert(session, CompanyFiling)
        statement = insert.values(batch)
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[CompanyFiling.accession_number],
                set_={
                    "form": statement.excluded.form,
                    "filed_at": statement.excluded.filed_at,
                    "report_date": statement.excluded.report_date,
                    "primary_document": statement.excluded.primary_document,
                    "source_url": statement.excluded.source_url,
                },
            )
        )


def _upsert_facts(session: Session, rows: list[dict[str, Any]]) -> None:
    deduplicated = _deduplicate_fact_rows(rows)
    for start in range(0, len(deduplicated), 2_000):
        batch = deduplicated[start : start + 2_000]
        if not batch:
            continue
        insert = _dialect_insert(session, CompanyFinancialFact)
        statement = insert.values(batch)
        conflict_target: dict[str, Any] = (
            {
                "index_elements": [
                    CompanyFinancialFact.ticker,
                    CompanyFinancialFact.taxonomy,
                    CompanyFinancialFact.concept,
                    CompanyFinancialFact.unit,
                    CompanyFinancialFact.period_end,
                    CompanyFinancialFact.filed_at,
                    CompanyFinancialFact.accession_number,
                ]
            }
            if session.get_bind().dialect.name == "sqlite"
            else {"constraint": "uq_company_financial_fact_observation"}
        )
        session.execute(
            statement.on_conflict_do_update(
                **conflict_target,
                set_={
                    "value": statement.excluded.value,
                    "label": statement.excluded.label,
                    "description": statement.excluded.description,
                    "frame": statement.excluded.frame,
                    "source_url": statement.excluded.source_url,
                },
            )
        )


def _deduplicate_fact_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return list(
        {tuple(row[field] for field in COMPANY_FACT_KEY_FIELDS): row for row in rows}.values()
    )


def _upsert_price_catalog(session: Session) -> None:
    rows = [
        {
            "series_id": f"EQ:{ticker}",
            "name": f"{name} split-adjusted close",
            "category": "equity_price",
            "unit": "USD",
            "frequency": "daily",
            "source_name": "Twelve Data",
            "source_url": "https://twelvedata.com/docs",
            "listing_status": "active",
            "sector": sector,
            "region": "united_states",
            "neutralization_group": f"industry:{sector}",
        }
        for ticker, _, name, sector, _ in COMPANY_CATALOG
    ]
    insert = _dialect_insert(session, MarketSeries)
    statement = insert.values(rows)
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[MarketSeries.series_id],
            set_={
                "name": statement.excluded.name,
                "category": statement.excluded.category,
                "unit": statement.excluded.unit,
                "frequency": statement.excluded.frequency,
                "source_name": statement.excluded.source_name,
                "source_url": statement.excluded.source_url,
                "listing_status": statement.excluded.listing_status,
                "sector": statement.excluded.sector,
                "region": statement.excluded.region,
                "neutralization_group": statement.excluded.neutralization_group,
            },
        )
    )


def _upsert_prices(session: Session, rows: list[dict[str, Any]]) -> int:
    deduplicated = list({(row["series_id"], row["observed_on"]): row for row in rows}.values())
    for start in range(0, len(deduplicated), 5_000):
        batch = deduplicated[start : start + 5_000]
        if not batch:
            continue
        insert = _dialect_insert(session, MarketObservation)
        statement = insert.values(batch)
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[
                    MarketObservation.series_id,
                    MarketObservation.observed_on,
                ],
                set_={
                    "value": statement.excluded.value,
                    "fetched_at": statement.excluded.fetched_at,
                },
            )
        )
    return len(deduplicated)


def _upsert_daily_bars(session: Session, rows: list[dict[str, Any]]) -> int:
    """Upsert complete bars without weakening the legacy scalar close series."""
    deduplicated = list({(row["series_id"], row["observed_on"]): row for row in rows}.values())
    for start in range(0, len(deduplicated), 2_000):
        batch = deduplicated[start : start + 2_000]
        if not batch:
            continue
        insert = _dialect_insert(session, MarketDailyBar)
        statement = insert.values(batch)
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[
                    MarketDailyBar.series_id,
                    MarketDailyBar.observed_on,
                ],
                set_={
                    "open_price": statement.excluded.open_price,
                    "high_price": statement.excluded.high_price,
                    "low_price": statement.excluded.low_price,
                    "close_price": statement.excluded.close_price,
                    "volume": statement.excluded.volume,
                    "adjustment": statement.excluded.adjustment,
                    "source_name": statement.excluded.source_name,
                    "source_url": statement.excluded.source_url,
                    "fetched_at": statement.excluded.fetched_at,
                },
            )
        )
    return len(deduplicated)


def _sync_state(session: Session, ticker: str) -> CompanySyncState:
    state = session.get(CompanySyncState, ticker)
    if state is None:
        state = CompanySyncState(
            ticker=ticker,
            facts_upserted=0,
            filings_upserted=0,
            prices_upserted=0,
        )
        session.add(state)
    return state


def _dialect_insert(session: Session, model: type[Any]) -> Any:
    if session.get_bind().dialect.name == "sqlite":
        return sqlite_insert(model)
    return postgresql_insert(model)


def _at(values: dict[str, Any], key: str, index: int) -> Any:
    items = values.get(key)
    if not isinstance(items, list) or index >= len(items):
        return None
    return items[index]


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _parse_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed and abs(parsed) != float("inf") else None


def _parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
