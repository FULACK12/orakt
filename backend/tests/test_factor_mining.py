"""Dual-track factor mining and cold artifact tests."""

import math
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.db.models import MarketAssetLifecycle, MarketObservation, MarketSeries
from app.factor_mining import (
    _expanded_bridge_variables,
    _factors_from_product_evidence,
    _replicate_market_factor_rule,
    _select_target_series,
    build_factor_research,
)
from app.schemas.research import ModelResearchResult


def _result() -> ModelResearchResult:
    return ModelResearchResult.model_validate(
        {
            "question": "Can Test Equity rise when liquidity and volatility interact?",
            "summary": "The local model retains a linear mechanism before factor mining.",
            "hypotheses": [
                {
                    "title": "Liquidity and valuation",
                    "premise": "Liquidity conditions change.",
                    "outcome": "Test Equity future returns change.",
                    "scope": {
                        "companies": ["Test Equity"],
                        "sectors": ["technology"],
                        "products": [],
                        "supply_chain_inputs": [],
                        "infrastructure": [],
                        "policies": [],
                        "geographies": ["United States"],
                    },
                    "steps": [
                        {
                            "sequence": 1,
                            "label": "Liquidity changes",
                            "status": "hypothesis",
                            "confidence": 0.4,
                            "evidence_refs": [],
                        },
                        {
                            "sequence": 2,
                            "label": "Discount rates adjust",
                            "status": "hypothesis",
                            "confidence": 0.4,
                            "evidence_refs": [],
                        },
                        {
                            "sequence": 3,
                            "label": "Equity valuation changes",
                            "status": "hypothesis",
                            "confidence": 0.4,
                            "evidence_refs": [],
                        },
                    ],
                    "counterarguments": [],
                    "evidence_gaps": [],
                    "confidence": 0.4,
                }
            ],
            "suggested_next_questions": [],
        }
    )


def test_legacy_generic_coal_mechanism_expands_to_measurable_bridges() -> None:
    hypothesis = _result().hypotheses[0]
    hypothesis.outcome = "Steam coal import prices change."
    hypothesis.steps[1].label = (
        "A transmission mechanism to the coal price is proposed but not established."
    )

    bridges = _expanded_bridge_variables(hypothesis)

    assert len(bridges) == 4
    assert any("融资" in bridge for bridge in bridges)
    assert any("库存" in bridge for bridge in bridges)
    assert any("运力" in bridge for bridge in bridges)
    assert any("汇率" in bridge for bridge in bridges)


def test_product_operating_fact_becomes_bounded_company_factor() -> None:
    evidence_id = "product-operating:MU:filing:dram-asp"
    factors = _factors_from_product_evidence(
        {
            "derived_equity_evidence": [
                {
                    "evidence_id": evidence_id,
                    "category": "product_operating_evidence",
                    "ticker": "MU",
                    "product": "DRAM",
                    "metric_type": "price_and_volume_change",
                    "metric_name": "average selling price and bit-shipment change",
                    "evidence_status": "reported_actual",
                    "signal": "positive",
                    "reported_values": ["62%", "low-40% range"],
                }
            ]
        },
        {evidence_id},
    )

    assert len(factors) == 1
    assert factors[0].factor_type == "company"
    assert factors[0].transformation == "change"
    assert factors[0].direction == "positive"
    assert factors[0].confidence == 0.65
    assert factors[0].evidence_refs == [evidence_id]
    assert "不能单独证明未来股价方向" in factors[0].hypothesis


def test_factor_replication_uses_disjoint_trials_and_freezes_future_signal() -> None:
    start = date(2020, 1, 1)
    target = MarketSeries(
        series_id="TEST_REPLICATION",
        name="Replication Test Equity",
        category="equity_price",
        unit="dollars",
        frequency="daily",
        source_name="Test",
        source_url="https://example.test/replication",
    )
    factor_series = [
        MarketSeries(
            series_id=f"PRED{index}",
            name=f"Predictor {index}",
            category="liquidity",
            unit="index",
            frequency="daily",
            source_name="Test",
            source_url=f"https://example.test/pred{index}",
        )
        for index in range(1, 3)
    ]
    samples: list[tuple[date, float, date]] = []
    paired: list[tuple[date, float, date, float]] = []
    changes: list[tuple[date, float]] = []
    price = 100.0
    target_rows: list[tuple[date, float]] = []
    for index in range(100):
        observed_on = start + timedelta(days=index * 2)
        outcome_on = observed_on + timedelta(days=1)
        signal = 1.0 if index % 2 == 0 else -1.0
        forward_return = 0.02 * signal
        samples.append((observed_on, forward_return, outcome_on))
        paired.append((observed_on, signal, outcome_on, forward_return))
        changes.append((observed_on, signal))
        target_rows.append((observed_on, price))
        price *= 1 + forward_return
        target_rows.append((outcome_on, price))

    replication = _replicate_market_factor_rule(
        target=target,
        target_rows=target_rows,
        samples=samples,
        candidates=[
            {"series": series, "paired": paired, "changes": changes}
            for series in factor_series
        ],
        horizon=1,
        transaction_cost_bps=25.0,
    )

    assert replication.retention_status == "provisional_retained"
    assert replication.valid_trials == 4
    assert replication.passed_trials == 4
    assert replication.pooled_excess_ci_low is not None
    assert replication.pooled_excess_ci_low > 0
    assert replication.future_validation_status == "pending"
    assert replication.prospective_position in {"long", "short"}
    assert replication.prospective_factor_ids
    for previous, current in zip(replication.trials, replication.trials[1:], strict=False):
        assert date.fromisoformat(previous.test_end_date) < date.fromisoformat(
            current.test_start_date
        )
    assert all(trial.transaction_cost_bps >= 25 for trial in replication.trials)


