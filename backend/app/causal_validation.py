"""Independent rule and local-model validation for proposed causal chains."""

# ruff: noqa: RUF001

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.extractors.llm import UNSUPPORTED_GRAMMAR_SCHEMA_KEYS
from app.schemas.logic_chains import (
    CausalCheckKey,
    CausalCheckStatus,
    CausalConclusion,
    CausalConfidenceBreakdown,
    CausalConfidenceComponent,
    CausalEvidenceFactView,
    CausalEvidenceSourceView,
    CausalNextDataSuggestion,
    CausalReasoningTraceStep,
    CausalValidationCheck,
    CausalValidationResult,
    EvidencePriority,
    ModelCausalValidation,
    ModelCausalValidationBatch,
    ModelLogicHypothesis,
    ReviewerRecommendation,
)

VALIDATOR_VERSION = "causal-validator-v1"
CHECK_KEYS: tuple[CausalCheckKey, ...] = (
    "premise_reported",
    "outcome_time_window",
    "mechanism_evidence",
    "market_expectations",
    "alternative_explanations",
    "causal_sufficiency",
)
STATUS_SCORE: dict[CausalCheckStatus, float] = {
    "passed": 1,
    "partially_supported": 0.55,
    "missing_evidence": 0.1,
    "failed": 0,
    "not_applicable": 1,
}
STATUS_RANK: dict[CausalCheckStatus, int] = {
    "failed": 0,
    "missing_evidence": 1,
    "partially_supported": 2,
    "passed": 3,
    "not_applicable": 4,
}
CHECK_WEIGHTS: dict[CausalCheckKey, float] = {
    "premise_reported": 0.15,
    "outcome_time_window": 0.15,
    "mechanism_evidence": 0.25,
    "market_expectations": 0.15,
    "alternative_explanations": 0.1,
    "causal_sufficiency": 0.2,
}
CONCLUSION_RANK: dict[CausalConclusion, int] = {
    "temporal_correlation_only": 0,
    "mechanism_partially_supported": 1,
    "mechanism_supported_not_causal": 2,
}
POLICY_TERMS = (
    "fomc",
    "federal reserve",
    "powell",
    "policy rate",
    "interest rate decision",
    "rate decision",
    "central bank",
    "美联储",
    "鲍威尔",
    "政策利率",
    "利率决定",
    "央行",
)
MARKET_TERMS = (
    "s&p",
    "nasdaq",
    "stock",
    "equity",
    "yield",
    "treasury",
    "bond",
    "market",
    "标普",
    "纳斯达克",
    "股票",
    "股市",
    "收益率",
    "美债",
    "市场",
)
EXPECTATION_TERMS = (
    "fed funds futures",
    "fedwatch",
    "rate futures",
    "higher for longer",
    "expected rate path",
    "market pricing",
    "利率期货",
    "市场定价",
    "利率路径预期",
    "更高更久",
)
DISASTER_TERMS = (
    "earthquake",
    "flood",
    "storm",
    "hurricane",
    "drought",
    "wildfire",
    "disaster",
    "地震",
    "洪水",
    "风暴",
    "飓风",
    "干旱",
    "山火",
    "灾害",
)

VALIDATOR_SYSTEM_PROMPT = """\
You are a separate causal-validation agent. You receive already-generated
hypotheses, deterministic gate results and a closed set of evidence records.
Return JSON only and match the supplied schema exactly.

For each hypothesis return each of these six checks exactly once:
premise_reported, outcome_time_window, mechanism_evidence,
market_expectations, alternative_explanations, causal_sufficiency.

Never invent an event, quote, measurement, source or evidence identifier.
Use only evidence_refs present in the supplied allowed_evidence_refs. A news
candidate proves that something was reported; it does not by itself prove the
claim is true. Annual macro context and market co-movement do not prove cause.
Human review guidance is a preference signal and is never factual evidence.

For Federal Reserve-to-equity chains, retain a supported transmission
mechanism only if evidence establishes both expected-rate-path repricing and
the relevant 2Y/10Y Treasury-yield move after the decision. Otherwise classify
the result as temporal_correlation_only. Check FOMC communications, Powell
remarks, Treasury yields, Fed Funds Futures or equivalent expectation evidence,
S&P 500/Nasdaq moves, and stronger competing explanations. Be skeptical and
downgrade confidence when evidence is missing. Never mark causality confirmed.
"""


