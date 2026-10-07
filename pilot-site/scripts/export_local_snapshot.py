"""Export a compact, attributed remote-pilot snapshot from the local NEWS database."""

from __future__ import annotations

import copy
import json
import math
import os
import re
import sys
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT.parent / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.horizon_backtest import MODEL_VERSION, build_horizon_models

OUTPUT = ROOT / "snapshot"
REPORT_DETAIL_OUTPUT = ROOT / "private-data" / "research-reports"
# Server-only bodies. pack-private-reports.mjs prepares the protected Worker
# store; no report body may be copied into a public static asset directory.
REMOTE_REPORT_LIMIT = 600
LOCAL_REPORT_AUDIT_VERSION = "local_report_audit_v12_a_share_confidence_gate"
DATABASE_URL = os.getenv(
    "NEWSAPP_SNAPSHOT_DATABASE_URL",
    "postgresql://newsapp:newsapp_dev_only@127.0.0.1:5432/newsapp",
)
LOCAL_API_URL = os.getenv("NEWSAPP_LOCAL_API_URL", "http://127.0.0.1:8000").rstrip("/")
SEMICONDUCTOR_COMPARISON_TICKERS = ("MU", "NVDA", "AMD", "MSFT")


def _text(value: object, *, limit: int = 1_500) -> str:
    return " ".join(str(value or "").split())[:limit]


def _strings(value: object, *, limit: int = 6) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_text(item, limit=700) for item in value if _text(item, limit=700)][:limit]


def _status(value: object) -> str:
    return {
        "verified": "verified",
        "partially_supported": "partial",
        "partial": "partial",
    }.get(str(value or ""), "missing")


def _recommendation(value: object) -> str:
    return {
        "accepted_for_research": "研究使用：接受",
        "revised_accepted_for_research": "研究使用：修改后接受",
        "revised_accepted_for_research_defer_for_trade_decision": "研究使用：修改后接受；交易决策：暂缓",
        "defer_for_evidence": "暂缓：等待更多证据",
        "rejected": "驳回",
    }.get(str(value or ""), _text(value, limit=160) or "本地审计已完成")


def _reference_ids(result: dict[str, object]) -> list[str]:
    refs: list[str] = []
    paper = result.get("paper_report")
    if isinstance(paper, dict):
        refs.extend(str(item) for item in paper.get("evidence_refs", []) if item)
    for hypothesis in result.get("hypotheses", []) if isinstance(result.get("hypotheses"), list) else []:
        if not isinstance(hypothesis, dict):
            continue
        for step in hypothesis.get("steps", []) if isinstance(hypothesis.get("steps"), list) else []:
            if isinstance(step, dict):
                refs.extend(str(item) for item in step.get("evidence_refs", []) if item)
    for dimension in result.get("equity_dimensions", []) if isinstance(result.get("equity_dimensions"), list) else []:
        if isinstance(dimension, dict):
            refs.extend(str(item) for item in dimension.get("evidence_refs", []) if item)
    return list(dict.fromkeys(refs))


def _evidence_item(item: dict[str, object]) -> dict[str, object]:
    category = str(item.get("category") or "evidence")
    tier = str(item.get("evidence_tier") or "")
    operating_status = str(item.get("evidence_status") or "")
    source = _text(
        item.get("source")
        or item.get("source_name")
        or item.get("provider")
        or item.get("related_company_name")
        or "Local auditable calculation",
        limit=160,
    )
    title = _text(
        item.get("title")
        or item.get("name")
        or item.get("site_name")
        or item.get("series_name")
        or item.get("concept")
        or item.get("metric_name")
        or category.replace("_", " "),
        limit=300,
    )
    if category == "product_operating_evidence":
        status_label = {
            "reported_actual": "已报告实际",
            "forward_looking_plan": "前瞻计划",
            "risk_disclosure": "风险披露",
        }.get(operating_status, "年报经营证据")
        title = f"{status_label} · {title}"
    claim = _text(
        item.get("excerpt")
        or item.get("source_excerpt")
        or item.get("summary")
        or item.get("assessment")
        or item.get("methodology")
        or item.get("method_limitations")
        or "Structured evidence retained in the local research snapshot.",
        limit=650,
    )
    observed_at = _text(
        item.get("published_at")
        or item.get("observed_on")
        or item.get("period_end")
        or item.get("filed_at")
        or item.get("occurred_at")
        or item.get("as_of")
        or item.get("available_at")
        or "local snapshot",
        limit=80,
    )
    reliability = 82
    if tier in {"official_or_structured", "full_text"}:
        reliability = 92 if tier == "official_or_structured" else 86
    elif category.startswith("derived_"):
        reliability = 84
    elif category == "product_operating_evidence":
        reliability = 94
    elif category in {"market_observation", "company_financial_fact"}:
        reliability = 91
    return {
        "title": title,
        "publisher": source,
        "url": _text(item.get("source_url"), limit=1_000),
        "observedAt": observed_at,
        "claim": claim,
        "supports": "contradict" if operating_status == "risk_disclosure" else "support",
        "reliability": reliability,
    }


