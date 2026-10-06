"""Deterministic quality gates for locally retained numerical observations."""

from __future__ import annotations

import math
from datetime import date
from itertools import pairwise

from app.db.models import MarketObservation, MarketSeries
from app.schemas.data_audit import SeriesQualityView

PRICE_CATEGORY_TERMS = ("price",)
PRICE_NAME_TERMS = ("price", "close", "价格", "收盘")


def is_price_like(series: MarketSeries) -> bool:
    text = f"{series.category} {series.name}".casefold()
    return any(term in text for term in (*PRICE_CATEGORY_TERMS, *PRICE_NAME_TERMS))


def valid_market_rows(
    series: MarketSeries,
    rows: list[MarketObservation],
) -> tuple[list[MarketObservation], int]:
    """Remove values that cannot be valid observations for the series identity."""
    price_like = is_price_like(series)
    valid: list[MarketObservation] = []
    invalid_count = 0
    for row in rows:
        value = float(row.value)
        if not math.isfinite(value) or (price_like and value <= 0):
            invalid_count += 1
            continue
        valid.append(row)
    return valid, invalid_count


def audit_market_rows(
    series: MarketSeries,
    rows: list[MarketObservation],
    *,
    window_start: date,
    window_end: date,
) -> SeriesQualityView:
    """Score coverage, endpoint validity, staleness, flatlines and jumps."""
    ordered = sorted(rows, key=lambda row: row.observed_on)
    valid, invalid_count = valid_market_rows(series, ordered)
    values = [float(row.value) for row in valid]
    expected = _expected_observations(series.frequency, window_start, window_end)
    coverage = min(len(valid) / max(expected, 1), 1.0)
    zero_count = sum(abs(float(row.value)) <= 1e-12 for row in ordered)
    unique_count = len({round(value, 12) for value in values})
    changes = [
        abs(current / previous - 1)
        for previous, current in pairwise(values)
        if abs(previous) > 1e-12
    ]
    maximum_change = max(changes) if changes else None
    flags: list[str] = []
    if not ordered:
        flags.append("no_observations")
    if invalid_count:
        flags.append("invalid_or_nonpositive_price_values")
    if ordered and not valid:
        flags.append("no_valid_observations")
    if expected >= 8 and coverage < 0.35:
        flags.append("sparse_window_coverage")
    if is_price_like(series) and len(valid) >= 5 and unique_count <= 1:
        flags.append("suspicious_flatline")
    if is_price_like(series) and maximum_change is not None and maximum_change > 3:
        flags.append("extreme_single_period_jump")
    if valid and _is_stale(series.frequency, valid[-1].observed_on, window_end):
        flags.append("stale_endpoint")
    severe = {
        "no_observations",
        "no_valid_observations",
        "suspicious_flatline",
        "invalid_or_nonpositive_price_values",
    }
    score = coverage
    if invalid_count:
        score *= max(0.0, 1 - invalid_count / max(len(ordered), 1))
    if "stale_endpoint" in flags:
        score *= 0.65
    if "suspicious_flatline" in flags:
        score *= 0.25
    if "extreme_single_period_jump" in flags:
        score *= 0.75
    minimum_valid_rows = 1 if _is_snapshot(series.frequency) else 2
    can_verify = (
        len(valid) >= minimum_valid_rows
        and coverage >= 0.2
        and not any(flag in severe for flag in flags)
    )
    return SeriesQualityView(
        series_id=series.series_id,
        name=series.name,
        category=series.category,
        source_name=series.source_name,
        unit=series.unit,
        frequency=series.frequency,
        window_start=window_start,
        window_end=window_end,
        first_observed_on=valid[0].observed_on if valid else None,
        last_observed_on=valid[-1].observed_on if valid else None,
        observation_count=len(valid),
        expected_observations=expected,
        coverage_ratio=round(coverage, 6),
        invalid_value_count=invalid_count,
        zero_value_count=zero_count,
        unique_value_count=unique_count,
        maximum_absolute_change_ratio=(
            round(maximum_change, 6) if maximum_change is not None else None
        ),
        quality_score=round(max(0.0, min(score, 1.0)), 6),
        can_verify_claims=can_verify,
        flags=flags,
    )


def _expected_observations(frequency: str | None, start: date, end: date) -> int:
    days = max((end - start).days + 1, 1)
    normalized = (frequency or "").casefold()
    if _is_snapshot(normalized):
        return 1
    if "day" in normalized or normalized == "d":
        return max(round(days * 5 / 7), 1)
    if "week" in normalized or normalized == "w":
        return max(round(days / 7), 1)
    if "quarter" in normalized or normalized == "q":
        return max(round(days / 91), 1)
    if "annual" in normalized or "year" in normalized or normalized == "a":
        return max(round(days / 365), 1)
    return max(round(days / 30), 1)


def _is_stale(frequency: str | None, last: date, end: date) -> bool:
    lag = max((end - last).days, 0)
    normalized = (frequency or "").casefold()
    if _is_snapshot(normalized):
        return lag > 45
    if "day" in normalized or normalized == "d":
        return lag > 10
    if "week" in normalized or normalized == "w":
        return lag > 28
    if "quarter" in normalized or normalized == "q":
        return lag > 150
    if "annual" in normalized or "year" in normalized or normalized == "a":
        return lag > 550
    return lag > 62


def _is_snapshot(frequency: str | None) -> bool:
    normalized = (frequency or "").casefold()
    return normalized in {"snapshot", "point_in_time", "point-in-time"}
