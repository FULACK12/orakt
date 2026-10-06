"""Validated contracts for major market-index reference and quote data."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class MarketIndexView(BaseModel):
    """A reviewed major index and its optional latest provider observation."""

    model_config = ConfigDict(extra="forbid")

    code: str
    provider_symbol: str
    name_en: str
    name_zh: str
    country_iso2: str = Field(min_length=2, max_length=2)
    exchange: str
    currency: str
    official_url: str
    quote_proxy_en: str | None = None
    quote_proxy_zh: str | None = None
    observed_on: date | None = None
    close: float | None = None
    change_percent: float | None = None


class MarketIndexResponse(BaseModel):
    """Index catalog plus explicit provider/credential/freshness state."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    provider_url: str
    quote_status: Literal[
        "ready",
        "partial",
        "credential_required",
        "provider_error",
    ]
    delay_notice_en: str
    delay_notice_zh: str
    fetched_at: datetime | None
    indices: list[MarketIndexView]


class HistoricalPriceBackfillCandidateView(BaseModel):
    """One lifecycle-safe candidate and its current retrieval state."""

    model_config = ConfigDict(extra="forbid")

    asset_key: str
    symbol: str
    name: str
    exchange: str
    asset_type: str
    ipo_date: date | None = None
    delisting_date: date
    priority_score: float
    priority_reasons: list[str]
    status: str
    attempt_count: int = Field(ge=0)
    observations_upserted: int = Field(ge=0)
    observed_start: date | None = None
    observed_end: date | None = None
    last_attempt_at: datetime | None = None
    last_error_code: str | None = None


class HistoricalPriceBackfillQueueResponse(BaseModel):
    """Measured queue and provider-limit disclosure for historical prices."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    provider: str
    provider_daily_request_limit: int = Field(ge=1)
    configured_daily_price_budget: int = Field(ge=1)
    queued_assets: int = Field(ge=0)
    pending_assets: int = Field(ge=0)
    synced_assets: int = Field(ge=0)
    partial_assets: int = Field(ge=0)
    unavailable_assets: int = Field(ge=0)
    ticker_reused_assets: int = Field(ge=0)
    factor_ready_assets: int = Field(ge=0)
    candidates: list[HistoricalPriceBackfillCandidateView]


class HistoricalSecurityIdentityView(BaseModel):
    """Cross-source identity and terminal-value audit for one historical asset."""

    model_config = ConfigDict(extra="forbid")

    asset_key: str
    symbol: str
    name: str
    exchange: str
    delisting_date: date
    series_id: str | None = None
    identity_status: str
    mapping_method: str | None = None
    figi: str | None = None
    composite_figi: str | None = None
    share_class_figi: str | None = None
    sec_cik: str | None = None
    mapped_name: str | None = None
    mapped_exchange: str | None = None
    name_similarity: float | None = None
    outcome_status: str
    outcome_type: str
    last_trade_date: date | None = None
    last_trade_price: float | None = None
    terminal_value_per_share: float | None = None
    exchange_ratio: float | None = None
    acquirer_symbol: str | None = None
    acquirer_price_on_payment: float | None = None
    acquirer_price_observed_on: date | None = None
    resolution_method: str | None = None
    cashflow_count: int = Field(default=0, ge=0)
    terminal_is_final: bool = False
    payment_date: date | None = None
    delisting_return: float | None = None
    evidence_url: str | None = None
    verified_at: datetime | None = None


class HistoricalIdentityAuditResponse(BaseModel):
    """Measured security-identity and terminal-outcome readiness."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    source: str
    verified_identity_assets: int = Field(ge=0)
    unresolved_identity_assets: int = Field(ge=0)
    ambiguous_identity_assets: int = Field(ge=0)
    mismatched_identity_assets: int = Field(ge=0)
    lifecycle_conflict_identity_assets: int = Field(ge=0)
    sec_cik_assets: int = Field(ge=0)
    verified_outcomes: int = Field(ge=0)
    outcomes_requiring_evidence: int = Field(ge=0)
    outcomes_requiring_identity: int = Field(ge=0)
    assets: list[HistoricalSecurityIdentityView]


