"""Contracts for autonomous local research and optional ChatGPT review."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ResearchStepStatus = Literal[
    "verified",
    "partially_supported",
    "evidence_missing",
    "hypothesis",
]


class ModelResearchStep(BaseModel):
    """One auditable link in a proposed research chain."""

    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1, le=8)
    label: str = Field(min_length=3, max_length=600)
    status: ResearchStepStatus
    confidence: float = Field(ge=0, le=0.75)
    evidence_refs: list[str] = Field(max_length=10)


class ModelResearchScope(BaseModel):
    """Entities and physical dependencies considered by the local model."""

    model_config = ConfigDict(extra="forbid")

    companies: list[str] = Field(max_length=20)
    sectors: list[str] = Field(max_length=20)
    products: list[str] = Field(max_length=20)
    supply_chain_inputs: list[str] = Field(max_length=20)
    infrastructure: list[str] = Field(max_length=20)
    policies: list[str] = Field(max_length=20)
    geographies: list[str] = Field(max_length=20)


class ModelResearchHypothesis(BaseModel):
    """A falsifiable hypothesis with an evidence-bounded mechanism chain."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=500)
    premise: str = Field(min_length=3, max_length=1_000)
    outcome: str = Field(min_length=3, max_length=1_000)
    scope: ModelResearchScope
    steps: list[ModelResearchStep] = Field(min_length=3, max_length=8)
    counterarguments: list[str] = Field(max_length=8)
    evidence_gaps: list[str] = Field(max_length=10)
    confidence: float = Field(ge=0, le=0.75)


class ModelEquityResearchDimension(BaseModel):
    """One mandatory lens for a public-equity question."""

    model_config = ConfigDict(extra="forbid")

    dimension: Literal[
        "fundamentals_valuation",
        "technicals_positioning",
        "macro_liquidity",
        "supply_chain_geopolitics",
        "technology_competition",
    ]
    assessment: str = Field(min_length=3, max_length=1_500)
    signal: Literal["bullish", "bearish", "mixed", "unknown"]
    confidence: float = Field(ge=0, le=0.75)
    evidence_refs: list[str] = Field(max_length=12)
    evidence_gaps: list[str] = Field(max_length=10)


class ModelEquityDecisionFramework(BaseModel):
    """Conditional timing framework, never a personalized trade instruction."""

    model_config = ConfigDict(extra="forbid")

    timing_assessment: Literal[
        "attractive",
        "neutral",
        "extended",
        "insufficient_evidence",
    ]
    current_price_context: str = Field(min_length=3, max_length=1_500)
    valuation_scenarios: list[str] = Field(max_length=8)
    entry_conditions: list[str] = Field(max_length=8)
    invalidation_conditions: list[str] = Field(max_length=8)
    monitoring_indicators: list[str] = Field(max_length=12)
    not_personalized_advice: bool


