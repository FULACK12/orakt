"""Cold-store official SEC Form 13F archives and extract reviewed issuers."""

from __future__ import annotations

import csv
import html
import io
import os
import re
import shutil
from calendar import monthrange
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from zipfile import ZipFile

import httpx
from sqlalchemy import desc, func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.companies import seed_company_catalog
from app.db.models import (
    CompanyInstitutionalHolding,
    InstitutionalArchiveState,
)

SEC_13F_DATA_PAGE = "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets"
SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"
SEC_13F_ARCHIVE_BASE = "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/"
# SEC Form 13F data sets do not include exchange tickers. Keep the translation
# explicit and reviewed instead of guessing from issuer names (which creates
# collisions such as Linde/Lineage). Multiple CUSIPs are retained only where
# the same reviewed company changed security identifiers.
REVIEWED_CUSIPS = {
    "037833100": "AAPL",
    "00287Y109": "ABBV",
    "038222105": "AMAT",
    "007903107": "AMD",
    "023135106": "AMZN",
    "11135F101": "AVGO",
    "060505104": "BAC",
    "084670702": "BRK.B",
    "149123101": "CAT",
    "22160K105": "COST",
    "79466L302": "CRM",
    "166764100": "CVX",
    "254687106": "DIS",
    "369604103": "GE",
    "369604301": "GE",
    "02079K305": "GOOGL",
    "437076102": "HD",
    "438516106": "HON",
    "478160104": "JNJ",
    "46625H100": "JPM",
    "191216100": "KO",
    "532457108": "LLY",
    "G5494J103": "LIN",
    "G54950103": "LIN",
    "57636Q104": "MA",
    "580135101": "MCD",
    "30303M102": "META",
    "58933Y105": "MRK",
    "594918104": "MSFT",
    "595112103": "MU",
    "65339F101": "NEE",
    "64110L106": "NFLX",
    "67066G104": "NVDA",
    "68389X105": "ORCL",
    "713448108": "PEP",
    "742718109": "PG",
    "74340W103": "PLD",
    "75513E101": "RTX",
    "88160R101": "TSLA",
    "91324P102": "UNH",
    "92826C839": "V",
    "931142103": "WMT",
    "30231G102": "XOM",
    "032654105": "ADI",
    "031652100": "AMKR",
    "N07059210": "ASML",
    "Y0255J100": "ASX",
    "172755100": "CRUS",
    "G39387108": "GFS",
    "219350105": "GLW",
    "458140100": "INTC",
    "466313103": "JBL",
    "55024U109": "LITE",
    "595017104": "MCHP",
    "N6596X109": "NXPI",
    "682189105": "ON",
    "747525103": "QCOM",
    "861012102": "STM",
    "83088M102": "SWKS",
    "87157D109": "SYNA",
    "874039100": "TSM",
    "882508104": "TXN",
    "910873405": "UMC",
    "925550105": "VIAV",
    "958102105": "WDC",
    "00724F101": "ADBE",
    "81762P102": "NOW",
    "459200101": "IBM",
    "872590104": "TMUS",
    "92343V104": "VZ",
    "00206R102": "T",
    "20030N101": "CMCSA",
    "654106103": "NKE",
    "550021109": "LULU",
    "548661107": "LOW",
    "09857L108": "BKNG",
    "855244109": "SBUX",
    "718172109": "PM",
    "609207105": "MDLZ",
    "194162103": "CL",
    "883556102": "TMO",
    "002824100": "ABT",
    "717081103": "PFE",
    "031162100": "AMGN",
    "375558103": "GILD",
    "46120E602": "ISRG",
    "38141G104": "GS",
    "617446448": "MS",
    "949746101": "WFC",
    "09290D101": "BLK",
    "78409V104": "SPGI",
    "025816109": "AXP",
    "097023105": "BA",
    "244199105": "DE",
    "911312106": "UPS",
    "907818108": "UNP",
    "539830109": "LMT",
    "20825C104": "COP",
    "806857108": "SLB",
    "26875P101": "EOG",
    "824348106": "SHW",
    "009158106": "APD",
    "35671D857": "FCX",
    "651639106": "NEM",
    "842587107": "SO",
    "26441C204": "DUK",
    "025537101": "AEP",
    "03027X100": "AMT",
    "29444U700": "EQIX",
    "95040Q104": "WELL",
}
REVIEWED_UNIVERSE_VERSION = "us_sector_leaders_108_v5"


