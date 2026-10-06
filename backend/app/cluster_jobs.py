"""Durable worker for full-snapshot event clustering jobs."""

from __future__ import annotations

import argparse
import logging
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Event, Thread

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.cluster_service import build_cluster_preview
from app.core.config import get_settings
from app.db.enums import ClusterJobStatus
from app.db.models import (
    ClusterJob,
    DocumentAnalysis,
    ResearchBatchItem,
    TaskControlRecord,
)
from app.db.session import get_session_factory
from app.embeddings import (
    EmbeddingClient,
    EmbeddingProviderUnavailableError,
    build_embedding_client,
)
from app.event_chains import generate_event_chain
from app.extractors import EventExtractor, build_event_extractor
from app.logic_chains import generate_logic_hypotheses
from app.model_workload import local_model_workload_lock
from app.schemas.cluster_jobs import ClusterJobParameters, ClusterJobResult
from app.schemas.clusters import ClusterPreviewRequest, ClusterPreviewResponse
from app.task_controls import (
    TaskCancellationRequested,
    finish_cancelled_cluster_job,
    raise_if_cancellation_requested,
)

logger = logging.getLogger(__name__)


class ModelWorkloadYieldRequested(RuntimeError):
    """A bounded cluster batch finished and a research report is waiting."""


class _ClusterJobWatchdog:
    """Restart one worker process when cancellation or progress is stuck."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        job_id: int,
        stall_timeout_seconds: float,
        cancellation_grace_seconds: float,
    ) -> None:
        self._session_factory = session_factory
        self._job_id = job_id
        self._stall_timeout_seconds = stall_timeout_seconds
        self._cancellation_grace_seconds = cancellation_grace_seconds
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
                job = session.get(ClusterJob, self._job_id)
                if job is None or job.status != ClusterJobStatus.RUNNING:
                    return
                now = datetime.now(UTC)
                control = session.scalar(
                    select(TaskControlRecord).where(
                        TaskControlRecord.task_kind == "cluster_job",
                        TaskControlRecord.task_id == self._job_id,
                        TaskControlRecord.action == "cancel",
                        TaskControlRecord.status == "requested",
                    )
                )
                if control is not None and _age_seconds(control.requested_at, now) > (
                    self._cancellation_grace_seconds
                ):
                    job.progress_stage = "cancellation_watchdog"
                    job.progress_message = "安全停止等待超时, 正在重启工作器完成取消"
                    job.heartbeat_at = now
                    session.commit()
                    logger.error(
                        "cluster_cancellation_watchdog_restart",
                        extra={"cluster_job_id": self._job_id},
                    )
                    os._exit(72)
                heartbeat = job.heartbeat_at or job.started_at or job.updated_at
                if _age_seconds(heartbeat, now) <= self._stall_timeout_seconds:
                    continue
                if job.attempt_count >= job.max_attempts:
                    job.status = ClusterJobStatus.FAILED
                    job.completed_at = now
                    job.progress_stage = "watchdog_failed"
                    job.progress_message = "连续无进展次数已达上限, 任务已停止等待检查"
                    job.error_message = "watchdog_stall_retry_limit_reached"
                else:
                    job.status = ClusterJobStatus.QUEUED
                    job.started_at = None
                    job.progress_stage = "watchdog_requeued"
                    job.progress_message = "长时间没有进展, 已自动重排并保留分析缓存"
                    job.error_message = "watchdog_stall_requeued"
                job.heartbeat_at = now
                session.commit()
                logger.error(
                    "cluster_stall_watchdog_restart",
                    extra={"cluster_job_id": self._job_id},
                )
                os._exit(73)


def classify_cluster_preview(
    preview: ClusterPreviewResponse,
) -> ClusterJobResult:
    """Split clusters into merge, manual-review and independent categories."""
    merge_ids = {
        cluster.cluster_id
        for cluster in preview.clusters
        if len(cluster.members) > 1
    }
    near_candidate_ids = {
        candidate_id
        for pair in preview.rejected_near_matches
        for candidate_id in (
            pair.left_candidate_id,
            pair.right_candidate_id,
        )
    }
    review_ids = {
        cluster.cluster_id
        for cluster in preview.clusters
        if cluster.cluster_id not in merge_ids
        and any(
            member.candidate_id in near_candidate_ids
            for member in cluster.members
        )
    }
    all_ids = {cluster.cluster_id for cluster in preview.clusters}
    return ClusterJobResult(
        preview=preview,
        merge_cluster_ids=sorted(merge_ids),
        review_cluster_ids=sorted(review_ids),
        independent_cluster_ids=sorted(all_ids - merge_ids - review_ids),
    )


class ClusterJobWorker:
    """Claim, process and finalize one database-backed job at a time."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        extractor: EventExtractor,
        embedding_client: EmbeddingClient,
        review_secret: str,
        logic_generator: Callable[[Session, int], object] | None = None,
        stall_timeout_seconds: float | None = None,
        cancellation_grace_seconds: float = 300,
    ) -> None:
        self._session_factory = session_factory
        self._extractor = extractor
        self._embedding_client = embedding_client
        self._review_secret = review_secret
        self._logic_generator = logic_generator
        self._stall_timeout_seconds = stall_timeout_seconds
        self._cancellation_grace_seconds = cancellation_grace_seconds
        self._model_retry_after_monotonic = 0.0

    def recover_interrupted_jobs(self) -> int:
        """Return jobs left running by a stopped worker to the queue."""
        cancelled_job_ids: list[int] = []
        with self._session_factory() as session:
            jobs = list(
                session.scalars(
                    select(ClusterJob).where(
                        ClusterJob.status == ClusterJobStatus.RUNNING
                    )
                )
            )
            for job in jobs:
                try:
                    raise_if_cancellation_requested(
                        session,
                        task_kind="cluster_job",
                        task_id=job.id,
                    )
                except TaskCancellationRequested:
                    cancelled_job_ids.append(job.id)
                    continue
                if job.attempt_count >= job.max_attempts:
                    job.status = ClusterJobStatus.FAILED
                    job.progress_stage = "watchdog_failed"
                    job.progress_message = "工作器异常中断次数已达上限, 需要人工检查"
                    job.error_message = "watchdog_retry_limit_reached"
                    job.completed_at = datetime.now(UTC)
                    continue
                job.status = ClusterJobStatus.QUEUED
                job.started_at = None
                job.progress_stage = "recovered_after_restart"
                job.progress_message = "工作器重启后已恢复排队, 将复用已完成的分析缓存"
                job.heartbeat_at = datetime.now(UTC)
                job.error_message = None
            session.commit()
        for job_id in cancelled_job_ids:
            with self._session_factory() as session:
                finish_cancelled_cluster_job(session, job_id=job_id)
        return len(jobs)

    def run_next(self) -> bool:
        """Claim and process the oldest queued job, if one exists."""
        if time.monotonic() < self._model_retry_after_monotonic:
            return False
        job_id = self._claim_next_job()
        if job_id is None:
            return False
        watchdog = self._start_watchdog(job_id)
        try:
            if not self._process_job(job_id):
                return False
        except Exception as exc:
            self._fail_job(job_id, exc)
        finally:
            if watchdog is not None:
                watchdog.stop()
        return True

    def run_forever(self, *, poll_seconds: float = 2) -> None:
        """Continuously process queued jobs until the process stops."""
        if poll_seconds < 0.1:
            raise ValueError("poll_seconds must be at least 0.1")
        self.recover_interrupted_jobs()
        try:
            while True:
                if not self.run_next():
                    time.sleep(poll_seconds)
        except KeyboardInterrupt:
            return

    def _claim_next_job(self) -> int | None:
        with self._session_factory() as session:
            job = session.scalar(
                select(ClusterJob)
                .where(ClusterJob.status == ClusterJobStatus.QUEUED)
                .order_by(ClusterJob.created_at, ClusterJob.id)
                .with_for_update(skip_locked=True)
            )
            if job is None:
                return None
            cooperative_resume = job.progress_stage in {
                "waiting_for_model",
                "yielded_to_report",
            }
            job.status = ClusterJobStatus.RUNNING
            now = datetime.now(UTC)
            job.started_at = now
            if cooperative_resume:
                # Resource hand-offs are scheduling decisions, not failed attempts.
                # Clamp legacy inflated counters produced before this distinction.
                job.attempt_count = min(job.attempt_count, 1)
            else:
                job.attempt_count += 1
            job.progress_percent = max(job.progress_percent, 2)
            job.progress_stage = "acquiring_model"
            job.progress_message = "正在申请共享本地模型资源"
            job.heartbeat_at = now
            job.error_message = None
            session.commit()
            return job.id

    def _process_job(self, job_id: int) -> bool:
        with self._session_factory() as session:
            job = session.get(ClusterJob, job_id)
            if job is None:
                return True
            with local_model_workload_lock(session) as acquired:
                if not acquired:
                    job.status = ClusterJobStatus.QUEUED
                    job.started_at = None
                    job.progress_stage = "waiting_for_model"
                    job.progress_message = "公司报告正在使用本地模型, 聚类任务继续排队"
                    job.heartbeat_at = datetime.now(UTC)
                    job.error_message = "Waiting for the shared local-model runtime"
                    session.commit()
                    return False
                raise_if_cancellation_requested(
                    session,
                    task_kind="cluster_job",
                    task_id=job_id,
                )
                parameters = ClusterJobParameters.model_validate(job.parameters)
                self._set_progress(
                    job_id,
                    stage="analyzing_documents",
                    percent=max(job.progress_percent, 5),
                    message=f"正在抽取并核对 {job.total_documents} 篇新闻的事件信息",
                )
                try:
                    preview = build_cluster_preview(
                        session,
                        request=ClusterPreviewRequest(
                            document_ids=parameters.document_ids,
                            merge_threshold=parameters.merge_threshold,
                            time_window_hours=parameters.time_window_hours,
                            location_radius_km=parameters.location_radius_km,
                        ),
                        extractor=self._extractor,
                        embedding_client=self._embedding_client,
                        review_secret=self._review_secret,
                        batch_size=parameters.batch_size,
                        progress_callback=lambda processed: (
                            self._update_progress_and_yield_if_research_waits(
                                job_id,
                                processed,
                            )
                        ),
                        phase_callback=lambda stage, percent, message: (
                            self._update_phase_and_check(
                                job_id,
                                stage=stage,
                                percent=percent,
                                message=message,
                            )
                        ),
                        cache_results=True,
                    )
                except ModelWorkloadYieldRequested:
                    job.status = ClusterJobStatus.QUEUED
                    job.started_at = None
                    job.progress_stage = "yielded_to_report"
                    job.progress_message = "已保存当前进度, 正在让出模型给公司报告"
                    job.heartbeat_at = datetime.now(UTC)
                    job.error_message = (
                        "Yielded the shared local-model runtime to a research report"
                    )
                    session.commit()
                    return False
                raise_if_cancellation_requested(
                    session,
                    task_kind="cluster_job",
                    task_id=job_id,
                )
                classified = classify_cluster_preview(preview)
                self._set_progress(
                    job_id,
                    stage="persisting_cluster_result",
                    percent=93,
                    message="正在保存聚类结果与文档分析索引",
                )
                analyses = list(
                    session.scalars(
                        select(DocumentAnalysis).where(
                            DocumentAnalysis.document_id.in_(
                                parameters.document_ids
                            )
                        )
                    )
                )
                for analysis in analyses:
                    analysis.last_cluster_job_id = job_id
                job.processed_documents = job.total_documents
                job.result = classified.model_dump(mode="json")
                session.flush()
                job.progress_percent = 96
                job.progress_stage = "building_event_chain"
                job.progress_message = "正在把相邻新闻整理为可审计事件链"
                job.heartbeat_at = datetime.now(UTC)
                generate_event_chain(session, job_id=job_id)
                session.commit()
                if self._logic_generator is not None:
                    self._set_progress(
                        job_id,
                        stage="generating_logic_chain",
                        percent=98,
                        message="正在提出并验证事件之间的逻辑假设",
                    )
                    try:
                        self._logic_generator(session, job_id)
                        session.commit()
                    except Exception:
                        session.rollback()
                        logger.exception(
                            "logic_hypothesis_generation_failed",
                            extra={"cluster_job_id": job_id},
                        )
                raise_if_cancellation_requested(
                    session,
                    task_kind="cluster_job",
                    task_id=job_id,
                )
                job.status = ClusterJobStatus.COMPLETED
                job.progress_percent = 100
                job.progress_stage = "completed"
                job.progress_message = "文档分析、聚类、事件链和逻辑链处理已完成"
                job.heartbeat_at = datetime.now(UTC)
                job.completed_at = job.heartbeat_at
                job.error_message = None
                session.commit()
                return True

    def _update_progress(self, job_id: int, processed: int) -> None:
        with self._session_factory() as session:
            job = session.get(ClusterJob, job_id)
            if job is None or job.status != ClusterJobStatus.RUNNING:
                return
            parameters = ClusterJobParameters.model_validate(job.parameters)
            cached_documents = int(
                session.scalar(
                    select(func.count(DocumentAnalysis.document_id)).where(
                        DocumentAnalysis.document_id.in_(parameters.document_ids)
                    )
                )
                or 0
            )
            # A yielded job restarts its preview scan from the first document,
            # while validated analyses remain reusable in the cache. Never let
            # the public counter jump backwards; include the durable cache so a
            # resumed job reports actual completed extraction work.
            job.processed_documents = min(
                max(job.processed_documents, processed, cached_documents),
                job.total_documents,
            )
            ratio = job.processed_documents / max(1, job.total_documents)
            job.progress_percent = max(job.progress_percent, min(75, 5 + ratio * 70))
            job.progress_stage = "analyzing_documents"
            job.progress_message = (
                f"正在抽取新闻事件 {job.processed_documents}/{job.total_documents}"
            )
            job.heartbeat_at = datetime.now(UTC)
            session.commit()

    def _update_progress_and_yield_if_research_waits(
        self,
        job_id: int,
        processed: int,
    ) -> None:
        """Commit a reusable cache boundary, then cooperatively yield to reports."""
        self._update_progress(job_id, processed)
        with self._session_factory() as session:
            raise_if_cancellation_requested(
                session,
                task_kind="cluster_job",
                task_id=job_id,
            )
            waiting_report = session.scalar(
                select(ResearchBatchItem.id)
                .where(ResearchBatchItem.status.in_(("queued", "running")))
                .limit(1)
            )
        if waiting_report is not None:
            raise ModelWorkloadYieldRequested

    def _update_phase_and_check(
        self,
        job_id: int,
        *,
        stage: str,
        percent: float,
        message: str,
    ) -> None:
        self._set_progress(
            job_id,
            stage=stage,
            percent=percent,
            message=message,
        )
        with self._session_factory() as session:
            raise_if_cancellation_requested(
                session,
                task_kind="cluster_job",
                task_id=job_id,
            )

    def _set_progress(
        self,
        job_id: int,
        *,
        stage: str,
        percent: float,
        message: str,
    ) -> None:
        with self._session_factory() as session:
            job = session.get(ClusterJob, job_id)
            if job is None or job.status != ClusterJobStatus.RUNNING:
                return
            job.progress_percent = max(job.progress_percent, min(100, percent))
            job.progress_stage = stage[:64]
            job.progress_message = message[:255]
            job.heartbeat_at = datetime.now(UTC)
            session.commit()

    def _start_watchdog(self, job_id: int) -> _ClusterJobWatchdog | None:
        if self._stall_timeout_seconds is None:
            return None
        watchdog = _ClusterJobWatchdog(
            self._session_factory,
            job_id=job_id,
            stall_timeout_seconds=self._stall_timeout_seconds,
            cancellation_grace_seconds=self._cancellation_grace_seconds,
        )
        watchdog.start()
        return watchdog

    def _fail_job(self, job_id: int, exc: Exception) -> None:
        if isinstance(exc, TaskCancellationRequested):
            with self._session_factory() as session:
                finish_cancelled_cluster_job(session, job_id=job_id)
            return
        with self._session_factory() as session:
            job = session.get(ClusterJob, job_id)
            if job is None:
                return
            if isinstance(exc, EmbeddingProviderUnavailableError):
                # Infrastructure downtime is not a failed analysis attempt. Keep
                # the same durable task queued, preserve its cache and back off
                # before probing Ollama again.
                job.status = ClusterJobStatus.QUEUED
                job.attempt_count = max(0, job.attempt_count - 1)
                job.started_at = None
                job.completed_at = None
                job.progress_stage = "waiting_for_model"
                job.progress_message = "Ollama 离线, 已保存进度并暂停等待恢复"
                job.heartbeat_at = datetime.now(UTC)
                job.error_message = f"{type(exc).__name__}: {str(exc)[:500]}"
                session.commit()
                self._model_retry_after_monotonic = time.monotonic() + 30
                return
            job.status = ClusterJobStatus.FAILED
            job.progress_stage = "failed"
            job.progress_message = "任务执行失败, 请查看错误信息"
            job.heartbeat_at = datetime.now(UTC)
            job.error_message = f"{type(exc).__name__}: {str(exc)[:500]}"
            job.completed_at = job.heartbeat_at
            session.commit()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-cluster-worker")
    parser.add_argument("--poll-seconds", type=float, default=2)
    return parser


def main() -> None:
    """Run the configured durable clustering worker."""
    args = build_parser().parse_args()
    settings = get_settings()
    worker = ClusterJobWorker(
        get_session_factory(),
        build_event_extractor(settings),
        build_embedding_client(settings),
        settings.cluster_review_secret,
        logic_generator=lambda session, job_id: generate_logic_hypotheses(
            session,
            job_id=job_id,
            settings=settings,
        ),
        stall_timeout_seconds=settings.cluster_watchdog_stall_seconds,
        cancellation_grace_seconds=settings.cluster_watchdog_cancel_grace_seconds,
    )
    worker.run_forever(poll_seconds=args.poll_seconds)


def _age_seconds(start: datetime, end: datetime) -> float:
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    return max(0.0, (end - start).total_seconds())


if __name__ == "__main__":
    main()