def build_rule_validation(
    hypothesis: ModelLogicHypothesis,
    *,
    premise: dict[str, Any],
    outcome: dict[str, Any],
    structured_evidence: dict[str, Any],
    settings: Settings,
    validator_model: str,
) -> CausalValidationResult:
    """Evaluate non-negotiable evidence gates before asking a model."""
    text = _chain_text(hypothesis, premise, outcome)
    policy_chain = _contains_any(text, POLICY_TERMS) and _contains_any(
        text,
        MARKET_TERMS,
    )
    time_window_hours = _time_window_hours(
        text,
        policy_chain=policy_chain,
        default=settings.causal_validation_window_hours,
    )
    allowed_refs = allowed_evidence_refs(
        hypothesis,
        premise=premise,
        outcome=outcome,
        structured_evidence=structured_evidence,
    )
    checks: list[CausalValidationCheck] = []
    missing: list[str] = []

    premise_document_id = premise.get("document_id")
    premise_ref = f"document:{premise_document_id}" if premise_document_id is not None else None
    premise_tier = str(premise.get("evidence_tier") or "unknown")
    if premise_ref is not None and premise_tier == "headline_only":
        missing.append("Substantive source text or structured data for the premise")
        checks.append(
            _check(
                "premise_reported",
                "partially_supported",
                (
                    "A stored headline reports the premise, but no substantive "
                    "article text or structured source is retained."
                ),
                "已保存标题可作为事件线索，但尚无正文或结构化来源独立验证前提。",
                [premise_ref],
            )
        )
    elif premise_ref is not None:
        checks.append(
            _check(
                "premise_reported",
                "passed",
                (
                    "A stored source document reports the premise. This "
                    "confirms the report exists, not that every claim is true."
                ),
                "已有来源文档报道前提事件；这只能确认报道存在，并不自动证明报道中的全部主张。",
                [premise_ref],
            )
        )
    else:
        missing.append("A source document that reports the premise")
        checks.append(
            _check(
                "premise_reported",
                "missing_evidence",
                "No stored source document could be resolved for the premise.",
                "未能为前提事件解析到已存储的来源文档。",
            )
        )

    premise_at = _parse_datetime(premise.get("occurred_at"))
    outcome_at = _parse_datetime(outcome.get("occurred_at"))
    market_outcome_status, market_outcome_refs = _market_outcome_evidence(
        " ".join(
            [
                str(outcome.get("title") or ""),
                str(outcome.get("summary") or ""),
                hypothesis.steps[-1].text,
            ]
        ).casefold(),
        structured_evidence=structured_evidence,
        premise_at=premise_at,
        outcome_at=outcome_at,
    )
    outcome_ref = (
        f"document:{outcome['document_id']}" if outcome.get("document_id") is not None else None
    )
    if premise_at is None or outcome_at is None or outcome_ref is None:
        missing.append("Dated source evidence for both premise and outcome")
        checks.append(
            _check(
                "outcome_time_window",
                "missing_evidence",
                "The premise or outcome lacks a resolvable source time.",
                "前提或结果事件缺少可解析的来源时间。",
                [ref for ref in (premise_ref, outcome_ref) if ref],
            )
        )
    else:
        gap = outcome_at - premise_at
        if timedelta(0) < gap <= timedelta(hours=time_window_hours):
            if market_outcome_status == "contradicted":
                checks.append(
                    _check(
                        "outcome_time_window",
                        "failed",
                        (
                            "The report is inside the time window, but the "
                            "available FRED index movement contradicts the "
                            "reported market direction."
                        ),
                        "报道处于时间窗口内，但FRED指数变动与报道中的市场方向相反。",
                        [
                            premise_ref,
                            outcome_ref,
                            *sorted(market_outcome_refs),
                        ],
                    )
                )
            elif market_outcome_status == "unavailable":
                missing.append("A matching S&P 500 or Nasdaq observation after the premise")
                checks.append(
                    _check(
                        "outcome_time_window",
                        "partially_supported",
                        (
                            f"The report follows the premise by "
                            f"{gap.total_seconds() / 3_600:.1f} hours, but no "
                            "matching FRED index close verifies the outcome."
                        ),
                        (
                            f"报道比前提晚 {gap.total_seconds() / 3_600:.1f} 小时，"
                            "但没有匹配的FRED指数收盘值验证结果。"
                        ),
                        [premise_ref, outcome_ref],
                    )
                )
            else:
                checks.append(
                    _check(
                        "outcome_time_window",
                        "passed",
                        (
                            f"The reported outcome follows the premise by "
                            f"{gap.total_seconds() / 3_600:.1f} hours, within the "
                            f"{time_window_hours}-hour validation window."
                        ),
                        (
                            f"报道中的结果比前提晚 {gap.total_seconds() / 3_600:.1f} 小时，"
                            f"处于 {time_window_hours} 小时验证窗口内。"
                        ),
                        [
                            premise_ref,
                            outcome_ref,
                            *sorted(market_outcome_refs),
                        ],
                    )
                )
        elif gap == timedelta(0):
            missing.append("Higher-resolution timestamps that establish event ordering")
            checks.append(
                _check(
                    "outcome_time_window",
                    "partially_supported",
                    (
                        "The two reports share the same resolved timestamp, "
                        "so the time window fits but event ordering is unknown."
                    ),
                    "两条报道解析到相同时间；虽然处于窗口内，但无法确定事件先后顺序。",
                    [
                        premise_ref,
                        outcome_ref,
                        *sorted(market_outcome_refs),
                    ],
                )
            )
        else:
            checks.append(
                _check(
                    "outcome_time_window",
                    "failed",
                    (
                        "The outcome is earlier than the premise or outside "
                        f"the {time_window_hours}-hour validation window."
                    ),
                    f"结果早于前提，或超出 {time_window_hours} 小时验证窗口。",
                    [premise_ref, outcome_ref],
                )
            )

    mechanism_steps = [step for step in hypothesis.steps if step.step_type == "inferred_mechanism"]
    referenced_mechanisms = []
    structured_mechanisms = []
    for step in mechanism_steps:
        valid = set(step.evidence_refs) & allowed_refs
        if valid:
            referenced_mechanisms.append(valid)
        if any(not _is_document_reference(ref) for ref in valid):
            structured_mechanisms.append(valid)
    if mechanism_steps and len(structured_mechanisms) == len(mechanism_steps):
        refs = sorted(set().union(*structured_mechanisms))
        checks.append(
            _check(
                "mechanism_evidence",
                "passed",
                "Every inferred mechanism step cites a supplied structured record.",
                "每个推断机制步骤都引用了已提供的结构化证据记录。",
                refs,
            )
        )
    elif referenced_mechanisms:
        refs = sorted(set().union(*referenced_mechanisms))
        missing.append("Structured evidence for every inferred mechanism step")
        checks.append(
            _check(
                "mechanism_evidence",
                "partially_supported",
                (
                    "Some mechanism steps cite stored documents, but one or "
                    "more steps still lack direct structured support."
                ),
                "部分机制步骤引用了文档，但仍有步骤缺少直接的结构化数据支持。",
                refs,
            )
        )
    else:
        missing.append("Direct evidence for each inferred transmission step")
        checks.append(
            _check(
                "mechanism_evidence",
                "missing_evidence",
                "No inferred mechanism step cites a supplied evidence record.",
                "没有推断机制步骤引用已提供的证据记录。",
            )
        )

    expectation_refs = _evidence_refs_by_category(
        structured_evidence,
        "market_expectation",
    )
    expectation_state, measured_expectation_refs = _market_expectations_repriced(
        structured_evidence,
        premise_at=premise_at,
        outcome_at=outcome_at,
    )
    if not policy_chain:
        checks.append(
            _check(
                "market_expectations",
                "not_applicable",
                "This is not a monetary-policy-to-market hypothesis.",
                "这不是货币政策向市场传导的假设。",
            )
        )
    elif expectation_state == "verified":
        checks.append(
            _check(
                "market_expectations",
                "passed",
                (
                    "Atlanta Fed MPT observations before and after the decision "
                    "show a material change in the expected rate path."
                ),
                "亚特兰大联储MPT在决策前后的观测显示预期利率路径发生了显著变化。",
                sorted(measured_expectation_refs),
            )
        )
    elif expectation_state == "stable":
        missing.append("A material pre/post change in the expected rate path")
        checks.append(
            _check(
                "market_expectations",
                "failed",
                (
                    "Available Atlanta Fed MPT observations do not show a "
                    "material pre/post repricing in the compared window."
                ),
                "现有亚特兰大联储MPT观测未显示比较窗口内存在显著的前后重新定价。",
                sorted(measured_expectation_refs),
            )
        )
    elif expectation_refs:
        missing.append("Both pre-decision and post-decision expectation observations")
        checks.append(
            _check(
                "market_expectations",
                "partially_supported",
                (
                    "Rate-path observations are available, but the selected "
                    "window lacks a complete pre/post pair."
                ),
                "已有利率路径观测，但所选窗口缺少完整的决策前后配对。",
                sorted(expectation_refs),
            )
        )
    elif _contains_any(text, EXPECTATION_TERMS):
        missing.append(
            "A measured pre/post expectation series such as the Atlanta Fed MPT"
        )
        checks.append(
            _check(
                "market_expectations",
                "partially_supported",
                (
                    "A report discusses market pricing, but no supplied "
                    "expectation series verifies the repricing."
                ),
                "报道提到市场定价，但没有已提供的预期序列验证重新定价过程。",
                [ref for ref in (premise_ref, outcome_ref) if ref],
            )
        )
    else:
        missing.append(
            "Atlanta Fed MPT or equivalent rate-path expectation data"
        )
        checks.append(
            _check(
                "market_expectations",
                "missing_evidence",
                "No supplied record measures whether the decision was already priced in.",
                "没有已提供的记录衡量该决策是否已被市场提前计价。",
            )
        )

    if hypothesis.counterevidence:
        checks.append(
            _check(
                "alternative_explanations",
                "passed",
                (
                    f"{len(hypothesis.counterevidence)} competing explanations "
                    "are retained for human comparison."
                ),
                f"已保留 {len(hypothesis.counterevidence)} 个替代解释供人工比较。",
            )
        )
    else:
        missing.append("At least one stronger competing explanation")
        checks.append(
            _check(
                "alternative_explanations",
                "missing_evidence",
                "The hypothesis does not retain a competing explanation.",
                "该假设没有保留替代解释。",
            )
        )

    yields_rose, yield_refs = _treasury_yields_rose(
        structured_evidence,
        premise_at=premise_at,
        outcome_at=outcome_at,
    )
    official_policy_refs = _evidence_refs_by_category(
        structured_evidence,
        "official_policy_communication",
    )
    expectation_check = next(check for check in checks if check.check_key == "market_expectations")
    mechanism_check = next(check for check in checks if check.check_key == "mechanism_evidence")
    timing_check = next(check for check in checks if check.check_key == "outcome_time_window")
    alternative_check = next(
        check for check in checks if check.check_key == "alternative_explanations"
    )
    if policy_chain:
        if (
            expectation_check.status == "passed"
            and yields_rose
            and official_policy_refs
            and mechanism_check.status == "passed"
            and timing_check.status == "passed"
            and alternative_check.status == "passed"
        ):
            conclusion: CausalConclusion = "mechanism_supported_not_causal"
            checks.append(
                _check(
                    "causal_sufficiency",
                    "passed",
                    (
                        "Rate-path repricing and both 2Y/10Y yield increases "
                        "are present, so the mechanism can be retained as "
                        "supported but not causally proven."
                    ),
                    "利率路径重新定价以及2年期、10年期收益率上升均有记录，因此可保留机制支持，但不能视为因果已证实。",
                    sorted(expectation_refs | yield_refs | official_policy_refs),
                )
            )
        else:
            conclusion = "temporal_correlation_only"
            if not official_policy_refs:
                missing.append("An official FOMC statement or relevant Powell communication")
            if not yields_rose:
                missing.append(
                    "Verified post-decision increases in both 2Y and 10Y Treasury yields"
                )
            checks.append(
                _check(
                    "causal_sufficiency",
                    "missing_evidence",
                    (
                        "The complete Fed transmission mechanism is not "
                        "verified; the result is limited to temporal correlation."
                    ),
                    "美联储传导机制尚未完整验证；当前结论仅限于时间上的相关性。",
                    sorted(yield_refs),
                )
            )
    elif timing_check.status == "passed" and mechanism_check.status == "passed":
        conclusion = "mechanism_supported_not_causal"
        checks.append(
            _check(
                "causal_sufficiency",
                "partially_supported",
                (
                    "The supplied evidence supports the proposed mechanism, "
                    "but observational evidence does not prove causality."
                ),
                "已提供的证据支持所提机制，但观察性证据不能证明因果关系。",
            )
        )
    elif mechanism_check.status == "partially_supported":
        conclusion = "mechanism_partially_supported"
        checks.append(
            _check(
                "causal_sufficiency",
                "partially_supported",
                "Only part of the proposed transmission path is supported.",
                "所提传导路径只有一部分得到支持。",
            )
        )
    else:
        conclusion = "temporal_correlation_only"
        checks.append(
            _check(
                "causal_sufficiency",
                "missing_evidence",
                "The evidence does not verify the proposed transmission path.",
                "现有证据尚未验证所提传导路径。",
            )
        )

    confidence_breakdown = _confidence_breakdown(
        hypothesis.confidence,
        checks,
        conclusion,
    )
    summary_en, summary_zh = _summary(conclusion, checks)
    recommendation, recommendation_en, recommendation_zh = (
        _reviewer_recommendation(checks, conclusion)
    )
    unique_missing = _unique(missing)[:12]
    return CausalValidationResult(
        validator_model=validator_model,
        validator_version=VALIDATOR_VERSION,
        validated_at=datetime.now(UTC),
        conclusion=conclusion,
        recalculated_confidence=confidence_breakdown.final_confidence,
        time_window_hours=time_window_hours,
        checks=checks,
        alternative_explanations=hypothesis.counterevidence,
        evidence_sources=_validation_sources(structured_evidence),
        evidence_facts=_validation_facts(
            structured_evidence,
            checks=checks,
        ),
        missing_evidence=unique_missing,
        confidence_breakdown=confidence_breakdown,
        reasoning_trace=_reasoning_trace(checks),
        next_data_suggestions=_next_data_suggestions(unique_missing, checks),
        reviewer_recommendation=recommendation,
        recommendation_en=recommendation_en,
        recommendation_zh=recommendation_zh,
        summary_en=summary_en,
        summary_zh=summary_zh,
    )


