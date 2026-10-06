"""Frozen factor rules must wait for genuinely unseen market observations."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    FactorExperiment,
    MarketObservation,
    MarketSeries,
    ResearchInquiry,
)
from app.factor_experiments import (
    factor_experiment_status,
    register_factor_experiments,
    settle_factor_experiments,
)
from app.schemas.research import (
    ModelFactorReplication,
    ModelFactorResearch,
    ModelProfitValidation,
)


def _replicated_research(anchor: date) -> ModelFactorResearch:
    replication = ModelFactorReplication(
        protocol_version="factor_replication_v1_nonoverlap_fdr",
        trials=[],
        total_trials=4,
        valid_trials=4,
        passed_trials=4,
        pass_rate=1.0,
        median_excess_return=0.04,
        pooled_mean_excess_return=0.01,
        pooled_excess_ci_low=0.003,
        pooled_excess_ci_high=0.017,
        stable_factor_ids=["market:PRED1:change5"],
        retention_status="provisional_retained",
        retention_reason="Four independent windows passed the frozen rule.",
        prospective_anchor_date=anchor.isoformat(),
        prospective_factor_ids=["market:PRED1:change5"],
        prospective_position="long",
        future_validation_status="pending",
        leakage_guard="No observation after the anchor can change this rule.",
    )
    validation = ModelProfitValidation(
        target_series_id="TEST_FUTURE",
        target_name="Future Test Equity",
        factor_ids=["market:PRED1:change5"],
        start_date="2020-01-01",
        end_date=anchor.isoformat(),
        train_end_date="2024-01-01",
        forecast_horizon_days=2,
        train_observations=80,
        test_observations=32,
        transaction_cost_bps=25,
        baseline_return=0.02,
        strategy_return=0.08,
        excess_return=0.06,
        hit_rate=0.7,
        max_drawdown=-0.05,
        sharpe_like=1.1,
        status="out_of_sample_positive",
        signal_rule="Use only the frozen long signal.",
        leakage_guard="Chronological split with no future inputs.",
        limitations=["Exploratory until prospective cohorts mature."],
        replication=replication,
    )
    return ModelFactorResearch(
        generated_at=datetime.now(UTC),
        linear_chain_retained=True,
        factors=[],
        nonlinear_links=[],
        profit_validations=[validation],
        archive_status="not_configured",
        research_caveat="Research evidence only; this is not a trading instruction.",
    )


def test_future_factor_outcome_is_registered_once_and_settled_once() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    anchor = date(2026, 9, 1)
    with Session(engine) as session:
        inquiry = ResearchInquiry(
            question="Does the frozen factor survive future data?",
            mode="autonomous",
            status="completed",
            local_model="test-model",
            evidence_snapshot={},
        )
        session.add_all(
            [
                inquiry,
                MarketSeries(
                    series_id="TEST_FUTURE",
                    name="Future Test Equity",
                    category="equity_price",
                    unit="dollars",
                    frequency="daily",
                    source_name="Test",
                    source_url="https://example.test/future",
                ),
            ]
        )
        session.flush()
        session.add(
            MarketObservation(
                series_id="TEST_FUTURE",
                observed_on=anchor,
                value=100,
                fetched_at=datetime.now(UTC),
            )
        )
        session.flush()

        research = _replicated_research(anchor)
        assert register_factor_experiments(
            session, research=research, inquiry_id=inquiry.id
        ) == 1
        session.flush()
        assert register_factor_experiments(
            session, research=research, inquiry_id=inquiry.id
        ) == 0
        assert settle_factor_experiments(session).settled == 0

        session.add(
            MarketObservation(
                series_id="TEST_FUTURE",
                observed_on=anchor + timedelta(days=1),
                value=101,
                fetched_at=datetime.now(UTC),
            )
        )
        session.flush()
        first_wait = settle_factor_experiments(session)
        assert first_wait.settled == 0
        assert first_wait.still_pending == 1

        session.add(
            MarketObservation(
                series_id="TEST_FUTURE",
                observed_on=anchor + timedelta(days=2),
                value=104,
                fetched_at=datetime.now(UTC),
            )
        )
        session.flush()
        settled = settle_factor_experiments(session)
        assert settled.settled == 1
        experiment = session.scalar(select(FactorExperiment))
        assert experiment is not None
        assert experiment.status == "future_validated"
        assert experiment.outcome is not None
        assert experiment.outcome.outcome_observed_on == anchor + timedelta(days=2)
        assert experiment.outcome.strategy_return == pytest.approx(0.0375)
        outcome_fingerprint = experiment.outcome.outcome_fingerprint

        session.add(
            MarketObservation(
                series_id="TEST_FUTURE",
                observed_on=anchor + timedelta(days=3),
                value=60,
                fetched_at=datetime.now(UTC),
            )
        )
        session.flush()
        assert settle_factor_experiments(session).scanned == 0
        session.refresh(experiment)
        assert experiment.outcome is not None
        assert experiment.outcome.outcome_fingerprint == outcome_fingerprint
        assert experiment.outcome.outcome_value == 104

        status = factor_experiment_status(session)
        assert status.total_experiments == 1
        assert status.future_validated == 1
        assert status.groups[0].reliability_status == "insufficient_future_samples"
