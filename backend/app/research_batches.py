"""Durable single-model queue for bounded US and China equity research."""

# ruff: noqa: RUF001

from __future__ import annotations

import argparse
import logging
import os
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from threading import Event, Thread
from typing import Any, Literal, cast

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.core.config import Settings, get_settings
from app.db.models import (
    ChinaDisclosureSyncState,
    CompanyFiling,
    CompanyFinancialFact,
    CompanyInsiderFilingState,
    CompanyInsiderTransaction,
    CompanyInstitutionalHolding,
    CompanyProfile,
    CompanySupplyChainEdge,
    MarketDailyBar,
    MarketObservation,
    MarketSeries,
    ResearchBatch,
    ResearchBatchItem,
    ResearchInquiry,
    TaskControlRecord,
)
from app.db.session import get_session_factory
from app.model_workload import local_model_workload_lock
from app.product_evidence import (
    build_product_operating_evidence,
    summarize_product_operating_evidence,
)
from app.queue_locks import RESEARCH_BATCH_QUEUE_LOCK_ID, acquire_queue_transaction_lock
from app.research import ResearchProviderError, run_research
from app.schemas.research import (
    ResearchBatchCreateRequest,
    ResearchBatchItemView,
    ResearchBatchView,
)
from app.task_controls import (
    RESEARCH_LONG_RUNNING_STAGES,
    TaskCancellationRequested,
    finish_cancelled_research_item,
    raise_if_cancellation_requested,
)

TEMPLATE_VERSION = "equity-batch-v4-csi800-report-ready"
PREFERRED_US_TICKERS = (
    "NVDA",
    "AAPL",
    "MSFT",
    "AMD",
    "AVGO",
    "AMAT",
    "AMZN",
    "TSLA",
    "XOM",
)

logger = logging.getLogger(__name__)


class ResearchBatchNotFoundError(LookupError):
    """Raised when a durable research batch does not exist."""


@dataclass(frozen=True)
class EquityBatchTarget:
    market_region: str
    research_scope: str
    ticker: str
    company_name: str
    sector: str | None
    question: str
    data_readiness: dict[str, Any]


