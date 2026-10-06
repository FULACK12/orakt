"""Source-reviewed supplier graph and deterministic market-factor bridge."""

from __future__ import annotations

import math
from datetime import date
from statistics import fmean
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    CompanyProfile,
    CompanySupplyChainCoverage,
    CompanySupplyChainEdge,
    MarketObservation,
    MarketSeries,
)

DEFAULT_SUPPLY_CHAIN_GAPS = [
    "supplier names",
    "product dependency",
    "facility mapping",
    "point-in-time source excerpts",
]


# These baskets are category-level market proxies for issuer disclosures that
# name an operational dependency but do not identify a supplier. Constituents
# must never be presented as confirmed counterparties of the subject company.
SUPPLY_CATEGORY_PROXY_SPECS: tuple[dict[str, Any], ...] = (
    {
        "key": "semiconductor_manufacturing_equipment",
        "label": "semiconductor manufacturing equipment basket",
        "match_terms": ("photolithography", "lithography"),
        "series_ids": ("EQ:ASML", "EQ:AMAT"),
    },
    {
        "key": "semiconductor_outsourced_manufacturing",
        "label": "semiconductor foundry, assembly and test basket",
        "match_terms": ("controller", "foundry", "assembly", "analog ic"),
        "series_ids": ("EQ:TSM", "EQ:UMC", "EQ:AMKR", "EQ:ASX"),
    },
    {
        "key": "regulated_utilities",
        "label": "regulated utilities basket",
        "match_terms": ("electricity", "natural gas", "water", "utilities"),
        "series_ids": ("TD:XLU",),
    },
    {
        "key": "datacenter_semiconductors",
        "label": "data-center semiconductor basket",
        "match_terms": ("datacenter", "data center", "server", "gpu"),
        "series_ids": ("EQ:NVDA", "EQ:AMD", "EQ:AVGO"),
    },
    {
        "key": "electronics_manufacturing_services",
        "label": "electronics manufacturing services basket",
        "match_terms": ("contract manufacturer", "company devices", "device manufacturing"),
        "series_ids": ("EQ:JBL", "EQ:AMKR", "EQ:ASX"),
    },
)


def ensure_supply_chain_coverage(session: Session) -> None:
    """Create a transparent pending state for every reviewed US issuer."""
    existing = set(session.scalars(select(CompanySupplyChainCoverage.ticker)))
    for ticker in session.scalars(select(CompanyProfile.ticker)):
        if ticker in existing:
            continue
        session.add(
            CompanySupplyChainCoverage(
                ticker=ticker,
                status="pending",
                gaps=list(DEFAULT_SUPPLY_CHAIN_GAPS),
            )
        )
    session.flush()


def refresh_supply_chain_coverage(session: Session, *, ticker: str) -> None:
    ensure_supply_chain_coverage(session)
    state = session.get(CompanySupplyChainCoverage, ticker)
    if state is None:
        return
    edges = list(
        session.scalars(
            select(CompanySupplyChainEdge).where(CompanySupplyChainEdge.subject_ticker == ticker)
        )
    )
    state.candidate_edges = sum(edge.review_status == "candidate" for edge in edges)
    state.verified_edges = sum(edge.review_status == "verified" for edge in edges)
    state.related_companies_with_market_data = sum(
        edge.review_status == "verified"
        and _related_series(session, edge.related_ticker) is not None
        for edge in edges
    )
    available_dates = [edge.available_at for edge in edges if edge.review_status == "verified"]
    state.latest_available_at = max(available_dates) if available_dates else None
    _reconcile_review_gap(state)
    if state.verified_edges:
        state.status = "verified_partial" if state.gaps else "verified"
    elif state.candidate_edges:
        state.status = "needs_review"
    else:
        state.status = "pending"
    session.flush()