def _number(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _trading_scenario(snapshot: dict[str, object]) -> dict[str, object] | None:
    derived = snapshot.get("derived_equity_evidence")
    if not isinstance(derived, list):
        return None
    technical = next(
        (
            item
            for item in derived
            if isinstance(item, dict)
            and item.get("category") == "derived_market_technical"
        ),
        None,
    )
    if not isinstance(technical, dict):
        return None
    positioning = next(
        (
            item
            for item in derived
            if isinstance(item, dict)
            and item.get("category") == "derived_institutional_positioning"
        ),
        None,
    )
    risk = technical.get("risk_reward")
    risk = risk if isinstance(risk, dict) else {}
    structure = technical.get("price_structure") or technical.get("close_only_structure")
    structure = structure if isinstance(structure, dict) else {}
    chart = technical.get("chart_points")
    chart = chart if isinstance(chart, list) else []
    one_week = structure.get("one_week_volatility_band")
    one_week = one_week if isinstance(one_week, dict) else {}
    two_week = structure.get("two_week_volatility_band")
    two_week = two_week if isinstance(two_week, dict) else {}
    support = structure.get("nearest_support")
    support = support if isinstance(support, dict) else {}
    resistance = structure.get("nearest_resistance")
    resistance = resistance if isinstance(resistance, dict) else {}
    managers = (
        positioning.get("top_manager_proxies", [])
        if isinstance(positioning, dict)
        else []
    )
    return {
        "ticker": _text(technical.get("ticker"), limit=16),
        "observedOn": _text(technical.get("observed_on"), limit=20),
        "entryPrice": _number(risk.get("entry_reference")),
        "stopReference": _number(risk.get("stop_reference")),
        "stopBasis": _text(risk.get("stop_basis"), limit=300),
        "targetReference": _number(risk.get("target_reference")),
        "targetBasis": _text(risk.get("target_basis"), limit=300),
        "downsideFraction": _number(risk.get("downside_fraction")),
        "upsideFraction": _number(risk.get("upside_fraction")),
        "rewardRiskRatio": _number(risk.get("reward_risk_ratio")),
        "barDataStatus": _text(technical.get("bar_data_status"), limit=40),
        "atr14": _number(technical.get("atr_14")),
        "volumeRatio20": _number(technical.get("volume_ratio_20")),
        "volumeStatus": _text(
            (
                technical.get("volume_confirmation", {}).get("status")
                if isinstance(technical.get("volume_confirmation"), dict)
                else ""
            ),
            limit=40,
        ),
        "support": {
            "label": _text(support.get("label"), limit=100),
            "value": _number(support.get("value")),
        },
        "resistance": {
            "label": _text(resistance.get("label"), limit=100),
            "value": _number(resistance.get("value")),
        },
        "oneWeekBand": {
            "lower": _number(one_week.get("lower")),
            "upper": _number(one_week.get("upper")),
            "expectedMove": _number(one_week.get("expected_move")),
        },
        "twoWeekBand": {
            "lower": _number(two_week.get("lower")),
            "upper": _number(two_week.get("upper")),
            "expectedMove": _number(two_week.get("expected_move")),
        },
        "averages": {
            "sma20": _number(technical.get("sma_20")),
            "sma50": _number(technical.get("sma_50")),
            "sma200": _number(technical.get("sma_200")),
        },
        "chart": [
            {
                "date": _text(item.get("date"), limit=20),
                "open": _number(item.get("open")),
                "high": _number(item.get("high")),
                "low": _number(item.get("low")),
                "close": _number(item.get("close")),
                "volume": _number(item.get("volume")),
                "sma20": _number(item.get("sma_20")),
                "sma50": _number(item.get("sma_50")),
            }
            for item in chart[-90:]
            if isinstance(item, dict) and _number(item.get("close")) is not None
        ],
        "institutional": {
            "actualAverageCostAvailable": False,
            "actualAverageCostStatus": "unavailable_from_form_13f",
            "reportPeriod": (
                _text(positioning.get("report_period"), limit=20)
                if isinstance(positioning, dict)
                else ""
            ),
            "quarterEndValuePerShareProxy": (
                _number(positioning.get("quarter_end_value_per_share_proxy"))
                if isinstance(positioning, dict)
                else None
            ),
            "proxyScope": (
                _text(positioning.get("proxy_scope"), limit=240)
                if isinstance(positioning, dict)
                else ""
            ),
            "topManagers": [
                {
                    "name": _text(item.get("manager_name"), limit=180),
                    "reportedShares": _number(item.get("reported_shares")),
                    "reportedShareChange": _number(
                        item.get("reported_share_change")
                    ),
                    "quarterEndValuePerShareProxy": _number(
                        item.get("quarter_end_value_per_share_proxy")
                    ),
                }
                for item in managers[:5]
                if isinstance(item, dict)
            ],
            "explanation": (
                "SEC Form 13F does not disclose purchase price or cost basis. "
                "Reported quarter-end value divided by shares is shown only as a "
                "dated valuation proxy, not an average buy price."
            ),
        },
        "methodNote": (
            (
                "Levels use split-adjusted OHLCV, swing highs/lows, ATR14, "
                "SMA20/50/200 and 63-day historical volatility. "
                if technical.get("bar_data_status") == "complete_ohlcv"
                else "Levels use adjusted closes, SMA20/50/200 and 63-day "
                "historical volatility. "
            )
            + "They are research scenario boundaries, not personalized advice, "
            "executable orders or guaranteed prices."
        ),
    }


def _camelize(value: object) -> object:
    if isinstance(value, list):
        return [_camelize(item) for item in value]
    if isinstance(value, dict):
        return {
            re.sub(r"_([a-z])", lambda match: match.group(1).upper(), str(key)): _camelize(item)
            for key, item in value.items()
        }
    return value


def _report_has_point_in_time_fundamentals(report: dict[str, object]) -> bool:
    readiness = report.get("dataReadiness")
    if isinstance(readiness, dict):
        for component in readiness.get("components", []):
            if (
                isinstance(component, dict)
                and component.get("key") == "fundamentals"
                and component.get("status") == "complete"
            ):
                return True
    disclosure = report.get("disclosureCoverage")
    return bool(
        isinstance(disclosure, dict)
        and int(disclosure.get("periodicReports") or 0) > 0
        and int(disclosure.get("financialMetrics") or 0) >= 4
    )


def _attach_entry_horizon_models(
    reports: list[dict[str, object]],
    *,
    observation_rows: list[dict[str, object]],
    bar_rows: list[dict[str, object]],
    generated_at: str,
) -> dict[str, object]:
    """Recreate point-in-time signals and score only outcomes known afterwards."""
    histories: dict[str, list[tuple[object, float, float | None]]] = {}
    for row in observation_rows:
        histories.setdefault(str(row["series_id"]), []).append(
            (row["observed_on"], float(row["value"]), None)
        )
    bar_histories: dict[str, list[tuple[object, float, float | None]]] = {}
    for row in bar_rows:
        bar_histories.setdefault(str(row["series_id"]), []).append(
            (
                row["observed_on"],
                float(row["close_price"]),
                float(row["volume"]) if row["volume"] is not None else None,
            )
        )
    aggregates: dict[str, dict[str, object]] = {}
    recent_evaluations: list[dict[str, object]] = []
    model_cache: dict[tuple[str, str, bool], dict[str, object]] = {}
    aggregated_windows: set[tuple[str, str, str]] = set()
    for report in reports:
        scenario = report.get("tradingScenario")
        if not isinstance(scenario, dict) or not report.get("ticker"):
            continue
        prefix = "CN" if report.get("marketRegion") == "china" else "EQ"
        series_id = f"{prefix}:{report['ticker']}"
        full_history = bar_histories.get(series_id) or histories.get(series_id) or []
        cutoff = str(scenario.get("observedOn") or "")[:10]
        retained = [item for item in full_history if item[0].isoformat() <= cutoff]
        if len(retained) < 35:
            continue
        dates = [item[0] for item in retained]
        closes = [item[1] for item in retained]
        has_volume = any(item[2] is not None for item in retained)
        volumes = [item[2] for item in retained] if has_volume else None
        fundamental_gate = _report_has_point_in_time_fundamentals(report)
        cache_key = (series_id, cutoff, fundamental_gate)
        cached_models = model_cache.get(cache_key)
        if cached_models is None:
            cached_models = build_horizon_models(
                dates,
                closes,
                volumes=volumes,
                point_in_time_fundamentals=fundamental_gate,
            )
            model_cache[cache_key] = cached_models
        models = copy.deepcopy(cached_models)
        cutoff_index = len(retained) - 1
        for model in models["models"]:
            key = str(model["key"])
            aggregate_window = (series_id, cutoff, key)
            aggregate_result = aggregate_window not in aggregated_windows
            if aggregate_result:
                aggregated_windows.add(aggregate_window)
            summary = aggregates.setdefault(
                key,
                {
                    "key": key,
                    "labelZh": model["label_zh"],
                    "labelEn": model["label_en"],
                    "reports": 0,
                    "matured": 0,
                    "pending": 0,
                    "maturedSignals": 0,
                    "positiveSignals": 0,
                    "netReturns": [],
                },
            )
            if aggregate_result:
                summary["reports"] = int(summary["reports"]) + 1
            horizon = int(model["horizon_sessions"])
            entry_index = cutoff_index + 1
            exit_index = cutoff_index + horizon
            signal = model.get("current_signal")
            triggered = bool(isinstance(signal, dict) and signal.get("triggered"))
            if exit_index >= len(full_history) or entry_index >= len(full_history):
                replay = {
                    "status": "pending",
                    "triggered": triggered,
                    "maturesAfterSessions": horizon,
                    "availableFutureSessions": max(0, len(full_history) - cutoff_index - 1),
                }
                if aggregate_result:
                    summary["pending"] = int(summary["pending"]) + 1
            else:
                entry = full_history[entry_index]
                exit_row = full_history[exit_index]
                net_return = exit_row[1] / entry[1] - 1 - 0.001
                path = full_history[entry_index : exit_index + 1]
                target = model.get("target_reference")
                stop = model.get("stop_reference")
                replay = {
                    "status": "matured_signal" if triggered else "matured_no_signal",
                    "triggered": triggered,
                    "entryDate": entry[0].isoformat(),
                    "exitDate": exit_row[0].isoformat(),
                    "entryClose": entry[1],
                    "exitClose": exit_row[1],
                    "netReturn": net_return,
                    "targetTouchedByClose": bool(
                        target is not None and any(item[1] >= float(target) for item in path)
                    ),
                    "stopTouchedByClose": bool(
                        stop is not None and any(item[1] <= float(stop) for item in path)
                    ),
                    "outcomeUse": "calibration_only_no_parameter_rewrite",
                }
                if aggregate_result:
                    summary["matured"] = int(summary["matured"]) + 1
                if triggered and aggregate_result:
                    summary["maturedSignals"] = int(summary["maturedSignals"]) + 1
                    if net_return > 0:
                        summary["positiveSignals"] = int(summary["positiveSignals"]) + 1
                    returns = summary["netReturns"]
                    if isinstance(returns, list):
                        returns.append(net_return)
                    recent_evaluations.append(
                        {
                            "reportId": report.get("id"),
                            "ticker": report.get("ticker"),
                            "horizon": key,
                            "entryDate": entry[0].isoformat(),
                            "exitDate": exit_row[0].isoformat(),
                            "netReturn": net_return,
                        }
                    )
            model["report_replay"] = replay
        scenario["horizonModels"] = _camelize(models)
    horizon_summaries: list[dict[str, object]] = []
    for summary in aggregates.values():
        values = summary.pop("netReturns")
        returns = values if isinstance(values, list) else []
        matured_signals = int(summary["maturedSignals"])
        summary["hitRate"] = (
            int(summary["positiveSignals"]) / matured_signals if matured_signals else None
        )
        summary["meanNetReturn"] = sum(returns) / len(returns) if returns else None
        summary["minimumSignalsForUpgradeReview"] = 30
        summary["upgradeEligible"] = matured_signals >= 30
        horizon_summaries.append(summary)
    return {
        "generatedAt": generated_at,
        "modelVersion": MODEL_VERSION,
        "status": "baseline_collecting_matured_report_outcomes",
        "parameterUpgradePolicy": (
            "A new parameter version requires at least 30 matured signals for a horizon, "
            "chronological out-of-sample improvement, and human review. Historical reports "
            "and outcomes are immutable."
        ),
        "historicalReportsEvaluated": sum(
            1
            for report in reports
            if isinstance(report.get("tradingScenario"), dict)
            and isinstance(report["tradingScenario"].get("horizonModels"), dict)
        ),
        "horizons": horizon_summaries,
        "recentMaturedSignals": recent_evaluations[-30:],
        "limitations": [
            "This baseline replays version-one rules using information available at each report cutoff; it is not proof that the original report made the same horizon forecast.",
            "Close-based outcome checks cannot prove intraday execution, and no result is personalized investment advice.",
            "Parameter updates are review-gated to reduce overfitting and survivorship bias.",
        ],
    }


def _load_durable_entry_calibration(cursor: object) -> dict[str, object] | None:
    """Read the newest completed append-only calibration run when migrated."""
    cursor.execute("SELECT to_regclass('public.entry_calibration_runs') AS table_name")
    if cursor.fetchone()["table_name"] is None:
        return None
    cursor.execute(
        """
        SELECT id, status, model_version, forecasts_created, outcomes_settled,
               pending_forecasts, summary, archive_status, archive_path,
               started_at, completed_at
        FROM entry_calibration_runs
        WHERE status IN ('completed', 'completed_archive_warning')
        ORDER BY completed_at DESC NULLS LAST, id DESC
        LIMIT 1
        """
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _merge_durable_entry_calibration(
    replay: dict[str, object],
    durable: dict[str, object] | None,
) -> dict[str, object]:
    """Prefer the local immutable ledger while retaining report-level replays."""
    if durable is None or not isinstance(durable.get("summary"), dict):
        replay["ledgerMode"] = "snapshot_replay_fallback"
        replay["productionModelChanged"] = False
        return replay
    summary = durable["summary"]
    labels = {
        item["key"]: (item["labelZh"], item["labelEn"])
        for item in replay.get("horizons", [])
        if isinstance(item, dict)
    }
    horizons: list[dict[str, object]] = []
    for item in summary.get("horizons", []):
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "")
        label_zh, label_en = labels.get(key, (key, key))
        matured_signals = int(item.get("matured_signals") or 0)
        minimum = int(item.get("minimum_signals_for_upgrade_review") or 30)
        horizons.append(
            {
                "key": key,
                "labelZh": label_zh,
                "labelEn": label_en,
                "reports": int(item.get("forecasts") or 0),
                "matured": int(item.get("matured") or 0),
                "pending": int(item.get("pending") or 0),
                "maturedSignals": matured_signals,
                "rawMaturedSignals": int(item.get("raw_matured_signals") or 0),
                "positiveSignals": round(
                    matured_signals * float(item.get("hit_rate") or 0)
                ),
                "hitRate": item.get("hit_rate"),
                "hitRateConfidenceInterval95": item.get(
                    "hit_rate_confidence_interval_95"
                ),
                "meanNetReturn": item.get("mean_net_return"),
                "meanNetReturnConfidenceInterval95": item.get(
                    "mean_net_return_confidence_interval_95"
                ),
                "benchmarkEvaluatedSignals": int(
                    item.get("benchmark_evaluated_signals") or 0
                ),
                "benchmarkCoverageRate": item.get("benchmark_coverage_rate"),
                "meanExcessReturn": item.get("mean_excess_return"),
                "meanExcessReturnConfidenceInterval95": item.get(
                    "mean_excess_return_confidence_interval_95"
                ),
                "benchmarkOutperformanceRate": item.get(
                    "benchmark_outperformance_rate"
                ),
                "sectorBenchmarkEvaluatedSignals": int(
                    item.get("sector_benchmark_evaluated_signals") or 0
                ),
                "sectorBenchmarkCoverageRate": item.get(
                    "sector_benchmark_coverage_rate"
                ),
                "meanSectorExcessReturn": item.get("mean_sector_excess_return"),
                "meanSectorExcessConfidenceInterval95": item.get(
                    "mean_sector_excess_confidence_interval_95"
                ),
                "sectorOutperformanceRate": item.get("sector_outperformance_rate"),
                "marketRegimes": _camelize(item.get("market_regimes", {})),
                "minimumSignalsForUpgradeReview": minimum,
                "upgradeEligible": matured_signals >= minimum,
                "candidateStatus": item.get("candidate_status") or "collecting",
                "productionModelChanged": bool(
                    item.get("production_model_changed", False)
                ),
            }
        )
    completed_at = durable.get("completed_at")
    replay.update(
        {
            "generatedAt": summary.get("generated_at")
            or (completed_at.isoformat() if completed_at else None),
            "modelVersion": durable.get("model_version") or MODEL_VERSION,
            "status": "durable_daily_settlement",
            "ledgerMode": "append_only_database_ledger",
            "ledgerRunId": durable.get("id"),
            "lastSettlementAt": completed_at.isoformat() if completed_at else None,
            "forecastsTotal": int(summary.get("forecast_total") or 0),
            "outcomesSettled": sum(
                int(item.get("matured") or 0)
                for item in summary.get("horizons", [])
                if isinstance(item, dict)
            ),
            "pendingForecasts": int(summary.get("pending_forecasts") or 0),
            "forecastsCreatedThisRun": int(durable.get("forecasts_created") or 0),
            "outcomesSettledThisRun": int(durable.get("outcomes_settled") or 0),
            "evaluationsCreatedThisRun": int(
                summary.get("evaluations_created") or 0
            ),
            "dailyCompanyUniverse": int(summary.get("daily_company_universe") or 0),
            "dailyCompanySnapshotsCreated": int(
                summary.get("daily_company_snapshots_created") or 0
            ),
            "dailyCompanySnapshotsCovered": int(
                summary.get("daily_company_snapshots_covered")
                or (
                    summary.get("daily_company_universe")
                    if summary.get("daily_company_snapshots_created")
                    else 0
                )
                or 0
            ),
            "dailyCompanyInsufficientHistory": int(
                summary.get("daily_company_insufficient_history") or 0
            ),
            "dailyCompanySnapshotGpuUsed": bool(
                summary.get("daily_company_snapshot_gpu_used", False)
            ),
            "evaluationVersion": summary.get("evaluation_version"),
            "benchmarkPolicy": _camelize(summary.get("benchmark_policy", {})),
            "archiveStatus": durable.get("archive_status"),
            "productionModelChanged": bool(
                summary.get("production_model_changed", False)
            ),
            "candidateReview": _camelize(summary.get("candidate_review", [])),
            "horizons": horizons or replay.get("horizons", []),
        }
    )
    return replay


def _canslim_scorecard(snapshot: dict[str, object]) -> dict[str, object] | None:
    derived = snapshot.get("derived_equity_evidence")
    if not isinstance(derived, list):
        return None
    scorecard = next(
        (
            item
            for item in derived
            if isinstance(item, dict)
            and item.get("category") == "derived_canslim_scorecard"
        ),
        None,
    )
    if not isinstance(scorecard, dict):
        return None
    criteria = [
        {
            "code": _text(item.get("code"), limit=2),
            "labelZh": _text(item.get("label_zh"), limit=80),
            "labelEn": _text(item.get("label_en"), limit=120),
            "weight": int(item.get("weight") or 0),
            "status": _text(item.get("status"), limit=20),
            "score": _number(item.get("score")) or 0,
            "observed": _text(item.get("observed"), limit=800),
            "threshold": _text(item.get("threshold"), limit=500),
            "evidenceCount": len(item.get("evidence_refs", []))
            if isinstance(item.get("evidence_refs"), list)
            else 0,
            "limitations": _strings(item.get("limitations"), limit=3),
        }
        for item in scorecard.get("criteria", [])
        if isinstance(item, dict)
    ]
    discipline = scorecard.get("discipline")
    discipline = discipline if isinstance(discipline, dict) else {}
    zone = discipline.get("traditional_buy_zone_proxy")
    zone = zone if isinstance(zone, list) else []
    return {
        "version": _text(scorecard.get("version"), limit=80),
        "ticker": _text(scorecard.get("ticker"), limit=16),
        "asOf": _text(scorecard.get("as_of"), limit=20),
        "overallScore": _number(scorecard.get("overall_score")) or 0,
        "coverageScore": _number(scorecard.get("coverage_score")) or 0,
        "decision": _text(scorecard.get("decision"), limit=80),
        "criteria": criteria,
        "discipline": {
            "status": _text(discipline.get("status"), limit=40),
            "pivotProxy": _number(discipline.get("pivot_proxy")),
            "buyZoneLower": _number(zone[0]) if len(zone) > 0 else None,
            "buyZoneUpper": _number(zone[1]) if len(zone) > 1 else None,
            "currentPrice": _number(discipline.get("current_price")),
            "currentPosition": _text(discipline.get("current_position"), limit=60),
            "stopLossRule": _text(discipline.get("stop_loss_rule"), limit=500),
            "profitRule": _text(discipline.get("profit_rule"), limit=500),
        },
        "limitations": _strings(scorecard.get("limitations"), limit=6),
    }


def _competitor_operating_comparison(
    snapshot: dict[str, object],
) -> dict[str, object] | None:
    derived = snapshot.get("derived_equity_evidence")
    if not isinstance(derived, list):
        return None
    comparison = next(
        (
            item
            for item in derived
            if isinstance(item, dict)
            and item.get("category") == "competitive_operating_comparison"
        ),
        None,
    )
    if not isinstance(comparison, dict):
        return None
    rows = []
    for item in comparison.get("rows", []):
        if not isinstance(item, dict):
            continue
        quarterly = item.get("quarterly")
        quarterly = quarterly if isinstance(quarterly, dict) else {}
        rows.append({
            "ticker": _text(item.get("ticker"), limit=16),
            "company": _text(item.get("company"), limit=180),
            "periodEnd": _text(item.get("period_end"), limit=20),
            "availableAt": _text(item.get("available_at"), limit=20),
            "revenueYoy": _number(item.get("revenue_yoy")),
            "grossMargin": _number(item.get("gross_margin")),
            "netMargin": _number(item.get("net_margin")),
            "researchIntensity": _number(
                item.get("research_and_development_to_revenue")
            ),
            "inventoryYoy": _number(item.get("inventory_yoy")),
            "ranks": item.get("ranks") if isinstance(item.get("ranks"), dict) else {},
            "qualityFlags": _strings(item.get("quality_flags"), limit=8),
            "quarterly": {
                "periodEnd": _text(quarterly.get("period_end"), limit=20),
                "comparisonPeriodEnd": _text(
                    quarterly.get("comparison_period_end"),
                    limit=20,
                ),
                "availableAt": _text(quarterly.get("available_at"), limit=20),
                "revenueYoy": _number(quarterly.get("revenue_yoy")),
                "grossMargin": _number(quarterly.get("gross_margin")),
                "netMargin": _number(quarterly.get("net_margin")),
                "researchIntensity": _number(
                    quarterly.get("research_and_development_to_revenue")
                ),
                "inventoryYoy": _number(quarterly.get("inventory_yoy")),
                "qualityFlags": _strings(
                    quarterly.get("quality_flags"),
                    limit=8,
                ),
                "ranks": (
                    quarterly.get("ranks")
                    if isinstance(quarterly.get("ranks"), dict)
                    else {}
                ),
            } if quarterly else None,
        })
    disclosures = [
        {
            "ticker": _text(item.get("ticker"), limit=16),
            "metricType": _text(item.get("metric_type"), limit=80),
            "metricName": _text(item.get("metric_name"), limit=180),
            "product": _text(item.get("product"), limit=180),
            "reportedValues": _strings(item.get("reported_values"), limit=8),
            "periodEnd": _text(item.get("period_end"), limit=20),
            "availableAt": _text(item.get("available_at"), limit=20),
            "filingForm": _text(item.get("filing_form"), limit=20),
            "sourceExcerpt": _text(item.get("source_excerpt"), limit=700),
            "sourceUrl": _text(item.get("source_url"), limit=1_000),
        }
        for item in comparison.get("product_disclosures", [])
        if isinstance(item, dict)
    ]
    return {
        "ticker": _text(comparison.get("ticker"), limit=16),
        "asOf": _text(comparison.get("as_of"), limit=20),
        "peerGroup": _strings(comparison.get("peer_group"), limit=8),
        "rows": rows,
        "productDisclosures": disclosures,
        "comparableProductMetricTypes": _strings(
            comparison.get("comparable_product_metric_types"),
            limit=12,
        ),
        "limitations": _strings(comparison.get("limitations"), limit=6),
    }


def _remote_report(row: dict[str, object], *, synced_at: str) -> dict[str, object] | None:
    result = row.get("result")
    snapshot = row.get("evidence_snapshot")
    if not isinstance(result, dict) or not isinstance(snapshot, dict):
        return None
    audit = snapshot.get("local_report_audit")
    if not isinstance(audit, dict) or audit.get("audit_version") not in {
        "local_report_audit_v2",
        "local_report_audit_v3",
        "local_report_audit_v4",
        "local_report_audit_v5",
        "local_report_audit_v6",
        "local_report_audit_v7",
        "local_report_audit_v8",
        "local_report_audit_v9",
        "local_report_audit_v10",
        "local_report_audit_v11_product_chain_gate",
        "local_report_audit_v12_a_share_confidence_gate",
    }:
        return None
    hypotheses = [item for item in result.get("hypotheses", []) if isinstance(item, dict)]
    primary = hypotheses[0] if hypotheses else {}
    paper = result.get("paper_report") if isinstance(result.get("paper_report"), dict) else {}
    steps = [item for item in primary.get("steps", []) if isinstance(item, dict)][:6]
    chain = [
        {
            "title": _text(step.get("label") or f"Step {index}", limit=220),
            "claim": _text(step.get("label") or step.get("claim"), limit=600),
            "status": _status(step.get("status")),
            "confidence": round(float(step.get("confidence") or 0) * 100),
            "evidenceCount": len(step.get("evidence_refs", [])) if isinstance(step.get("evidence_refs"), list) else 0,
        }
        for index, step in enumerate(steps, start=1)
    ]
    if not chain:
        chain = [{"title": "本地研究结论", "claim": _text(result.get("summary"), limit=600), "status": "partial", "confidence": 0, "evidenceCount": 0}]

    evidence_by_id: dict[str, dict[str, object]] = {}
    evidence_sections = (
        "documents",
        "derived_equity_evidence",
        "market_observations",
        "company_financials",
        "events",
        "economic_observations",
        "energy_observations",
        "priority_evidence",
    )
    fallback: list[dict[str, object]] = []
    for section in evidence_sections:
        values = snapshot.get(section)
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            evidence_id = str(item.get("evidence_id") or "")
            if evidence_id:
                evidence_by_id.setdefault(evidence_id, item)
            if item.get("can_verify_claims") is True or section == "derived_equity_evidence":
                fallback.append(item)
    referenced_evidence: list[dict[str, object]] = []
    for ref in _reference_ids(result):
        item = evidence_by_id.get(ref)
        if item and item not in referenced_evidence:
            referenced_evidence.append(item)

    representative_categories = (
        "derived_company_valuation",
        "derived_company_financial_trend",
        "product_operating_evidence",
        "derived_market_technical",
        "derived_macro_sensitivity",
        "company_news_document",
        "supply_chain_site_exposure",
        "institutional_holding",
        "insider_transaction",
    )
    selected_evidence: list[dict[str, object]] = []
    for category in representative_categories:
        representative = next(
            (item for item in referenced_evidence if item.get("category") == category),
            None,
        )
        if representative is not None:
            selected_evidence.append(representative)
    for item in referenced_evidence:
        if len(selected_evidence) >= 10:
            break
        if item not in selected_evidence:
            selected_evidence.append(item)
    for item in fallback:
        if len(selected_evidence) >= 10:
            break
        if item not in selected_evidence:
            selected_evidence.append(item)

    documents = [item for item in snapshot.get("documents", []) if isinstance(item, dict)] if isinstance(snapshot.get("documents"), list) else []
    full_documents = sum(1 for item in documents if item.get("can_verify_claims") is True)
    headline_documents = sum(1 for item in documents if item.get("evidence_tier") == "headline_only")
    checks = audit.get("checks") if isinstance(audit.get("checks"), dict) else {}
    cited = max(1, int(checks.get("cited_reference_count") or 0))
    missing = int(checks.get("missing_reference_count") or 0)
    headline = int(checks.get("headline_only_reference_count") or 0)
    future = int(checks.get("future_dated_reference_count") or 0)
    foreign = int(checks.get("foreign_subject_count") or 0)
    profit_count = int(checks.get("profit_validation_count") or 0)
    robust_positive = int(checks.get("robust_positive_count") or 0)
    score_rows = [
        {"label": "引用完整性", "score": max(0, round(100 * (cited - missing) / cited)), "weight": 25},
        {"label": "正文证据准入", "score": max(0, round(100 * (cited - headline) / cited)), "weight": 20},
        {"label": "时间一致性", "score": 100 if future == 0 else max(0, 100 - 20 * future), "weight": 15},
        {"label": "主体一致性", "score": 100 if foreign == 0 else max(0, 100 - 20 * foreign), "weight": 15},
        {"label": "样本外稳健性", "score": round(100 * robust_positive / profit_count) if profit_count else 0, "weight": 25},
    ]
    directional_confidence = snapshot.get("directional_confidence")
    directional_confidence = (
        directional_confidence if isinstance(directional_confidence, dict) else {}
    )
    primary_confidence = primary.get("confidence")
    if primary_confidence is None:
        primary_confidence = directional_confidence.get("score")
    confidence = max(0, min(100, round(float(primary_confidence or 0) * 100)))
    findings = _strings(paper.get("findings"), limit=6)
    limitations = _strings(paper.get("limitations"), limit=6)
    alternatives = _strings(paper.get("alternative_explanations"), limit=6) or _strings(primary.get("counterarguments"), limit=6)
    gaps = _strings(primary.get("evidence_gaps"), limit=6)
    next_questions = _strings(result.get("suggested_next_questions"), limit=6)
    context = snapshot.get("equity_research_context") if isinstance(snapshot.get("equity_research_context"), dict) else {}
    readiness = context.get("data_readiness")
    readiness = readiness if isinstance(readiness, dict) else None
    readiness_components = (
        [item for item in readiness.get("components", []) if isinstance(item, dict)]
        if readiness
        else []
    )
    official_disclosures = context.get("official_disclosure_coverage")
    official_disclosures = (
        official_disclosures if isinstance(official_disclosures, dict) else {}
    )
    structured_disclosures = context.get("structured_disclosure_coverage")
    structured_disclosures = (
        structured_disclosures if isinstance(structured_disclosures, dict) else {}
    )
    market_cutoff = _text(context.get("point_in_time_cutoff") or snapshot.get("generated_at"), limit=80)
    supply_cutoff = _text(context.get("supply_chain_point_in_time_cutoff"), limit=80)
    data_cutoff = market_cutoff
    if supply_cutoff and supply_cutoff != market_cutoff:
        data_cutoff = f"market {market_cutoff} · supply chain {supply_cutoff}"
    return {
        "id": f"local-{row['id']}",
        "origin": "local_ollama",
        "localInquiryId": int(row["id"]),
        "marketRegion": _text(context.get("market_region"), limit=16) or "global",
        "ticker": _text(context.get("ticker"), limit=32),
        "companyName": _text(context.get("company"), limit=255),
        "sector": _text(context.get("sector"), limit=128),
        "analysisMode": "news_first",
        "question": _text(result.get("question") or row.get("question"), limit=1_000),
        "thesis": _text(result.get("summary"), limit=3_000),
        "verdict": _recommendation(audit.get("recommendation")),
        "confidence": confidence,
        "confidenceDetail": (
            {
                "scoreKind": _text(
                    directional_confidence.get("score_kind"),
                    limit=120,
                ),
                "formula": _text(directional_confidence.get("formula"), limit=160),
                "rawChainScore": round(
                    float(directional_confidence.get("raw_chain_score") or 0) * 100
                ),
                "dataReadinessCap": round(
                    float(directional_confidence.get("data_readiness_cap") or 0) * 100
                ),
                "dataReadinessScore": (
                    round(float(directional_confidence["data_readiness_score"]) * 100)
                    if directional_confidence.get("data_readiness_score") is not None
                    else None
                ),
                "verifiedSteps": int(
                    directional_confidence.get("verified_steps") or 0
                ),
                "partiallySupportedSteps": int(
                    directional_confidence.get("partially_supported_steps") or 0
                ),
                "unresolvedSteps": int(
                    directional_confidence.get("unresolved_steps") or 0
                ),
                "validatedAlphaSupported": bool(
                    directional_confidence.get("validated_alpha_supported")
                ),
                "blockersZh": _strings(
                    directional_confidence.get("blockers_zh"),
                    limit=8,
                ),
                "blockersEn": _strings(
                    directional_confidence.get("blockers_en"),
                    limit=8,
                ),
            }
            if directional_confidence
            else None
        ),
        "createdAt": row["created_at"].isoformat(),
        "updatedAt": row["updated_at"].isoformat(),
        "syncedAt": synced_at,
        "model": _text(row.get("local_model"), limit=255),
        "dataCutoff": data_cutoff,
        "audit": {
            "version": audit.get("audit_version"),
            "status": audit.get("status"),
            "recommendation": audit.get("recommendation"),
            "openaiUsed": bool(audit.get("openai_used")),
            "citedReferences": cited,
            "missingReferences": missing,
            "headlineOnlyReferences": headline,
            "futureDatedReferences": future,
            "foreignSubjects": foreign,
            "repairsApplied": len(audit.get("repairs_applied", [])) if isinstance(audit.get("repairs_applied"), list) else 0,
        },
        "dataReadiness": (
            {
                "version": _text(readiness.get("version"), limit=80),
                "score": round(float(readiness.get("score") or 0) * 100),
                "status": _text(readiness.get("status"), limit=80),
                "directionalConclusionAllowed": bool(
                    readiness.get("directional_conclusion_allowed")
                ),
                "confidenceCap": round(
                    float(readiness.get("confidence_cap") or 0) * 100
                ),
                "missingRequired": _strings(
                    readiness.get("missing_required"),
                    limit=12,
                ),
                "policyZh": _text(readiness.get("policy_zh"), limit=600),
                "policyEn": _text(readiness.get("policy_en"), limit=600),
                "components": [
                    {
                        "key": _text(item.get("key"), limit=80),
                        "labelZh": _text(item.get("label_zh"), limit=160),
                        "labelEn": _text(item.get("label_en"), limit=160),
                        "weight": int(item.get("weight") or 0),
                        "score": round(float(item.get("score") or 0) * 100),
                        "status": _text(item.get("status"), limit=40),
                        "detailZh": _text(item.get("detail_zh"), limit=500),
                        "detailEn": _text(item.get("detail_en"), limit=500),
                    }
                    for item in readiness_components
                ],
            }
            if readiness
            else None
        ),
        "disclosureCoverage": (
            {
                "status": _text(official_disclosures.get("status"), limit=80),
                "periodStart": _text(
                    official_disclosures.get("period_start"), limit=20
                ),
                "periodEnd": _text(
                    official_disclosures.get("period_end"), limit=20
                ),
                "periodicReports": int(
                    official_disclosures.get("periodic_reports") or 0
                ),
                "shareholderDocuments": int(
                    official_disclosures.get("shareholder_documents") or 0
                ),
                "operatingDocuments": int(
                    official_disclosures.get("operating_documents") or 0
                ),
                "supplyChainDocuments": int(
                    official_disclosures.get("supply_chain_documents") or 0
                ),
                "structuredStatus": _text(
                    structured_disclosures.get("status"), limit=100
                ),
                "financialMetrics": int(
                    structured_disclosures.get("financial_metrics") or 0
                ),
                "shareholderExcerpts": int(
                    structured_disclosures.get("shareholder_excerpts") or 0
                ),
                "operatingExcerpts": int(
                    structured_disclosures.get("operating_excerpts") or 0
                ),
                "supplyChainExcerpts": int(
                    structured_disclosures.get("supply_chain_excerpts") or 0
                ),
            }
            if official_disclosures or structured_disclosures
            else None
        ),
        "newsReport": {
            "headline": _text(paper.get("title") or primary.get("title") or row.get("question"), limit=500),
            "narrative": _text(paper.get("abstract") or result.get("summary"), limit=2_500),
            "facts": findings or [_text(step.get("label"), limit=500) for step in steps if _status(step.get("status")) == "verified"][:6],
            "uncertainties": limitations or gaps,
            "documentsReviewed": len(documents),
            "fullContentReviewed": full_documents,
            "headlineOnlyExcluded": max(headline_documents, headline),
        },
        "chain": chain,
        "evidence": [_evidence_item(item) for item in selected_evidence[:10]],
        "alternatives": alternatives,
        "limitations": limitations + [item for item in gaps if item not in limitations][: max(0, 6 - len(limitations))],
        "nextData": next_questions or gaps,
        "scores": score_rows,
        "tradingScenario": _trading_scenario(snapshot),
        "canslim": _canslim_scorecard(snapshot),
        "competitorComparison": _competitor_operating_comparison(snapshot),
    }


def dump(name: str, value: object, *, pretty: bool = False) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=None if pretty else (",", ":"),
            indent=2 if pretty else None,
        ),
        encoding="utf-8",
    )


