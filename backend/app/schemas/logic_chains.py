"""Contracts for local-AI multi-step logic hypotheses and review feedback."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.research import ChatGPTResearchReview

LogicStepType = Literal[
    "reported_event",
    "economic_context",
    "market_observation",
    "inferred_mechanism",
    "possible_outcome",
    "counterevidence",
]
LogicChainStatus = Literal[
    "suggested",
    "accepted",
    "revised_accepted",
    "deferred",
    "rejected",
]
CausalCheckKey = Literal[
    "premise_reported",
    "outcome_time_window",
    "mechanism_evidence",
    "market_expectations",
    "alternative_explanations",
    "causal_sufficiency",
]
CausalCheckStatus = Literal[
    "passed",
    "partially_supported",
    "missing_evidence",
    "failed",
    "not_applicable",
]
CausalConclusion = Literal[
    "temporal_correlation_only",
    "mechanism_partially_supported",
    "mechanism_supported_not_causal",
]
EvidenceSourceStatus = Literal[
    "ready",
    "partial",
    "unavailable",
    "not_configured",
]
ReviewerRecommendation = Literal[
    "revised_accepted",
    "deferred",
    "rejected",
]
EvidencePriority = Literal["high", "medium", "low"]


class ModelLogicStep(BaseModel):
    """One explicitly typed step in a model-proposed logic chain."""

    model_config = ConfigDict(extra="forbid")

    step_type: LogicStepType
    text: str = Field(min_length=3, max_length=600)
    candidate_id: str | None = Field(default=None, max_length=128)
    confidence: float = Field(default=0.5, ge=0, le=1)
    relevance: float = Field(default=0.5, ge=0, le=1)
    evidence_refs: list[str] = Field(default_factory=list, max_length=8)


class ModelLogicHypothesis(BaseModel):
    """One constrained hypothesis returned by the local model."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=500)
    premise_candidate_id: str = Field(min_length=1, max_length=128)
    outcome_candidate_id: str = Field(min_length=1, max_length=128)
    steps: list[ModelLogicStep] = Field(min_length=3, max_length=6)
    confidence: float = Field(ge=0, le=1)
    association_score: float = Field(default=0.5, ge=0, le=1)
    evidence_coverage_score: float = Field(default=0, ge=0, le=1)
    rationale: str = Field(min_length=3, max_length=2_000)
    evidence_document_ids: list[int] = Field(min_length=2, max_length=8)
    counterevidence: list[str] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def require_an_inferred_mechanism(self) -> ModelLogicHypothesis:
        """Separate AI inference from reported events in every hypothesis."""
        if self.premise_candidate_id == self.outcome_candidate_id:
            raise ValueError("premise and outcome candidates must differ")
        if not any(step.step_type == "inferred_mechanism" for step in self.steps):
            raise ValueError("a logic chain requires an inferred mechanism")
        return self


class ModelLogicHypothesisBatch(BaseModel):
    """Strict provider response."""

    model_config = ConfigDict(extra="forbid")

    hypotheses: list[ModelLogicHypothesis] = Field(max_length=12)


class CausalValidationCheck(BaseModel):
    """One auditable gate evaluated by the causal-validation agent."""

    model_config = ConfigDict(extra="forbid")

    check_key: CausalCheckKey
    status: CausalCheckStatus
    score: float = Field(ge=0, le=1)
    explanation_en: str = Field(min_length=3, max_length=1_000)
    explanation_zh: str = Field(min_length=3, max_length=1_000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=12)


class CausalEvidenceSourceView(BaseModel):
    """Actual provider result for the evidence window, without credentials."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=2, max_length=100)
    name: str = Field(min_length=2, max_length=255)
    status: EvidenceSourceStatus
    observation_count: int = Field(ge=0)
    message_en: str = Field(min_length=3, max_length=500)
    message_zh: str = Field(min_length=3, max_length=500)
    source_url: str = Field(min_length=8, max_length=2_000)


class CausalEvidenceFactView(BaseModel):
    """One compact source-backed fact retained with a validation result."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=3, max_length=255)
    category: str = Field(min_length=2, max_length=100)
    label: str = Field(min_length=2, max_length=500)
    observed_at: str | None = Field(default=None, max_length=100)
    value_text: str = Field(min_length=1, max_length=1_000)
    source: str = Field(min_length=2, max_length=255)
    source_url: str = Field(min_length=8, max_length=2_000)
    used_by_checks: list[CausalCheckKey] = Field(default_factory=list, max_length=6)


