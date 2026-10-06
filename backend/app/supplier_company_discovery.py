"""Resolve verified public suppliers against the official SEC ticker catalog."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.models import CompanyProfile, CompanySupplyChainEdge, MarketSyncState

SEC_TICKER_CATALOG_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUPPLIER_PROFILE_PROVIDER_KEY = "sec_supplier_profiles"


class SupplierCompanyDiscoveryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_tickers: list[str] = Field(default_factory=list)
    profiles_upserted: int = Field(ge=0)
    matched_tickers: list[str] = Field(default_factory=list)
    unresolved_tickers: list[str] = Field(default_factory=list)
    skipped_recently: bool = False


async def sync_supplier_company_profiles_from_sec(
    session: Session,
    *,
    client: httpx.AsyncClient,
    refresh_after: timedelta = timedelta(hours=24),
) -> SupplierCompanyDiscoveryResult:
    """Create honest placeholder profiles only when SEC establishes ticker identity."""
    candidate_names = _missing_supplier_profile_candidates(session)
    candidates = sorted(candidate_names)
    state = session.get(MarketSyncState, SEC_SUPPLIER_PROFILE_PROVIDER_KEY)
    now = datetime.now(UTC)
    cached_unresolved = _cached_unresolved_tickers(state.last_error if state else None)
    if (
        state is not None
        and state.last_success_at is not None
        and _as_utc(state.last_success_at) > now - refresh_after
        and set(candidates).issubset(cached_unresolved)
    ):
        return SupplierCompanyDiscoveryResult(
            candidate_tickers=candidates,
            profiles_upserted=0,
            unresolved_tickers=candidates,
            skipped_recently=True,
        )
    state = _sync_state(session)
    state.last_started_at = now
    session.flush()
    if not candidates:
        state.last_success_at = now
        state.series_synced = 0
        state.last_error = None
        session.flush()
        return SupplierCompanyDiscoveryResult(profiles_upserted=0)

    try:
        response = await client.get(SEC_TICKER_CATALOG_URL)
        response.raise_for_status()
        catalog = _parse_sec_ticker_catalog(response.json())
        matched: list[str] = []
        for ticker in candidates:
            identity = catalog.get(ticker) or catalog.get(ticker.replace(".", "-"))
            if identity is None:
                continue
            cik, _, title = identity
            _upsert_profile(
                session,
                ticker=ticker,
                cik=cik,
                name=title or candidate_names[ticker],
            )
            matched.append(ticker)
        unresolved = [ticker for ticker in candidates if ticker not in matched]
        state.series_synced = len(matched)
        state.observations_upserted = 0
        state.last_success_at = datetime.now(UTC)
        state.last_error = (
            f"unresolved tickers: {','.join(unresolved)}" if unresolved else None
        )
        session.flush()
        return SupplierCompanyDiscoveryResult(
            candidate_tickers=candidates,
            profiles_upserted=len(matched),
            matched_tickers=matched,
            unresolved_tickers=unresolved,
        )
    except (httpx.HTTPError, TypeError, ValueError) as exc:
        state.last_error = f"{type(exc).__name__}: {str(exc)[:500]}"
        session.flush()
        raise


def _missing_supplier_profile_candidates(session: Session) -> dict[str, str]:
    existing = set(session.scalars(select(CompanyProfile.ticker)))
    candidates: dict[str, str] = {}
    for ticker, name in session.execute(
        select(
            CompanySupplyChainEdge.related_ticker,
            CompanySupplyChainEdge.related_company_name,
        ).where(
            CompanySupplyChainEdge.review_status == "verified",
            CompanySupplyChainEdge.related_ticker.is_not(None),
        )
    ):
        if not ticker:
            continue
        normalized = str(ticker).strip().upper()
        if normalized not in existing:
            candidates.setdefault(normalized, str(name))
    return candidates


def _parse_sec_ticker_catalog(payload: Any) -> dict[str, tuple[str, str, str]]:
    if not isinstance(payload, dict):
        raise TypeError("SEC ticker catalog must be an object")
    result: dict[str, tuple[str, str, str]] = {}
    for item in payload.values():
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").strip().upper()
        title = str(item.get("title") or "").strip()
        raw_cik = item.get("cik_str")
        try:
            cik = f"{int(raw_cik):010d}"
        except (TypeError, ValueError):
            continue
        if ticker and title:
            result[ticker] = (cik, ticker, title)
    if not result:
        raise ValueError("SEC ticker catalog contains no valid identities")
    return result


def _upsert_profile(
    session: Session,
    *,
    ticker: str,
    cik: str,
    name: str,
) -> None:
    insert = _dialect_insert(session, CompanyProfile)
    statement = insert.values(
        ticker=ticker,
        cik=cik,
        name=name,
        sector="Supplier network",
        industry="SEC identity resolved; classification pending",
        source_url=f"https://www.sec.gov/edgar/browse/?CIK={int(cik)}&owner=exclude",
    )
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[CompanyProfile.ticker],
            set_={
                "cik": statement.excluded.cik,
                "name": statement.excluded.name,
                "source_url": statement.excluded.source_url,
            },
        )
    )
def _sync_state(session: Session) -> MarketSyncState:
    state = session.get(MarketSyncState, SEC_SUPPLIER_PROFILE_PROVIDER_KEY)
    if state is None:
        state = MarketSyncState(
            provider_key=SEC_SUPPLIER_PROFILE_PROVIDER_KEY,
            series_synced=0,
            observations_upserted=0,
        )
        session.add(state)
    return state


def _dialect_insert(session: Session, model: type[Any]) -> Any:
    if session.get_bind().dialect.name == "sqlite":
        return sqlite_insert(model)
    return postgresql_insert(model)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _cached_unresolved_tickers(value: str | None) -> set[str]:
    prefix = "unresolved tickers: "
    if not value or not value.startswith(prefix):
        return set()
    return {
        item.strip().upper()
        for item in value.removeprefix(prefix).split(",")
        if item.strip()
    }