async def discover_sec_13f_archives(client: httpx.AsyncClient) -> list[str]:
    """Read the official download page so new quarterly archives need no code change."""
    try:
        response = await client.get(SEC_13F_DATA_PAGE, timeout=20)
        response.raise_for_status()
    except httpx.HTTPError:
        # SEC sometimes blocks the Drupal page while its public data ZIP URLs
        # remain available. Keep a deterministic official-name fallback so a
        # transient 403 cannot stop a restart-safe historical backfill.
        return _known_sec_13f_archive_urls()
    hrefs = re.findall(
        r'href=["\']([^"\']+\.zip(?:\?[^"\']*)?)["\']',
        html.unescape(response.text),
        flags=re.IGNORECASE,
    )
    result: list[str] = []
    seen: set[str] = set()
    for href in hrefs:
        url = urljoin(SEC_13F_DATA_PAGE, href)
        if url in seen:
            continue
        seen.add(url)
        result.append(url)
    return result or _known_sec_13f_archive_urls()


def _known_sec_13f_archive_urls(*, as_of: date | None = None) -> list[str]:
    """Generate the SEC's documented archive names through the latest window."""
    boundary = as_of or datetime.now(UTC).date()
    names = [
        f"{year}q{quarter}_form13f.zip"
        for year in range(2013, 2024)
        for quarter in range(1, 5)
        if (year, quarter) >= (2013, 2)
    ]
    names.append("01jan2024-29feb2024_form13f.zip")
    year = 2024
    start_month = 3
    while True:
        end_month = start_month + 2
        end_year = year
        if end_month > 12:
            end_month -= 12
            end_year += 1
        end_day = monthrange(end_year, end_month)[1]
        period_end = date(end_year, end_month, end_day)
        if period_end > boundary:
            break
        names.append(
            f"01{date(year, start_month, 1):%b%Y}-"
            f"{end_day:02d}{period_end:%b%Y}_form13f.zip".lower()
        )
        start_month += 3
        if start_month > 12:
            start_month -= 12
            year += 1
    return [urljoin(SEC_13F_ARCHIVE_BASE, name) for name in reversed(names)]


async def sync_sec_13f_archives(
    session: Session,
    *,
    client: httpx.AsyncClient,
    cold_root: Path,
    min_free_bytes: int,
    batch_size: int = 1,
) -> list[InstitutionalArchiveState]:
    """Download/import the next unprocessed official quarters, newest first."""
    if not 1 <= batch_size <= 8:
        raise ValueError("batch_size must be between one and eight")
    seed_company_catalog(session)
    session.commit()
    urls = await discover_sec_13f_archives(client)
    completed: list[InstitutionalArchiveState] = []
    for url in urls:
        archive_key = Path(urlparse(url).path).name
        state = session.get(InstitutionalArchiveState, archive_key)
        if (
            state is not None
            and state.status == "completed"
            and state.reviewed_universe_version == REVIEWED_UNIVERSE_VERSION
        ):
            continue
        completed.append(
            await _sync_one_archive(
                session,
                client=client,
                cold_root=cold_root,
                min_free_bytes=min_free_bytes,
                archive_url=url,
                archive_key=archive_key,
            )
        )
        if len(completed) >= batch_size:
            break
    return completed


