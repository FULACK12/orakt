"""Real-time task console and cooperative cancellation tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request

from app.api.tasks import cancel_task
from app.db.base import Base
from app.db.enums import ClusterJobStatus
from app.db.models import ClusterJob, ResearchBatch, ResearchBatchItem, TaskControlRecord
from app.schemas.tasks import TaskCancelRequest
from app.task_controls import (
    CANCELLED_MESSAGE,
    TaskCancellationRequested,
    TaskConfirmationError,
    build_task_console,
    finish_cancelled_research_item,
    raise_if_cancellation_requested,
    request_task_cancellation,
)


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def test_console_normalizes_live_report_and_cluster_progress(
    session_factory: sessionmaker[Session],
) -> None:
    now = datetime.now(UTC)
    with session_factory() as session:
        batch, item = _research_item(session, status="running")
        item.progress_percent = 42
        item.progress_stage = "writing_report"
        item.started_at = now
        item.heartbeat_at = now
        cluster = ClusterJob(
            status=ClusterJobStatus.QUEUED,
            total_documents=100,
            processed_documents=25,
            progress_percent=22.5,
            progress_stage="analyzing_documents",
            batch_size=5,
            parameters={},
        )
        session.add(cluster)
        session.commit()

        console = build_task_console(session, now=now)

    report_view = next(
        task for task in console.tasks if task.key == f"research_batch_item:{item.id}"
    )
    cluster_view = next(task for task in console.tasks if task.key == f"cluster_job:{cluster.id}")
    assert batch.id == report_view.parent_id
    assert report_view.state == "running"
    assert report_view.progress_percent == 42
    assert report_view.stage == "writing_report"
    assert cluster_view.state == "queued"
    assert cluster_view.progress_percent == 22.5
    assert cluster_view.queue_position == 1
    assert console.summary.model_busy is True


def test_queued_report_stops_immediately_without_deleting_audit_record(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        batch, item = _research_item(session, status="queued")
        session.commit()

        accepted, safe_checkpoint = request_task_cancellation(
            session,
            task_kind="research_batch_item",
            task_id=item.id,
            confirmation=f"research_batch_item:{item.id}",
        )
        console = build_task_console(session)
        control = session.query(TaskControlRecord).one()

    task = next(task for task in console.tasks if task.key == f"research_batch_item:{item.id}")
    assert accepted is True
    assert safe_checkpoint is True
    assert task.state == "cancelled"
    assert task.raw_status == "failed"
    assert item.error_message == CANCELLED_MESSAGE
    assert control.status == "acknowledged"
    assert batch.status == "failed"
    assert batch.failed_count == 1


def test_running_report_waits_for_worker_safe_checkpoint(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        _, item = _research_item(session, status="running")
        item.started_at = datetime.now(UTC)
        session.commit()

        accepted, safe_checkpoint = request_task_cancellation(
            session,
            task_kind="research_batch_item",
            task_id=item.id,
            confirmation=f"research_batch_item:{item.id}",
        )
        pending = build_task_console(session)
        with pytest.raises(TaskCancellationRequested):
            raise_if_cancellation_requested(
                session,
                task_kind="research_batch_item",
                task_id=item.id,
            )
        finish_cancelled_research_item(session, item_id=item.id)
        finished = build_task_console(session)

    pending_task = next(
        task for task in pending.tasks if task.key == f"research_batch_item:{item.id}"
    )
    finished_task = next(
        task for task in finished.tasks if task.key == f"research_batch_item:{item.id}"
    )
    assert accepted is True
    assert safe_checkpoint is False
    assert pending_task.state == "cancelling"
    assert pending_task.can_cancel is False
    assert finished_task.state == "cancelled"
    assert finished_task.cancel_acknowledged_at is not None


def test_queued_cluster_job_stops_immediately(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        job = ClusterJob(
            status=ClusterJobStatus.QUEUED,
            total_documents=10,
            processed_documents=0,
            batch_size=2,
            parameters={},
        )
        session.add(job)
        session.commit()

        accepted, safe_checkpoint = request_task_cancellation(
            session,
            task_kind="cluster_job",
            task_id=job.id,
            confirmation=f"cluster_job:{job.id}",
        )
        console = build_task_console(session)

    task = next(task for task in console.tasks if task.key == f"cluster_job:{job.id}")
    assert accepted is True
    assert safe_checkpoint is True
    assert task.state == "cancelled"
    assert job.status == ClusterJobStatus.FAILED
    assert job.error_message == CANCELLED_MESSAGE


def test_console_labels_no_work_duplicate_report_as_skipped(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        batch, item = _research_item(session, status="failed")
        batch.name = "Daily rotation (duplicate suppressed)"
        item.progress_percent = 100
        item.progress_message = "与既有批次完全重复, 已停止重复计算"
        session.commit()

        console = build_task_console(session)

    task = next(task for task in console.tasks if task.task_id == item.id)
    assert task.state == "skipped"
    assert task.details["duplicate_suppressed"] is True
    assert console.summary.skipped == 1
    assert console.summary.failed == 0


def test_console_collapses_repeated_cluster_snapshot_records(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        parameters = {
            "document_ids": [1, 2],
            "batch_size": 2,
            "merge_threshold": 0.86,
            "time_window_hours": 48,
            "location_radius_km": 100,
            "snapshot_fingerprint": "a" * 64,
            "extractor_name": "test",
            "embedding_provider": "test",
        }
        failed = ClusterJob(
            status=ClusterJobStatus.FAILED,
            total_documents=2,
            processed_documents=2,
            progress_percent=75,
            progress_stage="failed",
            batch_size=2,
            parameters=parameters,
            error_message="temporary failure",
        )
        completed = ClusterJob(
            status=ClusterJobStatus.COMPLETED,
            total_documents=2,
            processed_documents=2,
            progress_percent=100,
            progress_stage="completed",
            batch_size=2,
            parameters=parameters,
        )
        session.add_all([failed, completed])
        session.commit()

        console = build_task_console(session)

    cluster_tasks = [task for task in console.tasks if task.kind == "cluster_job"]
    assert len(cluster_tasks) == 1
    assert cluster_tasks[0].state == "completed"
    assert cluster_tasks[0].details["duplicate_records_collapsed"] == 1
    assert cluster_tasks[0].details["snapshot_attempt_records"] == [failed.id, completed.id]


def test_cancellation_requires_exact_task_key(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        _, item = _research_item(session, status="queued")
        session.commit()

        with pytest.raises(TaskConfirmationError):
            request_task_cancellation(
                session,
                task_kind="research_batch_item",
                task_id=item.id,
                confirmation="confirm",
            )


def test_cancel_endpoint_accepts_loopback_and_rejects_remote_host(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        _, local_item = _research_item(session, status="queued")
        session.commit()
        response = cancel_task(
            task_kind="research_batch_item",
            task_id=local_item.id,
            cancellation=TaskCancelRequest(
                confirmation=f"research_batch_item:{local_item.id}"
            ),
            http_request=_http_request("127.0.0.1"),
            session=session,
        )

    assert response.safe_checkpoint is True
    assert response.task.state == "cancelled"

    with session_factory() as session:
        _, remote_item = _research_item(session, status="queued")
        session.commit()
        with pytest.raises(HTTPException) as exc_info:
            cancel_task(
                task_kind="research_batch_item",
                task_id=remote_item.id,
                cancellation=TaskCancelRequest(
                    confirmation=f"research_batch_item:{remote_item.id}"
                ),
                http_request=_http_request("news-map.example.test"),
                session=session,
            )

    assert exc_info.value.status_code == 403


def _research_item(
    session: Session,
    *,
    status: str,
) -> tuple[ResearchBatch, ResearchBatchItem]:
    batch = ResearchBatch(
        name="Task console test batch",
        status="running" if status == "running" else "queued",
        template_version="test-v1",
        parameters={},
        target_count=1,
        completed_count=0,
        failed_count=0,
        started_at=datetime.now(UTC) if status == "running" else None,
    )
    item = ResearchBatchItem(
        market_region="us",
        research_scope="sec_numeric_evidence",
        ticker="AAPL",
        company_name="Apple Inc.",
        question="Test a durable report task.",
        priority=1,
        status=status,
        progress_percent=0,
        progress_stage=status,
        data_readiness={},
    )
    batch.items.append(item)
    session.add(batch)
    session.flush()
    return batch, item


def _http_request(hostname: str) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/operations/tasks/research_batch_item/1/cancel",
            "raw_path": b"/operations/tasks/research_batch_item/1/cancel",
            "query_string": b"",
            "headers": [(b"host", f"{hostname}:8000".encode())],
            "server": (hostname, 8000),
            "client": ("127.0.0.1", 49152),
        }
    )