class ModelAcademicResearchReport(BaseModel):
    """Paper-shaped synthesis with explicit evidence and limitations."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=500)
    abstract: str = Field(min_length=3, max_length=3_000)
    methodology: str = Field(min_length=3, max_length=3_000)
    evidence_chain: list[str] = Field(max_length=12)
    findings: list[str] = Field(max_length=12)
    alternative_explanations: list[str] = Field(max_length=10)
    limitations: list[str] = Field(max_length=10)
    conclusion: str = Field(min_length=3, max_length=3_000)
    evidence_refs: list[str] = Field(max_length=30)


class ModelNewsForecast(BaseModel):
    """One timestamped and falsifiable post-news possibility."""

    model_config = ConfigDict(extra="forbid")

    forecast_id: str = Field(min_length=3, max_length=160)
    anchor_evidence_ref: str = Field(min_length=3, max_length=160)
    anchor_title: str = Field(min_length=3, max_length=500)
    as_of: datetime
    hypothesis: str = Field(min_length=3, max_length=1_500)
    mechanism_chain: list[str] = Field(min_length=2, max_length=8)
    expected_outcome: str = Field(min_length=3, max_length=1_500)
    horizon_days: int = Field(ge=1, le=365)
    falsification_conditions: list[str] = Field(min_length=1, max_length=8)
    confidence: float = Field(ge=0, le=0.75)
    evaluation_mode: Literal["live_prospective", "historical_walk_forward"] = "live_prospective"
    status: Literal[
        "unresolved",
        "candidate_evidence_found",
        "supported",
        "partially_supported",
        "contradicted",
        "expired_insufficient_evidence",
    ] = "unresolved"
    supporting_evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    contradicting_evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    validation_summary: str | None = Field(default=None, max_length=2_000)
    last_validated_at: datetime | None = None


class ModelFactorCandidate(BaseModel):
    """One local-AI factor hypothesis before statistical validation."""

    model_config = ConfigDict(extra="forbid")

    factor_id: str = Field(min_length=3, max_length=160)
    name: str = Field(min_length=3, max_length=300)
    factor_type: Literal[
        "news_event",
        "market",
        "economic",
        "company",
        "supply_chain",
        "geopolitical",
        "interaction",
    ]
    direction: Literal["positive", "negative", "nonlinear", "regime_dependent"]
    transformation: Literal[
        "level",
        "change",
        "return",
        "surprise",
        "rolling_zscore",
        "binary_event",
        "interaction",
    ]
    lag_days: int = Field(ge=0, le=365)
    hypothesis: str = Field(min_length=3, max_length=1_500)
    evidence_refs: list[str] = Field(max_length=20)
    confidence: float = Field(ge=0, le=0.75)
    training_p_value: float | None = Field(default=None, ge=0, le=1)
    adjusted_q_value: float | None = Field(default=None, ge=0, le=1)


class ModelLinearTransmissionSegment(BaseModel):
    """One falsifiable adjacent segment inside a wider nonlinear hypothesis."""

    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1, le=8)
    source: str = Field(min_length=3, max_length=600)
    mechanism: str = Field(min_length=3, max_length=1_000)
    target: str = Field(min_length=3, max_length=600)
    direction: Literal["positive", "negative", "conditional", "unknown"]
    status: ResearchStepStatus
    evidence_refs: list[str] = Field(max_length=20)
    confidence: float = Field(ge=0, le=0.75)


class ModelNonlinearFactorLink(BaseModel):
    """An auditable nonlinear interaction between two or more factors."""

    model_config = ConfigDict(extra="forbid")

    link_id: str = Field(min_length=3, max_length=160)
    input_factor_ids: list[str] = Field(min_length=2, max_length=6)
    operator: Literal["and", "or", "threshold", "interaction", "regime_switch"]
    condition: str = Field(min_length=3, max_length=1_000)
    expected_output: str = Field(min_length=3, max_length=1_000)
    rationale: str = Field(min_length=3, max_length=1_500)
    evidence_refs: list[str] = Field(max_length=20)
    confidence: float = Field(ge=0, le=0.75)
    relationship_class: Literal[
        "exploratory_nonlinear",
        "partially_supported_nonlinear",
        "supported_nonlinear",
    ] = "exploratory_nonlinear"
    bridge_variables: list[str] = Field(default_factory=list, max_length=6)
    linear_segments: list[ModelLinearTransmissionSegment] = Field(
        default_factory=list,
        max_length=8,
    )


class ModelFactorReplicationTrial(BaseModel):
    """One non-overlapping, train-frozen replication window."""

    model_config = ConfigDict(extra="forbid")

    trial_id: str = Field(min_length=3, max_length=64)
    train_end_date: str
    test_start_date: str
    test_end_date: str
    selected_factor_ids: list[str] = Field(max_length=8)
    train_observations: int = Field(ge=0)
    test_observations: int = Field(ge=0)
    transaction_cost_bps: float = Field(ge=0, le=500)
    baseline_return: float | None = None
    strategy_return: float | None = None
    excess_return: float | None = None
    hit_rate: float | None = Field(default=None, ge=0, le=1)
    max_drawdown: float | None = Field(default=None, le=0)
    sharpe_like: float | None = None
    status: Literal["passed", "failed", "insufficient_data"]


class ModelFactorReplication(BaseModel):
    """Repeated independent trials plus one frozen prospective signal."""

    model_config = ConfigDict(extra="forbid")

    protocol_version: str = Field(min_length=3, max_length=96)
    trials: list[ModelFactorReplicationTrial] = Field(max_length=8)
    total_trials: int = Field(ge=0, le=8)
    valid_trials: int = Field(ge=0, le=8)
    passed_trials: int = Field(ge=0, le=8)
    pass_rate: float | None = Field(default=None, ge=0, le=1)
    median_excess_return: float | None = None
    pooled_mean_excess_return: float | None = None
    pooled_excess_ci_low: float | None = None
    pooled_excess_ci_high: float | None = None
    stable_factor_ids: list[str] = Field(max_length=8)
    retention_status: Literal[
        "insufficient_evidence",
        "rejected",
        "provisional_retained",
    ]
    retention_reason: str = Field(min_length=3, max_length=1_500)
    prospective_anchor_date: str | None = None
    prospective_factor_ids: list[str] = Field(default_factory=list, max_length=8)
    prospective_position: Literal["long", "short", "unavailable"] = "unavailable"
    future_validation_status: Literal["not_registered", "pending"] = "not_registered"
    leakage_guard: str = Field(min_length=3, max_length=1_500)


class ModelProfitValidation(BaseModel):
    """Chronological out-of-sample validation of one mined factor rule."""

    model_config = ConfigDict(extra="forbid")

    target_series_id: str = Field(min_length=1, max_length=160)
    target_name: str = Field(min_length=1, max_length=300)
    factor_ids: list[str] = Field(min_length=1, max_length=8)
    start_date: str | None = None
    end_date: str | None = None
    train_end_date: str | None = None
    forecast_horizon_days: int = Field(ge=1, le=90)
    train_observations: int = Field(ge=0)
    test_observations: int = Field(ge=0)
    transaction_cost_bps: float = Field(ge=0, le=500)
    baseline_return: float | None = None
    strategy_return: float | None = None
    excess_return: float | None = None
    hit_rate: float | None = Field(default=None, ge=0, le=1)
    max_drawdown: float | None = Field(default=None, le=0)
    sharpe_like: float | None = None
    status: Literal[
        "insufficient_data",
        "exploratory",
        "out_of_sample_positive",
        "out_of_sample_negative",
    ]
    signal_rule: str = Field(min_length=3, max_length=1_500)
    leakage_guard: str = Field(min_length=3, max_length=1_500)
    limitations: list[str] = Field(max_length=12)
    replication: ModelFactorReplication | None = None


class ModelCrossSectionAssetExposure(BaseModel):
    """Training-only factor exposure and latest bucket for one tradable asset."""

    model_config = ConfigDict(extra="forbid")

    series_id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=300)
    category: str = Field(min_length=1, max_length=100)
    train_observations: int = Field(ge=0)
    factor_loadings: dict[str, float] = Field(max_length=8)
    composite_exposure: float
    sector: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    neutralization_group: str | None = Field(default=None, max_length=160)
    latest_score: float | None = None
    latest_bucket: Literal["long", "short", "neutral", "unavailable"]
    robust_latest_score: float | None = None
    robust_latest_bucket: Literal["long", "short", "neutral", "unavailable"] = "unavailable"
    oos_mean_return: float | None = None


class ModelPortfolioContribution(BaseModel):
    """One linked contribution to compounded robust long-short performance."""

    model_config = ConfigDict(extra="forbid")

    dimension: Literal["asset_class", "industry", "region"]
    group: str = Field(min_length=1, max_length=160)
    contribution: float
    share_of_total: float | None = None
    long_periods: int = Field(ge=0)
    short_periods: int = Field(ge=0)


class ModelSurvivorshipAudit(BaseModel):
    """Point-in-time universe and delisting-return coverage disclosure."""

    model_config = ConfigDict(extra="forbid")

    point_in_time_membership_enforced: bool
    status: Literal["survivor_only", "partial_historical", "point_in_time_audited"]
    active_or_unknown_assets: int = Field(ge=0)
    historical_assets: int = Field(ge=0)
    discovered_delisted_assets: int = Field(default=0, ge=0)
    local_price_covered_delisted_assets: int = Field(default=0, ge=0)
    missing_price_delisted_assets: int = Field(default=0, ge=0)
    price_backfill_queued_assets: int = Field(default=0, ge=0)
    price_backfill_pending_assets: int = Field(default=0, ge=0)
    price_backfill_factor_ready_assets: int = Field(default=0, ge=0)
    price_backfill_partial_assets: int = Field(default=0, ge=0)
    price_backfill_unavailable_assets: int = Field(default=0, ge=0)
    price_backfill_ticker_reused_assets: int = Field(default=0, ge=0)
    identity_verified_assets: int = Field(default=0, ge=0)
    identity_unresolved_assets: int = Field(default=0, ge=0)
    identity_ambiguous_assets: int = Field(default=0, ge=0)
    identity_mismatched_assets: int = Field(default=0, ge=0)
    identity_lifecycle_conflict_assets: int = Field(default=0, ge=0)
    identity_sec_cik_assets: int = Field(default=0, ge=0)
    terminal_outcomes_verified: int = Field(default=0, ge=0)
    terminal_outcomes_requiring_evidence: int = Field(default=0, ge=0)
    terminal_outcomes_requiring_identity: int = Field(default=0, ge=0)
    terminal_evidence_assets_searched: int = Field(default=0, ge=0)
    terminal_evidence_cik_resolved: int = Field(default=0, ge=0)
    terminal_evidence_metadata_candidates: int = Field(default=0, ge=0)
    terminal_evidence_value_candidates: int = Field(default=0, ge=0)
    terminal_evidence_review_ready: int = Field(default=0, ge=0)
    terminal_evidence_accepted: int = Field(default=0, ge=0)
    supporting_evidence_accepted: int = Field(default=0, ge=0)
    terminal_evidence_needs_more: int = Field(default=0, ge=0)
    terminal_evidence_lifecycle_segmented_assets: int = Field(default=0, ge=0)
    terminal_evidence_body_contact_required: int = Field(default=0, ge=0)
    terminal_evidence_lifecycle_conflicts: int = Field(default=0, ge=0)
    lifecycle_catalog_start: str | None = None
    lifecycle_catalog_end: str | None = None
    assets_with_explicit_lifecycle: int = Field(ge=0)
    delisting_returns_covered: int = Field(ge=0)
    delisting_returns_missing: int = Field(ge=0)
    min_eligible_assets: int = Field(ge=0)
    median_eligible_assets: float = Field(ge=0)
    max_eligible_assets: int = Field(ge=0)
    methodology: str = Field(min_length=3, max_length=2_000)
    known_gaps: list[str] = Field(max_length=12)


class ModelCrossSectionRobustness(BaseModel):
    """Rolling, group-neutral and multiple-testing-adjusted portfolio audit."""

    model_config = ConfigDict(extra="forbid")

    training_mode: Literal["rolling_walk_forward"] = "rolling_walk_forward"
    training_window_rebalances: int = Field(ge=24, le=1_000)
    reestimate_every_rebalances: int = Field(ge=1, le=100)
    neutralization_dimensions: list[str] = Field(min_length=1, max_length=6)
    neutralization_group_count: int = Field(ge=0, le=100)
    candidate_factor_tests: int = Field(ge=0, le=100)
    adjusted_significant_factors: int = Field(ge=0, le=100)
    factor_ids: list[str] = Field(max_length=8)
    multiple_testing_method: str = Field(min_length=3, max_length=500)
    test_rebalances: int = Field(ge=0)
    top_bucket_return: float | None = None
    bottom_bucket_return: float | None = None
    long_short_return: float | None = None
    equal_weight_return: float | None = None
    top_vs_equal_excess: float | None = None
    hit_rate: float | None = Field(default=None, ge=0, le=1)
    max_drawdown: float | None = Field(default=None, le=0)
    sharpe_like: float | None = None
    contribution_attribution: list[ModelPortfolioContribution] = Field(
        default_factory=list,
        max_length=100,
    )
    attribution_reconciled: bool = False
    status: Literal[
        "insufficient_data",
        "exploratory",
        "out_of_sample_positive",
        "out_of_sample_negative",
    ]
    methodology: str = Field(min_length=3, max_length=2_000)
    limitations: list[str] = Field(max_length=12)


class ModelCrossSectionalValidation(BaseModel):
    """Cross-sectional, walk-forward validation over a tradable asset universe."""

    model_config = ConfigDict(extra="forbid")

    universe_name: str = Field(min_length=1, max_length=300)
    asset_count: int = Field(ge=0, le=100)
    # This is the registered pre-quality-gate universe, not the at-most-100
    # assets evaluated by the walk-forward model. Provider expansion can make
    # it substantially larger than the evaluated universe.
    expected_asset_count: int = Field(default=0, ge=0, le=2_000)
    asset_category_counts: dict[str, int] = Field(default_factory=dict, max_length=20)
    incomplete_assets: list[str] = Field(default_factory=list, max_length=100)
    factor_ids: list[str] = Field(min_length=1, max_length=8)
    start_date: str | None = None
    end_date: str | None = None
    train_end_date: str | None = None
    rebalance_horizon_days: int = Field(ge=1, le=90)
    train_rebalances: int = Field(ge=0)
    test_rebalances: int = Field(ge=0)
    long_bucket_size: int = Field(ge=0)
    short_bucket_size: int = Field(ge=0)
    transaction_cost_bps: float = Field(ge=0, le=500)
    top_bucket_return: float | None = None
    bottom_bucket_return: float | None = None
    long_short_return: float | None = None
    equal_weight_return: float | None = None
    top_vs_equal_excess: float | None = None
    hit_rate: float | None = Field(default=None, ge=0, le=1)
    max_drawdown: float | None = Field(default=None, le=0)
    sharpe_like: float | None = None
    status: Literal[
        "insufficient_data",
        "exploratory",
        "out_of_sample_positive",
        "out_of_sample_negative",
    ]
    asset_exposures: list[ModelCrossSectionAssetExposure] = Field(max_length=100)
    methodology: str = Field(min_length=3, max_length=2_000)
    leakage_guard: str = Field(min_length=3, max_length=1_500)
    limitations: list[str] = Field(max_length=12)
    robustness: ModelCrossSectionRobustness | None = None
    survivorship_audit: ModelSurvivorshipAudit | None = None


class ModelFactorResearch(BaseModel):
    """Dual-track linear and nonlinear factor-mining output."""

    model_config = ConfigDict(extra="forbid")

    method_version: str = "dual_track_factor_v9_nonlinear_linear_bridge"
    generated_at: datetime
    linear_chain_retained: bool
    factors: list[ModelFactorCandidate] = Field(max_length=24)
    nonlinear_links: list[ModelNonlinearFactorLink] = Field(max_length=12)
    profit_validations: list[ModelProfitValidation] = Field(max_length=6)
    cross_sectional_validations: list[ModelCrossSectionalValidation] = Field(
        default_factory=list,
        max_length=4,
    )
    archive_path: str | None = Field(default=None, max_length=1_000)
    archive_status: Literal["stored", "not_configured", "write_failed"]
    research_caveat: str = Field(min_length=3, max_length=2_000)


class ModelForecastValidationDecision(BaseModel):
    """Local validator decision over evidence that arrived after a forecast."""

    model_config = ConfigDict(extra="forbid")

    forecast_id: str
    status: Literal[
        "candidate_evidence_found",
        "supported",
        "partially_supported",
        "contradicted",
        "expired_insufficient_evidence",
    ]
    validation_summary: str = Field(min_length=3, max_length=2_000)
    supporting_evidence_refs: list[str] = Field(max_length=20)
    contradicting_evidence_refs: list[str] = Field(max_length=20)
    confidence: float = Field(ge=0, le=0.75)


class ModelForecastValidationBatch(BaseModel):
    """Bounded batch returned by the local forecast validator."""

    model_config = ConfigDict(extra="forbid")

    decisions: list[ModelForecastValidationDecision] = Field(max_length=12)


class ModelResearchResult(BaseModel):
    """Strict local-model research response."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=1_000)
    summary: str = Field(min_length=3, max_length=3_000)
    hypotheses: list[ModelResearchHypothesis] = Field(min_length=1, max_length=5)
    suggested_next_questions: list[str] = Field(max_length=8)
    equity_dimensions: list[ModelEquityResearchDimension] = Field(
        default_factory=list,
        max_length=5,
    )
    equity_decision_framework: ModelEquityDecisionFramework | None = None
    paper_report: ModelAcademicResearchReport | None = None
    news_forecasts: list[ModelNewsForecast] = Field(default_factory=list, max_length=12)
    factor_candidates: list[ModelFactorCandidate] = Field(default_factory=list, max_length=16)
    factor_research: ModelFactorResearch | None = None


