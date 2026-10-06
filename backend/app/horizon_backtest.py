"""Versioned, point-in-time entry scenarios and walk-forward validations.

The module is deliberately dependency-free so the local research service and the
hosted snapshot exporter use exactly the same calculations.
"""

# ruff: noqa: RUF001

from __future__ import annotations

import math
from datetime import date
from typing import Any

MODEL_VERSION = "entry_horizon_walk_forward_v1"

HORIZON_CONFIGS: tuple[dict[str, Any], ...] = (
    {
        "key": "ultra_short",
        "label_zh": "超短线（1–5个交易日）",
        "label_en": "Ultra-short (1–5 sessions)",
        "horizon_sessions": 3,
        "minimum_history": 80,
        "trend_short": 10,
        "trend_long": 20,
        "momentum_lookback": 5,
        "rsi_period": 14,
        "rsi_floor": 45.0,
        "rsi_ceiling": 74.0,
        "volume_ratio_floor": 0.85,
        "evaluation_stride": 3,
    },
    {
        "key": "swing",
        "label_zh": "波段（1–2周）",
        "label_en": "Swing (1–2 weeks)",
        "horizon_sessions": 10,
        "minimum_history": 120,
        "trend_short": 20,
        "trend_long": 50,
        "momentum_lookback": 20,
        "rsi_period": 14,
        "rsi_floor": 42.0,
        "rsi_ceiling": 72.0,
        "volume_ratio_floor": 0.80,
        "evaluation_stride": 10,
    },
    {
        "key": "medium",
        "label_zh": "中期（1–3个月）",
        "label_en": "Medium-term (1–3 months)",
        "horizon_sessions": 63,
        "minimum_history": 252,
        "trend_short": 50,
        "trend_long": 200,
        "momentum_lookback": 63,
        "rsi_period": 14,
        "rsi_floor": 38.0,
        "rsi_ceiling": 70.0,
        "volume_ratio_floor": 0.75,
        "evaluation_stride": 21,
    },
    {
        "key": "long_value",
        "label_zh": "长期价值（12个月及以上）",
        "label_en": "Long-term value (12+ months)",
        "horizon_sessions": 252,
        "minimum_history": 504,
        "trend_short": 50,
        "trend_long": 200,
        "momentum_lookback": 126,
        "rsi_period": 14,
        "rsi_floor": 32.0,
        "rsi_ceiling": 72.0,
        "volume_ratio_floor": 0.70,
        "evaluation_stride": 21,
        "requires_point_in_time_fundamentals": True,
    },
)


def build_horizon_models(
    dates: list[date],
    closes: list[float],
    *,
    volumes: list[float | None] | None = None,
    point_in_time_fundamentals: bool = False,
    transaction_cost_bps: float = 10.0,
    include_walk_forward_validation: bool = True,
) -> dict[str, Any]:
    """Build current scenarios plus chronological forecast backtests.

    A signal at session ``t`` uses only values at or before ``t``. The modeled
    entry is the next retained close and the outcome is the configured future
    close. Medium and long forecasts intentionally overlap; their output is a
    forecast-quality test, not a compounded portfolio return.
    """
    if len(dates) != len(closes):
        raise ValueError("dates and closes must have equal length")
    if volumes is not None and len(volumes) != len(closes):
        raise ValueError("volumes and closes must have equal length")
    models = [
        _build_one_horizon(
            dates,
            closes,
            volumes=volumes,
            config=config,
            point_in_time_fundamentals=point_in_time_fundamentals,
            transaction_cost_bps=transaction_cost_bps,
            include_walk_forward_validation=include_walk_forward_validation,
        )
        for config in HORIZON_CONFIGS
    ]
    return {
        "version": MODEL_VERSION,
        "parameter_policy": "frozen_versioned_parameters",
        "point_in_time_policy": (
            "Signals use only observations available at the decision close; entry "
            "starts at the next retained close. Historical outcomes never rewrite "
            "the original report inputs."
        ),
        "models": models,
    }


def apply_point_in_time_fundamental_gate(
    horizon_models: dict[str, Any] | None,
    *,
    available: bool,
) -> None:
    """Update only the current long-value gate after report fundamentals load."""
    if not isinstance(horizon_models, dict):
        return
    for model in horizon_models.get("models", []):
        if not isinstance(model, dict) or model.get("key") != "long_value":
            continue
        gate = model.get("fundamental_gate")
        if not isinstance(gate, dict):
            continue
        gate["passed"] = available
        if available and model.get("status") == "requires_point_in_time_fundamentals":
            signal = model.get("current_signal")
            model["status"] = (
                "research_signal"
                if isinstance(signal, dict) and signal.get("triggered")
                else "watch_only"
            )


