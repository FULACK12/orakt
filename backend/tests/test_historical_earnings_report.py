"""Earliest complete date-level evidence selection, without a model/network."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import CompanyFiling, CompanyFinancialFact, CompanyProfile
from app.historical_earnings_report import FilingText, build_packet, excerpts, validate_citations


def test_text_removes_hidden_markup():
    parser = FilingText()
    parser.feed("<ix:header>hidden</ix:header><script>bad</script><p>Visible &amp; facts</p>")
    assert parser.clean() == "Visible & facts"


def test_excerpts_deterministic_bounded_and_locatable():
    text = "a" * 20000 + "Item 2. Management discussion" + "b" * 20000
    for item in excerpts(text):
        assert item["text"] == text[item["start"] : item["end"]]
    assert sum(len(x["text"]) for x in excerpts(text)) <= 27000


def test_unknown_citations_fail_closed():
    validate_citations({"evidence_refs": ["SEC:fixture"]}, {"SEC:fixture"})
    with pytest.raises(ValueError):
        validate_citations({"nested": [{"evidence_refs": ["invented"]}]}, {"SEC:fixture"})
    with pytest.raises(ValueError):
        validate_citations({"finding": "Unsupported FACT:999"}, {"FACT:1"})


def test_standalone_historical_report_visible_in_market_catalog():
    from app.db.base import Base
    from app.db.models import ResearchInquiry
    from app.research import list_research_inquiry_summaries

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            ResearchInquiry(
                question="AAPL historical report",
                mode="user_question",
                status="completed",
                local_model="fixture",
                result={"fixture": True},
                evidence_snapshot={
                    "equity_context": {
                        "ticker": "AAPL",
                        "market_region": "us",
                        "company_name": "Apple",
                    }
                },
            )
        )
        session.flush()
        rows, total = list_research_inquiry_summaries(
            session, page=1, page_size=10, market_region="us", search="AAPL"
        )
        assert total == 1 and rows[0].ticker == "AAPL"
    engine.dispose()


def test_earliest_complete_not_earliest_title_no_later_facts(tmp_path):
    engine = create_engine("sqlite://")
    for model in (CompanyProfile, CompanyFiling, CompanyFinancialFact):
        model.__table__.create(engine)
    with Session(engine) as session:
        for acc, filed in [
            ("old", date(2000, 1, 1)),
            ("complete", date(2025, 8, 1)),
            ("later", date(2026, 8, 1)),
        ]:
            session.add(
                CompanyFiling(
                    accession_number=acc,
                    ticker="AAPL",
                    form="10-Q",
                    filed_at=filed,
                    report_date=date(filed.year, 6, 28),
                    primary_document="report.htm",
                    source_url="https://www.sec.gov/fixture",
                )
            )
        directory = tmp_path / "raw/sec/company-filings/AAPL/complete"
        directory.mkdir(parents=True)
        (directory / "report.htm").write_text("<p>" + "real body fixture " * 400 + "</p>")
        for index in range(12):
            session.add(
                CompanyFinancialFact(
                    ticker="AAPL",
                    accession_number="complete",
                    taxonomy="fixture",
                    concept=f"fact{index}",
                    label="fixture",
                    unit="USD",
                    value=1,
                    period_end=date(2025, 6, 28),
                    filed_at=date(2025 if index < 10 else 2026, 8, 1),
                    form="10-Q",
                    source_url="https://www.sec.gov/fixture",
                )
            )
        session.commit()
        packet = build_packet(session, ticker="AAPL", cold_root=tmp_path)
        assert packet["accession"] == "complete" and len(packet["facts"]) == 10
        assert packet["date_precision"] == "day"
        assert packet["older_filings_without_sufficient_local_body_or_facts"] == 1
        filing = session.get(CompanyFiling, "complete")
        filing.form = "10-K"
        session.commit()
        annual = build_packet(session, ticker="AAPL", cold_root=tmp_path, accession="complete")
        assert annual["accession"] == "complete"
        with pytest.raises(ValueError):
            build_packet(session, ticker="AAPL", cold_root=tmp_path, accession="old")
    engine.dispose()