class ResearchInquiryRequest(BaseModel):
    """One explicit research question."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=6, max_length=1_000)


class ResearchReviewRequest(BaseModel):
    """One explicit human decision over a stored research report."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["accepted", "revised_accepted", "deferred", "rejected"]
    reviewer_note: str | None = Field(default=None, max_length=4_000)


class ResearchReviewSignalView(BaseModel):
    """Append-only human report review exposed to the audit UI."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    decision: Literal["accepted", "revised_accepted", "deferred", "rejected"]
    reviewer_note: str | None
    created_at: datetime


class ChatGPTReviewFinding(BaseModel):
    """One actionable second-opinion finding."""

    model_config = ConfigDict(extra="forbid")

    severity: Literal["high", "medium", "low"]
    finding: str = Field(min_length=3, max_length=1_000)
    suggested_revision: str = Field(min_length=3, max_length=1_500)
    evidence_refs: list[str] = Field(max_length=10)


class ModelChatGPTResearchReview(BaseModel):
    """Strict Responses API review payload."""

    model_config = ConfigDict(extra="forbid")

    recommendation: Literal[
        "accept",
        "revise_and_accept",
        "defer_for_evidence",
        "reject",
    ]
    overall_assessment: str = Field(min_length=3, max_length=3_000)
    revised_summary: str = Field(min_length=3, max_length=3_000)
    confidence_adjustment: float = Field(ge=-0.75, le=0.75)
    findings: list[ChatGPTReviewFinding] = Field(max_length=12)
    missing_evidence: list[str] = Field(max_length=12)


class ChatGPTResearchReview(ModelChatGPTResearchReview):
    """Stored OpenAI review with provenance."""

    model: str
    reviewed_at: datetime


class ResearchInquiryView(BaseModel):
    """Stored research result exposed to the top workspace."""

    model_config = ConfigDict(extra="forbid")

    id: int
    question: str
    mode: Literal["user_question", "autonomous"]
    status: Literal["running", "completed", "failed"]
    local_model: str
    result: ModelResearchResult | None
    evidence_snapshot: dict[str, Any]
    chatgpt_review: ChatGPTResearchReview | None
    review_signals: list[ResearchReviewSignalView] = Field(default_factory=list)
    error: str | None
    created_at: datetime
    updated_at: datetime


class ResearchInquirySummaryView(BaseModel):
    """Lightweight catalog row that never includes report JSON payloads."""

    model_config = ConfigDict(extra="forbid")

    id: int
    question: str
    mode: Literal["user_question", "autonomous"]
    status: Literal["running", "completed", "failed"]
    local_model: str
    has_result: bool
    market_region: Literal["us", "china"] | None = None
    ticker: str | None = None
    company_name: str | None = None
    sector: str | None = None
    error: str | None
    created_at: datetime
    updated_at: datetime


class ResearchInquirySummaryListResponse(BaseModel):
    """Recent research catalog without evidence snapshots or generated reports."""

    model_config = ConfigDict(extra="forbid")

    inquiries: list[ResearchInquirySummaryView]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    pages: int = Field(ge=0)


class ResearchReportEvidenceChange(BaseModel):
    """One compact evidence identity added to or retired from a report version."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    category: str | None = None
    title: str | None = None
    observed_at: str | None = None
    source: str | None = None


