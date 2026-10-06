"""Auditable status for AI chains, model changes, and actual retraining."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import Settings, get_settings
from app.db.enums import ClusterJobStatus
from app.db.models import (
    ClusterJob,
    ExternalTrainingExample,
    LogicChainHypothesis,
    LogicChainReviewSignal,
    ResearchInquiry,
)
from app.logic_memory import qualified_logic_memories
from app.schemas.research import (
    AIChainInventoryView,
    AIModelStateView,
    AIStatusView,
    AITrainingStateView,
)


def build_ai_status(
    session: Session,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> AIStatusView:
    """Build a status snapshot without treating feedback as completed training."""
    runtime = settings or get_settings()
    generated_at = now or datetime.now(UTC)
    chain_rows = list(
        session.execute(
            select(
                LogicChainHypothesis.created_at,
                LogicChainHypothesis.updated_at,
                LogicChainHypothesis.status,
                LogicChainHypothesis.steps,
                LogicChainHypothesis.model_name,
                LogicChainHypothesis.prompt_version,
            ).order_by(LogicChainHypothesis.created_at.desc())
        )
    )
    signal_count = int(
        session.scalar(select(func.count()).select_from(LogicChainReviewSignal)) or 0
    )
    verified_memory_count = len(qualified_logic_memories(session, limit=10_000))
    external_pending_count = int(
        session.scalar(
            select(func.count())
            .select_from(ExternalTrainingExample)
            .where(ExternalTrainingExample.status == "pending")
        )
        or 0
    )
    external_approved_count = int(
        session.scalar(
            select(func.count())
            .select_from(ExternalTrainingExample)
            .where(ExternalTrainingExample.status == "approved")
        )
        or 0
    )
    training = _training_state(
        runtime,
        signal_count=signal_count,
        verified_memory_count=verified_memory_count,
        external_pending_count=external_pending_count,
        external_approved_count=external_approved_count,
    )

    validated_count = 0
    enhanced_count = 0
    latest_validation_at: datetime | None = None
    for row in chain_rows:
        validation = _causal_validation(row.steps)
        if validation is None:
            continue
        validated_count += 1
        if validation.get("evidence_facts") or validation.get("evidence_sources"):
            enhanced_count += 1
        validated_at = _parse_datetime(validation.get("validated_at"))
        if validated_at is not None and (
            latest_validation_at is None or validated_at > latest_validation_at
        ):
            latest_validation_at = validated_at

    latest_research = session.execute(
        select(
            ResearchInquiry.created_at,
            ResearchInquiry.evidence_snapshot,
        )
        .where(ResearchInquiry.status == "completed")
        .order_by(ResearchInquiry.created_at.desc())
        .limit(1)
    ).first()
    research_runs = int(
        session.scalar(
            select(func.count())
            .select_from(ResearchInquiry)
            .where(ResearchInquiry.status == "completed")
        )
        or 0
    )
    latest_research_at = latest_research.created_at if latest_research else None
    latest_evidence_at = (
        _parse_datetime(latest_research.evidence_snapshot.get("generated_at"))
        if latest_research
        else None
    )

    completed_jobs = list(
        session.scalars(
            select(ClusterJob)
            .where(
                ClusterJob.status == ClusterJobStatus.COMPLETED,
                ClusterJob.result.is_not(None),
            )
            .order_by(
                ClusterJob.completed_at.desc().nulls_last(),
                ClusterJob.id.desc(),
            )
            .limit(50)
        )
    )
    completed_job_ids = [job.id for job in completed_jobs]
    logic_job_ids = set(
        session.scalars(
            select(LogicChainHypothesis.cluster_job_id)
            .where(LogicChainHypothesis.cluster_job_id.in_(completed_job_ids))
            .distinct()
        )
    )
    latest_logic_job_id = session.scalar(
        select(func.max(LogicChainHypothesis.cluster_job_id))
    )

    def logic_state(job: ClusterJob) -> dict[str, Any]:
        value = dict(job.result or {}).get("logic_generation")
        return value if isinstance(value, dict) else {}

    pending_logic_jobs = [
        job
        for job in completed_jobs
        if job.id not in logic_job_ids
        and logic_state(job).get("status") != "completed"
    ]
    latest_completed_job = completed_jobs[0] if completed_jobs else None
    latest_refresh_state: Literal["current", "pending", "retrying"] = "current"
    if latest_completed_job is not None and latest_completed_job in pending_logic_jobs:
        latest_refresh_state = (
            "retrying"
            if logic_state(latest_completed_job).get("status") == "failed"
            else "pending"
        )

    trained_at = training.trained_at
    since_training = sum(
        1
        for row in chain_rows
        if trained_at is None or _aware(row.created_at) > trained_at
    )
    recent_boundary = generated_at - timedelta(hours=24)
    chains = AIChainInventoryView(
        total=len(chain_rows),
        new_24h=sum(
            1 for row in chain_rows if _aware(row.created_at) >= recent_boundary
        ),
        pending_review=sum(
            1 for row in chain_rows if row.status in {"suggested", "deferred"}
        ),
        validated=validated_count,
        enhanced_evidence_validated=enhanced_count,
        since_last_training=since_training,
        research_runs=research_runs,
        latest_completed_cluster_job_id=(
            latest_completed_job.id if latest_completed_job is not None else None
        ),
        latest_logic_cluster_job_id=(
            int(latest_logic_job_id) if latest_logic_job_id is not None else None
        ),
        logic_refresh_pending_jobs=len(pending_logic_jobs),
        logic_refresh_state=latest_refresh_state,
        latest_chain_at=chain_rows[0].created_at if chain_rows else None,
        latest_validation_at=latest_validation_at,
        latest_research_at=latest_research_at,
        latest_evidence_snapshot_at=latest_evidence_at,
    )
    return AIStatusView(
        generated_at=generated_at,
        chains=chains,
        model=_model_state(runtime, chain_rows),
        training=training,
    )


def _model_state(settings: Settings, rows: list[Any]) -> AIModelStateView:
    runtime_model = f"{settings.llm_provider}:{settings.llm_model}"
    if not rows:
        return AIModelStateView(
            app_version=__version__,
            runtime_model=runtime_model,
            state="no_chain_history",
        )

    versions: list[tuple[str, str, datetime]] = []
    for row in rows:
        signature = (row.model_name, row.prompt_version)
        if any((model, prompt) == signature for model, prompt, _ in versions):
            continue
        versions.append((row.model_name, row.prompt_version, row.created_at))
    current_model, current_prompt, _ = versions[0]
    previous_model = versions[1][0] if len(versions) > 1 else None
    previous_prompt = versions[1][1] if len(versions) > 1 else None
    first_seen = min(
        row.created_at
        for row in rows
        if row.model_name == current_model and row.prompt_version == current_prompt
    )
    state: Literal[
        "current",
        "upgrade_detected",
        "configured_change_pending_run",
        "no_chain_history",
    ]
    if current_model != runtime_model:
        state = "configured_change_pending_run"
    elif len(versions) > 1:
        state = "upgrade_detected"
    else:
        state = "current"
    return AIModelStateView(
        app_version=__version__,
        runtime_model=runtime_model,
        last_chain_model=current_model,
        previous_chain_model=previous_model,
        prompt_version=current_prompt,
        previous_prompt_version=previous_prompt,
        state=state,
        current_version_first_seen_at=first_seen,
    )


def _training_state(
    settings: Settings,
    *,
    signal_count: int,
    verified_memory_count: int = 0,
    external_pending_count: int = 0,
    external_approved_count: int = 0,
) -> AITrainingStateView:
    training_dataset_ready_count = verified_memory_count + external_approved_count
    manifest_path = settings.llm_training_manifest_path
    if manifest_path is None:
        state: Literal["signals_collected", "no_signals"] = (
            "signals_collected" if signal_count else "no_signals"
        )
        return AITrainingStateView(
            state=state,
            review_signal_count=signal_count,
            signal_count_used=0,
            pending_signal_count=signal_count,
            retraining_confirmed=False,
            manifest_configured=False,
            verified_memory_count=verified_memory_count,
            external_pending_count=external_pending_count,
            external_approved_count=external_approved_count,
            training_dataset_ready_count=training_dataset_ready_count,
            explanation=(
                "Review signals are stored, but no training artifact manifest was detected."
                if signal_count
                else "No review signals or training artifact manifest were detected."
            ),
        )
    manifest = _read_training_manifest(manifest_path)
    trained_at = _parse_datetime(manifest.get("trained_at")) if manifest else None
    trained_model = _clean_manifest_text(manifest.get("model_name")) if manifest else None
    run_id = _clean_manifest_text(manifest.get("training_run_id")) if manifest else None
    if manifest is None or trained_at is None or trained_model is None or run_id is None:
        return AITrainingStateView(
            state="manifest_invalid",
            review_signal_count=signal_count,
            signal_count_used=0,
            pending_signal_count=signal_count,
            retraining_confirmed=False,
            manifest_configured=True,
            verified_memory_count=verified_memory_count,
            external_pending_count=external_pending_count,
            external_approved_count=external_approved_count,
            training_dataset_ready_count=training_dataset_ready_count,
            explanation="The configured training manifest is missing or incomplete.",
        )
    used = _manifest_non_negative_int(manifest.get("training_signal_count"))
    return AITrainingStateView(
        state="retraining_confirmed",
        review_signal_count=signal_count,
        signal_count_used=used,
        pending_signal_count=max(signal_count - used, 0),
        retraining_confirmed=True,
        manifest_configured=True,
        verified_memory_count=verified_memory_count,
        external_pending_count=external_pending_count,
        external_approved_count=external_approved_count,
        training_dataset_ready_count=training_dataset_ready_count,
        training_run_id=run_id,
        trained_model=trained_model,
        base_model=_clean_manifest_text(manifest.get("base_model")),
        trained_at=trained_at,
        explanation="Retraining is confirmed by the configured training artifact manifest.",
    )


def _read_training_manifest(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _causal_validation(raw_steps: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw_steps)
    except (TypeError, json.JSONDecodeError):
        return None
    validation = payload.get("causal_validation") if isinstance(payload, dict) else None
    return validation if isinstance(validation, dict) else None


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _aware(parsed)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _clean_manifest_text(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()[:255]


def _manifest_non_negative_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if not isinstance(value, (int, float, str)):
        return 0
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0
