"""Daily, point-in-time settlement loop for versioned entry scenarios."""

from __future__ import annotations

import gzip
import hashlib
import json
import random
from bisect import bisect_right
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, defer, selectinload

from app.core.config import Settings
from app.db.models import (
    EntryCalibrationRun,
    EntryHorizonForecast,
    EntryHorizonOutcome,
    EntryOutcomeEvaluation,
    EntryParameterCandidate,
    MarketDailyBar,
    MarketObservation,
    MarketSeries,
    ResearchInquiry,
)
from app.horizon_backtest import HORIZON_CONFIGS, MODEL_VERSION, build_horizon_models
from app.storage.archive import ArchiveCapacityError, ColdArchive

OUTCOME_POLICY = "next_close_to_horizon_close_v1"
EVALUATION_POLICY = "benchmark_relative_path_v2_dual"
BASE_SIGNAL_THRESHOLD = 0.75
REVIEWED_THRESHOLD_GRID = (0.6, 2 / 3, 0.75, 0.8, 1.0)
BENCHMARK_SERIES_BY_REGION = {"us": "TD:SPY", "china": "TD:MCHI"}
US_SECTOR_BENCHMARKS = {
    "Technology": "TD:XLK",
    "Health care": "TD:XLV",
    "Financials": "TD:XLF",
    "Industrials": "TD:XLI",
    "Consumer": "TD:XLY",
    "Communication": "TD:XLC",
    "Consumer staples": "TD:XLP",
    "Materials": "TD:XLB",
    "Energy": "TD:XLE",
    "Real estate": "TD:XLRE",
    "Utilities": "TD:XLU",
}
HORIZON_KEYS = tuple(str(item["key"]) for item in HORIZON_CONFIGS)