class ResearchReportChangeSummary(BaseModel):
    """Structured report-to-report deltas used for a non-causal change explanation."""

    model_config = ConfigDict(extra="forbid")

    confidence_delta: float | None = None
    data_readiness_delta: float | None = None
    verified_steps_delta: int = 0
    unresolved_steps_delta: int = 0
    cited_evidence_delta: int = 0
    current_price_delta: float | None = None
    reward_risk_delta: float | None = None
    primary_signal_from: str | None = None
    primary_signal_to: str | None = None
    timing_from: str | None = None
    timing_to: str | None = None
    audit_status_from: str | None = None
    audit_status_to: str | None = None
    model_changed: bool = False
    summary_changed: bool = False
    new_category_counts: dict[str, int] = Field(default_factory=dict, max_length=8)
    retired_category_counts: dict[str, int] = Field(default_factory=dict, max_length=8)
    driver_codes: list[str] = Field(default_factory=list, max_length=16)


class ResearchReportComparisonVersion(BaseModel):
    """One compact same-company report snapshot for longitudinal comparison."""

    model_config = ConfigDict(extra="forbid")

    inquiry_id: int
    question: str
    status: Literal["running", "completed", "failed"]
    local_model: str
    created_at: datetime
    updated_at: datetime
    is_selected: bool = False
    confidence: float | None = Field(default=None, ge=0, le=1)
    data_readiness_score: float | None = Field(default=None, ge=0, le=1)
    data_readiness_status: str | None = None
    directional_conclusion_allowed: bool | None = None
    verified_steps: int = Field(default=0, ge=0)
    partially_supported_steps: int = Field(default=0, ge=0)
    unresolved_steps: int = Field(default=0, ge=0)
    evidence_count: int = Field(default=0, ge=0)
    cited_reference_count: int = Field(default=0, ge=0)
    missing_reference_count: int = Field(default=0, ge=0)
    new_evidence_count: int | None = Field(default=None, ge=0)
    retired_evidence_count: int | None = Field(default=None, ge=0)
    new_evidence: list[ResearchReportEvidenceChange] = Field(
        default_factory=list,
        max_length=8,
    )
    retired_evidence: list[ResearchReportEvidenceChange] = Field(
        default_factory=list,
        max_length=8,
    )
    change_summary: ResearchReportChangeSummary | None = None
    primary_signal: Literal["bullish", "bearish", "mixed", "unknown"] = "unknown"
    signal_counts: dict[str, int] = Field(default_factory=dict)
    timing_assessment: str | None = None
    current_price: float | None = None
    entry_reference: float | None = None
    stop_reference: float | None = None
    target_reference: float | None = None
    reward_risk_ratio: float | None = None
    audit_status: str | None = None
    audit_recommendation: str | None = None
    summary: str | None = None
    blockers: list[str] = Field(default_factory=list, max_length=8)


