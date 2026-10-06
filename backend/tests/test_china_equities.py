"""CSI 800 sector-leader selection and A-share storage tests."""

from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.china_equities import broad_china_sector, sync_china_equity_leaders
from app.db.base import Base
from app.db.models import MarketObservation, MarketSeries, MarketSyncState


class FakeResult:
    def __init__(self, rows: list[list[str]], fields: list[str] | None = None) -> None:
        self.error_code = "0"
        self.error_msg = "success"
        self.rows = rows
        self.fields = fields or []
        self.index = -1

    def next(self) -> bool:
        self.index += 1
        return self.index < len(self.rows)

    def get_row_data(self) -> list[str]:
        return self.rows[self.index]


class FakeBaoStock:
    def login(self) -> SimpleNamespace:
        return SimpleNamespace(error_code="0", error_msg="success")

    def logout(self) -> SimpleNamespace:
        return SimpleNamespace(error_code="0", error_msg="success")

    def query_hs300_stocks(self) -> FakeResult:
        return FakeResult(
            [
                ["2026-08-24", "sh.600001", "科技一"],
                ["2026-08-24", "sz.000002", "科技二"],
                ["2026-08-24", "sh.600003", "银行一"],
                ["2026-08-24", "sz.000004", "银行二"],
            ]
        )

    def query_zz500_stocks(self) -> FakeResult:
        return FakeResult(
            [
                ["2026-08-24", "sz.000002", "科技二"],
                ["2026-08-24", "sz.000005", "医药一"],
            ]
        )

    def query_stock_industry(self) -> FakeResult:
        return FakeResult(
            [
                ["2026-08-24", "sh.600001", "科技一", "C39计算机制造业", "证监会行业分类"],
                ["2026-08-24", "sz.000002", "科技二", "I65软件业", "证监会行业分类"],
                ["2026-08-24", "sh.600003", "银行一", "J66货币金融服务", "证监会行业分类"],
                ["2026-08-24", "sz.000004", "银行二", "J66货币金融服务", "证监会行业分类"],
                ["2026-08-24", "sz.000005", "医药一", "C27医药制造业", "证监会行业分类"],
            ]
        )

    def query_daily_history_k_AStock(self, _: str) -> FakeResult:
        fields = [
            "date",
            "code",
            "close",
            "amount",
            "tradestatus",
            "isST",
            "peTTM",
            "pbMRQ",
        ]
        return FakeResult(
            [
                ["2026-08-20", "sh.600001", "10", "500000000", "1", "0", "20", "3"],
                ["2026-08-20", "sz.000002", "10", "100000000", "1", "0", "15", "2"],
                ["2026-08-20", "sh.600003", "10", "600000000", "1", "0", "8", "1"],
                ["2026-08-20", "sz.000004", "10", "200000000", "1", "0", "12", "1.5"],
                ["2026-08-20", "sz.000005", "10", "300000000", "1", "0", "18", "2.5"],
            ],
            fields,
        )

    def query_profit_data(self, code: str, **_: int) -> FakeResult:
        values = {
            "sh.600001": ["0.10", "10", "100", "10"],
            "sz.000002": ["0.30", "100", "500", "100"],
            "sh.600003": ["0.20", "80", "400", "80"],
            "sz.000004": ["0.10", "20", "200", "20"],
            "sz.000005": ["0.18", "60", "300", "60"],
        }
        roe, profit, revenue, shares = values[code]
        fields = [
            "code",
            "pubDate",
            "statDate",
            "roeAvg",
            "netProfit",
            "MBRevenue",
            "totalShare",
        ]
        return FakeResult(
            [[code, "2026-08-15", "2026-06-30", roe, profit, revenue, shares]],
            fields,
        )

    def query_growth_data(self, code: str, **_: int) -> FakeResult:
        yoy = {
            "sh.600001": "0.05",
            "sz.000002": "0.40",
            "sh.600003": "0.20",
            "sz.000004": "0.02",
            "sz.000005": "0.16",
        }[code]
        return FakeResult(
            [[code, "2026-08-15", "2026-06-30", yoy]],
            ["code", "pubDate", "statDate", "YOYNI"],
        )

    def query_history_k_data_plus(
        self,
        code: str,
        fields: str,
        **_: str,
    ) -> FakeResult:
        amounts = {
            "sh.600001": "500000000",
            "sz.000002": "100000000",
            "sh.600003": "600000000",
            "sz.000004": "200000000",
            "sz.000005": "300000000",
        }
        if fields == "date,code,amount,tradestatus,isST":
            return FakeResult(
                [["2026-08-20", code, amounts[code], "1", "0"]]
            )
        return FakeResult(
            [
                ["2026-08-20", code, "10", "1000", amounts[code], "1.2", "1", "0"],
                ["2026-08-21", code, "11", "1200", amounts[code], "1.4", "1", "0"],
            ]
        )


def test_csrc_industries_map_to_cross_market_sectors() -> None:
    assert broad_china_sector("C39计算机制造业") == "Technology"
    assert broad_china_sector("C27医药制造业") == "Health care"
    assert broad_china_sector("C36汽车制造业") == "Automotive"
    assert broad_china_sector("J66货币金融服务") == "Financials"
    assert broad_china_sector("") is None


def test_china_equity_sync_selects_composite_leader_per_sector() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = sync_china_equity_leaders(
            session,
            history_start=date(2026, 8, 1),
            history_end=date(2026, 8, 27),
            leaders_per_sector=1,
            provider=FakeBaoStock(),
        )
        session.commit()

        assert result.universe == "CSI 300 + CSI 500 (CSI 800 proxy)"
        assert result.candidates_scanned == 5
        assert result.sectors == 3
        assert {leader.provider_code for leader in result.leaders} == {
            "sz.000002",
            "sh.600003",
            "sz.000005",
        }
        assert session.scalar(select(func.count()).select_from(MarketSeries)) == 36
        assert session.scalar(select(func.count()).select_from(MarketObservation)) == 48
        assert session.get(MarketSeries, "CN:000002").sector == "Technology"
        assert session.get(MarketSeries, "CNAMT:600003").category == "equity_turnover"
        assert session.get(MarketSeries, "CNSCORE:000002").category == "equity_factor"
        assert session.get(MarketSeries, "CNSCORE:000002").frequency == "snapshot"
        assert session.get(MarketSeries, "CN:000005").sector == "Health care"
        assert session.get(MarketSeries, "CN:000005").neutralization_group == "csrc:C27医药制造业"
        assert result.leaders[0].composite_score > 0
        state = session.get(MarketSyncState, "baostock_china_leaders")
        assert state is not None
        assert state.series_synced == 3
        assert state.observations_upserted == 48
    engine.dispose()