def _build_one_horizon(
    dates: list[date],
    closes: list[float],
    *,
    volumes: list[float | None] | None,
    config: dict[str, Any],
    point_in_time_fundamentals: bool,
    transaction_cost_bps: float,
    include_walk_forward_validation: bool,
) -> dict[str, Any]:
    horizon = int(config["horizon_sessions"])
    minimum_history = int(config["minimum_history"])
    current_signal = _signal_at(closes, volumes, len(closes) - 1, config)
    annualized_volatility = _annualized_volatility(closes[-64:])
    expected_move = (
        annualized_volatility * math.sqrt(horizon / 252)
        if annualized_volatility is not None
        else None
    )
    current = closes[-1] if closes else None
    entry_lower = current * (1 - 0.25 * expected_move) if current and expected_move else None
    entry_upper = current * (1 + 0.10 * expected_move) if current and expected_move else None
    stop = current * (1 - 0.70 * expected_move) if current and expected_move else None
    target = current * (1 + expected_move) if current and expected_move else None
    downside = (current - stop) / current if current and stop else None
    upside = (target - current) / current if current and target else None
    reward_risk = upside / downside if downside and upside else None
    requires_fundamentals = bool(config.get("requires_point_in_time_fundamentals"))
    gate_passed = not requires_fundamentals or point_in_time_fundamentals
    if len(closes) < minimum_history:
        current_status = "insufficient_history"
    elif not gate_passed:
        current_status = "requires_point_in_time_fundamentals"
    elif current_signal["triggered"]:
        current_status = "research_signal"
    else:
        current_status = "watch_only"
    validation = (
        _walk_forward_validation(
            dates,
            closes,
            volumes=volumes,
            config=config,
            transaction_cost_bps=transaction_cost_bps,
        )
        if include_walk_forward_validation
        else {
            "type": "deferred_to_append_only_calibration_ledger",
            "status": "daily_snapshot_only",
            "transaction_cost_bps": transaction_cost_bps,
            "leakage_guard": (
                "The daily forecast freezes data through the decision close; "
                "outcomes and dual-benchmark evaluation are settled separately."
            ),
        }
    )
    exposed_parameters = {
        key: value
        for key, value in config.items()
        if key
        not in {
            "key",
            "label_zh",
            "label_en",
        }
    }
    exposed_parameters["signal_score_threshold"] = 0.75
    exposed_parameters["transaction_cost_bps"] = transaction_cost_bps
    return {
        "key": config["key"],
        "label_zh": config["label_zh"],
        "label_en": config["label_en"],
        "horizon_sessions": horizon,
        "status": current_status,
        "current_signal": current_signal,
        "entry_zone": {"lower": entry_lower, "upper": entry_upper},
        "stop_reference": stop,
        "target_reference": target,
        "expected_move": expected_move,
        "downside_fraction": downside,
        "upside_fraction": upside,
        "reward_risk_ratio": reward_risk,
        "fundamental_gate": {
            "required": requires_fundamentals,
            "passed": gate_passed,
            "explanation": (
                "Long-value status requires financial statements that were available "
                "at the report cutoff; a price-only backtest cannot establish fair value."
                if requires_fundamentals
                else "No fundamental gate is used for this technical horizon."
            ),
        },
        "parameters": exposed_parameters,
        "validation": validation,
    }


def _signal_at(
    closes: list[float],
    volumes: list[float | None] | None,
    index: int,
    config: dict[str, Any],
) -> dict[str, Any]:
    if index < 0 or index + 1 < int(config["minimum_history"]):
        return {"triggered": False, "score": None, "components": []}
    short_window = int(config["trend_short"])
    long_window = int(config["trend_long"])
    momentum_window = int(config["momentum_lookback"])
    current = closes[index]
    short_average = _mean(closes[index - short_window + 1 : index + 1])
    long_average = _mean(closes[index - long_window + 1 : index + 1])
    momentum = current / closes[index - momentum_window] - 1
    rsi_period = int(config["rsi_period"])
    rsi = _rsi(closes[index - rsi_period : index + 1], rsi_period)
    components: list[dict[str, Any]] = [
        {"key": "trend_alignment", "passed": short_average >= long_average},
        {"key": "price_above_long_average", "passed": current >= long_average},
        {"key": "positive_momentum", "passed": momentum > 0},
        {
            "key": "rsi_not_extreme",
            "passed": rsi is not None
            and float(config["rsi_floor"]) <= rsi <= float(config["rsi_ceiling"]),
        },
    ]
    volume_ratio = None
    current_volume = volumes[index] if volumes is not None and index >= 20 else None
    if volumes is not None and current_volume is not None:
        history = [value for value in volumes[index - 20 : index] if value is not None]
        if history and _mean(history) > 0:
            volume_ratio = float(current_volume) / _mean(history)
            components.append(
                {
                    "key": "volume_confirmation",
                    "passed": volume_ratio >= float(config["volume_ratio_floor"]),
                }
            )
    score = sum(bool(item["passed"]) for item in components) / len(components)
    return {
        "triggered": score >= 0.75,
        "score": round(score, 4),
        "components": components,
        "observed": {
            "short_average": short_average,
            "long_average": long_average,
            "momentum": momentum,
            "rsi": rsi,
            "volume_ratio": volume_ratio,
        },
    }


