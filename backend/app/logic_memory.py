"""Qualified logic memory, external-data quarantine, and training export."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Literal, cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    ExternalTrainingExample,
    LogicChainHypothesis,
)
from app.schemas.logic_chains import (
    ExternalTrainingExampleImport,
    ExternalTrainingExampleList,
    ExternalTrainingExampleView,
    ExternalTrainingImportRequest,
    ExternalTrainingImportResponse,
    TrainingDatasetExample,
    TrainingDatasetResponse,
    VerifiedLogicMemoryResponse,
    VerifiedLogicMemoryView,
)

MEMORY_QUALIFICATION_RULE = (
    "Human accepted/revised-accepted; validator conclusion is "
    "mechanism_supported_not_causal; recalculated confidence >= 0.55; premise, "
    "outcome and mechanism gates passed; at least two source-backed evidence facts; "
    "human review occurred after the retained validation."
)
TRAINING_SYSTEM_MESSAGE = (
    "Produce an auditable, non-causal logic-chain analysis. Separate reported facts, "
    "measured observations, inferred mechanisms, counterevidence and missing evidence."
)


class ExternalTrainingExampleNotFoundError(LookupError):
    """Raised when an external training example does not exist."""


def qualified_logic_memories(
    session: Session,
    *,
    focus: str = "",
    limit: int = 100,
) -> list[VerifiedLogicMemoryView]:
    """Return only human-approved chains that pass strict evidence gates."""
    rows = list(
        session.scalars(
            select(LogicChainHypothesis)
            .where(LogicChainHypothesis.status.in_(("accepted", "revised_accepted")))
            .order_by(LogicChainHypothesis.decided_at.desc(), LogicChainHypothesis.id.desc())
            .limit(max(limit * 8, 100))
        )
    )
    focus_tokens = _tokens(focus)
    retained: list[tuple[float, VerifiedLogicMemoryView]] = []
    for row in rows:
        memory = _qualified_memory(row)
        if memory is None:
            continue
        relevance = _similarity(focus_tokens, _tokens(_memory_text(memory))) if focus_tokens else 0
        retained.append((relevance, memory))
    retained.sort(
        key=lambda item: (item[0], item[1].quality_score, item[1].reviewed_at),
        reverse=True,
    )
    return [item[1] for item in retained[:limit]]


def list_verified_logic_memories(
    session: Session,
    *,
    focus: str = "",
    limit: int = 100,
) -> VerifiedLogicMemoryResponse:
    memories = qualified_logic_memories(session, focus=focus, limit=limit)
    return VerifiedLogicMemoryResponse(
        memory_count=len(memories),
        memories=memories,
        qualification_rule=MEMORY_QUALIFICATION_RULE,
    )


def import_external_training_examples(
    session: Session,
    request: ExternalTrainingImportRequest,
) -> ExternalTrainingImportResponse:
    """Idempotently stage licensed external examples; never auto-approve them."""
    fingerprints = {_external_fingerprint(example) for example in request.examples}
    existing = set(
        session.scalars(
            select(ExternalTrainingExample.fingerprint).where(
                ExternalTrainingExample.fingerprint.in_(fingerprints)
            )
        )
    )
    imported = 0
    duplicates = 0
    for example in request.examples:
        fingerprint = _external_fingerprint(example)
        if fingerprint in existing:
            duplicates += 1
            continue
        evidence = [item.model_dump(mode="json") for item in example.evidence]
        session.add(
            ExternalTrainingExample(
                fingerprint=fingerprint,
                title=example.title.strip(),
                instruction=example.instruction.strip(),
                input_context=example.input_context.strip(),
                ideal_response=example.ideal_response.strip(),
                evidence=json.dumps(evidence, ensure_ascii=False),
                source_name=example.source_name.strip(),
                source_url=example.source_url.strip(),
                license_name=example.license_name.strip(),
                status="pending",
                quality_score=_automatic_external_quality(example),
            )
        )
        existing.add(fingerprint)
        imported += 1
    session.flush()
    pending = int(
        session.scalar(
            select(func.count())
            .select_from(ExternalTrainingExample)
            .where(ExternalTrainingExample.status == "pending")
        )
        or 0
    )
    return ExternalTrainingImportResponse(
        imported_count=imported,
        duplicate_count=duplicates,
        pending_count=pending,
    )


def list_external_training_examples(
    session: Session,
    *,
    limit: int = 500,
) -> ExternalTrainingExampleList:
    rows = list(
        session.scalars(
            select(ExternalTrainingExample)
            .order_by(ExternalTrainingExample.created_at.desc())
            .limit(limit)
        )
    )
    counts = {
        status: int(
            session.scalar(
                select(func.count())
                .select_from(ExternalTrainingExample)
                .where(ExternalTrainingExample.status == status)
            )
            or 0
        )
        for status in ("pending", "approved", "rejected")
    }
    return ExternalTrainingExampleList(
        example_count=sum(counts.values()),
        pending_count=counts["pending"],
        approved_count=counts["approved"],
        rejected_count=counts["rejected"],
        examples=[_external_view(row) for row in rows],
    )


def review_external_training_example(
    session: Session,
    *,
    example_id: int,
    status: Literal["approved", "rejected"],
    quality_score: float,
    review_note: str,
) -> ExternalTrainingExampleView:
    """Apply the mandatory human gate for external data."""
    row = session.get(ExternalTrainingExample, example_id)
    if row is None:
        raise ExternalTrainingExampleNotFoundError(str(example_id))
    row.status = status
    row.quality_score = quality_score
    row.review_note = review_note.strip()
    row.decided_at = datetime.now(UTC)
    session.flush()
    return _external_view(row)


def build_training_dataset(
    session: Session,
    *,
    limit: int = 2_000,
) -> TrainingDatasetResponse:
    """Export qualified internal memory plus approved external examples."""
    memories = qualified_logic_memories(session, limit=limit)
    examples: list[TrainingDatasetExample] = [
        _memory_training_example(memory) for memory in memories
    ]
    remaining = max(limit - len(examples), 0)
    external_rows = list(
        session.scalars(
            select(ExternalTrainingExample)
            .where(ExternalTrainingExample.status == "approved")
            .order_by(
                ExternalTrainingExample.quality_score.desc(),
                ExternalTrainingExample.decided_at.desc(),
            )
            .limit(remaining)
        )
    )
    examples.extend(_external_training_example(row) for row in external_rows)
    return TrainingDatasetResponse(
        example_count=len(examples),
        internal_verified_count=len(memories),
        approved_external_count=len(external_rows),
        examples=examples,
    )


def _qualified_memory(row: LogicChainHypothesis) -> VerifiedLogicMemoryView | None:
    try:
        analysis = json.loads(row.steps)
    except (TypeError, json.JSONDecodeError):
        return None
    validation = analysis.get("causal_validation") if isinstance(analysis, dict) else None
    if not isinstance(validation, dict):
        return None
    if validation.get("conclusion") != "mechanism_supported_not_causal":
        return None
    validated_at = _parsed_datetime(validation.get("validated_at"))
    reviewed_at = row.decided_at or row.updated_at
    if validated_at is None or _aware(reviewed_at) < validated_at:
        return None
    confidence = _score(validation.get("recalculated_confidence"))
    if confidence < 0.55:
        return None
    facts = validation.get("evidence_facts")
    checks = validation.get("checks")
    steps = analysis.get("steps")
    if not isinstance(facts, list) or len(facts) < 2:
        return None
    if not isinstance(steps, list) or len(steps) < 3:
        return None
    if not isinstance(checks, list):
        return None
    statuses = {
        str(check.get("check_key")): str(check.get("status"))
        for check in checks
        if isinstance(check, dict)
    }
    if any(
        statuses.get(key) != "passed"
        for key in ("premise_reported", "outcome_time_window", "mechanism_evidence")
    ):
        return None
    evidence_coverage = _score(analysis.get("evidence_coverage_score"))
    passed_ratio = sum(value == "passed" for value in statuses.values()) / max(
        len(statuses), 1
    )
    quality = round(
        confidence * 0.45
        + min(evidence_coverage, 1) * 0.25
        + min(len(facts) / 6, 1) * 0.15
        + passed_ratio * 0.15,
        3,
    )
    return VerifiedLogicMemoryView(
        hypothesis_id=row.id,
        title=row.title,
        status=cast(Literal["accepted", "revised_accepted"], row.status),
        conclusion="mechanism_supported_not_causal",
        validated_confidence=confidence,
        quality_score=quality,
        steps=steps[:8],
        evidence_facts=facts[:20],
        counterevidence=[str(item)[:1_000] for item in analysis.get("counterevidence", [])[:8]],
        summary_en=str(validation.get("summary_en") or row.rationale)[:2_000],
        summary_zh=str(validation.get("summary_zh") or row.rationale)[:2_000],
        reviewed_at=reviewed_at,
        model_name=row.model_name,
        prompt_version=row.prompt_version,
    )


def _memory_training_example(memory: VerifiedLogicMemoryView) -> TrainingDatasetExample:
    ideal = {
        "title": memory.title,
        "steps": memory.steps,
        "counterevidence": memory.counterevidence,
        "conclusion": memory.conclusion,
        "confidence": memory.validated_confidence,
        "summary_en": memory.summary_en,
        "summary_zh": memory.summary_zh,
    }
    return TrainingDatasetExample(
        messages=[
            {"role": "system", "content": TRAINING_SYSTEM_MESSAGE},
            {
                "role": "user",
                "content": json.dumps(
                    {"evidence_facts": memory.evidence_facts}, ensure_ascii=False
                ),
            },
            {"role": "assistant", "content": json.dumps(ideal, ensure_ascii=False)},
        ],
        metadata={
            "origin": "verified_logic_memory",
            "hypothesis_id": memory.hypothesis_id,
            "quality_score": memory.quality_score,
            "reviewed_at": memory.reviewed_at.isoformat(),
            "causality_confirmed": False,
        },
    )


def _external_training_example(row: ExternalTrainingExample) -> TrainingDatasetExample:
    return TrainingDatasetExample(
        messages=[
            {"role": "system", "content": TRAINING_SYSTEM_MESSAGE},
            {
                "role": "user",
                "content": f"{row.instruction}\n\nContext:\n{row.input_context}",
            },
            {"role": "assistant", "content": row.ideal_response},
        ],
        metadata={
            "origin": "approved_external",
            "external_example_id": row.id,
            "source_name": row.source_name,
            "source_url": row.source_url,
            "license": row.license_name,
            "evidence": json.loads(row.evidence),
            "quality_score": float(row.quality_score),
            "reviewed_at": row.decided_at.isoformat() if row.decided_at else None,
        },
    )


def _external_view(row: ExternalTrainingExample) -> ExternalTrainingExampleView:
    evidence = json.loads(row.evidence)
    return ExternalTrainingExampleView(
        id=row.id,
        title=row.title,
        source_name=row.source_name,
        source_url=row.source_url,
        license_name=row.license_name,
        status=cast(Literal["pending", "approved", "rejected"], row.status),
        quality_score=float(row.quality_score),
        evidence_count=len(evidence) if isinstance(evidence, list) else 0,
        review_note=row.review_note,
        created_at=row.created_at,
        decided_at=row.decided_at,
    )


def _external_fingerprint(example: ExternalTrainingExampleImport) -> str:
    canonical = json.dumps(example.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _automatic_external_quality(example: ExternalTrainingExampleImport) -> float:
    dated = sum(bool(item.observed_at) for item in example.evidence)
    source_diversity = len({item.source_url for item in example.evidence})
    return round(
        min(len(example.evidence) / 6, 1) * 0.25
        + min(dated / 3, 1) * 0.2
        + min(source_diversity / 3, 1) * 0.2
        + (0.2 if len(example.ideal_response) >= 300 else 0.1)
        + 0.1,
        3,
    )


def _score(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return 0
    try:
        return min(max(float(value), 0), 1)
    except (TypeError, ValueError):
        return 0


def _parsed_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return _aware(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _tokens(value: str) -> set[str]:
    normalized = value.casefold()
    words = set(re.findall(r"[a-z0-9][a-z0-9_-]{2,}", normalized))
    cjk = re.findall(r"[\u3400-\u9fff]+", normalized)
    return words | {
        run[index : index + 2]
        for run in cjk
        for index in range(max(0, len(run) - 1))
    }


def _memory_text(memory: VerifiedLogicMemoryView) -> str:
    return " ".join(
        [
            memory.title,
            memory.summary_en,
            memory.summary_zh,
            json.dumps(memory.steps, ensure_ascii=False),
        ]
    )


def _similarity(left: set[str], right: set[str]) -> float:
    return len(left & right) / max(len(left | right), 1)