def _research_report_index_item(report: dict[str, object]) -> dict[str, object]:
    audit = report.get("audit") if isinstance(report.get("audit"), dict) else None
    readiness = (
        report.get("dataReadiness")
        if isinstance(report.get("dataReadiness"), dict)
        else None
    )
    disclosure = (
        report.get("disclosureCoverage")
        if isinstance(report.get("disclosureCoverage"), dict)
        else None
    )
    scenario = (
        report.get("tradingScenario")
        if isinstance(report.get("tradingScenario"), dict)
        else None
    )
    return {
        "id": report.get("id"),
        "localInquiryId": report.get("localInquiryId"),
        "historical": report.get("historical"),
        "dataCutoff": report.get("dataCutoff"),
        "questionEn": report.get("questionEn"),
        "marketRegion": report.get("marketRegion"),
        "ticker": report.get("ticker"),
        "companyName": report.get("companyName"),
        "sector": report.get("sector"),
        "analysisMode": report.get("analysisMode"),
        "question": report.get("question"),
        "model": report.get("model"),
        "confidence": report.get("confidence"),
        "createdAt": report.get("createdAt"),
        "updatedAt": report.get("updatedAt"),
        "audit": (
            {
                key: audit.get(key)
                for key in (
                    "status",
                    "missingReferences",
                    "headlineOnlyReferences",
                    "futureDatedReferences",
                    "foreignSubjects",
                )
            }
            if audit
            else None
        ),
        "dataReadiness": (
            {
                "score": readiness.get("score"),
                "directionalConclusionAllowed": readiness.get(
                    "directionalConclusionAllowed"
                ),
            }
            if readiness
            else None
        ),
        "disclosureCoverage": (
            {
                "status": disclosure.get("status"),
                "financialMetrics": disclosure.get("financialMetrics"),
            }
            if disclosure
            else None
        ),
        "tradingScenario": (
            {
                key: ([] if key == "chart" else scenario.get(key))
                for key in (
                    "ticker",
                    "observedOn",
                    "entryPrice",
                    "support",
                    "stopReference",
                    "targetReference",
                    "rewardRiskRatio",
                    "downsideFraction",
                    "upsideFraction",
                    "atr14",
                    "chart",
                )
            }
            if scenario
            else None
        ),
        "hasCompetitorComparison": isinstance(
            report.get("competitorComparison"), dict
        ),
    }