def _walk_forward_validation(
    dates: list[date],
    closes: list[float],
    *,
    volumes: list[float | None] | None,
    config: dict[str, Any],
    transaction_cost_bps: float,
) -> dict[str, Any]:
    horizon = int(config["horizon_sessions"])
    start = int(config["minimum_history"]) - 1
    stride = int(config["evaluation_stride"])
    candidates: list[dict[str, Any]] = []
    for index in range(start, len(closes) - horizon - 1, stride):
        signal = _signal_at(closes, volumes, index, config)
        entry_index = index + 1
        exit_index = min(index + horizon, len(closes) - 1)
        gross_return = closes[exit_index] / closes[entry_index] - 1
        candidates.append(
            {
                "decision_date": dates[index].isoformat(),
                "entry_date": dates[entry_index].isoformat(),
                "exit_date": dates[exit_index].isoformat(),
                "triggered": bool(signal["triggered"]),
                "gross_return": gross_return,
            }
        )
    split = max(1, int(len(candidates) * 0.7)) if candidates else 0
    train = candidates[:split]
    test = candidates[split:]
    signaled = [item for item in test if item["triggered"]]
    cost = transaction_cost_bps / 10_000
    strategy_returns = [float(item["gross_return"]) - cost for item in signaled]
    baseline_returns = [float(item["gross_return"]) for item in test]
    mean_strategy = _mean(strategy_returns) if strategy_returns else None
    mean_baseline = _mean(baseline_returns) if baseline_returns else None
    overlap = stride < horizon
    minimum_tests = 5 if horizon <= 10 else 3
    if len(test) < minimum_tests or len(signaled) < max(1, minimum_tests // 2):
        status = "insufficient_out_of_sample"
    elif mean_strategy is not None and mean_baseline is not None and mean_strategy > mean_baseline:
        status = "out_of_sample_positive"
    else:
        status = "out_of_sample_negative"
    return {
        "type": "chronological_walk_forward_forecast_backtest",
        "start_date": dates[start].isoformat() if len(dates) > start else None,
        "end_date": dates[-1].isoformat() if dates else None,
        "train_end_date": train[-1]["decision_date"] if train else None,
        "train_observations": len(train),
        "test_observations": len(test),
        "test_signals": len(signaled),
        "transaction_cost_bps": transaction_cost_bps,
        "mean_strategy_return": mean_strategy,
        "mean_baseline_return": mean_baseline,
        "excess_mean_return": (
            mean_strategy - mean_baseline
            if mean_strategy is not None and mean_baseline is not None
            else None
        ),
        "hit_rate": (
            sum(value > 0 for value in strategy_returns) / len(strategy_returns)
            if strategy_returns
            else None
        ),
        "evaluation_stride_sessions": stride,
        "overlapping_forward_windows": overlap,
        "status": status,
        "leakage_guard": (
            "Every decision uses data through close t only; modeled entry is close "
            "t+1; chronological 70/30 split; parameters remain frozen at model version."
        ),
        "limitations": [
            (
                "Forecast returns use retained daily closes and do not model intraday "
                "fills, taxes, market impact or borrow constraints."
            ),
            (
                "Forward windows overlap, so mean return and hit rate are forecast "
                "diagnostics, not a compounded portfolio return."
                if overlap
                else (
                    "Forward windows do not overlap; transaction cost is still a "
                    "simplified round-trip assumption."
                )
            ),
            "Historical performance is not evidence of future profitability.",
        ],
    }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _rsi(values: list[float], period: int) -> float | None:
    if len(values) <= period:
        return None
    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    recent = changes[-period:]
    gains = sum(max(change, 0) for change in recent) / period
    losses = sum(max(-change, 0) for change in recent) / period
    if losses == 0:
        return 100.0
    relative_strength = gains / losses
    return 100 - 100 / (1 + relative_strength)


def _annualized_volatility(values: list[float]) -> float | None:
    if len(values) < 3:
        return None
    returns = [
        math.log(values[index] / values[index - 1])
        for index in range(1, len(values))
        if values[index] > 0 and values[index - 1] > 0
    ]
    if len(returns) < 2:
        return None
    average = _mean(returns)
    variance = sum((value - average) ** 2 for value in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(252)
