"""Durable earnings preparation without invoking current-data research workers.

Only metadata is stored in SQL; full document text remains in the archive.
The production dispatcher is intentionally not enabled: packet verification must
be repeated at dispatch and the model adapter must accept only that packet.
"""

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.earnings_task import EarningsResearchTask
from app.earnings_evidence_packet import (
    EvidenceDocument,
    EvidencePacketError,
    build_evidence_packet,
)
from app.earnings_phase_manifest import (
    EarningsEvent,
    EvidenceReference,
    ManifestVersions,
    Phase,
    PhaseCutoffs,
    build_earnings_phase_manifest,
)


def enqueue_earnings_event(
    session: Session,
    *,
    event: EarningsEvent,
    cutoffs: PhaseCutoffs,
    versions: ManifestVersions,
    evidence: Sequence[EvidenceReference],
    documents: Mapping[str, EvidenceDocument],
    release_source_url: str,
    required_evidence_refs: Mapping[Phase, Sequence[str]] | None = None,
    now: datetime | None = None,
) -> list[EarningsResearchTask]:
    """Stage all three phases atomically; caller owns commit/rollback.

    Each evidence ID must identify an immutable archive version. Missing bodies
    are recorded as blocked; they do not start model work. A retry may promote a
    blocked task after missing archive contents arrive; manifest metadata is
    never rewritten. Cancelled tasks never silently requeue.
    """
    clock = now or datetime.now(UTC)
    manifests = build_earnings_phase_manifest(
        event=event,
        cutoffs=cutoffs,
        versions=versions,
        evidence=evidence,
        now=clock,
        required_evidence_refs=required_evidence_refs,
    )
    results = []
    for manifest in manifests:
        reasons = list(manifest.reasons)
        packet_bytes = None
        try:
            source = urlsplit(release_source_url)
            source_valid = (
                source.scheme == "https"
                and bool(source.hostname)
                and source.username is None
                and source.password is None
                and not any(char.isspace() for char in release_source_url)
            )
        except (ValueError, TypeError, AttributeError):
            source_valid = False
        if not source_valid:
            reasons.append("release_source_required")
        if manifest.status == "ready":
            # Deliberately select only this phase's references; no latest-pack fallback.
            selected = {
                ref.id: documents[ref.id] for ref in manifest.evidence if ref.id in documents
            }
            try:
                packet = build_evidence_packet(manifest, selected)
                packet_bytes = packet.total_utf8_bytes
            except EvidencePacketError as exc:
                reasons.append(str(exc))
        readiness = {
            "reasons": sorted(set(reasons)),
            "evidence_count": len(manifest.evidence),
            "verified_utf8_bytes": packet_bytes,
            "release_source_url": release_source_url if source_valid else None,
            "checked_at": clock.isoformat(),
            "execution_permitted": False,
            "dispatch_blockers": ["isolated_model_dispatcher_not_enabled"],
        }
        status = "blocked" if reasons else "awaiting_dispatch"
        existing = session.scalar(
            select(EarningsResearchTask)
            .where(
                EarningsResearchTask.fingerprint == manifest.fingerprint,
            )
            .with_for_update()
        )
        if existing is None:
            candidate = EarningsResearchTask(
                fingerprint=manifest.fingerprint,
                ticker=manifest.ticker,
                fiscal_period=manifest.fiscal_period,
                phase=manifest.phase,
                manifest=asdict(manifest),
                readiness=readiness,
                status=status,
            )
            try:
                with session.begin_nested():
                    session.add(candidate)
                    session.flush()
                existing = candidate
            except IntegrityError:
                # A concurrent preparer inserted the same immutable input.
                existing = session.scalar(
                    select(EarningsResearchTask)
                    .where(
                        EarningsResearchTask.fingerprint == manifest.fingerprint,
                    )
                    .with_for_update()
                )
                if existing is None:
                    raise
        if existing.status != "cancelled":
            existing.readiness = readiness
            existing.status = status
        results.append(existing)
    session.flush()
    return results


def cancel_earnings_task(session: Session, task_id: int) -> bool:
    """Cancel an unstarted staged item; never kill processes or erase data."""
    result = session.execute(
        update(EarningsResearchTask)
        .where(
            EarningsResearchTask.id == task_id,
            EarningsResearchTask.status.in_(("blocked", "awaiting_dispatch")),
        )
        .values(status="cancelled")
    )
    return result.rowcount == 1


def earnings_queue_summary(session: Session, *, limit: int = 50) -> dict[str, Any]:
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    counts = dict(
        session.execute(
            select(EarningsResearchTask.status, func.count()).group_by(
                EarningsResearchTask.status,
            )
        ).all()
    )
    tasks = session.scalars(
        select(EarningsResearchTask)
        .order_by(
            EarningsResearchTask.id.desc(),
        )
        .limit(limit)
    ).all()
    return {
        "total": sum(counts.values()),
        "counts": counts,
        "execution_permitted": False,
        "items": [
            {
                "id": task.id,
                "ticker": task.ticker,
                "period": task.fiscal_period,
                "phase": task.phase,
                "status": task.status,
                "fingerprint": task.fingerprint,
                "readiness": task.readiness,
            }
            for task in tasks
        ],
    }
