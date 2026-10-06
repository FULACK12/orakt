"""Auditable economic-cycle models derived from retained FRED observations."""

from __future__ import annotations

from datetime import UTC, datetime
from statistics import mean
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import MarketObservation
from app.schemas.cycle_models import (
    CycleModelSuiteResponse,
    CycleModelView,
    CycleSignalView,
)


def build_cycle_model_suite(session: Session) -> CycleModelSuiteResponse:
    """Evaluate several distinct theories without presenting any as certainty."""
    series_ids = {
        "SAHMREALTIME",
        "T10Y2Y",
        "INDPRO",
        "BUSINV",
        "ISRATIO",
        "DGORDER",
        "HOUST",
        "PERMIT",
        "MORTGAGE30US",
        "BAMLH0A0HYM2",
        "NFCI",
        "TDSP",
        "PCEPILFE",
        "GDPC1",
        "GDPPOT",
        "DFF",
        "CFNAI",
        "PAYEMS",
        "M2SL",
        "TCU",
    }
    values = {
        series_id: _series_values(session, series_id, limit=20)
        for series_id in series_ids
    }
    models = [
        _sahm_model(values),
        _yield_curve_model(values),
        _kitchin_model(values),
        _housing_model(values),
        _financial_cycle_model(values),
        _taylor_model(values),
        _coincident_model(values),
        _liquidity_model(values),
    ]
    observed_dates = [
        signal.observed_on
        for model in models
        for signal in model.signals
        if signal.observed_on
    ]
    return CycleModelSuiteResponse(
        generated_at=datetime.now(UTC),
        as_of=max(observed_dates) if observed_dates else None,
        models=models,
    )


def _sahm_model(values: dict[str, list[dict[str, Any]]]) -> CycleModelView:
    latest = _latest(values["SAHMREALTIME"])
    score = _bounded((0.5 - latest) / 0.5) if latest is not None else 0.0
    return _model(
        key="sahm_rule",
        name="Sahm Rule recession signal",
        theory=(
            "A rapid rise in the three-month unemployment average relative to its "
            "prior twelve-month low is a coincident recession signal."
        ),
        horizon="coincident to 3 months",
        scores=[score] if latest is not None else [],
        signals=[
            _signal(
                values,
                "SAHMREALTIME",
                "Real-time Sahm Rule",
                score,
            )
        ],
        required=["SAHMREALTIME"],
        caveats=[
            "A 0.50 percentage-point threshold is a signal, not an official NBER call.",
            "Labour-market revisions can change the historical reading.",
        ],
    )


def _yield_curve_model(values: dict[str, list[dict[str, Any]]]) -> CycleModelView:
    latest = _latest(values["T10Y2Y"])
    score = _bounded(latest / 1.25) if latest is not None else 0.0
    return _model(
        key="yield_curve",
        name="Yield-curve leading signal",
        theory=(
            "A sustained 10-year/2-year inversion can precede weaker activity as "
            "expected future short rates fall and bank intermediation tightens."
        ),
        horizon="6 to 24 months",
        scores=[score] if latest is not None else [],
        signals=[_signal(values, "T10Y2Y", "10Y minus 2Y Treasury", score, periods=6)],
        required=["T10Y2Y"],
        caveats=[
            "Term premia and central-bank balance sheets can distort the curve.",
            "Re-steepening after inversion may occur near, not after, the downturn.",
        ],
    )


def _kitchin_model(values: dict[str, list[dict[str, Any]]]) -> CycleModelView:
    industrial = _growth(values["INDPRO"], 12)
    orders = _growth(values["DGORDER"], 12)
    inventory_ratio_change = _change(values["ISRATIO"], 12)
    scores = [
        _bounded((industrial or 0.0) / 5.0),
        _bounded((orders or 0.0) / 10.0),
        _bounded(-(inventory_ratio_change or 0.0) / 0.15),
    ]
    return _model(
        key="kitchin_inventory",
        name="Kitchin inventory-cycle proxy",
        theory=(
            "Short business cycles can emerge as new orders, production and "
            "inventories adjust with different lags."
        ),
        horizon="6 to 18 months",
        scores=scores,
        signals=[
            _signal(values, "INDPRO", "Industrial production YoY", scores[0], growth=12),
            _signal(values, "DGORDER", "Durable-goods orders YoY", scores[1], growth=12),
            _signal(
                values,
                "ISRATIO",
                "Inventory-to-sales ratio change",
                scores[2],
                periods=12,
            ),
        ],
        required=["INDPRO", "DGORDER", "ISRATIO"],
        caveats=[
            "This is a transparent proxy, not a direct estimate of Kitchin's original cycle.",
            "Pandemic and supply-chain disruptions can break normal inventory lags.",
        ],
    )