def call_validator_agent(
    items: list[tuple[ModelLogicHypothesis, CausalValidationResult]],
    *,
    structured_evidence: dict[str, Any],
    allowed_refs: dict[tuple[str, str], set[str]],
    settings: Settings,
    transport: httpx.BaseTransport | None = None,
) -> dict[tuple[str, str], ModelCausalValidation]:
    """Run a separately prompted local model; failure leaves rule results intact."""
    if not items or settings.llm_provider == "mock":
        return {}
    messages = [
        {"role": "system", "content": VALIDATOR_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "hypotheses": [
                        {
                            "hypothesis": hypothesis.model_dump(mode="json"),
                            "deterministic_validation": validation.model_dump(mode="json"),
                            "allowed_evidence_refs": sorted(
                                allowed_refs[
                                    (
                                        hypothesis.premise_candidate_id,
                                        hypothesis.outcome_candidate_id,
                                    )
                                ]
                            ),
                        }
                        for hypothesis, validation in items
                    ],
                    "structured_evidence": structured_evidence,
                },
                ensure_ascii=False,
            ),
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
                    "name": "causal_validations",
                    "strict": True,
                    "schema": schema,
                },
            },
        }
    else:
        return {}
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
            content = (
                data["message"]["content"]
                if settings.llm_provider == "ollama"
                else data["choices"][0]["message"]["content"]
            )
            batch = _validated_agent_batch(content)
            return {
                (
                    validation.premise_candidate_id,
                    validation.outcome_candidate_id,
                ): validation
                for validation in batch.validations
            }
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
            ValidationError,
        ):
            continue
    return {}


