"""Leased deterministic report-audit queue with frozen historical evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import ResearchInquiry, ResearchReportAuditJob
from app.db.session import get_session_factory
from app.research import LOCAL_REPORT_AUDIT_VERSION, audit_local_report
from app.schemas.research import ResearchAuditQueueView, ResearchAuditStatusView

AUDIT_VERSION = LOCAL_REPORT_AUDIT_VERSION
LEASE_MINUTES = 15
RETRY_DELAYS_SECONDS = (60, 300, 1_800)


def queue_research_report_audits(
    session: Session,
    *,
    mode: Literal["audit_only", "refresh_and_audit"] = "audit_only",
    limit: int = 100,
    inquiry_ids: tuple[int, ...] | None = None,
) -> ResearchAuditQueueView:
    """Idempotently queue one frozen-source audit job per completed report."""
    statement = select(ResearchInquiry).where(
        ResearchInquiry.status == "completed",
        ResearchInquiry.result.is_not(None),
    )
    requested_ids = tuple(dict.fromkeys(inquiry_ids or ()))
    if requested_ids:
        statement = statement.where(ResearchInquiry.id.in_(requested_ids))
    rows = list(
        session.scalars(
            statement.order_by(ResearchInquiry.created_at, ResearchInquiry.id).limit(limit)
        )
    )
    queued = 0
    existing = 0
    already_audited = 0
    now = datetime.now(UTC)
    for priority, row in enumerate(rows, start=1):
        current_audit = (row.evidence_snapshot or {}).get("local_report_audit")
        if (
            mode == "audit_only"
            and isinstance(current_audit, dict)
            and current_audit.get("audit_version") == AUDIT_VERSION
        ):
            already_audited += 1
            continue
        fingerprint = research_source_fingerprint(row)
        duplicate = session.scalar(
            select(ResearchReportAuditJob.id).where(
                ResearchReportAuditJob.inquiry_id == row.id,
                ResearchReportAuditJob.audit_version == AUDIT_VERSION,
                ResearchReportAuditJob.source_fingerprint == fingerprint,
            )
        )
        if duplicate is not None:
            existing += 1
            continue
        session.add(
            ResearchReportAuditJob(
                inquiry_id=row.id,
                audit_version=AUDIT_VERSION,
                mode=mode,
                status="queued",
                priority=priority,
                attempt_count=0,
                max_attempts=3,
                available_at=now,
                source_fingerprint=fingerprint,
            )
        )
        queued += 1
    session.commit()
    return ResearchAuditQueueView(
        scanned_reports=len(rows),
        queued_jobs=queued,
        existing_jobs=existing,
        already_audited=already_audited,
        mode=mode,
    )


def research_audit_status(session: Session) -> ResearchAuditStatusView:
    counts = {
        status: count
        for status, count in session.execute(
            select(ResearchReportAuditJob.status, func.count()).group_by(
                ResearchReportAuditJob.status
            )
        )
    }
    latest = session.scalar(
        select(func.max(ResearchReportAuditJob.completed_at)).where(
            ResearchReportAuditJob.status == "completed"
        )
    )
    return ResearchAuditStatusView(
        queued=int(counts.get("queued", 0)),
        running=int(counts.get("running", 0)),
        completed=int(counts.get("completed", 0)),
        failed=int(counts.get("failed", 0)),
        superseded=int(counts.get("superseded", 0)),
        latest_completed_at=latest,
    )


def research_source_fingerprint(row: ResearchInquiry) -> str:
    payload = {
        "result": row.result,
        "evidence_snapshot": row.evidence_snapshot,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ResearchAuditWorker:
    """Lease and apply deterministic audits without using the model runtime."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        worker_id: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"

    def recover_expired_jobs(self) -> int:
        now = datetime.now(UTC)
        with self._session_factory() as session:
            jobs = list(
                session.scalars(
                    select(ResearchReportAuditJob).where(
                        ResearchReportAuditJob.status == "running",
                        ResearchReportAuditJob.lease_expires_at < now,
                    )
                )
            )
            for job in jobs:
                job.worker_id = None
                job.lease_expires_at = None
                if job.attempt_count >= job.max_attempts:
                    job.status = "failed"
                    job.completed_at = now
                    job.error_message = "audit lease expired after maximum attempts"
                else:
                    job.status = "queued"
                    job.available_at = now
                    job.error_message = "recovered expired audit lease"
            session.commit()
            return len(jobs)

    def run_next(self) -> bool:
        job_id = self._claim_next_job()
        if job_id is None:
            return False
        try:
            self._process_job(job_id)
        except Exception as exc:
            self._retry_or_fail(job_id, exc)
        return True

    def run_forever(self, *, poll_seconds: float = 5) -> None:
        if poll_seconds < 0.5:
            raise ValueError("poll_seconds must be at least 0.5")
        try:
            while True:
                self.recover_expired_jobs()
                if not self.run_next():
                    time.sleep(poll_seconds)
        except KeyboardInterrupt:
            return

    def _claim_next_job(self) -> int | None:
        now = datetime.now(UTC)
        with self._session_factory() as session:
            job = session.scalar(
                select(ResearchReportAuditJob)
                .where(
                    ResearchReportAuditJob.status == "queued",
                    ResearchReportAuditJob.available_at <= now,
                )
                .order_by(
                    ResearchReportAuditJob.priority,
                    ResearchReportAuditJob.created_at,
                )
                .with_for_update(skip_locked=True)
            )
            if job is None:
                return None
            job.status = "running"
            job.attempt_count += 1
            job.worker_id = self._worker_id
            job.started_at = job.started_at or now
            job.lease_expires_at = now + timedelta(minutes=LEASE_MINUTES)
            job.error_message = None
            session.commit()
            return job.id

    def _process_job(self, job_id: int) -> None:
        with self._session_factory() as session:
            job = session.get(ResearchReportAuditJob, job_id)
            if job is None:
                return
            row = session.get(ResearchInquiry, job.inquiry_id)
            now = datetime.now(UTC)
            if row is None or row.status != "completed" or row.result is None:
                job.status = "superseded"
                job.error_message = "research report is no longer auditable"
                job.completed_at = now
                job.lease_expires_at = None
                session.commit()
                return
            if research_source_fingerprint(row) != job.source_fingerprint:
                job.status = "superseded"
                job.error_message = "research report changed after this audit was queued"
                job.completed_at = now
                job.lease_expires_at = None
                session.commit()
                return
            job.before_result = _json_copy(row.result)
            job.before_evidence_snapshot = _json_copy(row.evidence_snapshot)
            audited = audit_local_report(
                session,
                inquiry_id=row.id,
                refresh_equity_evidence=job.mode == "refresh_and_audit",
                refresh_document_evidence=job.mode == "refresh_and_audit",
            )
            session.flush()
            session.refresh(row, attribute_names=["result", "evidence_snapshot"])
            audit = audited.evidence_snapshot.get("local_report_audit")
            job.audit_summary = audit if isinstance(audit, dict) else {}
            job.output_fingerprint = research_source_fingerprint(row)
            job.status = "completed"
            job.completed_at = now
            job.lease_expires_at = None
            job.worker_id = self._worker_id
            session.commit()

    def _retry_or_fail(self, job_id: int, exc: Exception) -> None:
        with self._session_factory() as session:
            job = session.get(ResearchReportAuditJob, job_id)
            if job is None:
                return
            now = datetime.now(UTC)
            job.worker_id = None
            job.lease_expires_at = None
            job.error_message = f"{type(exc).__name__}: {str(exc)[:1_900]}"
            if job.attempt_count >= job.max_attempts:
                job.status = "failed"
                job.completed_at = now
            else:
                delay_index = min(job.attempt_count - 1, len(RETRY_DELAYS_SECONDS) - 1)
                job.status = "queued"
                job.available_at = now + timedelta(seconds=RETRY_DELAYS_SECONDS[delay_index])
            session.commit()


def _json_copy(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return json.loads(json.dumps(value, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-research-audit-worker")
    parser.add_argument("--poll-seconds", type=float, default=5)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    ResearchAuditWorker(get_session_factory()).run_forever(poll_seconds=args.poll_seconds)


if __name__ == "__main__":
    main()