class ResearchReportComparisonResponse(BaseModel):
    """Bounded same-company report history without full report payloads."""

    model_config = ConfigDict(extra="forbid")

    selected_inquiry_id: int
    comparable: bool
    reason: str | None = None
    market_region: Literal["us", "china"] | None = None
    ticker: str | None = None
    company_name: str | None = None
    sector: str | None = None
    total_versions: int = Field(ge=0)
    versions: list[ResearchReportComparisonVersion]


class ResearchReportChangeAlert(BaseModel):
    """Material latest-versus-prior report change for one company."""

    model_config = ConfigDict(extra="forbid")

    latest_inquiry_id: int
    previous_inquiry_id: int
    market_region: Literal["us", "china"]
    ticker: str
    company_name: str
    sector: str | None = None
    latest_created_at: datetime
    previous_created_at: datetime
    severity: Literal["critical", "high", "medium", "low"]
    alert_score: int = Field(ge=0, le=100)
    assessment: Literal[
        "evidence_upgrade",
        "evidence_downgrade",
        "mixed_change",
        "parameter_refresh",
    ]
    current_confidence: float | None = Field(default=None, ge=0, le=1)
    previous_confidence: float | None = Field(default=None, ge=0, le=1)
    current_readiness: float | None = Field(default=None, ge=0, le=1)
    previous_readiness: float | None = Field(default=None, ge=0, le=1)
    change_summary: ResearchReportChangeSummary


