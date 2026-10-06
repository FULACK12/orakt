"""Leakage and horizon-gate tests for the entry backtest baseline."""

from datetime import date, timedelta

from app.horizon_backtest import (
    HORIZON_CONFIGS,
    _signal_at,
    apply_point_in_time_fundamental_gate,
    build_horizon_models,
)


def _history(length: int = 900) -> tuple[list[date], list[float]]:
    start = date(2022, 1, 3)
    dates = [start + timedelta(days=index) for index in range(length)]
    closes = [100 + index * 0.08 + (index % 13 - 6) * 0.35 for index in range(length)]
    return dates, closes


def test_signal_at_decision_date_does_not_read_future_prices() -> None:
    _, closes = _history()
    decision_index = 300
    changed_future = closes[: decision_index + 1] + [
        value * 4 for value in closes[decision_index + 1 :]
    ]

    baseline = _signal_at(closes, None, decision_index, HORIZON_CONFIGS[1])
    changed = _signal_at(changed_future, None, decision_index, HORIZON_CONFIGS[1])

    assert changed == baseline


def test_horizon_models_expose_frozen_parameters_and_chronological_split() -> None:
    dates, closes = _history()

    result = build_horizon_models(dates, closes)

    assert result["parameter_policy"] == "frozen_versioned_parameters"
    assert len(result["models"]) == 4
    for model in result["models"]:
        validation = model["validation"]
        assert validation["train_observations"] > 0
        assert validation["train_end_date"] < validation["end_date"]
        assert "close t+1" in validation["leakage_guard"]
        assert model["parameters"]["transaction_cost_bps"] == 10.0


def test_long_value_signal_requires_and_accepts_point_in_time_fundamentals() -> None:
    dates, closes = _history()
    result = build_horizon_models(dates, closes)
    long_value = result["models"][-1]

    assert long_value["fundamental_gate"]["passed"] is False
    assert long_value["status"] == "requires_point_in_time_fundamentals"

    apply_point_in_time_fundamental_gate(result, available=True)

    assert long_value["fundamental_gate"]["passed"] is True
    assert long_value["status"] in {"research_signal", "watch_only"}
