"""Reviewed US large-company fundamentals and price history."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.companies import latest_company_facts
from app.db.models import (
    CompanyFiling,
    CompanyProfile,
    CompanySupplyChainEdge,
    CompanySyncState,
    MarketObservation,
)
from app.db.session import get_db_session
from app.schemas.companies import (
    CompanyFactView,
    CompanyListResponse,
    CompanySupplyChainCoverageResponse,
    CompanySupplyChainEdgeResponse,
    CompanySupplyChainEdgeView,
    CompanyView,
    SupplierMarketHistoryStatusView,
    SupplyChainSiteExposureResponse,
)
from app.supplier_market_history import supplier_market_history_status
from app.supply_chain import supply_chain_coverage_rows
from app.supply_chain_sites import supply_chain_site_exposure

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/supply-chain/coverage", response_model=CompanySupplyChainCoverageResponse)
def supply_chain_coverage(
    session: Annotated[Session, Depends(get_db_session)],
) -> CompanySupplyChainCoverageResponse:
    """Expose verified/candidate/missing supplier coverage without overstating completeness."""
    rows = supply_chain_coverage_rows(session)
    session.commit()
    return CompanySupplyChainCoverageResponse(companies=rows)


@router.get(
    "/supply-chain/market-history",
    response_model=SupplierMarketHistoryStatusView,
)
def supply_chain_market_history(
    session: Annotated[Session, Depends(get_db_session)],
) -> SupplierMarketHistoryStatusView:
    """Expose restart-safe supplier price coverage and exact retained ranges."""
    return SupplierMarketHistoryStatusView.model_validate(
        supplier_market_history_status(session)
    )


@router.get(
    "/supply-chain/{ticker}/sites",
    response_model=SupplyChainSiteExposureResponse,
)
def supply_chain_sites(
    ticker: str,
    session: Annotated[Session, Depends(get_db_session)],
    as_of: Annotated[date | None, Query()] = None,
    weeks: Annotated[int, Query(ge=1, le=520)] = 12,
    limit: Annotated[int, Query(ge=1, le=2_000)] = 500,
) -> SupplyChainSiteExposureResponse:
    """Return source-bounded manufacturing regions and nearby risk signals."""
    return SupplyChainSiteExposureResponse.model_validate(
        supply_chain_site_exposure(
            session,
            ticker=ticker,
            as_of=as_of or date.today(),
            weeks=weeks,
            limit=limit,
        )
    )


@router.get(
    "/supply-chain/{ticker}",
    response_model=CompanySupplyChainEdgeResponse,
)
def supply_chain_edges(
    ticker: str,
    session: Annotated[Session, Depends(get_db_session)],
) -> CompanySupplyChainEdgeResponse:
    """List quoted candidates and verified edges for an auditable issuer graph."""
    normalized = ticker.strip().upper()
    edges = list(
        session.scalars(
            select(CompanySupplyChainEdge)
            .where(CompanySupplyChainEdge.subject_ticker == normalized)
            .order_by(
                desc(CompanySupplyChainEdge.available_at),
                desc(CompanySupplyChainEdge.confidence),
            )
        )
    )
    return CompanySupplyChainEdgeResponse(
        edges=[CompanySupplyChainEdgeView.model_validate(edge) for edge in edges]
    )


@router.get("", response_model=CompanyListResponse)
def list_companies(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> CompanyListResponse:
    return CompanyListResponse(
        companies=[
            _company_view(session, profile, fact_limit=12)
            for profile in session.scalars(
                select(CompanyProfile).order_by(CompanyProfile.ticker).limit(limit)
            )
        ]
    )


@router.get("/{ticker}", response_model=CompanyView)
def get_company(
    ticker: str,
    session: Annotated[Session, Depends(get_db_session)],
) -> CompanyView:
    profile = session.get(CompanyProfile, ticker.upper())
    if profile is None:
        raise HTTPException(status_code=404, detail="company not found")
    return _company_view(session, profile, fact_limit=100)


def _company_view(
    session: Session,
    profile: CompanyProfile,
    *,
    fact_limit: int,
) -> CompanyView:
    price = session.execute(
        select(MarketObservation.value, MarketObservation.observed_on)
        .where(MarketObservation.series_id == f"EQ:{profile.ticker}")
        .order_by(desc(MarketObservation.observed_on))
        .limit(1)
    ).one_or_none()
    filing = session.scalar(
        select(CompanyFiling)
        .where(CompanyFiling.ticker == profile.ticker)
        .order_by(desc(CompanyFiling.filed_at))
        .limit(1)
    )
    state = session.get(CompanySyncState, profile.ticker)
    facts = latest_company_facts(
        session,
        ticker=profile.ticker,
        limit=fact_limit,
    )
    return CompanyView(
        ticker=profile.ticker,
        cik=profile.cik,
        name=profile.name,
        sector=profile.sector,
        industry=profile.industry,
        source_url=profile.source_url,
        latest_price=float(price[0]) if price else None,
        price_observed_on=price[1] if price else None,
        latest_filing_form=filing.form if filing else None,
        latest_filing_date=filing.filed_at if filing else None,
        latest_facts=[
            CompanyFactView(
                concept=fact.concept,
                label=fact.label,
                unit=fact.unit,
                value=fact.value,
                period_start=fact.period_start,
                period_end=fact.period_end,
                filed_at=fact.filed_at,
                form=fact.form,
                fiscal_year=fact.fiscal_year,
                fiscal_period=fact.fiscal_period,
                source_url=fact.source_url,
            )
            for fact in facts
        ],
        last_success_at=state.last_success_at if state else None,
        last_error=state.last_error if state else None,
    )