class _ResearchBatchWatchdog:
    """Restart the report worker when one durable item stops making progress."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        item_id: int,
        stall_timeout_seconds: float,
        model_stall_timeout_seconds: float,
        cancellation_grace_seconds: float,
        max_attempts: int,
    ) -> None:
        self._session_factory = session_factory
        self._item_id = item_id
        self._stall_timeout_seconds = stall_timeout_seconds
        self._model_stall_timeout_seconds = model_stall_timeout_seconds
        self._cancellation_grace_seconds = cancellation_grace_seconds
        self._max_attempts = max_attempts
        self._stop = Event()
        self._thread = Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1)

    def _run(self) -> None:
        while not self._stop.wait(5):
            with self._session_factory() as session:
                item = session.get(ResearchBatchItem, self._item_id)
                if item is None or item.status != "running":
                    return
                now = datetime.now(UTC)
                control = session.scalar(
                    select(TaskControlRecord).where(
                        TaskControlRecord.task_kind == "research_batch_item",
                        TaskControlRecord.task_id == self._item_id,
                        TaskControlRecord.action == "cancel",
                        TaskControlRecord.status == "requested",
                    )
                )
                if control is not None and _age_seconds(control.requested_at, now) > (
                    self._cancellation_grace_seconds
                ):
                    item.progress_stage = "cancellation_watchdog"
                    item.progress_message = "安全停止等待超时，正在重启报告工作器完成取消"
                    item.heartbeat_at = now
                    session.commit()
                    logger.error(
                        "research_cancellation_watchdog_restart",
                        extra={"research_batch_item_id": self._item_id},
                    )
                    os._exit(74)
                heartbeat = item.heartbeat_at or item.started_at or item.updated_at
                stall_timeout = (
                    self._model_stall_timeout_seconds
                    if item.progress_stage in RESEARCH_LONG_RUNNING_STAGES
                    else self._stall_timeout_seconds
                )
                if _age_seconds(heartbeat, now) <= stall_timeout:
                    continue
                if item.attempt_count >= self._max_attempts:
                    item.status = "failed"
                    item.completed_at = now
                    item.progress_stage = "watchdog_failed"
                    item.progress_message = "连续无进展次数已达上限，任务已停止等待检查"
                    item.error_message = "research_watchdog_stall_retry_limit_reached"
                else:
                    item.status = "queued"
                    item.started_at = None
                    item.progress_percent = 0
                    item.progress_stage = "watchdog_requeued"
                    item.progress_message = "长时间没有进展，已自动重排并将从证据整理重新开始"
                    item.error_message = "research_watchdog_stall_requeued"
                item.heartbeat_at = now
                ResearchBatchWorker._update_batch_status(
                    session,
                    item.batch_id,
                    now=now,
                )
                session.commit()
                logger.error(
                    "research_stall_watchdog_restart",
                    extra={"research_batch_item_id": self._item_id},
                )
                os._exit(75)


def create_equity_research_batch(
    session: Session,
    *,
    request: ResearchBatchCreateRequest,
) -> ResearchBatchView:
    """Materialize an idempotent active batch from the retained equity catalog."""
    acquire_queue_transaction_lock(session, RESEARCH_BATCH_QUEUE_LOCK_ID)
    parameters = request.model_dump(mode="json")
    active = list(
        session.scalars(
            select(ResearchBatch)
            .where(ResearchBatch.status.in_(("queued", "running")))
            .options(selectinload(ResearchBatch.items))
            .order_by(desc(ResearchBatch.created_at))
        )
    )
    for batch in active:
        if batch.parameters == parameters and batch.template_version == TEMPLATE_VERSION:
            return research_batch_view(batch)

    explicit = set(request.tickers or [])
    targets: list[EquityBatchTarget] = []
    if "us" in request.regions:
        targets.extend(
            _select_us_targets(
                session,
                limit=request.limit_per_region,
                explicit=explicit,
            )
        )
    if "china" in request.regions:
        targets.extend(
            _select_china_targets(
                session,
                limit=request.limit_per_region,
                explicit=explicit,
            )
        )
    if not targets:
        raise ValueError("no retained equity targets matched the requested batch")
    batch = ResearchBatch(
        name=request.name or f"美股/A股本地证据批次 {datetime.now(UTC):%Y-%m-%d %H:%M}",
        status="queued",
        template_version=TEMPLATE_VERSION,
        parameters=parameters,
        target_count=len(targets),
        completed_count=0,
        failed_count=0,
    )
    session.add(batch)
    session.flush()
    for priority, target in enumerate(targets, start=1):
        session.add(
            ResearchBatchItem(
                batch_id=batch.id,
                market_region=target.market_region,
                research_scope=target.research_scope,
                ticker=target.ticker,
                company_name=target.company_name,
                sector=target.sector,
                question=target.question,
                priority=priority,
                status="queued",
                data_readiness=target.data_readiness,
                progress_percent=0,
                progress_stage="queued",
                progress_message="等待本地 AI 运行时",
            )
        )
    session.commit()
    return get_research_batch(session, batch.id)


def get_research_batch(session: Session, batch_id: int) -> ResearchBatchView:
    batch = session.scalar(
        select(ResearchBatch)
        .where(ResearchBatch.id == batch_id)
        .options(selectinload(ResearchBatch.items))
    )
    if batch is None:
        raise ResearchBatchNotFoundError(batch_id)
    return research_batch_view(batch)


def list_research_batches(
    session: Session,
    *,
    limit: int,
) -> list[ResearchBatchView]:
    batches = list(
        session.scalars(
            select(ResearchBatch)
            .options(selectinload(ResearchBatch.items))
            .order_by(desc(ResearchBatch.created_at), desc(ResearchBatch.id))
            .limit(limit)
        )
    )
    return [research_batch_view(batch) for batch in batches]


def retry_failed_batch_items(session: Session, *, batch_id: int) -> ResearchBatchView:
    batch = session.scalar(
        select(ResearchBatch)
        .where(ResearchBatch.id == batch_id)
        .options(selectinload(ResearchBatch.items))
    )
    if batch is None:
        raise ResearchBatchNotFoundError(batch_id)
    failed = [item for item in batch.items if item.status == "failed"]
    if not failed:
        return research_batch_view(batch)
    for item in failed:
        item.status = "queued"
        item.attempt_count = 0
        item.error_message = None
        item.started_at = None
        item.completed_at = None
        item.progress_percent = 0
        item.progress_stage = "queued"
        item.progress_message = "等待重试"
        item.heartbeat_at = None
    batch.status = (
        "running"
        if batch.completed_count
        or any(item.status == "running" for item in batch.items)
        else "queued"
    )
    batch.failed_count = 0
    batch.completed_at = None
    session.commit()
    return get_research_batch(session, batch_id)


def research_batch_view(batch: ResearchBatch) -> ResearchBatchView:
    item_progress = [
        100.0 if item.status == "completed" else float(item.progress_percent)
        for item in batch.items
    ]
    return ResearchBatchView(
        id=batch.id,
        name=batch.name,
        status=cast(
            Literal["queued", "running", "completed", "partial_failed", "failed"],
            batch.status,
        ),
        template_version=batch.template_version,
        parameters=batch.parameters,
        target_count=batch.target_count,
        completed_count=batch.completed_count,
        failed_count=batch.failed_count,
        progress_percent=round(sum(item_progress) / batch.target_count, 2),
        items=[ResearchBatchItemView.model_validate(item) for item in batch.items],
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        started_at=batch.started_at,
        completed_at=batch.completed_at,
    )


class ResearchBatchWorker:
    """Claim one target at a time and serialize access to the local model."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        settings: Settings | None = None,
        stall_timeout_seconds: float | None = None,
        model_stall_timeout_seconds: float | None = None,
        cancellation_grace_seconds: float = 300,
        max_attempts: int = 3,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings or get_settings()
        self._stall_timeout_seconds = stall_timeout_seconds
        self._model_stall_timeout_seconds = (
            model_stall_timeout_seconds
            if model_stall_timeout_seconds is not None
            else stall_timeout_seconds
        )
        self._cancellation_grace_seconds = cancellation_grace_seconds
        self._max_attempts = max_attempts

    def recover_interrupted_items(self) -> int:
        cancelled_item_ids: list[int] = []
        with self._session_factory() as session:
            items = list(
                session.scalars(
                    select(ResearchBatchItem).where(ResearchBatchItem.status == "running")
                )
            )
            batch_ids = {item.batch_id for item in items}
            for item in items:
                try:
                    raise_if_cancellation_requested(
                        session,
                        task_kind="research_batch_item",
                        task_id=item.id,
                    )
                except TaskCancellationRequested:
                    cancelled_item_ids.append(item.id)
                    continue
                if item.attempt_count >= self._max_attempts:
                    item.status = "failed"
                    item.progress_stage = "watchdog_failed"
                    item.progress_message = "工作器异常中断次数已达上限，需要人工检查"
                    item.error_message = "research_watchdog_retry_limit_reached"
                    item.completed_at = datetime.now(UTC)
                    continue
                item.status = "queued"
                item.started_at = None
                item.error_message = "Recovered after an interrupted research worker"
                item.progress_percent = 0
                item.progress_stage = "recovered_after_restart"
                item.progress_message = "服务重启后已恢复排队，将从证据整理重新开始"
                item.heartbeat_at = datetime.now(UTC)
            batch_ids.update(
                session.scalars(
                    select(ResearchBatch.id).where(ResearchBatch.status.in_(("queued", "running")))
                )
            )
            session.flush()
            now = datetime.now(UTC)
            for batch_id in batch_ids:
                self._update_batch_status(session, batch_id, now=now)
            session.commit()
        for item_id in cancelled_item_ids:
            with self._session_factory() as session:
                finish_cancelled_research_item(session, item_id=item_id)
        return len(items)

    def run_next(self) -> bool:
        item_id = self._claim_next_item()
        if item_id is None:
            return False
        watchdog = self._start_watchdog(item_id)
        try:
            return self._process_item(item_id)
        except Exception as exc:
            self._fail_item(item_id, exc)
            return True
        finally:
            if watchdog is not None:
                watchdog.stop()

    def run_forever(self, *, poll_seconds: float = 5) -> None:
        if poll_seconds < 0.5:
            raise ValueError("poll_seconds must be at least 0.5")
        self.recover_interrupted_items()
        try:
            while True:
                if not self.run_next():
                    time.sleep(poll_seconds)
        except KeyboardInterrupt:
            return

    def _claim_next_item(self) -> int | None:
        with self._session_factory() as session:
            item = session.scalar(
                select(ResearchBatchItem)
                .join(ResearchBatch, ResearchBatch.id == ResearchBatchItem.batch_id)
                .where(ResearchBatchItem.status == "queued")
                .order_by(
                    ResearchBatch.created_at,
                    ResearchBatch.id,
                    ResearchBatchItem.priority,
                    ResearchBatchItem.created_at,
                )
                .with_for_update(skip_locked=True, of=ResearchBatchItem)
            )
            if item is None:
                return None
            now = datetime.now(UTC)
            item.status = "running"
            item.attempt_count += 1
            item.started_at = now
            item.error_message = None
            item.progress_percent = max(item.progress_percent, 2)
            item.progress_stage = "acquiring_model"
            item.progress_message = "正在申请本地 AI 运行时"
            item.heartbeat_at = now
            batch = session.get(ResearchBatch, item.batch_id)
            if batch is not None:
                batch.status = "running"
                batch.started_at = batch.started_at or now
            session.commit()
            return item.id

    def _process_item(self, item_id: int) -> bool:
        with self._session_factory() as session:
            item = session.get(ResearchBatchItem, item_id)
            if item is None:
                return True
            with local_model_workload_lock(session) as acquired:
                if not acquired:
                    item.status = "queued"
                    item.attempt_count = max(0, item.attempt_count - 1)
                    item.started_at = None
                    item.error_message = "Waiting for the shared local-model runtime"
                    item.progress_percent = min(item.progress_percent, 2)
                    item.progress_stage = "queued"
                    item.progress_message = "其他本地 AI 任务正在运行，等待资源"
                    item.heartbeat_at = datetime.now(UTC)
                    session.commit()
                    return False
                try:
                    raise_if_cancellation_requested(
                        session,
                        task_kind="research_batch_item",
                        task_id=item_id,
                    )
                    result = run_research(
                        session,
                        question=item.question,
                        mode="user_question",
                        settings=self._settings,
                        resume_checkpoint=(
                            item.checkpoint_data.get("resume")
                            if isinstance(item.checkpoint_data, dict)
                            else None
                        ),
                        progress_callback=lambda stage, percent, message: self._report_progress(
                            item_id,
                            stage=stage,
                            percent=percent,
                            message=message,
                        ),
                        checkpoint_callback=(
                            lambda stage, percent, message, payload: self._report_checkpoint(
                                item_id,
                                stage=stage,
                                percent=percent,
                                message=message,
                                payload=payload,
                            )
                        ),
                    )
                    now = datetime.now(UTC)
                    item.inquiry_id = result.id
                    item.status = "completed"
                    item.progress_percent = 100
                    item.progress_stage = "completed"
                    item.progress_message = "报告和本地审计已完成"
                    item.heartbeat_at = now
                    item.completed_at = now
                    item.audit_summary = _batch_audit_summary(result.evidence_snapshot)
                    self._update_batch_status(session, item.batch_id, now=now)
                    session.commit()
                    return True
                except TaskCancellationRequested:
                    session.rollback()
                    finish_cancelled_research_item(session, item_id=item_id)
                    return True
                except ResearchProviderError as exc:
                    now = datetime.now(UTC)
                    item.status = "failed"
                    item.error_message = str(exc)[:2_000]
                    item.completed_at = now
                    item.progress_stage = "failed"
                    item.progress_message = "报告生成失败，可查看错误并重试"
                    item.heartbeat_at = now
                    self._update_batch_status(session, item.batch_id, now=now)
                    session.commit()
                    return True

    def _fail_item(self, item_id: int, exc: Exception) -> None:
        with self._session_factory() as session:
            item = session.get(ResearchBatchItem, item_id)
            if item is None:
                return
            now = datetime.now(UTC)
            item.status = "failed"
            item.error_message = f"{type(exc).__name__}: {str(exc)[:1_900]}"
            item.completed_at = now
            item.progress_stage = "failed"
            item.progress_message = "研究任务异常终止"
            item.heartbeat_at = now
            self._update_batch_status(session, item.batch_id, now=now)
            session.commit()

    def _report_progress(
        self,
        item_id: int,
        *,
        stage: str,
        percent: int,
        message: str,
    ) -> None:
        with self._session_factory() as progress_session:
            item = progress_session.get(ResearchBatchItem, item_id)
            if item is None or item.status != "running":
                return
            raise_if_cancellation_requested(
                progress_session,
                task_kind="research_batch_item",
                task_id=item_id,
            )
            item.progress_percent = float(max(item.progress_percent, percent))
            item.progress_stage = stage[:64]
            item.progress_message = message[:255]
            item.heartbeat_at = datetime.now(UTC)
            progress_session.commit()

    def _start_watchdog(self, item_id: int) -> _ResearchBatchWatchdog | None:
        if self._stall_timeout_seconds is None:
            return None
        watchdog = _ResearchBatchWatchdog(
            self._session_factory,
            item_id=item_id,
            stall_timeout_seconds=self._stall_timeout_seconds,
            model_stall_timeout_seconds=(
                self._model_stall_timeout_seconds or self._stall_timeout_seconds
            ),
            cancellation_grace_seconds=self._cancellation_grace_seconds,
            max_attempts=self._max_attempts,
        )
        watchdog.start()
        return watchdog

    def _report_checkpoint(
        self,
        item_id: int,
        *,
        stage: str,
        percent: int,
        message: str,
        payload: dict[str, Any],
    ) -> None:
        with self._session_factory() as checkpoint_session:
            item = checkpoint_session.get(ResearchBatchItem, item_id)
            if item is None or item.status != "running":
                return
            raise_if_cancellation_requested(
                checkpoint_session,
                task_kind="research_batch_item",
                task_id=item_id,
            )
            now = datetime.now(UTC)
            current = item.checkpoint_data if isinstance(item.checkpoint_data, dict) else {}
            raw_history = current.get("history")
            history = list(raw_history) if isinstance(raw_history, list) else []
            history.append(
                {
                    "stage": stage[:64],
                    "percent": float(max(0, min(100, percent))),
                    "saved_at": now.isoformat(),
                    "attempt_count": item.attempt_count,
                    "summary": _checkpoint_summary(message=message, payload=payload),
                }
            )
            item.checkpoint_data = {
                "schema_version": 1,
                "latest_stage": stage[:64],
                "history": history[-32:],
                "resume": payload,
            }
            item.checkpoint_at = now
            item.progress_percent = max(item.progress_percent, float(percent))
            item.progress_stage = stage[:64]
            item.progress_message = message[:255]
            item.heartbeat_at = now
            checkpoint_session.commit()

    @staticmethod
    def _update_batch_status(session: Session, batch_id: int, *, now: datetime) -> None:
        # The application session disables autoflush. Without this explicit flush,
        # the aggregate query sees the current item in its previous state and leaves
        # a fully completed batch stuck at 50%/running until another item changes.
        session.flush()
        batch = session.get(ResearchBatch, batch_id)
        if batch is None:
            return
        statuses = list(
            session.scalars(
                select(ResearchBatchItem.status).where(ResearchBatchItem.batch_id == batch_id)
            )
        )
        batch.completed_count = sum(status == "completed" for status in statuses)
        batch.failed_count = sum(status == "failed" for status in statuses)
        if any(status in {"queued", "running"} for status in statuses):
            batch.status = "running" if batch.started_at else "queued"
            return
        batch.completed_at = now
        if batch.failed_count == 0:
            batch.status = "completed"
        elif batch.completed_count:
            batch.status = "partial_failed"
        else:
            batch.status = "failed"