def merge_agent_validation(
    rule_result: CausalValidationResult,
    agent_result: ModelCausalValidation | None,
    *,
    allowed_refs: set[str],
    validator_model: str,
) -> CausalValidationResult:
    """Let the model downgrade rule results, but never bypass evidence gates."""
    if agent_result is None:
        return rule_result
    agent_checks = {check.check_key: check for check in agent_result.checks}
    merged_checks = []
    for rule_check in rule_result.checks:
        agent_check = agent_checks.get(rule_check.check_key)
        if (
            agent_check is None
            or rule_check.status == "not_applicable"
            or STATUS_RANK[agent_check.status] > STATUS_RANK[rule_check.status]
        ):
            merged_checks.append(rule_check)
            continue
        merged_checks.append(
            CausalValidationCheck(
                check_key=rule_check.check_key,
                status=agent_check.status,
                score=STATUS_SCORE[agent_check.status],
                explanation_en=agent_check.explanation_en,
                explanation_zh=agent_check.explanation_zh,
                evidence_refs=[ref for ref in agent_check.evidence_refs if ref in allowed_refs],
            )
        )
    conclusion = (
        agent_result.conclusion
        if CONCLUSION_RANK[agent_result.conclusion] <= CONCLUSION_RANK[rule_result.conclusion]
        else rule_result.conclusion
    )
    original_confidence = (
        rule_result.confidence_breakdown.original_confidence
        if rule_result.confidence_breakdown is not None
        else rule_result.recalculated_confidence
    )
    confidence_breakdown = _confidence_breakdown(
        original_confidence,
        merged_checks,
        conclusion,
        validator_cap=agent_result.recalculated_confidence,
    )
    missing_evidence = _unique(
        [
            *rule_result.missing_evidence,
            *agent_result.missing_evidence,
        ]
    )[:12]
    summary_en, summary_zh = _summary(conclusion, merged_checks)
    recommendation, recommendation_en, recommendation_zh = (
        _reviewer_recommendation(merged_checks, conclusion)
    )
    return CausalValidationResult(
        validator_model=validator_model,
        validator_version=VALIDATOR_VERSION,
        validated_at=datetime.now(UTC),
        conclusion=conclusion,
        recalculated_confidence=confidence_breakdown.final_confidence,
        time_window_hours=rule_result.time_window_hours,
        checks=merged_checks,
        alternative_explanations=_unique(
            [
                *rule_result.alternative_explanations,
                *agent_result.alternative_explanations,
            ]
        )[:8],
        evidence_sources=rule_result.evidence_sources,
        evidence_facts=_mark_validation_facts(
            rule_result.evidence_facts,
            merged_checks,
        ),
        missing_evidence=missing_evidence,
        confidence_breakdown=confidence_breakdown,
        reasoning_trace=_reasoning_trace(merged_checks),
        next_data_suggestions=_next_data_suggestions(
            missing_evidence,
            merged_checks,
        ),
        reviewer_recommendation=recommendation,
        recommendation_en=recommendation_en,
        recommendation_zh=recommendation_zh,
        summary_en=summary_en,
        summary_zh=summary_zh,
    )


def allowed_evidence_refs(
    hypothesis: ModelLogicHypothesis,
    *,
    premise: dict[str, Any],
    outcome: dict[str, Any],
    structured_evidence: dict[str, Any],
) -> set[str]:
    """Return the closed evidence-ID set that a validator may cite."""
    refs: set[str] = set()
    for candidate in (premise, outcome):
        candidate_id = candidate.get("candidate_id")
        document_id = candidate.get("document_id")
        if candidate_id is not None:
            refs.update(
                {
                    str(candidate_id),
                    f"candidate:{candidate_id}",
                }
            )
        if document_id is not None:
            refs.update(
                {
                    str(document_id),
                    f"document:{document_id}",
                }
            )
    refs.update(f"document:{value}" for value in hypothesis.evidence_document_ids)
    for rows in structured_evidence.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("evidence_id"):
                refs.add(str(row["evidence_id"]))
    return refs