class ResearchReportChangeAlertListResponse(BaseModel):
    """Bounded latest report-change alerts across companies."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    total_companies_with_history: int = Field(ge=0)
    alerts: list[ResearchReportChangeAlert]
    methodology: str


class ResearchInquiryListResponse(BaseModel):
    """Recent research runs."""

    model_config = ConfigDict(extra="forbid")

    inquiries: list[ResearchInquiryView]


class ForecastRefreshView(BaseModel):
    """Summary of one local walk-forward validation pass."""

    model_config = ConfigDict(extra="forbid")

    scanned_reports: int = Field(ge=0)
    forecasts_checked: int = Field(ge=0)
    forecasts_updated: int = Field(ge=0)


class FactorRefreshView(BaseModel):
    """Summary of one stored-report factor-mining backfill."""

    model_config = ConfigDict(extra="forbid")

    scanned_reports: int = Field(ge=0)
    factor_reports_updated: int = Field(ge=0)
    cold_artifacts_stored: int = Field(ge=0)


class FactorExperimentView(BaseModel):
    """One frozen prospective factor experiment and optional realized outcome."""

    model_config = ConfigDict(extra="forbid")

    id: int
    source_inquiry_id: int | None = None
    target_series_id: str
    target_name: str
    method_version: str
    protocol_version: str
    forecast_horizon_observations: int = Field(ge=1)
    factor_ids: list[str]
    replication_summary: dict[str, Any]
    anchor_observed_on: str
    anchor_value: float
    predicted_position: Literal["long", "short"]
    transaction_cost_bps: float = Field(ge=0)
    status: Literal["pending", "future_validated", "future_failed"]
    outcome_observed_on: str | None = None
    raw_return: float | None = None
    strategy_return: float | None = None
    prediction_correct: bool | None = None
    frozen_at: datetime


class FactorExperimentGroupView(BaseModel):
    """Prospective results aggregated only across identically specified rules."""

    model_config = ConfigDict(extra="forbid")

    target_series_id: str
    method_version: str
    protocol_version: str
    forecast_horizon_observations: int = Field(ge=1)
    factor_ids: list[str]
    experiments: int = Field(ge=0)
    pending: int = Field(ge=0)
    matured: int = Field(ge=0)
    passed: int = Field(ge=0)
    prospective_hit_rate: float | None = Field(default=None, ge=0, le=1)
    mean_strategy_return: float | None = None
    reliability_status: Literal[
        "awaiting_future_samples",
        "insufficient_future_samples",
        "prospectively_retained",
        "prospectively_rejected",
    ]


class FactorExperimentStatusView(BaseModel):
    """Factor laboratory inventory, repeated trials and future validation status."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    total_experiments: int = Field(ge=0)
    pending_experiments: int = Field(ge=0)
    future_validated: int = Field(ge=0)
    future_failed: int = Field(ge=0)
    groups: list[FactorExperimentGroupView]
    recent_experiments: list[FactorExperimentView]
    methodology: str


