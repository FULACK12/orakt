"""Public contracts for reviewed companies and SEC financial history."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class CompanyFactView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept: str
    label: str
    unit: str
    value: float
    period_start: date | None
    period_end: date
    filed_at: date
    form: str
    fiscal_year: int | None
    fiscal_period: str | None
    source_url: str


class CompanyView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    cik: str
    name: str
    sector: str
    industry: str
    source_url: str
    latest_price: float | None = None
    price_observed_on: date | None = None
    latest_filing_form: str | None = None
    latest_filing_date: date | None = None
    latest_facts: list[CompanyFactView]
    last_success_at: datetime | None = None
    last_error: str | None = None


class CompanyListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    companies: list[CompanyView]


class CompanySupplyChainCoverageView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    company_name: str
    status: str
    candidate_edges: int
    verified_edges: int
    related_companies_with_market_data: int
    latest_available_at: date | None
    latest_filing_accession: str | None
    latest_filing_date: date | None
    latest_raw_archive_path: str | None
    last_parser_version: str | None
    gaps: list[str]
    last_completed_at: datetime | None
    last_error: str | None


class CompanySupplyChainCoverageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    companies: list[CompanySupplyChainCoverageView]


class CompanySupplyChainEdgeView(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    subject_ticker: str
    related_company_name: str
    related_ticker: str | None
    relationship_type: str
    product_or_input: str
    geography: str | None
    dependency_level: str
    review_status: str
    confidence: float
    source_kind: str
    source_ref: str
    source_url: str
    source_excerpt: str
    observed_at: date
    available_at: date
    reviewed_at: datetime | None
    reviewed_by: str | None
    review_note: str | None


class CompanySupplyChainEdgeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edges: list[CompanySupplyChainEdgeView]


class SupplierMarketHistoryRowView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    company_name: str
    verified_relation_count: int
    series_id: str
    status: str
    observation_count: int
    observed_start: date | None
    observed_end: date | None
    last_started_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    company_profile_available: bool
    filing_count: int
    financial_fact_count: int


class SupplierMarketHistoryStatusView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tracked_tickers: int
    available_tickers: int
    pending_tickers: int
    profiled_tickers: int
    filing_tickers: int
    fundamental_tickers: int
    rows: list[SupplierMarketHistoryRowView]


class SupplyChainNearbyPortView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    distance_km: float = Field(ge=0)
    website: str | None


class SupplyChainNearbyEventView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: int
    title: str
    start_at: datetime
    event_type: str | None = None
    severity: float | None = Field(default=None, ge=0, le=1)


class SupplyChainSiteExposureView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_id: int
    edge_id: int
    context_ticker: str
    facility_role: str
    subject_ticker: str
    related_company_name: str
    related_ticker: str | None
    site_kind: str
    site_name: str
    country_name: str
    country_iso2: str | None
    admin1_name: str | None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    coordinate_precision: str
    verification_status: str
    association_scope: str
    source_ref: str
    source_url: str
    source_excerpt: str
    available_at: date
    exposure_radius_km: float = Field(ge=0)
    conflict_events: int = Field(ge=0)
    conflict_fatalities: int = Field(ge=0)
    disaster_event_count: int = Field(ge=0)
    disaster_events: list[SupplyChainNearbyEventView]
    power_signal_count: int = Field(ge=0)
    power_signals: list[SupplyChainNearbyEventView]
    nearest_port: SupplyChainNearbyPortView | None
    port_route_status: str
    exposure_attention_score: float = Field(ge=0, le=1)
    period_start: date
    period_end: date


class SupplyChainSiteExposureResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    as_of: date
    weeks: int = Field(ge=1, le=520)
    period_start: date
    site_count: int = Field(ge=0)
    returned_site_count: int = Field(ge=0)
    geocoded_site_count: int = Field(ge=0)
    exact_facility_count: int = Field(ge=0)
    regional_location_count: int = Field(ge=0)
    company_facility_count: int = Field(ge=0)
    supplier_location_count: int = Field(ge=0)
    conflict_exposed_count: int = Field(ge=0)
    disaster_exposed_count: int = Field(ge=0)
    power_signal_count: int = Field(ge=0)
    truncated: bool
    sites: list[SupplyChainSiteExposureView]
    methodology: str
    limitations: list[str]