def _validated_agent_batch(content: str) -> ModelCausalValidationBatch:
    raw = json.loads(content)
    if not isinstance(raw, dict) or not isinstance(
        raw.get("validations"),
        list,
    ):
        raise ValueError("validator response must contain validations")
    validations = []
    for item in raw["validations"][:12]:
        if not isinstance(item, dict):
            continue
        normalized = dict(item)
        normalized["recalculated_confidence"] = min(
            0.75,
            max(0, _float(normalized.get("recalculated_confidence"))),
        )
        try:
            validations.append(ModelCausalValidation.model_validate(normalized))
        except (TypeError, ValidationError):
            continue
    return ModelCausalValidationBatch(validations=validations)


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

    schema = compatible(ModelCausalValidationBatch.model_json_schema())
    if not isinstance(schema, dict):
        raise TypeError("validator JSON schema must be an object")
    return schema


def _check(
    key: CausalCheckKey,
    status: CausalCheckStatus,
    explanation_en: str,
    explanation_zh: str,
    evidence_refs: Sequence[str | None] | None = None,
) -> CausalValidationCheck:
    return CausalValidationCheck(
        check_key=key,
        status=status,
        score=STATUS_SCORE[status],
        explanation_en=explanation_en,
        explanation_zh=explanation_zh,
        evidence_refs=_unique(
            [ref for ref in (evidence_refs or []) if ref is not None]
        )[:12],
    )


def _chain_text(
    hypothesis: ModelLogicHypothesis,
    premise: dict[str, Any],
    outcome: dict[str, Any],
) -> str:
    return " ".join(
        [
            hypothesis.title,
            hypothesis.rationale,
            *(step.text for step in hypothesis.steps),
            str(premise.get("event_type") or ""),
            str(premise.get("title") or ""),
            str(premise.get("summary") or ""),
            str(outcome.get("event_type") or ""),
            str(outcome.get("title") or ""),
            str(outcome.get("summary") or ""),
        ]
    ).casefold()


def _time_window_hours(
    text: str,
    *,
    policy_chain: bool,
    default: int,
) -> int:
    if policy_chain:
        return 72
    if _contains_any(text, DISASTER_TERMS):
        return 720
    return default


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _is_document_reference(reference: str) -> bool:
    return (
        reference.startswith("document:")
        or reference.startswith("candidate:")
        or reference.isdigit()
    )


def _evidence_refs_by_category(
    structured_evidence: dict[str, Any],
    category: str,
) -> set[str]:
    refs = set()
    for rows in structured_evidence.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("category") == category and row.get("evidence_id"):
                refs.add(str(row["evidence_id"]))
    return refs


def _market_outcome_evidence(
    outcome_text: str,
    *,
    structured_evidence: dict[str, Any],
    premise_at: datetime | None,
    outcome_at: datetime | None,
) -> tuple[str, set[str]]:
    if premise_at is None:
        return "unavailable", set()
    falling_terms = (
        "decline",
        "lower",
        "slump",
        "sell-off",
        "selloff",
        "drop",
        "fall",
        "baisse",
        "下跌",
        "走低",
        "暴跌",
        "回落",
    )
    rising_terms = (
        "rise",
        "higher",
        "rally",
        "gain",
        "surge",
        "hausse",
        "上涨",
        "走高",
        "反弹",
        "大涨",
    )
    direction = (
        -1
        if any(term in outcome_text for term in falling_terms)
        else (1 if any(term in outcome_text for term in rising_terms) else 0)
    )
    if direction == 0:
        return "not_applicable", set()
    if "nasdaq" in outcome_text or "纳斯达克" in outcome_text:
        series_ids = {"NASDAQCOM"}
    elif (
        "s&p" in outcome_text
        or "wall street" in outcome_text
        or "stock" in outcome_text
        or "equity" in outcome_text
        or "actions" in outcome_text
        or "股市" in outcome_text
        or "股票" in outcome_text
        or "美股" in outcome_text
        or "标普" in outcome_text
    ):
        series_ids = {"SP500", "NASDAQCOM"}
    else:
        return "not_applicable", set()
    rows = structured_evidence.get("fred_observations", [])
    if not isinstance(rows, list):
        return "unavailable", set()
    grouped: dict[
        str,
        list[tuple[datetime, float, str]],
    ] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("series_id") not in series_ids:
            continue
        observed_at = _parse_datetime(row.get("observed_on"))
        value = _optional_float(row.get("value"))
        evidence_id = row.get("evidence_id")
        if observed_at is None or value is None or evidence_id is None:
            continue
        grouped.setdefault(str(row["series_id"]), []).append((observed_at, value, str(evidence_id)))
    deadline = max(
        premise_at + timedelta(days=3),
        outcome_at or premise_at,
    )
    comparisons: list[bool] = []
    refs: set[str] = set()
    for observations in grouped.values():
        observations.sort(key=lambda item: item[0])
        prior = next(
            (item for item in reversed(observations) if item[0].date() < premise_at.date()),
            None,
        )
        after = next(
            (
                item
                for item in observations
                if premise_at.date() <= item[0].date() <= deadline.date()
            ),
            None,
        )
        if prior is None or after is None:
            continue
        refs.update({prior[2], after[2]})
        change = after[1] - prior[1]
        comparisons.append(change < 0 if direction < 0 else change > 0)
    if not comparisons:
        return "unavailable", refs
    if any(comparisons):
        return "verified", refs
    return "contradicted", refs


def _validation_sources(
    structured_evidence: dict[str, Any],
) -> list[CausalEvidenceSourceView]:
    rows = structured_evidence.get("source_health", [])
    if not isinstance(rows, list):
        return []
    sources = []
    for row in rows[:8]:
        if not isinstance(row, dict):
            continue
        try:
            sources.append(CausalEvidenceSourceView.model_validate(row))
        except ValidationError:
            continue
    return sources