class FactorExperimentSettlementView(BaseModel):
    """One prospective-factor settlement pass."""

    model_config = ConfigDict(extra="forbid")

    scanned: int = Field(ge=0)
    settled: int = Field(ge=0)
    still_pending: int = Field(ge=0)


class ResearchBatchCreateRequest(BaseModel):
    """Create a bounded equity-report generation batch."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=3, max_length=255)
    regions: list[Literal["us", "china"]] = Field(
        default_factory=lambda: ["us", "china"],
        min_length=1,
        max_length=2,
    )
    limit_per_region: int = Field(default=2, ge=1, le=200)
    tickers: list[str] | None = Field(default=None, min_length=1, max_length=400)

    @field_validator("regions")
    @classmethod
    def unique_regions(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("regions must be unique")
        return value

    @field_validator("tickers")
    @classmethod
    def normalize_tickers(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [item.strip().upper() for item in value if item.strip()]
        if not normalized or len(set(normalized)) != len(normalized):
            raise ValueError("tickers must be non-empty and unique")
        return normalized


class ResearchBatchItemView(BaseModel):
    """Observable lifecycle and evidence readiness for one batch target."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    market_region: Literal["us", "china"]
    research_scope: Literal["sec_numeric_evidence", "market_factor_evidence"]
    ticker: str
    company_name: str
    sector: str | None
    question: str
    priority: int = Field(ge=0)
    status: Literal["queued", "running", "completed", "failed"]
    attempt_count: int = Field(ge=0)
    progress_percent: float = Field(ge=0, le=100)
    progress_stage: str
    progress_message: str | None
    heartbeat_at: datetime | None
    inquiry_id: int | None
    data_readiness: dict[str, Any]
    audit_summary: dict[str, Any] | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None