def _select_us_targets(
    session: Session,
    *,
    limit: int,
    explicit: set[str],
) -> list[EquityBatchTarget]:
    profiles = list(session.scalars(select(CompanyProfile).order_by(CompanyProfile.ticker)))
    if explicit:
        profiles = [item for item in profiles if item.ticker.upper() in explicit]
    fact_counts = {
        ticker: count
        for ticker, count in session.execute(
            select(CompanyFinancialFact.ticker, func.count(CompanyFinancialFact.id)).group_by(
                CompanyFinancialFact.ticker
            )
        )
    }
    filing_counts = {
        ticker: count
        for ticker, count in session.execute(
            select(CompanyFiling.ticker, func.count(CompanyFiling.accession_number)).group_by(
                CompanyFiling.ticker
            )
        )
    }
    holding_counts = {
        ticker: count
        for ticker, count in session.execute(
            select(
                CompanyInstitutionalHolding.ticker,
                func.count(CompanyInstitutionalHolding.id),
            ).group_by(CompanyInstitutionalHolding.ticker)
        )
    }
    insider_stats = {
        ticker: {
            "transactions": int(point_in_time_count or 0),
            "raw_transactions": int(raw_count or 0),
            "future_dated_transactions": int(future_count or 0),
            "starts_at": starts_at.isoformat() if starts_at else None,
            "ends_at": ends_at.isoformat() if ends_at else None,
        }
        for (
            ticker,
            raw_count,
            point_in_time_count,
            future_count,
            starts_at,
            ends_at,
        ) in session.execute(
            select(
                CompanyInsiderTransaction.ticker,
                func.count(CompanyInsiderTransaction.id),
                func.count(CompanyInsiderTransaction.id).filter(
                    CompanyInsiderTransaction.transaction_date <= func.current_date()
                ),
                func.count(CompanyInsiderTransaction.id).filter(
                    CompanyInsiderTransaction.transaction_date > func.current_date()
                ),
                func.min(CompanyInsiderTransaction.transaction_date).filter(
                    CompanyInsiderTransaction.transaction_date <= func.current_date()
                ),
                func.max(CompanyInsiderTransaction.transaction_date).filter(
                    CompanyInsiderTransaction.transaction_date <= func.current_date()
                ),
            ).group_by(CompanyInsiderTransaction.ticker)
        )
    }
    insider_filing_states: dict[str, dict[str, int]] = {}
    for ticker, status, count in session.execute(
        select(
            CompanyInsiderFilingState.ticker,
            CompanyInsiderFilingState.status,
            func.count(),
        ).group_by(
            CompanyInsiderFilingState.ticker,
            CompanyInsiderFilingState.status,
        )
    ):
        values = insider_filing_states.setdefault(
            ticker,
            {"completed": 0, "failed": 0},
        )
        if status in values:
            values[status] = int(count or 0)
    price_stats = {
        series_id.split(":", 1)[1]: {
            "observations": count,
            "starts_at": starts_at.isoformat() if starts_at else None,
            "ends_at": ends_at.isoformat() if ends_at else None,
        }
        for series_id, count, starts_at, ends_at in session.execute(
            select(
                MarketObservation.series_id,
                func.count(),
                func.min(MarketObservation.observed_on),
                func.max(MarketObservation.observed_on),
            )
            .where(MarketObservation.series_id.like("EQ:%"))
            .group_by(MarketObservation.series_id)
        )
    }
    daily_bar_stats = {
        series_id.split(":", 1)[1]: {
            "observations": int(count or 0),
            "starts_at": starts_at.isoformat() if starts_at else None,
            "ends_at": ends_at.isoformat() if ends_at else None,
            "volume_observations": int(volume_count or 0),
        }
        for series_id, count, starts_at, ends_at, volume_count in session.execute(
            select(
                MarketDailyBar.series_id,
                func.count(),
                func.min(MarketDailyBar.observed_on),
                func.max(MarketDailyBar.observed_on),
                func.count(MarketDailyBar.volume),
            )
            .where(MarketDailyBar.series_id.like("EQ:%"))
            .group_by(MarketDailyBar.series_id)
        )
    }
    verified_supply_counts = {
        ticker: int(count or 0)
        for ticker, count in session.execute(
            select(
                CompanySupplyChainEdge.subject_ticker,
                func.count(CompanySupplyChainEdge.id),
            )
            .where(CompanySupplyChainEdge.review_status == "verified")
            .group_by(CompanySupplyChainEdge.subject_ticker)
        )
    }
    prior_questions = " ".join(
        session.scalars(
            select(ResearchInquiry.question).where(ResearchInquiry.status == "completed")
        )
    ).casefold()
    preferred = {ticker: index for index, ticker in enumerate(PREFERRED_US_TICKERS)}
    profiles.sort(
        key=lambda item: (
            item.ticker.casefold() in prior_questions,
            preferred.get(item.ticker, len(preferred) + 1),
            -int(fact_counts.get(item.ticker, 0)),
            item.ticker,
        )
    )
    targets: list[EquityBatchTarget] = []
    for profile in profiles[:limit]:
        stats = price_stats.get(profile.ticker, {})
        bar_stats = daily_bar_stats.get(profile.ticker, {})
        complete_daily_bars = (
            int(bar_stats.get("observations") or 0) >= 252
            and int(bar_stats.get("volume_observations") or 0) >= 252
        )
        verified_supply_count = int(verified_supply_counts.get(profile.ticker, 0))
        product_evidence = build_product_operating_evidence(
            session,
            ticker=profile.ticker,
            as_of=(
                date.fromisoformat(str(stats["ends_at"])) if stats.get("ends_at") else date.today()
            ),
            cold_data_root=get_settings().cold_data_root,
        )
        product_coverage = summarize_product_operating_evidence(product_evidence)
        missing = [
            label
            for condition, label in (
                (not stats, "adjusted daily price history"),
                (not complete_daily_bars, "complete daily OHLCV and volume history"),
                (not fact_counts.get(profile.ticker), "SEC standardized financial facts"),
                (not filing_counts.get(profile.ticker), "SEC filing references"),
                (not holding_counts.get(profile.ticker), "structured SEC 13F holdings"),
                (
                    not insider_stats.get(profile.ticker, {}).get("transactions"),
                    "parsed SEC Form 4 insider transactions",
                ),
                (not product_evidence, "product ASP/volume and contract evidence"),
                (not verified_supply_count, "facility and supplier dependency graph"),
            )
            if condition
        ]
        preflight_checks = {
            "daily_ohlcv": complete_daily_bars,
            "financial_facts": bool(fact_counts.get(profile.ticker)),
            "filings": bool(filing_counts.get(profile.ticker)),
            "institutional_holdings": bool(holding_counts.get(profile.ticker)),
            "insider_transactions": bool(insider_stats.get(profile.ticker, {}).get("transactions")),
            "verified_supply_chain": bool(verified_supply_count),
            "product_operating_evidence": bool(product_evidence),
        }
        preflight_score = round(
            sum(preflight_checks.values()) / len(preflight_checks),
            4,
        )
        readiness = {
            "scope": "SEC numeric evidence plus explicit evidence-gap audit",
            "price": stats,
            "daily_ohlcv": bar_stats,
            "preflight_score": preflight_score,
            "preflight_status": (
                "ready_for_full_evidence_build"
                if all(preflight_checks.values())
                else "evidence_gap_report_only"
            ),
            "preflight_checks": preflight_checks,
            "financial_fact_count": int(fact_counts.get(profile.ticker, 0)),
            "filing_count": int(filing_counts.get(profile.ticker, 0)),
            "institutional_holding_count": int(holding_counts.get(profile.ticker, 0)),
            "insider_transactions": insider_stats.get(
                profile.ticker,
                {
                    "transactions": 0,
                    "raw_transactions": 0,
                    "future_dated_transactions": 0,
                    "starts_at": None,
                    "ends_at": None,
                },
            ),
            "insider_filing_states": insider_filing_states.get(
                profile.ticker,
                {"completed": 0, "failed": 0},
            ),
            "verified_supply_chain_edges": verified_supply_count,
            "product_operating_evidence": product_coverage,
            "missing_evidence": missing,
            "quality_warning": (
                "Batch readiness is measured from retained rows. The final report reruns a "
                "stricter point-in-time gate for OHLCV, company documents, ownership, macro "
                "alignment and source-reviewed supply-chain evidence."
            ),
        }
        targets.append(
            EquityBatchTarget(
                market_region="us",
                research_scope="sec_numeric_evidence",
                ticker=profile.ticker,
                company_name=profile.name,
                sector=profile.sector,
                question=_us_question(profile),
                data_readiness=readiness,
            )
        )
    return targets