def _validation_facts(
    structured_evidence: dict[str, Any],
    *,
    checks: list[CausalValidationCheck],
) -> list[CausalEvidenceFactView]:
    referenced = {reference for check in checks for reference in check.evidence_refs}
    facts: list[CausalEvidenceFactView] = []
    seen: set[str] = set()
    for rows in structured_evidence.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict) or not row.get("evidence_id"):
                continue
            evidence_id = str(row["evidence_id"])
            if evidence_id in seen:
                continue
            fact = _evidence_fact(row)
            if fact is None:
                continue
            seen.add(evidence_id)
            facts.append(fact)
    facts.sort(
        key=lambda fact: (
            fact.evidence_id not in referenced,
            _fact_category_rank(fact.category),
            fact.observed_at or "",
        )
    )
    return _mark_validation_facts(facts[:20], checks)


def _mark_validation_facts(
    facts: Sequence[CausalEvidenceFactView],
    checks: Sequence[CausalValidationCheck],
) -> list[CausalEvidenceFactView]:
    """Expose which validation gates actually cited each source-backed fact."""
    used_by: dict[str, list[CausalCheckKey]] = {}
    for check in checks:
        for reference in check.evidence_refs:
            keys = used_by.setdefault(reference, [])
            if check.check_key not in keys:
                keys.append(check.check_key)
    return [
        fact.model_copy(
            update={"used_by_checks": used_by.get(fact.evidence_id, [])},
        )
        for fact in facts
    ]


def _evidence_fact(
    row: dict[str, Any],
) -> CausalEvidenceFactView | None:
    evidence_id = str(row.get("evidence_id") or "")
    category = str(row.get("category") or "observation")
    source = str(row.get("source") or "")
    source_url = str(row.get("source_url") or "")
    if not evidence_id or not source or not source_url.startswith("http"):
        return None
    observed_at = row.get("observed_on") or row.get("published_at")
    if category == "treasury_yield":
        label = "U.S. Treasury 2Y / 10Y yields"
        value_text = (
            f"2Y {_display_value(row.get('two_year'))}% · "
            f"10Y {_display_value(row.get('ten_year'))}%"
        )
    elif category == "official_policy_communication":
        label = str(row.get("title") or "Federal Reserve communication")
        value_text = str(row.get("summary") or label)
    elif category == "market_expectation":
        label = (
            "Atlanta Fed MPT · "
            f"quarter from {(row.get('reference_start') or '—')!s}"
        )
        value_text = (
            f"mean {_display_value(row.get('mean_rate_bps'))} bps · "
            f"cut {_display_value(row.get('cut_probability'))}% · "
            f"hike {_display_value(row.get('hike_probability'))}%"
        )
    elif row.get("series_id"):
        label = str(row.get("label") or row["series_id"])
        value_text = (
            f"{_display_value(row.get('value'))} {str(row.get('unit') or '').strip()}"
        ).strip()
    elif row.get("symbol"):
        label = str(row["symbol"])
        value_text = f"close {_display_value(row.get('close'))}"
        if row.get("change_percent") is not None:
            value_text += f" · {_display_value(row.get('change_percent'))}%"
    elif row.get("indicator"):
        label = str(row["indicator"])
        observed_at = str(row.get("year") or observed_at or "")
        value_text = (
            f"{_display_value(row.get('value'))} {str(row.get('unit') or '').strip()}"
        ).strip()
    else:
        return None
    try:
        return CausalEvidenceFactView(
            evidence_id=evidence_id,
            category=category,
            label=label[:500],
            observed_at=str(observed_at)[:100] if observed_at else None,
            value_text=value_text[:1_000],
            source=source[:255],
            source_url=source_url[:2_000],
        )
    except ValidationError:
        return None


def _fact_category_rank(category: str) -> int:
    order = {
        "official_policy_communication": 0,
        "market_expectation": 1,
        "treasury_yield": 2,
        "market_index": 3,
        "policy_rate": 4,
        "policy_target": 5,
        "inflation_expectation": 6,
        "market_volatility": 7,
        "commodity_price": 8,
        "currency_index": 9,
        "credit_spread": 10,
        "economic_context": 11,
    }
    return order.get(category, 20)


def _display_value(value: object) -> str:
    number = _optional_float(value)
    if number is None:
        return "—"
    return f"{number:,.4f}".rstrip("0").rstrip(".")


def _treasury_yields_rose(
    structured_evidence: dict[str, Any],
    *,
    premise_at: datetime | None,
    outcome_at: datetime | None,
) -> tuple[bool, set[str]]:
    if premise_at is None:
        return False, set()
    rows = structured_evidence.get("treasury_yields", [])
    if not isinstance(rows, list):
        return False, set()
    observations = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        observed_at = _parse_datetime(row.get("observed_on"))
        two_year = _optional_float(row.get("two_year"))
        ten_year = _optional_float(row.get("ten_year"))
        if observed_at is None or two_year is None or ten_year is None:
            continue
        observations.append((observed_at, two_year, ten_year, row))
    observations.sort(key=lambda item: item[0])
    prior = next(
        (item for item in reversed(observations) if item[0].date() < premise_at.date()),
        None,
    )
    deadline = max(
        premise_at + timedelta(days=3),
        outcome_at or premise_at,
    )
    after = next(
        (item for item in observations if premise_at.date() <= item[0].date() <= deadline.date()),
        None,
    )
    refs = {
        str(item[3]["evidence_id"])
        for item in (prior, after)
        if item is not None and item[3].get("evidence_id")
    }
    if prior is None or after is None:
        return False, refs
    return after[1] > prior[1] and after[2] > prior[2], refs


