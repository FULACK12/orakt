"""Point-in-time, same-definition operating comparisons for public equities."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import CompanyFinancialFact, CompanyProfile
from app.product_evidence import build_product_operating_evidence

COMPETITOR_GROUPS: dict[str, tuple[str, ...]] = {
    "AAPL": ("AAPL", "MSFT", "GOOGL", "AMZN"),
    "MSFT": ("MSFT", "GOOGL", "AMZN", "AAPL"),
    "NVDA": ("NVDA", "AMD", "INTC", "MU"),
    "AMD": ("AMD", "NVDA", "INTC", "MU"),
    "MU": ("MU", "NVDA", "AMD", "INTC"),
}

_REVENUE_CONCEPTS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)
_FLOW_CONCEPTS = {
    *_REVENUE_CONCEPTS,
    "GrossProfit",
    "NetIncomeLoss",
    "ResearchAndDevelopmentExpense",
}
_INSTANT_CONCEPTS = {"InventoryNet"}


def build_competitor_operating_comparison(
    session: Session,
    *,
    ticker: str,
    as_of: date,
    cold_data_root: Path,
) -> dict[str, Any] | None:
    """Compare standardized filed metrics and keep product excerpts in a separate layer."""
    normalized = ticker.strip().upper()
    requested = COMPETITOR_GROUPS.get(normalized)
    if requested is None:
        return None
    profiles = {
        item.ticker: item
        for item in session.scalars(
            select(CompanyProfile).where(CompanyProfile.ticker.in_(requested))
        )
    }
    rows: list[dict[str, Any]] = []
    product_disclosures: list[dict[str, Any]] = []
    for peer in requested:
        row = _annual_metric_snapshot(session, ticker=peer, as_of=as_of)
        if row is not None:
            row["company"] = profiles.get(peer).name if peer in profiles else peer
            quarterly = _quarterly_metric_snapshot(session, ticker=peer, as_of=as_of)
            row["quarterly"] = quarterly
            if quarterly is not None:
                row["underlying_evidence_refs"] = list(
                    dict.fromkeys(
                        [
                            *row.get("underlying_evidence_refs", []),
                            *quarterly.get("underlying_evidence_refs", []),
                        ]
                    )
                )
            rows.append(row)
        peer_evidence = build_product_operating_evidence(
            session,
            ticker=peer,
            as_of=as_of,
            cold_data_root=cold_data_root,
            limit=12,
            quarterly_periods=2,
        )
        latest_by_metric: dict[str, dict[str, Any]] = {}
        for item in peer_evidence:
            if item.get("evidence_status") != "reported_actual":
                continue
            key = str(item.get("metric_type") or "")
            if not key:
                continue
            current = latest_by_metric.get(key)
            if current is None or str(item.get("available_at") or "") > str(
                current.get("available_at") or ""
            ):
                latest_by_metric[key] = item
        for item in latest_by_metric.values():
            product_disclosures.append(
                {
                    "ticker": peer,
                    "metric_type": item.get("metric_type"),
                    "metric_name": item.get("metric_name"),
                    "product": item.get("product"),
                    "reported_values": item.get("reported_values") or [],
                    "period_end": item.get("period_end"),
                    "available_at": item.get("available_at"),
                    "filing_form": item.get("filing_form"),
                    "source_excerpt": item.get("source_excerpt"),
                    "source_url": item.get("source_url"),
                    "evidence_ref": item.get("evidence_id"),
                }
            )
    if not rows:
        return None
    ranks = {
        metric: _metric_ranks(rows, metric=metric)
        for metric in (
            "revenue_yoy",
            "gross_margin",
            "net_margin",
            "research_and_development_to_revenue",
        )
    }
    for row in rows:
        row["ranks"] = {
            metric: rank_by_ticker.get(row["ticker"])
            for metric, rank_by_ticker in ranks.items()
        }
    quarterly_ranks = {
        metric: _nested_metric_ranks(rows, group="quarterly", metric=metric)
        for metric in (
            "revenue_yoy",
            "gross_margin",
            "net_margin",
            "research_and_development_to_revenue",
        )
    }
    for row in rows:
        quarterly = row.get("quarterly")
        if not isinstance(quarterly, dict):
            continue
        quarterly["ranks"] = {
            metric: rank_by_ticker.get(row["ticker"])
            for metric, rank_by_ticker in quarterly_ranks.items()
        }
    comparable_product_types = sorted(
        metric_type
        for metric_type in {item["metric_type"] for item in product_disclosures}
        if sum(item["metric_type"] == metric_type for item in product_disclosures) >= 2
    )
    return {
        "evidence_id": f"derived:competitive-operating:{normalized}:{as_of.isoformat()}",
        "category": "competitive_operating_comparison",
        "ticker": normalized,
        "as_of": as_of.isoformat(),
        "peer_group": list(requested),
        "rows": rows,
        "product_disclosures": product_disclosures,
        "comparable_product_metric_types": comparable_product_types,
        "metric_definitions": {
            "quarterly_revenue_yoy": (
                "Latest filed single-quarter revenue versus the comparable issuer quarter "
                "approximately one year earlier."
            ),
            "quarterly_margins": (
                "Single-quarter gross profit, net income and R&D divided by revenue for "
                "that same quarter; year-to-date contexts are excluded."
            ),
            "revenue_yoy": "Latest filed annual revenue versus the preceding annual period.",
            "gross_margin": "Gross profit divided by revenue for the same annual period.",
            "net_margin": "Net income divided by revenue for the same annual period.",
            "research_and_development_to_revenue": (
                "Research and development expense divided by revenue for the same period."
            ),
            "inventory_yoy": "Year-over-year change in reported period-end inventory.",
        },
        "source": "Point-in-time SEC Company Facts and archived SEC filing excerpts",
        "underlying_evidence_refs": list(
            dict.fromkeys(
                ref
                for row in rows
                for ref in row.get("underlying_evidence_refs", [])
            )
        )[:80],
        "limitations": [
            "Definitions are standardized, but fiscal year-end dates can differ by issuer.",
            (
                "Quarterly comparisons use each issuer's latest available single quarter; "
                "calendar dates and product cycles can differ."
            ),
            (
                "Product disclosure rows are compared only when metric_type overlaps; "
                "differently named product revenue is not ranked as if identical."
            ),
            (
                "Annual accounting ratios and quarterly product wording do not establish "
                "future stock returns."
            ),
            (
                "Extreme or missing ratios remain visible with quality flags; the flag "
                "requires review of one-off gains, taxonomy coverage or corporate actions."
            ),
        ],
        "can_verify_claims": True,
    }


def _quarterly_metric_snapshot(
    session: Session,
    *,
    ticker: str,
    as_of: date,
) -> dict[str, Any] | None:
    """Build a same-quarter accounting snapshot while excluding 10-Q YTD contexts."""
    facts = list(
        session.scalars(
            select(CompanyFinancialFact)
            .where(
                CompanyFinancialFact.ticker == ticker,
                CompanyFinancialFact.concept.in_(_FLOW_CONCEPTS | _INSTANT_CONCEPTS),
                CompanyFinancialFact.form.in_(("10-Q", "10-Q/A")),
                CompanyFinancialFact.filed_at <= as_of,
                CompanyFinancialFact.period_end <= as_of,
            )
            .order_by(
                desc(CompanyFinancialFact.period_end),
                desc(CompanyFinancialFact.filed_at),
            )
            .limit(800)
        )
    )
    by_period: dict[date, dict[str, CompanyFinancialFact]] = {}
    for fact in facts:
        if fact.concept in _FLOW_CONCEPTS:
            if fact.period_start is None:
                continue
            duration = (fact.period_end - fact.period_start).days
            if not 60 <= duration <= 120:
                continue
        by_period.setdefault(fact.period_end, {}).setdefault(fact.concept, fact)
    revenue_periods = sorted(
        (
            period_end
            for period_end, values in by_period.items()
            if _revenue_fact(values) is not None
        ),
        reverse=True,
    )
    if not revenue_periods:
        return None
    latest_end = revenue_periods[0]
    prior_candidates = [
        period_end
        for period_end in revenue_periods[1:]
        if 340 <= (latest_end - period_end).days <= 390
    ]
    prior_end = (
        min(prior_candidates, key=lambda item: abs((latest_end - item).days - 365))
        if prior_candidates
        else None
    )
    latest = by_period[latest_end]
    prior = by_period.get(prior_end, {}) if prior_end else {}
    revenue = _revenue_fact(latest)
    prior_revenue = _revenue_fact(prior)
    if revenue is None:
        return None
    gross_profit = latest.get("GrossProfit")
    net_income = latest.get("NetIncomeLoss")
    research = latest.get("ResearchAndDevelopmentExpense")
    inventory = latest.get("InventoryNet")
    prior_inventory = prior.get("InventoryNet")
    used = [
        item
        for item in (
            revenue,
            prior_revenue,
            gross_profit,
            net_income,
            research,
            inventory,
            prior_inventory,
        )
        if item is not None
    ]
    revenue_yoy = _growth(
        revenue.value,
        prior_revenue.value if prior_revenue else None,
    )
    gross_margin = _ratio(
        gross_profit.value if gross_profit else None,
        revenue.value,
    )
    net_margin = _ratio(
        net_income.value if net_income else None,
        revenue.value,
    )
    research_intensity = _ratio(
        research.value if research else None,
        revenue.value,
    )
    return {
        "period_end": latest_end.isoformat(),
        "comparison_period_end": prior_end.isoformat() if prior_end else None,
        "available_at": max(item.filed_at for item in used).isoformat(),
        "revenue": revenue.value,
        "revenue_yoy": revenue_yoy,
        "gross_margin": gross_margin,
        "net_margin": net_margin,
        "research_and_development_to_revenue": research_intensity,
        "inventory_yoy": _growth(
            inventory.value if inventory else None,
            prior_inventory.value if prior_inventory else None,
        ),
        "quality_flags": _metric_quality_flags(
            revenue_yoy=revenue_yoy,
            gross_margin=gross_margin,
            net_margin=net_margin,
            research_intensity=research_intensity,
        ),
        "underlying_evidence_refs": [_fact_ref(item) for item in used],
    }


def _annual_metric_snapshot(
    session: Session,
    *,
    ticker: str,
    as_of: date,
) -> dict[str, Any] | None:
    facts = list(
        session.scalars(
            select(CompanyFinancialFact)
            .where(
                CompanyFinancialFact.ticker == ticker,
                CompanyFinancialFact.concept.in_(_FLOW_CONCEPTS | _INSTANT_CONCEPTS),
                CompanyFinancialFact.form.in_(("10-K", "10-K/A")),
                CompanyFinancialFact.filed_at <= as_of,
                CompanyFinancialFact.period_end <= as_of,
            )
            .order_by(
                desc(CompanyFinancialFact.period_end),
                desc(CompanyFinancialFact.filed_at),
            )
            .limit(600)
        )
    )
    by_period: dict[date, dict[str, CompanyFinancialFact]] = {}
    for fact in facts:
        if fact.concept in _FLOW_CONCEPTS:
            if fact.period_start is None:
                continue
            duration = (fact.period_end - fact.period_start).days
            if not 300 <= duration <= 400:
                continue
        by_period.setdefault(fact.period_end, {}).setdefault(fact.concept, fact)
    revenue_periods = sorted(
        (
            period_end
            for period_end, values in by_period.items()
            if _revenue_fact(values) is not None
        ),
        reverse=True,
    )
    if not revenue_periods:
        return None
    latest_end = revenue_periods[0]
    prior_end = revenue_periods[1] if len(revenue_periods) > 1 else None
    latest = by_period[latest_end]
    prior = by_period.get(prior_end, {}) if prior_end else {}
    revenue = _revenue_fact(latest)
    prior_revenue = _revenue_fact(prior)
    if revenue is None:
        return None
    gross_profit = latest.get("GrossProfit")
    net_income = latest.get("NetIncomeLoss")
    research = latest.get("ResearchAndDevelopmentExpense")
    inventory = latest.get("InventoryNet")
    prior_inventory = prior.get("InventoryNet")
    used = [
        item
        for item in (
            revenue,
            prior_revenue,
            gross_profit,
            net_income,
            research,
            inventory,
            prior_inventory,
        )
        if item is not None
    ]
    revenue_yoy = _growth(revenue.value, prior_revenue.value if prior_revenue else None)
    gross_margin = _ratio(gross_profit.value if gross_profit else None, revenue.value)
    net_margin = _ratio(net_income.value if net_income else None, revenue.value)
    research_intensity = _ratio(
        research.value if research else None,
        revenue.value,
    )
    return {
        "ticker": ticker,
        "period_end": latest_end.isoformat(),
        "available_at": max(item.filed_at for item in used).isoformat(),
        "revenue": revenue.value,
        "revenue_yoy": revenue_yoy,
        "gross_margin": gross_margin,
        "net_margin": net_margin,
        "research_and_development_to_revenue": research_intensity,
        "inventory_yoy": _growth(
            inventory.value if inventory else None,
            prior_inventory.value if prior_inventory else None,
        ),
        "quality_flags": _metric_quality_flags(
            revenue_yoy=revenue_yoy,
            gross_margin=gross_margin,
            net_margin=net_margin,
            research_intensity=research_intensity,
        ),
        "underlying_evidence_refs": [_fact_ref(item) for item in used],
    }


def _revenue_fact(values: dict[str, CompanyFinancialFact]) -> CompanyFinancialFact | None:
    return next((values.get(concept) for concept in _REVENUE_CONCEPTS if values.get(concept)), None)


def _growth(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous <= 0:
        return None
    return current / previous - 1


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def _metric_quality_flags(
    *,
    revenue_yoy: float | None,
    gross_margin: float | None,
    net_margin: float | None,
    research_intensity: float | None,
) -> list[str]:
    flags: list[str] = []
    if revenue_yoy is not None and (revenue_yoy > 1.5 or revenue_yoy < -0.75):
        flags.append("extreme_revenue_change_review_corporate_actions")
    if gross_margin is None:
        flags.append("gross_margin_unavailable_in_standard_taxonomy")
    elif gross_margin > 1 or gross_margin < -0.25:
        flags.append("gross_margin_outside_expected_accounting_range")
    if net_margin is not None and (net_margin > 0.6 or net_margin < -0.6):
        flags.append("extreme_net_margin_review_one_offs")
    if research_intensity is None:
        flags.append("research_intensity_unavailable_in_standard_taxonomy")
    return flags


def _fact_ref(fact: CompanyFinancialFact) -> str:
    return (
        f"sec:{fact.ticker}:{fact.concept}:{fact.period_end.isoformat()}:"
        f"{fact.accession_number}"
    )


def _metric_ranks(rows: list[dict[str, Any]], *, metric: str) -> dict[str, int]:
    ranked = sorted(
        (row for row in rows if isinstance(row.get(metric), (int, float))),
        key=lambda row: float(row[metric]),
        reverse=True,
    )
    return {str(row["ticker"]): index + 1 for index, row in enumerate(ranked)}


def _nested_metric_ranks(
    rows: list[dict[str, Any]],
    *,
    group: str,
    metric: str,
) -> dict[str, int]:
    ranked = sorted(
        (
            row
            for row in rows
            if isinstance(row.get(group), dict)
            and isinstance(row[group].get(metric), (int, float))
        ),
        key=lambda row: float(row[group][metric]),
        reverse=True,
    )
    return {str(row["ticker"]): index + 1 for index, row in enumerate(ranked)}