def _housing_model(values: dict[str, list[dict[str, Any]]]) -> CycleModelView:
    starts = _growth(values["HOUST"], 12)
    permits = _growth(values["PERMIT"], 12)
    mortgage_change = _change(values["MORTGAGE30US"], 12)
    scores = [
        _bounded((starts or 0.0) / 15.0),
        _bounded((permits or 0.0) / 15.0),
        _bounded(-(mortgage_change or 0.0) / 2.0),
    ]
    return _model(
        key="housing_leading",
        name="Housing leading-cycle proxy",
        theory=(
            "Permits and starts often lead residential investment, employment and "
            "interest-sensitive household demand."
        ),
        horizon="3 to 18 months",
        scores=scores,
        signals=[
            _signal(values, "HOUST", "Housing starts YoY", scores[0], growth=12),
            _signal(values, "PERMIT", "Building permits YoY", scores[1], growth=12),
            _signal(
                values,
                "MORTGAGE30US",
                "30Y mortgage-rate change",
                scores[2],
                periods=12,
            ),
        ],
        required=["HOUST", "PERMIT", "MORTGAGE30US"],
        caveats=[
            "Regional supply constraints and demographics can dominate national rates.",
            "Starts, completions and sales operate with different lags.",
        ],
    )


def _financial_cycle_model(
    values: dict[str, list[dict[str, Any]]],
) -> CycleModelView:
    credit = _latest(values["BAMLH0A0HYM2"])
    conditions = _latest(values["NFCI"])
    debt_service = _latest(values["TDSP"])
    scores = [
        _bounded((4.5 - credit) / 2.5) if credit is not None else 0.0,
        _bounded(-conditions) if conditions is not None else 0.0,
        _bounded((12.0 - debt_service) / 4.0) if debt_service is not None else 0.0,
    ]
    return _model(
        key="financial_cycle",
        name="Credit and financial-cycle proxy",
        theory=(
            "Credit spreads, broad financial conditions and household debt service "
            "measure the ease of financing and balance-sheet pressure."
        ),
        horizon="3 to 24 months",
        scores=scores,
        signals=[
            _signal(values, "BAMLH0A0HYM2", "High-yield OAS", scores[0]),
            _signal(values, "NFCI", "Chicago Fed NFCI", scores[1]),
            _signal(values, "TDSP", "Household debt-service ratio", scores[2]),
        ],
        required=["BAMLH0A0HYM2", "NFCI", "TDSP"],
        caveats=[
            "Asset valuations and private-credit conditions are not fully captured.",
            "Low spreads can reflect resilience or late-cycle risk appetite.",
        ],
    )


def _taylor_model(values: dict[str, list[dict[str, Any]]]) -> CycleModelView:
    inflation = _growth(values["PCEPILFE"], 12)
    real_gdp = _latest(values["GDPC1"])
    potential = _latest(values["GDPPOT"])
    policy_rate = _latest(values["DFF"])
    output_gap = (
        ((real_gdp / potential) - 1) * 100
        if real_gdp is not None and potential is not None and potential != 0
        else None
    )
    taylor_rate = (
        0.5 + inflation + 0.5 * (inflation - 2.0) + 0.5 * output_gap
        if inflation is not None and output_gap is not None
        else None
    )
    policy_gap = (
        policy_rate - taylor_rate
        if policy_rate is not None and taylor_rate is not None
        else None
    )
    score = _bounded(-(policy_gap or 0.0) / 3.0)
    return _model(
        key="taylor_policy_gap",
        name="Taylor-style policy-gap model",
        theory=(
            "A rules-based policy benchmark combines core inflation and the real "
            "output gap; the actual-rate gap indicates relative restraint or support."
        ),
        horizon="6 to 18 months",
        scores=[score] if policy_gap is not None else [],
        signals=[
            _custom_signal("PCEPILFE", "Core PCE inflation YoY", inflation),
            _custom_signal("GDPC1/GDPPOT", "Real output gap", output_gap),
            _custom_signal("DFF-Taylor", "Actual minus model policy rate", policy_gap, score),
        ],
        required=["PCEPILFE", "GDPC1", "GDPPOT", "DFF"],
        available=values,
        caveats=[
            "The neutral real rate is assumed at 0.5%; alternative estimates vary.",
            "This is a policy benchmark, not a Federal Reserve forecast.",
        ],
    )


def _coincident_model(values: dict[str, list[dict[str, Any]]]) -> CycleModelView:
    cfnai = _latest(values["CFNAI"])
    industrial = _growth(values["INDPRO"], 12)
    payrolls = _growth(values["PAYEMS"], 12)
    scores = [
        _bounded(cfnai or 0.0),
        _bounded((industrial or 0.0) / 5.0),
        _bounded((payrolls or 0.0) / 3.0),
    ]
    return _model(
        key="coincident_activity",
        name="Coincident real-activity model",
        theory=(
            "Broad activity, industrial output and payroll growth jointly describe "
            "the current real-economy regime."
        ),
        horizon="now to 6 months",
        scores=scores,
        signals=[
            _signal(values, "CFNAI", "Chicago Fed activity index", scores[0]),
            _signal(values, "INDPRO", "Industrial production YoY", scores[1], growth=12),
            _signal(values, "PAYEMS", "Nonfarm payrolls YoY", scores[2], growth=12),
        ],
        required=["CFNAI", "INDPRO", "PAYEMS"],
        caveats=["Coincident data are revised and are not reliable market-timing tools."],
    )