class CausalConfidenceComponent(BaseModel):
    """One transparent contribution to the validator's weighted gate score."""

    model_config = ConfigDict(extra="forbid")

    check_key: CausalCheckKey
    weight: float = Field(ge=0, le=1)
    score: float = Field(ge=0, le=1)
    contribution: float = Field(ge=0, le=1)
    status: CausalCheckStatus


class CausalConfidenceBreakdown(BaseModel):
    """How the displayed confidence was calculated and capped."""

    model_config = ConfigDict(extra="forbid")

    original_confidence: float = Field(ge=0, le=0.75)
    weighted_gate_score: float = Field(ge=0, le=1)
    conclusion_cap: float = Field(ge=0, le=0.75)
    validator_cap: float | None = Field(default=None, ge=0, le=0.75)
    final_confidence: float = Field(ge=0, le=0.75)
    limiting_factor: str = Field(min_length=3, max_length=100)
    components: list[CausalConfidenceComponent] = Field(
        min_length=1,
        max_length=6,
    )


class CausalReasoningTraceStep(BaseModel):
    """Ordered, inspectable validator trace; no hidden chain-of-thought."""

    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1, le=6)
    check_key: CausalCheckKey
    status: CausalCheckStatus
    score: float = Field(ge=0, le=1)
    explanation_en: str = Field(min_length=3, max_length=1_000)
    explanation_zh: str = Field(min_length=3, max_length=1_000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=12)


