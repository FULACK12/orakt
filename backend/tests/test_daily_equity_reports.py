from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.daily_equity_reports import schedule_daily_equity_reports
from app.db import models as _models  # noqa: F401
from app.db.base import Base
from app.db.models import CompanyFiling, CompanyProfile, ResearchInquiry


def test_daily_rotation_prefers_company_without_a_report(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime(2026, 9, 13, 12, tzinfo=UTC)
    captured = {}

    def fake_create(session, *, request):
        captured["request"] = request
        return SimpleNamespace(id=9, target_count=len(request.tickers or []))

    monkeypatch.setattr("app.daily_equity_reports.create_equity_research_batch", fake_create)
    with Session(engine, expire_on_commit=False) as session:
        for index, ticker in enumerate(("AAPL", "MSFT"), start=1):
            session.add(
                CompanyProfile(
                    ticker=ticker,
                    cik=f"{index:010d}",
                    name=ticker,
                    sector="Technology",
                    industry="Software",
                    source_url="https://example.com",
                )
            )
        session.add(
            ResearchInquiry(
                question="MSFT report",
                mode="user_question",
                status="completed",
                local_model="test",
                result={},
                evidence_snapshot={
                    "equity_research_context": {
                        "market_region": "us",
                        "ticker": "MSFT",
                    }
                },
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()

        result = schedule_daily_equity_reports(session, budget=1, now=now)

    assert result["status"] == "queued"
    assert result["selected"] == ["us:AAPL"]
    assert captured["request"].tickers == ["AAPL"]
    assert result["estimated_gpu_minutes"] == 4.0


def test_daily_rotation_prioritizes_new_filing_without_consuming_rotation_budget(
    monkeypatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime(2026, 9, 13, 12, tzinfo=UTC)
    captured = {}

    def fake_create(session, *, request):
        captured["request"] = request
        return SimpleNamespace(id=91, target_count=len(request.tickers or []))

    monkeypatch.setattr("app.daily_equity_reports.create_equity_research_batch", fake_create)
    with Session(engine, expire_on_commit=False) as session:
        for index, ticker in enumerate(("AAPL", "MSFT"), start=1):
            session.add(
                CompanyProfile(
                    ticker=ticker,
                    cik=f"{index:010d}",
                    name=ticker,
                    sector="Technology",
                    industry="Software",
                    source_url="https://example.com",
                )
            )
        session.add(
            ResearchInquiry(
                question="AAPL old report",
                mode="user_question",
                status="completed",
                local_model="test",
                result={},
                evidence_snapshot={
                    "equity_research_context": {"market_region": "us", "ticker": "AAPL"}
                },
                created_at=datetime(2026, 9, 1, tzinfo=UTC),
                updated_at=datetime(2026, 9, 1, tzinfo=UTC),
            )
        )
        session.add(
            CompanyFiling(
                accession_number="0000000000-26-000001",
                ticker="AAPL",
                form="10-Q",
                filed_at=date(2026, 9, 10),
                source_url="https://example.com/filing",
            )
        )
        session.commit()

        result = schedule_daily_equity_reports(
            session,
            budget=1,
            event_budget=1,
            now=now,
        )

    assert result["status"] == "queued"
    assert result["triggered_targets"] == 1
    assert result["rotation_targets"] == 1
    assert result["selected"] == ["us:AAPL", "us:MSFT"]
    assert result["trigger_reasons"]["us:AAPL"][0]["kind"] == "new_official_filing"
    assert captured["request"].tickers == ["AAPL", "MSFT"]