def dump_research_report_assets(
    reports: list[dict[str, object]], *, generated_at: str
) -> None:
    """Keep the hosted worker light and deliver only one report body on demand."""
    REPORT_DETAIL_OUTPUT.mkdir(parents=True, exist_ok=True)
    # Frozen file-backed dossier revisions are not ResearchInquiry rows. Preserve
    # them explicitly during a DB snapshot refresh instead of silently deleting
    # the only published index/body pair. Full content validation runs at packing.
    ids = {r.get('id') for r in reports}
    for archived in sorted(REPORT_DETAIL_OUTPUT.glob('dossier-*.json')):
        import hashlib
        report = json.loads(archived.read_text(encoding='utf-8'))['report']
        dossier_path = REPORT_DETAIL_OUTPUT.parent/'company-dossiers'/archived.name
        review_path = REPORT_DETAIL_OUTPUT.parent/'dossier-reviews'/archived.name
        dossier = json.loads(dossier_path.read_text(encoding='utf-8'))
        consolidated = dossier.get('version') == 'consolidated-site/v1'
        receipt = json.loads(review_path.read_text(encoding='utf-8')) if consolidated else {}
        valid_review = (
            dossier.get('review', {}).get('state') == 'assistant_reviewed_research_only'
            and receipt.get('version') == 'consolidated-publication/v1'
            and receipt.get('siteDossierSha256') == hashlib.sha256(dossier_path.read_bytes()).hexdigest()
            and receipt.get('reviewedDossierSha256') == dossier.get('provenance', {}).get('reviewedDossierHash')
            and receipt.get('wholeReportAudit') == dossier.get('wholeReportAudit')
            and dossier.get('eligibleForPredictiveBacktest') is False
            and dossier.get('validatedAlpha') is False
        ) if consolidated else (
            dossier.get('review', {}).get('state') == 'assistant_reviewed'
            and dossier['review'].get('assistantRevisionHash') == hashlib.sha256(review_path.read_bytes()).hexdigest()
        )
        if (report.get('id') != archived.stem or dossier.get('ticker') != report.get('ticker')
                or dossier.get('asOf') != report.get('dataCutoff')
                or not valid_review):
            raise ValueError('Cannot preserve an unverified dossier archive')
        if report['id'] not in ids:
            reports.append(report)
            ids.add(report['id'])
    for stale in REPORT_DETAIL_OUTPUT.glob("*.json"):
        stale.unlink()
    for report in reports:
        report_id = str(report.get("id") or "")
        safe_id = "".join(
            character
            for character in report_id
            if character.isalnum() or character in {"-", "_"}
        )
        if not safe_id or safe_id != report_id:
            raise ValueError(f"unsafe report id for hosted asset: {report_id!r}")
        (REPORT_DETAIL_OUTPUT / f"{safe_id}.json").write_text(
            json.dumps(
                {"report": report},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
    dump(
        "research-report-index.json",
        {
            "generatedAt": generated_at,
            "total": len(reports),
            "detailEndpoint": "/api/research-report?id=",
            "reports": [_research_report_index_item(report) for report in reports],
        },
    )


def _supply_chain_snapshot(tickers: list[str], *, as_of: str) -> dict[str, object]:
    sites_by_id: dict[int, dict[str, object]] = {}
    summaries: list[dict[str, object]] = []
    for ticker in tickers:
        query = urlencode({"as_of": as_of, "weeks": 12, "limit": 500})
        request = Request(
            f"{LOCAL_API_URL}/companies/supply-chain/{ticker}/sites?{query}",
            headers={"User-Agent": "NEWS-Map-Pilot-Snapshot/1.0"},
        )
        with urlopen(request, timeout=120) as response:
            payload = json.load(response)
        summaries.append(
            {
                "ticker": ticker,
                "siteCount": int(payload.get("site_count") or 0),
                "returnedSiteCount": int(payload.get("returned_site_count") or 0),
                "geocodedSiteCount": int(payload.get("geocoded_site_count") or 0),
                "exactFacilityCount": int(payload.get("exact_facility_count") or 0),
                "companyFacilityCount": int(
                    payload.get("company_facility_count") or 0
                ),
                "supplierLocationCount": int(
                    payload.get("supplier_location_count") or 0
                ),
                "conflictExposedCount": int(payload.get("conflict_exposed_count") or 0),
                "disasterExposedCount": int(payload.get("disaster_exposed_count") or 0),
                "powerSignalCount": int(payload.get("power_signal_count") or 0),
                "truncated": bool(payload.get("truncated")),
            }
        )
        for item in payload.get("sites") or []:
            if not isinstance(item, dict):
                continue
            site_id = int(item["site_id"])
            context_ticker = _text(item.get("context_ticker") or ticker, limit=16)
            facility_role = _text(item.get("facility_role"), limit=40)
            exported_site = {
                    "siteId": site_id,
                    "contextTicker": context_ticker,
                    "contextTickers": [context_ticker],
                    "facilityRole": facility_role,
                    "subjectTicker": _text(item.get("subject_ticker"), limit=16),
                    "relatedCompanyName": _text(
                        item.get("related_company_name"), limit=220
                    ),
                    "relatedTicker": _text(item.get("related_ticker"), limit=16),
                    "siteKind": _text(item.get("site_kind"), limit=40),
                    "siteName": _text(item.get("site_name"), limit=220),
                    "countryName": _text(item.get("country_name"), limit=100),
                    "countryIso2": _text(item.get("country_iso2"), limit=2),
                    "admin1Name": _text(item.get("admin1_name"), limit=120),
                    "coordinates": [
                        float(item["longitude"]),
                        float(item["latitude"]),
                    ],
                    "coordinatePrecision": _text(
                        item.get("coordinate_precision"), limit=40
                    ),
                    "verificationStatus": _text(
                        item.get("verification_status"), limit=40
                    ),
                    "associationScope": _text(
                        item.get("association_scope"), limit=60
                    ),
                    "sourceUrl": _text(item.get("source_url"), limit=1_000),
                    "sourceExcerpt": _text(item.get("source_excerpt"), limit=500),
                    "availableAt": _text(item.get("available_at"), limit=20),
                    "conflictEvents": int(item.get("conflict_events") or 0),
                    "conflictFatalities": int(item.get("conflict_fatalities") or 0),
                    "disasterEventCount": int(item.get("disaster_event_count") or 0),
                    "powerSignalCount": int(item.get("power_signal_count") or 0),
                    "nearestPort": item.get("nearest_port"),
                    "portRouteStatus": _text(item.get("port_route_status"), limit=60),
                    "exposureAttentionScore": float(
                        item.get("exposure_attention_score") or 0
                    ),
                    "periodStart": _text(item.get("period_start"), limit=20),
                    "periodEnd": _text(item.get("period_end"), limit=20),
                }
            existing = sites_by_id.get(site_id)
            if existing is None:
                sites_by_id[site_id] = exported_site
                continue
            context_tickers = {
                str(value)
                for value in existing.get("contextTickers", [])
                if str(value)
            }
            context_tickers.add(context_ticker)
            if (
                facility_role == "company_facility"
                and existing.get("facilityRole") != "company_facility"
            ):
                exported_site["contextTickers"] = sorted(context_tickers)
                sites_by_id[site_id] = exported_site
            else:
                existing["contextTickers"] = sorted(context_tickers)
    return {
        "generatedAt": datetime.now(UTC).isoformat(),
        "asOf": as_of,
        "weeks": 12,
        "summaries": summaries,
        "sites": list(sites_by_id.values()),
        "methodology": (
            "Source-reviewed company facilities and upstream supplier locations with "
            "clustered rendering. Region centroids are references, not exact factories; "
            "proximity is not proof of disruption or customer-specific production."
        ),
    }


def _period_return(values: list[float], sessions: int) -> float | None:
    if len(values) <= sessions or values[-sessions - 1] == 0:
        return None
    return values[-1] / values[-sessions - 1] - 1


def _annualized_volatility(values: list[float]) -> float | None:
    if len(values) < 3:
        return None
    returns = [current / previous - 1 for previous, current in pairwise(values)]
    mean = sum(returns) / len(returns)
    variance = sum((item - mean) ** 2 for item in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(252)


def _maximum_drawdown(values: list[float]) -> float | None:
    if not values:
        return None
    peak = values[0]
    drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        drawdown = min(drawdown, value / peak - 1)
    return drawdown


def _first_fact(
    facts: dict[str, dict[str, object]],
    *names: str,
) -> dict[str, object] | None:
    candidates = [facts[name] for name in names if name in facts]
    return max(
        candidates,
        key=lambda item: (item["period_end"], item["filed_at"]),
        default=None,
    )


def _fact_for_period(
    row: dict[str, object] | None,
    period_end: object,
) -> dict[str, object] | None:
    if row is None or row["period_end"] != period_end:
        return None
    return row


def _semiconductor_comparison_snapshot(cursor: object, *, generated_at: str) -> dict[str, object]:
    """Build a same-cutoff comparison without using an LLM or inventing rankings."""
    tickers = list(SEMICONDUCTOR_COMPARISON_TICKERS)
    cursor.execute(
        """
        SELECT p.ticker, p.name, p.industry, p.source_url,
               coalesce(c.verified_edges, 0) AS verified_edges,
               coalesce(c.candidate_edges, 0) AS candidate_edges,
               (SELECT count(*) FROM company_supply_chain_edges e
                WHERE e.subject_ticker=p.ticker AND e.review_status='verified'
                  AND e.related_company_name LIKE 'Undisclosed%%') AS unnamed_verified_edges,
               (SELECT count(*) FROM company_filings f
                WHERE f.ticker=p.ticker) AS filing_count,
               (SELECT count(*) FROM company_institutional_holdings h
                WHERE h.ticker=p.ticker) AS institutional_count,
               (SELECT count(*) FROM company_insider_transactions i
                WHERE i.ticker=p.ticker) AS insider_count
        FROM company_profiles p
        LEFT JOIN company_supply_chain_coverage c ON c.ticker=p.ticker
        WHERE p.ticker = ANY(%s)
        ORDER BY array_position(%s::text[], p.ticker)
        """,
        (tickers, tickers),
    )
    profiles = {str(row["ticker"]): row for row in cursor.fetchall()}
    cursor.execute(
        """
        SELECT series_id, observed_on, open_price, high_price, low_price,
               close_price, volume
        FROM market_daily_bars
        WHERE series_id = ANY(%s)
        ORDER BY series_id, observed_on
        """,
        ([f"EQ:{ticker}" for ticker in tickers],),
    )
    bars: dict[str, list[dict[str, object]]] = {ticker: [] for ticker in tickers}
    for row in cursor.fetchall():
        bars[str(row["series_id"]).removeprefix("EQ:")].append(row)

    concepts = [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "NetIncomeLoss",
        "ProfitLoss",
        "ResearchAndDevelopmentExpense",
        "CommonStockSharesOutstanding",
        "StockholdersEquity",
        "LongTermDebtCurrent",
        "LongTermDebtNoncurrent",
    ]
    cursor.execute(
        """
        SELECT ticker, concept, value, unit, period_end, filed_at, source_url
        FROM company_financial_facts
        WHERE ticker = ANY(%s)
          AND concept = ANY(%s)
          AND form IN ('10-K', '10-K/A')
          AND fiscal_period = 'FY'
        ORDER BY ticker, period_end DESC, filed_at DESC
        """,
        (tickers, concepts),
    )
    facts: dict[str, dict[str, dict[str, object]]] = {ticker: {} for ticker in tickers}
    for row in cursor.fetchall():
        facts[str(row["ticker"])].setdefault(str(row["concept"]), row)

    companies: list[dict[str, object]] = []
    for ticker in tickers:
        profile = profiles[ticker]
        ticker_bars = bars[ticker]
        closes = [float(row["close_price"]) for row in ticker_bars]
        volumes = [float(row["volume"]) if row["volume"] is not None else None for row in ticker_bars]
        ticker_facts = facts[ticker]

        revenue_row = _first_fact(
            ticker_facts,
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        )
        income_row = _first_fact(ticker_facts, "NetIncomeLoss", "ProfitLoss")
        rnd_row = _first_fact(ticker_facts, "ResearchAndDevelopmentExpense")
        shares_row = _first_fact(ticker_facts, "CommonStockSharesOutstanding")
        equity_row = _first_fact(ticker_facts, "StockholdersEquity")
        debt_current_row = _first_fact(ticker_facts, "LongTermDebtCurrent")
        debt_noncurrent_row = _first_fact(ticker_facts, "LongTermDebtNoncurrent")
        fiscal_period_end = revenue_row["period_end"] if revenue_row else None

        income_row = _fact_for_period(income_row, fiscal_period_end)
        rnd_row = _fact_for_period(rnd_row, fiscal_period_end)
        shares_row = _fact_for_period(shares_row, fiscal_period_end)
        equity_row = _fact_for_period(equity_row, fiscal_period_end)
        debt_current_row = _fact_for_period(debt_current_row, fiscal_period_end)
        debt_noncurrent_row = _fact_for_period(debt_noncurrent_row, fiscal_period_end)
        revenue = float(revenue_row["value"]) if revenue_row else None
        net_income = float(income_row["value"]) if income_row else None
        research_and_development = float(rnd_row["value"]) if rnd_row else None
        shares = float(shares_row["value"]) if shares_row else None
        equity = float(equity_row["value"]) if equity_row else None
        debt = sum(
            float(row["value"])
            for row in (debt_current_row, debt_noncurrent_row)
            if row is not None
        )
        latest_close = closes[-1] if closes else None
        market_cap = latest_close * shares if latest_close is not None and shares else None
        volume_values = [value for value in volumes[-20:] if value is not None]
        complete_ohlcv = len(ticker_bars) >= 252 and all(
            row["volume"] is not None for row in ticker_bars[-252:]
        )
        required_facts = (revenue, net_income, research_and_development, shares, equity)
        missing: list[str] = []
        if not complete_ohlcv:
            missing.append("complete_ohlcv")
        if any(value is None for value in required_facts):
            missing.append("annual_fundamentals")
        if int(profile["verified_edges"]) == 0:
            missing.append("verified_supply_chain")
        market_score = 30 if complete_ohlcv else 15 if len(closes) >= 252 else 0
        fundamental_score = round(
            35 * sum(value is not None for value in required_facts) / len(required_facts)
        )
        filing_score = 10 if int(profile["filing_count"]) else 0
        ownership_score = 5 * int(int(profile["institutional_count"]) > 0) + 5 * int(
            int(profile["insider_count"]) > 0
        )
        supply_score = round(15 * min(int(profile["verified_edges"]), 3) / 3)
        data_score = market_score + fundamental_score + filing_score + ownership_score + supply_score
        companies.append(
            {
                "ticker": ticker,
                "name": profile["name"],
                "industry": profile["industry"],
                "dataCoverageScore": data_score,
                "dataStatus": "comparison_ready" if data_score >= 85 else "bounded_comparison",
                "missing": missing,
                "market": {
                    "historyStart": ticker_bars[0]["observed_on"].isoformat() if ticker_bars else None,
                    "historyEnd": ticker_bars[-1]["observed_on"].isoformat() if ticker_bars else None,
                    "barCount": len(ticker_bars),
                    "completeOhlcv": complete_ohlcv,
                    "latestClose": latest_close,
                    "return21d": _period_return(closes, 21),
                    "return63d": _period_return(closes, 63),
                    "return252d": _period_return(closes, 252),
                    "annualizedVolatility63d": _annualized_volatility(closes[-64:]),
                    "maximumDrawdown252d": _maximum_drawdown(closes[-252:]),
                    "sma20": sum(closes[-20:]) / 20 if len(closes) >= 20 else None,
                    "sma50": sum(closes[-50:]) / 50 if len(closes) >= 50 else None,
                    "sma200": sum(closes[-200:]) / 200 if len(closes) >= 200 else None,
                    "volumeRatio20": (
                        volumes[-1] / (sum(volume_values) / len(volume_values))
                        if volumes and volumes[-1] is not None and volume_values
                        else None
                    ),
                },
                "fundamentals": {
                    "periodEnd": revenue_row["period_end"].isoformat() if revenue_row else None,
                    "revenue": revenue,
                    "netIncome": net_income,
                    "researchAndDevelopment": research_and_development,
                    "netMargin": net_income / revenue if net_income is not None and revenue else None,
                    "researchIntensity": (
                        research_and_development / revenue
                        if research_and_development is not None and revenue
                        else None
                    ),
                    "marketCapitalizationProxy": market_cap,
                    "priceToSalesProxy": market_cap / revenue if market_cap is not None and revenue else None,
                    "priceToEarningsProxy": (
                        market_cap / net_income
                        if market_cap is not None and net_income is not None and net_income > 0
                        else None
                    ),
                    "debtToEquity": debt / equity if equity and debt else 0.0 if equity else None,
                    "sourceUrl": revenue_row["source_url"] if revenue_row else profile["source_url"],
                },
                "evidence": {
                    "filingCount": int(profile["filing_count"]),
                    "institutionalObservationCount": int(profile["institutional_count"]),
                    "insiderTransactionCount": int(profile["insider_count"]),
                    "verifiedSupplyChainEdges": int(profile["verified_edges"]),
                    "unnamedVerifiedSupplyChainEdges": int(profile["unnamed_verified_edges"]),
                    "candidateSupplyChainEdges": int(profile["candidate_edges"]),
                },
            }
        )

    def leader(path: tuple[str, str], *, reverse: bool = True) -> dict[str, object] | None:
        section, key = path
        eligible = [
            item
            for item in companies
            if isinstance(item.get(section), dict) and item[section].get(key) is not None
        ]
        return sorted(eligible, key=lambda item: float(item[section][key]), reverse=reverse)[0] if eligible else None

    momentum = leader(("market", "return63d"))
    volatility = leader(("market", "annualizedVolatility63d"))
    margin = leader(("fundamentals", "netMargin"))
    findings = [
        {
            "key": "momentum_63d",
            "ticker": momentum["ticker"] if momentum else None,
            "labelZh": "63 日相对动量最高",
            "labelEn": "Highest 63-session momentum",
            "value": momentum["market"]["return63d"] if momentum else None,
            "caveatZh": "仅描述截至同一交易日的历史涨跌，不预测后续方向。",
            "caveatEn": "Historical same-cutoff return only; it does not predict direction.",
        },
        {
            "key": "volatility_63d",
            "ticker": volatility["ticker"] if volatility else None,
            "labelZh": "63 日历史波动最高",
            "labelEn": "Highest 63-session historical volatility",
            "value": volatility["market"]["annualizedVolatility63d"] if volatility else None,
            "caveatZh": "波动率衡量价格离散程度，不等同于亏损概率。",
            "caveatEn": "Volatility measures dispersion, not loss probability.",
        },
        {
            "key": "latest_annual_margin",
            "ticker": margin["ticker"] if margin else None,
            "labelZh": "最新年度净利率最高",
            "labelEn": "Highest latest annual net margin",
            "value": margin["fundamentals"]["netMargin"] if margin else None,
            "caveatZh": "各公司财年截止日不同，报告同时显示原始截止日。",
            "caveatEn": "Fiscal year-ends differ and are disclosed for each issuer.",
        },
    ]
    return {
        "version": "semiconductor_comparison_v1",
        "generatedAt": generated_at,
        "marketDataCutoff": max(
            (str(item["market"]["historyEnd"]) for item in companies if item["market"]["historyEnd"]),
            default=None,
        ),
        "titleZh": "MU · NVDA · AMD · MSFT 半导体与算力链横向报告",
        "titleEn": "MU · NVDA · AMD · MSFT semiconductor and compute-chain comparison",
        "verdictZh": "同口径数据比较已完成；不构成股票排名、买入建议或目标价。",
        "verdictEn": "Same-method comparison complete; this is not a stock ranking, buy call or price target.",
        "openaiUsed": False,
        "companies": companies,
        "findings": findings,
        "methodologyZh": "价格统一使用拆股调整日线 OHLCV；财务使用报告日前可获得的最新年度 SEC 事实；市值及估值为最新收盘价乘期末股数的可复核代理值。未具名供应依赖保留为“未披露”，不猜测公司身份。",
        "methodologyEn": "Prices use split-adjusted daily OHLCV; fundamentals use the latest annual SEC facts available by the report date; capitalization and multiples are auditable proxies using latest close and period-end shares. Unnamed dependencies remain undisclosed rather than inferred.",
    }


def main() -> None:
    with psycopg.connect(  # noqa: SIM117
        DATABASE_URL, row_factory=dict_row
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, title, summary, event_type, start_at, end_at,
                       country_code, severity, confidence, latitude, longitude
                FROM events
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL
                  AND start_at >= DATE '2025-01-01'
                ORDER BY start_at DESC, id DESC
                """
            )
            ucdp_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT d.id, d.title, d.language, d.published_at, d.url,
                       length(coalesce(d.body, '')) AS body_characters,
                       d.credibility_score, s.name AS source_name, s.country,
                       d.raw_metadata->>'collector' AS collector
                FROM documents d
                JOIN sources s ON s.id = d.source_id
                WHERE d.raw_metadata->>'collector' IN ('rss', 'gdelt_doc_discovery')
                ORDER BY d.published_at DESC NULLS LAST, d.id DESC
                """
            )
            article_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                  (SELECT count(*) FROM events WHERE latitude IS NOT NULL AND longitude IS NOT NULL) AS local_events,
                  (SELECT count(*) FROM conflict_aggregate_observations) AS local_acled_rows,
                  (SELECT coalesce(sum(events), 0) FROM conflict_aggregate_observations) AS local_acled_events,
                  (SELECT count(*) FROM documents WHERE raw_metadata->>'collector'='rss') AS rss_documents,
                  (SELECT count(*) FROM documents WHERE raw_metadata->>'collector'='rss' AND length(coalesce(body,'')) >= 100) AS substantive_articles,
                  (SELECT count(*) FROM documents WHERE raw_metadata->>'collector'='gdelt_doc_discovery') AS headline_only_discovery,
                  (SELECT min(start_at) FROM events WHERE latitude IS NOT NULL AND longitude IS NOT NULL) AS event_min,
                  (SELECT max(start_at) FROM events WHERE latitude IS NOT NULL AND longitude IS NOT NULL) AS event_max,
                  (SELECT min(published_at) FROM documents WHERE raw_metadata->>'collector'='rss' AND length(coalesce(body,'')) >= 100) AS news_min,
                  (SELECT max(published_at) FROM documents WHERE raw_metadata->>'collector'='rss' AND length(coalesce(body,'')) >= 100) AS news_max
                """
            )
            totals = cursor.fetchone()

            cursor.execute(
                """
                WITH latest_job AS (
                  SELECT id, status, total_documents, processed_documents,
                         parameters->'document_ids' AS document_ids,
                         parameters->>'batch_size' AS configured_batch_size,
                         error_message, started_at, completed_at, updated_at
                  FROM cluster_jobs
                  ORDER BY id DESC
                  LIMIT 1
                ), job_documents AS (
                  SELECT j.id AS job_id, value::bigint AS document_id
                  FROM latest_job j
                  CROSS JOIN LATERAL json_array_elements_text(
                    coalesce(j.document_ids, '[]'::json)
                  )
                )
                SELECT j.id, j.status, j.total_documents, j.processed_documents,
                       j.configured_batch_size,
                       j.error_message,
                       j.started_at, j.completed_at, j.updated_at,
                       count(d.document_id) FILTER (
                         WHERE a.extraction->>'extractor' LIKE 'ollama:%%'
                       ) AS local_model_documents,
                       count(d.document_id) FILTER (
                         WHERE a.extraction->>'extractor' LIKE 'ollama:%%'
                           AND a.extraction->>'extractor' NOT LIKE '%%+repair-v1'
                       ) AS direct_model_documents,
                       count(d.document_id) FILTER (
                         WHERE a.extraction->>'extractor' LIKE '%%+repair-v1'
                       ) AS repaired_documents,
                       count(d.document_id) FILTER (
                         WHERE a.extraction->>'extractor' = 'mock-v1'
                       ) AS fallback_documents,
                       count(d.document_id) FILTER (
                         WHERE a.document_id IS NULL
                       ) AS pending_documents,
                       max(a.extraction->>'extractor') FILTER (
                         WHERE a.extraction->>'extractor' LIKE 'ollama:%%'
                       ) AS local_model
                FROM latest_job j
                LEFT JOIN job_documents d ON d.job_id=j.id
                LEFT JOIN document_analyses a ON a.document_id=d.document_id
                GROUP BY j.id, j.status, j.total_documents, j.processed_documents,
                         j.configured_batch_size, j.error_message,
                         j.started_at, j.completed_at, j.updated_at
                """
            )
            cluster_audit_row = cursor.fetchone()

            cursor.execute(
                """
                SELECT c.evidence_key, c.asset_key, l.symbol, l.name,
                       l.delisting_date, s.sec_cik, i.identity_status,
                       o.status AS outcome_status, p.series_id,
                       c.form, c.filed_on, c.source_url, c.evidence_type,
                       c.candidate_value, c.value_unit, c.evidence_excerpt,
                       c.confidence, c.review_status, c.review_note, c.reviewed_at
                FROM market_delisting_evidence_candidates c
                JOIN market_asset_lifecycles l ON l.asset_key = c.asset_key
                JOIN market_delisting_evidence_states s ON s.asset_key = c.asset_key
                LEFT JOIN market_asset_identifiers i ON i.asset_key = c.asset_key
                LEFT JOIN market_delisting_outcomes o ON o.asset_key = c.asset_key
                LEFT JOIN market_price_backfill_states p ON p.asset_key = c.asset_key
                WHERE c.evidence_basis = 'filing_body_extract'
                ORDER BY l.symbol, c.filed_on DESC, c.confidence DESC
                """
            )
            sec_evidence_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                  (SELECT count(*) FROM market_delisting_evidence_states) AS assets_searched,
                  (SELECT coalesce(sum(filing_count), 0) FROM market_delisting_evidence_states) AS candidate_filings,
                  (SELECT count(*) FROM market_delisting_evidence_candidates WHERE evidence_basis='filing_body_extract') AS value_candidates,
                  (SELECT count(*) FROM market_delisting_evidence_candidates WHERE evidence_basis='filing_body_extract' AND review_status='candidate') AS pending_review,
                  (SELECT count(*) FROM market_delisting_evidence_states WHERE status='lifecycle_conflict_ticker_reuse') AS lifecycle_conflicts
                """
            )
            sec_evidence_totals = cursor.fetchone()

            cursor.execute(
                """
                SELECT id, question, local_model, result, evidence_snapshot,
                       created_at, updated_at
                FROM research_inquiries
                WHERE status = 'completed'
                  AND result IS NOT NULL
                  AND evidence_snapshot->'local_report_audit'->>'audit_version'
                      IN (
                        'local_report_audit_v2', 'local_report_audit_v3',
                        'local_report_audit_v4', 'local_report_audit_v5',
                        'local_report_audit_v6', 'local_report_audit_v7',
                        'local_report_audit_v8', 'local_report_audit_v9',
                        'local_report_audit_v10',
                        'local_report_audit_v11_product_chain_gate',
                        'local_report_audit_v12_a_share_confidence_gate'
                      )
                ORDER BY updated_at DESC, id DESC
                LIMIT %s
                """,
                (REMOTE_REPORT_LIMIT,),
            )
            research_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT series_id, observed_on, value
                FROM market_observations
                WHERE series_id LIKE 'EQ:%%' OR series_id LIKE 'CN:%%'
                ORDER BY series_id, observed_on
                """
            )
            equity_observation_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT series_id, observed_on, close_price, volume
                FROM market_daily_bars
                WHERE series_id LIKE 'EQ:%%' OR series_id LIKE 'CN:%%'
                ORDER BY series_id, observed_on
                """
            )
            equity_bar_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT split_part(s.series_id, ':', 2) AS ticker,
                       regexp_replace(
                         s.name,
                         ' \\([0-9]{6}\\) 前复权收盘价$',
                         ''
                       ) AS company_name,
                       s.sector,
                       replace(coalesce(s.neutralization_group, ''), 'csrc:', '') AS industry,
                       count(o.observed_on) AS observation_count,
                       min(o.observed_on) AS starts_at,
                       max(o.observed_on) AS ends_at,
                       latest_score.value AS leader_score,
                       latest_score.observed_on AS score_observed_on
                FROM market_series s
                LEFT JOIN market_observations o ON o.series_id = s.series_id
                LEFT JOIN LATERAL (
                  SELECT score.value, score.observed_on
                  FROM market_observations score
                  WHERE score.series_id = 'CNSCORE:' || split_part(s.series_id, ':', 2)
                  ORDER BY score.observed_on DESC
                  LIMIT 1
                ) latest_score ON true
                WHERE s.category = 'equity_price'
                  AND s.region = 'china'
                  AND s.listing_status = 'active'
                  AND s.series_id LIKE 'CN:%%'
                GROUP BY s.series_id, s.name, s.sector, s.neutralization_group,
                         latest_score.value, latest_score.observed_on
                ORDER BY s.sector, latest_score.value DESC NULLS LAST, s.series_id
                """
            )
            china_equity_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT p.ticker, p.name AS company_name, p.sector, p.industry,
                       count(b.observed_on) AS observation_count,
                       min(b.observed_on) AS starts_at,
                       max(b.observed_on) AS ends_at
                FROM company_profiles p
                LEFT JOIN market_daily_bars b
                  ON b.series_id = 'EQ:' || p.ticker
                GROUP BY p.ticker, p.name, p.sector, p.industry
                ORDER BY p.sector, p.ticker
                """
            )
            us_equity_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT b.id, b.name, b.status, b.parameters, b.target_count,
                       b.completed_count, b.failed_count, b.created_at,
                       b.started_at, b.completed_at,
                       count(*) FILTER (WHERE i.status='queued') AS queued_count,
                       count(*) FILTER (WHERE i.status='running') AS running_count,
                       max(i.ticker) FILTER (WHERE i.status='running') AS running_ticker,
                       max(i.progress_percent) FILTER (WHERE i.status='running') AS progress_percent,
                       max(i.progress_stage) FILTER (WHERE i.status='running') AS progress_stage,
                       max(i.progress_message) FILTER (WHERE i.status='running') AS progress_message
                FROM research_batches b
                JOIN research_batch_items i ON i.batch_id=b.id
                GROUP BY b.id
                ORDER BY b.id DESC
                LIMIT 30
                """
            )
            research_batch_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT ticker
                FROM (
                    SELECT subject_ticker AS ticker
                    FROM company_supply_chain_sites
                    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
                    UNION
                    SELECT related_ticker AS ticker
                    FROM company_supply_chain_sites
                    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
                      AND coordinate_precision = 'exact_facility'
                      AND verification_status = 'verified_exact'
                      AND related_ticker IS NOT NULL
                ) supply_chain_tickers
                ORDER BY ticker
                """
            )
            supply_chain_tickers = [
                str(row["ticker"]).upper() for row in cursor.fetchall()
            ]
            comparison_generated_at = datetime.now(UTC).isoformat()
            semiconductor_comparison = _semiconductor_comparison_snapshot(
                cursor,
                generated_at=comparison_generated_at,
            )
            durable_entry_calibration = _load_durable_entry_calibration(cursor)

    conflicts: list[dict[str, object]] = []
    for row in ucdp_rows:
        title = str(row["title"])
        parts = [part.strip() for part in title.split("·", 1)]
        conflicts.append(
            {
                "id": f"u{row['id']}",
                "title": parts[0],
                "location": parts[1] if len(parts) > 1 else parts[0],
                "summary": row["summary"] or "UCDP georeferenced conflict record.",
                "country": row["country_code"] or "--",
                "date": row["start_at"].date().isoformat(),
                "endDate": (row["end_at"] or row["start_at"]).date().isoformat(),
                "severity": round(float(row["severity"]) * 100),
                "confidence": round(float(row["confidence"]) * 100),
                "coordinates": [float(row["longitude"]), float(row["latitude"])],
                "source": "UCDP GED 26.1",
                "eventType": row["event_type"],
                "eventCount": 1,
            }
        )
    conflicts.sort(key=lambda item: (str(item["date"]), int(item["severity"])), reverse=True)

    articles = [
        {
            "id": f"n{row['id']}",
            "title": row["title"],
            "language": row["language"] or "und",
            "publishedAt": row["published_at"].isoformat() if row["published_at"] else None,
            "url": row["url"],
            "source": row["source_name"],
            "country": row["country"],
            "credibility": round(float(row["credibility_score"] or 0.5) * 100),
            "contentStatus": (
                "feed_content"
                if row["collector"] == "rss"
                and int(row["body_characters"] or 0) >= 100
                else "headline_only"
            ),
            "bodyCharactersLocal": int(row["body_characters"] or 0),
            "collector": row["collector"],
        }
        for row in article_rows
    ]

    sec_candidates: list[dict[str, object]] = []
    for row in sec_evidence_rows:
        identity_status = row["identity_status"] or "not_checked"
        outcome_status = row["outcome_status"] or "not_materialized"
        factor_block_reason = None
        if outcome_status == "verified":
            factor_block_reason = "terminal_outcome_already_verified"
        elif identity_status != "verified":
            factor_block_reason = "identity_not_verified"
        elif not row["series_id"]:
            factor_block_reason = "price_series_not_ready"
        sec_candidates.append(
            {
                "evidenceKey": row["evidence_key"],
                "assetKey": row["asset_key"],
                "symbol": row["symbol"],
                "name": row["name"],
                "delistingDate": row["delisting_date"].isoformat(),
                "secCik": row["sec_cik"],
                "identityStatus": identity_status,
                "outcomeStatus": outcome_status,
                "factorEligible": factor_block_reason is None,
                "factorBlockReason": factor_block_reason,
                "form": row["form"],
                "filedOn": row["filed_on"].isoformat(),
                "sourceUrl": row["source_url"],
                "evidenceType": row["evidence_type"],
                "candidateValue": (
                    float(row["candidate_value"])
                    if row["candidate_value"] is not None
                    else None
                ),
                "valueUnit": row["value_unit"],
                "excerpt": row["evidence_excerpt"],
                "confidence": round(float(row["confidence"]) * 100),
                "reviewStatus": row["review_status"],
                "reviewNote": row["review_note"],
                "reviewedAt": (
                    row["reviewed_at"].isoformat() if row["reviewed_at"] else None
                ),
            }
        )

    synced_at = comparison_generated_at
    supply_chain = _supply_chain_snapshot(
        supply_chain_tickers,
        as_of=datetime.now(UTC).date().isoformat(),
    )
    research_reports = [
        report
        for row in research_rows
        if (report := _remote_report(row, synced_at=synced_at)) is not None
    ]
    entry_backtest_status = _merge_durable_entry_calibration(
        _attach_entry_horizon_models(
            research_reports,
            observation_rows=equity_observation_rows,
            bar_rows=equity_bar_rows,
            generated_at=synced_at,
        ),
        durable_entry_calibration,
    )
    reports_by_company = {
        (str(report.get("marketRegion") or "global"), str(report.get("ticker") or "")): [
            item["id"]
            for item in research_reports
            if item.get("marketRegion") == report.get("marketRegion")
            and item.get("ticker") == report.get("ticker")
        ]
        for report in research_reports
        if report.get("ticker")
    }
    china_equity_catalog = [
        {
            "marketRegion": "china",
            "ticker": str(row["ticker"]),
            "companyName": str(row["company_name"]),
            "sector": row["sector"],
            "industry": row["industry"] or None,
            "dataStart": row["starts_at"].isoformat() if row["starts_at"] else None,
            "dataEnd": row["ends_at"].isoformat() if row["ends_at"] else None,
            "observationCount": int(row["observation_count"] or 0),
            "leaderScore": (
                round(float(row["leader_score"]), 4)
                if row["leader_score"] is not None
                else None
            ),
            "scoreObservedOn": (
                row["score_observed_on"].isoformat()
                if row["score_observed_on"]
                else None
            ),
            "reportIds": reports_by_company.get(
                ("china", str(row["ticker"])),
                [],
            ),
        }
        for row in china_equity_rows
    ]
    us_equity_catalog = [
        {
            "marketRegion": "us",
            "ticker": str(row["ticker"]),
            "companyName": str(row["company_name"]),
            "sector": row["sector"],
            "industry": row["industry"],
            "dataStart": row["starts_at"].isoformat() if row["starts_at"] else None,
            "dataEnd": row["ends_at"].isoformat() if row["ends_at"] else None,
            "observationCount": int(row["observation_count"] or 0),
            "leaderScore": None,
            "scoreObservedOn": None,
            "reportIds": reports_by_company.get(("us", str(row["ticker"])), []),
        }
        for row in us_equity_rows
    ]
    equity_catalog = [*china_equity_catalog, *us_equity_catalog]
    # Keep the portfolio-build denominator stable as individual chunks finish.
    # A large campaign is split into multiple named chunks; later enhancement
    # batches remain part of the same published build history. Start from the
    # newest multi-chunk portfolio campaign and include every subsequent batch.
    campaign_batch_rows: list[dict[str, object]] = []
    if research_batch_rows:
        campaign_groups: dict[str, list[dict[str, object]]] = {}
        for row in research_batch_rows:
            root = str(row["name"]).rsplit("·", 1)[0].strip()
            campaign_groups.setdefault(root, []).append(row)
        portfolio_groups = [
            rows
            for rows in campaign_groups.values()
            if len(rows) >= 2
            and sum(int(row["target_count"]) for row in rows) >= 100
        ]
        if portfolio_groups:
            newest_group = max(
                portfolio_groups,
                key=lambda rows: max(int(row["id"]) for row in rows),
            )
            first_batch_id = min(int(row["id"]) for row in newest_group)
            campaign_batch_rows = [
                row
                for row in research_batch_rows
                if int(row["id"]) >= first_batch_id
            ]
        else:
            active_campaigns = {
                str(row["name"]).rsplit("·", 1)[0].strip()
                for row in research_batch_rows
                if row["status"] in {"queued", "running"}
            }
            if not active_campaigns:
                active_campaigns = {
                    str(research_batch_rows[0]["name"]).rsplit("·", 1)[0].strip()
                }
            campaign_batch_rows = [
                row
                for row in research_batch_rows
                if str(row["name"]).rsplit("·", 1)[0].strip()
                in active_campaigns
            ]
    report_generation = {
        "targetCount": sum(int(row["target_count"]) for row in campaign_batch_rows),
        "completedCount": sum(int(row["completed_count"]) for row in campaign_batch_rows),
        "failedCount": sum(int(row["failed_count"]) for row in campaign_batch_rows),
        "queuedCount": sum(int(row["queued_count"] or 0) for row in campaign_batch_rows),
        "runningCount": sum(int(row["running_count"] or 0) for row in campaign_batch_rows),
        "triggeredTargets": sum(
            int((row["parameters"] or {}).get("triggered_targets") or 0)
            for row in campaign_batch_rows
            if isinstance(row["parameters"], dict)
        ),
        "dailyPolicy": {
            "rotationBudget": int(
                os.getenv("NEWSAPP_DAILY_EQUITY_AI_REPORT_BUDGET", "12")
            ),
            "eventBudget": int(
                os.getenv("NEWSAPP_DAILY_EQUITY_AI_EVENT_REPORT_BUDGET", "4")
            ),
            "gpuConcurrency": 1,
            "snapshotGpuUsed": False,
            "triggerPolicy": "new_official_evidence_or_material_price_move_v1",
        },
        "batches": [
            {
                "id": int(row["id"]),
                "name": row["name"],
                "status": row["status"],
                "targetCount": int(row["target_count"]),
                "completedCount": int(row["completed_count"]),
                "failedCount": int(row["failed_count"]),
                "queuedCount": int(row["queued_count"] or 0),
                "runningCount": int(row["running_count"] or 0),
                "runningTicker": row["running_ticker"],
                "progressPercent": float(row["progress_percent"] or 0),
                "progressStage": row["progress_stage"],
                "progressMessage": row["progress_message"],
                "createdAt": row["created_at"].isoformat(),
                "completedAt": row["completed_at"].isoformat() if row["completed_at"] else None,
                "rotationBudget": (
                    int(row["parameters"].get("rotation_budget") or 0)
                    if isinstance(row["parameters"], dict)
                    else 0
                ),
                "eventBudget": (
                    int(row["parameters"].get("event_budget") or 0)
                    if isinstance(row["parameters"], dict)
                    else 0
                ),
                "triggeredTargets": (
                    int(row["parameters"].get("triggered_targets") or 0)
                    if isinstance(row["parameters"], dict)
                    else 0
                ),
                "triggerReasons": (
                    _camelize(row["parameters"].get("trigger_reasons") or {})
                    if isinstance(row["parameters"], dict)
                    else {}
                ),
            }
            for row in campaign_batch_rows
        ],
    }
    cluster_audit = None
    if cluster_audit_row:
        cluster_total = int(cluster_audit_row["total_documents"] or 0)
        local_model_documents = int(
            cluster_audit_row["local_model_documents"] or 0
        )
        direct_model_documents = int(
            cluster_audit_row["direct_model_documents"] or 0
        )
        repaired_documents = int(cluster_audit_row["repaired_documents"] or 0)
        fallback_documents = int(cluster_audit_row["fallback_documents"] or 0)
        cluster_processed = max(
            int(cluster_audit_row["processed_documents"] or 0),
            local_model_documents + fallback_documents,
        )
        cluster_audit = {
            "jobId": int(cluster_audit_row["id"]),
            "status": cluster_audit_row["status"],
            "totalDocuments": cluster_total,
            "processedDocuments": cluster_processed,
            "progressPercent": (
                round(100 * cluster_processed / cluster_total, 1)
                if cluster_total
                else 0
            ),
            "localModelDocuments": local_model_documents,
            "directModelDocuments": direct_model_documents,
            "repairedDocuments": repaired_documents,
            "fallbackDocuments": fallback_documents,
            "pendingDocuments": int(cluster_audit_row["pending_documents"] or 0),
            "localModel": cluster_audit_row["local_model"],
            "waitReason": cluster_audit_row["error_message"],
            "fallbackRate": (
                round(
                    100
                    * fallback_documents
                    / max(local_model_documents + fallback_documents, 1),
                    1,
                )
            ),
            "batchSize": int(cluster_audit_row["configured_batch_size"] or 0),
            "startedAt": (
                cluster_audit_row["started_at"].isoformat()
                if cluster_audit_row["started_at"]
                else None
            ),
            "completedAt": (
                cluster_audit_row["completed_at"].isoformat()
                if cluster_audit_row["completed_at"]
                else None
            ),
            "updatedAt": cluster_audit_row["updated_at"].isoformat(),
            "scope": "latest_local_news_cluster_job",
        }
    manifest = {
        "generatedAt": synced_at,
        "snapshotMode": "published_static_snapshot",
        "aiPipeline": {
            "clusterExtraction": cluster_audit,
            "reportGeneration": {
                "completedReports": len(research_reports),
                "detailAssets": len(research_reports),
                "auditableOnSite": True,
                "source": "local_postgresql_export",
            },
        },
        "localTotals": {
            "geolocatedEvents": int(totals["local_events"]),
            "acledAggregateRows": int(totals["local_acled_rows"]),
            "acledRepresentedEvents": int(totals["local_acled_events"]),
            "rssDocuments": int(totals["rss_documents"]),
            "substantiveArticles": int(totals["substantive_articles"]),
            "headlineOnlyDiscovery": int(totals["headline_only_discovery"]),
        },
        "remoteSnapshot": {
            "conflictRecords": len(conflicts),
            "ucdpRecords": len(ucdp_rows),
            "newsIndexRecords": len(articles),
            "contentReadyArticles": sum(
                1 for item in articles if item["contentStatus"] == "feed_content"
            ),
            "secEvidenceCandidates": len(sec_candidates),
            "localResearchReports": len(research_reports),
            "activeChinaSectorLeaders": len(china_equity_catalog),
            "activeChinaSectors": len(
                {item["sector"] for item in china_equity_catalog if item["sector"]}
            ),
            "activeUsSectorLeaders": len(us_equity_catalog),
            "activeUsSectors": len(
                {item["sector"] for item in us_equity_catalog if item["sector"]}
            ),
            "localResearchAuditVersion": LOCAL_REPORT_AUDIT_VERSION,
            "supplyChainSites": len(supply_chain["sites"]),
            "supplyChainExactFacilities": sum(
                1
                for item in supply_chain["sites"]
                if item["coordinatePrecision"] == "exact_facility"
            ),
            "supplyChainTickers": len(supply_chain["summaries"]),
            "semiconductorComparisonCompanies": len(
                semiconductor_comparison["companies"]
            ),
            "entryBacktestModelVersion": entry_backtest_status["modelVersion"],
            "entryBacktestReports": entry_backtest_status[
                "historicalReportsEvaluated"
            ],
            "conflictStartsAt": min(str(item["date"]) for item in conflicts),
            "conflictEndsAt": max(str(item["date"]) for item in conflicts),
            "newsStartsAt": totals["news_min"].isoformat() if totals["news_min"] else None,
            "newsEndsAt": totals["news_max"].isoformat() if totals["news_max"] else None,
        },
        "sourceBoundaries": {
            "localConflictStartsAt": totals["event_min"].isoformat() if totals["event_min"] else None,
            "localConflictEndsAt": totals["event_max"].isoformat() if totals["event_max"] else None,
        },
        "evidencePolicy": {
            "headlineOnlyExcluded": int(totals["headline_only_discovery"]),
            "minimumBodyCharacters": 100,
            "note": "Headline-only discovery records remain search leads and are excluded from AI evidence until a licensed feed or original source supplies substantive text.",
        },
    }
    dump("conflicts.json", conflicts)
    dump(
        "news-research-index.json",
        {
            "headlineOnlyTotal": int(totals["headline_only_discovery"]),
            "leads": [
            {
                "title": item["title"],
                "publishedAt": item["publishedAt"],
                "url": item["url"],
                "source": item["source"],
                "language": item["language"],
                "contentStatus": item["contentStatus"],
            }
            for item in articles
            if item["contentStatus"] == "feed_content"
            ],
        },
    )
    dump("snapshot-manifest.json", manifest, pretty=True)
    dump("entry-backtest-status.json", entry_backtest_status, pretty=True)
    dump("supply-chain-sites.json", supply_chain)
    dump("semiconductor-comparison.json", semiconductor_comparison, pretty=True)
    dump(
        "equity-report-catalog.json",
        {
            "generatedAt": synced_at,
            "universe": "CSI 800 proxy leaders + reviewed U.S. cross-sector leaders",
            "methodology": (
                "Top ten active leaders per broad CSRC-derived sector, ranked by "
                "market capitalization, revenue, net profit, ROE, profit growth, "
                "liquidity and valuation. Historical rows are retained; only current "
                "leaders are marked active. The U.S. catalog is a reviewed cross-sector "
                "large-cap and supply-network universe backed by SEC issuer identities."
            ),
            "generation": report_generation,
            "companies": equity_catalog,
        },
        pretty=True,
    )
    dump(
        "research-reports.json",
        {
            "generatedAt": synced_at,
            "total": len(research_reports),
            "reports": research_reports,
        },
        pretty=True,
    )
    dump_research_report_assets(research_reports, generated_at=synced_at)
    dump(
        "sec-evidence.json",
        {
            "generatedAt": datetime.now(UTC).isoformat(),
            "source": "SEC EDGAR primary filings",
            "metrics": {
                "assetsSearched": int(sec_evidence_totals["assets_searched"]),
                "candidateFilings": int(sec_evidence_totals["candidate_filings"]),
                "valueCandidates": int(sec_evidence_totals["value_candidates"]),
                "pendingReview": int(sec_evidence_totals["pending_review"]),
                "lifecycleConflicts": int(sec_evidence_totals["lifecycle_conflicts"]),
            },
            "candidates": sec_candidates,
        },
        pretty=True,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
