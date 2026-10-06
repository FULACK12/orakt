"""End-to-end checks for the retained-data audit report."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.data_audit import build_data_audit_report
from app.db.base import Base
from app.db.models import CompanyProfile, MarketObservation, MarketSeries


def test_data_audit_groups_equities_and_exposes_rejected_price_series() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    today = date.today()
    with Session(engine) as session:
        session.add(
            CompanyProfile(
                ticker="AAPL",
                cik="0000320193",
                name="Apple Inc.",
                sector="Technology",
                industry="Consumer electronics",
                source_url="https://www.sec.gov/edgar/browse/?CIK=320193",
            )
        )
        session.add_all(
            [
                MarketSeries(
                    series_id="EQ:AAPL",
                    name="Apple Inc. split-adjusted close",
                    category="equity_price",
                    unit="USD",
                    frequency="daily",
                    source_name="Twelve Data",
                    source_url="https://twelvedata.com/docs",
                    sector="Technology",
                    region="united_states",
                ),
                MarketSeries(
                    series_id="CN:600001",
                    name="测试科技 (600001) 前复权收盘价",
                    category="equity_price",
                    unit="CNY",
                    frequency="daily",
                    source_name="BaoStock",
                    source_url="https://www.baostock.com/",
                    sector="Technology",
                    region="china",
                ),
                MarketSeries(
                    series_id="CNAMT:600001",
                    name="测试科技 (600001) 成交额",
                    category="equity_turnover",
                    unit="CNY",
                    frequency="daily",
                    source_name="BaoStock",
                    source_url="https://www.baostock.com/",
                    sector="Technology",
                    region="china",
                ),
                MarketSeries(
                    series_id="COAL:BAD",
                    name="Broken steam coal price",
                    category="commodity_price",
                    unit="USD",
                    frequency="daily",
                    source_name="Fixture",
                    source_url="https://example.test/coal",
                ),
                MarketSeries(
                    series_id="CNSCORE:600001",
                    name="测试科技 (600001) 行业龙头综合分",
                    category="equity_factor",
                    unit="score_0_100",
                    frequency="snapshot",
                    source_name="BaoStock",
                    source_url="https://www.baostock.com/",
                    sector="Technology",
                    region="china",
                ),
            ]
        )
        session.add(
            MarketObservation(
                series_id="CNSCORE:600001",
                observed_on=today,
                value=82.5,
                fetched_at=datetime.now(UTC),
            )
        )
        for index in range(60):
            observed_on = today - timedelta(days=59 - index)
            session.add_all(
                [
                    MarketObservation(
                        series_id="EQ:AAPL",
                        observed_on=observed_on,
                        value=150 + index,
                        fetched_at=datetime.now(UTC),
                    ),
                    MarketObservation(
                        series_id="CN:600001",
                        observed_on=observed_on,
                        value=10 + index / 10,
                        fetched_at=datetime.now(UTC),
                    ),
                    MarketObservation(
                        series_id="CNAMT:600001",
                        observed_on=observed_on,
                        value=100_000_000 + index,
                        fetched_at=datetime.now(UTC),
                    ),
                    MarketObservation(
                        series_id="COAL:BAD",
                        observed_on=observed_on,
                        value=0,
                        fetched_at=datetime.now(UTC),
                    ),
                ]
            )
        session.flush()

        report = build_data_audit_report(session, persist=False)

        assert report.market_series_count == 5
        assert report.market_observation_count == 241
        assert report.china_leader_count == 1
        assert report.us_equity_count == 1
        assert report.china_sector_leaders["Technology"][0].symbol == "600001"
        assert report.us_sector_equities["Technology"][0].symbol == "AAPL"
        assert report.fulltext_backlog.headline_only_count == 0
        coal = next(item for item in report.abnormal_series if item.series_id == "COAL:BAD")
        assert coal.can_verify_claims is False
        assert "invalid_or_nonpositive_price_values" in coal.flags
        assert all(item.series_id != "CNSCORE:600001" for item in report.abnormal_series)
    engine.dispose()