def test_factor_mining_keeps_linear_chain_and_uses_oos_split(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        series = [
            MarketSeries(
                series_id="TEST",
                name="Test Equity Price",
                category="equity_index",
                unit="index",
                frequency="daily",
                source_name="Test",
                source_url="https://example.test/target",
            ),
            MarketSeries(
                series_id="PRED1",
                name="Liquidity Proxy",
                category="liquidity",
                unit="index",
                frequency="daily",
                source_name="Test",
                source_url="https://example.test/p1",
            ),
            MarketSeries(
                series_id="PRED2",
                name="Volatility Proxy",
                category="risk",
                unit="index",
                frequency="daily",
                source_name="Test",
                source_url="https://example.test/p2",
            ),
            MarketSeries(
                series_id="CPI_TEST",
                name="Test Consumer Price Index",
                category="inflation",
                unit="index",
                frequency="daily",
                source_name="Test",
                source_url="https://example.test/cpi",
            ),
            MarketSeries(
                series_id="DCOILWTICO",
                name="West Texas Intermediate Crude Oil Price",
                category="commodity_price",
                unit="dollars",
                frequency="daily",
                source_name="Test",
                source_url="https://example.test/oil",
            ),
            MarketSeries(
                series_id="SP500",
                name="S&P 500",
                category="market_index",
                unit="index",
                frequency="daily",
                source_name="Test",
                source_url="https://example.test/sp500",
            ),
        ]
        series.extend(
            MarketSeries(
                series_id=f"ASSET{index}",
                name=f"Cross Section Equity {index}",
                category="equity_price",
                unit="dollars",
                frequency="daily",
                source_name="Test",
                source_url=f"https://example.test/asset{index}",
                listing_status="delisted" if index == 5 else "active",
                listed_from=date(2020, 1, 1) if index == 5 else None,
                listed_until=date(2020, 12, 6) if index == 5 else None,
                delisting_return=-0.2 if index == 5 else None,
            )
            for index in range(1, 6)
        )
        session.add_all(series)
        session.add_all(
            [
                MarketAssetLifecycle(
                    asset_key=f"av:test:{symbol}",
                    provider_key="alpha_vantage_listing_status",
                    symbol=symbol,
                    name=f"Historical {symbol}",
                    exchange="NYSE",
                    asset_type="Stock",
                    ipo_date=date(2010, 1, 4),
                    delisting_date=date(2019, 1, 2),
                    listing_status="delisted",
                    snapshot_date=date(2026, 8, 24),
                    fetched_at=datetime.now(UTC),
                    source_url="https://www.alphavantage.co/documentation/",
                )
                for symbol in ("OLDONE", "OLDTWO")
            ]
        )
        start = date(2020, 1, 1)
        target_value = predictor_one = predictor_two = 100.0
        asset_values = {f"ASSET{index}": 100.0 for index in range(1, 6)}
        for index in range(420):
            signal = math.sin(index / 18)
            target_value *= 1 + 0.002 * signal
            predictor_one *= 1 + 0.0022 * signal
            predictor_two *= 1 - 0.0018 * math.cos(index / 23)
            for asset_index, series_id in enumerate(asset_values, start=1):
                loading = (asset_index - 3) * 0.0011
                asset_values[series_id] *= 1 + loading * signal + 0.0003 * asset_index
            observed_on = start + timedelta(days=index)
            for series_id, value in (
                ("TEST", target_value),
                ("PRED1", predictor_one),
                ("PRED2", predictor_two),
                ("CPI_TEST", predictor_one * 2),
                ("DCOILWTICO", predictor_two * 0.7),
                ("SP500", target_value * 1.1),
                *asset_values.items(),
            ):
                if series_id == "ASSET5" and observed_on > date(2020, 12, 6):
                    continue
                session.add(
                    MarketObservation(
                        series_id=series_id,
                        observed_on=observed_on,
                        value=value,
                        fetched_at=datetime.now(UTC),
                    )
                )
        session.flush()

        research = build_factor_research(
            session,
            result=_result(),
            evidence={},
            settings=Settings(
                cold_data_root=tmp_path,
                cold_archive_min_free_gb=1,
                cold_archive_max_used_percent=99,
            ),
            inquiry_id=7,
        )

        assert research.linear_chain_retained is True
        assert research.factors
        assert research.nonlinear_links
        ai_link = next(
            link
            for link in research.nonlinear_links
            if link.link_id.startswith("ai:interaction:")
        )
        assert ai_link.relationship_class == "exploratory_nonlinear"
        assert ai_link.bridge_variables == ["Discount rates adjust"]
        assert len(ai_link.linear_segments) == 2
        assert ai_link.linear_segments[0].source == "Liquidity changes"
        assert ai_link.linear_segments[0].target == "Discount rates adjust"
        assert ai_link.linear_segments[1].target == "Equity valuation changes"
        validation = research.profit_validations[0]
        assert validation.target_series_id == "TEST"
        assert validation.train_observations > validation.test_observations > 0
        assert validation.train_end_date is not None
        assert "70/30" in validation.leakage_guard
        assert {
            item.forecast_horizon_days for item in research.profit_validations
        } == {1, 5, 20, 60}
        cross_validation = research.cross_sectional_validations[0]
        assert cross_validation.asset_count >= 6
        assert cross_validation.expected_asset_count >= cross_validation.asset_count
        assert cross_validation.asset_category_counts
        assert cross_validation.train_rebalances > cross_validation.test_rebalances > 0
        assert cross_validation.factor_ids
        assert cross_validation.asset_exposures
        assert cross_validation.long_bucket_size > 0
        assert "70/30" in cross_validation.leakage_guard
        assert "之前" in cross_validation.leakage_guard
        assert {
            item.rebalance_horizon_days
            for item in research.cross_sectional_validations
        } == {1, 5, 20, 60}
        assert cross_validation.robustness is not None
        assert cross_validation.robustness.candidate_factor_tests >= 2
        assert cross_validation.robustness.adjusted_significant_factors >= 1
        assert cross_validation.robustness.test_rebalances > 0
        assert cross_validation.robustness.neutralization_group_count >= 2
        assert "Benjamini-Hochberg" in cross_validation.robustness.multiple_testing_method
        assert cross_validation.robustness.contribution_attribution
        assert cross_validation.robustness.attribution_reconciled is True
        for dimension in {
            row.dimension for row in cross_validation.robustness.contribution_attribution
        }:
            dimension_total = sum(
                row.contribution
                for row in cross_validation.robustness.contribution_attribution
                if row.dimension == dimension
            )
            assert math.isclose(
                dimension_total,
                cross_validation.robustness.long_short_return or 0.0,
                abs_tol=1e-8,
            )
        assert cross_validation.survivorship_audit is not None
        assert cross_validation.survivorship_audit.point_in_time_membership_enforced is True
        assert cross_validation.survivorship_audit.historical_assets == 1
        assert cross_validation.survivorship_audit.discovered_delisted_assets == 2
        assert cross_validation.survivorship_audit.missing_price_delisted_assets == 2
        assert cross_validation.survivorship_audit.delisting_returns_covered == 1
        assert cross_validation.survivorship_audit.max_eligible_assets >= (
            cross_validation.survivorship_audit.min_eligible_assets
        )
        assert any(exposure.neutralization_group for exposure in cross_validation.asset_exposures)
        assert research.method_version == "dual_track_factor_v10_product_operating_bridge"
        assert research.archive_status == "stored"
        assert research.archive_path is not None
        assert (tmp_path / research.archive_path).is_file()

        oil_result = _result()
        oil_result.question = "Could a Brent crude oil supply shock raise oil prices?"
        oil_result.hypotheses[0].scope.companies = []
        oil_result.hypotheses[0].scope.products = ["Brent crude oil"]
        selected_target = _select_target_series(session, oil_result)
        assert selected_target is not None
        assert selected_target.series_id == "DCOILWTICO"

        generic_result = _result()
        generic_result.question = "Does liquidity affect broad asset returns?"
        generic_result.hypotheses[0].scope.companies = []
        generic_result.hypotheses[0].scope.products = []
        selected_target = _select_target_series(session, generic_result)
        assert selected_target is not None
        assert selected_target.series_id == "SP500"
    engine.dispose()