class DelistingOutcomeEvidenceRequest(BaseModel):
    """Human-reviewed post-delisting value from a cited primary source."""

    model_config = ConfigDict(extra="forbid")

    evidence_key: str = Field(min_length=64, max_length=64)
    outcome_type: Literal[
        "cash_acquisition",
        "stock_acquisition",
        "cash_and_stock",
        "liquidation_distribution",
        "bankruptcy_worthless",
        "continued_trading",
    ]
    terminal_value_per_share: float | None = Field(default=None, ge=0, le=1_000_000)
    payment_date: date
    evidence_url: HttpUrl
    evidence_note: str = Field(min_length=20, max_length=2_000)


class DelistingEvidenceCandidateView(BaseModel):
    """One SEC filing candidate; it is not a verified terminal return."""

    model_config = ConfigDict(extra="forbid")

    evidence_key: str
    accession_number: str
    subject_symbol: str | None = None
    subject_sec_cik: str | None = None
    form: str
    filed_on: date
    observed_on: date | None = None
    source_url: str
    evidence_type: str
    evidence_basis: str
    candidate_value: float | None = None
    value_unit: str | None = None
    evidence_excerpt: str | None = None
    confidence: float = Field(ge=0, le=1)
    body_status: str
    review_status: str
    review_role: str | None = None
    review_note: str | None = None
    reviewed_at: datetime | None = None


class HistoricalDelistingEvidenceAssetView(BaseModel):
    """SEC discovery state and candidates for one historical security."""

    model_config = ConfigDict(extra="forbid")

    asset_key: str
    symbol: str
    name: str
    delisting_date: date
    sec_cik: str | None = None
    identity_status: str
    outcome_status: str
    factor_eligible: bool
    factor_block_reason: str | None = None
    terminal_value_per_share: float | None = None
    lifecycle_resolution_type: str | None = None
    authoritative_status: str | None = None
    authoritative_delisting_date: date | None = None
    search_status: str
    cik_name: str | None = None
    cik_name_similarity: float | None = None
    filing_count: int = Field(ge=0)
    extracted_candidate_count: int = Field(ge=0)
    body_access_status: str
    search_start: date | None = None
    search_end: date | None = None
    last_attempt_at: datetime | None = None
    candidates: list[DelistingEvidenceCandidateView]


class HistoricalDelistingEvidenceResponse(BaseModel):
    """Measured SEC discovery coverage with an explicit full-text access gate."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    source: str
    body_retrieval_ready: bool
    evidence_assets_searched: int = Field(ge=0)
    evidence_assets_cik_resolved: int = Field(ge=0)
    evidence_metadata_candidates: int = Field(ge=0)
    evidence_value_candidates: int = Field(ge=0)
    evidence_review_ready: int = Field(ge=0)
    evidence_terminal_accepted: int = Field(ge=0)
    evidence_supporting_accepted: int = Field(ge=0)
    evidence_needs_more: int = Field(ge=0)
    evidence_lifecycle_segmented_assets: int = Field(ge=0)
    evidence_body_contact_required_assets: int = Field(ge=0)
    evidence_provider_error_assets: int = Field(ge=0)
    evidence_lifecycle_conflict_assets: int = Field(ge=0)
    assets: list[HistoricalDelistingEvidenceAssetView]


class DelistingEvidenceReviewRequest(BaseModel):
    """Human review over a candidate; terminal-return verification remains separate."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["accepted", "rejected", "needs_more_evidence"]
    review_role: Literal["terminal_outcome", "supporting_evidence"] | None = None
    review_note: str = Field(min_length=10, max_length=2_000)


class SupplementalDelistingEvidenceRequest(BaseModel):
    """Reviewer-extracted value from a cited SEC completion filing or exhibit."""

    model_config = ConfigDict(extra="forbid")

    accession_number: str = Field(min_length=18, max_length=40)
    form: Literal["8-K", "8-K/A", "6-K", "20-F", "25", "25-NSE", "15F"]
    filed_on: date
    observed_on: date | None = None
    source_url: HttpUrl
    evidence_type: Literal[
        "cash_consideration_per_share",
        "share_exchange_ratio",
        "acquirer_closing_price",
        "zero_recovery_per_share",
        "liquidation_distribution_per_share",
        "adr_cash_distribution_per_share",
    ]
    candidate_value: float = Field(ge=0, le=1_000_000)
    value_unit: Literal[
        "USD_per_share",
        "acquirer_shares_per_share",
        "USD_per_acquirer_share",
    ]
    subject_symbol: str | None = Field(default=None, min_length=1, max_length=64)
    subject_sec_cik: str | None = Field(default=None, min_length=1, max_length=16)
    evidence_excerpt: str = Field(min_length=40, max_length=2_000)
    confidence: float = Field(default=0.95, ge=0.8, le=1)