def _select_china_targets(
    session: Session,
    *,
    limit: int,
    explicit: set[str],
) -> list[EquityBatchTarget]:
    price_series = list(
        session.scalars(
            select(MarketSeries)
            .where(
                MarketSeries.category == "equity_price",
                MarketSeries.region == "china",
                MarketSeries.listing_status == "active",
                MarketSeries.series_id.like("CN:%"),
            )
            .order_by(MarketSeries.series_id)
        )
    )
    if explicit:
        price_series = [
            item for item in price_series if item.series_id.split(":", 1)[1].upper() in explicit
        ]
    candidates: list[tuple[float, MarketSeries, dict[str, Any]]] = []
    for series in price_series:
        ticker = series.series_id.split(":", 1)[1]
        stats_row = session.execute(
            select(
                func.count(),
                func.min(MarketObservation.observed_on),
                func.max(MarketObservation.observed_on),
            ).where(MarketObservation.series_id == series.series_id)
        ).one()
        score_row = session.execute(
            select(MarketObservation.value, MarketObservation.observed_on)
            .where(MarketObservation.series_id == f"CNSCORE:{ticker}")
            .order_by(desc(MarketObservation.observed_on))
            .limit(1)
        ).first()
        score = float(score_row.value) if score_row is not None else 0.0
        candidates.append(
            (
                score,
                series,
                {
                    "observations": int(stats_row[0]),
                    "starts_at": stats_row[1].isoformat() if stats_row[1] else None,
                    "ends_at": stats_row[2].isoformat() if stats_row[2] else None,
                    "sector_score": score,
                    "score_observed_on": (
                        score_row.observed_on.isoformat() if score_row is not None else None
                    ),
                },
            )
        )
    candidates.sort(key=lambda item: (-item[0], item[1].series_id))
    selected: list[tuple[float, MarketSeries, dict[str, Any]]] = []
    used_sectors: set[str] = set()
    for candidate in candidates:
        sector = candidate[1].sector or "unknown"
        if sector in used_sectors and len(candidates) > limit:
            continue
        selected.append(candidate)
        used_sectors.add(sector)
        if len(selected) >= limit:
            break
    if len(selected) < limit:
        selected_ids = {item[1].series_id for item in selected}
        selected.extend(item for item in candidates if item[1].series_id not in selected_ids)
        selected = selected[:limit]
    targets: list[EquityBatchTarget] = []
    for _, series, price_stats in selected:
        ticker = series.series_id.split(":", 1)[1]
        company_name = series.name.split(f" ({ticker})", 1)[0].strip()
        neutralization_group = series.neutralization_group or ""
        disclosure_state = session.get(ChinaDisclosureSyncState, ticker)
        periodic_reports = disclosure_state.periodic_reports if disclosure_state else 0
        shareholder_documents = disclosure_state.shareholder_documents if disclosure_state else 0
        operating_documents = disclosure_state.operating_documents if disclosure_state else 0
        supply_documents = disclosure_state.supply_chain_documents if disclosure_state else 0
        missing_evidence = [
            "structured point-in-time quarterly statement line items",
            "northbound daily capital-flow provenance",
        ]
        if not periodic_reports:
            missing_evidence.append(
                "exchange announcement full text and original availability timestamp"
            )
        if not operating_documents:
            missing_evidence.append("product, contract, order and production records")
        if not shareholder_documents:
            missing_evidence.append("shareholder and institution disclosure provenance")
        if not supply_documents:
            missing_evidence.append("facility and supplier dependency graph")
        readiness = {
            "scope": "CSI 800 factors plus official CNINFO issuer evidence and gap audit",
            "universe": "CSI 300 + CSI 500 (CSI 800 proxy)",
            "broad_sector": series.sector,
            "csrc_industry": (
                neutralization_group.split(":", 1)[1]
                if neutralization_group.startswith("csrc:")
                else None
            ),
            "price": price_stats,
            "snapshot_series": [
                f"{prefix}:{ticker}"
                for prefix in (
                    "CNSCORE",
                    "CNMCAP",
                    "CNREV",
                    "CNNP",
                    "CNROE",
                    "CNYOYNI",
                    "CNPE",
                    "CNPB",
                )
            ],
            "official_disclosure_coverage": {
                "status": disclosure_state.status if disclosure_state else "pending",
                "period_start": (
                    disclosure_state.period_start.isoformat()
                    if disclosure_state and disclosure_state.period_start
                    else None
                ),
                "period_end": (
                    disclosure_state.period_end.isoformat()
                    if disclosure_state and disclosure_state.period_end
                    else None
                ),
                "periodic_reports": periodic_reports,
                "shareholder_documents": shareholder_documents,
                "operating_documents": operating_documents,
                "supply_chain_documents": supply_documents,
            },
            "missing_evidence": missing_evidence,
            "quality_warning": (
                "CNINFO PDFs/full text are admissible evidence; snapshot ratios are not "
                "treated as filing facts until structured extraction is complete, so the "
                "pack is not filing-audited in structured-data terms."
            ),
        }
        targets.append(
            EquityBatchTarget(
                market_region="china",
                research_scope="market_factor_evidence",
                ticker=ticker,
                company_name=company_name,
                sector=series.sector,
                question=_china_question(company_name, ticker),
                data_readiness=readiness,
            )
        )
    return targets


