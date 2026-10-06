"""Budgeted daily rotation for full local-AI company reports."""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    ChinaDisclosureSyncState,
    CompanyFiling,
    CompanyProfile,
    CompanySupplyChainEdge,
    MarketDailyBar,
    MarketSeries,
    ResearchBatch,
    ResearchBatchItem,
    ResearchInquiry,
)
from app.db.session import get_session_factory
from app.queue_locks import DAILY_EQUITY_QUEUE_LOCK_ID, acquire_queue_transaction_lock
from app.research_batches import create_equity_research_batch
from app.schemas.research import ResearchBatchCreateRequest

DAILY_BATCH_PREFIX = "每日AI轮换"
MEASURED_MEDIAN_MINUTES_PER_REPORT = 3.96


def schedule_daily_equity_reports(
    session: Session,
    *,
    budget: int,
    event_budget: int = 4,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Queue material changes first, then fill a bounded oldest-report rotation."""
    observed_at = (now or datetime.now(UTC)).astimezone(UTC)
    batch_name = f"{DAILY_BATCH_PREFIX} · {observed_at:%Y-%m-%d}"
    # Several services can be replaced during a Docker deployment. Serialize
    # the check-and-create section so an old and a new scheduler cannot both
    # materialize the same daily batch.
    acquire_queue_transaction_lock(session, DAILY_EQUITY_QUEUE_LOCK_ID)
    existing = session.scalar(select(ResearchBatch).where(ResearchBatch.name == batch_name))
    if existing is not None:
        return {
            "status": "already_scheduled",
            "batch_id": existing.id,
            "targets_queued": existing.target_count,
            "budget": budget,
            "event_budget": event_budget,
            "triggered_targets": int(existing.parameters.get("triggered_targets") or 0),
        }
    if budget <= 0 and event_budget <= 0:
        return {
            "status": "disabled",
            "targets_queued": 0,
            "budget": budget,
            "event_budget": event_budget,
        }

    active = {
        (item.market_region, item.ticker)
        for item in session.scalars(
            select(ResearchBatchItem).where(ResearchBatchItem.status.in_(("queued", "running")))
        )
    }
    latest: dict[tuple[str, str], datetime] = {}
    for report in session.scalars(
        select(ResearchInquiry).where(ResearchInquiry.status == "completed")
    ):
        context = report.evidence_snapshot.get("equity_research_context")
        if not isinstance(context, dict):
            continue
        region = str(context.get("market_region") or "")
        ticker = str(context.get("ticker") or "").upper()
        if region not in {"us", "china"} or not ticker:
            continue
        key = (region, ticker)
        timestamp = report.created_at
        if timestamp is not None and (key not in latest or timestamp > latest[key]):
            latest[key] = timestamp

    universe: list[tuple[Literal["us", "china"], str]] = [
        ("us", ticker)
        for ticker in session.scalars(select(CompanyProfile.ticker).order_by(CompanyProfile.ticker))
    ]
    universe.extend(
        (
            "china",
            series_id.split(":", 1)[1],
        )
        for series_id in session.scalars(
            select(MarketSeries.series_id)
            .where(
                MarketSeries.category == "equity_price",
                MarketSeries.region == "china",
                MarketSeries.listing_status == "active",
                MarketSeries.series_id.like("CN:%"),
            )
            .order_by(MarketSeries.series_id)
        )
    )
    eligible = [item for item in universe if item not in active]
    trigger_reasons = _material_change_triggers(
        session,
        universe=eligible,
        latest_reports=latest,
        observed_at=observed_at,
    )
    triggered = sorted(
        trigger_reasons,
        key=lambda item: (
            -max(float(reason.get("severity") or 0) for reason in trigger_reasons[item]),
            item[0],
            item[1],
        ),
    )[: max(0, event_budget)]
    triggered_set = set(triggered)
    eligible.sort(
        key=lambda item: (
            item in latest,
            latest.get(item, datetime.min.replace(tzinfo=UTC)),
            item[0],
            item[1],
        )
    )
    rotation = [item for item in eligible if item not in triggered_set][:budget]
    selected = [*triggered, *rotation]
    if not selected:
        return {"status": "nothing_to_queue", "targets_queued": 0, "budget": budget}
    regions = cast(list[Literal["us", "china"]], sorted({item[0] for item in selected}))
    tickers = [item[1] for item in selected]
    batch = create_equity_research_batch(
        session,
        request=ResearchBatchCreateRequest(
            name=batch_name,
            regions=regions,
            limit_per_region=len(selected),
            tickers=tickers,
        ),
    )
    persisted_batch = session.get(ResearchBatch, batch.id)
    if persisted_batch is not None:
        persisted_batch.parameters = {
            **persisted_batch.parameters,
            "rotation_budget": budget,
            "event_budget": event_budget,
            "triggered_targets": len(triggered),
            "trigger_policy": "new_official_evidence_or_material_price_move_v1",
            "trigger_reasons": {
                f"{region}:{ticker}": trigger_reasons[(region, ticker)]
                for region, ticker in triggered
            },
        }
        items = list(
            session.scalars(
                select(ResearchBatchItem).where(ResearchBatchItem.batch_id == batch.id)
            )
        )
        for item in items:
            key = (item.market_region, item.ticker)
            if key in trigger_reasons and key in triggered_set:
                item.data_readiness = {
                    **item.data_readiness,
                    "daily_trigger": {
                        "triggered": True,
                        "reasons": trigger_reasons[key],
                    },
                }
        session.commit()
    return {
        "status": "queued",
        "batch_id": batch.id,
        "targets_queued": batch.target_count,
        "budget": budget,
        "event_budget": event_budget,
        "triggered_targets": len(triggered),
        "rotation_targets": len(rotation),
        "estimated_gpu_minutes": round(batch.target_count * MEASURED_MEDIAN_MINUTES_PER_REPORT, 1),
        "policy": "material_change_first_then_missing_oldest_single_gpu_rotation",
        "selected": [f"{region}:{ticker}" for region, ticker in selected],
        "trigger_reasons": {
            f"{region}:{ticker}": trigger_reasons[(region, ticker)]
            for region, ticker in triggered
        },
    }


def _material_change_triggers(
    session: Session,
    *,
    universe: list[tuple[Literal["us", "china"], str]],
    latest_reports: dict[tuple[str, str], datetime],
    observed_at: datetime,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Return auditable triggers using only retained point-in-time data."""
    reasons: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    keys = set(universe)
    us_tickers = [ticker for region, ticker in universe if region == "us"]
    china_tickers = [ticker for region, ticker in universe if region == "china"]

    filing_dates = {
        ticker: filed_at
        for ticker, filed_at in session.execute(
            select(CompanyFiling.ticker, func.max(CompanyFiling.filed_at))
            .where(CompanyFiling.ticker.in_(us_tickers or ["__none__"]))
            .group_by(CompanyFiling.ticker)
        )
    }
    supply_updates = {
        ticker: updated_at
        for ticker, updated_at in session.execute(
            select(
                CompanySupplyChainEdge.subject_ticker,
                func.max(CompanySupplyChainEdge.updated_at),
            )
            .where(CompanySupplyChainEdge.subject_ticker.in_(us_tickers or ["__none__"]))
            .group_by(CompanySupplyChainEdge.subject_ticker)
        )
    }
    china_updates = {
        row.ticker: row.updated_at
        for row in session.scalars(
            select(ChinaDisclosureSyncState).where(
                ChinaDisclosureSyncState.ticker.in_(china_tickers or ["__none__"])
            )
        )
    }
    for key, last_report in latest_reports.items():
        if key not in keys:
            continue
        region, ticker = key
        report_date = last_report.date()
        if region == "us":
            filed_at = filing_dates.get(ticker)
            if filed_at is not None and filed_at > report_date:
                reasons[key].append(
                    {
                        "kind": "new_official_filing",
                        "label": "出现晚于上次报告的 SEC 法定披露",
                        "as_of": filed_at.isoformat(),
                        "severity": 1.0,
                    }
                )
            supply_at = supply_updates.get(ticker)
            if supply_at is not None and _as_utc(supply_at) > _as_utc(last_report):
                reasons[key].append(
                    {
                        "kind": "new_supply_chain_evidence",
                        "label": "供应链证据在上次报告后更新",
                        "as_of": _as_utc(supply_at).isoformat(),
                        "severity": 0.75,
                    }
                )
        else:
            disclosure_at = china_updates.get(ticker)
            if disclosure_at is not None and _as_utc(disclosure_at) > _as_utc(last_report):
                reasons[key].append(
                    {
                        "kind": "new_exchange_disclosure",
                        "label": "交易所公告证据在上次报告后更新",
                        "as_of": _as_utc(disclosure_at).isoformat(),
                        "severity": 1.0,
                    }
                )

    series_to_key = {
        f"{'CN' if region == 'china' else 'EQ'}:{ticker}": (region, ticker)
        for region, ticker in universe
        if (region, ticker) in latest_reports
    }
    price_rows = session.execute(
        select(
            MarketDailyBar.series_id,
            MarketDailyBar.observed_on,
            MarketDailyBar.close_price,
        )
        .where(
            MarketDailyBar.series_id.in_(list(series_to_key) or ["__none__"]),
            MarketDailyBar.observed_on <= observed_at.date(),
            MarketDailyBar.observed_on >= observed_at.date() - timedelta(days=45),
        )
        .order_by(MarketDailyBar.series_id, MarketDailyBar.observed_on)
    )
    prices: dict[str, list[tuple[Any, float]]] = defaultdict(list)
    for series_id, observed_on, close_price in price_rows:
        prices[series_id].append((observed_on, float(close_price)))
    for series_id, rows in prices.items():
        if len(rows) < 2 or (observed_at.date() - rows[-1][0]).days > 10:
            continue
        key = series_to_key[series_id]
        one_day = rows[-1][1] / rows[-2][1] - 1 if rows[-2][1] else 0.0
        if abs(one_day) >= 0.05:
            reasons[key].append(
                {
                    "kind": "one_day_price_anomaly",
                    "label": "最新单日涨跌超过 5%",
                    "value": round(one_day, 6),
                    "as_of": rows[-1][0].isoformat(),
                    "severity": min(1.0, abs(one_day) / 0.1),
                }
            )
        if len(rows) >= 21 and rows[-21][1]:
            twenty_session = rows[-1][1] / rows[-21][1] - 1
            if abs(twenty_session) >= 0.12:
                reasons[key].append(
                    {
                        "kind": "twenty_session_price_anomaly",
                        "label": "近 20 个交易日涨跌超过 12%",
                        "value": round(twenty_session, 6),
                        "as_of": rows[-1][0].isoformat(),
                        "severity": min(1.0, abs(twenty_session) / 0.24),
                    }
                )
    return dict(reasons)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-daily-equity-reports")
    parser.add_argument("--budget", type=int)
    parser.add_argument("--event-budget", type=int)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=86_400)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = get_settings()
    budget = settings.daily_equity_ai_report_budget if args.budget is None else args.budget
    event_budget = (
        settings.daily_equity_ai_event_report_budget
        if args.event_budget is None
        else args.event_budget
    )
    while True:
        with get_session_factory()() as session:
            result = schedule_daily_equity_reports(
                session,
                budget=budget,
                event_budget=event_budget,
            )
        print("daily_equity_reports=" + json.dumps(result, ensure_ascii=False), flush=True)
        if not args.loop:
            return
        time.sleep(max(3_600, args.interval_seconds))


if __name__ == "__main__":
    main()
