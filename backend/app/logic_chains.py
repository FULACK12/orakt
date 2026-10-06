"""Local-AI multi-step hypotheses with a human-reviewed training trail."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

import httpx
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.causal_validation import (
    allowed_evidence_refs,
    build_rule_validation,
    call_validator_agent,
    merge_agent_validation,
)
from app.core.config import Settings, get_settings
from app.core.text import repair_common_mojibake
from app.db.enums import ClusterJobStatus
from app.db.models import (
    ClusterJob,
    CountryProfile,
    Document,
    EconomicIndicator,
    EconomicObservation,
    LogicChainHypothesis,
    LogicChainReviewSignal,
    MarketObservation,
    MarketSeries,
)
from app.evidence_quality import document_evidence_tier
from app.evidence_sources import fetch_validation_evidence
from app.extractors.llm import UNSUPPORTED_GRAMMAR_SCHEMA_KEYS
from app.logic_memory import qualified_logic_memories
from app.market_history import build_cycle_snapshot
from app.schemas.cluster_jobs import ClusterJobResult
from app.schemas.clusters import ClusterCandidate
from app.schemas.logic_chains import (
    CausalHistoricalCaseView,
    CausalValidationResult,
    LogicChainGenerationResponse,
    LogicChainHypothesisView,
    LogicChainResponse,
    LogicChainReviewSignalView,
    LogicChainStatus,
    LogicChainTrainingSignalsResponse,
    ModelLogicHypothesis,
    ModelLogicHypothesisBatch,
)
from app.schemas.research import ChatGPTResearchReview

PROMPT_VERSION = "logic-chain-v3-financial-evidence"
ECONOMIC_CONTEXT_CODES = {
    "FP.CPI.TOTL.ZG",
    "NY.GDP.MKTP.CD",
    "NY.GDP.MKTP.KD.ZG",
    "GC.DOD.TOTL.GD.ZS",
    "BN.CAB.XOKA.GD.ZS",
    "FI.RES.TOTL.CD",
    "PA.NUS.FCRF",
    "NV.AGR.TOTL.CD",
    "NV.IND.TOTL.CD",
    "NV.IND.MANF.CD",
    "AG.PRD.CROP.XD",
    "AG.PRD.FOOD.XD",
}
MARKET_CONTEXT_SYMBOLS = (
    "USD/JPY",
    "EUR/USD",
    "XAU/USD",
    "WTI/USD",
    "US2Y",
    "US10Y",
    "SPY",
    "QQQ",
    "EWJ",
)
LOGIC_SIGNAL_TERMS = (
    "bank",
    "rate",
    "inflation",
    "liquidity",
    "credit",
    "bond",
    "currency",
    "market",
    "stock",
    "equity",
    "trade",
    "tariff",
    "sanction",
    "export",
    "import",
    "supply",
    "demand",
    "production",
    "oil",
    "gas",
    "shipping",
    "port",
    "closure",
    "policy",
    "conflict",
    "央行",
    "利率",
    "通胀",
    "流动性",
    "债券",
    "汇率",
    "股市",
    "关税",
    "制裁",
    "出口",
    "进口",
    "供应",
    "需求",
    "生产",
    "石油",
    "天然气",
    "航运",
    "港口",
    "政策",
    "冲突",
    "banque centrale",
    "banco central",
    "zentralbank",
    "inflación",
    "pétrole",
    "marché",
    "mercado",
    "البنك",
    "الفائدة",
    "التضخم",
    "النفط",
    "السوق",
    "عقوبات",
)
SYSTEM_PROMPT = """\
You propose a small number of professional, reviewable news logic-chain
hypotheses using reported events and the supplied structured evidence.
Return JSON only and match the supplied schema exactly.
Use only the supplied candidate IDs and document IDs. Never invent an event.
Treat headline_only candidates as discovery leads. They cannot independently
verify a premise, outcome or transmission mechanism and must lower confidence.
Each chain must have 3-6 steps: reported premise, at least one explicitly
inferred mechanism, and a possible reported outcome. Use economic_context and
market_observation steps only when supplied evidence supports them. Every step
needs its own confidence, relevance and evidence_refs. Inference is not evidence.
For monetary policy, distinguish the policy decision from repricing of the
expected rate path, sovereign yields, valuation and asset-price responses.
Use at least five steps for a monetary-policy-to-market chain when the supplied
evidence supports them: decision, communications, path repricing, yields, and
valuation/market response. A non-empty counterevidence list is mandatory.
Consider reserves, debt, exchange rates and plausible policy reactions, but do
not state that a government will sell reserves or bonds without reported proof.
Consider commodity and supply-chain transmission such as a shipping chokepoint
to energy prices, and weather/disasters to crops, industry and local output.
Always list meaningful counterevidence or alternative causes such as earnings,
sector news, fiscal policy, geopolitics or unrelated supply shocks.
Do not claim causality. Prefer zero hypotheses over a weak or unrelated chain.
Do not connect two candidates from the same document. Maximum confidence is 0.75.
Prefer financially material, measurable chains: monetary-policy expectations to
yields and valuation; inflation/growth to earnings and credit; debt/liquidity to
currencies and funding; commodities/logistics to margins and output. State a
testable market or economic outcome and time window whenever evidence permits.
"""


class LogicChainJobNotFoundError(LookupError):
    """Raised when a completed clustering snapshot is unavailable."""


class LogicChainHypothesisNotFoundError(LookupError):
    """Raised when a logic hypothesis does not exist."""


class LocalLogicChainError(RuntimeError):
    """Raised when the configured local provider returns no valid response."""


def generate_logic_hypotheses(
    session: Session,
    *,
    job_id: int,
    settings: Settings | None = None,
    max_candidates: int = 18,
    transport: httpx.BaseTransport | None = None,
    include_external_market: bool = False,
) -> LogicChainGenerationResponse:
    """Generate hypotheses, then run a separate causal-validation stage."""
    runtime = settings or get_settings()
    _, _, candidate_payload = _candidate_context(session, job_id)
    candidates = _select_candidates(candidate_payload, max_candidates)
    structured_evidence = _structured_evidence_context(
        session,
        candidates,
        settings=runtime,
        include_external_market=include_external_market,
        transport=transport,
    )
    if len(candidates) < 2 or runtime.llm_provider == "mock":
        batch = ModelLogicHypothesisBatch(hypotheses=[])
        model_name = f"{runtime.llm_provider}:{runtime.llm_model}"
    else:
        batch = _call_local_model(
            candidates,
            structured_evidence=structured_evidence,
            settings=runtime,
            transport=transport,
        )
        model_name = f"{runtime.llm_provider}:{runtime.llm_model}"
    generated_count = persist_logic_hypotheses(
        session,
        job_id=job_id,
        batch=batch,
        model_name=model_name,
    )
    validated_count = (
        validate_logic_hypotheses(
            session,
            job_id=job_id,
            settings=runtime,
            include_external_evidence=include_external_market,
            transport=transport,
            structured_evidence=structured_evidence,
        )
        if runtime.causal_validation_enabled
        else 0
    )
    response = list_logic_hypotheses(session, job_id=job_id)
    return LogicChainGenerationResponse(
        **response.model_dump(),
        generated_count=generated_count,
        validated_count=validated_count,
    )


def refresh_recent_logic_hypotheses(
    session: Session,
    *,
    settings: Settings | None = None,
    limit: int = 2,
    scan_limit: int = 50,
    max_attempts: int = 3,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """Retry recent completed snapshots and retain an auditable terminal state."""
    runtime = settings or get_settings()
    jobs = list(
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
            .limit(scan_limit)
        )
    )
    summary: dict[str, Any] = {
        "jobs_scanned": len(jobs),
        "jobs_attempted": 0,
        "jobs_completed": 0,
        "jobs_failed": 0,
        "jobs_reconciled": 0,
        "hypotheses_generated": 0,
        "hypotheses_validated": 0,
        "job_ids": [],
    }
    pending: list[ClusterJob] = []
    for job in jobs:
        result = dict(job.result or {})
        state = result.get("logic_generation")
        state = state if isinstance(state, dict) else {}
        existing_count = int(
            session.scalar(
                select(func.count())
                .select_from(LogicChainHypothesis)
                .where(LogicChainHypothesis.cluster_job_id == job.id)
            )
            or 0
        )
        if existing_count:
            if state.get("status") != "completed":
                _record_logic_generation_state(
                    job,
                    status="completed",
                    attempt_count=int(state.get("attempt_count") or 0),
                    hypotheses=existing_count,
                    validated=existing_count,
                    reconciled_existing=True,
                )
                summary["jobs_reconciled"] += 1
            continue
        if state.get("status") == "completed":
            continue
        if int(state.get("attempt_count") or 0) >= max_attempts:
            continue
        pending.append(job)

    for job in pending[:limit]:
        prior_state = dict((job.result or {}).get("logic_generation") or {})
        attempt_count = int(prior_state.get("attempt_count") or 0) + 1
        summary["jobs_attempted"] += 1
        summary["job_ids"].append(job.id)
        try:
            with session.begin_nested():
                response = generate_logic_hypotheses(
                    session,
                    job_id=job.id,
                    settings=runtime,
                    transport=transport,
                )
        except Exception as exc:
            _record_logic_generation_state(
                job,
                status="failed",
                attempt_count=attempt_count,
                hypotheses=0,
                validated=0,
                error=f"{type(exc).__name__}: {str(exc)[:500]}",
            )
            summary["jobs_failed"] += 1
            continue
        _record_logic_generation_state(
            job,
            status="completed",
            attempt_count=attempt_count,
            hypotheses=response.hypothesis_count,
            validated=response.validated_count,
        )
        summary["jobs_completed"] += 1
        summary["hypotheses_generated"] += response.generated_count
        summary["hypotheses_validated"] += response.validated_count
    session.flush()
    return summary


def _record_logic_generation_state(
    job: ClusterJob,
    *,
    status: Literal["completed", "failed"],
    attempt_count: int,
    hypotheses: int,
    validated: int,
    error: str | None = None,
    reconciled_existing: bool = False,
) -> None:
    result = dict(job.result or {})
    result["logic_generation"] = {
        "status": status,
        "attempt_count": attempt_count,
        "attempted_at": datetime.now(UTC).isoformat(),
        "hypotheses": hypotheses,
        "validated": validated,
        "error": error,
        "reconciled_existing": reconciled_existing,
        "prompt_version": PROMPT_VERSION,
    }
    job.result = result


def persist_logic_hypotheses(
    session: Session,
    *,
    job_id: int,
    batch: ModelLogicHypothesisBatch,
    model_name: str,
) -> int:
    """Validate candidate/document references, then idempotently persist rows."""
    _, candidates, _ = _candidate_context(session, job_id)
    existing = {
        (row.premise_candidate_id, row.outcome_candidate_id): row
        for row in session.scalars(
            select(LogicChainHypothesis).where(LogicChainHypothesis.cluster_job_id == job_id)
        )
    }
    generated_count = 0
    seen: set[tuple[str, str]] = set()
    for proposal in batch.hypotheses:
        premise = candidates.get(proposal.premise_candidate_id)
        outcome = candidates.get(proposal.outcome_candidate_id)
        if premise is None or outcome is None:
            continue
        if premise.document_id == outcome.document_id:
            continue
        referenced_ids = {
            step.candidate_id for step in proposal.steps if step.candidate_id is not None
        }
        if not referenced_ids.issubset(candidates):
            continue
        allowed_documents = {
            candidates[candidate_id].document_id for candidate_id in referenced_ids
        } | {premise.document_id, outcome.document_id}
        evidence_ids = sorted(set(proposal.evidence_document_ids))
        if (
            not set(evidence_ids).issubset(allowed_documents)
            or premise.document_id not in evidence_ids
            or outcome.document_id not in evidence_ids
        ):
            continue
        key = (proposal.premise_candidate_id, proposal.outcome_candidate_id)
        if key in seen:
            continue
        seen.add(key)
        row = existing.get(key)
        if row is None:
            row = LogicChainHypothesis(
                cluster_job_id=job_id,
                premise_candidate_id=proposal.premise_candidate_id,
                outcome_candidate_id=proposal.outcome_candidate_id,
                status="suggested",
                model_name=model_name,
                prompt_version=PROMPT_VERSION,
            )
            session.add(row)
            existing[key] = row
            generated_count += 1
        if row.status != "suggested":
            continue
        normalized_steps = [step.model_dump() for step in proposal.steps]
        for step in normalized_steps:
            step["confidence"] = min(float(step["confidence"]), 0.75)
        normalized_steps[0]["step_type"] = "reported_event"
        normalized_steps[0]["candidate_id"] = proposal.premise_candidate_id
        normalized_steps[-1]["step_type"] = "possible_outcome"
        normalized_steps[-1]["candidate_id"] = proposal.outcome_candidate_id
        row.title = proposal.title.strip()
        row.steps = json.dumps(
            {
                "steps": normalized_steps,
                "association_score": proposal.association_score,
                "evidence_coverage_score": proposal.evidence_coverage_score,
                "counterevidence": proposal.counterevidence,
            },
            ensure_ascii=False,
        )
        row.confidence = min(float(proposal.confidence), 0.75)
        row.rationale = proposal.rationale.strip()
        row.evidence_document_ids = json.dumps(evidence_ids)
        row.model_name = model_name
        row.prompt_version = PROMPT_VERSION
    session.flush()
    return generated_count


def list_logic_hypotheses(
    session: Session,
    *,
    job_id: int,
) -> LogicChainResponse:
    """Return logic hypotheses and the number of retained human signals."""
    _, candidates, _ = _candidate_context(session, job_id)
    rows = list(
        session.scalars(
            select(LogicChainHypothesis)
            .where(LogicChainHypothesis.cluster_job_id == job_id)
            .order_by(
                LogicChainHypothesis.confidence.desc(),
                LogicChainHypothesis.id,
            )
        )
    )
    historical_cases = _historical_cases_by_hypothesis(session, rows)
    hypotheses = [
        _hypothesis_view(
            row,
            candidates,
            historical_cases=historical_cases.get(row.id, []),
        )
        for row in rows
        if row.premise_candidate_id in candidates and row.outcome_candidate_id in candidates
    ]
    signal_count = session.scalar(
        select(func.count())
        .select_from(LogicChainReviewSignal)
        .join(
            LogicChainHypothesis,
            LogicChainReviewSignal.hypothesis_id == LogicChainHypothesis.id,
        )
        .where(LogicChainHypothesis.cluster_job_id == job_id)
    )
    return LogicChainResponse(
        cluster_job_id=job_id,
        hypothesis_count=len(hypotheses),
        training_signal_count=int(signal_count or 0),
        hypotheses=hypotheses,
    )


def validate_logic_hypotheses(
    session: Session,
    *,
    job_id: int,
    settings: Settings | None = None,
    include_external_evidence: bool = True,
    transport: httpx.BaseTransport | None = None,
    structured_evidence: dict[str, Any] | None = None,
) -> int:
    """Validate every stored hypothesis with rules and a separate local agent."""
    runtime = settings or get_settings()
    _, _, candidate_payload = _candidate_context(session, job_id)
    payload_by_id = {str(candidate["candidate_id"]): candidate for candidate in candidate_payload}
    evidence = structured_evidence or _structured_evidence_context(
        session,
        candidate_payload,
        settings=runtime,
        include_external_market=include_external_evidence,
        transport=transport,
    )
    rows = list(
        session.scalars(
            select(LogicChainHypothesis)
            .where(LogicChainHypothesis.cluster_job_id == job_id)
            .order_by(LogicChainHypothesis.id)
        )
    )
    prepared: list[
        tuple[
            LogicChainHypothesis,
            dict[str, Any],
            ModelLogicHypothesis,
            CausalValidationResult,
            set[str],
        ]
    ] = []
    validator_model = f"{runtime.llm_provider}:{runtime.llm_model}"
    for row in rows:
        premise = payload_by_id.get(row.premise_candidate_id)
        outcome = payload_by_id.get(row.outcome_candidate_id)
        if premise is None or outcome is None:
            continue
        analysis = json.loads(row.steps)
        try:
            hypothesis = ModelLogicHypothesis(
                title=row.title,
                premise_candidate_id=row.premise_candidate_id,
                outcome_candidate_id=row.outcome_candidate_id,
                steps=analysis.get("steps", []),
                confidence=float(row.confidence),
                association_score=float(analysis.get("association_score", 0.5)),
                evidence_coverage_score=float(analysis.get("evidence_coverage_score", 0)),
                rationale=row.rationale,
                evidence_document_ids=json.loads(row.evidence_document_ids),
                counterevidence=analysis.get("counterevidence", []),
            )
        except (TypeError, ValueError, ValidationError):
            continue
        refs = allowed_evidence_refs(
            hypothesis,
            premise=premise,
            outcome=outcome,
            structured_evidence=evidence,
        )
        rule_result = build_rule_validation(
            hypothesis,
            premise=premise,
            outcome=outcome,
            structured_evidence=evidence,
            settings=runtime,
            validator_model=f"rules:{runtime.llm_model}",
        )
        prepared.append((row, analysis, hypothesis, rule_result, refs))

    agent_results = call_validator_agent(
        [(hypothesis, rule_result) for _, _, hypothesis, rule_result, _ in prepared],
        structured_evidence=evidence,
        allowed_refs={
            (
                hypothesis.premise_candidate_id,
                hypothesis.outcome_candidate_id,
            ): refs
            for _, _, hypothesis, _, refs in prepared
        },
        settings=runtime,
        transport=transport,
    )
    for row, analysis, hypothesis, rule_result, refs in prepared:
        key = (
            hypothesis.premise_candidate_id,
            hypothesis.outcome_candidate_id,
        )
        merged = merge_agent_validation(
            rule_result,
            agent_results.get(key),
            allowed_refs=refs,
            validator_model=(
                validator_model if key in agent_results else rule_result.validator_model
            ),
        )
        analysis["causal_validation"] = merged.model_dump(mode="json")
        row.steps = json.dumps(analysis, ensure_ascii=False)
    session.flush()
    return len(prepared)


def review_logic_hypothesis(
    session: Session,
    *,
    hypothesis_id: int,
    decision: str,
    reviewer_note: str | None = None,
    suggested_correction: str | None = None,
) -> None:
    """Update current review state and append an immutable feedback snapshot."""
    row = session.get(LogicChainHypothesis, hypothesis_id)
    if row is None:
        raise LogicChainHypothesisNotFoundError(str(hypothesis_id))
    now = datetime.now(UTC)
    row.status = decision
    row.review_note = _clean_optional(reviewer_note)
    row.suggested_correction = _clean_optional(suggested_correction)
    row.decided_at = now
    snapshot = {
        "cluster_job_id": row.cluster_job_id,
        "title": row.title,
        "premise_candidate_id": row.premise_candidate_id,
        "outcome_candidate_id": row.outcome_candidate_id,
        "analysis": json.loads(row.steps),
        "confidence": float(row.confidence),
        "rationale": row.rationale,
        "evidence_document_ids": json.loads(row.evidence_document_ids),
        "model_name": row.model_name,
        "prompt_version": row.prompt_version,
    }
    session.add(
        LogicChainReviewSignal(
            hypothesis_id=row.id,
            decision=decision,
            reviewer_note=row.review_note,
            suggested_correction=row.suggested_correction,
            feature_snapshot=json.dumps(snapshot, ensure_ascii=False),
            created_at=now,
        )
    )
    session.flush()


def list_training_signals(
    session: Session,
    *,
    limit: int = 500,
) -> LogicChainTrainingSignalsResponse:
    """List append-only human decisions without exposing hidden credentials."""
    rows = list(
        session.scalars(
            select(LogicChainReviewSignal)
            .order_by(LogicChainReviewSignal.created_at.desc())
            .limit(limit)
        )
    )
    count = session.scalar(select(func.count()).select_from(LogicChainReviewSignal))
    return LogicChainTrainingSignalsResponse(
        signal_count=int(count or 0),
        signals=[
            LogicChainReviewSignalView(
                id=row.id,
                hypothesis_id=row.hypothesis_id,
                decision=cast(
                    Literal[
                        "accepted",
                        "revised_accepted",
                        "deferred",
                        "rejected",
                    ],
                    row.decision,
                ),
                reviewer_note=row.reviewer_note,
                suggested_correction=row.suggested_correction,
                created_at=row.created_at,
            )
            for row in rows
        ],
    )


def _candidate_context(
    session: Session,
    job_id: int,
) -> tuple[ClusterJob, dict[str, ClusterCandidate], list[dict[str, Any]]]:
    job = session.get(ClusterJob, job_id)
    if (
        job is None
        or job.status not in {ClusterJobStatus.RUNNING, ClusterJobStatus.COMPLETED}
        or job.result is None
    ):
        raise LogicChainJobNotFoundError(str(job_id))
    result = ClusterJobResult.model_validate(job.result)
    representatives: list[ClusterCandidate] = []
    for cluster in result.preview.clusters:
        representatives.append(
            next(
                (
                    member
                    for member in cluster.members
                    if member.candidate_id == cluster.representative_candidate_id
                ),
                cluster.members[0],
            )
        )
    candidate_map = {candidate.candidate_id: candidate for candidate in representatives}
    document_ids = {candidate.document_id for candidate in representatives}
    documents = {
        document.id: document
        for document in session.scalars(select(Document).where(Document.id.in_(document_ids)))
    }
    payload = []
    for candidate in representatives:
        document = documents.get(candidate.document_id)
        occurred_at = candidate.event.occurred_at or (
            (document.published_at or document.fetched_at) if document is not None else None
        )
        payload.append(
            {
                "candidate_id": candidate.candidate_id,
                "document_id": candidate.document_id,
                "evidence_tier": (
                    document_evidence_tier(document)
                    if document is not None
                    else "headline_only"
                ),
                "event_type": candidate.event.event_type,
                "title": repair_common_mojibake(candidate.event.title),
                "summary": repair_common_mojibake(candidate.event.summary)[:500],
                "occurred_at": (occurred_at.isoformat() if occurred_at is not None else None),
                "country_code": (
                    candidate.event.location.country_code
                    if candidate.event.location is not None
                    else None
                ),
                "entities": [
                    repair_common_mojibake(entity.name)
                    for entity in candidate.event.entities[:5]
                ],
            }
        )
    return job, candidate_map, payload


def _select_candidates(
    candidates: list[dict[str, Any]],
    maximum: int,
) -> list[dict[str, Any]]:
    non_quakes = [candidate for candidate in candidates if candidate["event_type"] != "earthquake"]
    substantive = [
        candidate
        for candidate in non_quakes
        if candidate.get("evidence_tier")
        in {None, "feed_content", "official_or_structured"}
    ]
    primary_pool = substantive if len(substantive) >= 2 else non_quakes
    latest = sorted(
        primary_pool,
        key=lambda candidate: candidate["occurred_at"] or "",
        reverse=True,
    )
    priority = sorted(
        primary_pool,
        key=lambda candidate: (
            _logic_signal_score(candidate),
            candidate["occurred_at"] or "",
        ),
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    seen_documents: set[str] = set()

    def add_candidates(rows: list[dict[str, Any]]) -> None:
        for candidate in rows:
            document_key = str(
                candidate.get("document_id") or candidate["candidate_id"]
            )
            if document_key in seen_documents:
                continue
            seen_documents.add(document_key)
            selected.append(candidate)
            if len(selected) >= maximum:
                return

    add_candidates([row for row in priority if _logic_signal_score(row) > 0])
    if len(selected) < maximum:
        add_candidates(latest)
    if len(selected) < maximum and primary_pool is not non_quakes:
        headline_rows = sorted(
            [row for row in non_quakes if row not in primary_pool],
            key=lambda candidate: (
                _logic_signal_score(candidate),
                candidate["occurred_at"] or "",
            ),
            reverse=True,
        )
        add_candidates(headline_rows)
    return selected


def _logic_signal_score(candidate: dict[str, Any]) -> int:
    text = " ".join(
        [
            str(candidate.get("event_type") or ""),
            str(candidate.get("title") or ""),
            str(candidate.get("summary") or ""),
        ]
    ).casefold()
    return sum(term in text for term in LOGIC_SIGNAL_TERMS)


_MARKET_CONTEXT_CACHE: tuple[datetime, list[dict[str, Any]]] | None = None


def _structured_evidence_context(
    session: Session,
    candidates: list[dict[str, Any]],
    *,
    settings: Settings,
    include_external_market: bool,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """Build traceable macro and optional market context for model review."""
    country_codes = {
        str(candidate["country_code"]).upper()
        for candidate in candidates
        if candidate.get("country_code")
    }
    rows = (
        session.execute(
            select(
                CountryProfile.iso2,
                CountryProfile.name,
                EconomicObservation,
                EconomicIndicator,
            )
            .join(
                EconomicObservation,
                EconomicObservation.country_iso3 == CountryProfile.iso3,
            )
            .join(
                EconomicIndicator,
                EconomicIndicator.code == EconomicObservation.indicator_code,
            )
            .where(
                CountryProfile.iso2.in_(country_codes),
                EconomicObservation.indicator_code.in_(ECONOMIC_CONTEXT_CODES),
            )
            .order_by(
                CountryProfile.iso2,
                EconomicObservation.indicator_code,
                EconomicObservation.year.desc(),
            )
        ).all()
        if country_codes
        else []
    )
    newest: dict[tuple[str, str], dict[str, Any]] = {}
    for iso2, country_name, observation, indicator in rows:
        key = (iso2, observation.indicator_code)
        newest.setdefault(
            key,
            {
                "evidence_id": (
                    f"world-bank:{iso2}:{observation.indicator_code}:{observation.year}"
                ),
                "category": "economic_context",
                "country_iso2": iso2,
                "country": country_name,
                "indicator_code": observation.indicator_code,
                "indicator": indicator.name_en,
                "year": observation.year,
                "value": observation.value,
                "unit": indicator.unit,
                "source": indicator.source_name,
                "source_url": indicator.source_url,
            },
        )
    retained_market = _retained_market_context(session)
    live_market = _fetch_market_context(settings) if include_external_market else []
    market = [*retained_market, *live_market]
    official = (
        fetch_validation_evidence(
            settings,
            occurred_at=[
                occurred_at
                for candidate in candidates
                if (occurred_at := _parse_optional_datetime(candidate.get("occurred_at")))
                is not None
            ],
            transport=transport,
        )
        if include_external_market
        else {
            "treasury_yields": [],
            "federal_reserve_items": [],
            "market_expectations": [],
            "fred_observations": [],
            "source_catalog": [],
            "fetch_errors": [],
            "source_health": [],
        }
    )
    source_health = [
        *official.get("source_health", []),
        {
            "key": "fred_local_history",
            "name": "Locally retained FRED history",
            "status": "ready" if retained_market else "partial",
            "observation_count": len(retained_market),
            "message_en": (
                "Dated macro-financial observations are retained locally."
                if retained_market
                else "Historical FRED materialization has not completed."
            ),
            "message_zh": (
                "本地已保存带日期的宏观金融观测。"
                if retained_market
                else "FRED 历史数据尚未完成本地化。"
            ),
            "source_url": "https://fred.stlouisfed.org/",
        },
        {
            "key": "world_bank",
            "name": "World Bank Indicators",
            "status": "ready" if newest else "partial",
            "observation_count": len(newest),
            "message_en": (
                "Relevant annual country observations are available."
                if newest
                else "No relevant country observation matched this hypothesis window."
            ),
            "message_zh": (
                "已获得相关国家的年度观测。"
                if newest
                else "该假设范围内没有匹配到相关国家年度观测。"
            ),
            "source_url": "https://data.worldbank.org/",
        },
        {
            "key": "twelve_data",
            "name": "Twelve Data",
            "status": (
                "ready"
                if live_market
                else (
                    "unavailable" if settings.twelve_data_api_key is not None else "not_configured"
                )
            ),
            "observation_count": len(live_market),
            "message_en": (
                "High-frequency market observations are available."
                if live_market
                else "No usable market observation was returned for this request."
            ),
            "message_zh": (
                "已获得高频市场观测。"
                if live_market
                else "本次请求未返回可用市场观测。"
            ),
            "source_url": "https://twelvedata.com/docs",
        },
    ]
    memory_focus = " ".join(
        f"{candidate.get('title') or ''} {candidate.get('summary') or ''}"
        for candidate in candidates
    )
    verified_memories = [
        memory.model_dump(mode="json")
        for memory in qualified_logic_memories(
            session,
            focus=memory_focus,
            limit=6,
        )
    ]
    return {
        "economic_observations": list(newest.values()),
        "market_observations": market,
        "economic_cycle": build_cycle_snapshot(session),
        **official,
        "source_health": source_health,
        "human_review_guidance": _human_review_guidance(session),
        "verified_logic_memory": verified_memories,
        "evidence_rules": [
            "Annual economic values are context, not proof of an event cause.",
            "Market observations show co-movement, not causality.",
            (
                "SPY, QQQ and EWJ observations are ETF proxies, not the "
                "underlying S&P 500, Nasdaq Composite or Nikkei indices."
            ),
            "Policy-action steps must remain conditional unless directly reported.",
            "Counterevidence and alternative explanations are required.",
            (
                "Federal Reserve chains should distinguish the decision, "
                "statement/dot plot/press conference, expected-rate-path "
                "repricing, 2Y/10Y Treasury yields, equity valuation and "
                "S&P 500/Nasdaq response. Prefer the Atlanta Fed Market "
                "Probability Tracker for rate-path evidence; if it or primary "
                "FOMC evidence is absent, identify it as missing evidence."
            ),
            (
                "FX-reserve, sovereign-debt and commodity-policy responses "
                "must be framed as scenarios unless a source reports the "
                "action; include competing earnings, sector and geopolitical "
                "explanations."
            ),
            (
                "Human review guidance expresses analyst preferences and "
                "corrections. It is not factual evidence and must never be "
                "cited as proof."
            ),
            (
                "Verified logic memory is a prior human-approved analogy, not "
                "evidence that the current event occurred. Reuse its mechanism "
                "structure only when current dated evidence independently supports it."
            ),
        ],
    }


def _retained_market_context(session: Session) -> list[dict[str, Any]]:
    """Select the latest three values per reviewed local market series."""
    result: list[dict[str, Any]] = []
    for series in session.scalars(select(MarketSeries).order_by(MarketSeries.series_id)):
        for observation in session.scalars(
            select(MarketObservation)
            .where(MarketObservation.series_id == series.series_id)
            .order_by(MarketObservation.observed_on.desc())
            .limit(3)
        ):
            result.append(
                {
                    "evidence_id": (
                        f"market:{series.series_id}:{observation.observed_on.isoformat()}"
                    ),
                    "category": "market_observation",
                    "symbol": series.series_id,
                    "name": series.name,
                    "observed_on": observation.observed_on.isoformat(),
                    "value": observation.value,
                    "unit": series.unit,
                    "source": series.source_name,
                    "source_url": series.source_url,
                }
            )
    return result


def _human_review_guidance(
    session: Session,
    *,
    limit: int = 8,
) -> list[dict[str, str | None]]:
    """Return recent append-only corrections as prompting preferences."""
    rows = session.execute(
        select(
            LogicChainReviewSignal,
            LogicChainHypothesis.title,
        )
        .join(
            LogicChainHypothesis,
            LogicChainHypothesis.id == LogicChainReviewSignal.hypothesis_id,
        )
        .order_by(LogicChainReviewSignal.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "decision": signal.decision,
            "hypothesis_title": title,
            "reviewer_note": signal.reviewer_note,
            "suggested_correction": signal.suggested_correction,
        }
        for signal, title in rows
    ]


def _fetch_market_context(settings: Settings) -> list[dict[str, Any]]:
    """Fetch a small cached market panel only for explicit human generation."""
    global _MARKET_CONTEXT_CACHE
    now = datetime.now(UTC)
    if _MARKET_CONTEXT_CACHE is not None and now - _MARKET_CONTEXT_CACHE[0] < timedelta(minutes=15):
        return _MARKET_CONTEXT_CACHE[1]
    if settings.twelve_data_api_key is None:
        return []
    api_key = settings.twelve_data_api_key.get_secret_value()
    observations: list[dict[str, Any]] = []
    with httpx.Client(timeout=settings.market_request_timeout_seconds) as client:
        for symbol in MARKET_CONTEXT_SYMBOLS:
            try:
                response = client.get(
                    "https://api.twelvedata.com/time_series",
                    params={
                        "symbol": symbol,
                        "interval": "1day",
                        "outputsize": "2",
                        "apikey": api_key,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or payload.get("status") == "error":
                    continue
                values = payload.get("values")
                if not isinstance(values, list) or not values:
                    continue
                latest = values[0]
                previous = values[1] if len(values) > 1 else None
                close = float(latest["close"])
                previous_close = (
                    float(previous["close"])
                    if isinstance(previous, dict) and previous.get("close")
                    else None
                )
                change_percent = (
                    ((close - previous_close) / previous_close) * 100 if previous_close else None
                )
                observations.append(
                    {
                        "evidence_id": (f"twelve:{symbol}:{latest.get('datetime')}"),
                        "category": "market_observation",
                        "symbol": symbol,
                        "observed_on": latest.get("datetime"),
                        "close": close,
                        "change_percent": change_percent,
                        "source": "Twelve Data",
                        "source_url": "https://twelvedata.com/docs",
                    }
                )
            except (httpx.HTTPError, KeyError, TypeError, ValueError):
                continue
    _MARKET_CONTEXT_CACHE = (now, observations)
    return observations


def _call_local_model(
    candidates: list[dict[str, Any]],
    *,
    structured_evidence: dict[str, Any],
    settings: Settings,
    transport: httpx.BaseTransport | None,
) -> ModelLogicHypothesisBatch:
    prompt_context = _fit_logic_prompt_context(
        candidates,
        structured_evidence,
        max_chars=settings.llm_max_input_chars,
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(prompt_context, ensure_ascii=False),
        },
    ]
    schema = _provider_json_schema()
    if settings.llm_provider == "ollama":
        endpoint = "/api/chat"
        payload = {
            "model": settings.llm_model,
            "messages": messages,
            "stream": False,
            "think": False,
            "format": schema,
            "options": {"temperature": 0},
        }
    elif settings.llm_provider in {"llama_cpp", "vllm"}:
        endpoint = "/v1/chat/completions"
        payload = {
            "model": settings.llm_model,
            "messages": messages,
            "stream": False,
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "news_logic_hypotheses",
                    "strict": True,
                    "schema": schema,
                },
            },
        }
    else:
        return ModelLogicHypothesisBatch(hypotheses=[])
    last_error: Exception | None = None
    for _ in range(settings.llm_max_attempts):
        try:
            with httpx.Client(
                base_url=str(settings.llm_base_url).rstrip("/"),
                timeout=settings.llm_timeout_seconds,
                transport=transport,
            ) as client:
                response = client.post(endpoint, json=payload)
                response.raise_for_status()
            data = response.json()
            if settings.llm_provider == "ollama":
                content = data["message"]["content"]
            else:
                content = data["choices"][0]["message"]["content"]
            return _validated_model_batch(content)
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
            ValidationError,
        ) as exc:
            last_error = exc
    raise LocalLogicChainError(
        "local model failed to return a valid logic-chain batch"
    ) from last_error


def _fit_logic_prompt_context(
    candidates: list[dict[str, Any]],
    structured_evidence: dict[str, Any],
    *,
    max_chars: int,
) -> dict[str, Any]:
    """Keep the most useful evidence while enforcing the configured input budget."""
    compact_candidates = [
        {
            **candidate,
            "title": str(candidate.get("title") or "")[:320],
            "summary": str(candidate.get("summary") or "")[:260],
            "entities": list(candidate.get("entities") or [])[:5],
        }
        for candidate in candidates[:18]
    ]
    list_limits = {
        "economic_observations": 16,
        "market_observations": 20,
        "treasury_yields": 10,
        "federal_reserve_items": 6,
        "market_expectations": 8,
        "fred_observations": 12,
        "source_catalog": 8,
        "fetch_errors": 6,
        "source_health": 8,
        "human_review_guidance": 4,
        "verified_logic_memory": 6,
        "evidence_rules": 8,
    }
    compact_evidence: dict[str, Any] = {}
    for key, value in structured_evidence.items():
        if isinstance(value, list):
            compact_evidence[key] = [
                _compact_prompt_value(item)
                for item in value[: list_limits.get(key, 12)]
            ]
        else:
            compact_evidence[key] = _compact_prompt_value(value)
    context = {
        "candidates": compact_candidates,
        "structured_evidence": compact_evidence,
    }
    optional_lists = (
        "human_review_guidance",
        "verified_logic_memory",
        "source_catalog",
        "fetch_errors",
        "economic_observations",
        "market_observations",
        "fred_observations",
        "treasury_yields",
        "federal_reserve_items",
        "market_expectations",
    )
    while _prompt_size(context) > max_chars:
        reduced = False
        if len(compact_candidates) > 8:
            compact_candidates.pop()
            reduced = True
        else:
            for key in optional_lists:
                values = compact_evidence.get(key)
                minimum = 4 if key in {
                    "market_observations",
                    "fred_observations",
                } else 0
                if isinstance(values, list) and len(values) > minimum:
                    values.pop()
                    reduced = True
                    break
        if not reduced:
            break
    if _prompt_size(context) > max_chars:
        for candidate in compact_candidates:
            candidate["summary"] = str(candidate.get("summary") or "")[:100]
    if _prompt_size(context) > max_chars:
        raise LocalLogicChainError(
            "compacted logic-chain evidence exceeds the configured input budget"
        )
    return context


def _compact_prompt_value(value: Any) -> Any:
    """Bound verbose provider prose without changing numeric observations."""
    if isinstance(value, dict):
        return {
            str(key): _compact_prompt_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_compact_prompt_value(item) for item in value[:12]]
    if isinstance(value, str):
        return repair_common_mojibake(value)[:320]
    return value


def _prompt_size(value: dict[str, Any]) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def _validated_model_batch(content: str) -> ModelLogicHypothesisBatch:
    """Validate hypotheses independently so one malformed item cannot erase all."""
    raw = json.loads(content)
    if not isinstance(raw, dict) or not isinstance(
        raw.get("hypotheses"),
        list,
    ):
        raise ValueError("logic-chain response must contain hypotheses")
    hypotheses = []
    for item in raw["hypotheses"][:12]:
        if not isinstance(item, dict):
            continue
        normalized = dict(item)
        normalized["confidence"] = _bounded_score(
            normalized.get("confidence"),
            maximum=0.75,
        )
        normalized["association_score"] = _bounded_score(
            normalized.get("association_score", 0.5),
        )
        normalized["evidence_coverage_score"] = _bounded_score(
            normalized.get("evidence_coverage_score", 0),
        )
        steps = normalized.get("steps")
        if not isinstance(steps, list):
            continue
        normalized_steps = []
        for step in steps[:6]:
            if not isinstance(step, dict):
                continue
            normalized_step = dict(step)
            normalized_step["confidence"] = _bounded_score(
                normalized_step.get("confidence", 0.5),
                maximum=0.75,
            )
            normalized_step["relevance"] = _bounded_score(
                normalized_step.get("relevance", 0.5),
            )
            evidence_refs = normalized_step.get("evidence_refs", [])
            normalized_step["evidence_refs"] = (
                evidence_refs[:8] if isinstance(evidence_refs, list) else []
            )
            normalized_steps.append(normalized_step)
        normalized["steps"] = normalized_steps
        evidence_ids = normalized.get("evidence_document_ids")
        if isinstance(evidence_ids, list):
            normalized["evidence_document_ids"] = evidence_ids[:8]
        counterevidence = normalized.get("counterevidence", [])
        normalized["counterevidence"] = (
            counterevidence[:6] if isinstance(counterevidence, list) else []
        )
        try:
            hypotheses.append(ModelLogicHypothesis.model_validate(normalized))
        except (TypeError, ValidationError):
            continue
    return ModelLogicHypothesisBatch(hypotheses=hypotheses)


def _bounded_score(
    value: Any,
    *,
    maximum: float = 1,
) -> float:
    try:
        return max(0, min(float(value), maximum))
    except (TypeError, ValueError):
        return 0


def _provider_json_schema() -> dict[str, Any]:
    def compatible(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: compatible(item)
                for key, item in value.items()
                if key not in UNSUPPORTED_GRAMMAR_SCHEMA_KEYS
            }
        if isinstance(value, list):
            return [compatible(item) for item in value]
        return value

    schema = compatible(ModelLogicHypothesisBatch.model_json_schema())
    if not isinstance(schema, dict):
        raise TypeError("model JSON schema must be an object")
    return schema


def _hypothesis_view(
    row: LogicChainHypothesis,
    candidates: dict[str, ClusterCandidate],
    *,
    historical_cases: list[CausalHistoricalCaseView] | None = None,
) -> LogicChainHypothesisView:
    analysis = json.loads(row.steps)
    steps = analysis.get("steps", [])
    association_score = float(analysis.get("association_score", 0.5))
    evidence_coverage_score = float(
        analysis.get(
            "evidence_coverage_score",
            min(1, len(json.loads(row.evidence_document_ids)) / 4),
        )
    )
    confidence = float(row.confidence)
    causal_validation = None
    raw_validation = analysis.get("causal_validation")
    if isinstance(raw_validation, dict):
        try:
            causal_validation = CausalValidationResult.model_validate(raw_validation)
        except ValidationError:
            causal_validation = None
    chatgpt_review = None
    raw_chatgpt_review = analysis.get("chatgpt_review")
    if isinstance(raw_chatgpt_review, dict):
        try:
            chatgpt_review = ChatGPTResearchReview.model_validate(
                raw_chatgpt_review
            )
        except ValidationError:
            chatgpt_review = None
    effective_confidence = (
        min(confidence, causal_validation.recalculated_confidence)
        if causal_validation is not None
        else confidence
    )
    composite_score = min(
        1,
        effective_confidence * 0.45 + association_score * 0.35 + evidence_coverage_score * 0.2,
    )
    return LogicChainHypothesisView(
        id=row.id,
        cluster_job_id=row.cluster_job_id,
        title=row.title,
        premise_candidate_id=row.premise_candidate_id,
        premise_title=candidates[row.premise_candidate_id].event.title,
        outcome_candidate_id=row.outcome_candidate_id,
        outcome_title=candidates[row.outcome_candidate_id].event.title,
        steps=steps,
        confidence=confidence,
        association_score=association_score,
        evidence_coverage_score=evidence_coverage_score,
        rationale=row.rationale,
        evidence_document_ids=json.loads(row.evidence_document_ids),
        counterevidence=analysis.get("counterevidence", []),
        status=cast(LogicChainStatus, row.status),
        model_name=row.model_name,
        prompt_version=row.prompt_version,
        review_note=row.review_note,
        suggested_correction=row.suggested_correction,
        decided_at=row.decided_at,
        composite_score=composite_score,
        causal_validation=causal_validation,
        chatgpt_review=chatgpt_review,
        historical_cases=historical_cases or [],
    )


def _historical_cases_by_hypothesis(
    session: Session,
    current_rows: list[LogicChainHypothesis],
    *,
    limit: int = 200,
) -> dict[int, list[CausalHistoricalCaseView]]:
    """Match current hypotheses to prior human-reviewed analyses."""
    signals = list(
        session.scalars(
            select(LogicChainReviewSignal)
            .order_by(LogicChainReviewSignal.created_at.desc())
            .limit(limit)
        )
    )
    cases: list[tuple[LogicChainReviewSignal, dict[str, Any], set[str]]] = []
    for signal in signals:
        try:
            snapshot = json.loads(signal.feature_snapshot)
        except (TypeError, ValueError):
            continue
        if not isinstance(snapshot, dict):
            continue
        cases.append(
            (
                signal,
                snapshot,
                _case_tokens(_snapshot_case_text(snapshot)),
            )
        )
    result: dict[int, list[CausalHistoricalCaseView]] = {}
    for row in current_rows:
        current_tokens = _case_tokens(_row_case_text(row))
        matches: list[CausalHistoricalCaseView] = []
        for signal, snapshot, case_tokens in cases:
            similarity = _jaccard_similarity(current_tokens, case_tokens)
            if similarity < 0.12:
                continue
            analysis = snapshot.get("analysis")
            validation = (
                analysis.get("causal_validation")
                if isinstance(analysis, dict)
                else None
            )
            conclusion = None
            validated_confidence = None
            validation_summary_en = None
            validation_summary_zh = None
            if isinstance(validation, dict):
                try:
                    parsed_validation = CausalValidationResult.model_validate(
                        validation
                    )
                    conclusion = parsed_validation.conclusion
                    validated_confidence = (
                        parsed_validation.recalculated_confidence
                    )
                    validation_summary_en = parsed_validation.summary_en
                    validation_summary_zh = parsed_validation.summary_zh
                except ValidationError:
                    pass
            fallback_en = (
                signal.suggested_correction
                or signal.reviewer_note
                or f"Human reviewer decision: {signal.decision}."
            )
            fallback_zh = (
                signal.suggested_correction
                or signal.reviewer_note
                or f"历史人工审核结论: {signal.decision}。"
            )
            matches.append(
                CausalHistoricalCaseView(
                    hypothesis_id=signal.hypothesis_id,
                    title=str(snapshot.get("title") or "Historical case")[:500],
                    reviewed_at=signal.created_at,
                    decision=cast(
                        Literal[
                            "accepted",
                            "revised_accepted",
                            "deferred",
                            "rejected",
                        ],
                        signal.decision,
                    ),
                    similarity_score=round(similarity, 4),
                    original_confidence=_bounded_score(
                        snapshot.get("confidence", 0),
                        maximum=0.75,
                    ),
                    validated_confidence=validated_confidence,
                    conclusion=conclusion,
                    summary_en=(validation_summary_en or fallback_en)[:1_000],
                    summary_zh=(validation_summary_zh or fallback_zh)[:1_000],
                )
            )
        matches.sort(
            key=lambda case: (
                case.similarity_score,
                case.reviewed_at,
            ),
            reverse=True,
        )
        result[row.id] = matches[:5]
    return result


def _row_case_text(row: LogicChainHypothesis) -> str:
    return f"{row.title} {row.rationale} {row.steps}"


def _snapshot_case_text(snapshot: dict[str, Any]) -> str:
    return " ".join(
        str(snapshot.get(key) or "")
        for key in ("title", "rationale", "analysis")
    )


def _case_tokens(text: str) -> set[str]:
    """Use words plus CJK bigrams so multilingual cases can be compared."""
    normalized = repair_common_mojibake(text).casefold()
    words = {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_-]+", normalized)
        if len(token) >= 3
    }
    cjk_runs = re.findall(r"[\u3400-\u9fff]+", normalized)
    bigrams = {
        run[index : index + 2]
        for run in cjk_runs
        for index in range(max(0, len(run) - 1))
    }
    return words | bigrams


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0
    return len(left & right) / len(left | right)


def _clean_optional(value: str | None) -> str | None:
    cleaned = value.strip() if value else ""
    return cleaned or None


def _parse_optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
