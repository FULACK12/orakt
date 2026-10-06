"""Reviewed US company, SEC filing and standardized XBRL fact history."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class CompanyProfile(TimestampMixin, Base):
    """One reviewed large US public company."""

    __tablename__ = "company_profiles"

    ticker: Mapped[str] = mapped_column(String(16), primary_key=True)
    cik: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str] = mapped_column(String(128), nullable=False)
    industry: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)


class CompanySupplyChainEdge(IntegerIdMixin, TimestampMixin, Base):
    """One source-quoted, point-in-time company relationship."""

    __tablename__ = "company_supply_chain_edges"
    __table_args__ = (
        CheckConstraint(
            "relationship_type IN ('supplier', 'customer', 'foundry', "
            "'contract_manufacturer', 'equipment', 'materials', 'logistics', "
            "'energy', 'cloud', 'distributor')",
            name="company_supply_chain_relationship_type",
        ),
        CheckConstraint(
            "dependency_level IN ('unknown', 'low', 'medium', 'high', 'sole_source')",
            name="company_supply_chain_dependency_level",
        ),
        CheckConstraint(
            "review_status IN ('candidate', 'verified', 'rejected', 'expired')",
            name="company_supply_chain_review_status",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="company_supply_chain_confidence",
        ),
        UniqueConstraint(
            "subject_ticker",
            "related_company_name",
            "relationship_type",
            "product_or_input",
            "source_ref",
            name="uq_company_supply_chain_evidence_edge",
        ),
        Index(
            "ix_company_supply_chain_subject_status",
            "subject_ticker",
            "review_status",
            "available_at",
        ),
    )

    subject_ticker: Mapped[str] = mapped_column(
        ForeignKey("company_profiles.ticker", ondelete="CASCADE"), nullable=False
    )
    related_company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    related_ticker: Mapped[str | None] = mapped_column(String(32))
    relationship_type: Mapped[str] = mapped_column(String(32), nullable=False)
    product_or_input: Mapped[str] = mapped_column(String(255), nullable=False)
    geography: Mapped[str | None] = mapped_column(String(255))
    dependency_level: Mapped[str] = mapped_column(String(16), nullable=False)
    review_status: Mapped[str] = mapped_column(String(24), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[date] = mapped_column(Date, nullable=False)
    available_at: Mapped[date] = mapped_column(Date, nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(64))
    review_note: Mapped[str | None] = mapped_column(Text)


class CompanySupplyChainSite(IntegerIdMixin, TimestampMixin, Base):
    """One source-bounded facility or manufacturing-region location."""

    __tablename__ = "company_supply_chain_sites"
    __table_args__ = (
        CheckConstraint(
            "site_kind IN ('facility', 'manufacturing_region', 'port', 'airport', 'power_asset')",
            name="company_supply_chain_site_kind",
        ),
        CheckConstraint(
            "coordinate_precision IN ('exact_facility', 'city_centroid', "
            "'admin1_centroid', 'country_centroid', 'unresolved')",
            name="company_supply_chain_site_coordinate_precision",
        ),
        CheckConstraint(
            "verification_status IN ('verified_exact', 'verified_region', "
            "'derived_proximity', 'candidate', 'rejected')",
            name="company_supply_chain_site_verification_status",
        ),
        CheckConstraint(
            "association_scope IN ('issuer_reported_manufacturing_region', "
            "'supplier_facility_not_customer_linked', 'customer_linked_facility', "
            "'confirmed_production_line', 'proximity_reference')",
            name="company_supply_chain_site_association_scope",
        ),
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="company_supply_chain_site_latitude",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="company_supply_chain_site_longitude",
        ),
        UniqueConstraint(
            "edge_id",
            "site_kind",
            "site_name",
            "country_iso2",
            name="uq_company_supply_chain_site",
        ),
        Index(
            "ix_company_supply_chain_site_subject",
            "subject_ticker",
            "verification_status",
        ),
        Index(
            "ix_company_supply_chain_site_coordinates",
            "latitude",
            "longitude",
        ),
    )

    edge_id: Mapped[int] = mapped_column(
        ForeignKey("company_supply_chain_edges.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_ticker: Mapped[str] = mapped_column(
        ForeignKey("company_profiles.ticker", ondelete="CASCADE"),
        nullable=False,
    )
    related_company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    related_ticker: Mapped[str | None] = mapped_column(String(32))
    site_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    site_name: Mapped[str] = mapped_column(String(255), nullable=False)
    country_name: Mapped[str] = mapped_column(String(128), nullable=False)
    country_iso2: Mapped[str | None] = mapped_column(String(2))
    admin1_name: Mapped[str | None] = mapped_column(String(255))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    coordinate_precision: Mapped[str] = mapped_column(String(32), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False)
    association_scope: Mapped[str] = mapped_column(String(64), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[date] = mapped_column(Date, nullable=False)
    available_at: Mapped[date] = mapped_column(Date, nullable=False)


class CompanySupplyChainCoverage(TimestampMixin, Base):
    """Honest per-issuer completeness state for the supplier graph."""

    __tablename__ = "company_supply_chain_coverage"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'discovering', 'needs_review', "
            "'verified_partial', 'verified', 'failed')",
            name="company_supply_chain_coverage_status",
        ),
    )

    ticker: Mapped[str] = mapped_column(
        ForeignKey("company_profiles.ticker", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    candidate_edges: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verified_edges: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    related_companies_with_market_data: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    latest_available_at: Mapped[date | None] = mapped_column(Date)
    latest_filing_accession: Mapped[str | None] = mapped_column(String(32))
    latest_filing_date: Mapped[date | None] = mapped_column(Date)
    latest_raw_archive_path: Mapped[str | None] = mapped_column(Text)
    last_parser_version: Mapped[str | None] = mapped_column(String(64))
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gaps: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    last_error: Mapped[str | None] = mapped_column(Text)


class CompanyFiling(TimestampMixin, Base):
    """One retained SEC submission reference."""

    __tablename__ = "company_filings"
    __table_args__ = (Index("ix_company_filings_ticker_filed", "ticker", "filed_at"),)

    accession_number: Mapped[str] = mapped_column(String(32), primary_key=True)
    ticker: Mapped[str] = mapped_column(
        ForeignKey("company_profiles.ticker", ondelete="CASCADE"),
        nullable=False,
    )
    form: Mapped[str] = mapped_column(String(32), nullable=False)
    filed_at: Mapped[date] = mapped_column(Date, nullable=False)
    report_date: Mapped[date | None] = mapped_column(Date)
    fiscal_year: Mapped[int | None] = mapped_column(Integer)
    fiscal_period: Mapped[str | None] = mapped_column(String(16))
    primary_document: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)


class CompanyFinancialFact(IntegerIdMixin, TimestampMixin, Base):
    """One standardized SEC XBRL observation with filing provenance."""

    __tablename__ = "company_financial_facts"
    __table_args__ = (
        UniqueConstraint(
            "ticker",
            "taxonomy",
            "concept",
            "unit",
            "period_end",
            "filed_at",
            "accession_number",
            name="uq_company_financial_fact_observation",
        ),
        Index(
            "ix_company_facts_ticker_concept_end",
            "ticker",
            "concept",
            "period_end",
        ),
    )

    ticker: Mapped[str] = mapped_column(
        ForeignKey("company_profiles.ticker", ondelete="CASCADE"),
        nullable=False,
    )
    taxonomy: Mapped[str] = mapped_column(String(32), nullable=False)
    concept: Mapped[str] = mapped_column(String(128), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    filed_at: Mapped[date] = mapped_column(Date, nullable=False)
    form: Mapped[str] = mapped_column(String(32), nullable=False)
    fiscal_year: Mapped[int | None] = mapped_column(Integer)
    fiscal_period: Mapped[str | None] = mapped_column(String(16))
    frame: Mapped[str | None] = mapped_column(String(32))
    accession_number: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)


class CompanySyncState(Base):
    """Per-company SEC and price synchronization audit."""

    __tablename__ = "company_sync_states"

    ticker: Mapped[str] = mapped_column(
        ForeignKey("company_profiles.ticker", ondelete="CASCADE"),
        primary_key=True,
    )
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    facts_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filings_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prices_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)


class ChinaDisclosureSyncState(TimestampMixin, Base):
    """Restart-safe CNINFO disclosure and full-text archive coverage per A-share."""

    __tablename__ = "china_disclosure_sync_states"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'discovering', 'completed', 'partial', 'failed')",
            name="china_disclosure_sync_status",
        ),
        Index(
            "ix_china_disclosure_sync_status_success",
            "status",
            "last_success_at",
        ),
    )

    ticker: Mapped[str] = mapped_column(String(16), primary_key=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    org_id: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    announcements_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    documents_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    documents_archived: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    periodic_reports: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shareholder_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    operating_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    supply_chain_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class CompanyInstitutionalHolding(IntegerIdMixin, TimestampMixin, Base):
    """One issuer holding disclosed in a structured SEC Form 13F filing."""

    __tablename__ = "company_institutional_holdings"
    __table_args__ = (
        UniqueConstraint(
            "ticker",
            "accession_number",
            "info_table_key",
            name="uq_company_institutional_holding_filing_row",
        ),
        Index(
            "ix_company_institutional_ticker_period",
            "ticker",
            "report_period",
        ),
    )

    ticker: Mapped[str] = mapped_column(
        ForeignKey("company_profiles.ticker", ondelete="CASCADE"),
        nullable=False,
    )
    cusip: Mapped[str] = mapped_column(String(9), nullable=False)
    accession_number: Mapped[str] = mapped_column(String(32), nullable=False)
    info_table_key: Mapped[str] = mapped_column(String(64), nullable=False)
    report_period: Mapped[date] = mapped_column(Date, nullable=False)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    manager_cik: Mapped[str] = mapped_column(String(16), nullable=False)
    manager_name: Mapped[str] = mapped_column(String(255), nullable=False)
    issuer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    title_of_class: Mapped[str] = mapped_column(String(128), nullable=False)
    value_thousands: Mapped[float] = mapped_column(Float, nullable=False)
    shares_or_principal: Mapped[float] = mapped_column(Float, nullable=False)
    shares_type: Mapped[str] = mapped_column(String(16), nullable=False)
    put_call: Mapped[str | None] = mapped_column(String(16))
    investment_discretion: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)


class InstitutionalArchiveState(Base):
    """Download/import checkpoint for one official quarterly 13F ZIP."""

    __tablename__ = "institutional_archive_states"

    archive_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    local_path: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    archive_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    holdings_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reviewed_universe_version: Mapped[str | None] = mapped_column(String(64))
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class CompanyInsiderTransaction(IntegerIdMixin, TimestampMixin, Base):
    """One transaction parsed from an official SEC ownership XML filing."""

    __tablename__ = "company_insider_transactions"
    __table_args__ = (
        UniqueConstraint(
            "accession_number",
            "transaction_kind",
            "transaction_index",
            name="uq_company_insider_transaction_filing_row",
        ),
        Index(
            "ix_company_insider_ticker_transaction_date",
            "ticker",
            "transaction_date",
        ),
    )

    ticker: Mapped[str] = mapped_column(
        ForeignKey("company_profiles.ticker", ondelete="CASCADE"),
        nullable=False,
    )
    accession_number: Mapped[str] = mapped_column(
        ForeignKey("company_filings.accession_number", ondelete="CASCADE"),
        nullable=False,
    )
    form: Mapped[str] = mapped_column(String(32), nullable=False)
    filed_at: Mapped[date] = mapped_column(Date, nullable=False)
    transaction_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    transaction_index: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_date: Mapped[date | None] = mapped_column(Date)
    deemed_execution_date: Mapped[date | None] = mapped_column(Date)
    security_title: Mapped[str] = mapped_column(String(255), nullable=False)
    transaction_code: Mapped[str | None] = mapped_column(String(8))
    acquired_disposed: Mapped[str | None] = mapped_column(String(1))
    shares: Mapped[float | None] = mapped_column(Float)
    price_per_share: Mapped[float | None] = mapped_column(Float)
    shares_owned_following: Mapped[float | None] = mapped_column(Float)
    direct_or_indirect: Mapped[str | None] = mapped_column(String(1))
    ownership_nature: Mapped[str | None] = mapped_column(Text)
    derivative_exercise_price: Mapped[float | None] = mapped_column(Float)
    derivative_exercise_date: Mapped[date | None] = mapped_column(Date)
    derivative_expiration_date: Mapped[date | None] = mapped_column(Date)
    underlying_security_title: Mapped[str | None] = mapped_column(String(255))
    underlying_shares: Mapped[float | None] = mapped_column(Float)
    equity_swap_involved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_10b5_1: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reporting_owners: Mapped[list[dict[str, object]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    footnote_text: Mapped[str | None] = mapped_column(Text)
    remarks: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)


class CompanyInsiderFilingState(Base):
    """Restart-safe download and parse checkpoint for one ownership filing."""

    __tablename__ = "company_insider_filing_states"

    accession_number: Mapped[str] = mapped_column(
        ForeignKey("company_filings.accession_number", ondelete="CASCADE"),
        primary_key=True,
    )
    ticker: Mapped[str] = mapped_column(
        ForeignKey("company_profiles.ticker", ondelete="CASCADE"),
        nullable=False,
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_archive_path: Mapped[str | None] = mapped_column(Text)
    raw_sha256: Mapped[str | None] = mapped_column(String(64))
    raw_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    transactions_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parser_version: Mapped[str | None] = mapped_column(String(64))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