async def _sync_one_archive(
    session: Session,
    *,
    client: httpx.AsyncClient,
    cold_root: Path,
    min_free_bytes: int,
    archive_url: str,
    archive_key: str,
) -> InstitutionalArchiveState:
    target_dir = cold_root / "raw" / "sec" / "13f"
    target_dir.mkdir(parents=True, exist_ok=True)
    archive_path = target_dir / archive_key
    state = session.get(InstitutionalArchiveState, archive_key)
    if state is None:
        state = InstitutionalArchiveState(
            archive_key=archive_key,
            source_url=archive_url,
            status="pending",
            archive_bytes=0,
            rows_seen=0,
            holdings_upserted=0,
        )
        session.add(state)
    state.last_started_at = datetime.now(UTC)
    state.last_error = None
    session.commit()
    try:
        if not archive_path.is_file():
            state.status = "downloading"
            session.commit()
            await _download(
                client,
                url=archive_url,
                path=archive_path,
                min_free_bytes=min_free_bytes,
            )
        state.local_path = str(archive_path.relative_to(cold_root))
        state.archive_bytes = archive_path.stat().st_size
        state.status = "importing"
        session.commit()
        rows_seen, holdings = _materialize_archive(session, archive_path)
        state = session.get(InstitutionalArchiveState, archive_key) or state
        state.rows_seen = rows_seen
        state.holdings_upserted = holdings
        state.reviewed_universe_version = REVIEWED_UNIVERSE_VERSION
        state.status = "completed"
        state.last_success_at = datetime.now(UTC)
        state.last_error = None
        session.commit()
    except Exception as exc:
        session.rollback()
        state = session.get(InstitutionalArchiveState, archive_key) or state
        state.status = "failed"
        state.last_error = f"{type(exc).__name__}: {str(exc)[:1_800]}"
        session.commit()
    return state


async def _download(
    client: httpx.AsyncClient,
    *,
    url: str,
    path: Path,
    min_free_bytes: int,
) -> None:
    free = shutil.disk_usage(path.parent).free
    if free < min_free_bytes:
        raise OSError(f"cold storage free bytes {free} below configured reserve {min_free_bytes}")
    temporary = path.with_suffix(path.suffix + ".part")
    try:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            with temporary.open("wb") as handle:
                async for chunk in response.aiter_bytes(1024 * 1024):
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _materialize_archive(session: Session, path: Path) -> tuple[int, int]:
    with ZipFile(path) as archive:
        submission_member = _find_member(archive, "SUBMISSION.tsv")
        cover_member = _find_member(archive, "COVERPAGE.tsv")
        info_member = _find_member(archive, "INFOTABLE.tsv")
        submissions = _table_map(archive, submission_member, "ACCESSION_NUMBER")
        covers = _table_map(archive, cover_member, "ACCESSION_NUMBER")
        rows_seen = 0
        upserted = 0
        batch: list[dict[str, Any]] = []
        with archive.open(info_member) as binary:
            text = io.TextIOWrapper(binary, encoding="utf-8-sig", errors="replace")
            for raw in csv.DictReader(text, delimiter="\t"):
                rows_seen += 1
                row = _normalize_row(raw)
                cusip = re.sub(r"[^A-Z0-9]", "", row.get("CUSIP", "").upper())
                ticker = REVIEWED_CUSIPS.get(cusip)
                if ticker is None:
                    continue
                accession = row.get("ACCESSION_NUMBER", "")
                submission = submissions.get(accession, {})
                cover = covers.get(accession, {})
                filing_date = _parse_sec_date(submission.get("FILING_DATE"))
                report_period = _parse_sec_date(submission.get("PERIODOFREPORT"))
                if filing_date is None or report_period is None:
                    continue
                manager_cik = submission.get("CIK", "").strip()
                manager_name = cover.get("FILINGMANAGER_NAME", "").strip()
                info_key = row.get("INFOTABLE_SK", "").strip()
                if not accession or not manager_cik or not manager_name or not info_key:
                    continue
                batch.append(
                    {
                        "ticker": ticker,
                        "cusip": cusip,
                        "accession_number": accession,
                        "info_table_key": info_key,
                        "report_period": report_period,
                        "filing_date": filing_date,
                        "manager_cik": manager_cik,
                        "manager_name": manager_name[:255],
                        "issuer_name": row.get("NAMEOFISSUER", "")[:255],
                        "title_of_class": row.get("TITLEOFCLASS", "")[:128],
                        "value_thousands": _number(row.get("VALUE")),
                        "shares_or_principal": _number(row.get("SSHPRNAMT")),
                        "shares_type": row.get("SSHPRNAMTTYPE", "")[:16],
                        "put_call": row.get("PUTCALL", "")[:16] or None,
                        "investment_discretion": row.get("INVESTMENTDISCRETION", "")[:32],
                        "source_url": (
                            f"{SEC_ARCHIVES_BASE}/{int(manager_cik)}/{accession.replace('-', '')}/"
                        ),
                    }
                )
                if len(batch) >= 2_000:
                    upserted += _upsert_holdings(session, batch)
                    session.commit()
                    batch.clear()
        if batch:
            upserted += _upsert_holdings(session, batch)
            session.commit()
    return rows_seen, upserted