def _us_question(profile: CompanyProfile) -> str:
    return (
        f"截至本地数据最新截止日，{profile.name}（{profile.ticker}）未来6至12个月的"
        "盈利、估值和股价驱动是否获得证据支持？请从产品与竞争、合同/订单、季度与"
        "TTM财报、机构/内部人资金、估值和技术形态、宏观流动性、原料与工厂供应链、"
        "地缘/灾害风险、替代技术九个维度构建可审计报告。只引用本地证据；缺失时"
        "逐项标记，不给出确定买点、目标价或盈利承诺。"
    )


def _china_question(company_name: str, ticker: str) -> str:
    return (
        f"截至本地数据最新截止日，{company_name}（{ticker}）未来6至12个月的市场"
        "状态是否获得证据支持？使用BaoStock前复权行情、PE/PB、ROE、收入/利润快照、"
        "行业龙头分、技术形态、宏观敏感度，以及已归档的交易所公告/季度财报、合同"
        "产销、股东资金和供应链全文生成A股因子报告。逐项引用已经接入的原文；对"
        "尚未结构化或尚未覆盖的证据明确标记，"
        "不得把快照当点时财报，不给出确定买点、目标价或盈利承诺。"
    )


def _batch_audit_summary(evidence: dict[str, Any]) -> dict[str, Any]:
    audit = evidence.get("local_report_audit")
    audit = audit if isinstance(audit, dict) else {}
    context = evidence.get("equity_research_context")
    context = context if isinstance(context, dict) else {}
    return {
        "audit_version": audit.get("audit_version"),
        "recommendation": audit.get("recommendation"),
        "checks": audit.get("checks", {}),
        "material_findings": audit.get("material_findings", []),
        "point_in_time_cutoff": context.get("point_in_time_cutoff"),
        "market_region": context.get("market_region"),
        "research_scope": context.get("research_scope", "sec_numeric_evidence"),
        "required_missing_evidence": context.get("required_missing_evidence", []),
    }