class StockDelistingOutcomeEvidenceRequest(BaseModel):
    """Two-source valuation of fixed-ratio stock merger consideration."""

    model_config = ConfigDict(extra="forbid")

    exchange_ratio_evidence_key: str = Field(min_length=64, max_length=64)
    valuation_evidence_key: str = Field(min_length=64, max_length=64)
    acquirer_symbol: str = Field(min_length=1, max_length=64)
    payment_date: date
    evidence_note: str = Field(min_length=20, max_length=2_000)


class SecPrimaryIdentityRequest(BaseModel):
    """Reviewer-cited SEC identity used when automated FIGI mapping misses."""

    model_config = ConfigDict(extra="forbid")

    sec_cik: str = Field(min_length=1, max_length=16)
    subject_name: str = Field(min_length=3, max_length=255)
    evidence_url: HttpUrl
    evidence_note: str = Field(min_length=20, max_length=2_000)


class LifecycleResolutionRequest(BaseModel):
    """Primary-source correction layered over provider lifecycle metadata."""

    model_config = ConfigDict(extra="forbid")

    resolution_type: Literal[
        "provider_conflict_active",
        "adr_program_terminated",
        "bankruptcy_pending",
        "liquidation_pending",
        "verified_delisted",
    ]
    authoritative_status: Literal["active", "delisted", "bankruptcy", "liquidation"]
    authoritative_delisting_date: date | None = None
    evidence_url: HttpUrl
    evidence_note: str = Field(min_length=20, max_length=2_000)


class LifecycleResolutionView(BaseModel):
    """Audited lifecycle status without mutation of the provider snapshot."""

    model_config = ConfigDict(extra="forbid")

    asset_key: str
    symbol: str
    provider_status: str
    provider_delisting_date: date | None = None
    resolution_type: str
    authoritative_status: str
    authoritative_delisting_date: date | None = None
    evidence_url: str
    evidence_note: str
    reviewed_at: datetime


class TerminalCashflowRequest(BaseModel):
    """One confirmed or estimated shareholder terminal distribution."""

    model_config = ConfigDict(extra="forbid")

    evidence_key: str = Field(min_length=64, max_length=64)
    cashflow_type: Literal[
        "liquidation_distribution",
        "bankruptcy_recovery",
        "adr_cash_distribution",
        "stock_distribution_cash_value",
        "other_terminal_distribution",
    ]
    amount_per_share: float = Field(ge=0, le=1_000_000)
    payment_date: date
    status: Literal["confirmed", "estimated"]
    is_final: bool = False
    evidence_note: str = Field(min_length=20, max_length=2_000)


class TerminalCashflowView(BaseModel):
    """Immutable reviewed cashflow in a staged shareholder outcome."""

    model_config = ConfigDict(extra="forbid")

    cashflow_key: str
    asset_key: str
    evidence_key: str
    sequence: int = Field(ge=1)
    cashflow_type: str
    amount_per_share: float = Field(ge=0)
    payment_date: date
    status: str
    is_final: bool
    evidence_url: str
    evidence_note: str
    reviewed_at: datetime


class MultiStageOutcomeRequest(BaseModel):
    """Finalize the sum of reviewed terminal cashflows after the final stage."""

    model_config = ConfigDict(extra="forbid")

    outcome_type: Literal[
        "liquidation_distribution",
        "bankruptcy_worthless",
        "cash_and_stock",
    ]
    evidence_note: str = Field(min_length=20, max_length=2_000)


class LifecycleSegmentRequest(BaseModel):
    """Reviewed SEC evidence used to split a contaminated provider series."""

    model_config = ConfigDict(extra="forbid")

    evidence_key: str = Field(min_length=64, max_length=64)


class LifecycleSegmentResponse(BaseModel):
    """Immutable lineage for an SEC-anchored historical price segment."""

    model_config = ConfigDict(extra="forbid")

    asset_key: str
    symbol: str
    source_series_id: str
    segmented_series_id: str
    evidence_key: str
    provider_delisting_date: date | None = None
    terminal_filing_date: date
    last_trade_date: date
    first_contaminated_date: date | None = None
    retained_observations: int = Field(ge=1)
    excluded_observations: int = Field(ge=0)
    segment_method: str
    segmented_at: datetime
