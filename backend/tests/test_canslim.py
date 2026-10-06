"""Auditable CAN SLIM scorecard regression tests."""

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import canslim


def test_canslim_total_stays_on_a_zero_to_one_hundred_scale(monkeypatch) -> None:
    monkeypatch.setattr(
        canslim,
        "_quarterly_earnings",
        lambda *_args, **_kwargs: {
            "latest_eps": 1.5,
            "prior_eps": 1.0,
            "eps_yoy": 0.5,
            "evidence_refs": ["quarterly"],
        },
    )
    monkeypatch.setattr(
        canslim,
        "_annual_earnings",
        lambda *_args, **_kwargs: {
            "eps_cagr": 0.3,
            "span_years": 3.0,
            "roe": 0.2,
            "evidence_refs": ["annual"],
        },
    )
    monkeypatch.setattr(
        canslim,
        "_market_direction",
        lambda *_args, **_kwargs: {
            "evidence_id": "market:SP500:test",
            "above_sma_50": True,
            "above_sma_200": True,
            "return_21d": 0.02,
            "return_252d": 0.15,
        },
    )
    technical = {
        "evidence_id": "market:EQ:TEST",
        "adjusted_close": 99.0,
        "high_52_week_close": 100.0,
        "drawdown_from_52_week_high": -0.01,
        "return_252d": 0.3,
        "volume_ratio_20": 1.5,
        "volume_confirmation": {"latest_candle_direction": "up"},
    }
    result = canslim.build_canslim_scorecard(
        Session(create_engine("sqlite+pysqlite:///:memory:")),
        ticker="TEST",
        as_of=date(2026, 9, 1),
        technical=technical,
        product_evidence=[
            {"evidence_id": f"product:{index}", "evidence_status": "reported_actual"}
            for index in range(5)
        ],
        institutional_evidence=[
            {"evidence_id": "holding:up", "reported_share_change": 100},
            {"evidence_id": "holding:up-2", "reported_share_change": 10},
        ],
    )

    assert result["overall_score"] == 98.5
    assert 0 <= result["overall_score"] <= 100
    assert result["coverage_score"] == 100
    assert result["decision"] == "criteria_supported"


def test_new_factor_does_not_exceed_its_evidence_subscore() -> None:
    criterion = canslim._new_factor_criterion(
        [
            {"evidence_id": f"product:{index}", "evidence_status": "reported_actual"}
            for index in range(20)
        ],
        technical={"drawdown_from_52_week_high": -0.25},
    )

    assert criterion["status"] == "partial"
    assert criterion["score"] == 70.0