def build_institutional_evidence(
    session: Session,
    *,
    ticker: str,
    manager_limit: int = 25,
) -> list[dict[str, Any]]:
    """Compare latest two reported quarters without pretending to know cost basis."""
    periods = list(
        session.scalars(
            select(CompanyInstitutionalHolding.report_period)
            .where(CompanyInstitutionalHolding.ticker == ticker)
            .distinct()
            .order_by(desc(CompanyInstitutionalHolding.report_period))
            .limit(2)
        )
    )
    if not periods:
        return []
    rows = list(
        session.scalars(
            select(CompanyInstitutionalHolding)
            .where(
                CompanyInstitutionalHolding.ticker == ticker,
                CompanyInstitutionalHolding.report_period.in_(periods),
                CompanyInstitutionalHolding.put_call.is_(None),
            )
            .order_by(
                desc(CompanyInstitutionalHolding.report_period),
                desc(CompanyInstitutionalHolding.filing_date),
            )
        )
    )
    by_period = {period: _latest_manager_totals(rows, period=period) for period in periods}
    latest = by_period[periods[0]]
    previous = by_period.get(periods[1], {}) if len(periods) > 1 else {}
    ranked = sorted(
        latest.items(),
        key=lambda item: item[1]["value_thousands"],
        reverse=True,
    )[:manager_limit]
    return [
        {
            "evidence_id": (f"sec13f:{ticker}:{periods[0].isoformat()}:{manager_cik}"),
            "category": "institutional_holding",
            "ticker": ticker,
            "report_period": periods[0].isoformat(),
            "previous_report_period": (periods[1].isoformat() if len(periods) > 1 else None),
            "manager_cik": manager_cik,
            "manager_name": values["manager_name"],
            "manager_style_hint": _manager_style_hint(values["manager_name"]),
            "reported_shares": values["shares"],
            "previous_reported_shares": previous.get(manager_cik, {}).get("shares"),
            "reported_share_change": (
                values["shares"] - previous[manager_cik]["shares"]
                if manager_cik in previous
                else None
            ),
            # SEC changed Column 4 from nearest-thousand to nearest-dollar
            # reporting in 2023. Normalize both eras for model evidence while
            # retaining the legacy database column during the historical backfill.
            "reported_value_usd": (
                values["value_thousands"]
                if periods[0] >= date(2023, 1, 1)
                else values["value_thousands"] * 1_000
            ),
            "reported_value_source_unit": (
                "nearest_usd" if periods[0] >= date(2023, 1, 1) else "thousands_usd"
            ),
            "source": "SEC Form 13F structured data",
            "source_url": values["source_url"],
            "limitations": [
                "Quarter-end holdings are filed with a delay and may have amendments.",
                "13F does not disclose purchase price/cost basis or all assets/short positions.",
                "Manager style is only a hint; it does not identify the exact fund vehicle.",
            ],
        }
        for manager_cik, values in ranked
    ]