def _market_expectations_repriced(
    structured_evidence: dict[str, Any],
    *,
    premise_at: datetime | None,
    outcome_at: datetime | None,
) -> tuple[str, set[str]]:
    if premise_at is None:
        return "unavailable", set()
    rows = structured_evidence.get("market_expectations", [])
    if not isinstance(rows, list):
        return "unavailable", set()
    grouped: dict[str, list[tuple[datetime, dict[str, Any]]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        observed_at = _parse_datetime(row.get("observed_on"))
        reference_start = str(row.get("reference_start") or "")
        if observed_at is None or not reference_start:
            continue
        grouped.setdefault(reference_start, []).append((observed_at, row))
    deadline = max(premise_at + timedelta(days=3), outcome_at or premise_at)
    comparisons: list[bool] = []
    refs: set[str] = set()
    for observations in grouped.values():
        observations.sort(key=lambda item: item[0])
        prior = next(
            (
                item
                for item in reversed(observations)
                if item[0].date() < premise_at.date()
            ),
            None,
        )
        after = next(
            (
                item
                for item in observations
                if premise_at.date() < item[0].date() <= deadline.date()
            ),
            None,
        )
        if prior is None or after is None:
            continue
        for item in (prior, after):
            evidence_id = item[1].get("evidence_id")
            if evidence_id:
                refs.add(str(evidence_id))
        comparisons.append(_expectation_change_is_material(prior[1], after[1]))
    if not comparisons:
        return "unavailable", refs
    if any(comparisons):
        return "verified", refs
    return "stable", refs


def _expectation_change_is_material(
    prior: dict[str, Any],
    after: dict[str, Any],
) -> bool:
    thresholds = {
        "mean_rate_bps": 2.0,
        "mode_rate_bps": 2.0,
        "cut_probability": 2.0,
        "hike_probability": 2.0,
    }
    for key, threshold in thresholds.items():
        before_value = _optional_float(prior.get(key))
        after_value = _optional_float(after.get(key))
        if (
            before_value is not None
            and after_value is not None
            and abs(after_value - before_value) >= threshold
        ):
            return True
    return False


def _recalculate_confidence(
    original_confidence: float,
    checks: list[CausalValidationCheck],
    conclusion: CausalConclusion,
) -> float:
    return _confidence_breakdown(
        original_confidence,
        checks,
        conclusion,
    ).final_confidence


def _confidence_breakdown(
    original_confidence: float,
    checks: Sequence[CausalValidationCheck],
    conclusion: CausalConclusion,
    *,
    validator_cap: float | None = None,
) -> CausalConfidenceBreakdown:
    """Return every weighted contribution and every cap behind the score."""
    applicable = [check for check in checks if check.status != "not_applicable"]
    denominator = sum(CHECK_WEIGHTS[check.check_key] for check in applicable)
    weighted = (
        sum(
            CHECK_WEIGHTS[check.check_key] * check.score
            for check in applicable
        )
        / denominator
        if denominator
        else 0
    )
    conclusion_cap = _confidence_cap(conclusion)
    limits = {
        "original_model_confidence": original_confidence,
        "weighted_validation_gates": weighted,
        "conclusion_safety_cap": conclusion_cap,
    }
    if validator_cap is not None:
        limits["independent_validator_cap"] = validator_cap
    limiting_factor = min(limits, key=lambda key: limits[key])
    final_confidence = round(min(limits.values()), 4)
    components = [
        CausalConfidenceComponent(
            check_key=check.check_key,
            weight=round(
                CHECK_WEIGHTS[check.check_key] / denominator,
                4,
            )
            if denominator and check.status != "not_applicable"
            else 0,
            score=check.score,
            contribution=round(
                CHECK_WEIGHTS[check.check_key] * check.score / denominator,
                4,
            )
            if denominator and check.status != "not_applicable"
            else 0,
            status=check.status,
        )
        for check in checks
    ]
    return CausalConfidenceBreakdown(
        original_confidence=round(original_confidence, 4),
        weighted_gate_score=round(weighted, 4),
        conclusion_cap=conclusion_cap,
        validator_cap=validator_cap,
        final_confidence=final_confidence,
        limiting_factor=limiting_factor,
        components=components,
    )


def _confidence_cap(conclusion: CausalConclusion) -> float:
    if conclusion == "temporal_correlation_only":
        return 0.45
    if conclusion == "mechanism_partially_supported":
        return 0.6
    return 0.75


def _reasoning_trace(
    checks: Sequence[CausalValidationCheck],
) -> list[CausalReasoningTraceStep]:
    return [
        CausalReasoningTraceStep(
            sequence=index,
            check_key=check.check_key,
            status=check.status,
            score=check.score,
            explanation_en=check.explanation_en,
            explanation_zh=check.explanation_zh,
            evidence_refs=check.evidence_refs,
        )
        for index, check in enumerate(checks, start=1)
    ]


def _reviewer_recommendation(
    checks: Sequence[CausalValidationCheck],
    conclusion: CausalConclusion,
) -> tuple[ReviewerRecommendation, str, str]:
    by_key = {check.check_key: check for check in checks}
    premise = by_key.get("premise_reported")
    timing = by_key.get("outcome_time_window")
    mechanism = by_key.get("mechanism_evidence")
    if (
        (premise is not None and premise.status == "failed")
        or (timing is not None and timing.status == "failed")
    ):
        return (
            "rejected",
            "Reject: a reported endpoint or the required event ordering failed validation.",
            "建议驳回：至少一个已报道端点或必要的事件先后顺序未通过验证。",
        )
    if (
        conclusion != "temporal_correlation_only"
        and mechanism is not None
        and mechanism.status in {"passed", "partially_supported"}
    ):
        return (
            "revised_accepted",
            (
                "Revise and accept as a non-causal analytical hypothesis; "
                "retain the evidence limits and alternatives."
            ),
            "建议修改后接受为非因果分析假设，并保留证据限制与替代解释。",
        )
    return (
        "deferred",
        "Defer until the missing mechanism or market evidence is supplied.",
        "建议暂缓，等待补充缺失的机制或市场证据。",
    )


def _next_data_suggestions(
    missing_evidence: Sequence[str],
    checks: Sequence[CausalValidationCheck],
) -> list[CausalNextDataSuggestion]:
    """Translate vague gaps into concrete, actionable evidence requests."""
    text = " ".join(missing_evidence).casefold()
    suggestions: list[CausalNextDataSuggestion] = []

    def add(
        key: str,
        priority: EvidencePriority,
        label_en: str,
        label_zh: str,
        reason_en: str,
        reason_zh: str,
        source_url: str | None,
    ) -> None:
        if any(item.key == key for item in suggestions):
            return
        suggestions.append(
            CausalNextDataSuggestion(
                key=key,
                priority=priority,
                label_en=label_en,
                label_zh=label_zh,
                reason_en=reason_en,
                reason_zh=reason_zh,
                source_url=source_url,
            )
        )

    if any(term in text for term in ("expectation", "rate-path", "mpt", "fedwatch")):
        add(
            "rate_expectations",
            "high",
            "Pre/post policy-rate expectation observations",
            "决策前后的政策利率预期观测",
            "Needed to determine whether the decision was already priced in.",
            "用于判断决策是否已被市场提前计价。",
            "https://www.atlantafed.org/cqer/research/market-probability-tracker",
        )
    if any(term in text for term in ("2y", "10y", "treasury", "yield")):
        add(
            "treasury_yields",
            "high",
            "2Y and 10Y Treasury yields around the event",
            "事件前后的2年期、10年期美债收益率",
            "Validates or falsifies the proposed bond-market transmission step.",
            "用于验证或反驳所提债券市场传导步骤。",
            "https://home.treasury.gov/resource-center/data-chart-center/interest-rates",
        )
    if any(term in text for term in ("fomc", "powell", "official")):
        add(
            "official_policy",
            "high",
            "FOMC statement, projections, or Powell communication",
            "FOMC声明、经济预测或鲍威尔沟通",
            "Anchors the policy signal to a primary source instead of a paraphrase.",
            "用第一手资料确定政策信号，而不是依赖转述。",
            "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
        )
    if any(term in text for term in ("timestamp", "dated", "ordering", "time")):
        add(
            "precise_timestamps",
            "high",
            "Precise publication and market observation timestamps",
            "精确的发布时间与市场观测时间戳",
            "Required to establish that the proposed cause precedes the outcome.",
            "用于确认所提原因确实先于结果发生。",
            None,
        )
    if any(term in text for term in ("s&p", "nasdaq", "market observation")):
        add(
            "equity_response",
            "medium",
            "S&P 500 and Nasdaq observations in the validation window",
            "验证窗口内的标普500与纳斯达克观测",
            "Confirms whether the claimed market result actually occurred.",
            "用于确认所述市场结果是否确实发生。",
            "https://fred.stlouisfed.org/",
        )
    alternative_check = next(
        (
            check
            for check in checks
            if check.check_key == "alternative_explanations"
        ),
        None,
    )
    if (
        "competing explanation" in text
        or (
            alternative_check is not None
            and alternative_check.status in {"missing_evidence", "failed"}
        )
    ):
        add(
            "alternative_explanations",
            "medium",
            "Earnings, sector, fiscal, and geopolitical alternatives",
            "财报、行业、财政与地缘政治替代解释",
            "Tests whether a stronger contemporaneous explanation fits the outcome.",
            "用于检验是否存在解释力更强的同期因素。",
            None,
        )
    mechanism_check = next(
        (check for check in checks if check.check_key == "mechanism_evidence"),
        None,
    )
    if (
        mechanism_check is not None
        and mechanism_check.status in {"missing_evidence", "partially_supported"}
    ):
        add(
            "mechanism_steps",
            "high",
            "One source-backed observation for every inferred step",
            "每个推断步骤至少一条有来源的观测",
            "Prevents an unsupported intermediate mechanism from bridging two events.",
            "避免由无证据的中间机制强行连接两个事件。",
            None,
        )
    return suggestions[:8]


def _summary(
    conclusion: CausalConclusion,
    checks: Sequence[CausalValidationCheck],
) -> tuple[str, str]:
    by_key = {check.check_key: check for check in checks}
    timing_verified = by_key.get("outcome_time_window") is not None and (
        by_key["outcome_time_window"].status == "passed"
    )
    mechanism_status = (
        by_key["mechanism_evidence"].status
        if "mechanism_evidence" in by_key
        else "missing_evidence"
    )
    expectation_status = (
        by_key["market_expectations"].status
        if "market_expectations" in by_key
        else "missing_evidence"
    )
    if conclusion == "mechanism_supported_not_causal":
        return (
            (
                "The event order and proposed transmission mechanism were "
                "supported by this validation window"
                + (
                    ", including market-expectation evidence"
                    if expectation_status == "passed"
                    else ""
                )
                + "; the result remains an observational inference, not proof of causality."
            ),
            (
                "本次验证窗口支持事件先后顺序与所提传导机制"
                + ("，并包含市场预期证据" if expectation_status == "passed" else "")
                + "；结论仍是观察性推断，并非因果证明。"
            ),
        )
    if conclusion == "mechanism_partially_supported":
        return (
            (
                "The outcome timing is "
                + ("verified" if timing_verified else "not fully verified")
                + f", while the mechanism gate is {mechanism_status.replace('_', ' ')} "
                + f"and the expectations gate is {expectation_status.replace('_', ' ')}. "
                "Retain only the supported steps and send the remainder to review."
            ),
            (
                f"结果时间顺序{'已验证' if timing_verified else '尚未完整验证'}；"
                f"机制门状态为{_status_zh(mechanism_status)}，"
                f"市场预期门状态为{_status_zh(expectation_status)}。"
                "应只保留已有支持的步骤，其余交由人工复核。"
            ),
        )
    return (
        (
            "The event timing is "
            + ("consistent" if timing_verified else "not fully established")
            + f", but the mechanism gate is {mechanism_status.replace('_', ' ')} "
            + f"and the expectations gate is {expectation_status.replace('_', ' ')}. "
            "The current evidence therefore supports at most temporal correlation."
        ),
        (
            f"事件时间关系{'一致' if timing_verified else '尚未完整确立'}；"
            f"机制门状态为{_status_zh(mechanism_status)}，"
            f"市场预期门状态为{_status_zh(expectation_status)}。"
            "因此当前证据最多只能支持时间相关性。"
        ),
    )


def _status_zh(status: CausalCheckStatus) -> str:
    return {
        "passed": "已通过",
        "partially_supported": "部分支持",
        "missing_evidence": "证据不足",
        "failed": "未通过",
        "not_applicable": "不适用",
    }[status]


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _optional_float(value: object) -> float | None:
    try:
        if value in (None, "", "."):
            return None
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _float(value: object) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))