def build_supply_chain_evidence(
    session: Session,
    *,
    ticker: str,
    as_of: date,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return verified edges and point-in-time supplier market factors only."""
    edges = list(
        session.scalars(
            select(CompanySupplyChainEdge)
            .where(
                CompanySupplyChainEdge.subject_ticker == ticker,
                CompanySupplyChainEdge.review_status == "verified",
                CompanySupplyChainEdge.available_at <= as_of,
                (CompanySupplyChainEdge.valid_from.is_(None))
                | (CompanySupplyChainEdge.valid_from <= as_of),
                (CompanySupplyChainEdge.valid_to.is_(None))
                | (CompanySupplyChainEdge.valid_to >= as_of),
            )
            .order_by(
                desc(CompanySupplyChainEdge.confidence), desc(CompanySupplyChainEdge.available_at)
            )
        )
    )
    # A published supplier list can contain hundreds of equally verified rows.
    # Prefer relationships that can be bridged to retained market data, without
    # inflating their source confidence or dropping the complete stored graph.
    series_cache: dict[str | None, MarketSeries | None] = {}
    for edge in edges:
        if edge.related_ticker not in series_cache:
            series_cache[edge.related_ticker] = _related_series(session, edge.related_ticker)
    edges.sort(
        key=lambda edge: (
            series_cache[edge.related_ticker] is not None,
            edge.confidence,
            edge.available_at,
        ),
        reverse=True,
    )
    edges = edges[:80]
    edge_evidence: list[dict[str, Any]] = []
    factor_evidence: list[dict[str, Any]] = []
    for edge in edges:
        edge_ref = f"supply-edge:{edge.id}"
        edge_evidence.append(
            {
                "evidence_id": edge_ref,
                "category": "verified_supply_chain_edge",
                "ticker": ticker,
                "related_company_name": edge.related_company_name,
                "related_ticker": edge.related_ticker,
                "relationship_type": edge.relationship_type,
                "product_or_input": edge.product_or_input,
                "geography": edge.geography,
                "dependency_level": edge.dependency_level,
                "confidence": edge.confidence,
                "observed_at": edge.observed_at.isoformat(),
                "available_at": edge.available_at.isoformat(),
                "source_kind": edge.source_kind,
                "source_ref": edge.source_ref,
                "source_url": edge.source_url,
                "source_excerpt": edge.source_excerpt[:1_500],
                "review_status": edge.review_status,
                "can_verify_claims": True,
            }
        )
        factor = _supplier_market_factor(session, edge=edge, as_of=as_of)
        if factor is not None:
            factor["source_edge_ref"] = edge_ref
            factor_evidence.append(factor)
    return edge_evidence, factor_evidence


def count_verified_supply_chain_edges(
    session: Session,
    *,
    ticker: str,
    as_of: date,
) -> int:
    """Count the complete point-in-time graph, not the bounded evidence payload."""
    return int(
        session.scalar(
            select(func.count())
            .select_from(CompanySupplyChainEdge)
            .where(
                CompanySupplyChainEdge.subject_ticker == ticker,
                CompanySupplyChainEdge.review_status == "verified",
                CompanySupplyChainEdge.available_at <= as_of,
                (CompanySupplyChainEdge.valid_from.is_(None))
                | (CompanySupplyChainEdge.valid_from <= as_of),
                (CompanySupplyChainEdge.valid_to.is_(None))
                | (CompanySupplyChainEdge.valid_to >= as_of),
            )
        )
        or 0
    )


def supply_chain_coverage_rows(session: Session) -> list[dict[str, Any]]:
    ensure_supply_chain_coverage(session)
    profiles = {item.ticker: item for item in session.scalars(select(CompanyProfile))}
    rows = list(
        session.scalars(
            select(CompanySupplyChainCoverage).order_by(CompanySupplyChainCoverage.ticker)
        )
    )
    for row in rows:
        _reconcile_review_gap(row)
    session.flush()
    return [
        {
            "ticker": row.ticker,
            "company_name": profiles[row.ticker].name,
            "status": row.status,
            "candidate_edges": row.candidate_edges,
            "verified_edges": row.verified_edges,
            "related_companies_with_market_data": row.related_companies_with_market_data,
            "latest_available_at": row.latest_available_at,
            "latest_filing_accession": row.latest_filing_accession,
            "latest_filing_date": row.latest_filing_date,
            "latest_raw_archive_path": row.latest_raw_archive_path,
            "last_parser_version": row.last_parser_version,
            "gaps": row.gaps,
            "last_completed_at": row.last_completed_at,
            "last_error": row.last_error,
        }
        for row in rows
        if row.ticker in profiles
    ]


def _reconcile_review_gap(state: CompanySupplyChainCoverage) -> None:
    """Keep human-review status text consistent with measured candidate counts."""
    gaps = list(state.gaps or [])
    review_gap = "candidate relationships require source review"
    if state.candidate_edges and review_gap not in gaps:
        gaps.insert(0, review_gap)
    elif not state.candidate_edges and review_gap in gaps:
        gaps = [item for item in gaps if item != review_gap]
    state.gaps = gaps


def _supplier_market_factor(
    session: Session,
    *,
    edge: CompanySupplyChainEdge,
    as_of: date,
) -> dict[str, Any] | None:
    related = _related_series(session, edge.related_ticker)
    target = session.get(MarketSeries, f"EQ:{edge.subject_ticker}")
    if target is None:
        return None
    if related is None:
        return _category_proxy_market_factor(session, edge=edge, target=target, as_of=as_of)
    target_rows = _market_rows(session, target.series_id, as_of=as_of)
    related_rows = _market_rows(session, related.series_id, as_of=as_of)
    common_dates = sorted(set(target_rows) & set(related_rows))
    if len(common_dates) < 62:
        return None
    target_returns = _returns(target_rows, common_dates)
    related_returns = _returns(related_rows, common_dates)
    aligned = sorted(set(target_returns) & set(related_returns))[-252:]
    if len(aligned) < 60:
        return None
    contemporaneous = _correlation(
        [related_returns[item] for item in aligned],
        [target_returns[item] for item in aligned],
    )
    lag_supplier: list[float] = []
    lead_target: list[float] = []
    for index in range(len(aligned) - 1):
        lag_supplier.append(related_returns[aligned[index]])
        lead_target.append(target_returns[aligned[index + 1]])
    lag_correlation = _correlation(lag_supplier, lead_target)
    recent_dates = common_dates[-22:]
    momentum_21d = (
        related_rows[recent_dates[-1]] / related_rows[recent_dates[0]] - 1
        if len(recent_dates) >= 2 and related_rows[recent_dates[0]] > 0
        else None
    )
    return {
        "evidence_id": f"supplier-factor:{edge.id}:{as_of.isoformat()}",
        "category": "derived_supplier_factor",
        "ticker": edge.subject_ticker,
        "proxy_type": "verified_named_supplier",
        "identity_status": "verified_named_supplier",
        "supplier_series_id": related.series_id,
        "supplier_name": edge.related_company_name,
        "product_or_input": edge.product_or_input,
        "as_of": as_of.isoformat(),
        "sample_size": len(aligned),
        "supplier_return_21d": momentum_21d,
        "same_day_return_correlation": contemporaneous,
        "supplier_lag1_target_return_correlation": lag_correlation,
        "method": "daily split-adjusted returns; supplier t versus target t+1 is exploratory",
        "limitations": [
            "A supplier stock price is not a direct measure of component volume, "
            "price, capacity or delivery reliability.",
            "Correlation does not prove operational transmission and may reflect "
            "common market exposure.",
        ],
        "can_verify_claims": True,
    }


def _category_proxy_market_factor(
    session: Session,
    *,
    edge: CompanySupplyChainEdge,
    target: MarketSeries,
    as_of: date,
) -> dict[str, Any] | None:
    """Build a transparent category basket without inferring supplier identity."""
    spec = _category_proxy_spec(edge)
    if spec is None:
        return None
    component_series = [
        series
        for series_id in spec["series_ids"]
        if (series := session.get(MarketSeries, series_id)) is not None
    ]
    if not component_series:
        return None
    target_rows = _market_rows(session, target.series_id, as_of=as_of)
    target_dates = sorted(target_rows)
    target_returns = _returns(target_rows, target_dates)
    component_returns: dict[str, dict[date, float]] = {}
    for series in component_series:
        rows = _market_rows(session, series.series_id, as_of=as_of)
        returns = _returns(rows, sorted(rows))
        if returns:
            component_returns[series.series_id] = returns
    factor_returns: dict[date, float] = {}
    for observed_on in target_returns:
        values = [
            returns[observed_on]
            for returns in component_returns.values()
            if observed_on in returns
        ]
        if values:
            factor_returns[observed_on] = fmean(values)
    aligned = sorted(set(target_returns) & set(factor_returns))[-252:]
    if len(aligned) < 60:
        return None
    contemporaneous = _correlation(
        [factor_returns[item] for item in aligned],
        [target_returns[item] for item in aligned],
    )
    lag_correlation = _correlation(
        [factor_returns[item] for item in aligned[:-1]],
        [target_returns[item] for item in aligned[1:]],
    )
    recent_returns = [factor_returns[item] for item in aligned[-21:]]
    momentum_21d = math.exp(sum(recent_returns)) - 1 if recent_returns else None
    components = [
        {
            "series_id": series.series_id,
            "name": series.name,
            "source_name": series.source_name,
        }
        for series in component_series
        if series.series_id in component_returns
    ]
    return {
        "evidence_id": f"supply-category-factor:{edge.id}:{as_of.isoformat()}",
        "category": "derived_supplier_factor",
        "ticker": edge.subject_ticker,
        "proxy_type": "category_basket",
        "identity_status": "unnamed_dependency_not_supplier_identification",
        "supplier_series_id": f"BASKET:{spec['key']}",
        "supplier_name": f"{spec['label']} (category proxy; not a confirmed supplier)",
        "product_or_input": edge.product_or_input,
        "basket_components": components,
        "as_of": as_of.isoformat(),
        "sample_size": len(aligned),
        "supplier_return_21d": momentum_21d,
        "same_day_return_correlation": contemporaneous,
        "supplier_lag1_target_return_correlation": lag_correlation,
        "method": (
            "equal-weighted mean of available daily split-adjusted component returns; "
            "category basket t versus target t+1 is exploratory"
        ),
        "limitations": [
            "The issuer filing identifies only a dependency category. Basket constituents "
            "are not asserted to be suppliers or counterparties of the issuer.",
            "The basket measures sector co-movement, not orders, price, capacity, delivery "
            "reliability or a verified operational transmission channel.",
            "Correlation does not prove causality and may reflect common market exposure.",
        ],
        "can_verify_claims": True,
    }


def _category_proxy_spec(edge: CompanySupplyChainEdge) -> dict[str, Any] | None:
    haystack = " ".join(
        str(value or "").casefold()
        for value in (
            edge.related_company_name,
            edge.relationship_type,
            edge.product_or_input,
        )
    )
    for spec in SUPPLY_CATEGORY_PROXY_SPECS:
        if any(term in haystack for term in spec["match_terms"]):
            return spec
    return None


def _related_series(session: Session, ticker: str | None) -> MarketSeries | None:
    if not ticker:
        return None
    candidates = (ticker,) if ":" in ticker else (f"EQ:{ticker.upper()}", f"CN:{ticker}", ticker)
    for series_id in candidates:
        series = session.get(MarketSeries, series_id)
        if series is not None:
            return series
    return None


def _market_rows(session: Session, series_id: str, *, as_of: date) -> dict[date, float]:
    rows = list(
        session.execute(
            select(MarketObservation.observed_on, MarketObservation.value)
            .where(
                MarketObservation.series_id == series_id,
                MarketObservation.observed_on <= as_of,
            )
            .order_by(desc(MarketObservation.observed_on))
            .limit(560)
        )
    )
    return {observed_on: float(value) for observed_on, value in rows if float(value) > 0}


def _returns(values: dict[date, float], dates: list[date]) -> dict[date, float]:
    result: dict[date, float] = {}
    for index in range(1, len(dates)):
        before = values[dates[index - 1]]
        current = values[dates[index]]
        if before > 0 and current > 0:
            result[dates[index]] = math.log(current / before)
    return result


def _correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    left_mean = fmean(left)
    right_mean = fmean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right, strict=True))
    denominator = math.sqrt(
        sum((x - left_mean) ** 2 for x in left) * sum((y - right_mean) ** 2 for y in right)
    )
    return numerator / denominator if denominator > 1e-18 else None
