"""Same-definition competitor comparison tests."""

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.competitive_evidence import (
    _metric_quality_flags,
    build_competitor_operating_comparison,
)
from app.db.base import Base
from app.db.models import CompanyFinancialFact, CompanyProfile


def _fact(
    ticker: str,
    concept: str,
    value: float,
    period_end: date,
    *,
    period_start: date | None,
) -> CompanyFinancialFact:
    return CompanyFinancialFact(
        ticker=ticker,
        taxonomy="us-gaap",
        concept=concept,
        label=concept,
        unit="USD",
        value=value,
        period_start=period_start,
        period_end=period_end,
        filed_at=period_end.replace(year=period_end.year + 1),
        form="10-K",
        fiscal_year=period_end.year,
        fiscal_period="FY",
        accession_number=f"{ticker}-{concept}-{period_end.year}",
        source_url="https://www.sec.gov/",
    )


def _quarter_fact(
    ticker: str,
    concept: str,
    value: float,
    period_end: date,
    *,
    period_start: date | None,
) -> CompanyFinancialFact:
    return CompanyFinancialFact(
        ticker=ticker,
        taxonomy="us-gaap",
        concept=concept,
        label=concept,
        unit="USD",
        value=value,
        period_start=period_start,
        period_end=period_end,
        filed_at=date(period_end.year, 11, 1),
        form="10-Q",
        fiscal_year=period_end.year,
        fiscal_period="Q3",
        accession_number=f"{ticker}-{concept}-{period_end.year}-Q3",
        source_url="https://www.sec.gov/",
    )


def test_competitor_comparison_aligns_definitions_and_ranks(tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for ticker in ("AAPL", "MSFT"):
            session.add(
                CompanyProfile(
                    ticker=ticker,
                    cik=f"{len(ticker):010d}{'1' if ticker == 'AAPL' else '2'}"[-10:],
                    name=ticker,
                    sector="Technology",
                    industry="Technology",
                    source_url="https://www.sec.gov/",
                )
            )
        for ticker, latest_revenue, prior_revenue in (
            ("AAPL", 120.0, 100.0),
            ("MSFT", 110.0, 100.0),
        ):
            for period_end, revenue in (
                (date(2024, 12, 31), prior_revenue),
                (date(2025, 12, 31), latest_revenue),
            ):
                start = date(period_end.year, 1, 1)
                session.add_all(
                    [
                        _fact(ticker, "Revenues", revenue, period_end, period_start=start),
                        _fact(ticker, "GrossProfit", revenue * 0.5, period_end, period_start=start),
                        _fact(
                            ticker,
                            "NetIncomeLoss",
                            revenue * 0.2,
                            period_end,
                            period_start=start,
                        ),
                        _fact(
                            ticker,
                            "ResearchAndDevelopmentExpense",
                            revenue * 0.1,
                            period_end,
                            period_start=start,
                        ),
                        _fact(
                            ticker,
                            "InventoryNet",
                            revenue * 0.05,
                            period_end,
                            period_start=None,
                        ),
                    ]
                )
            for period_end, revenue in (
                (date(2025, 9, 30), prior_revenue / 4),
                (date(2026, 9, 30), latest_revenue / 4),
            ):
                start = date(period_end.year, 7, 1)
                session.add_all(
                    [
                        _quarter_fact(
                            ticker,
                            "Revenues",
                            revenue,
                            period_end,
                            period_start=start,
                        ),
                        _quarter_fact(
                            ticker,
                            "GrossProfit",
                            revenue * 0.5,
                            period_end,
                            period_start=start,
                        ),
                        _quarter_fact(
                            ticker,
                            "NetIncomeLoss",
                            revenue * 0.2,
                            period_end,
                            period_start=start,
                        ),
                        _quarter_fact(
                            ticker,
                            "ResearchAndDevelopmentExpense",
                            revenue * 0.1,
                            period_end,
                            period_start=start,
                        ),
                    ]
                )
        session.commit()
        result = build_competitor_operating_comparison(
            session,
            ticker="AAPL",
            as_of=date(2027, 1, 1),
            cold_data_root=tmp_path,
        )

    assert result is not None
    rows = {row["ticker"]: row for row in result["rows"]}
    assert round(rows["AAPL"]["revenue_yoy"], 6) == 0.2
    assert round(rows["MSFT"]["revenue_yoy"], 6) == 0.1
    assert rows["AAPL"]["ranks"]["revenue_yoy"] == 1
    assert rows["MSFT"]["ranks"]["revenue_yoy"] == 2
    assert round(rows["AAPL"]["quarterly"]["revenue_yoy"], 6) == 0.2
    assert round(rows["MSFT"]["quarterly"]["revenue_yoy"], 6) == 0.1
    assert rows["AAPL"]["quarterly"]["ranks"]["revenue_yoy"] == 1
    assert rows["MSFT"]["quarterly"]["ranks"]["revenue_yoy"] == 2
    assert "fiscal year-end dates can differ" in result["limitations"][0]


def test_extreme_quarterly_ratios_are_flagged_without_being_deleted() -> None:
    flags = _metric_quality_flags(
        revenue_yoy=2.1,
        gross_margin=None,
        net_margin=0.91,
        research_intensity=None,
    )

    assert "extreme_revenue_change_review_corporate_actions" in flags
    assert "extreme_net_margin_review_one_offs" in flags
    assert "gross_margin_unavailable_in_standard_taxonomy" in flags
    assert "research_intensity_unavailable_in_standard_taxonomy" in flags
