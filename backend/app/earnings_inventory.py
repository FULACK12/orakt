"""Read-only inventory of retained filings; never infer earnings release clocks."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import CompanyFiling, CompanyFinancialFact, FilingTimingObservation


def earnings_inventory(
    session: Session, tickers: tuple[str, ...] = ("AAPL", "NVDA", "AMD")
) -> dict:
    items = []
    for ticker in tickers:
        filings = session.execute(
            select(
                CompanyFiling.form,
                func.count(),
                func.min(CompanyFiling.filed_at),
                func.max(CompanyFiling.filed_at),
            )
            .where(CompanyFiling.ticker == ticker)
            .group_by(CompanyFiling.form)
        ).all()
        latest = session.scalar(
            select(CompanyFiling)
            .where(
                CompanyFiling.ticker == ticker,
                CompanyFiling.form == "10-Q",
            )
            .order_by(CompanyFiling.filed_at.desc(), CompanyFiling.accession_number.desc())
            .limit(1)
        )
        facts = session.scalar(
            select(func.count())
            .select_from(CompanyFinancialFact)
            .where(
                CompanyFinancialFact.ticker == ticker,
            )
        )
        timing_count = session.scalar(
            select(func.count(func.distinct(FilingTimingObservation.accession_number)))
            .join(
                CompanyFiling,
                CompanyFiling.accession_number == FilingTimingObservation.accession_number,
            )
            .where(CompanyFiling.ticker == ticker, FilingTimingObservation.accepted_at.is_not(None))
        )
        items.append(
            {
                "ticker": ticker,
                "financial_fact_count": facts,
                "filings_with_sec_acceptance_time": timing_count,
                "sec_acceptance_is_earnings_release": False,
                "filings": [
                    {
                        "form": form,
                        "count": count,
                        "first_filed_on": first.isoformat(),
                        "last_filed_on": last.isoformat(),
                    }
                    for form, count, first, last in filings
                ],
                "latest_10q": None
                if latest is None
                else {
                    "accession_number": latest.accession_number,
                    "filed_on": latest.filed_at.isoformat(),
                    "report_period_end": latest.report_date.isoformat()
                    if latest.report_date
                    else None,
                    "source_url": latest.source_url,
                },
                "stageable": False,
                "blockers": [
                    "issuer_earnings_release_clock_not_verified",
                    "evidence_version_availability_timestamps_not_verified",
                    "trading_session_cutoffs_not_verified",
                ]
                + ([] if latest else ["no_retained_10q"]),
            }
        )
    return {"read_only": True, "execution_permitted": False, "companies": items}
