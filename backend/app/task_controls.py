"""Safe, cooperative cancellation and normalized task-console snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.enums import ClusterJobStatus
from app.db.models import (
    ClusterJob,
    ResearchBatch,
    ResearchBatchItem,
    TaskControlRecord,
)
from app.schemas.tasks import (
    ResearchCheckpointEntry,
    ResearchCheckpointResponse,
    TaskConsoleItem,
    TaskConsoleResponse,
    TaskConsoleSummary,
    TaskKind,
    TaskState,
)

CANCEL_REQUESTED_MESSAGE = "cancellation_requested_by_local_operator"
CANCELLED_MESSAGE = "cancelled_by_local_operator_at_safe_checkpoint"
RESEARCH_LONG_RUNNING_STAGES = frozenset(
    {
        "question_planning",
        "local_draft",
        "local_episode_repair",
        "local_evidence_revision",
    }
)


class TaskNotFoundError(LookupError):
    """Raised when a task key does not resolve to a durable task."""


class TaskNotCancellableError(RuntimeError):
    """Raised when terminal work cannot be cancelled."""


class TaskConfirmationError(ValueError):
    """Raised when the caller did not echo the exact task key."""


class TaskCancellationRequested(RuntimeError):
    """Cooperative signal raised only at a worker safe checkpoint."""

    def __init__(self, task_kind: TaskKind, task_id: int) -> None:
        self.task_kind = task_kind
        self.task_id = task_id
        super().__init__(f"{task_kind}:{task_id} cancellation requested")


def request_task_cancellation(
    session: Session,
    *,
    task_kind: TaskKind,
    task_id: int,
    confirmation: str,
) -> tuple[bool, bool]:
    """Request cancellation and immediately stop work that has not started."""
    key = f"{task_kind}:{task_id}"
    if confirmation != key:
        raise TaskConfirmationError(f"confirmation must exactly equal {key}")
    now = datetime.now(UTC)
    control = _control_record(session, task_kind=task_kind, task_id=task_id)
    if task_kind == "research_batch_item":
        item = session.get(ResearchBatchItem, task_id)
        if item is None:
            raise TaskNotFoundError(key)
        if _research_item_cancelled(item):
            if control is not None and control.status != "acknowledged":
                _acknowledge(control, now=now)
                session.commit()
            return False, True
        if item.status in {"completed", "failed"}:
            raise TaskNotCancellableError(f"{key} is already terminal")
        control = _ensure_control(
            session,
            control=control,
            task_kind=task_kind,
            task_id=task_id,
            now=now,
        )
        if item.status == "queued":
            _finish_cancelled_research_item(item, now=now)
            _acknowledge(control, now=now)
            _update_research_batch_status(session, item.batch_id, now=now)
            safe_checkpoint = True
        else:
            item.progress_stage = "cancelling"
            item.progress_message = "已请求安全停止, 等待当前模型或证据步骤结束"
            item.heartbeat_at = now
            safe_checkpoint = False
    else:
        job = session.get(ClusterJob, task_id)
        if job is None:
            raise TaskNotFoundError(key)
        if _cluster_job_cancelled(job):
            if control is not None and control.status != "acknowledged":
                _acknowledge(control, now=now)
                session.commit()
            return False, True
        if job.status in {ClusterJobStatus.COMPLETED, ClusterJobStatus.FAILED}:
            raise TaskNotCancellableError(f"{key} is already terminal")
        control = _ensure_control(
            session,
            control=control,
            task_kind=task_kind,
            task_id=task_id,
            now=now,
        )
        if job.status == ClusterJobStatus.QUEUED:
            _finish_cancelled_cluster_job(job, now=now)
            _acknowledge(control, now=now)
            safe_checkpoint = True
        else:
            job.progress_stage = "cancelling"
            job.progress_message = "已请求安全停止, 等待当前模型或聚类步骤结束"
            job.heartbeat_at = now
            job.error_message = CANCEL_REQUESTED_MESSAGE
            safe_checkpoint = False
    session.commit()
    return True, safe_checkpoint


def raise_if_cancellation_requested(
    session: Session,
    *,
    task_kind: TaskKind,
    task_id: int,
) -> None:
    """Raise a typed signal when an unacknowledged request exists."""
    requested = session.scalar(
        select(TaskControlRecord.id).where(
            TaskControlRecord.task_kind == task_kind,
            TaskControlRecord.task_id == task_id,
            TaskControlRecord.action == "cancel",
            TaskControlRecord.status == "requested",
        )
    )
    if requested is not None:
        raise TaskCancellationRequested(task_kind, task_id)


def finish_cancelled_research_item(
    session: Session,
    *,
    item_id: int,
) -> None:
    """Acknowledge a running report cancellation at a safe checkpoint."""
    now = datetime.now(UTC)
    item = session.get(ResearchBatchItem, item_id)
    if item is None:
        return
    _finish_cancelled_research_item(item, now=now)
    control = _control_record(
        session,
        task_kind="research_batch_item",
        task_id=item_id,
    )
    if control is not None:
        _acknowledge(control, now=now)
    _update_research_batch_status(session, item.batch_id, now=now)
    session.commit()


def finish_cancelled_cluster_job(session: Session, *, job_id: int) -> None:
    """Acknowledge a running cluster cancellation at a cache boundary."""
    now = datetime.now(UTC)
    job = session.get(ClusterJob, job_id)
    if job is None:
        return
    _finish_cancelled_cluster_job(job, now=now)
    control = _control_record(session, task_kind="cluster_job", task_id=job_id)
    if control is not None:
        _acknowledge(control, now=now)
    session.commit()


def build_task_console(
    session: Session,
    *,
    limit: int = 120,
    now: datetime | None = None,
) -> TaskConsoleResponse:
    """Return active tasks plus the most recent terminal work."""
    generated_at = now or datetime.now(UTC)
    active_items = list(
        session.scalars(
            select(ResearchBatchItem)
            .join(ResearchBatch, ResearchBatch.id == ResearchBatchItem.batch_id)
            .where(ResearchBatchItem.status.in_(("queued", "running")))
            .order_by(
                ResearchBatch.created_at,
                ResearchBatch.id,
                ResearchBatchItem.priority,
                ResearchBatchItem.created_at,
            )
        )
    )
    terminal_items = list(
        session.scalars(
            select(ResearchBatchItem)
            .where(ResearchBatchItem.status.in_(("completed", "failed")))
            .order_by(ResearchBatchItem.updated_at.desc(), ResearchBatchItem.id.desc())
            .limit(limit)
        )
    )
    active_jobs = list(
        session.scalars(
            select(ClusterJob)
            .where(ClusterJob.status.in_((ClusterJobStatus.QUEUED, ClusterJobStatus.RUNNING)))
            .order_by(ClusterJob.created_at, ClusterJob.id)
        )
    )
    terminal_jobs = list(
        session.scalars(
            select(ClusterJob)
            .where(ClusterJob.status.in_((ClusterJobStatus.COMPLETED, ClusterJobStatus.FAILED)))
            .order_by(ClusterJob.updated_at.desc(), ClusterJob.id.desc())
            .limit(limit)
        )
    )
    control_rows = list(session.scalars(select(TaskControlRecord)))
    controls = {(row.task_kind, row.task_id): row for row in control_rows}
    batches = {
        batch.id: batch
        for batch in session.scalars(
            select(ResearchBatch).where(
                ResearchBatch.id.in_({item.batch_id for item in [*active_items, *terminal_items]})
            )
        )
    }
    queued_research_ids = [item.id for item in active_items if item.status == "queued"]
    cluster_jobs, cluster_lineages = _collapse_cluster_snapshot_attempts(
        _unique_by_id([*active_jobs, *terminal_jobs])
    )
    queued_cluster_ids = [
        job.id for job in cluster_jobs if job.status == ClusterJobStatus.QUEUED
    ]
    tasks = [
        _research_task_view(
            item,
            batch=batches.get(item.batch_id),
            control=controls.get(("research_batch_item", item.id)),
            now=generated_at,
            queue_position=(
                queued_research_ids.index(item.id) + 1 if item.id in queued_research_ids else None
            ),
        )
        for item in _unique_by_id([*active_items, *terminal_items])[:limit]
    ]
    tasks.extend(
        _cluster_task_view(
            job,
            control=controls.get(("cluster_job", job.id)),
            now=generated_at,
            queue_position=(
                queued_cluster_ids.index(job.id) + 1 if job.id in queued_cluster_ids else None
            ),
            lineage=lineage,
        )
        for job in cluster_jobs[:limit]
        for lineage in [cluster_lineages.get(job.id, [job.id])]
    )
    state_order = {
        "cancelling": 0,
        "running": 1,
        "queued": 2,
        "failed": 3,
        "cancelled": 4,
        "skipped": 5,
        "completed": 6,
    }
    tasks.sort(key=lambda task: (state_order[task.state], -task.updated_at.timestamp()))
    counts: dict[TaskState, int] = {
        "queued": 0,
        "running": 0,
        "cancelling": 0,
        "completed": 0,
        "failed": 0,
        "cancelled": 0,
        "skipped": 0,
    }
    for task in tasks:
        counts[task.state] += 1
    return TaskConsoleResponse(
        generated_at=generated_at,
        refresh_after_seconds=2,
        summary=TaskConsoleSummary(
            queued=counts["queued"],
            running=counts["running"],
            cancelling=counts["cancelling"],
            completed=counts["completed"],
            failed=counts["failed"],
            cancelled=counts["cancelled"],
            skipped=counts["skipped"],
            model_busy=bool(counts["running"] or counts["cancelling"]),
        ),
        tasks=tasks,
    )


def task_from_console(
    console: TaskConsoleResponse,
    *,
    task_kind: TaskKind,
    task_id: int,
) -> TaskConsoleItem:
    key = f"{task_kind}:{task_id}"
    for task in console.tasks:
        if task.key == key:
            return task
    raise TaskNotFoundError(key)


def research_checkpoint_response(
    session: Session,
    *,
    item_id: int,
) -> ResearchCheckpointResponse:
    """Expose compact checkpoint history while retaining the full resume payload locally."""
    item = session.get(ResearchBatchItem, item_id)
    if item is None:
        raise TaskNotFoundError(f"research_batch_item:{item_id}")
    checkpoint = item.checkpoint_data if isinstance(item.checkpoint_data, dict) else {}
    raw_history = checkpoint.get("history")
    history = raw_history if isinstance(raw_history, list) else []
    entries: list[ResearchCheckpointEntry] = []
    for raw in history:
        if not isinstance(raw, dict):
            continue
        try:
            entries.append(ResearchCheckpointEntry.model_validate(raw))
        except (TypeError, ValueError):
            continue
    resume = checkpoint.get("resume")
    return ResearchCheckpointResponse(
        task_id=item.id,
        latest_stage=(str(checkpoint["latest_stage"]) if checkpoint.get("latest_stage") else None),
        latest_at=item.checkpoint_at,
        resumable=isinstance(resume, dict) and isinstance(resume.get("evidence"), dict),
        entries=entries,
    )


def _research_task_view(
    item: ResearchBatchItem,
    *,
    batch: ResearchBatch | None,
    control: TaskControlRecord | None,
    now: datetime,
    queue_position: int | None,
) -> TaskConsoleItem:
    settings = get_settings()
    suppressed = _research_item_duplicate_suppressed(item, batch=batch)
    state: TaskState = (
        "skipped"
        if suppressed
        else _derived_state(
            raw_status=item.status,
            cancelled=_research_item_cancelled(item),
            control=control,
        )
    )
    return TaskConsoleItem(
        key=f"research_batch_item:{item.id}",
        kind="research_batch_item",
        task_id=item.id,
        parent_id=item.batch_id,
        title=f"{item.ticker} · {item.company_name}",
        subtitle=batch.name if batch is not None else f"研究批次 #{item.batch_id}",
        state=state,
        raw_status=item.status,
        progress_percent=item.progress_percent,
        stage=item.progress_stage,
        message=(
            item.error_message
            if state == "failed" and item.error_message
            else item.progress_message or item.error_message
        ),
        queue_position=queue_position,
        can_cancel=item.status in {"queued", "running"} and state != "cancelling",
        cancel_requested_at=control.requested_at if control is not None else None,
        cancel_acknowledged_at=control.acknowledged_at if control is not None else None,
        created_at=item.created_at,
        updated_at=item.updated_at,
        started_at=item.started_at,
        completed_at=item.completed_at,
        heartbeat_at=item.heartbeat_at,
        elapsed_seconds=_elapsed(item.started_at or item.created_at, item.completed_at or now),
        stale_seconds=(
            _elapsed(item.heartbeat_at, now) if item.heartbeat_at is not None else None
        ),
        watchdog_threshold_seconds=(
            settings.research_watchdog_model_stall_seconds
            if item.progress_stage in RESEARCH_LONG_RUNNING_STAGES
            else settings.research_watchdog_stall_seconds
        ),
        details={
            "ticker": item.ticker,
            "company": item.company_name,
            "market_region": item.market_region,
            "attempt_count": item.attempt_count,
            "max_attempts": settings.research_batch_max_attempts,
            "inquiry_id": item.inquiry_id,
            "batch_status": batch.status if batch is not None else None,
            "research_scope": item.research_scope,
            "sector": item.sector,
            "question": item.question,
            "checkpoint_count": len(
                item.checkpoint_data.get("history", [])
                if isinstance(item.checkpoint_data, dict)
                else []
            ),
            "latest_checkpoint": (
                item.checkpoint_data.get("latest_stage")
                if isinstance(item.checkpoint_data, dict)
                else None
            ),
            "checkpoint_at": item.checkpoint_at.isoformat() if item.checkpoint_at else None,
            "duplicate_suppressed": suppressed,
        },
    )


def _cluster_task_view(
    job: ClusterJob,
    *,
    control: TaskControlRecord | None,
    now: datetime,
    queue_position: int | None,
    lineage: list[int],
) -> TaskConsoleItem:
    raw_status = job.status.value
    state = _derived_state(
        raw_status=raw_status,
        cancelled=_cluster_job_cancelled(job),
        control=control,
    )
    return TaskConsoleItem(
        key=f"cluster_job:{job.id}",
        kind="cluster_job",
        task_id=job.id,
        parent_id=None,
        title=f"新闻聚类与小报告 #{job.id}",
        subtitle=(
            f"{job.processed_documents} / {job.total_documents} 条文档"
            + (f" · 已合并 {len(lineage)} 条同快照历史记录" if len(lineage) > 1 else "")
        ),
        state=state,
        raw_status=raw_status,
        progress_percent=round(job.progress_percent, 2),
        stage=job.progress_stage,
        message=(
            job.error_message
            if state == "failed" and job.error_message
            else job.progress_message or job.error_message
        ),
        queue_position=queue_position,
        can_cancel=job.status in {ClusterJobStatus.QUEUED, ClusterJobStatus.RUNNING}
        and state != "cancelling",
        cancel_requested_at=control.requested_at if control is not None else None,
        cancel_acknowledged_at=control.acknowledged_at if control is not None else None,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        heartbeat_at=job.heartbeat_at,
        elapsed_seconds=_elapsed(job.started_at or job.created_at, job.completed_at or now),
        stale_seconds=(
            _elapsed(job.heartbeat_at, now)
            if job.status == ClusterJobStatus.RUNNING and job.heartbeat_at is not None
            else None
        ),
        watchdog_threshold_seconds=900,
        details={
            "processed_documents": job.processed_documents,
            "total_documents": job.total_documents,
            "batch_size": job.batch_size,
            "attempt_count": job.attempt_count,
            "max_attempts": job.max_attempts,
            "snapshot_fingerprint": (
                job.parameters.get("snapshot_fingerprint")
                if isinstance(job.parameters, dict)
                else None
            ),
            "snapshot_attempt_records": lineage,
            "duplicate_records_collapsed": max(0, len(lineage) - 1),
        },
    )


def _derived_state(
    *,
    raw_status: str,
    cancelled: bool,
    control: TaskControlRecord | None,
) -> TaskState:
    if cancelled:
        return "cancelled"
    if control is not None and control.status == "requested":
        return "cancelling"
    return cast(TaskState, raw_status)


def _control_record(
    session: Session,
    *,
    task_kind: TaskKind,
    task_id: int,
) -> TaskControlRecord | None:
    return session.scalar(
        select(TaskControlRecord).where(
            TaskControlRecord.task_kind == task_kind,
            TaskControlRecord.task_id == task_id,
            TaskControlRecord.action == "cancel",
        )
    )


def _ensure_control(
    session: Session,
    *,
    control: TaskControlRecord | None,
    task_kind: TaskKind,
    task_id: int,
    now: datetime,
) -> TaskControlRecord:
    if control is not None:
        return control
    control = TaskControlRecord(
        task_kind=task_kind,
        task_id=task_id,
        action="cancel",
        status="requested",
        requested_at=now,
        message="Cancellation requested from the local task console.",
    )
    session.add(control)
    session.flush()
    return control


def _acknowledge(control: TaskControlRecord, *, now: datetime) -> None:
    control.status = "acknowledged"
    control.acknowledged_at = now
    control.message = "Cancellation completed at a worker safe checkpoint."


def _finish_cancelled_research_item(
    item: ResearchBatchItem,
    *,
    now: datetime,
) -> None:
    item.status = "failed"
    item.progress_stage = "cancelled"
    item.progress_message = "已在安全检查点停止"
    item.error_message = CANCELLED_MESSAGE
    item.heartbeat_at = now
    item.completed_at = now


def _finish_cancelled_cluster_job(job: ClusterJob, *, now: datetime) -> None:
    job.status = ClusterJobStatus.FAILED
    job.progress_stage = "cancelled"
    job.progress_message = "已在安全检查点停止"
    job.heartbeat_at = now
    job.error_message = CANCELLED_MESSAGE
    job.completed_at = now


def _research_item_cancelled(item: ResearchBatchItem) -> bool:
    return item.progress_stage == "cancelled" or item.error_message == CANCELLED_MESSAGE


def _research_item_duplicate_suppressed(
    item: ResearchBatchItem,
    *,
    batch: ResearchBatch | None,
) -> bool:
    """Recognize legacy no-work duplicate rows without calling them failures."""
    if item.progress_stage in {"duplicate_suppressed", "superseded"}:
        return True
    if item.attempt_count != 0 or item.inquiry_id is not None:
        return False
    text = " ".join(
        value
        for value in (
            item.progress_message,
            item.error_message,
            batch.name if batch is not None else None,
        )
        if value
    )
    return "重复任务" in text or "完全重复" in text


def _cluster_job_cancelled(job: ClusterJob) -> bool:
    return job.error_message == CANCELLED_MESSAGE


def _update_research_batch_status(
    session: Session,
    batch_id: int,
    *,
    now: datetime,
) -> None:
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
    batch.status = (
        "completed"
        if batch.failed_count == 0
        else "partial_failed"
        if batch.completed_count
        else "failed"
    )


class _HasIntegerId(Protocol):
    id: int


def _unique_by_id[T: _HasIntegerId](rows: list[T]) -> list[T]:
    unique: dict[int, T] = {}
    for row in rows:
        row_id = int(row.id)
        unique.setdefault(row_id, row)
    return list(unique.values())


def _collapse_cluster_snapshot_attempts(
    jobs: list[ClusterJob],
) -> tuple[list[ClusterJob], dict[int, list[int]]]:
    """Show one task chain for repeated attempts over an identical snapshot."""
    groups: dict[tuple[object, ...], list[ClusterJob]] = {}
    for job in jobs:
        parameters = job.parameters if isinstance(job.parameters, dict) else {}
        fingerprint = parameters.get("snapshot_fingerprint")
        if fingerprint:
            key: tuple[object, ...] = ("fingerprint", str(fingerprint))
        else:
            raw_ids = parameters.get("document_ids")
            document_ids = tuple(raw_ids) if isinstance(raw_ids, list) else (job.id,)
            key = (
                "legacy",
                document_ids,
                parameters.get("batch_size"),
                parameters.get("merge_threshold"),
                parameters.get("time_window_hours"),
                parameters.get("location_radius_km"),
            )
        groups.setdefault(key, []).append(job)

    representatives: list[ClusterJob] = []
    lineages: dict[int, list[int]] = {}
    for attempts in groups.values():
        active = [
            job
            for job in attempts
            if job.status in {ClusterJobStatus.QUEUED, ClusterJobStatus.RUNNING}
        ]
        completed = [job for job in attempts if job.status == ClusterJobStatus.COMPLETED]
        representative = (
            max(active, key=lambda job: job.id)
            if active
            else max(completed, key=lambda job: job.id)
            if completed
            else max(attempts, key=lambda job: job.id)
        )
        representatives.append(representative)
        lineages[representative.id] = sorted(job.id for job in attempts)
    representatives.sort(key=lambda job: job.updated_at, reverse=True)
    return representatives, lineages


def _elapsed(start: datetime, end: datetime) -> float:
    if start.tzinfo is None and end.tzinfo is not None:
        start = start.replace(tzinfo=UTC)
    elif start.tzinfo is not None and end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    return max(0.0, (end - start).total_seconds())
