"""Compute source coverage from retained records rather than configuration alone."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import Date, and_, case, cast, func, select
from sqlalchemy.orm import Session

from app.alpha_vantage_listings import alpha_vantage_listing_coverage
from app.collectors.gdelt import (
    GDELT_DOC_BACKFILL_STATE_KEY,
    GDELT_DOC_SOURCE_BOUNDARY,
)
from app.companies import company_coverage
from app.conflicts.acled_aggregate import ACLED_COUNTRY_HISTORY_PRODUCTS
from app.core.config import Settings
from app.db.models import (
    ConflictAggregateObservation,
    ConflictAggregateSyncState,
    ConflictCountryIndicatorObservation,
    CountryProfile,
    Document,
    EconomicIndicator,
    EconomicObservation,
    EconomicSyncState,
    EnergyObservation,
    EnergySeries,
    EnergySyncState,
    Event,
    EventDocument,
    GdeltArchiveState,
    RSSFeed,
    Source,
)
from app.gdelt_history import gdelt_history_coverage
from app.institutional_history import institutional_coverage
from app.market_history import (
    market_history_coverage,
    twelve_data_history_coverage,
)
from app.schemas.coverage import CoverageResponse, CoverageStatus, DatasetCoverage

HISTORY_DAYS = 365


def build_coverage_report(
    session: Session,
    *,
    settings: Settings,
    now: datetime | None = None,
    include_sources: bool = True,
) -> CoverageResponse:
    """Return measured coverage, timestamp quality and known provider gaps."""
    generated_at = now or datetime.now(UTC)
    target_end = generated_at.date()
    target_start = target_end - timedelta(days=HISTORY_DAYS - 1)
    gdelt_news = _document_dataset(
        session,
        collector="gdelt_doc_discovery",
        key="news_gdelt",
        name="Multilingual historical news discovery",
        provider="GDELT DOC 2.0",
        target_start=target_start,
        target_end=target_end,
        last_success_at=session.scalar(
            select(func.max(Document.fetched_at)).where(
                Document.raw_metadata["collector"].as_string()
                == "gdelt_doc_discovery"
            )
        ),
        notes=[
            "Publisher titles, URLs and timestamps are retained; publisher full text "
            "is not copied unless separately licensed.",
            (
                "Official DOC 2.0 searchable boundary: "
                f"{GDELT_DOC_SOURCE_BOUNDARY.isoformat()}."
            ),
            "Automatic backfill uses restart-safe 30-day windows and conservative "
            "rate-limit cooldowns.",
            *_gdelt_doc_backfill_notes(session),
        ],
    )
    gdelt_state = session.get(GdeltArchiveState, GDELT_DOC_BACKFILL_STATE_KEY)
    if gdelt_state is None or gdelt_state.status != "completed_source_boundary":
        gdelt_news.status = "partial" if gdelt_news.record_count else "missing"
    datasets = [
        _document_dataset(
            session,
            collector="rss",
            key="news_rss",
            name="Licensed and public RSS news",
            provider="Publisher RSS/Atom feeds",
            target_start=target_start,
            target_end=target_end,
            last_success_at=session.scalar(select(func.max(RSSFeed.last_success_at))),
            notes=[
                "Completeness is measured as observed publication days in the requested "
                "365-day window; RSS feeds often expose only their latest entries."
            ],
        ),
        _gdelt_event_history_coverage(session),
        gdelt_news,
        _ucdp_coverage(session, target_start=target_start, target_end=target_end),
        _acled_coverage(session, target_start=target_start, target_end=target_end),
        _acled_country_history_coverage(session),
        _economic_coverage(session),
        _energy_coverage(session),
        _fred_market_coverage(
            session,
            configured=settings.fred_api_key is not None,
        ),
        _twelve_market_coverage(
            session,
            configured=settings.twelve_data_api_key is not None,
        ),
        _alpha_vantage_lifecycle_coverage(
            session,
            configured=settings.alpha_vantage_api_key is not None,
        ),
        _company_sec_coverage(session),
        _company_price_coverage(
            session,
            configured=settings.twelve_data_api_key is not None,
        ),
        _company_institutional_coverage(session),
    ]
    return CoverageResponse(
        generated_at=generated_at,
        target_starts_at=target_start.isoformat(),
        target_ends_at=target_end.isoformat(),
        datasets=datasets,
        sources=(
            _rss_source_coverage(
                session,
                target_start=target_start,
                target_end=target_end,
            )
            if include_sources
            else []
        ),
    )


def _document_dataset(
    session: Session,
    *,
    collector: str,
    key: str,
    name: str,
    provider: str,
    target_start: date,
    target_end: date,
    last_success_at: datetime | None,
    notes: list[str],
) -> DatasetCoverage:
    collector_column = Document.raw_metadata["collector"].as_string()
    total, timestamped, with_content, first_at, last_at, periods = session.execute(
        select(
            func.count(Document.id),
            func.sum(case((Document.published_at.is_not(None), 1), else_=0)),
            func.sum(
                case(
                    (func.length(func.coalesce(Document.body, "")) >= 100, 1),
                    else_=0,
                )
            ),
            func.min(Document.published_at),
            func.max(Document.published_at),
            func.count(func.distinct(cast(Document.published_at, Date))).filter(
                Document.published_at >= _day_start(target_start),
                Document.published_at < _day_start(target_end + timedelta(days=1)),
            ),
        ).where(collector_column == collector)
    ).one()
    total_int = int(total or 0)
    timestamped_int = int(timestamped or 0)
    with_content_int = int(with_content or 0)
    period_count = int(periods or 0)
    expected = (target_end - target_start).days + 1
    completeness = min(period_count / expected, 1.0)
    timestamp_ratio = timestamped_int / total_int if total_int else None
    return DatasetCoverage(
        key=key,
        name=name,
        provider=provider,
        category="news",
        starts_at=_iso(first_at),
        ends_at=_iso(last_at),
        record_count=total_int,
        distinct_periods=period_count,
        expected_periods=expected,
        completeness_ratio=completeness,
        timestamp_ratio=timestamp_ratio,
        content_ratio=(with_content_int / total_int if total_int else None),
        headline_only_count=max(total_int - with_content_int, 0),
        last_success_at=last_success_at,
        status=_status(
            count=total_int,
            completeness=completeness,
            timestamp_ratio=timestamp_ratio,
            last_at=last_at,
            target_end=target_end,
        ),
        notes=notes,
    )


def _gdelt_doc_backfill_notes(session: Session) -> list[str]:
    state = session.get(GdeltArchiveState, GDELT_DOC_BACKFILL_STATE_KEY)
    if state is None:
        return ["Historical discovery checkpoint is awaiting its first run."]
    notes = [
        f"Historical discovery checkpoint: {state.starts_at or 'unknown'}; "
        f"status={state.status}."
    ]
    if state.last_error:
        notes.append(f"last backfill error: {state.last_error[:240]}")
    return notes


def _rss_source_coverage(
    session: Session,
    *,
    target_start: date,
    target_end: date,
) -> list[DatasetCoverage]:
    collector_column = Document.raw_metadata["collector"].as_string()
    rows = session.execute(
        select(
            RSSFeed.id,
            Source.name,
            Source.country,
            Source.language,
            RSSFeed.last_success_at,
            RSSFeed.last_error,
            func.count(Document.id),
            func.sum(case((Document.published_at.is_not(None), 1), else_=0)),
            func.sum(
                case(
                    (func.length(func.coalesce(Document.body, "")) >= 100, 1),
                    else_=0,
                )
            ),
            func.min(Document.published_at),
            func.max(Document.published_at),
            func.count(func.distinct(cast(Document.published_at, Date))).filter(
                Document.published_at >= _day_start(target_start),
                Document.published_at < _day_start(target_end + timedelta(days=1)),
            ),
        )
        .join(Source, Source.id == RSSFeed.source_id)
        .outerjoin(
            Document,
            and_(
                Document.source_id == Source.id,
                collector_column == "rss",
            ),
        )
        .where(RSSFeed.enabled.is_(True))
        .group_by(
            RSSFeed.id,
            Source.name,
            Source.country,
            Source.language,
            RSSFeed.last_success_at,
            RSSFeed.last_error,
        )
        .order_by(Source.name)
    ).all()
    expected = (target_end - target_start).days + 1
    result: list[DatasetCoverage] = []
    for (
        feed_id,
        source_name,
        country,
        language,
        last_success_at,
        last_error,
        total,
        timestamped,
        with_content,
        first_at,
        last_at,
        periods,
    ) in rows:
        total_int = int(total or 0)
        timestamped_int = int(timestamped or 0)
        with_content_int = int(with_content or 0)
        period_count = int(periods or 0)
        completeness = min(period_count / expected, 1.0)
        timestamp_ratio = timestamped_int / total_int if total_int else None
        source_notes = [
            f"country={country or 'global'}; language={language or 'unknown'}",
        ]
        if last_error:
            source_notes.append(f"last error: {str(last_error)[:240]}")
        result.append(
            DatasetCoverage(
                key=f"rss_feed_{feed_id}",
                name=source_name,
                provider="RSS/Atom",
                category="news",
                starts_at=_iso(first_at),
                ends_at=_iso(last_at),
                record_count=total_int,
                distinct_periods=period_count,
                expected_periods=expected,
                completeness_ratio=completeness,
                timestamp_ratio=timestamp_ratio,
                content_ratio=(
                    with_content_int / total_int if total_int else None
                ),
                headline_only_count=max(total_int - with_content_int, 0),
                last_success_at=last_success_at,
                status=_status(
                    count=total_int,
                    completeness=completeness,
                    timestamp_ratio=timestamp_ratio,
                    last_at=last_at,
                    target_end=target_end,
                ),
                notes=source_notes,
            )
        )
    return result


def _ucdp_coverage(
    session: Session,
    *,
    target_start: date,
    target_end: date,
) -> DatasetCoverage:
    collector_column = Document.raw_metadata["collector"].as_string()
    total, first_at, last_at, periods, last_import = session.execute(
        select(
            func.count(func.distinct(Event.id)),
            func.min(Event.start_at),
            func.max(func.coalesce(Event.end_at, Event.start_at)),
            func.count(func.distinct(cast(Event.start_at, Date))).filter(
                Event.start_at >= _day_start(target_start),
                Event.start_at < _day_start(target_end + timedelta(days=1)),
            ),
            func.max(Document.fetched_at),
        )
        .join(EventDocument, EventDocument.event_id == Event.id)
        .join(Document, Document.id == EventDocument.document_id)
        .where(collector_column == "ucdp_gedevents")
    ).one()
    count = int(total or 0)
    period_count = int(periods or 0)
    expected = (target_end - target_start).days + 1
    completeness = min(period_count / expected, 1.0)
    return DatasetCoverage(
        key="conflict_ucdp",
        name="Georeferenced conflict events",
        provider="UCDP Candidate Events",
        category="conflict",
        starts_at=_iso(first_at),
        ends_at=_iso(last_at),
        record_count=count,
        distinct_periods=period_count,
        expected_periods=expected,
        completeness_ratio=completeness,
        timestamp_ratio=1.0 if count else None,
        last_success_at=last_import,
        status=_status(
            count=count,
            completeness=completeness,
            timestamp_ratio=1.0 if count else None,
            last_at=last_at,
            target_end=target_end,
            stale_days=45,
        ),
        notes=[
            "Coverage uses event start/end timestamps, not article publication time.",
            "The UCDP GED source boundary is 1989; the historical service now refreshes "
            "1989-2025 while Candidate Events supplies the current year.",
        ],
    )


def _gdelt_event_history_coverage(session: Session) -> DatasetCoverage:
    coverage = gdelt_history_coverage(session)
    status = str(coverage["status"])
    count = int(coverage["event_count"])
    return DatasetCoverage(
        key="historical_gdelt_events",
        name="Global structured event history",
        provider="GDELT Event Database 1.0 archive",
        category="news",
        starts_at=_iso(coverage["starts_at"]),
        ends_at=_iso(coverage["ends_at"]),
        record_count=count,
        distinct_periods=int(coverage["month_count"]),
        expected_periods=int(coverage["expected_month_count"]),
        completeness_ratio=(
            min(
                1.0,
                int(coverage["month_count"])
                / max(1, int(coverage["expected_month_count"])),
            )
            if count
            else 0.0
        ),
        timestamp_ratio=1.0 if count else None,
        content_ratio=0.0 if count else None,
        headline_only_count=None,
        last_success_at=coverage["last_success_at"],
        status=(
            "complete"
            if status == "completed" and count > 0
            else "partial"
            if status in {"downloading", "importing"} or count > 0
            else "missing"
        ),
        notes=[
            "This is structured CAMEO event history, not article full text.",
            (
                "The 1979-2013 reduced archive uses the target actor's CAMEO "
                "country/region prefix when a country field is unavailable."
            ),
            f"Cold archive bytes: {int(coverage['archive_bytes']):,}.",
            *(
                [
                    "Official archive dates recorded as unavailable (HTTP 404): "
                    f"{int(coverage['unavailable_days']):,}."
                ]
                if coverage["unavailable_days"]
                else []
            ),
            *(
                [f"last error: {coverage['last_error']}"]
                if coverage["last_error"]
                else []
            ),
        ],
    )


def _acled_coverage(
    session: Session,
    *,
    target_start: date,
    target_end: date,
) -> DatasetCoverage:
    rows, events, first_week, last_week, periods, last_success = session.execute(
        select(
            func.count(ConflictAggregateObservation.id),
            func.sum(ConflictAggregateObservation.events),
            func.min(ConflictAggregateObservation.week),
            func.max(ConflictAggregateObservation.week),
            func.count(func.distinct(ConflictAggregateObservation.week)).filter(
                ConflictAggregateObservation.week >= target_start,
                ConflictAggregateObservation.week <= target_end,
            ),
            func.max(ConflictAggregateSyncState.last_success_at),
        ).select_from(ConflictAggregateObservation).outerjoin(
            ConflictAggregateSyncState,
            ConflictAggregateSyncState.source_file
            == ConflictAggregateObservation.source_file,
        )
    ).one()
    row_count = int(rows or 0)
    observed_weeks = int(periods or 0)
    expected_weeks = max(((target_end - target_start).days // 7) + 1, 1)
    completeness = min(observed_weeks / expected_weeks, 1.0)
    return DatasetCoverage(
        key="conflict_acled",
        name="Subnational conflict aggregates",
        provider="ACLED licensed export",
        category="conflict",
        starts_at=_iso(first_week),
        ends_at=_iso(last_week),
        record_count=int(events or row_count),
        distinct_periods=observed_weeks,
        expected_periods=expected_weeks,
        completeness_ratio=completeness,
        timestamp_ratio=1.0 if row_count else None,
        last_success_at=last_success,
        status=_status(
            count=row_count,
            completeness=completeness,
            timestamp_ratio=1.0 if row_count else None,
            last_at=last_week,
            target_end=target_end,
            stale_days=21,
        ),
        notes=[
            "Record count is the summed number of events; completeness is measured by weeks.",
            "The currently licensed Open myACLED regional Admin-1 files begin in 2023; "
            "older subnational ACLED history is not exposed by those downloaded files.",
        ],
    )


def _acled_country_history_coverage(session: Session) -> DatasetCoverage:
    count, first_period, last_period, countries, last_import = session.execute(
        select(
            func.count(ConflictCountryIndicatorObservation.id),
            func.min(ConflictCountryIndicatorObservation.period),
            func.max(ConflictCountryIndicatorObservation.period),
            func.count(func.distinct(ConflictCountryIndicatorObservation.country)),
            func.max(ConflictCountryIndicatorObservation.imported_at),
        )
    ).one()
    products = len(
        session.execute(
            select(
                ConflictCountryIndicatorObservation.metric,
                ConflictCountryIndicatorObservation.frequency,
            ).distinct()
        ).all()
    )
    count_int = int(count or 0)
    completeness = min(products / ACLED_COUNTRY_HISTORY_PRODUCTS, 1.0)
    return DatasetCoverage(
        key="conflict_acled_country_history",
        name="Country-level long-run conflict indicators",
        provider="ACLED licensed aggregated country files",
        category="conflict",
        starts_at=_iso(first_period),
        ends_at=_iso(last_period),
        record_count=count_int,
        distinct_periods=products,
        expected_periods=ACLED_COUNTRY_HISTORY_PRODUCTS,
        completeness_ratio=completeness,
        timestamp_ratio=1.0 if count_int else None,
        last_success_at=last_import,
        status=(
            "missing"
            if count_int == 0
            else "complete"
            if completeness >= 1.0
            else "partial"
        ),
        notes=[
            f"{int(countries or 0)} countries retained; country coverage begins in "
            "different years and the earliest available row is reported above.",
            "These are country-period totals, not raw event coordinates or military "
            "positions; they must not be rendered as precise battle locations.",
            "The local watcher automatically imports changed authenticated workbooks "
            "placed in raw/acled/history.",
        ],
    )


def _economic_coverage(session: Session) -> DatasetCoverage:
    count, start_year, end_year, countries, indicators = session.execute(
        select(
            func.count(EconomicObservation.year),
            func.min(EconomicObservation.year),
            func.max(EconomicObservation.year),
            func.count(func.distinct(EconomicObservation.country_iso3)),
            func.count(func.distinct(EconomicObservation.indicator_code)),
        )
    ).one()
    configured_countries = int(session.scalar(select(func.count(CountryProfile.iso3))) or 0)
    configured_indicators = int(
        session.scalar(
            select(func.count(EconomicIndicator.code)).where(
                EconomicIndicator.enabled.is_(True)
            )
        )
        or 0
    )
    count_int = int(count or 0)
    years = (int(end_year) - int(start_year) + 1) if start_year and end_year else 0
    expected = configured_countries * configured_indicators * years
    completeness = min(count_int / expected, 1.0) if expected else None
    last_success = session.scalar(select(func.max(EconomicSyncState.last_success_at)))
    return DatasetCoverage(
        key="economics_world_bank",
        name="Country economic, population and production indicators",
        provider="World Bank Indicators API",
        category="economics",
        starts_at=str(start_year) if start_year is not None else None,
        ends_at=str(end_year) if end_year is not None else None,
        record_count=count_int,
        distinct_periods=years,
        expected_periods=expected or None,
        completeness_ratio=completeness,
        timestamp_ratio=1.0 if count_int else None,
        last_success_at=last_success,
        status=(
            "missing"
            if count_int == 0
            else "complete"
            if completeness is not None and completeness >= 0.95
            else "partial"
        ),
        notes=[
            f"{int(countries or 0)} countries and {int(indicators or 0)} indicators retained.",
            "Annual releases lag the current year; an absent 2026 value is not treated "
            "as a fabricated zero.",
            "Automatic backfill target is 1960, the World Development Indicators "
            "historical boundary used by this application.",
            "Completeness is measured against the configured country-indicator-year grid.",
        ],
    )


def _energy_coverage(session: Session) -> DatasetCoverage:
    count, first_period, last_period, materialized = session.execute(
        select(
            func.count(EnergyObservation.period),
            func.min(EnergyObservation.period),
            func.max(EnergyObservation.period),
            func.count(func.distinct(EnergyObservation.series_id)),
        )
    ).one()
    cataloged = int(session.scalar(select(func.count(EnergySeries.series_id))) or 0)
    count_int = int(count or 0)
    materialized_int = int(materialized or 0)
    completeness = (
        min(materialized_int / cataloged, 1.0)
        if cataloged
        else 0.0
    )
    last_success = session.scalar(select(func.max(EnergySyncState.last_success_at)))
    failed_rows = session.execute(
        select(EnergySyncState.dataset_key, EnergySyncState.last_error)
        .where(EnergySyncState.last_error.is_not(None))
        .order_by(EnergySyncState.dataset_key)
    ).all()
    failure_notes = [
        f"{dataset}: {str(error).strip()[:180]}"
        for dataset, error in failed_rows
        if error
    ]
    return DatasetCoverage(
        key="energy_eia",
        name="Energy supply, production, trade and outlook history",
        provider="US Energy Information Administration bulk archives",
        category="energy",
        starts_at=first_period,
        ends_at=last_period,
        record_count=count_int,
        distinct_periods=materialized_int,
        expected_periods=cataloged or None,
        completeness_ratio=completeness,
        timestamp_ratio=1.0 if count_int else None,
        last_success_at=last_success,
        status=(
            "missing"
            if count_int == 0
            else "complete"
            if completeness >= 0.95
            else "partial"
        ),
        notes=[
            f"{cataloged} series cataloged; {materialized_int} series materialized locally.",
            *(
                [f"Failed datasets: {'; '.join(failure_notes)}"]
                if failure_notes
                else []
            ),
        ],
    )


def _configured_market_coverage(
    *,
    key: str,
    name: str,
    provider: str,
    configured: bool,
    notes: list[str],
) -> DatasetCoverage:
    return DatasetCoverage(
        key=key,
        name=name,
        provider=provider,
        category="market",
        record_count=0,
        completeness_ratio=0.0,
        status="partial" if configured else "missing",
        notes=[
            f"credential status: {'configured' if configured else 'not configured'}",
            *notes,
        ],
    )


def _fred_market_coverage(
    session: Session,
    *,
    configured: bool,
) -> DatasetCoverage:
    coverage = market_history_coverage(session)
    series_count = int(coverage["series_count"])
    expected_series = int(coverage["expected_series_count"])
    completeness = min(series_count / expected_series, 1.0) if expected_series else 0.0
    count = int(coverage["record_count"])
    requested_boundary = _as_date(coverage["requested_history_start"])
    boundary_attempted = (
        requested_boundary is not None
        and requested_boundary <= date(1776, 7, 4)
        and not coverage["last_error"]
    )
    notes = [
        f"{series_count} of {expected_series} reviewed series retained locally.",
        f"credential status: {'configured' if configured else 'not configured'}",
        "Includes policy rates, Treasury yields, equities, inflation, labour, "
        "real activity, credit, liquidity and financial conditions.",
        "Automatic synchronization requests the FRED provider boundary for each series; "
        f"last requested start={coverage['requested_history_start'] or 'unknown'}.",
    ]
    if coverage["last_error"]:
        notes.append(f"last sync warning: {coverage['last_error']}")
    return DatasetCoverage(
        key="market_fred",
        name="US macro, market and economic-cycle history",
        provider="Federal Reserve Economic Data (FRED)",
        category="market",
        starts_at=_iso(coverage["starts_at"]),
        ends_at=_iso(coverage["ends_at"]),
        record_count=count,
        distinct_periods=series_count,
        expected_periods=expected_series,
        completeness_ratio=completeness,
        timestamp_ratio=1.0 if count else None,
        last_success_at=coverage["last_success_at"],
        status=(
            "missing"
            if count == 0
            else "complete"
            if completeness >= 0.95 and boundary_attempted
            else "partial"
        ),
        notes=notes,
    )


def _twelve_market_coverage(
    session: Session,
    *,
    configured: bool,
) -> DatasetCoverage:
    coverage = twelve_data_history_coverage(session)
    series_count = int(coverage["series_count"])
    expected_series = int(coverage["expected_series_count"])
    completeness = min(series_count / expected_series, 1.0) if expected_series else 0.0
    count = int(coverage["record_count"])
    requested_boundary = _as_date(coverage["requested_history_start"])
    boundary_attempted = (
        requested_boundary is not None
        and requested_boundary <= date(1776, 7, 4)
        and not coverage["last_error"]
    )
    notes = [
        f"{series_count} of {expected_series} reviewed global proxy series retained locally.",
        f"credential status: {'configured' if configured else 'not configured'}",
        "Proxy instruments are labeled explicitly and are not presented as official "
        "underlying index levels.",
        "Each proxy uses Twelve Data's earliest_timestamp boundary before chunked "
        "historical retrieval; "
        f"last requested start={coverage['requested_history_start'] or 'unknown'}.",
    ]
    if coverage["last_error"]:
        notes.append(f"last sync warning: {coverage['last_error']}")
    return DatasetCoverage(
        key="market_twelve_data",
        name="Global daily market proxy history",
        provider="Twelve Data",
        category="market",
        starts_at=_iso(coverage["starts_at"]),
        ends_at=_iso(coverage["ends_at"]),
        record_count=count,
        distinct_periods=series_count,
        expected_periods=expected_series,
        completeness_ratio=completeness,
        timestamp_ratio=1.0 if count else None,
        last_success_at=coverage["last_success_at"],
        status=(
            "missing"
            if count == 0
            else "complete"
            if completeness >= 0.95 and boundary_attempted
            else "partial"
        ),
        notes=notes,
    )


def _alpha_vantage_lifecycle_coverage(
    session: Session,
    *,
    configured: bool,
) -> DatasetCoverage:
    coverage = alpha_vantage_listing_coverage(session)
    total = int(coverage["record_count"])
    delisted = int(coverage["delisted_assets"])
    price_covered = int(coverage["local_price_covered_delisted_assets"])
    missing_prices = int(coverage["missing_price_delisted_assets"])
    price_ratio = min(price_covered / delisted, 1.0) if delisted else 0.0
    notes = [
        f"credential status: {'configured' if configured else 'not configured'}",
        (
            f"{int(coverage['active_assets'])} current and {delisted} delisted US stocks/ETFs "
            "discovered in the lifecycle catalog."
        ),
        (
            f"{price_covered} delisted lifecycle rows have a matching local historical-price "
            f"series; {missing_prices} still require licensed or imported price history."
        ),
        (
            f"Backfill queue: {int(coverage['price_backfill_queued_assets'])} materialized, "
            f"{int(coverage['price_backfill_pending_assets'])} pending, "
            f"{int(coverage['price_backfill_factor_ready_assets'])} factor-ready, "
            f"{int(coverage['price_backfill_partial_assets'])} partial, "
            f"{int(coverage['price_backfill_unavailable_assets'])} unavailable, and "
            f"{int(coverage['price_backfill_ticker_reused_assets'])} rejected for ticker reuse."
        ),
        (
            "Listing membership can be reconstructed only after "
            f"{coverage['point_in_time_boundary']}; the earliest retained IPO date is "
            f"{coverage['earliest_ipo_date'] or 'unknown'}, and catalog rows do not contain prices."
        ),
    ]
    if coverage["last_error"]:
        notes.append(f"last sync warning: {coverage['last_error']}")
    return DatasetCoverage(
        key="market_alpha_vantage_lifecycle",
        name="US listed and delisted asset lifecycle catalog",
        provider="Alpha Vantage LISTING_STATUS",
        category="market",
        starts_at=_iso(coverage["starts_at"]),
        ends_at=_iso(coverage["ends_at"]),
        record_count=total,
        distinct_periods=price_covered,
        expected_periods=delisted,
        completeness_ratio=price_ratio,
        timestamp_ratio=1.0 if total else None,
        last_success_at=coverage["last_success_at"],
        status=(
            "missing"
            if total == 0
            else "complete"
            if delisted > 0 and missing_prices == 0
            else "partial"
        ),
        notes=notes,
    )


def _company_sec_coverage(session: Session) -> DatasetCoverage:
    coverage = company_coverage(session)
    companies = int(coverage["company_count"])
    expected = int(coverage["expected_company_count"])
    facts = int(coverage["fact_count"])
    completeness = min(companies / expected, 1.0) if expected else 0.0
    return DatasetCoverage(
        key="company_sec",
        name="US large-company filings and standardized fundamentals",
        provider="SEC EDGAR Submissions and Company Facts",
        category="market",
        starts_at=_iso(coverage["fact_start"]),
        ends_at=_iso(coverage["fact_end"]),
        record_count=facts,
        distinct_periods=companies,
        expected_periods=expected,
        completeness_ratio=completeness,
        timestamp_ratio=1.0 if facts else None,
        last_success_at=coverage["last_success_at"],
        status=(
            "missing"
            if facts == 0
            else "complete"
            if completeness >= 0.95
            else "partial"
        ),
        notes=[
            f"{companies} of {expected} reviewed companies; "
            f"{int(coverage['filing_count'])} filing references.",
            "SEC standardized XBRL facts are primary-source data; company-specific "
            "extensions may not be directly comparable.",
        ],
    )


def _company_price_coverage(
    session: Session,
    *,
    configured: bool,
) -> DatasetCoverage:
    coverage = company_coverage(session)
    priced = int(coverage["priced_companies"])
    expected = int(coverage["expected_company_count"])
    count = int(coverage["price_count"])
    completeness = min(priced / expected, 1.0) if expected else 0.0
    return DatasetCoverage(
        key="company_prices",
        name="US large-company daily price history",
        provider="Twelve Data",
        category="market",
        starts_at=_iso(coverage["price_start"]),
        ends_at=_iso(coverage["price_end"]),
        record_count=count,
        distinct_periods=priced,
        expected_periods=expected,
        completeness_ratio=completeness,
        timestamp_ratio=1.0 if count else None,
        last_success_at=coverage["last_success_at"],
        status=(
            "missing"
            if count == 0
            else "complete"
            if completeness >= 0.95
            else "partial"
        ),
        notes=[
            f"{priced} of {expected} reviewed companies have local prices.",
            f"credential status: {'configured' if configured else 'not configured'}",
            "Prices are split-adjusted provider observations; freshness and history "
            "depend on the personal data plan.",
            "Each company is backfilled to the symbol-specific earliest_timestamp, then "
            "refreshed daily.",
        ],
    )


def _company_institutional_coverage(session: Session) -> DatasetCoverage:
    coverage = institutional_coverage(session)
    completed = int(coverage["archives_completed"])
    expected_archives = 53
    count = int(coverage["count"])
    completeness = min(completed / expected_archives, 1.0)
    return DatasetCoverage(
        key="company_institutional_13f",
        name="US institutional holdings for reviewed issuers",
        provider="SEC Form 13F structured quarterly archives",
        category="market",
        starts_at=_iso(coverage["starts_at"]),
        ends_at=_iso(coverage["ends_at"]),
        record_count=count,
        distinct_periods=completed,
        expected_periods=expected_archives,
        completeness_ratio=completeness,
        timestamp_ratio=1.0 if count else None,
        last_success_at=coverage["last_success_at"],
        status=(
            "missing"
            if count == 0
            else "complete"
            if completeness >= 1.0
            else "partial"
        ),
        notes=[
            "Official structured archive boundary is May 2013; new quarters are "
            "discovered from the SEC download page automatically.",
            f"{int(coverage['manager_count'])} distinct reporting managers retained.",
            "13F is delayed, may be amended, omits cost basis and does not identify "
            "the exact active/passive fund vehicle behind every manager position.",
        ],
    )


def _status(
    *,
    count: int,
    completeness: float,
    timestamp_ratio: float | None,
    last_at: Any,
    target_end: date,
    stale_days: int = 7,
) -> CoverageStatus:
    if count == 0:
        return "missing"
    last_date = _as_date(last_at)
    if last_date is not None and last_date < target_end - timedelta(days=stale_days):
        return "stale"
    if timestamp_ratio is None or timestamp_ratio < 0.98 or completeness < 0.95:
        return "partial"
    return "complete"


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _day_start(value: date) -> datetime:
    return datetime(value.year, value.month, value.day, tzinfo=UTC)