def _checkpoint_summary(
    *,
    message: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    evidence = payload.get("evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    result = payload.get("result")
    result = result if isinstance(result, dict) else {}
    hypotheses = result.get("hypotheses")
    hypotheses = hypotheses if isinstance(hypotheses, list) else []
    factor_research = result.get("factor_research")
    factor_research = factor_research if isinstance(factor_research, dict) else {}
    audit = evidence.get("local_report_audit")
    audit = audit if isinstance(audit, dict) else {}
    counts = {
        key: len(value)
        for key in (
            "documents",
            "events",
            "market_observations",
            "economic_observations",
            "company_financials",
            "derived_equity_evidence",
        )
        if isinstance((value := evidence.get(key)), list)
    }
    factor_rows = factor_research.get("factors")
    nonlinear_rows = factor_research.get("nonlinear_links")
    validation_rows = factor_research.get("profit_validations")
    return {
        "message": message[:255],
        "evidence_counts": counts,
        "report_summary": str(result.get("summary") or "")[:1_200] or None,
        "hypothesis_count": len(hypotheses),
        "hypotheses": [
            {
                "title": str(item.get("title") or "")[:240],
                "confidence": item.get("confidence"),
            }
            for item in hypotheses[:8]
            if isinstance(item, dict)
        ],
        "factor_count": len(factor_rows) if isinstance(factor_rows, list) else 0,
        "nonlinear_link_count": (
            len(nonlinear_rows) if isinstance(nonlinear_rows, list) else 0
        ),
        "profit_validation_count": (
            len(validation_rows) if isinstance(validation_rows, list) else 0
        ),
        "audit_recommendation": audit.get("recommendation"),
        "audit_finding_count": len(audit.get("material_findings", []))
        if isinstance(audit.get("material_findings"), list)
        else 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-research-batch-worker")
    parser.add_argument("--poll-seconds", type=float, default=5)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = get_settings()
    worker = ResearchBatchWorker(
        get_session_factory(),
        settings=settings,
        stall_timeout_seconds=settings.research_watchdog_stall_seconds,
        model_stall_timeout_seconds=settings.research_watchdog_model_stall_seconds,
        cancellation_grace_seconds=settings.research_watchdog_cancel_grace_seconds,
        max_attempts=settings.research_batch_max_attempts,
    )
    worker.run_forever(poll_seconds=args.poll_seconds)


def _age_seconds(start: datetime, end: datetime) -> float:
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    return max(0.0, (end - start).total_seconds())


if __name__ == "__main__":
    main()
