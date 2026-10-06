"""Durable prospective validation for factors that survive repeated backtests."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from statistics import fmean
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    FactorExperiment,
    FactorExperimentOutcome,
    MarketObservation,
)
from app.schemas.research import (
    FactorExperimentGroupView,
    FactorExperimentSettlementView,
    FactorExperimentStatusView,
    FactorExperimentView,
    ModelFactorResearch,
)

FACTOR_EXPERIMENT_POLICY = "factor_future_outcome_v1_frozen"


def register_factor_experiments(
    session: Session,
    *,
    research: ModelFactorResearch,
    inquiry_id: int,
) -> int:
    """Freeze only repeatedly replicated factor rules for future evaluation."""
    created = 0
    for validation in research.profit_validations:
        replication = validation.replication
        if (
            replication is None
            or replication.retention_status != "provisional_retained"
            or replication.future_validation_status != "pending"
            or replication.prospective_anchor_date is None
            or not replication.prospective_factor_ids
            or replication.prospective_position == "unavailable"
        ):
            continue
        anchor = datetime.fromisoformat(replication.prospective_anchor_date).date()
        anchor_value = session.scalar(
            select(MarketObservation.value).where(
                MarketObservation.series_id == validation.target_series_id,
                MarketObservation.observed_on == anchor,
            )
        )
        if anchor_value is None or abs(float(anchor_value)) <= 1e-12:
            continue
        fingerprint = _fingerprint(
            {
                "target_series_id": validation.target_series_id,
                "horizon": validation.forecast_horizon_days,
                "anchor": anchor.isoformat(),
                "factor_ids": sorted(replication.prospective_factor_ids),
                "position": replication.prospective_position,
                "method_version": research.method_version,
                "protocol_version": replication.protocol_version,
            }
        )
        exists = session.scalar(
            select(FactorExperiment.id).where(
                FactorExperiment.input_fingerprint == fingerprint
            )
        )
        if exists is not None:
            continue
        session.add(
            FactorExperiment(
                source_inquiry_id=inquiry_id,
                target_series_id=validation.target_series_id,
                target_name=validation.target_name,
                method_version=research.method_version,
                protocol_version=replication.protocol_version,
                forecast_horizon_observations=validation.forecast_horizon_days,
                factor_ids=replication.prospective_factor_ids,
                replication_summary=replication.model_dump(mode="json"),
                anchor_observed_on=anchor,
                anchor_value=float(anchor_value),
                predicted_position=(
                    1 if replication.prospective_position == "long" else -1
                ),
                transaction_cost_bps=max(validation.transaction_cost_bps, 25.0),
                status="pending",
                input_fingerprint=fingerprint,
            )
        )
        created += 1
    return created


def settle_factor_experiments(session: Session) -> FactorExperimentSettlementView:
    """Insert immutable outcomes only after the required future observations exist."""
    experiments = list(
        session.scalars(
            select(FactorExperiment)
            .options(selectinload(FactorExperiment.outcome))
            .where(FactorExperiment.status == "pending")
            .order_by(FactorExperiment.anchor_observed_on, FactorExperiment.id)
        )
    )
    settled = 0
    for experiment in experiments:
        observations = list(
            session.execute(
                select(MarketObservation.observed_on, MarketObservation.value)
                .where(
                    MarketObservation.series_id == experiment.target_series_id,
                    MarketObservation.observed_on > experiment.anchor_observed_on,
                )
                .order_by(MarketObservation.observed_on)
                .limit(experiment.forecast_horizon_observations)
            )
        )
        if len(observations) < experiment.forecast_horizon_observations:
            continue
        outcome_on, outcome_value = observations[-1]
        raw_return = float(outcome_value) / experiment.anchor_value - 1.0
        strategy_return = (
            experiment.predicted_position * raw_return
            - experiment.transaction_cost_bps / 10_000
        )
        prediction_correct = experiment.predicted_position * raw_return > 0
        fingerprint = _fingerprint(
            {
                "experiment": experiment.input_fingerprint,
                "outcome_on": outcome_on.isoformat(),
                "outcome_value": float(outcome_value),
                "policy": FACTOR_EXPERIMENT_POLICY,
            }
        )
        experiment.outcome = FactorExperimentOutcome(
            outcome_observed_on=outcome_on,
            outcome_value=float(outcome_value),
            raw_return=raw_return,
            strategy_return=strategy_return,
            prediction_correct=prediction_correct,
            outcome_fingerprint=fingerprint,
        )
        experiment.status = "future_validated" if prediction_correct else "future_failed"
        settled += 1
    session.flush()
    return FactorExperimentSettlementView(
        scanned=len(experiments),
        settled=settled,
        still_pending=len(experiments) - settled,
    )


def factor_experiment_status(
    session: Session,
    *,
    limit: int = 40,
) -> FactorExperimentStatusView:
    """Return a bounded audit view over frozen and matured experiments."""
    total = int(session.scalar(select(func.count(FactorExperiment.id))) or 0)
    counts = dict(
        session.execute(
            select(FactorExperiment.status, func.count(FactorExperiment.id)).group_by(
                FactorExperiment.status
            )
        ).all()
    )
    rows = list(
        session.scalars(
            select(FactorExperiment)
            .options(selectinload(FactorExperiment.outcome))
            .order_by(FactorExperiment.frozen_at.desc(), FactorExperiment.id.desc())
            .limit(limit)
        )
    )
    grouped: dict[
        tuple[str, str, str, int, tuple[str, ...]], list[FactorExperiment]
    ] = defaultdict(list)
    for row in session.scalars(
        select(FactorExperiment)
        .options(selectinload(FactorExperiment.outcome))
        .order_by(FactorExperiment.id)
    ):
        grouped[
            (
                row.target_series_id,
                row.method_version,
                row.protocol_version,
                row.forecast_horizon_observations,
                tuple(sorted(str(item) for item in row.factor_ids)),
            )
        ].append(row)
    groups: list[FactorExperimentGroupView] = []
    for (
        target_series_id,
        method_version,
        protocol_version,
        horizon,
        factor_ids,
    ), experiments in grouped.items():
        matured = [item for item in experiments if item.outcome is not None]
        passed = [item for item in matured if item.outcome and item.outcome.prediction_correct]
        if not matured:
            reliability = "awaiting_future_samples"
        elif len(matured) < 3:
            reliability = "insufficient_future_samples"
        elif len(passed) / len(matured) >= 2 / 3 and fmean(
            item.outcome.strategy_return for item in matured if item.outcome
        ) > 0:
            reliability = "prospectively_retained"
        else:
            reliability = "prospectively_rejected"
        groups.append(
            FactorExperimentGroupView(
                target_series_id=target_series_id,
                method_version=method_version,
                protocol_version=protocol_version,
                forecast_horizon_observations=horizon,
                factor_ids=list(factor_ids),
                experiments=len(experiments),
                pending=sum(item.status == "pending" for item in experiments),
                matured=len(matured),
                passed=len(passed),
                prospective_hit_rate=(len(passed) / len(matured) if matured else None),
                mean_strategy_return=(
                    fmean(item.outcome.strategy_return for item in matured if item.outcome)
                    if matured
                    else None
                ),
                reliability_status=reliability,
            )
        )
    groups.sort(key=lambda item: (item.matured, item.experiments), reverse=True)
    return FactorExperimentStatusView(
        generated_at=datetime.now(UTC),
        total_experiments=total,
        pending_experiments=int(counts.get("pending", 0)),
        future_validated=int(counts.get("future_validated", 0)),
        future_failed=int(counts.get("future_failed", 0)),
        groups=groups[:40],
        recent_experiments=[_experiment_view(row) for row in rows],
        methodology=(
            "Only rules that pass at least three non-overlapping, FDR-screened, "
            "cost-adjusted replications are frozen. Future outcomes are append-only; "
            "three or more identical prospective cohorts are required before a rule "
            "can be prospectively retained."
        ),
    )


def _experiment_view(row: FactorExperiment) -> FactorExperimentView:
    outcome = row.outcome
    return FactorExperimentView(
        id=row.id,
        source_inquiry_id=row.source_inquiry_id,
        target_series_id=row.target_series_id,
        target_name=row.target_name,
        method_version=row.method_version,
        protocol_version=row.protocol_version,
        forecast_horizon_observations=row.forecast_horizon_observations,
        factor_ids=[str(item) for item in row.factor_ids],
        replication_summary=row.replication_summary,
        anchor_observed_on=row.anchor_observed_on.isoformat(),
        anchor_value=row.anchor_value,
        predicted_position="long" if row.predicted_position > 0 else "short",
        transaction_cost_bps=row.transaction_cost_bps,
        status=row.status,
        outcome_observed_on=(outcome.outcome_observed_on.isoformat() if outcome else None),
        raw_return=outcome.raw_return if outcome else None,
        strategy_return=outcome.strategy_return if outcome else None,
        prediction_correct=outcome.prediction_correct if outcome else None,
        frozen_at=row.frozen_at,
    )


def _fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