class ResearchBatchView(BaseModel):
    """Durable batch progress with all bounded target items."""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    status: Literal["queued", "running", "completed", "partial_failed", "failed"]
    template_version: str
    parameters: dict[str, Any]
    target_count: int = Field(ge=1)
    completed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    progress_percent: float = Field(ge=0, le=100)
    items: list[ResearchBatchItemView]
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ResearchBatchListResponse(BaseModel):
    """Newest durable equity research batches."""

    model_config = ConfigDict(extra="forbid")

    batches: list[ResearchBatchView]


class ResearchAuditQueueRequest(BaseModel):
    """Queue deterministic audits without silently refreshing historical evidence."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["audit_only", "refresh_and_audit"] = "audit_only"
    limit: int = Field(default=100, ge=1, le=100)
    inquiry_ids: list[int] = Field(default_factory=list, max_length=100)

    @field_validator("inquiry_ids")
    @classmethod
    def validate_inquiry_ids(cls, value: list[int]) -> list[int]:
        if any(item <= 0 for item in value):
            raise ValueError("inquiry ids must be positive")
        return list(dict.fromkeys(value))


class ResearchAuditQueueView(BaseModel):
    """Summary after idempotently materializing report-audit jobs."""

    model_config = ConfigDict(extra="forbid")

    scanned_reports: int = Field(ge=0)
    queued_jobs: int = Field(ge=0)
    existing_jobs: int = Field(ge=0)
    already_audited: int = Field(ge=0)
    mode: Literal["audit_only", "refresh_and_audit"]


class ResearchAuditStatusView(BaseModel):
    """Current deterministic report-audit queue inventory."""

    model_config = ConfigDict(extra="forbid")

    queued: int = Field(ge=0)
    running: int = Field(ge=0)
    completed: int = Field(ge=0)
    failed: int = Field(ge=0)
    superseded: int = Field(ge=0)
    latest_completed_at: datetime | None = None


class ResearchContextView(BaseModel):
    """Lightweight job identifiers needed by the independent research page."""

    model_config = ConfigDict(extra="forbid")

    latest_cluster_job_id: int | None = Field(default=None, gt=0)
    latest_logic_job_id: int | None = Field(default=None, gt=0)


class AIChainInventoryView(BaseModel):
    """Formal chain inventory and source-backed validation activity."""

    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    new_24h: int = Field(ge=0)
    pending_review: int = Field(ge=0)
    validated: int = Field(ge=0)
    enhanced_evidence_validated: int = Field(ge=0)
    since_last_training: int = Field(ge=0)
    research_runs: int = Field(ge=0)
    latest_completed_cluster_job_id: int | None = Field(default=None, gt=0)
    latest_logic_cluster_job_id: int | None = Field(default=None, gt=0)
    logic_refresh_pending_jobs: int = Field(default=0, ge=0)
    logic_refresh_state: Literal["current", "pending", "retrying"] = "current"
    latest_chain_at: datetime | None = None
    latest_validation_at: datetime | None = None
    latest_research_at: datetime | None = None
    latest_evidence_snapshot_at: datetime | None = None


class AIModelStateView(BaseModel):
    """Runtime model and the model/prompt provenance used by stored chains."""

    model_config = ConfigDict(extra="forbid")

    app_version: str
    runtime_model: str
    last_chain_model: str | None = None
    previous_chain_model: str | None = None
    prompt_version: str | None = None
    previous_prompt_version: str | None = None
    state: Literal[
        "current",
        "upgrade_detected",
        "configured_change_pending_run",
        "no_chain_history",
    ]
    current_version_first_seen_at: datetime | None = None


class AITrainingStateView(BaseModel):
    """Auditable distinction between review signals and confirmed retraining."""

    model_config = ConfigDict(extra="forbid")

    state: Literal[
        "no_signals",
        "signals_collected",
        "retraining_confirmed",
        "manifest_invalid",
    ]
    review_signal_count: int = Field(ge=0)
    signal_count_used: int = Field(ge=0)
    pending_signal_count: int = Field(ge=0)
    verified_memory_count: int = Field(default=0, ge=0)
    external_pending_count: int = Field(default=0, ge=0)
    external_approved_count: int = Field(default=0, ge=0)
    training_dataset_ready_count: int = Field(default=0, ge=0)
    retraining_confirmed: bool
    manifest_configured: bool
    training_run_id: str | None = None
    trained_model: str | None = None
    base_model: str | None = None
    trained_at: datetime | None = None
    explanation: str


class AIStatusView(BaseModel):
    """One honest status snapshot for AI chains, upgrades, and training."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    chains: AIChainInventoryView
    model: AIModelStateView
    training: AITrainingStateView
