"""Inventory must not manufacture release times from date-only SEC records."""

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import CompanyFiling, CompanyFinancialFact, FilingTimingObservation
from app.earnings_inventory import earnings_inventory


def test_date_only_inventory_remains_blocked_and_does_not_write():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CompanyFiling.__table__.create(engine)
    CompanyFinancialFact.__table__.create(engine)
    FilingTimingObservation.__table__.create(engine)
    with Session(engine) as session:
        session.add(
            CompanyFiling(
                accession_number="synthetic-1",
                ticker="TEST",
                form="10-Q",
                filed_at=date(2025, 4, 1),
                report_date=date(2025, 3, 31),
                source_url="https://example.com/filing",
            )
        )
        session.commit()
        result = earnings_inventory(session, ("TEST", "MISSING"))
        assert result["read_only"] is True
        assert result["execution_permitted"] is False
        assert result["companies"][0]["filings"][0]["count"] == 1
        assert result["companies"][0]["latest_10q"]["filed_on"] == "2025-04-01"
        assert result["companies"][0]["stageable"] is False
        assert result["companies"][0]["filings_with_sec_acceptance_time"] == 0
        assert result["companies"][0]["sec_acceptance_is_earnings_release"] is False
        assert "no_retained_10q" in result["companies"][1]["blockers"]
        assert not session.new and not session.dirty and not session.deleted
    engine.dispose()