def _liquidity_model(values: dict[str, list[dict[str, Any]]]) -> CycleModelView:
    money_growth = _growth(values["M2SL"], 12)
    conditions = _latest(values["NFCI"])
    utilization = _latest(values["TCU"])
    scores = [
        _bounded((money_growth or 0.0) / 8.0),
        _bounded(-(conditions or 0.0)),
        _bounded(((utilization or 78.0) - 78.0) / 4.0),
    ]
    return _model(
        key="liquidity_capacity",
        name="Liquidity and capacity regime",
        theory=(
            "Money growth and financial conditions affect nominal demand, while "
            "capacity utilization indicates how readily supply can respond."
        ),
        horizon="6 to 18 months",
        scores=scores,
        signals=[
            _signal(values, "M2SL", "M2 money growth YoY", scores[0], growth=12),
            _signal(values, "NFCI", "Chicago Fed NFCI", scores[1]),
            _signal(values, "TCU", "Capacity utilization", scores[2]),
        ],
        required=["M2SL", "NFCI", "TCU"],
        caveats=[
            "Money demand shifts can weaken simple money-growth relationships.",
            "Financial conditions can reverse quickly with market repricing.",
        ],
    )


def _model(
    *,
    key: str,
    name: str,
    theory: str,
    horizon: str,
    scores: list[float],
    signals: list[CycleSignalView],
    required: list[str],
    caveats: list[str],
    available: dict[str, list[dict[str, Any]]] | None = None,
) -> CycleModelView:
    available_map = available or {
        signal.series_id: ([{}] if signal.value is not None else [])
        for signal in signals
    }
    missing = [
        series_id
        for series_id in required
        if not available_map.get(series_id)
    ]
    usable_scores = [
        signal.score
        for signal in signals
        if signal.value is not None
    ] or scores
    score = mean(usable_scores) if usable_scores else 0.0
    confidence = max(0.0, min(1.0, (len(required) - len(missing)) / len(required)))
    regime = (
        "insufficient_data"
        if confidence < 0.5
        else "expansion"
        if score >= 0.35
        else "contraction"
        if score <= -0.35
        else "transition"
    )
    return CycleModelView(
        key=key,
        name=name,
        theory=theory,
        horizon=horizon,
        regime=regime,
        score=round(_bounded(score), 4),
        confidence=round(confidence, 4),
        signals=signals,
        missing_series=missing,
        caveats=caveats,
    )


def _signal(
    values: dict[str, list[dict[str, Any]]],
    series_id: str,
    label: str,
    score: float,
    *,
    periods: int | None = None,
    growth: int | None = None,
) -> CycleSignalView:
    series = values[series_id]
    value = _growth(series, growth) if growth else _latest(series)
    change = _change(series, periods) if periods else None
    return CycleSignalView(
        series_id=series_id,
        label=label,
        value=round(value, 4) if value is not None else None,
        change=round(change, 4) if change is not None else None,
        score=round(_bounded(score), 4),
        observed_on=(str(series[-1]["observed_on"]) if series else None),
    )


def _custom_signal(
    series_id: str,
    label: str,
    value: float | None,
    score: float = 0.0,
) -> CycleSignalView:
    return CycleSignalView(
        series_id=series_id,
        label=label,
        value=round(value, 4) if value is not None else None,
        score=round(_bounded(score), 4),
    )


def _series_values(
    session: Session,
    series_id: str,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    rows = list(
        session.execute(
            select(
                MarketObservation.observed_on,
                MarketObservation.value,
            )
            .where(MarketObservation.series_id == series_id)
            .order_by(desc(MarketObservation.observed_on))
            .limit(limit)
        )
    )
    rows.reverse()
    return [
        {"observed_on": observed_on, "value": float(value)}
        for observed_on, value in rows
    ]


def _latest(values: list[dict[str, Any]]) -> float | None:
    return float(values[-1]["value"]) if values else None


def _change(
    values: list[dict[str, Any]],
    periods: int | None,
) -> float | None:
    if periods is None or len(values) <= periods:
        return None
    return float(values[-1]["value"]) - float(values[-periods - 1]["value"])


def _growth(
    values: list[dict[str, Any]],
    periods: int | None,
) -> float | None:
    if periods is None or len(values) <= periods:
        return None
    latest = float(values[-1]["value"])
    previous = float(values[-periods - 1]["value"])
    if previous == 0:
        return None
    return ((latest / previous) - 1.0) * 100


def _bounded(value: float) -> float:
    return max(-1.0, min(1.0, value))