def institutional_coverage(session: Session) -> dict[str, Any]:
    count, start, end, managers = session.execute(
        select(
            func.count(CompanyInstitutionalHolding.id),
            func.min(CompanyInstitutionalHolding.report_period),
            func.max(CompanyInstitutionalHolding.report_period),
            func.count(func.distinct(CompanyInstitutionalHolding.manager_cik)),
        )
    ).one()
    completed = int(
        session.scalar(
            select(func.count())
            .select_from(InstitutionalArchiveState)
            .where(InstitutionalArchiveState.status == "completed")
        )
        or 0
    )
    return {
        "count": int(count or 0),
        "starts_at": start,
        "ends_at": end,
        "manager_count": int(managers or 0),
        "archives_completed": completed,
        "last_success_at": session.scalar(
            select(func.max(InstitutionalArchiveState.last_success_at))
        ),
    }


def _latest_manager_totals(
    rows: list[CompanyInstitutionalHolding],
    *,
    period: date,
) -> dict[str, dict[str, Any]]:
    selected_accession: dict[str, str] = {}
    totals: dict[str, dict[str, Any]] = defaultdict(lambda: {"shares": 0.0, "value_thousands": 0.0})
    for row in rows:
        if row.report_period != period:
            continue
        accession = selected_accession.setdefault(row.manager_cik, row.accession_number)
        if row.accession_number != accession:
            continue
        total = totals[row.manager_cik]
        total["manager_name"] = row.manager_name
        total["source_url"] = row.source_url
        total["shares"] += row.shares_or_principal
        total["value_thousands"] += row.value_thousands
    return dict(totals)


def _manager_style_hint(name: str) -> str:
    normalized = name.casefold()
    if any(token in normalized for token in ("vanguard", "blackrock", "state street", "geode")):
        return "large index/passive business present; exact fund mandate unknown"
    return "manager style not classified from filing data"


def _find_member(archive: ZipFile, suffix: str) -> str:
    for name in archive.namelist():
        if name.upper().endswith(suffix.upper()):
            return name
    raise ValueError(f"13F archive is missing {suffix}")


def _table_map(archive: ZipFile, member: str, key: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    with archive.open(member) as binary:
        text = io.TextIOWrapper(binary, encoding="utf-8-sig", errors="replace")
        for raw in csv.DictReader(text, delimiter="\t"):
            row = _normalize_row(raw)
            if row.get(key):
                result[row[key]] = row
    return result


def _normalize_row(raw: dict[str | None, str | None]) -> dict[str, str]:
    return {str(key or "").strip().upper(): str(value or "").strip() for key, value in raw.items()}


def _parse_sec_date(value: str | None) -> date | None:
    if not value:
        return None
    for pattern in ("%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.title(), pattern).date()
        except ValueError:
            continue
    return None


def _number(value: str | None) -> float:
    try:
        return float(str(value or "0").replace(",", ""))
    except ValueError:
        return 0.0


def _upsert_holdings(session: Session, rows: list[dict[str, Any]]) -> int:
    deduplicated = {
        (row["ticker"], row["accession_number"], row["info_table_key"]): row for row in rows
    }
    insert = (
        postgresql_insert(CompanyInstitutionalHolding)
        if session.bind is not None and session.bind.dialect.name == "postgresql"
        else sqlite_insert(CompanyInstitutionalHolding)
    )
    statement = insert.values(list(deduplicated.values()))
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[
                CompanyInstitutionalHolding.ticker,
                CompanyInstitutionalHolding.accession_number,
                CompanyInstitutionalHolding.info_table_key,
            ],
            set_={
                "report_period": statement.excluded.report_period,
                "filing_date": statement.excluded.filing_date,
                "manager_name": statement.excluded.manager_name,
                "value_thousands": statement.excluded.value_thousands,
                "shares_or_principal": statement.excluded.shares_or_principal,
                "source_url": statement.excluded.source_url,
            },
        )
    )
    return len(deduplicated)