class CausalNextDataSuggestion(BaseModel):
    """Specific evidence that can raise or falsify the hypothesis."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=2, max_length=100)
    priority: EvidencePriority
    label_en: str = Field(min_length=3, max_length=500)
    label_zh: str = Field(min_length=3, max_length=500)
    reason_en: str = Field(min_length=3, max_length=1_000)
    reason_zh: str = Field(min_length=3, max_length=1_000)
    source_url: str | None = Field(default=None, max_length=2_000)


class CausalHistoricalCaseView(BaseModel):
    """A prior human-reviewed hypothesis used only as a comparison."""

    model_config = ConfigDict(extra="forbid")

    hypothesis_id: int = Field(gt=0)
    title: str = Field(min_length=3, max_length=500)
    reviewed_at: datetime
    decision: Literal[
        "accepted",
        "revised_accepted",
        "deferred",
        "rejected",
    ]
    similarity_score: float = Field(ge=0, le=1)
    original_confidence: float = Field(ge=0, le=0.75)
    validated_confidence: float | None = Field(default=None, ge=0, le=0.75)
    conclusion: CausalConclusion | None = None
    summary_en: str = Field(min_length=3, max_length=1_000)
    summary_zh: str = Field(min_length=3, max_length=1_000)


class CausalValidationResult(BaseModel):
    """Stored result from rules plus a separately prompted local validator."""

    model_config = ConfigDict(extra="forbid")

    validator_model: str = Field(min_length=3, max_length=255)
    validator_version: str = Field(min_length=3, max_length=100)
    validated_at: datetime
    conclusion: CausalConclusion
    recalculated_confidence: float = Field(ge=0, le=0.75)
    time_window_hours: int = Field(ge=1, le=8_760)
    checks: list[CausalValidationCheck] = Field(min_length=6, max_length=6)
    alternative_explanations: list[str] = Field(
        default_factory=list,
        max_length=8,
    )
    evidence_sources: list[CausalEvidenceSourceView] = Field(
        default_factory=list,
        max_length=8,
    )
    evidence_facts: list[CausalEvidenceFactView] = Field(
        default_factory=list,
        max_length=20,
    )
    missing_evidence: list[str] = Field(default_factory=list, max_length=12)
    confidence_breakdown: CausalConfidenceBreakdown | None = None
    reasoning_trace: list[CausalReasoningTraceStep] = Field(
        default_factory=list,
        max_length=6,
    )
    next_data_suggestions: list[CausalNextDataSuggestion] = Field(
        default_factory=list,
        max_length=8,
    )
    reviewer_recommendation: ReviewerRecommendation = "deferred"
    recommendation_en: str = Field(
        default="Defer pending additional evidence.",
        min_length=3,
        max_length=1_000,
    )
    recommendation_zh: str = Field(
        default="建议暂缓, 等待更多证据。",
        min_length=3,
        max_length=1_000,
    )
    summary_en: str = Field(min_length=3, max_length=2_000)
    summary_zh: str = Field(min_length=3, max_length=2_000)
    causality_is_confirmed: Literal[False] = False


class ModelCausalValidationCheck(BaseModel):
    """Constrained assessment emitted by the independent local validator."""

    model_config = ConfigDict(extra="forbid")

    check_key: CausalCheckKey
    status: CausalCheckStatus
    explanation_en: str = Field(min_length=3, max_length=1_000)
    explanation_zh: str = Field(min_length=3, max_length=1_000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=12)


class ModelCausalValidation(BaseModel):
    """One local-validator response tied to an existing hypothesis."""

    model_config = ConfigDict(extra="forbid")

    premise_candidate_id: str = Field(min_length=1, max_length=128)
    outcome_candidate_id: str = Field(min_length=1, max_length=128)
    checks: list[ModelCausalValidationCheck] = Field(
        min_length=6,
        max_length=6,
    )
    alternative_explanations: list[str] = Field(
        default_factory=list,
        max_length=8,
    )
    missing_evidence: list[str] = Field(default_factory=list, max_length=12)
    conclusion: CausalConclusion
    recalculated_confidence: float = Field(ge=0, le=0.75)
    summary_en: str = Field(min_length=3, max_length=2_000)
    summary_zh: str = Field(min_length=3, max_length=2_000)

    @model_validator(mode="after")
    def require_each_validation_gate_once(self) -> ModelCausalValidation:
        """Reject duplicated or omitted checks from the validator model."""
        keys = [check.check_key for check in self.checks]
        if len(set(keys)) != 6:
            raise ValueError("each causal validation gate is required once")
        return self


class ModelCausalValidationBatch(BaseModel):
    """Strict batch returned by the independent local validator."""

    model_config = ConfigDict(extra="forbid")

    validations: list[ModelCausalValidation] = Field(max_length=12)


class LogicChainHypothesisView(ModelLogicHypothesis):
    """Review state and provenance added to a model hypothesis."""

    id: int = Field(gt=0)
    cluster_job_id: int = Field(gt=0)
    premise_title: str
    outcome_title: str
    status: LogicChainStatus
    model_name: str
    prompt_version: str
    review_note: str | None
    suggested_correction: str | None
    decided_at: datetime | None
    composite_score: float = Field(ge=0, le=1)
    causal_validation: CausalValidationResult | None = None
    historical_cases: list[CausalHistoricalCaseView] = Field(
        default_factory=list,
        max_length=5,
    )
    chatgpt_review: ChatGPTResearchReview | None = None


class LogicChainResponse(BaseModel):
    """All reviewable multi-step hypotheses for one clustering snapshot."""

    model_config = ConfigDict(extra="forbid")

    cluster_job_id: int = Field(gt=0)
    hypothesis_count: int = Field(ge=0)
    training_signal_count: int = Field(ge=0)
    hypotheses: list[LogicChainHypothesisView]
    causality_is_confirmed: Literal[False] = False


class LogicChainGenerationResponse(LogicChainResponse):
    """Idempotent generation result."""

    generated_count: int = Field(ge=0)
    validated_count: int = Field(ge=0)


class LogicChainValidationResponse(LogicChainResponse):
    """Idempotent revalidation result."""

    validated_count: int = Field(ge=0)


class LogicChainReviewRequest(BaseModel):
    """A human decision plus reusable correction text."""

    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "accepted",
        "revised_accepted",
        "deferred",
        "rejected",
    ]
    reviewer_note: str | None = Field(default=None, max_length=2_000)
    suggested_correction: str | None = Field(default=None, max_length=4_000)


class LogicChainReviewSignalView(BaseModel):
    """One append-only feedback row for audit and future tuning."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(gt=0)
    hypothesis_id: int = Field(gt=0)
    decision: Literal[
        "accepted",
        "revised_accepted",
        "deferred",
        "rejected",
    ]
    reviewer_note: str | None
    suggested_correction: str | None
    created_at: datetime


class LogicChainTrainingSignalsResponse(BaseModel):
    """Review history that can be exported into a tuning dataset."""

    model_config = ConfigDict(extra="forbid")

    signal_count: int = Field(ge=0)
    signals: list[LogicChainReviewSignalView]


