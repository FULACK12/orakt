"""Question-specific public-equity evidence engineering tests."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.companies import seed_company_catalog
from app.db.base import Base
from app.db.enums import SourceType
from app.db.models import (
    CompanyFinancialFact,
    CompanyProfile,
    Document,
    MarketDailyBar,
    MarketObservation,
    MarketSeries,
    Source,
)
from app.equity_research import (
    _company_document_evidence,
    _china_equity_data_readiness,
    _equity_data_readiness,
    _financial_trend_snapshot,
    _growth_rate,
    _latest_valuation_basis,
    _preferred_revenue_fact,
    _question_target_prices,
    _technical_snapshot,
    _valuation_snapshot,
    build_equity_research_pack,
    detect_company_ticker,
)
from app.research import (
    _complete_equity_dimensions,
    _ensure_equity_subject_grounding,
    _fallback_equity_framework,
    _net_income_trend_text,
    _sanitize_research_result,
)
from app.research_evidence import _search_terms, _selected_market_series
from app.schemas.research import ModelEquityResearchDimension, ModelResearchResult


def test_explicit_long_ticker_beats_incidental_short_company_tokens() -> None:
    profiles = [
        CompanyProfile(
            ticker="T",
            cik="0000732717",
            name="AT&T Inc.",
            sector="Communication",
            industry="Telecommunications",
            source_url="https://www.sec.gov/edgar/browse/?CIK=732717",
        ),
        CompanyProfile(
            ticker="LULU",
            cik="0001397187",
            name="lululemon athletica inc.",
            sector="Consumer",
            industry="Athletic apparel and footwear",
            source_url="https://www.sec.gov/edgar/browse/?CIK=1397187",
        ),
    ]

    question = "lululemon athletica inc.（LULU）未来6至12个月的盈利是否获得证据支持？"

    assert detect_company_ticker(question, profiles) == "LULU"
    assert detect_company_ticker("AT&T（T）未来一年的现金流如何？", profiles) == "T"


def test_negative_profit_base_is_described_as_loss_change_not_growth() -> None:
    assert _growth_rate(-267.0, -18_756.0) is None
    assert (
        _net_income_trend_text(
            [
                {"net_income": -18_756_000_000.0},
                {"net_income": -267_000_000.0, "net_income_yoy": None},
            ]
        )
        == "净亏损由 18.76 十亿美元收窄至 267.00 百万美元"
    )


def test_technical_snapshot_exports_chart_and_bounded_risk_reward_scenario() -> None:
    start = date(2026, 1, 2)
    rows = [
        (start + timedelta(days=index), 180 + index * 0.18 + (index % 7 - 3) * 0.7)
        for index in range(220)
    ]

    snapshot = _technical_snapshot("AAPL", rows)

    assert snapshot is not None
    assert len(snapshot["chart_points"]) == 90
    assert snapshot["chart_points"][-1]["date"] == rows[-1][0].isoformat()
    assert snapshot["chart_points"][-1]["close"] == rows[-1][1]
    assert snapshot["chart_points"][-1]["sma_20"] is not None
    scenario = snapshot["risk_reward"]
    assert scenario["entry_reference"] == rows[-1][1]
    assert scenario["stop_reference"] < scenario["entry_reference"]
    assert scenario["target_reference"] > scenario["entry_reference"]
    assert scenario["downside_fraction"] > 0
    assert scenario["upside_fraction"] > 0
    assert scenario["reward_risk_ratio"] > 0
    assert "not a recommendation" in scenario["interpretation"]
    horizons = snapshot["horizon_models"]
    assert horizons["version"] == "entry_horizon_walk_forward_v1"
    assert [item["key"] for item in horizons["models"]] == [
        "ultra_short",
        "swing",
        "medium",
        "long_value",
    ]
    assert horizons["models"][0]["parameters"]["transaction_cost_bps"] == 10.0
    assert horizons["models"][0]["validation"]["train_end_date"] is not None
    assert "close t+1" in horizons["models"][0]["validation"]["leakage_guard"]
    assert horizons["models"][3]["fundamental_gate"]["required"] is True
    assert horizons["models"][3]["fundamental_gate"]["passed"] is False


def test_technical_snapshot_prefers_ohlcv_atr_and_volume() -> None:
    start = date(2026, 1, 2)
    bars = []
    for index in range(220):
        close = 180 + index * 0.18 + (index % 7 - 3) * 0.7
        open_price = close - (0.6 if index % 2 else -0.4)
        bars.append(
            MarketDailyBar(
                series_id="EQ:AAPL",
                observed_on=start + timedelta(days=index),
                open_price=open_price,
                high_price=max(open_price, close) + 1.2,
                low_price=min(open_price, close) - 1.1,
                close_price=close,
                volume=1_000_000 + index * 2_000,
                adjustment="splits",
                source_name="Twelve Data",
                source_url="https://twelvedata.com/docs",
                fetched_at=datetime(2026, 8, 31, tzinfo=UTC),
            )
        )
    rows = [(item.observed_on, item.close_price) for item in bars]

    snapshot = _technical_snapshot("AAPL", rows, daily_bars=bars)

    assert snapshot is not None
    assert snapshot["bar_data_status"] == "complete_ohlcv"
    assert snapshot["atr_14"] > 0
    assert snapshot["average_volume_20"] > 0
    assert snapshot["volume_ratio_20"] > 0
    assert snapshot["kdj_k"] is not None
    assert snapshot["kdj_close_proxy_k"] is None
    assert snapshot["chart_points"][-1]["open"] == bars[-1].open_price
    assert snapshot["chart_points"][-1]["high"] == bars[-1].high_price
    assert snapshot["chart_points"][-1]["low"] == bars[-1].low_price
    assert snapshot["chart_points"][-1]["volume"] == bars[-1].volume
    assert snapshot["price_structure"]["method"].startswith("split_adjusted_ohlcv")
    assert "ATR14" in snapshot["risk_reward"]["stop_basis"]
    assert (
        snapshot["risk_reward"]["target_reference"] - snapshot["risk_reward"]["entry_reference"]
        >= 0.25 * snapshot["atr_14"]
    )


def test_equity_data_readiness_blocks_direction_without_complete_ohlcv() -> None:
    readiness = _equity_data_readiness(
        technical={
            "observations": 520,
            "bar_data_status": "close_only_fallback",
        },
        financial_trend={"periods": 5},
        filing_count=12,
        company_document_count=6,
        product_operating_evidence_count=6,
        product_operating_actual_count=4,
        institutional_evidence_count=3,
        insider_evidence_count=2,
        macro_sensitivity={"sensitivities": []},
        verified_supply_chain_edge_total=3,
        supplier_market_factor_count=1,
        supply_chain_site_count=1,
    )

    assert readiness["score"] > 0.75
    assert readiness["status"] == "evidence_gap_report_only"
    assert readiness["directional_conclusion_allowed"] is False
    assert readiness["hard_gates"]["daily_ohlcv"] is False
    assert "daily_ohlcv" in readiness["missing_required"]
    assert readiness["confidence_cap"] <= 0.55


def test_equity_data_readiness_allows_conditional_research_when_gates_pass() -> None:
    readiness = _equity_data_readiness(
        technical={"observations": 520, "bar_data_status": "complete_ohlcv"},
        financial_trend={"periods": 5},
        filing_count=12,
        company_document_count=6,
        product_operating_evidence_count=6,
        product_operating_actual_count=4,
        institutional_evidence_count=3,
        insider_evidence_count=2,
        macro_sensitivity={"sensitivities": []},
        verified_supply_chain_edge_total=3,
        supplier_market_factor_count=1,
        supply_chain_site_count=1,
    )

    assert readiness["score"] == 1
    assert readiness["status"] == "full_research_ready"
    assert readiness["directional_conclusion_allowed"] is True
    assert readiness["missing_required"] == []


def test_a_share_data_readiness_scores_each_evidence_class_without_inventing_coverage() -> None:
    readiness = _china_equity_data_readiness(
        technical={"observations": 520, "bar_data_status": "close_only_fallback"},
        snapshot_count=8,
        company_document_count=12,
        periodic_report_count=6,
        structured_financial_metric_count=0,
        shareholder_document_count=5,
        shareholder_excerpt_count=0,
        operating_document_count=4,
        operating_excerpt_count=3,
        supply_chain_document_count=3,
        supply_chain_excerpt_count=2,
        macro_sensitivity={"sensitivities": []},
    )

    assert readiness["version"] == "a_share_data_readiness_v1"
    assert 0 < readiness["score"] < 1
    assert readiness["directional_conclusion_allowed"] is False
    assert readiness["confidence_cap"] <= 0.55
    assert "structured_financials" in readiness["missing_required"]
    components = {item["key"]: item for item in readiness["components"]}
    assert components["latest_fundamental_snapshot"]["score"] == 0.55
    assert components["structured_financials"]["score"] == 0
    assert components["ownership_evidence"]["status"] == "partial"


def test_a_share_data_readiness_allows_only_complete_conditional_research() -> None:
    readiness = _china_equity_data_readiness(
        technical={"observations": 520, "bar_data_status": "complete_ohlcv"},
        snapshot_count=8,
        company_document_count=12,
        periodic_report_count=6,
        structured_financial_metric_count=12,
        shareholder_document_count=5,
        shareholder_excerpt_count=5,
        operating_document_count=5,
        operating_excerpt_count=5,
        supply_chain_document_count=5,
        supply_chain_excerpt_count=5,
        macro_sensitivity={"sensitivities": []},
    )

    assert readiness["score"] >= 0.9
    assert readiness["directional_conclusion_allowed"] is True
    assert readiness["missing_required"] == []


def test_aapl_sanitizer_removes_cross_industry_factors_and_forecasts() -> None:
    result = ModelResearchResult.model_validate(
        {
            "question": "Apple AAPL未来6至12个月的条件链是否获得证据支持?",
            "summary": "Apple的方向取决于盈利、估值和产品需求。",
            "hypotheses": [
                {
                    "title": "Apple多因子条件链",
                    "premise": "AAPL当前价格和财务可观测。",
                    "outcome": "AAPL未来方向仍需验证。",
                    "scope": {
                        "companies": ["Apple Inc."],
                        "sectors": ["Technology"],
                        "products": ["iPhone"],
                        "supply_chain_inputs": [],
                        "infrastructure": [],
                        "policies": [],
                        "geographies": [],
                    },
                    "steps": [
                        {
                            "sequence": 1,
                            "label": "AAPL技术状态可由点时价格验证。",
                            "status": "verified",
                            "confidence": 0.6,
                            "evidence_refs": ["derived:technical:AAPL"],
                        },
                        {
                            "sequence": 2,
                            "label": "Apple产品需求仍需全文和公司披露验证。",
                            "status": "evidence_missing",
                            "confidence": 0.2,
                            "evidence_refs": [],
                        },
                        {
                            "sequence": 3,
                            "label": "AAPL未来方向仍是待验证假设。",
                            "status": "hypothesis",
                            "confidence": 0.2,
                            "evidence_refs": [],
                        },
                    ],
                    "counterarguments": [],
                    "evidence_gaps": [],
                    "confidence": 0.5,
                }
            ],
            "suggested_next_questions": ["AAPL产品需求是否改善?"],
            "factor_candidates": [
                {
                    "factor_id": "bad:ev:copper",
                    "name": "Copper Price Index",
                    "factor_type": "economic",
                    "direction": "negative",
                    "transformation": "change",
                    "lag_days": 30,
                    "hypothesis": "Copper prices reduce EV manufacturer margins.",
                    "evidence_refs": [],
                    "confidence": 0.4,
                },
                {
                    "factor_id": "good:aapl:technical",
                    "name": "AAPL technical state",
                    "factor_type": "market",
                    "direction": "regime_dependent",
                    "transformation": "rolling_zscore",
                    "lag_days": 0,
                    "hypothesis": "AAPL momentum is conditional, not a buy signal.",
                    "evidence_refs": ["derived:technical:AAPL"],
                    "confidence": 0.5,
                },
            ],
            "news_forecasts": [
                {
                    "forecast_id": "forecast:bad",
                    "anchor_evidence_ref": "document:1",
                    "anchor_title": "Chinese bank update",
                    "as_of": "2026-08-20T00:00:00Z",
                    "hypothesis": "Copper prices may pressure Chinese EV makers.",
                    "mechanism_chain": ["Copper rises", "EV margins fall"],
                    "expected_outcome": "EV equities decline.",
                    "horizon_days": 90,
                    "falsification_conditions": ["EV margins do not fall."],
                    "confidence": 0.4,
                },
                {
                    "forecast_id": "forecast:good",
                    "anchor_evidence_ref": "document:2",
                    "anchor_title": "Apple product event",
                    "as_of": "2026-08-21T00:00:00Z",
                    "hypothesis": "Apple product demand may alter AAPL estimates.",
                    "mechanism_chain": ["Apple demand changes", "AAPL estimates change"],
                    "expected_outcome": "AAPL valuation expectations change.",
                    "horizon_days": 90,
                    "falsification_conditions": ["Apple estimates remain unchanged."],
                    "confidence": 0.4,
                },
            ],
        }
    )
    evidence = {
        "equity_research_context": {
            "market_region": "us",
            "ticker": "AAPL",
            "company": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer electronics",
            "point_in_time_cutoff": "2026-08-27",
            "reviewed_search_plan_not_evidence": {"products": ["iPhone", "Services"]},
        },
        "derived_equity_evidence": [
            {
                "evidence_id": "derived:technical:AAPL",
                "category": "derived_market_technical",
                "ticker": "AAPL",
                "observed_on": "2026-08-27",
                "adjusted_close": 314.58,
                "sma_20": 309.0,
                "sma_50": 312.0,
                "sma_200": 282.0,
                "rsi_14": 51.57,
                "macd_histogram": 0.42,
                "return_21d": -0.07,
                "drawdown_from_52_week_high": -0.075,
            }
        ],
        "news_forecast_anchors": [
            {
                "evidence_id": "document:1",
                "title": "Chinese bank update",
                "excerpt": "A bank discussed electric vehicles and copper.",
                "published_at": "2026-08-20T00:00:00Z",
                "evidence_tier": "full_text",
            },
            {
                "evidence_id": "document:2",
                "title": "Apple product event",
                "excerpt": "Apple discussed iPhone demand and its services business.",
                "published_at": "2026-08-21T00:00:00Z",
                "evidence_tier": "full_text",
            },
        ],
    }

    sanitized = _sanitize_research_result(result, evidence=evidence)

    assert [item.factor_id for item in sanitized.factor_candidates] == ["good:aapl:technical"]
    assert [item.forecast_id for item in sanitized.news_forecasts] == ["forecast:good"]
    repairs = evidence["local_report_repairs"]
    assert any(item["section"] == "factor_candidates" for item in repairs)
    assert any(item["section"] == "news_forecasts" for item in repairs)


def test_micron_question_builds_five_lens_technical_and_valuation_context() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_company_catalog(session)
        session.add_all(
            [
                MarketSeries(
                    series_id="EQ:MU",
                    name="Micron adjusted daily close",
                    category="company_equity",
                    unit="USD",
                    frequency="daily",
                    source_name="Twelve Data",
                    source_url="https://twelvedata.com/",
                ),
                MarketSeries(
                    series_id="DGS10",
                    name="10-Year Treasury Constant Maturity Rate",
                    category="treasury_yield",
                    unit="percent",
                    frequency="daily",
                    source_name="FRED",
                    source_url="https://fred.stlouisfed.org/series/DGS10",
                ),
                MarketSeries(
                    series_id="HISTSEC:MU:old",
                    name="Historical SEC proxy with a misleading source match",
                    category="historical_equity_price",
                    unit="USD",
                    frequency="weekly",
                    source_name="SEC EDGAR",
                    source_url="https://www.sec.gov/",
                ),
            ]
        )
        start = date(2025, 1, 2)
        session.add_all(
            [
                MarketObservation(
                    series_id="EQ:MU",
                    observed_on=start + timedelta(days=index),
                    value=90 + index * 0.2,
                    fetched_at=datetime(2026, 8, 2, tzinfo=UTC),
                )
                for index in range(260)
            ]
        )
        session.add_all(
            [
                MarketObservation(
                    series_id="DGS10",
                    observed_on=start + timedelta(days=index),
                    value=4 + ((index % 7) - 3) * 0.01 + index * 0.0001,
                    fetched_at=datetime(2026, 8, 2, tzinfo=UTC),
                )
                for index in range(260)
            ]
        )
        session.add_all(
            [
                _fact("CommonStockSharesOutstanding", "shares", 1_100_000_000),
                _fact("Revenues", "USD", 35_000_000_000),
                _fact("NetIncomeLoss", "USD", 8_000_000_000),
                _fact("EarningsPerShareDiluted", "USD/shares", 7.2),
            ]
        )
        session.commit()

        question = "截至2026-08-26, 美光的股价会涨吗? 700美元是否合理, 2Y/10Y美债收益率有何影响?"
        context, evidence = build_equity_research_pack(
            session,
            question=question,
        )
        selected_market = _selected_market_series(
            session,
            terms=_search_terms(question),
            required_refs=[],
        )
        targeted_market = _selected_market_series(
            session,
            terms=_search_terms("美光 电力 流动性"),
            required_refs=[],
            target_series_id="EQ:MU",
        )

    assert context is not None
    assert context["ticker"] == "MU"
    assert len(context["required_dimensions"]) == 5
    assert context["financial_trend_status"] == "point_in_time_annual_trend_available"
    assert context["macro_sensitivity_status"] == "descriptive_aligned_changes_available"
    technical = next(item for item in evidence if item["category"] == "derived_market_technical")
    valuation = next(item for item in evidence if item["category"] == "derived_company_valuation")
    trend = next(item for item in evidence if item["category"] == "derived_company_financial_trend")
    macro = next(item for item in evidence if item["category"] == "derived_macro_sensitivity")
    assert technical["macd_12_26"] is not None
    assert technical["rsi_14"] is not None
    assert valuation["question_price_scenarios"][0]["target_price"] == 700
    assert valuation["question_price_scenarios"][0]["implied_market_cap"] > 0
    assert trend["periods"][-1]["fiscal_year"] == 2025
    assert macro["sensitivities"][0]["series_id"] == "DGS10"
    assert macro["sensitivities"][0]["sample_size"] >= 250
    assert selected_market[:2] == ["EQ:MU", "DGS10"]
    assert "HISTSEC:MU:old" not in selected_market
    assert targeted_market[0] == "EQ:MU"
    assert not any(item.startswith("CN:") for item in targeted_market)
    generic = ModelResearchResult.model_validate(
        {
            "question": question,
            "summary": "Treasury yields may affect technology valuations.",
            "hypotheses": [
                {
                    "title": "Generic technology valuation",
                    "premise": "Rates changed.",
                    "outcome": "Valuations may change.",
                    "scope": {
                        "companies": [],
                        "sectors": ["Technology"],
                        "products": [],
                        "supply_chain_inputs": [],
                        "infrastructure": [],
                        "policies": [],
                        "geographies": [],
                    },
                    "steps": [
                        {
                            "sequence": index,
                            "label": label,
                            "status": "evidence_missing",
                            "confidence": 0.2,
                            "evidence_refs": [],
                        }
                        for index, label in enumerate(
                            ("财务数据", "市场指标", "行业竞争"),
                            start=1,
                        )
                    ],
                    "counterarguments": [],
                    "evidence_gaps": [],
                    "confidence": 0.2,
                }
            ],
            "suggested_next_questions": [],
        }
    )
    evidence.extend(
        [
            {
                "evidence_id": f"site:MU:{index}",
                "category": "supply_chain_site_exposure",
            }
            for index in range(6)
        ]
        + [
            {
                "evidence_id": f"edge:MU:{index}",
                "category": "verified_supply_chain_edge",
            }
            for index in range(6)
        ]
        + [
            {
                "evidence_id": f"factor:MU:{index}",
                "category": "derived_supplier_factor",
            }
            for index in range(4)
        ]
        + [
            {
                "evidence_id": "product-operating:MU:filing:dram",
                "category": "product_operating_evidence",
                "product": "DRAM",
                "metric_name": "reported DRAM revenue",
                "evidence_status": "reported_actual",
                "reported_values": ["$28.58 billion"],
            }
        ]
    )
    _ensure_equity_subject_grounding(
        generic,
        evidence={
            "equity_research_context": context,
            "derived_equity_evidence": evidence,
        },
    )
    assert "700美元是上涨估值情景" in generic.summary
    assert "MU" in generic.hypotheses[0].title
    assert generic.hypotheses[0].title.endswith("多因子条件链")
    assert generic.paper_report is not None
    assert "MU" in generic.paper_report.title
    assert generic.paper_report.title.endswith("五维点时证据研究")
    assert any(
        "product-operating:MU:filing:dram" in step.evidence_refs
        for step in generic.hypotheses[0].steps
    )
    assert (
        max(
            len(step.evidence_refs)
            for hypothesis in generic.hypotheses
            for step in hypothesis.steps
        )
        <= 10
    )
    engine.dispose()


def test_omitted_model_dimension_is_preserved_as_evidence_insufficient() -> None:
    existing = ModelEquityResearchDimension(
        dimension="fundamentals_valuation",
        assessment="Fundamentals are mixed.",
        signal="mixed",
        confidence=0.5,
        evidence_refs=["derived:valuation:MU"],
        evidence_gaps=[],
    )
    completed = _complete_equity_dimensions(
        [existing],
        evidence={
            "derived_equity_evidence": [
                {
                    "evidence_id": "derived:valuation:MU",
                    "category": "derived_company_valuation",
                },
                {
                    "evidence_id": "derived:technical:MU",
                    "category": "derived_market_technical",
                    "observed_on": "2026-07-31",
                    "adjusted_close": 938.40,
                    "sma_20": 912.35,
                    "sma_50": 958.92,
                    "sma_200": 581.54,
                    "rsi_14": 42.72,
                    "macd_histogram": -14.35,
                    "return_21d": -0.203,
                    "drawdown_from_52_week_high": -0.322,
                },
            ],
            "market_observations": [],
            "economic_observations": [],
            "company_financials": [],
            "events": [],
            "documents": [],
        },
        allowed_refs={"derived:valuation:MU", "derived:technical:MU"},
    )

    assert len(completed) == 5
    missing = next(item for item in completed if item.dimension == "technicals_positioning")
    assert missing.signal == "mixed"
    assert missing.confidence == 0.6
    assert missing.evidence_refs == ["derived:technical:MU"]
    assert "高于 SMA20" in missing.assessment
    assert "低于 SMA50" in missing.assessment
    fundamentals = next(item for item in completed if item.dimension == "fundamentals_valuation")
    assert "intervention" not in fundamentals.assessment.casefold()
    assert fundamentals.evidence_refs == ["derived:valuation:MU"]
    macro = next(item for item in completed if item.dimension == "macro_liquidity")
    assert macro.signal == "unknown"
    assert macro.confidence == 0.15


def test_new_verified_supplier_evidence_replaces_stale_supply_dimension() -> None:
    stale = ModelEquityResearchDimension(
        dimension="supply_chain_geopolitics",
        assessment="Apple Inc. (AAPL) 的供应链仍待验证。",
        signal="unknown",
        confidence=0.2,
        evidence_refs=["document:1"],
        evidence_gaps=["缺少供应商关系。"],
    )
    evidence = {
        "equity_research_context": {
            "ticker": "AAPL",
            "company": "Apple Inc.",
            "market_region": "us",
            "verified_supply_chain_edge_total": 187,
            "reviewed_search_plan_not_evidence": {},
        },
        "derived_equity_evidence": [
            {
                "evidence_id": "document:1",
                "category": "company_news_document",
            },
            {
                "evidence_id": "supply-edge:1",
                "category": "verified_supply_chain_edge",
                "related_company_name": "Taiwan Semiconductor Manufacturing",
            },
            {
                "evidence_id": "supplier-factor:1",
                "category": "derived_supplier_factor",
                "supplier_name": "Taiwan Semiconductor Manufacturing",
            },
        ],
        "market_observations": [],
        "economic_observations": [],
        "company_financials": [],
        "events": [],
        "documents": [],
    }

    completed = _complete_equity_dimensions(
        [stale],
        evidence=evidence,
        allowed_refs={"document:1", "supply-edge:1", "supplier-factor:1"},
    )
    supply = next(item for item in completed if item.dimension == "supply_chain_geopolitics")

    assert supply.signal == "mixed"
    assert supply.confidence == 0.5
    assert "数据库共有187条" in supply.assessment
    assert "本次证据包纳入1条" in supply.assessment
    assert "supply-edge:1" in supply.evidence_refs


def test_category_proxy_is_not_reported_as_a_named_supplier_relationship() -> None:
    evidence = {
        "equity_research_context": {
            "ticker": "MSFT",
            "company": "Microsoft Corp.",
            "market_region": "us",
            "verified_supply_chain_edge_total": 1,
            "reviewed_search_plan_not_evidence": {},
        },
        "derived_equity_evidence": [
            {
                "evidence_id": "supply-edge:2",
                "category": "verified_supply_chain_edge",
                "related_company_name": "Undisclosed datacenter component suppliers",
            },
            {
                "evidence_id": "supply-category-factor:2",
                "category": "derived_supplier_factor",
                "proxy_type": "category_basket",
                "supplier_name": "data-center semiconductor basket",
            },
        ],
        "market_observations": [],
        "economic_observations": [],
        "company_financials": [],
        "events": [],
        "documents": [],
    }

    completed = _complete_equity_dimensions(
        [],
        evidence=evidence,
        allowed_refs={"supply-edge:2", "supply-category-factor:2"},
    )
    supply = next(item for item in completed if item.dimension == "supply_chain_geopolitics")

    assert supply.confidence == 0.38
    assert "1个未披露具体供应商的依赖类别使用行业篮子代理" in supply.assessment
    assert "篮子成分不得解释为关联公司或真实供应商" in supply.assessment
    assert "关系可与关联公司的市场序列对齐" not in supply.assessment


def test_company_facilities_are_not_reported_as_missing_supplier_locations() -> None:
    context = {
        "ticker": "MU",
        "company": "Micron Technology Inc.",
        "market_region": "us",
        "verified_supply_chain_edge_total": 0,
        "reviewed_search_plan_not_evidence": {},
    }
    sites = [
        {
            "evidence_id": f"supply-site:{index}:2026-08-31",
            "category": "supply_chain_site_exposure",
            "site_name": f"Micron Facility {index}",
            "facility_role": "company_facility",
            "coordinate_precision": "exact_facility",
            "latitude": 40.0 + index,
            "longitude": -100.0 + index,
            "conflict_events": 0,
            "disaster_event_count": 0,
        }
        for index in range(1, 9)
    ]
    completed = _complete_equity_dimensions(
        [],
        evidence={
            "equity_research_context": context,
            "derived_equity_evidence": sites,
            "market_observations": [],
            "economic_observations": [],
            "company_financials": [],
            "events": [],
            "documents": [],
        },
        allowed_refs={str(item["evidence_id"]) for item in sites},
    )
    supply = next(item for item in completed if item.dimension == "supply_chain_geopolitics")

    assert supply.signal == "unknown"
    assert supply.confidence == 0.46
    assert "8条标记为公司自有设施" in supply.assessment
    assert "0条标记为上游供应商地点" in supply.assessment
    assert "公司自有设施不能被误写成上游供应商" in supply.assessment
    assert supply.evidence_gaps[0].startswith("已取得精确设施坐标")


def test_fallback_framework_flags_high_trailing_multiple_as_extended() -> None:
    framework = _fallback_equity_framework(
        {
            "derived_equity_evidence": [
                {
                    "category": "derived_market_technical",
                    "adjusted_close": 823.03,
                },
                {
                    "category": "derived_company_valuation",
                    "basis_revenue": 33_300_000_000,
                    "basis_gross_profit": 18_000_000_000,
                    "basis_operating_income": 11_000_000_000,
                    "basis_net_income": 7_500_000_000,
                    "basis_research_and_development": 4_000_000_000,
                    "trailing_price_to_sales": 24.7,
                    "trailing_price_to_earnings": 108.4,
                    "question_price_scenarios": [
                        {
                            "target_price": 700,
                            "implied_market_cap": 785_400_000_000,
                            "implied_price_to_sales": 21.01,
                            "implied_price_to_earnings": 92.23,
                        }
                    ],
                },
            ]
        }
    )

    assert framework.timing_assessment == "extended"
    assert "785.40" in framework.valuation_scenarios[0]
    assert framework.not_personalized_advice is True


def test_ttm_proxy_uses_annual_plus_current_quarters_minus_prior_comparables() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    annual_values = {
        "RevenueFromContractWithCustomerExcludingAssessedTax": 100.0,
        "GrossProfit": 40.0,
        "OperatingIncomeLoss": 20.0,
        "NetIncomeLoss": 10.0,
        "EarningsPerShareDiluted": 10.0,
        "ResearchAndDevelopmentExpense": 5.0,
    }
    current_values = {
        "RevenueFromContractWithCustomerExcludingAssessedTax": (30.0, 35.0, 40.0),
        "GrossProfit": (12.0, 14.0, 16.0),
        "OperatingIncomeLoss": (6.0, 7.0, 8.0),
        "NetIncomeLoss": (3.0, 4.0, 5.0),
        "EarningsPerShareDiluted": (3.0, 4.0, 5.0),
        "ResearchAndDevelopmentExpense": (1.5, 1.6, 1.7),
    }
    prior_values = {
        "RevenueFromContractWithCustomerExcludingAssessedTax": (20.0, 20.0, 20.0),
        "GrossProfit": (8.0, 8.0, 8.0),
        "OperatingIncomeLoss": (4.0, 4.0, 4.0),
        "NetIncomeLoss": (1.0, 1.0, 1.0),
        "EarningsPerShareDiluted": (1.0, 1.0, 1.0),
        "ResearchAndDevelopmentExpense": (1.0, 1.0, 1.0),
    }
    current_ends = (date(2025, 11, 27), date(2026, 2, 26), date(2026, 5, 28))
    prior_ends = (date(2024, 11, 28), date(2025, 2, 27), date(2025, 5, 29))
    with Session(engine) as session:
        annual_facts = {
            concept: _period_fact(
                concept,
                value,
                period_start=date(2024, 8, 30),
                period_end=date(2025, 8, 28),
                filed_at=date(2025, 10, 3),
                form="10-K",
                fiscal_period="FY",
                suffix=f"annual-{index}",
            )
            for index, (concept, value) in enumerate(annual_values.items())
        }
        session.add_all(annual_facts.values())
        for concept_index, concept in enumerate(annual_values):
            for period_index, period_end in enumerate(current_ends):
                session.add(
                    _period_fact(
                        concept,
                        current_values[concept][period_index],
                        period_start=period_end - timedelta(days=89),
                        period_end=period_end,
                        filed_at=period_end + timedelta(days=20),
                        form="10-Q",
                        fiscal_period=f"Q{period_index + 1}",
                        suffix=f"current-{concept_index}-{period_index}",
                    )
                )
            for period_index, period_end in enumerate(prior_ends):
                session.add(
                    _period_fact(
                        concept,
                        prior_values[concept][period_index],
                        period_start=period_end - timedelta(days=89),
                        period_end=period_end,
                        filed_at=period_end + timedelta(days=20),
                        form="10-Q",
                        fiscal_period=f"Q{period_index + 1}",
                        suffix=f"prior-{concept_index}-{period_index}",
                    )
                )
        session.commit()
        basis = _latest_valuation_basis(
            session,
            ticker="MU",
            as_of=date(2026, 8, 26),
            annual_facts=annual_facts,
        )

    assert basis["basis"] == "ttm_proxy"
    assert basis["period_end"] == "2026-05-28"
    assert basis["values"]["RevenueFromContractWithCustomerExcludingAssessedTax"] == 145.0
    assert basis["values"]["NetIncomeLoss"] == 19.0
    assert basis["values"]["EarningsPerShareDiluted"] == 19.0
    engine.dispose()


def test_price_scenario_parser_does_not_treat_month_horizon_as_price() -> None:
    assert _question_target_prices("NVDA未来6至12个月的盈利与估值驱动是否获得支持?") == []
    assert _question_target_prices("美光700的价格是否合理?") == [700.0]
    assert _question_target_prices("Is a price target of $320 reasonable?") == [320.0]


def test_apple_company_news_rejects_retail_accessory_and_fruit_matches() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source = Source(
            name="Discovery",
            country=None,
            language="en",
            source_type=SourceType.NEWS,
            credibility_baseline=Decimal("0.500"),
        )
        rows = [
            Document(
                source=source,
                url="https://publisher.test/apple-event",
                title="Apple announces its September iPhone event",
                body="Apple announced the event and described the iPhone launch schedule. " * 6,
                published_at=datetime(2026, 8, 27, tzinfo=UTC),
                content_hash="a" * 64,
            ),
            Document(
                source=source,
                url="https://www.amazon.com/product/charger",
                title="Apple Watch compatible wireless charger",
                body="This marketplace product page lists an Apple Watch charger. " * 6,
                published_at=datetime(2026, 8, 27, tzinfo=UTC),
                content_hash="b" * 64,
            ),
            Document(
                source=source,
                url="https://publisher.test/headphones",
                title="首款专为苹果 iPhone 用户打造的 Agent 耳机开始预售",
                body="该产品由第三方厂商发布，并获得苹果授权芯片和 MFi 认证。" * 10,
                published_at=datetime(2026, 8, 27, tzinfo=UTC),
                content_hash="c" * 64,
            ),
            Document(
                source=source,
                url="https://publisher.test/juice",
                title="清晨一杯苹果胡萝卜汁让健康更简单",
                body="鲜榨果汁和苹果胡萝卜汁是家庭健康饮食的一部分。" * 10,
                published_at=datetime(2026, 8, 27, tzinfo=UTC),
                content_hash="d" * 64,
            ),
        ]
        session.add_all(rows)
        session.commit()

        evidence = _company_document_evidence(
            session,
            ticker="AAPL",
            as_of=date(2026, 8, 27),
        )

    assert [item["title"] for item in evidence] == ["Apple announces its September iPhone event"]
    engine.dispose()


def test_company_news_uses_official_sec_catalog_name_without_manual_alias() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source = Source(
            name="Company Wire",
            country=None,
            language="en",
            source_type=SourceType.NEWS,
            credibility_baseline=Decimal("0.500"),
        )
        session.add(
            Document(
                source=source,
                url="https://publisher.test/costco-results",
                title="Costco Wholesale reports quarterly results",
                body=("Costco Wholesale discussed membership growth and merchandise sales. " * 6),
                published_at=datetime(2026, 8, 27, tzinfo=UTC),
                content_hash="e" * 64,
            )
        )
        session.add(
            Document(
                source=source,
                url="https://publisher.test/unrelated-cost",
                title="Insurance costs increase after severe storms",
                body="The cost of insurance increased after the storms. " * 8,
                published_at=datetime(2026, 8, 27, tzinfo=UTC),
                content_hash="f" * 64,
            )
        )
        session.commit()

        evidence = _company_document_evidence(
            session,
            ticker="COST",
            company_name="Costco Wholesale Corp.",
            as_of=date(2026, 8, 27),
        )

    assert [item["title"] for item in evidence] == ["Costco Wholesale reports quarterly results"]
    engine.dispose()


def test_amd_company_news_accepts_exact_three_letter_ticker_in_title() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source = Source(
            name="Semiconductor Wire",
            country=None,
            language="en",
            source_type=SourceType.NEWS,
            credibility_baseline=Decimal("0.500"),
        )
        session.add_all(
            [
                Document(
                    source=source,
                    url="https://publisher.test/amd-data-center",
                    title="AMD reports new data-center accelerator demand",
                    body=(
                        "AMD discussed Instinct accelerator demand, customer qualification "
                        "and data-center revenue. " * 6
                    ),
                    published_at=datetime(2026, 8, 27, tzinfo=UTC),
                    content_hash="7" * 64,
                ),
                Document(
                    source=source,
                    url="https://publisher.test/unrelated",
                    title="Regional demand improves",
                    body="An unrelated market update mentioned demand conditions. " * 8,
                    published_at=datetime(2026, 8, 27, tzinfo=UTC),
                    content_hash="8" * 64,
                ),
            ]
        )
        session.commit()

        evidence = _company_document_evidence(
            session,
            ticker="AMD",
            company_name="Advanced Micro Devices Inc.",
            as_of=date(2026, 8, 27),
        )

    assert [item["title"] for item in evidence] == [
        "AMD reports new data-center accelerator demand"
    ]
    engine.dispose()


def test_company_news_rejects_incidental_mentions_outside_article_lead() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source = Source(
            name="Enterprise Ranking",
            country=None,
            language="zh",
            source_type=SourceType.NEWS,
            credibility_baseline=Decimal("0.500"),
        )
        session.add_all(
            [
                Document(
                    source=source,
                    url="https://publisher.test/msft-cloud",
                    title="微软发布云业务季度更新",
                    body="微软Azure与企业软件是本文主题。" * 80,
                    published_at=datetime(2026, 8, 27, tzinfo=UTC),
                    content_hash="1" * 64,
                ),
                Document(
                    source=source,
                    url="https://publisher.test/china-erp-ranking",
                    title="中国ERP厂商综合实力排名",
                    body=("用友、金蝶和钉钉占据国内企业软件市场。" * 100)
                    + ("附录对照Microsoft Dynamics与微软产品。" * 3),
                    published_at=datetime(2026, 8, 27, tzinfo=UTC),
                    content_hash="2" * 64,
                ),
            ]
        )
        session.commit()

        evidence = _company_document_evidence(
            session,
            ticker="MSFT",
            company_name="Microsoft Corp.",
            as_of=date(2026, 8, 27),
        )

    assert [item["title"] for item in evidence] == ["微软发布云业务季度更新"]
    engine.dispose()


def test_revenue_taxonomy_selection_prefers_latest_period_over_old_alias() -> None:
    old_alias = _period_fact(
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        26.9,
        period_start=date(2021, 1, 31),
        period_end=date(2022, 1, 30),
        filed_at=date(2022, 3, 18),
        form="10-K",
        fiscal_period="FY",
        suffix="old-revenue-alias",
    )
    latest_revenue = _period_fact(
        "Revenues",
        215.9,
        period_start=date(2025, 1, 27),
        period_end=date(2026, 1, 25),
        filed_at=date(2026, 2, 25),
        form="10-K",
        fiscal_period="FY",
        suffix="latest-revenues",
    )

    selected = _preferred_revenue_fact(
        {
            old_alias.concept: old_alias,
            latest_revenue.concept: latest_revenue,
        }
    )

    assert selected is latest_revenue


def test_valuation_snapshot_uses_latest_revenue_alias_for_basis_lookup() -> None:
    old_alias = _period_fact(
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        26_914_000_000,
        period_start=date(2021, 1, 31),
        period_end=date(2022, 1, 30),
        filed_at=date(2022, 3, 1),
        form="10-K",
        fiscal_period="FY",
        suffix="old-valuation-revenue",
    )
    latest_revenue = _period_fact(
        "Revenues",
        215_938_000_000,
        period_start=date(2025, 1, 27),
        period_end=date(2026, 1, 25),
        filed_at=date(2026, 3, 1),
        form="10-K",
        fiscal_period="FY",
        suffix="latest-valuation-revenue",
    )
    shares = _period_fact(
        "CommonStockSharesOutstanding",
        24_500_000_000,
        period_start=date(2026, 1, 25),
        period_end=date(2026, 1, 25),
        filed_at=date(2026, 3, 1),
        form="10-K",
        fiscal_period="FY",
        suffix="shares",
    )
    snapshot = _valuation_snapshot(
        "NVDA",
        [(date(2026, 8, 27), 220.0)],
        {
            old_alias.concept: old_alias,
            latest_revenue.concept: latest_revenue,
            shares.concept: shares,
        },
        question="NVDA未来6至12个月如何?",
        valuation_basis={
            "basis": "latest_fiscal_year",
            "period_end": latest_revenue.period_end.isoformat(),
            "values": {latest_revenue.concept: latest_revenue.value},
            "facts": [latest_revenue],
        },
        latest_shares=shares,
    )

    assert snapshot is not None
    assert snapshot["annual_revenue"] == latest_revenue.value
    assert snapshot["basis_revenue"] == latest_revenue.value
    assert snapshot["question_price_scenarios"] == []


def test_financial_trend_uses_annual_duration_and_period_end_year() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_company_catalog(session)
        annual_2020_revenue = _period_fact(
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            100.0,
            period_start=date(2019, 9, 29),
            period_end=date(2020, 9, 26),
            filed_at=date(2022, 10, 28),
            form="10-K",
            fiscal_period="FY",
            suffix="annual-2020-revenue",
        )
        annual_2020_revenue.fiscal_year = 2022
        annual_2020_income = _period_fact(
            "NetIncomeLoss",
            20.0,
            period_start=date(2019, 9, 29),
            period_end=date(2020, 9, 26),
            filed_at=date(2022, 10, 28),
            form="10-K",
            fiscal_period="FY",
            suffix="annual-2020-income",
        )
        annual_2020_income.fiscal_year = 2022
        annual_2021_revenue = _period_fact(
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            120.0,
            period_start=date(2020, 9, 27),
            period_end=date(2021, 9, 25),
            filed_at=date(2023, 11, 3),
            form="10-K",
            fiscal_period="FY",
            suffix="annual-2021-revenue",
        )
        annual_2021_revenue.fiscal_year = 2023
        annual_2021_income = _period_fact(
            "NetIncomeLoss",
            30.0,
            period_start=date(2020, 9, 27),
            period_end=date(2021, 9, 25),
            filed_at=date(2023, 11, 3),
            form="10-K",
            fiscal_period="FY",
            suffix="annual-2021-income",
        )
        annual_2021_income.fiscal_year = 2023
        quarterly_2020_revenue = _period_fact(
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            25.0,
            period_start=date(2020, 3, 29),
            period_end=date(2020, 6, 27),
            filed_at=date(2024, 1, 1),
            form="10-K",
            fiscal_period="FY",
            suffix="quarterly-2020-revenue",
        )
        quarterly_2020_revenue.fiscal_year = 2020
        session.add_all(
            [
                annual_2020_revenue,
                annual_2020_income,
                annual_2021_revenue,
                annual_2021_income,
                quarterly_2020_revenue,
            ]
        )
        session.commit()
        trend = _financial_trend_snapshot(session, ticker="MU", as_of=date(2026, 8, 28))

    assert trend is not None
    periods = {item["fiscal_year"]: item for item in trend["periods"]}
    assert periods[2020]["revenue"] == 100.0
    assert round(periods[2021]["revenue_yoy"], 6) == 0.2
    assert round(periods[2021]["net_income_yoy"], 6) == 0.5
    engine.dispose()


def _fact(concept: str, unit: str, value: float) -> CompanyFinancialFact:
    return CompanyFinancialFact(
        ticker="MU",
        taxonomy="us-gaap",
        concept=concept,
        label=concept,
        unit=unit,
        value=value,
        period_start=date(2024, 8, 30),
        period_end=date(2025, 8, 28),
        filed_at=date(2025, 9, 1),
        form="10-K",
        fiscal_year=2025,
        fiscal_period="FY",
        accession_number=f"0000723125-25-{len(concept):06d}",
        source_url="https://www.sec.gov/Archives/edgar/data/723125/",
    )


def _period_fact(
    concept: str,
    value: float,
    *,
    period_start: date,
    period_end: date,
    filed_at: date,
    form: str,
    fiscal_period: str,
    suffix: str,
) -> CompanyFinancialFact:
    return CompanyFinancialFact(
        ticker="MU",
        taxonomy="us-gaap",
        concept=concept,
        label=concept,
        unit="USD/shares" if concept == "EarningsPerShareDiluted" else "USD",
        value=value,
        period_start=period_start,
        period_end=period_end,
        filed_at=filed_at,
        form=form,
        fiscal_year=period_end.year,
        fiscal_period=fiscal_period,
        accession_number=f"test-{suffix}",
        source_url="https://www.sec.gov/Archives/edgar/data/723125/",
    )