def run_entry_calibration(
    session: Session,
    *,
    settings: Settings,
    now: datetime | None = None,
    archive: ColdArchive | None = None,
) -> dict[str, Any]:
    """Freeze new forecasts, settle matured outcomes, and prepare review candidates.

    Forecast inputs are never updated after insertion. Outcomes do not exist while
    pending and are inserted exactly once after the required future sessions exist.
    """
    observed_at = (now or datetime.now(UTC)).astimezone(UTC)
    run = EntryCalibrationRun(
        status="running",
        model_version=MODEL_VERSION,
        forecasts_created=0,
        outcomes_settled=0,
        pending_forecasts=0,
        summary={},
        archive_status="not_attempted",
        started_at=observed_at,
    )
    session.add(run)
    session.flush()

    previous_run = session.scalar(
        select(EntryCalibrationRun)
        .where(
            EntryCalibrationRun.id != run.id,
            EntryCalibrationRun.status.in_(("completed", "completed_archive_warning")),
        )
        .order_by(EntryCalibrationRun.id.desc())
        .limit(1)
    )
    previous_summary = (
        previous_run.summary if previous_run is not None and previous_run.summary else {}
    )
    report_watermark = int(previous_summary.get("research_inquiry_watermark_id") or 0)
    if previous_run is not None and report_watermark == 0:
        report_watermark = int(
            session.scalar(
                select(func.max(ResearchInquiry.id)).where(
                    ResearchInquiry.status == "completed",
                    ResearchInquiry.updated_at <= previous_run.completed_at,
                )
            )
            or 0
        )
    reports = _unique_equity_report_windows(
        session,
        after_id=report_watermark,
        updated_after=previous_run.completed_at if previous_run is not None else None,
    )
    current_report_watermark = int(
        session.scalar(
            select(func.max(ResearchInquiry.id)).where(ResearchInquiry.status == "completed")
        )
        or report_watermark
    )
    histories: dict[str, list[tuple[date, float, float | None]]] = {}
    forecasts_created = 0
    outcomes_settled = 0
    evaluations_created = 0
    skipped_reports = 0
    daily_companies_frozen = 0
    daily_companies_covered = 0
    daily_companies_insufficient_history = 0

    existing = {
        (row.series_id, row.report_cutoff, row.model_version, row.horizon_key): row
        for row in session.scalars(
            select(EntryHorizonForecast)
            .options(defer(EntryHorizonForecast.forecast_payload))
            .where(EntryHorizonForecast.model_version == MODEL_VERSION)
        )
    }
    for report in reports:
        context = report.evidence_snapshot.get("equity_research_context")
        if not isinstance(context, dict):
            skipped_reports += 1
            continue
        market_region = str(context.get("market_region") or "")
        ticker = str(context.get("ticker") or "").upper()
        sector = str(context.get("sector") or "") or None
        cutoff = _parse_date(context.get("point_in_time_cutoff"))
        if market_region not in {"us", "china"} or not ticker or cutoff is None:
            skipped_reports += 1
            continue
        series_id = str(
            context.get("price_series_id")
            or f"{'CN' if market_region == 'china' else 'EQ'}:{ticker}"
        )
        if all(
            (series_id, cutoff, MODEL_VERSION, horizon_key) in existing
            for horizon_key in HORIZON_KEYS
        ):
            continue
        full_history = _history_for(histories, session, series_id)
        retained = [item for item in full_history if item[0] <= cutoff]
        if len(retained) < 35:
            skipped_reports += 1
            continue
        dates = [item[0] for item in retained]
        closes = [item[1] for item in retained]
        volumes = (
            [item[2] for item in retained]
            if any(item[2] is not None for item in retained)
            else None
        )
        horizon_models = build_horizon_models(
            dates,
            closes,
            volumes=volumes,
            point_in_time_fundamentals=_has_point_in_time_fundamentals(report),
        )
        input_fingerprint = _fingerprint(
            {
                "series_id": series_id,
                "cutoff": cutoff.isoformat(),
                "dates": [item.isoformat() for item in dates],
                "closes": closes,
                "volumes": volumes,
                "model_version": MODEL_VERSION,
            }
        )
        for model in horizon_models["models"]:
            signal = model.get("current_signal")
            signal = signal if isinstance(signal, dict) else {}
            horizon_key = str(model["key"])
            identity = (series_id, cutoff, MODEL_VERSION, horizon_key)
            forecast = existing.get(identity)
            if forecast is None:
                forecast = EntryHorizonForecast(
                    source_inquiry_id=report.id,
                    market_region=market_region,
                    ticker=ticker,
                    series_id=series_id,
                    report_cutoff=cutoff,
                    model_version=MODEL_VERSION,
                    horizon_key=horizon_key,
                    horizon_sessions=int(model["horizon_sessions"]),
                    signal_triggered=bool(signal.get("triggered")),
                    signal_score=(
                        float(signal["score"]) if signal.get("score") is not None else None
                    ),
                    forecast_payload={
                        **model,
                        "calibration_context": {
                            "sector": sector,
                            "source_kind": "local_ai_research_report",
                        },
                    },
                    input_fingerprint=input_fingerprint,
                    created_at=observed_at,
                )
                session.add(forecast)
                existing[identity] = forecast
                forecasts_created += 1

    daily_targets = _daily_equity_targets(session)
    latest_equity_cutoffs = _latest_equity_cutoffs(session)
    for target in daily_targets:
        series_id = target["series_id"]
        latest_cutoff = latest_equity_cutoffs.get(series_id)
        if latest_cutoff is not None and all(
            (series_id, latest_cutoff, MODEL_VERSION, horizon_key) in existing
            for horizon_key in HORIZON_KEYS
        ):
            daily_companies_covered += 1
            continue
        full_history = _load_recent_history(session, series_id, limit=504)
        if len(full_history) < 35:
            daily_companies_insufficient_history += 1
            continue
        cutoff = full_history[-1][0]
        if all(
            (series_id, cutoff, MODEL_VERSION, horizon_key) in existing
            for horizon_key in HORIZON_KEYS
        ):
            daily_companies_covered += 1
            continue
        created_for_company = 0
        # Current signals require at most 504 retained sessions. Keeping the
        # complete multi-decade series here only enlarged fingerprints and JSON
        # payload preparation without changing any indicator value.
        model_history = full_history[-504:]
        horizon_models = build_horizon_models(
            [item[0] for item in model_history],
            [item[1] for item in model_history],
            volumes=(
                [item[2] for item in model_history]
                if any(item[2] is not None for item in model_history)
                else None
            ),
            point_in_time_fundamentals=False,
            include_walk_forward_validation=False,
        )
        input_fingerprint = _fingerprint(
            {
                "series_id": series_id,
                "cutoff": cutoff.isoformat(),
                "dates": [item[0].isoformat() for item in model_history],
                "closes": [item[1] for item in model_history],
                "volumes": [item[2] for item in model_history],
                "model_version": MODEL_VERSION,
                "source_kind": "daily_deterministic_company_snapshot",
            }
        )
        for model in horizon_models["models"]:
            horizon_key = str(model["key"])
            identity = (series_id, cutoff, MODEL_VERSION, horizon_key)
            if identity in existing:
                continue
            signal = model.get("current_signal")
            signal = signal if isinstance(signal, dict) else {}
            forecast = EntryHorizonForecast(
                source_inquiry_id=None,
                market_region=target["market_region"],
                ticker=target["ticker"],
                series_id=series_id,
                report_cutoff=cutoff,
                model_version=MODEL_VERSION,
                horizon_key=horizon_key,
                horizon_sessions=int(model["horizon_sessions"]),
                signal_triggered=bool(signal.get("triggered")),
                signal_score=(float(signal["score"]) if signal.get("score") is not None else None),
                forecast_payload={
                    **model,
                    "calibration_context": {
                        "sector": target["sector"],
                        "source_kind": "daily_deterministic_company_snapshot",
                        "gpu_used": False,
                    },
                },
                input_fingerprint=input_fingerprint,
                created_at=observed_at,
            )
            session.add(forecast)
            existing[identity] = forecast
            forecasts_created += 1
            created_for_company += 1
        if created_for_company:
            daily_companies_frozen += 1
        if all(
            (series_id, cutoff, MODEL_VERSION, str(model["key"])) in existing
            for model in horizon_models["models"]
        ):
            daily_companies_covered += 1

    session.flush()
    all_forecasts = list(
        session.scalars(
            select(EntryHorizonForecast)
            .options(
                defer(EntryHorizonForecast.forecast_payload),
                selectinload(EntryHorizonForecast.outcome).selectinload(
                    EntryHorizonOutcome.evaluations
                ),
            )
            .where(EntryHorizonForecast.model_version == MODEL_VERSION)
        )
    )
    sector_by_series = _series_sector_map(session)
    forecasts_needing_evaluation: list[
        tuple[EntryHorizonForecast, list[tuple[date, float, float | None]] | None]
    ] = []
    pending_by_series: dict[str, list[EntryHorizonForecast]] = defaultdict(list)
    for forecast in all_forecasts:
        if forecast.outcome is not None and _has_current_evaluation(forecast.outcome):
            continue
        if forecast.outcome is not None:
            forecasts_needing_evaluation.append((forecast, None))
            continue
        if (observed_at.date() - forecast.report_cutoff).days < forecast.horizon_sessions:
            # Fewer calendar days than required trading sessions can never be
            # mature, so avoid any history query for fresh daily rows.
            continue
        latest_series_date = latest_equity_cutoffs.get(forecast.series_id)
        if latest_series_date is None or latest_series_date <= forecast.report_cutoff:
            # The aggregate watermark proves there are no post-cutoff rows, so
            # a per-series maturity query cannot produce an outcome.
            continue
        pending_by_series[forecast.series_id].append(forecast)

    payload_ids = {
        forecast.id for forecast, _ in forecasts_needing_evaluation
    } | {
        forecast.id
        for series_forecasts in pending_by_series.values()
        for forecast in series_forecasts
    }
    forecast_payloads = {
        forecast_id: payload
        for forecast_id, payload in session.execute(
            select(
                EntryHorizonForecast.id,
                EntryHorizonForecast.forecast_payload,
            ).where(EntryHorizonForecast.id.in_(payload_ids or {-1}))
        )
    }

    # Read only post-cutoff rows once per company. Previously every pending
    # forecast could pull the issuer's complete price history merely to prove
    # that it was not mature yet.
    maturity_cutoffs = {
        series_id: min(item.report_cutoff for item in series_forecasts)
        for series_id, series_forecasts in pending_by_series.items()
    }
    maturity_histories = _load_histories_after(session, maturity_cutoffs)
    for series_id, series_forecasts in pending_by_series.items():
        future_history = maturity_histories.get(series_id, [])
        future_dates = [item[0] for item in future_history]
        for forecast in series_forecasts:
            start_index = bisect_right(future_dates, forecast.report_cutoff)
            forecast_path = future_history[
                start_index : start_index + forecast.horizon_sessions
            ]
            outcome = _matured_outcome_from_future(
                forecast,
                future_history=forecast_path,
                forecast_payload=forecast_payloads.get(forecast.id, {}),
                settled_at=observed_at,
            )
            if outcome is not None:
                session.add(outcome)
                forecast.outcome = outcome
                session.flush()
                outcomes_settled += 1
                forecasts_needing_evaluation.append((forecast, forecast_path))

    evaluation_start = min(
        (
            forecast.outcome.entry_date
            for forecast, _ in forecasts_needing_evaluation
            if forecast.outcome is not None
        ),
        default=observed_at.date(),
    )
    evaluation_end = max(
        (
            forecast.outcome.exit_date
            for forecast, _ in forecasts_needing_evaluation
            if forecast.outcome is not None
        ),
        default=observed_at.date(),
    )
    for forecast, bounded_asset_history in forecasts_needing_evaluation:
        if forecast.outcome is None:
            continue
        asset_history = bounded_asset_history or _load_history_between(
            session,
            forecast.series_id,
            forecast.outcome.entry_date,
            forecast.outcome.exit_date,
        )
        benchmark_series_id = BENCHMARK_SERIES_BY_REGION[forecast.market_region]
        benchmark_history = _history_for(histories, session, benchmark_series_id)
        context = forecast_payloads.get(forecast.id, {}).get("calibration_context")
        context = context if isinstance(context, dict) else {}
        sector = str(context.get("sector") or sector_by_series.get(forecast.series_id) or "")
        sector_series_id, sector_history = _sector_benchmark_history(
            session,
            market_region=forecast.market_region,
            sector=sector,
            histories=histories,
            evaluation_start=evaluation_start,
            evaluation_end=evaluation_end,
        )
        evaluation = _outcome_evaluation(
            forecast,
            forecast.outcome,
            full_history=asset_history,
            benchmark_history=benchmark_history,
            sector_benchmark_series_id=sector_series_id,
            sector_benchmark_history=sector_history,
            evaluated_at=observed_at,
        )
        session.add(evaluation)
        forecast.outcome.evaluations.append(evaluation)
        evaluations_created += 1
    session.flush()
    pending = sum(item.outcome is None for item in all_forecasts)
    candidate_summaries = _refresh_parameter_candidates(
        session,
        minimum_signals=settings.entry_calibration_min_signals,
        observed_at=observed_at,
    )
    horizon_summary = _horizon_summary(
        all_forecasts,
        minimum_signals=settings.entry_calibration_min_signals,
        candidates=candidate_summaries,
    )
    summary: dict[str, Any] = {
        "generated_at": observed_at.isoformat(),
        "run_id": run.id,
        "model_version": MODEL_VERSION,
        "production_model_changed": False,
        "policy": "append_only_outcomes_review_gated_parameter_candidates",
        "reports_scanned": len(reports),
        "reports_skipped": skipped_reports,
        "research_inquiry_watermark_id": current_report_watermark,
        "daily_company_universe": len(daily_targets),
        "daily_company_snapshots_created": daily_companies_frozen,
        "daily_company_snapshots_covered": daily_companies_covered,
        "daily_company_insufficient_history": daily_companies_insufficient_history,
        "daily_company_snapshot_gpu_used": False,
        "forecasts_created": forecasts_created,
        "outcomes_settled": outcomes_settled,
        "evaluations_created": evaluations_created,
        "evaluation_version": EVALUATION_POLICY,
        "benchmark_policy": {
            "us": "TD:SPY · S&P 500 tradable proxy",
            "china": "TD:MCHI · broad China equity tradable proxy",
            "us_sector": "Select Sector SPDR tradable proxies matched by company sector",
            "china_sector": "Current-universe equal-weight sector proxy; survivorship caveat",
        },
        "forecast_total": len(all_forecasts),
        "pending_forecasts": pending,
        "horizons": horizon_summary,
        "candidate_review": candidate_summaries,
        "leakage_guard": (
            "Forecast rows freeze only data available through the report cutoff. "
            "Matured outcomes and benchmark evaluations are append-only and never "
            "rewrite the forecast payload. Market regime uses benchmark data available "
            "through the report cutoff only."
        ),
    }
    run.forecasts_created = forecasts_created
    run.outcomes_settled = outcomes_settled
    run.pending_forecasts = pending
    run.summary = summary
    run.completed_at = observed_at

    resolved_archive = archive or ColdArchive(
        settings.cold_data_root,
        min_free_bytes=settings.cold_archive_min_free_gb * 1024**3,
        max_used_percent=settings.cold_archive_max_used_percent,
    )
    try:
        encoded = json.dumps(
            summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        relative = (
            "model-outputs/entry-calibration/"
            f"{observed_at:%Y/%m/%d}/run-{run.id}-{digest[:16]}.json.gz"
        )
        run.archive_path = resolved_archive.store_bytes(
            relative, gzip.compress(encoded, compresslevel=6, mtime=0)
        )
        run.archive_status = "stored"
        run.status = "completed"
    except (ArchiveCapacityError, OSError) as exc:
        run.archive_status = "write_failed"
        run.status = "completed_archive_warning"
        run.error_message = str(exc)[:2_000]
    return summary


def evaluate_threshold_candidate(
    samples: list[dict[str, Any]],
    *,
    minimum_signals: int,
) -> dict[str, Any]:
    """Chronologically compare a bounded threshold grid with frozen v1."""
    ordered = sorted(samples, key=lambda item: (item["report_cutoff"], item["ticker"]))
    base_signals = [item for item in ordered if item["score"] >= BASE_SIGNAL_THRESHOLD]
    independent_base = _independent_windows(base_signals)
    if len(independent_base) < minimum_signals:
        return {
            "status": "collecting",
            "matured_samples": len(ordered),
            "raw_matured_base_signals": len(base_signals),
            "matured_base_signals": len(independent_base),
            "minimum_signals": minimum_signals,
            "progress": min(1.0, len(independent_base) / minimum_signals),
            "independence_policy": "overlapping_calendar_windows_equal_weighted_once",
        }
    split = max(1, int(len(ordered) * 0.7))
    train, test = ordered[:split], ordered[split:]
    required_train = max(5, int(minimum_signals * 0.5))
    scored: list[tuple[float, float, int]] = []
    for threshold in REVIEWED_THRESHOLD_GRID:
        metrics = _sample_metrics(train, threshold)
        if metrics["signals"] >= required_train:
            scored.append(
                (
                    float(metrics["dual_adjusted_mean_return"]),
                    threshold,
                    int(metrics["signals"]),
                )
            )
    chosen = max(scored, default=(0.0, BASE_SIGNAL_THRESHOLD, 0))[1]
    base_metrics = _sample_metrics(test, BASE_SIGNAL_THRESHOLD)
    candidate_metrics = _sample_metrics(test, chosen)
    comparable = base_metrics["signals"] >= 3 and candidate_metrics["signals"] >= 3
    benchmark_comparable = bool(
        comparable
        and base_metrics["benchmark_coverage_rate"] >= 0.8
        and candidate_metrics["benchmark_coverage_rate"] >= 0.8
    )
    sector_comparable = bool(
        comparable
        and base_metrics["sector_benchmark_coverage_rate"] >= 0.8
        and candidate_metrics["sector_benchmark_coverage_rate"] >= 0.8
    )
    excess_improved = bool(
        not benchmark_comparable
        or (
            candidate_metrics["mean_excess_return"] > base_metrics["mean_excess_return"]
            and candidate_metrics["benchmark_outperformance_rate"]
            >= base_metrics["benchmark_outperformance_rate"]
        )
    )
    sector_excess_improved = bool(
        not sector_comparable
        or (
            candidate_metrics["mean_sector_excess_return"]
            > base_metrics["mean_sector_excess_return"]
            and candidate_metrics["sector_outperformance_rate"]
            >= base_metrics["sector_outperformance_rate"]
        )
    )
    drawdown_not_worse = bool(
        candidate_metrics["forecast_sequence_max_drawdown"]
        >= base_metrics["forecast_sequence_max_drawdown"]
    )
    confidence_not_worse = bool(
        candidate_metrics["mean_net_return_confidence_interval_95"][0]
        >= base_metrics["mean_net_return_confidence_interval_95"][0]
    )
    improved = bool(
        comparable
        and chosen != BASE_SIGNAL_THRESHOLD
        and candidate_metrics["mean_net_return"] > base_metrics["mean_net_return"]
        and candidate_metrics["hit_rate"] >= base_metrics["hit_rate"]
        and candidate_metrics["worst_net_return"] >= base_metrics["worst_net_return"]
        and excess_improved
        and sector_excess_improved
        and drawdown_not_worse
        and confidence_not_worse
    )
    return {
        "status": "ready_for_review" if improved else "baseline_retained",
        "matured_samples": len(ordered),
        "raw_matured_base_signals": len(base_signals),
        "matured_base_signals": len(independent_base),
        "minimum_signals": minimum_signals,
        "progress": 1.0,
        "train_samples": len(train),
        "test_samples": len(test),
        "chosen_threshold": round(chosen, 4),
        "base_threshold": BASE_SIGNAL_THRESHOLD,
        "base_test": base_metrics,
        "candidate_test": candidate_metrics,
        "benchmark_comparable": benchmark_comparable,
        "sector_benchmark_comparable": sector_comparable,
        "selection_objective": "dual_benchmark_adjusted_mean_return",
        "independence_policy": "overlapping_calendar_windows_equal_weighted_once",
        "confidence_interval_policy": "deterministic_bootstrap_percentile_95",
        "drawdown_scope": (
            "Chronological forecast-sequence diagnostic; not a compounded live portfolio."
        ),
        "human_review_required": True,
        "production_model_changed": False,
    }


def _unique_equity_report_windows(
    session: Session,
    *,
    after_id: int = 0,
    updated_after: datetime | None = None,
) -> list[ResearchInquiry]:
    changed_since_last_run = ResearchInquiry.id > after_id
    if updated_after is not None:
        changed_since_last_run = or_(
            changed_since_last_run,
            ResearchInquiry.updated_at > updated_after,
        )
    rows = list(
        session.scalars(
            select(ResearchInquiry)
            .where(
                ResearchInquiry.status == "completed",
                changed_since_last_run,
            )
            .order_by(ResearchInquiry.id.desc())
        )
    )
    unique: dict[tuple[str, str, str], ResearchInquiry] = {}
    for row in rows:
        context = row.evidence_snapshot.get("equity_research_context")
        if not isinstance(context, dict):
            continue
        identity = (
            str(context.get("market_region") or ""),
            str(context.get("ticker") or "").upper(),
            str(context.get("point_in_time_cutoff") or "")[:10],
        )
        if all(identity):
            unique.setdefault(identity, row)
    return list(unique.values())


def _daily_equity_targets(session: Session) -> list[dict[str, str]]:
    """Return the reviewed active company universe for GPU-free daily snapshots."""
    rows = list(
        session.scalars(
            select(MarketSeries)
            .where(
                MarketSeries.category == "equity_price",
                MarketSeries.listing_status == "active",
                MarketSeries.series_id.like("EQ:%") | MarketSeries.series_id.like("CN:%"),
            )
            .order_by(MarketSeries.series_id)
        )
    )
    return [
        {
            "series_id": row.series_id,
            "ticker": row.series_id.split(":", 1)[1],
            "market_region": "china" if row.series_id.startswith("CN:") else "us",
            "sector": str(row.sector or ""),
        }
        for row in rows
    ]


def _series_sector_map(session: Session) -> dict[str, str]:
    return {
        series_id: str(sector or "")
        for series_id, sector in session.execute(
            select(MarketSeries.series_id, MarketSeries.sector).where(
                MarketSeries.category == "equity_price"
            )
        )
    }


def _latest_equity_cutoffs(session: Session) -> dict[str, date]:
    """Read latest bar dates, including observation-only equity series."""
    cutoffs = {
        series_id: observed_on
        for series_id, observed_on in session.execute(
            select(
                MarketDailyBar.series_id,
                func.max(MarketDailyBar.observed_on),
            )
            .where(MarketDailyBar.series_id.like("EQ:%") | MarketDailyBar.series_id.like("CN:%"))
            .group_by(MarketDailyBar.series_id)
        )
        if observed_on is not None
    }
    observation_cutoffs = session.execute(
        select(
            MarketObservation.series_id,
            func.max(MarketObservation.observed_on),
        )
        .where(
            MarketObservation.series_id.like("EQ:%")
            | MarketObservation.series_id.like("CN:%")
        )
        .group_by(MarketObservation.series_id)
    )
    for series_id, observed_on in observation_cutoffs:
        if observed_on is not None and observed_on > cutoffs.get(series_id, date.min):
            cutoffs[series_id] = observed_on
    return cutoffs


def _sector_benchmark_history(
    session: Session,
    *,
    market_region: str,
    sector: str,
    histories: dict[str, list[tuple[date, float, float | None]]],
    evaluation_start: date,
    evaluation_end: date,
) -> tuple[str | None, list[tuple[date, float, float | None]]]:
    if not sector:
        return None, []
    if market_region == "us":
        series_id = US_SECTOR_BENCHMARKS.get(sector)
        if series_id is None:
            return None, []
        return series_id, _history_for(histories, session, series_id)
    synthetic_id = "CN-SECTOR-EW:" + sector.lower().replace(" ", "_")
    if synthetic_id not in histories:
        members = list(
            session.scalars(
                select(MarketSeries.series_id).where(
                    MarketSeries.category == "equity_price",
                    MarketSeries.region == "china",
                    MarketSeries.listing_status == "active",
                    MarketSeries.sector == sector,
                    MarketSeries.series_id.like("CN:%"),
                )
            )
        )
        proxy_start = evaluation_start - timedelta(days=14)
        member_histories = [
            _load_history_between(session, item, proxy_start, evaluation_end)
            for item in members
        ]
        histories[synthetic_id] = _equal_weight_sector_history(member_histories)
    return synthetic_id, histories[synthetic_id]


def _equal_weight_sector_history(
    member_histories: list[list[tuple[date, float, float | None]]],
) -> list[tuple[date, float, float | None]]:
    """Build a daily-rebalanced proxy from current reviewed sector members."""
    returns_by_date: dict[date, list[float]] = defaultdict(list)
    for history in member_histories:
        for previous, current in pairwise(history):
            if previous[1] > 0:
                returns_by_date[current[0]].append(current[1] / previous[1] - 1)
    level = 100.0
    result: list[tuple[date, float, float | None]] = []
    for observed_on in sorted(returns_by_date):
        values = returns_by_date[observed_on]
        if not values:
            continue
        level *= 1 + sum(values) / len(values)
        result.append((observed_on, level, None))
    return result


def _load_history(session: Session, series_id: str) -> list[tuple[date, float, float | None]]:
    bars = list(
        session.execute(
            select(
                MarketDailyBar.series_id,
                MarketDailyBar.observed_on,
                MarketDailyBar.close_price,
                MarketDailyBar.volume,
            )
            .where(MarketDailyBar.series_id == series_id)
            .order_by(MarketDailyBar.observed_on)
        )
    )
    if bars:
        return [
            (
                row.observed_on,
                float(row.close_price),
                float(row.volume) if row.volume is not None else None,
            )
            for row in bars
        ]
    observations = list(
        session.execute(
            select(MarketObservation.observed_on, MarketObservation.value)
            .where(MarketObservation.series_id == series_id)
            .order_by(MarketObservation.observed_on)
        )
    )
    return [(row.observed_on, float(row.value), None) for row in observations]


def _load_histories_after(
    session: Session,
    cutoffs: dict[str, date],
) -> dict[str, list[tuple[date, float, float | None]]]:
    """Load compact post-cutoff histories in at most two database queries."""
    if not cutoffs:
        return {}
    series_ids = list(cutoffs)
    earliest_cutoff = min(cutoffs.values())
    bars = list(
        session.execute(
            select(
                MarketDailyBar.series_id,
                MarketDailyBar.observed_on,
                MarketDailyBar.close_price,
                MarketDailyBar.volume,
            )
            .where(
                MarketDailyBar.series_id.in_(series_ids),
                MarketDailyBar.observed_on > earliest_cutoff,
            )
            .order_by(MarketDailyBar.series_id, MarketDailyBar.observed_on)
        )
    )
    result: dict[str, list[tuple[date, float, float | None]]] = defaultdict(list)
    for bar_row in bars:
        if bar_row.observed_on > cutoffs[bar_row.series_id]:
            result[bar_row.series_id].append(
                (
                    bar_row.observed_on,
                    float(bar_row.close_price),
                    float(bar_row.volume) if bar_row.volume is not None else None,
                )
            )
    observation_series = [series_id for series_id in series_ids if not result.get(series_id)]
    if not observation_series:
        return dict(result)
    observations = list(
        session.execute(
            select(
                MarketObservation.series_id,
                MarketObservation.observed_on,
                MarketObservation.value,
            )
            .where(
                MarketObservation.series_id.in_(observation_series),
                MarketObservation.observed_on > earliest_cutoff,
            )
            .order_by(MarketObservation.series_id, MarketObservation.observed_on)
        )
    )
    for observation_row in observations:
        if observation_row.observed_on > cutoffs[observation_row.series_id]:
            result[observation_row.series_id].append(
                (observation_row.observed_on, float(observation_row.value), None)
            )
    return dict(result)


def _load_recent_history(
    session: Session,
    series_id: str,
    *,
    limit: int,
) -> list[tuple[date, float, float | None]]:
    """Load the bounded tail required by current, non-backtest signals."""
    bars = list(
        session.execute(
            select(
                MarketDailyBar.observed_on,
                MarketDailyBar.close_price,
                MarketDailyBar.volume,
            )
            .where(MarketDailyBar.series_id == series_id)
            .order_by(MarketDailyBar.observed_on.desc())
            .limit(limit)
        )
    )
    if bars:
        return list(
            reversed(
                [
                    (
                        row.observed_on,
                        float(row.close_price),
                        float(row.volume) if row.volume is not None else None,
                    )
                    for row in bars
                ]
            )
        )
    observations = list(
        session.execute(
            select(MarketObservation.observed_on, MarketObservation.value)
            .where(MarketObservation.series_id == series_id)
            .order_by(MarketObservation.observed_on.desc())
            .limit(limit)
        )
    )
    return list(
        reversed([(row.observed_on, float(row.value), None) for row in observations])
    )


def _load_history_between(
    session: Session,
    series_id: str,
    start: date,
    end: date,
) -> list[tuple[date, float, float | None]]:
    """Load only the realized path needed by one evaluation."""
    bars = list(
        session.execute(
            select(
                MarketDailyBar.observed_on,
                MarketDailyBar.close_price,
                MarketDailyBar.volume,
            )
            .where(
                MarketDailyBar.series_id == series_id,
                MarketDailyBar.observed_on >= start,
                MarketDailyBar.observed_on <= end,
            )
            .order_by(MarketDailyBar.observed_on)
        )
    )
    if bars:
        return [
            (
                row.observed_on,
                float(row.close_price),
                float(row.volume) if row.volume is not None else None,
            )
            for row in bars
        ]
    observations = list(
        session.execute(
            select(MarketObservation.observed_on, MarketObservation.value)
            .where(
                MarketObservation.series_id == series_id,
                MarketObservation.observed_on >= start,
                MarketObservation.observed_on <= end,
            )
            .order_by(MarketObservation.observed_on)
        )
    )
    return [(row.observed_on, float(row.value), None) for row in observations]


def _history_for(
    histories: dict[str, list[tuple[date, float, float | None]]],
    session: Session,
    series_id: str,
) -> list[tuple[date, float, float | None]]:
    history = histories.get(series_id)
    if history is None:
        history = _load_history(session, series_id)
        histories[series_id] = history
    return history


def _has_point_in_time_fundamentals(report: ResearchInquiry) -> bool:
    context = report.evidence_snapshot.get("equity_research_context")
    if isinstance(context, dict) and str(context.get("financial_trend_status", "")).startswith(
        "point_in_time"
    ):
        return True
    evidence = report.evidence_snapshot.get("derived_equity_evidence")
    return bool(
        isinstance(evidence, list)
        and any(
            isinstance(item, dict)
            and item.get("category") in {"derived_financial_trend", "company_financial_trend"}
            for item in evidence
        )
    )


def _matured_outcome_from_future(
    forecast: EntryHorizonForecast,
    *,
    future_history: list[tuple[date, float, float | None]],
    forecast_payload: dict[str, Any],
    settled_at: datetime,
) -> EntryHorizonOutcome | None:
    if len(future_history) < forecast.horizon_sessions:
        return None
    entry = future_history[0]
    exit_row = future_history[forecast.horizon_sessions - 1]
    path = future_history[: forecast.horizon_sessions]
    transaction_cost_bps = float(
        forecast_payload.get("parameters", {}).get("transaction_cost_bps", 10.0)
    )
    net_return = exit_row[1] / entry[1] - 1 - transaction_cost_bps / 10_000
    target = forecast_payload.get("target_reference")
    stop = forecast_payload.get("stop_reference")
    payload = {
        "forecast_id": forecast.id,
        "entry_date": entry[0].isoformat(),
        "exit_date": exit_row[0].isoformat(),
        "entry_close": entry[1],
        "exit_close": exit_row[1],
        "net_return": net_return,
        "transaction_cost_bps": transaction_cost_bps,
        "policy": OUTCOME_POLICY,
    }
    return EntryHorizonOutcome(
        forecast_id=forecast.id,
        entry_date=entry[0],
        exit_date=exit_row[0],
        entry_close=entry[1],
        exit_close=exit_row[1],
        net_return=net_return,
        transaction_cost_bps=transaction_cost_bps,
        target_touched_by_close=bool(
            target is not None and any(item[1] >= float(target) for item in path)
        ),
        stop_touched_by_close=bool(
            stop is not None and any(item[1] <= float(stop) for item in path)
        ),
        outcome_fingerprint=_fingerprint(payload),
        calculation_policy=OUTCOME_POLICY,
        settled_at=settled_at,
    )


def _has_current_evaluation(outcome: EntryHorizonOutcome) -> bool:
    return any(item.evaluation_version == EVALUATION_POLICY for item in outcome.evaluations)


def _current_evaluation(outcome: EntryHorizonOutcome) -> EntryOutcomeEvaluation | None:
    return next(
        (item for item in outcome.evaluations if item.evaluation_version == EVALUATION_POLICY),
        None,
    )


def _outcome_evaluation(
    forecast: EntryHorizonForecast,
    outcome: EntryHorizonOutcome,
    *,
    full_history: list[tuple[date, float, float | None]],
    benchmark_history: list[tuple[date, float, float | None]],
    sector_benchmark_series_id: str | None,
    sector_benchmark_history: list[tuple[date, float, float | None]],
    evaluated_at: datetime,
) -> EntryOutcomeEvaluation:
    """Add point-in-time market context without changing the settled outcome."""
    asset_path = [row for row in full_history if outcome.entry_date <= row[0] <= outcome.exit_date]
    path_returns = [row[1] / outcome.entry_close - 1 for row in asset_path]
    maximum_adverse_excursion = min(path_returns, default=0.0)
    maximum_favorable_excursion = max(path_returns, default=0.0)

    benchmark_series_id = BENCHMARK_SERIES_BY_REGION[forecast.market_region]
    benchmark = _benchmark_result(
        benchmark_history,
        entry_date=outcome.entry_date,
        exit_date=outcome.exit_date,
    )
    benchmark_entry = benchmark["entry"]
    benchmark_exit = benchmark["exit"]
    benchmark_return = benchmark["return"]
    excess_net_return = (
        outcome.net_return - benchmark_return if benchmark_return is not None else None
    )
    benchmark_coverage = str(benchmark["coverage"])
    sector_benchmark = _benchmark_result(
        sector_benchmark_history,
        entry_date=outcome.entry_date,
        exit_date=outcome.exit_date,
    )
    sector_entry = sector_benchmark["entry"]
    sector_exit = sector_benchmark["exit"]
    sector_return = sector_benchmark["return"]
    sector_excess_net_return = (
        outcome.net_return - sector_return if sector_return is not None else None
    )
    market_regime = _market_regime(
        benchmark_history,
        as_of=forecast.report_cutoff,
    )
    payload = {
        "outcome_id": outcome.id,
        "evaluation_version": EVALUATION_POLICY,
        "benchmark_series_id": benchmark_series_id,
        "benchmark_entry_date": benchmark_entry[0].isoformat() if benchmark_entry else None,
        "benchmark_exit_date": benchmark_exit[0].isoformat() if benchmark_exit else None,
        "benchmark_entry_close": benchmark_entry[1] if benchmark_entry else None,
        "benchmark_exit_close": benchmark_exit[1] if benchmark_exit else None,
        "benchmark_return": benchmark_return,
        "excess_net_return": excess_net_return,
        "sector_benchmark_series_id": sector_benchmark_series_id,
        "sector_benchmark_entry_date": sector_entry[0].isoformat() if sector_entry else None,
        "sector_benchmark_exit_date": sector_exit[0].isoformat() if sector_exit else None,
        "sector_benchmark_return": sector_return,
        "sector_excess_net_return": sector_excess_net_return,
        "sector_benchmark_coverage": sector_benchmark["coverage"],
        "maximum_adverse_excursion": maximum_adverse_excursion,
        "maximum_favorable_excursion": maximum_favorable_excursion,
        "market_regime": market_regime,
        "benchmark_coverage": benchmark_coverage,
        "market_regime_cutoff": forecast.report_cutoff.isoformat(),
    }
    return EntryOutcomeEvaluation(
        outcome_id=outcome.id,
        evaluation_version=EVALUATION_POLICY,
        benchmark_series_id=benchmark_series_id,
        benchmark_entry_date=benchmark_entry[0] if benchmark_entry else None,
        benchmark_exit_date=benchmark_exit[0] if benchmark_exit else None,
        benchmark_entry_close=benchmark_entry[1] if benchmark_entry else None,
        benchmark_exit_close=benchmark_exit[1] if benchmark_exit else None,
        benchmark_return=benchmark_return,
        excess_net_return=excess_net_return,
        sector_benchmark_series_id=sector_benchmark_series_id,
        sector_benchmark_entry_date=sector_entry[0] if sector_entry else None,
        sector_benchmark_exit_date=sector_exit[0] if sector_exit else None,
        sector_benchmark_return=sector_return,
        sector_excess_net_return=sector_excess_net_return,
        sector_benchmark_coverage=str(sector_benchmark["coverage"]),
        maximum_adverse_excursion=maximum_adverse_excursion,
        maximum_favorable_excursion=maximum_favorable_excursion,
        market_regime=market_regime,
        benchmark_coverage=benchmark_coverage,
        metrics_payload=payload,
        evaluation_fingerprint=_fingerprint(payload),
        evaluated_at=evaluated_at,
    )


def _benchmark_result(
    history: list[tuple[date, float, float | None]],
    *,
    entry_date: date,
    exit_date: date,
) -> dict[str, Any]:
    path = [row for row in history if entry_date <= row[0] <= exit_date]
    entry = path[0] if path else None
    exit_row = path[-1] if path else None
    value = (
        exit_row[1] / entry[1] - 1
        if entry is not None and exit_row is not None and entry[0] < exit_row[0]
        else None
    )
    if entry is None or exit_row is None or value is None:
        coverage = "unavailable"
    elif entry[0] == entry_date and exit_row[0] == exit_date:
        coverage = "exact_session_dates"
    else:
        coverage = "nearest_available_sessions"
    return {"entry": entry, "exit": exit_row, "return": value, "coverage": coverage}


def _market_regime(
    benchmark_history: list[tuple[date, float, float | None]],
    *,
    as_of: date,
) -> str:
    retained = [row[1] for row in benchmark_history if row[0] <= as_of]
    if len(retained) < 64:
        return "unavailable"
    latest = retained[-1]
    long_average = sum(retained[-200:]) / min(200, len(retained))
    momentum = latest / retained[-64] - 1
    if latest >= long_average and momentum > 0:
        return "risk_on"
    if latest < long_average and momentum < 0:
        return "risk_off"
    return "mixed"


def _refresh_parameter_candidates(
    session: Session,
    *,
    minimum_signals: int,
    observed_at: datetime,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    forecasts = list(
        session.scalars(
            select(EntryHorizonForecast)
            .options(
                defer(EntryHorizonForecast.forecast_payload),
                selectinload(EntryHorizonForecast.outcome).selectinload(
                    EntryHorizonOutcome.evaluations
                ),
            )
            .where(EntryHorizonForecast.model_version == MODEL_VERSION)
        )
    )
    for forecast in forecasts:
        if forecast.outcome is None or forecast.signal_score is None:
            continue
        evaluation = _current_evaluation(forecast.outcome)
        grouped[forecast.horizon_key].append(
            {
                "report_cutoff": forecast.report_cutoff.isoformat(),
                "ticker": forecast.ticker,
                "entry_date": forecast.outcome.entry_date.isoformat(),
                "exit_date": forecast.outcome.exit_date.isoformat(),
                "score": forecast.signal_score,
                "net_return": forecast.outcome.net_return,
                "benchmark_return": (
                    evaluation.benchmark_return if evaluation is not None else None
                ),
                "excess_net_return": (
                    evaluation.excess_net_return if evaluation is not None else None
                ),
                "sector_benchmark_return": (
                    evaluation.sector_benchmark_return if evaluation is not None else None
                ),
                "sector_excess_net_return": (
                    evaluation.sector_excess_net_return if evaluation is not None else None
                ),
                "sector_benchmark_coverage": (
                    evaluation.sector_benchmark_coverage
                    if evaluation is not None
                    else "unavailable"
                ),
                "maximum_adverse_excursion": (
                    evaluation.maximum_adverse_excursion if evaluation is not None else None
                ),
                "maximum_favorable_excursion": (
                    evaluation.maximum_favorable_excursion if evaluation is not None else None
                ),
                "market_regime": (
                    evaluation.market_regime if evaluation is not None else "unavailable"
                ),
                "benchmark_coverage": (
                    evaluation.benchmark_coverage if evaluation is not None else "unavailable"
                ),
            }
        )
    summaries: list[dict[str, Any]] = []
    for horizon_key in ("ultra_short", "swing", "medium", "long_value"):
        samples = grouped.get(horizon_key, [])
        result = evaluate_threshold_candidate(samples, minimum_signals=minimum_signals)
        result["horizon_key"] = horizon_key
        if result["status"] == "collecting":
            summaries.append(result)
            continue
        sample_fingerprint = _fingerprint(samples)
        candidate_version = f"entry_horizon_candidate_v2_{horizon_key}_{sample_fingerprint[:12]}"
        result["candidate_version"] = candidate_version
        result["sample_fingerprint"] = sample_fingerprint
        summaries.append(result)
        exists = session.scalar(
            select(EntryParameterCandidate.id).where(
                EntryParameterCandidate.candidate_version == candidate_version
            )
        )
        if exists is None:
            session.add(
                EntryParameterCandidate(
                    base_model_version=MODEL_VERSION,
                    candidate_version=candidate_version,
                    horizon_key=horizon_key,
                    status=str(result["status"]),
                    sample_fingerprint=sample_fingerprint,
                    sample_count=len(samples),
                    parameter_changes={
                        "signal_score_threshold": result["chosen_threshold"],
                        "base_signal_score_threshold": BASE_SIGNAL_THRESHOLD,
                    },
                    comparison_metrics=result,
                    created_at=observed_at,
                    updated_at=observed_at,
                )
            )
    return summaries


def _horizon_summary(
    forecasts: list[EntryHorizonForecast],
    *,
    minimum_signals: int,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidate_by_key = {item["horizon_key"]: item for item in candidates}
    rows: list[dict[str, Any]] = []
    for key in ("ultra_short", "swing", "medium", "long_value"):
        scoped = [item for item in forecasts if item.horizon_key == key]
        matured = [item for item in scoped if item.outcome is not None]
        matured_signals = [item for item in matured if item.signal_triggered]
        evaluations = [
            evaluation
            for item in matured_signals
            if item.outcome is not None
            and (evaluation := _current_evaluation(item.outcome)) is not None
        ]
        signal_samples: list[dict[str, Any]] = []
        for forecast in matured_signals:
            if forecast.outcome is None:
                continue
            evaluation = _current_evaluation(forecast.outcome)
            signal_samples.append(
                {
                    "report_cutoff": forecast.report_cutoff.isoformat(),
                    "entry_date": forecast.outcome.entry_date.isoformat(),
                    "exit_date": forecast.outcome.exit_date.isoformat(),
                    "ticker": forecast.ticker,
                    "score": 1.0,
                    "net_return": forecast.outcome.net_return,
                    "excess_net_return": evaluation.excess_net_return if evaluation else None,
                    "sector_excess_net_return": evaluation.sector_excess_net_return
                    if evaluation
                    else None,
                    "maximum_adverse_excursion": evaluation.maximum_adverse_excursion
                    if evaluation
                    else None,
                    "maximum_favorable_excursion": evaluation.maximum_favorable_excursion
                    if evaluation
                    else None,
                    "market_regime": evaluation.market_regime if evaluation else "unavailable",
                }
            )
        metrics = _sample_metrics(signal_samples, 0.5)
        regime_counts: dict[str, int] = defaultdict(int)
        for evaluation in evaluations:
            regime_counts[evaluation.market_regime] += 1
        rows.append(
            {
                "key": key,
                "forecasts": len(scoped),
                "matured": len(matured),
                "pending": len(scoped) - len(matured),
                "raw_matured_signals": len(matured_signals),
                "matured_signals": metrics["signals"],
                "hit_rate": metrics["hit_rate"],
                "mean_net_return": metrics["mean_net_return"],
                "mean_net_return_confidence_interval_95": metrics[
                    "mean_net_return_confidence_interval_95"
                ],
                "hit_rate_confidence_interval_95": metrics["hit_rate_confidence_interval_95"],
                "benchmark_evaluated_signals": round(
                    metrics["signals"] * metrics["benchmark_coverage_rate"]
                ),
                "benchmark_coverage_rate": metrics["benchmark_coverage_rate"],
                "mean_excess_return": metrics["mean_excess_return"],
                "benchmark_outperformance_rate": metrics["benchmark_outperformance_rate"],
                "mean_excess_return_confidence_interval_95": metrics[
                    "mean_excess_return_confidence_interval_95"
                ],
                "sector_benchmark_evaluated_signals": round(
                    metrics["signals"] * metrics["sector_benchmark_coverage_rate"]
                ),
                "sector_benchmark_coverage_rate": metrics["sector_benchmark_coverage_rate"],
                "mean_sector_excess_return": metrics["mean_sector_excess_return"],
                "sector_outperformance_rate": metrics["sector_outperformance_rate"],
                "mean_sector_excess_confidence_interval_95": metrics[
                    "mean_sector_excess_confidence_interval_95"
                ],
                "market_regimes": dict(regime_counts),
                "minimum_signals_for_upgrade_review": minimum_signals,
                "candidate_status": candidate_by_key.get(key, {}).get("status", "collecting"),
                "production_model_changed": False,
            }
        )
    return rows


def _sample_metrics(samples: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    raw_selected = [item for item in samples if item["score"] >= threshold]
    selected = _independent_windows(raw_selected)
    returns = [float(item["net_return"]) for item in selected]
    excess_returns = [
        float(item["excess_net_return"])
        for item in selected
        if item.get("excess_net_return") is not None
    ]
    sector_excess_returns = [
        float(item["sector_excess_net_return"])
        for item in selected
        if item.get("sector_excess_net_return") is not None
    ]
    dual_adjusted_returns = [_dual_adjusted_return(item) for item in selected]
    adverse_excursions = [
        float(item["maximum_adverse_excursion"])
        for item in selected
        if item.get("maximum_adverse_excursion") is not None
    ]
    favorable_excursions = [
        float(item["maximum_favorable_excursion"])
        for item in selected
        if item.get("maximum_favorable_excursion") is not None
    ]
    regimes: dict[str, dict[str, Any]] = {}
    for regime in ("risk_on", "risk_off", "mixed", "unavailable"):
        regime_samples = [item for item in selected if item.get("market_regime") == regime]
        if not regime_samples:
            continue
        regime_returns = [float(item["net_return"]) for item in regime_samples]
        regime_excess = [
            float(item["excess_net_return"])
            for item in regime_samples
            if item.get("excess_net_return") is not None
        ]
        regime_sector_excess = [
            float(item["sector_excess_net_return"])
            for item in regime_samples
            if item.get("sector_excess_net_return") is not None
        ]
        regimes[regime] = {
            "signals": len(regime_samples),
            "mean_net_return": sum(regime_returns) / len(regime_returns),
            "hit_rate": sum(value > 0 for value in regime_returns) / len(regime_returns),
            "mean_excess_return": (
                sum(regime_excess) / len(regime_excess) if regime_excess else None
            ),
            "mean_sector_excess_return": (
                sum(regime_sector_excess) / len(regime_sector_excess)
                if regime_sector_excess
                else None
            ),
        }
    return {
        "raw_signals": len(raw_selected),
        "signals": len(returns),
        "mean_net_return": sum(returns) / len(returns) if returns else None,
        "hit_rate": sum(value > 0 for value in returns) / len(returns) if returns else None,
        "worst_net_return": min(returns) if returns else None,
        "mean_excess_return": (
            sum(excess_returns) / len(excess_returns) if excess_returns else None
        ),
        "benchmark_outperformance_rate": (
            sum(value > 0 for value in excess_returns) / len(excess_returns)
            if excess_returns
            else None
        ),
        "benchmark_coverage_rate": (len(excess_returns) / len(selected) if selected else 0.0),
        "mean_sector_excess_return": (
            sum(sector_excess_returns) / len(sector_excess_returns)
            if sector_excess_returns
            else None
        ),
        "sector_outperformance_rate": (
            sum(value > 0 for value in sector_excess_returns) / len(sector_excess_returns)
            if sector_excess_returns
            else None
        ),
        "sector_benchmark_coverage_rate": (
            len(sector_excess_returns) / len(selected) if selected else 0.0
        ),
        "dual_adjusted_mean_return": (
            sum(dual_adjusted_returns) / len(dual_adjusted_returns)
            if dual_adjusted_returns
            else None
        ),
        "mean_net_return_confidence_interval_95": _bootstrap_mean_interval(returns),
        "mean_excess_return_confidence_interval_95": _bootstrap_mean_interval(excess_returns),
        "mean_sector_excess_confidence_interval_95": _bootstrap_mean_interval(
            sector_excess_returns
        ),
        "hit_rate_confidence_interval_95": _wilson_interval(returns),
        "worst_adverse_excursion": min(adverse_excursions) if adverse_excursions else None,
        "best_favorable_excursion": max(favorable_excursions) if favorable_excursions else None,
        "forecast_sequence_max_drawdown": _forecast_sequence_max_drawdown(returns),
        "regimes": regimes,
    }


def _independent_windows(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse overlapping calendar exposures into equal-weight time windows."""
    ordered = sorted(
        samples,
        key=lambda item: (
            str(item.get("entry_date") or item["report_cutoff"]),
            str(item.get("exit_date") or item["report_cutoff"]),
            item["ticker"],
        ),
    )
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_exit: date | None = None
    for item in ordered:
        entry = _parse_date(item.get("entry_date") or item["report_cutoff"])
        exit_date = _parse_date(item.get("exit_date") or item["report_cutoff"])
        if entry is None or exit_date is None:
            continue
        if current and current_exit is not None and entry > current_exit:
            groups.append(current)
            current = []
            current_exit = None
        current.append(item)
        current_exit = max(current_exit or exit_date, exit_date)
    if current:
        groups.append(current)
    return [_aggregate_independent_window(group) for group in groups]


def _aggregate_independent_window(group: list[dict[str, Any]]) -> dict[str, Any]:
    def mean(key: str) -> float | None:
        values = [float(item[key]) for item in group if item.get(key) is not None]
        return sum(values) / len(values) if values else None

    regimes: dict[str, int] = defaultdict(int)
    for item in group:
        regimes[str(item.get("market_regime") or "unavailable")] += 1
    regime = max(sorted(regimes), key=lambda key: regimes[key]) if regimes else "unavailable"
    adverse = [
        float(item["maximum_adverse_excursion"])
        for item in group
        if item.get("maximum_adverse_excursion") is not None
    ]
    favorable = [
        float(item["maximum_favorable_excursion"])
        for item in group
        if item.get("maximum_favorable_excursion") is not None
    ]
    return {
        "report_cutoff": min(str(item["report_cutoff"]) for item in group),
        "entry_date": min(str(item.get("entry_date") or item["report_cutoff"]) for item in group),
        "exit_date": max(str(item.get("exit_date") or item["report_cutoff"]) for item in group),
        "ticker": ",".join(sorted({str(item["ticker"]) for item in group})),
        "constituent_signals": len(group),
        "net_return": mean("net_return") or 0.0,
        "excess_net_return": mean("excess_net_return"),
        "sector_excess_net_return": mean("sector_excess_net_return"),
        "maximum_adverse_excursion": min(adverse) if adverse else None,
        "maximum_favorable_excursion": max(favorable) if favorable else None,
        "market_regime": regime,
    }


def _dual_adjusted_return(sample: dict[str, Any]) -> float:
    values = [
        float(value)
        for value in (
            sample.get("excess_net_return"),
            sample.get("sector_excess_net_return"),
        )
        if value is not None
    ]
    return sum(values) / len(values) if values else float(sample["net_return"])


def _bootstrap_mean_interval(values: list[float]) -> list[float | None]:
    if len(values) < 2:
        return [None, None]
    seed = int(_fingerprint(values)[:16], 16)
    generator = random.Random(seed)
    sample_count = len(values)
    means = sorted(
        sum(generator.choice(values) for _ in range(sample_count)) / sample_count
        for _ in range(2_000)
    )
    return [means[49], means[1_949]]


def _wilson_interval(returns: list[float]) -> list[float | None]:
    if not returns:
        return [None, None]
    successes = sum(value > 0 for value in returns)
    count = len(returns)
    z = 1.959963984540054
    center = (successes / count + z * z / (2 * count)) / (1 + z * z / count)
    margin = (
        z
        * ((successes / count * (1 - successes / count) / count + z * z / (4 * count**2)) ** 0.5)
        / (1 + z * z / count)
    )
    return [max(0.0, center - margin), min(1.0, center + margin)]


def _forecast_sequence_max_drawdown(returns: list[float]) -> float | None:
    if not returns:
        return None
    wealth = 1.0
    peak = 1.0
    maximum_drawdown = 0.0
    for value in returns:
        wealth *= 1 + value
        peak = max(peak, wealth)
        maximum_drawdown = min(maximum_drawdown, wealth / peak - 1)
    return maximum_drawdown


def _parse_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _fingerprint(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
