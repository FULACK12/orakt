"""Auditable yearly evidence coverage for autonomous research planning."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import distinct, extract, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    CompanyFinancialFact,
    Document,
    EconomicObservation,
    Event,
    MarketObservation,
)


def build_research_event_table(
    session: Session,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Summarize which closed years are sufficiently complete for research.

    The table deliberately measures retained local records. A configured API or
    a very old first observation does not make a year research-ready.
    """
    generated_at = now or datetime.now(UTC)
    current_year = generated_at.year
    rows: dict[int, dict[str, Any]] = {}

    def period(year: int) -> dict[str, Any]:
        return rows.setdefault(
            year,
            {
                "year": year,
                "start": f"{year:04d}-01-01",
                "end": f"{year:04d}-12-31",
                "documents": 0,
                "full_documents": 0,
                "news_sources": 0,
                "events": 0,
                "market_observations": 0,
                "market_series": 0,
                "company_facts": 0,
                "company_tickers": 0,
                "economic_observations": 0,
                "economic_indicators": 0,
                "economic_countries": 0,
                "representative_events": [],
            },
        )

    document_year = extract("year", Document.published_at)
    substantive_body = (
        Document.body.is_not(None) & (func.length(func.trim(Document.body)) >= 120)
    )
    for year, count, full_count, source_count in session.execute(
        select(
            document_year,
            func.count(Document.id),
            func.count(Document.id).filter(substantive_body),
            func.count(distinct(Document.source_id)),
        )
        .where(Document.published_at.is_not(None))
        .group_by(document_year)
    ):
        if year is None:
            continue
        item = period(int(year))
        item.update(
            documents=int(count or 0),
            full_documents=int(full_count or 0),
            news_sources=int(source_count or 0),
        )

    event_year = extract("year", Event.start_at)
    for year, count in session.execute(
        select(event_year, func.count(Event.id)).group_by(event_year)
    ):
        if year is not None:
            period(int(year))["events"] = int(count or 0)

    market_year = extract("year", MarketObservation.observed_on)
    for year, count, series_count in session.execute(
        select(
            market_year,
            func.count(),
            func.count(distinct(MarketObservation.series_id)),
        ).group_by(market_year)
    ):
        if year is None:
            continue
        item = period(int(year))
        item.update(
            market_observations=int(count or 0),
            market_series=int(series_count or 0),
        )

    company_year = extract("year", CompanyFinancialFact.period_end)
    for year, count, ticker_count in session.execute(
        select(
            company_year,
            func.count(CompanyFinancialFact.id),
            func.count(distinct(CompanyFinancialFact.ticker)),
        ).group_by(company_year)
    ):
        if year is None:
            continue
        item = period(int(year))
        item.update(
            company_facts=int(count or 0),
            company_tickers=int(ticker_count or 0),
        )

    for year, count, indicator_count, country_count in session.execute(
        select(
            EconomicObservation.year,
            func.count(),
            func.count(distinct(EconomicObservation.indicator_code)),
            func.count(distinct(EconomicObservation.country_iso3)),
        ).group_by(EconomicObservation.year)
    ):
        item = period(int(year))
        item.update(
            economic_observations=int(count or 0),
            economic_indicators=int(indicator_count or 0),
            economic_countries=int(country_count or 0),
        )

    for item in rows.values():
        news_score = min(item["full_documents"] / 20, 1.0) * 0.7 + min(
            item["news_sources"] / 3, 1.0
        ) * 0.3
        event_score = min(item["events"] / 1_000, 1.0)
        market_score = min(item["market_series"] / 40, 1.0)
        company_score = min(item["company_tickers"] / 12, 1.0)
        economic_score = min(item["economic_indicators"] / 5, 1.0) * 0.6 + min(
            item["economic_countries"] / 50, 1.0
        ) * 0.4
        domain_scores = {
            "news": news_score,
            "events": event_score,
            "market": market_score,
            "company": company_score,
            "economy": economic_score,
        }
        item["domain_scores"] = {
            key: round(value, 3) for key, value in domain_scores.items()
        }
        item["evidence_domains"] = sum(value >= 0.5 for value in domain_scores.values())
        item["coverage_score"] = round(
            news_score * 0.12
            + event_score * 0.22
            + market_score * 0.26
            + company_score * 0.22
            + economic_score * 0.18,
            3,
        )
        item["closed_period"] = item["year"] < current_year
        item["structured_ready"] = bool(
            item["closed_period"]
            and item["events"] >= 500
            and item["market_series"] >= 40
            and item["company_tickers"] >= 12
            and item["economic_indicators"] >= 3
        )
        item["cross_domain_ready"] = bool(
            item["structured_ready"]
            and item["evidence_domains"] == 5
            and item["coverage_score"] >= 0.65
        )
        item["broad_media_ready"] = bool(
            item["news_sources"] >= 50 or item["full_documents"] >= 200
        )
        item["eligible"] = bool(
            item["cross_domain_ready"] and item["broad_media_ready"]
        )
        if item["full_documents"] >= 200:
            item["media_mode"] = "rich_content"
        elif item["news_sources"] >= 50 and item["full_documents"] < 100:
            item["media_mode"] = "headline_broad"
        elif item["documents"]:
            item["media_mode"] = "sparse_content"
        else:
            item["media_mode"] = "no_retained_news"

    eligible_years = sorted(
        item["year"] for item in rows.values() if item["eligible"]
    )
    structured_years = sorted(
        item["year"] for item in rows.values() if item["structured_ready"]
    )
    cross_domain_years = sorted(
        item["year"] for item in rows.values() if item["cross_domain_ready"]
    )
    reliable_start_year = eligible_years[0] if eligible_years else None
    reliable_end_year = eligible_years[-1] if eligible_years else None
    display_start = (
        max(min(rows), structured_years[0])
        if rows and structured_years
        else (max(min(rows), current_year - 12) if rows else current_year)
    )

    displayed_periods = [
        rows[year]
        for year in range(display_start, current_year + 1)
        if year in rows
    ]
    for item in displayed_periods:
        event_start = datetime(item["year"], 1, 1, tzinfo=UTC)
        event_end = datetime(item["year"] + 1, 1, 1, tzinfo=UTC)
        samples = list(
            session.scalars(
                select(Event)
                .where(Event.start_at >= event_start, Event.start_at < event_end)
                .order_by(Event.severity.desc(), Event.confidence.desc(), Event.start_at)
                .limit(2)
            )
        )
        item["representative_events"] = [
            {
                "evidence_id": f"event:{event.id}",
                "category": "event",
                "event_type": event.event_type,
                "title": event.title[:300],
                "summary": (event.summary or "")[:500],
                "occurred_at": event.start_at.isoformat(),
                "country_code": event.country_code,
                "severity": float(event.severity),
                "confidence": float(event.confidence),
            }
            for event in samples
        ]

    media_rich_years = sorted(
        item["year"]
        for item in rows.values()
        if item["news_sources"] >= 50 or item["full_documents"] >= 200
    )
    earliest_observation_year = min(rows) if rows else None
    return {
        "generated_at": generated_at.isoformat(),
        "earliest_observation": (
            f"{earliest_observation_year:04d}-01-01"
            if earliest_observation_year is not None
            else None
        ),
        "reliable_start": (
            f"{reliable_start_year:04d}-01-01"
            if reliable_start_year is not None
            else None
        ),
        "structured_start": (
            f"{structured_years[0]:04d}-01-01" if structured_years else None
        ),
        "cross_domain_start": (
            f"{cross_domain_years[0]:04d}-01-01" if cross_domain_years else None
        ),
        "reliable_end": (
            f"{reliable_end_year:04d}-12-31"
            if reliable_end_year is not None
            else None
        ),
        "media_rich_start": (
            f"{media_rich_years[0]:04d}-01-01" if media_rich_years else None
        ),
        "current_open_period": {
            "start": f"{current_year:04d}-01-01",
            "end": generated_at.date().isoformat(),
            "eligible": False,
            "reason": "current_year_is_incomplete",
        },
        "eligible_years": eligible_years,
        "periods": displayed_periods,
        "methodology": (
            "A closed year is eligible for autonomous conclusions only when all "
            "five retained evidence domains (news, event, market, company and "
            "macroeconomic data) pass minimum thresholds and retained news has "
            "broad source or full-text coverage. Earlier cross-domain years remain "
            "comparison-only; the current partial year is monitoring-only."
        ),
    }


def select_preferred_research_period(
    event_table: dict[str, Any],
    *,
    prior_questions: list[str],
) -> dict[str, Any] | None:
    """Choose the earliest complete, not-recently-used period for the next run."""
    periods = [
        item
        for item in event_table.get("periods", [])
        if isinstance(item, dict) and item.get("eligible")
    ]
    if not periods:
        return None
    recently_used_years: set[int] = set()
    for question in prior_questions:
        # Event windows often cross New Year. Only the window's first year is the
        # selected research period; marking every mentioned year caused the next
        # complete period to be skipped.
        match = re.search(r"(?:18|19|20|21)\d{2}", question)
        if match:
            recently_used_years.add(int(match.group(0)))
    unused = [item for item in periods if item["year"] not in recently_used_years]
    pool = unused or periods
    selected = min(pool, key=lambda item: (item["year"], -item["coverage_score"]))
    return {
        "year": selected["year"],
        "start": selected["start"],
        "end": selected["end"],
        "coverage_score": selected["coverage_score"],
        "evidence_domains": selected["evidence_domains"],
        "reason": (
            "earliest_complete_unused_period"
            if unused
            else "complete_period_rotation_restarted"
        ),
    }