class VerifiedLogicMemoryView(BaseModel):
    """A human-approved, evidence-qualified prior mechanism for retrieval."""

    model_config = ConfigDict(extra="forbid")

    hypothesis_id: int = Field(gt=0)
    title: str = Field(min_length=3, max_length=500)
    status: Literal["accepted", "revised_accepted"]
    conclusion: Literal["mechanism_supported_not_causal"]
    validated_confidence: float = Field(ge=0.55, le=0.75)
    quality_score: float = Field(ge=0, le=1)
    steps: list[dict[str, Any]] = Field(min_length=3, max_length=8)
    evidence_facts: list[dict[str, Any]] = Field(min_length=2, max_length=20)
    counterevidence: list[str] = Field(default_factory=list, max_length=8)
    summary_en: str = Field(min_length=3, max_length=2_000)
    summary_zh: str = Field(min_length=3, max_length=2_000)
    reviewed_at: datetime
    model_name: str = Field(min_length=3, max_length=255)
    prompt_version: str = Field(min_length=3, max_length=100)


class VerifiedLogicMemoryResponse(BaseModel):
    """Qualified memories available for analogical retrieval and training export."""

    model_config = ConfigDict(extra="forbid")

    memory_count: int = Field(ge=0)
    memories: list[VerifiedLogicMemoryView]
    qualification_rule: str


class ExternalEvidenceItem(BaseModel):
    """A provenance-bearing evidence item supplied with an external example."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=3, max_length=500)
    source_url: str = Field(min_length=8, max_length=2_000)
    observed_at: str | None = Field(default=None, max_length=100)
    excerpt: str = Field(min_length=3, max_length=2_000)


class ExternalTrainingExampleImport(BaseModel):
    """One external example; it always enters quarantine as pending."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=500)
    instruction: str = Field(min_length=10, max_length=4_000)
    input_context: str = Field(min_length=10, max_length=20_000)
    ideal_response: str = Field(min_length=10, max_length=20_000)
    evidence: list[ExternalEvidenceItem] = Field(min_length=1, max_length=20)
    source_name: str = Field(min_length=2, max_length=255)
    source_url: str = Field(min_length=8, max_length=2_000)
    license_name: str = Field(min_length=2, max_length=255)


class ExternalTrainingImportRequest(BaseModel):
    """A bounded batch imported from a licensed external dataset."""

    model_config = ConfigDict(extra="forbid")

    examples: list[ExternalTrainingExampleImport] = Field(min_length=1, max_length=100)


class ExternalTrainingExampleView(BaseModel):
    """Review state for one isolated external example."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(gt=0)
    title: str
    source_name: str
    source_url: str
    license_name: str
    status: Literal["pending", "approved", "rejected"]
    quality_score: float = Field(ge=0, le=1)
    evidence_count: int = Field(ge=1)
    review_note: str | None = None
    created_at: datetime
    decided_at: datetime | None = None


class ExternalTrainingImportResponse(BaseModel):
    """Idempotent result of staging external data."""

    model_config = ConfigDict(extra="forbid")

    imported_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)


class ExternalTrainingExampleList(BaseModel):
    """External data inventory without returning full training text."""

    model_config = ConfigDict(extra="forbid")

    example_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    approved_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    examples: list[ExternalTrainingExampleView]


class ExternalTrainingReviewRequest(BaseModel):
    """Human gate before an external example can enter training export."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["approved", "rejected"]
    quality_score: float = Field(ge=0, le=1)
    review_note: str = Field(min_length=3, max_length=2_000)


class TrainingDatasetExample(BaseModel):
    """One chat-format supervised example with auditable provenance."""

    model_config = ConfigDict(extra="forbid")

    messages: list[dict[str, str]] = Field(min_length=3, max_length=3)
    metadata: dict[str, Any]


class TrainingDatasetResponse(BaseModel):
    """Dataset ready for JSONL serialization; it does not claim training occurred."""

    model_config = ConfigDict(extra="forbid")

    example_count: int = Field(ge=0)
    internal_verified_count: int = Field(ge=0)
    approved_external_count: int = Field(ge=0)
    dataset_format: Literal["chat_jsonl"] = "chat_jsonl"
    training_performed: Literal[False] = False
    examples: list[TrainingDatasetExample]
