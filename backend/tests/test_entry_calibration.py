from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db import models as _models  # noqa: F401
from app.db.base import Base
from app.db.models import (
    EntryCalibrationRun,
    EntryHorizonForecast,
    EntryHorizonOutcome,
    EntryOutcomeEvaluation,
    EntryParameterCandidate,
    EntryParameterCandidateReview,
    MarketDailyBar,
    MarketSeries,
    ResearchInquiry,
)
from app.entry_calibration import evaluate_threshold_candidate, run_entry_calibration
from app.entry_review_import import import_candidate_reviews
from app.storage.archive import ColdArchive


def test_daily_calibration_is_idempotent_and_outcomes_are_append_only(tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    started = date(2023, 1, 2)
    observed = datetime(2026, 9, 13, 12, tzinfo=UTC)
    with Session(engine, expire_on_commit=False) as session:
        session.add(
            MarketSeries(
                series_id="EQ:AAPL",
                name="Apple adjusted close",
                category="equity_price",
                unit="USD",
                frequency="daily",
                source_name="test",
                source_url="https://example.com",
                listing_status="active",
            )
        )
        dates: list[date] = []
        for index in range(800):
            observed_on = started + timedelta(days=index)
            dates.append(observed_on)
            close = 100 + index * 0.1
            session.add(
                MarketDailyBar(
                    series_id="EQ:AAPL",
                    observed_on=observed_on,
                    open_price=close - 0.05,
                    high_price=close + 0.1,
                    low_price=close - 0.1,
                    close_price=close,
                    volume=1_000_000,
                    adjustment="splits",
                    source_name="test",
                    source_url="https://example.com",
                    fetched_at=observed,
                )
            )
        snapshot = {
            "equity_research_context": {
                "market_region": "us",
                "ticker": "AAPL",
                "price_series_id": "EQ:AAPL",
                "point_in_time_cutoff": dates[520].isoformat(),
                "financial_trend_status": "point_in_time_annual_trend_available",
            },
            "derived_equity_evidence": [],
        }
        for suffix in ("one", "duplicate"):
            session.add(
                ResearchInquiry(
                    question=f"AAPL {suffix}",
                    mode="user_question",
                    status="completed",
                    local_model="test",
                    result={},
                    evidence_snapshot=snapshot,
                )
            )
        session.commit()

        archive = ColdArchive(
            tmp_path,
            min_free_bytes=0,
            max_used_percent=99,
            disk_usage_provider=lambda _: (10_000_000, 0, 10_000_000),
        )
        settings = Settings(
            cold_data_root=tmp_path,
            cold_archive_min_free_gb=1,
            cold_archive_max_used_percent=99,
        )
        first = run_entry_calibration(session, settings=settings, now=observed, archive=archive)
        session.commit()

        assert first["reports_scanned"] == 1
        assert first["forecasts_created"] == 8
        assert first["outcomes_settled"] == 4
        assert first["evaluations_created"] == 4
        assert first["daily_company_universe"] == 1
        assert first["daily_company_snapshots_created"] == 1
        assert first["daily_company_snapshots_covered"] == 1
        assert first["daily_company_insufficient_history"] == 0
        forecasts = list(session.scalars(select(EntryHorizonForecast)))
        outcomes = list(session.scalars(select(EntryHorizonOutcome)))
        evaluations = list(session.scalars(select(EntryOutcomeEvaluation)))
        original_fingerprints = [item.outcome_fingerprint for item in outcomes]
        assert len(forecasts) == 8
        assert all(
            item.forecast_payload["validation"]["status"] == "daily_snapshot_only"
            for item in forecasts
            if item.source_inquiry_id is None
        )
        assert len(outcomes) == len(evaluations) == 4
        assert all(item.input_fingerprint for item in forecasts)
        assert all(item.benchmark_coverage == "unavailable" for item in evaluations)

        second = run_entry_calibration(
            session,
            settings=settings,
            now=observed + timedelta(days=1),
            archive=archive,
        )
        session.commit()

        assert second["forecasts_created"] == 0
        assert second["daily_company_snapshots_created"] == 0
        assert second["daily_company_snapshots_covered"] == 1
        assert second["outcomes_settled"] == 0
        assert second["evaluations_created"] == 0
        assert (
            session.scalar(
                select(EntryCalibrationRun).order_by(EntryCalibrationRun.id.desc())
            ).status
            == "completed"
        )
        assert [
            item.outcome_fingerprint
            for item in session.scalars(
                select(EntryHorizonOutcome).order_by(EntryHorizonOutcome.id)
            )
        ] == original_fingerprints


def test_candidate_requires_samples_and_review_gate() -> None:
    collecting = evaluate_threshold_candidate(
        [
            {
                "report_cutoff": f"2026-01-{index + 1:02d}",
                "ticker": "AAPL",
                "score": 1.0,
                "net_return": 0.01,
            }
            for index in range(10)
        ],
        minimum_signals=30,
    )
    assert collecting["status"] == "collecting"
    assert collecting["matured_base_signals"] == 10

    samples = [
        {
            "report_cutoff": (date(2025, 1, 1) + timedelta(days=index)).isoformat(),
            "ticker": f"T{index:02d}",
            "score": 1.0 if index % 2 else 0.8,
            "net_return": 0.03 if index % 2 else -0.02,
        }
        for index in range(60)
    ]
    candidate = evaluate_threshold_candidate(samples, minimum_signals=30)

    assert candidate["status"] == "ready_for_review"
    assert candidate["chosen_threshold"] == 1.0
    assert candidate["human_review_required"] is True
    assert candidate["production_model_changed"] is False
    assert candidate["base_test"]["forecast_sequence_max_drawdown"] is not None


def test_candidate_gate_counts_overlapping_exposures_once() -> None:
    samples = [
        {
            "report_cutoff": "2026-09-01",
            "entry_date": "2026-09-02",
            "exit_date": "2026-09-04",
            "ticker": ticker,
            "score": 1.0,
            "net_return": 0.01,
            "excess_net_return": 0.005,
            "sector_excess_net_return": 0.004,
        }
        for ticker in ("AAPL", "AMD", "MSFT", "MU", "NVDA", "TSLA")
    ]

    candidate = evaluate_threshold_candidate(samples, minimum_signals=10)

    assert candidate["raw_matured_base_signals"] == 6
    assert candidate["matured_base_signals"] == 1
    assert candidate["independence_policy"] == ("overlapping_calendar_windows_equal_weighted_once")


def test_candidate_review_import_is_idempotent_and_does_not_promote() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    created = datetime(2026, 9, 13, 12, tzinfo=UTC)
    with Session(engine, expire_on_commit=False) as session:
        candidate = EntryParameterCandidate(
            base_model_version="entry_horizon_walk_forward_v1",
            candidate_version="entry_horizon_candidate_v2_ultra_short_test",
            horizon_key="ultra_short",
            status="ready_for_review",
            sample_fingerprint="a" * 64,
            sample_count=60,
            parameter_changes={"signal_score_threshold": 0.8},
            comparison_metrics={},
            created_at=created,
            updated_at=created,
        )
        session.add(candidate)
        session.commit()
        payload = {
            "reviews": [
                {
                    "id": "review-1",
                    "report_id": (
                        "entry-candidate:entry_horizon_walk_forward_v1:"
                        "entry_horizon_candidate_v2_ultra_short_test"
                    ),
                    "decision": "revise",
                    "comment": "Require stronger risk-off evidence.",
                    "confidence": 80,
                    "created_at": "2026-09-13T12:30:00Z",
                }
            ]
        }

        first = import_candidate_reviews(session, payload)
        session.commit()
        second = import_candidate_reviews(session, payload)
        session.commit()

        assert first["records_imported"] == 1
        assert second["duplicates_skipped"] == 1
        assert session.scalar(select(EntryParameterCandidateReview)).decision == "revise"
        assert session.get(EntryParameterCandidate, candidate.id).status == "ready_for_review"
