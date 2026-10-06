"""Locally retained market and macro-financial time series."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class MarketSeries(TimestampMixin, Base):
    """Reviewed metadata for one market or macro-financial series."""

    __tablename__ = "market_series"

    series_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    frequency: Mapped[str] = mapped_column(String(32), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    listing_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unknown",
        server_default="unknown",
    )
    listed_from: Mapped[date | None] = mapped_column(Date)
    listed_until: Mapped[date | None] = mapped_column(Date)
    delisting_return: Mapped[float | None] = mapped_column(Float)
    sector: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    neutralization_group: Mapped[str | None] = mapped_column(String(160))


class MarketObservation(Base):
    """One dated observation retained from an official or licensed provider."""

    __tablename__ = "market_observations"
    __table_args__ = (
        Index("ix_market_observations_observed_on", "observed_on"),
        Index("ix_market_observations_series_date", "series_id", "observed_on"),
    )

    series_id: Mapped[str] = mapped_column(
        ForeignKey("market_series.series_id", ondelete="CASCADE"),
        primary_key=True,
    )
    observed_on: Mapped[date] = mapped_column(Date, primary_key=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MarketDailyBar(Base):
    """One split-adjusted daily OHLCV bar retained alongside scalar series."""

    __tablename__ = "market_daily_bars"
    __table_args__ = (
        Index("ix_market_daily_bars_observed_on", "observed_on"),
        Index("ix_market_daily_bars_series_date", "series_id", "observed_on"),
    )

    series_id: Mapped[str] = mapped_column(
        ForeignKey("market_series.series_id", ondelete="CASCADE"),
        primary_key=True,
    )
    observed_on: Mapped[date] = mapped_column(Date, primary_key=True)
    open_price: Mapped[float] = mapped_column(Float, nullable=False)
    high_price: Mapped[float] = mapped_column(Float, nullable=False)
    low_price: Mapped[float] = mapped_column(Float, nullable=False)
    close_price: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float | None] = mapped_column(Float)
    adjustment: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="splits",
        server_default="splits",
    )
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MarketSyncState(Base):
    """Auditable status and retained range for one market provider."""

    __tablename__ = "market_sync_states"

    provider_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    history_start: Mapped[date | None] = mapped_column(Date)
    history_end: Mapped[date | None] = mapped_column(Date)
    series_synced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    observations_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)


class MarketAssetLifecycle(Base):
    """One provider-discovered equity lifecycle used to reconstruct historical universes."""

    __tablename__ = "market_asset_lifecycles"
    __table_args__ = (
        Index(
            "ix_market_asset_lifecycles_provider_status_dates",
            "provider_key",
            "listing_status",
            "ipo_date",
            "delisting_date",
        ),
        Index(
            "ix_market_asset_lifecycles_symbol_exchange",
            "symbol",
            "exchange",
        ),
    )

    asset_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    exchange: Mapped[str] = mapped_column(String(64), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(64), nullable=False)
    ipo_date: Mapped[date | None] = mapped_column(Date)
    delisting_date: Mapped[date | None] = mapped_column(Date)
    listing_status: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)


class MarketPriceBackfillState(TimestampMixin, Base):
    """Attempt and priority state for one lifecycle-safe historical price backfill."""

    __tablename__ = "market_price_backfill_states"
    __table_args__ = (
        Index(
            "ix_market_price_backfill_states_status_priority",
            "status",
            "priority_score",
        ),
    )

    asset_key: Mapped[str] = mapped_column(
        ForeignKey("market_asset_lifecycles.asset_key", ondelete="CASCADE"),
        primary_key=True,
    )
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    priority_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    priority_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observations_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    observed_start: Mapped[date | None] = mapped_column(Date)
    observed_end: Mapped[date | None] = mapped_column(Date)
    series_id: Mapped[str | None] = mapped_column(
        ForeignKey("market_series.series_id", ondelete="SET NULL")
    )
    source_series_id: Mapped[str | None] = mapped_column(
        ForeignKey("market_series.series_id", ondelete="SET NULL")
    )
    lifecycle_evidence_key: Mapped[str | None] = mapped_column(
        ForeignKey(
            "market_delisting_evidence_candidates.evidence_key",
            ondelete="SET NULL",
        )
    )
    provider_delisting_date: Mapped[date | None] = mapped_column(Date)
    lifecycle_terminal_date: Mapped[date | None] = mapped_column(Date)
    lifecycle_segment_method: Mapped[str | None] = mapped_column(String(64))
    lifecycle_segmented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    raw_archive_path: Mapped[str | None] = mapped_column(Text)
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_error_message: Mapped[str | None] = mapped_column(Text)


class MarketAssetIdentifier(TimestampMixin, Base):
    """Cross-provider identity gate for one discovered historical security."""

    __tablename__ = "market_asset_identifiers"
    __table_args__ = (
        Index("ix_market_asset_identifiers_status", "identity_status"),
        Index("ix_market_asset_identifiers_figi", "composite_figi"),
    )

    asset_key: Mapped[str] = mapped_column(
        ForeignKey("market_asset_lifecycles.asset_key", ondelete="CASCADE"),
        primary_key=True,
    )
    identity_status: Mapped[str] = mapped_column(String(32), nullable=False)
    mapping_method: Mapped[str | None] = mapped_column(String(64))
    figi: Mapped[str | None] = mapped_column(String(32))
    composite_figi: Mapped[str | None] = mapped_column(String(32))
    share_class_figi: Mapped[str | None] = mapped_column(String(32))
    sec_cik: Mapped[str | None] = mapped_column(String(16))
    mapped_ticker: Mapped[str | None] = mapped_column(String(64))
    mapped_name: Mapped[str | None] = mapped_column(String(255))
    mapped_exchange: Mapped[str | None] = mapped_column(String(64))
    security_type: Mapped[str | None] = mapped_column(String(64))
    name_similarity: Mapped[float | None] = mapped_column(Float)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_archive_path: Mapped[str | None] = mapped_column(Text)
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_error_message: Mapped[str | None] = mapped_column(Text)


class MarketDelistingOutcome(TimestampMixin, Base):
    """Audited post-delisting shareholder value and derived terminal return."""

    __tablename__ = "market_delisting_outcomes"
    __table_args__ = (
        Index("ix_market_delisting_outcomes_status", "status"),
    )

    asset_key: Mapped[str] = mapped_column(
        ForeignKey("market_asset_lifecycles.asset_key", ondelete="CASCADE"),
        primary_key=True,
    )
    series_id: Mapped[str | None] = mapped_column(
        ForeignKey("market_series.series_id", ondelete="SET NULL")
    )
    evidence_key: Mapped[str | None] = mapped_column(
        ForeignKey(
            "market_delisting_evidence_candidates.evidence_key",
            ondelete="SET NULL",
        )
    )
    valuation_evidence_key: Mapped[str | None] = mapped_column(
        ForeignKey(
            "market_delisting_evidence_candidates.evidence_key",
            ondelete="SET NULL",
        )
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome_type: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    last_trade_date: Mapped[date | None] = mapped_column(Date)
    last_trade_price: Mapped[float | None] = mapped_column(Float)
    terminal_value_per_share: Mapped[float | None] = mapped_column(Float)
    exchange_ratio: Mapped[float | None] = mapped_column(Float)
    acquirer_symbol: Mapped[str | None] = mapped_column(String(64))
    acquirer_price_on_payment: Mapped[float | None] = mapped_column(Float)
    acquirer_price_observed_on: Mapped[date | None] = mapped_column(Date)
    resolution_method: Mapped[str | None] = mapped_column(String(64))
    cashflow_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    terminal_is_final: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default="false",
    )
    payment_date: Mapped[date | None] = mapped_column(Date)
    delisting_return: Mapped[float | None] = mapped_column(Float)
    evidence_url: Mapped[str | None] = mapped_column(Text)
    evidence_note: Mapped[str | None] = mapped_column(Text)
    evidence_hash: Mapped[str | None] = mapped_column(String(64))
    verification_method: Mapped[str | None] = mapped_column(String(64))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketLifecycleResolution(TimestampMixin, Base):
    """Human-reviewed correction layered over a provider lifecycle snapshot."""

    __tablename__ = "market_lifecycle_resolutions"
    __table_args__ = (
        Index("ix_market_lifecycle_resolutions_type", "resolution_type"),
        Index("ix_market_lifecycle_resolutions_status", "authoritative_status"),
    )

    asset_key: Mapped[str] = mapped_column(
        ForeignKey("market_asset_lifecycles.asset_key", ondelete="CASCADE"),
        primary_key=True,
    )
    resolution_type: Mapped[str] = mapped_column(String(64), nullable=False)
    authoritative_status: Mapped[str] = mapped_column(String(32), nullable=False)
    authoritative_delisting_date: Mapped[date | None] = mapped_column(Date)
    evidence_url: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_note: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MarketTerminalCashflow(TimestampMixin, Base):
    """One reviewed shareholder cashflow in a multi-stage terminal outcome."""

    __tablename__ = "market_terminal_cashflows"
    __table_args__ = (
        Index("ix_market_terminal_cashflows_asset_date", "asset_key", "payment_date"),
        Index("ix_market_terminal_cashflows_status", "status"),
    )

    cashflow_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    asset_key: Mapped[str] = mapped_column(
        ForeignKey("market_asset_lifecycles.asset_key", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_key: Mapped[str] = mapped_column(
        ForeignKey(
            "market_delisting_evidence_candidates.evidence_key",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    cashflow_type: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_per_share: Mapped[float] = mapped_column(Float, nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    is_final: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default="false",
    )
    evidence_url: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_note: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MarketDelistingEvidenceState(TimestampMixin, Base):
    """Per-asset SEC discovery state, including explicit full-text access readiness."""

    __tablename__ = "market_delisting_evidence_states"
    __table_args__ = (
        Index("ix_market_delisting_evidence_states_status", "status"),
    )

    asset_key: Mapped[str] = mapped_column(
        ForeignKey("market_asset_lifecycles.asset_key", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")
    sec_cik: Mapped[str | None] = mapped_column(String(16))
    cik_name: Mapped[str | None] = mapped_column(String(255))
    cik_name_similarity: Mapped[float | None] = mapped_column(Float)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filing_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extracted_candidate_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    body_access_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="contact_required",
    )
    search_start: Mapped[date | None] = mapped_column(Date)
    search_end: Mapped[date | None] = mapped_column(Date)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_archive_path: Mapped[str | None] = mapped_column(Text)
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_error_message: Mapped[str | None] = mapped_column(Text)


class MarketDelistingEvidenceCandidate(TimestampMixin, Base):
    """One immutable filing or extracted terminal-value candidate awaiting review."""

    __tablename__ = "market_delisting_evidence_candidates"
    __table_args__ = (
        Index(
            "ix_market_delisting_evidence_candidates_asset_review",
            "asset_key",
            "review_status",
        ),
        Index(
            "ix_market_delisting_evidence_candidates_accession",
            "accession_number",
        ),
    )

    evidence_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    asset_key: Mapped[str] = mapped_column(
        ForeignKey("market_asset_lifecycles.asset_key", ondelete="CASCADE"),
        nullable=False,
    )
    sec_cik: Mapped[str] = mapped_column(String(16), nullable=False)
    subject_symbol: Mapped[str | None] = mapped_column(String(64))
    subject_sec_cik: Mapped[str | None] = mapped_column(String(16))
    accession_number: Mapped[str] = mapped_column(String(40), nullable=False)
    document_name: Mapped[str] = mapped_column(String(255), nullable=False)
    form: Mapped[str] = mapped_column(String(32), nullable=False)
    filed_on: Mapped[date] = mapped_column(Date, nullable=False)
    observed_on: Mapped[date | None] = mapped_column(Date)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    candidate_value: Mapped[float | None] = mapped_column(Float)
    value_unit: Mapped[str | None] = mapped_column(String(32))
    evidence_excerpt: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    body_status: Mapped[str] = mapped_column(String(32), nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="candidate",
    )
    review_role: Mapped[str | None] = mapped_column(String(32))
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_archive_path: Mapped[str | None] = mapped_column(Text)
