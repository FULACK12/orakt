"""Read services for bilingual economic indicator and map endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    CountryProfile,
    EconomicIndicator,
    EconomicObservation,
    EconomicSyncState,
)
from app.schemas.economics import (
    EconomicCountryDetailResponse,
    EconomicCountryMetric,
    EconomicCountryPoint,
    EconomicCountryRanking,
    EconomicIndicatorListResponse,
    EconomicIndicatorView,
    EconomicMapResponse,
    EconomicMetricRank,
    EconomicRankingResponse,
    EconomicRankingWeight,
    EconomicSyncStatusView,
)


class EconomicIndicatorNotFoundError(LookupError):
    """Requested indicator is not enabled or has not been catalogued."""


class EconomicCountryNotFoundError(LookupError):
    """Requested ISO-2 country is not present in the provider catalog."""


RANKING_COMPONENTS: dict[str, tuple[float, str, float | None]] = {
    "NY.GDP.MKTP.CD": (18, "higher", None),
    "NY.GDP.PCAP.CD": (14, "higher", None),
    "NY.GDP.MKTP.KD.ZG": (12, "higher", None),
    "FP.CPI.TOTL.ZG": (10, "target", 2.0),
    "SL.UEM.TOTL.ZS": (10, "lower", None),
    "GC.DOD.TOTL.GD.ZS": (10, "lower", None),
    "FI.RES.TOTL.CD": (10, "higher", None),
    "NV.IND.MANF.CD": (9, "higher", None),
    "BN.CAB.XOKA.GD.ZS": (7, "higher", None),
}


def list_indicators(session: Session) -> EconomicIndicatorListResponse:
    """Return the reviewed, enabled indicator catalog."""
    rows = list(
        session.scalars(
            select(EconomicIndicator)
            .where(EconomicIndicator.enabled.is_(True))
            .order_by(EconomicIndicator.name_en)
        )
    )
    return EconomicIndicatorListResponse(
        indicators=[
            EconomicIndicatorView.model_validate(row)
            for row in rows
        ]
    )


def build_economic_map(
    session: Session,
    *,
    indicator_code: str,
    year: int | None,
) -> EconomicMapResponse:
    """Build one same-year country comparison using capital reference points."""
    indicator = session.get(EconomicIndicator, indicator_code)
    if indicator is None or not indicator.enabled:
        raise EconomicIndicatorNotFoundError(indicator_code)

    coverage_rows = [
        (int(row[0]), int(row[1]))
        for row in session.execute(
            select(
                EconomicObservation.year,
                func.count(EconomicObservation.country_iso3),
            )
            .where(EconomicObservation.indicator_code == indicator_code)
            .group_by(EconomicObservation.year)
            .order_by(EconomicObservation.year.desc())
        ).all()
    ]
    available_years = sorted(
        {datetime.now(UTC).year, *(row[0] for row in coverage_rows)},
        reverse=True,
    )
    selected_year = year
    if selected_year is None:
        selected_year = _newest_well_covered_year(coverage_rows)

    points: list[EconomicCountryPoint] = []
    if selected_year is not None:
        rows = session.execute(
            select(EconomicObservation, CountryProfile)
            .join(
                CountryProfile,
                CountryProfile.iso3 == EconomicObservation.country_iso3,
            )
            .where(
                EconomicObservation.indicator_code == indicator_code,
                EconomicObservation.year == selected_year,
                CountryProfile.latitude.is_not(None),
                CountryProfile.longitude.is_not(None),
            )
            .order_by(CountryProfile.name)
        ).all()
        for observation, country in rows:
            if country.latitude is None or country.longitude is None:
                continue
            points.append(
                EconomicCountryPoint(
                    iso2=country.iso2,
                    iso3=country.iso3,
                    country_name=country.name,
                    region=country.region,
                    capital_city=country.capital_city,
                    latitude=float(country.latitude),
                    longitude=float(country.longitude),
                    year=observation.year,
                    value=observation.value,
                )
            )

    return EconomicMapResponse(
        generated_at=datetime.now(UTC),
        indicator=EconomicIndicatorView.model_validate(indicator),
        selected_year=selected_year,
        available_years=available_years,
        country_count=len(points),
        points=points,
    )


def build_country_detail(
    session: Session,
    *,
    iso2: str,
) -> EconomicCountryDetailResponse:
    """Return country metadata plus each indicator's newest available value."""
    country = session.scalar(
        select(CountryProfile).where(
            func.upper(CountryProfile.iso2) == iso2.upper()
        )
    )
    if country is None:
        raise EconomicCountryNotFoundError(iso2.upper())

    latest_year = (
        select(
            EconomicObservation.indicator_code.label("indicator_code"),
            func.max(EconomicObservation.year).label("year"),
        )
        .where(EconomicObservation.country_iso3 == country.iso3)
        .group_by(EconomicObservation.indicator_code)
        .subquery()
    )
    rows = session.execute(
        select(EconomicObservation, EconomicIndicator)
        .join(
            latest_year,
            (latest_year.c.indicator_code == EconomicObservation.indicator_code)
            & (latest_year.c.year == EconomicObservation.year),
        )
        .join(
            EconomicIndicator,
            EconomicIndicator.code == EconomicObservation.indicator_code,
        )
        .where(
            EconomicObservation.country_iso3 == country.iso3,
            EconomicIndicator.enabled.is_(True),
        )
        .order_by(EconomicIndicator.name_en)
    ).all()
    return EconomicCountryDetailResponse(
        iso2=country.iso2,
        iso3=country.iso3,
        country_name=country.name,
        region=country.region,
        income_level=country.income_level,
        capital_city=country.capital_city,
        latitude=(
            float(country.latitude)
            if country.latitude is not None
            else None
        ),
        longitude=(
            float(country.longitude)
            if country.longitude is not None
            else None
        ),
        metrics=[
            EconomicCountryMetric(
                indicator=EconomicIndicatorView.model_validate(indicator),
                year=observation.year,
                value=observation.value,
            )
            for observation, indicator in rows
        ],
    )


def get_sync_status(session: Session) -> EconomicSyncStatusView | None:
    """Return the latest World Bank collector state when available."""
    row = session.get(EconomicSyncState, "world_bank_indicators")
    if row is None:
        return None
    return EconomicSyncStatusView(
        source_key=row.source_key,
        last_started_at=row.last_started_at,
        last_success_at=row.last_success_at,
        history_start_year=row.history_start_year,
        history_end_year=row.history_end_year,
        rows_upserted=row.rows_upserted,
        consecutive_failures=row.consecutive_failures,
        last_error=row.last_error,
    )


def build_economic_rankings(
    session: Session,
    *,
    year: int | None = None,
    weight_overrides: dict[str, float] | None = None,
    country_iso2: str | None = None,
    top_limit: int = 20,
) -> EconomicRankingResponse:
    """Rank countries using transparent percentile components and weights."""
    indicators = {
        row.code: row
        for row in session.scalars(
            select(EconomicIndicator).where(
                EconomicIndicator.code.in_(RANKING_COMPONENTS),
                EconomicIndicator.enabled.is_(True),
            )
        )
    }
    weights = {
        code: (
            max(0, float((weight_overrides or {}).get(code, default_weight))),
            direction,
            target,
        )
        for code, (default_weight, direction, target) in RANKING_COMPONENTS.items()
        if code in indicators
    }
    if not weights or sum(row[0] for row in weights.values()) <= 0:
        raise ValueError("at least one ranking weight must be positive")
    if year is None:
        coverage = [
            (int(row[0]), int(row[1]))
            for row in session.execute(
                select(
                    EconomicObservation.year,
                    func.count(func.distinct(EconomicObservation.country_iso3)),
                )
                .where(EconomicObservation.indicator_code.in_(weights))
                .group_by(EconomicObservation.year)
                .order_by(EconomicObservation.year.desc())
            ).all()
        ]
        year = _newest_well_covered_year(coverage) or datetime.now(UTC).year

    rows = session.execute(
        select(EconomicObservation, CountryProfile)
        .join(
            CountryProfile,
            CountryProfile.iso3 == EconomicObservation.country_iso3,
        )
        .where(
            EconomicObservation.indicator_code.in_(weights),
            EconomicObservation.year == year,
        )
    ).all()
    by_country: dict[str, dict[str, float]] = {}
    profiles: dict[str, CountryProfile] = {}
    by_indicator: dict[str, list[tuple[str, float]]] = {
        code: [] for code in weights
    }
    for observation, country in rows:
        by_country.setdefault(country.iso3, {})[
            observation.indicator_code
        ] = float(observation.value)
        profiles[country.iso3] = country
        by_indicator[observation.indicator_code].append(
            (country.iso3, float(observation.value))
        )

    component_scores: dict[tuple[str, str], tuple[int, int, float]] = {}
    for code, indicator_values in by_indicator.items():
        _, direction, target = weights[code]
        ordered = sorted(
            indicator_values,
            key=lambda item: _ranking_quality(
                item[1],
                direction=direction,
                target=target,
            ),
            reverse=True,
        )
        total = len(ordered)
        for index, (iso3, _) in enumerate(ordered, start=1):
            normalized = (
                1
                if total <= 1
                else 1 - ((index - 1) / (total - 1))
            )
            component_scores[(iso3, code)] = (index, total, normalized)

    total_weight = sum(row[0] for row in weights.values())
    unranked: list[tuple[str, float, float, list[EconomicMetricRank]]] = []
    for iso3, country_values in by_country.items():
        available_weight = sum(
            weights[code][0]
            for code in country_values
            if (iso3, code) in component_scores
        )
        if available_weight <= 0 or len(country_values) < 3:
            continue
        coverage_ratio = available_weight / total_weight
        weighted_score = sum(
            component_scores[(iso3, code)][2] * weights[code][0]
            for code in country_values
            if (iso3, code) in component_scores
        ) / available_weight
        composite = weighted_score * (0.7 + 0.3 * coverage_ratio)
        metric_ranks = [
            EconomicMetricRank(
                indicator_code=code,
                value=value,
                year=year,
                rank=component_scores[(iso3, code)][0],
                ranked_country_count=component_scores[(iso3, code)][1],
                normalized_score=component_scores[(iso3, code)][2],
            )
            for code, value in country_values.items()
            if (iso3, code) in component_scores
        ]
        unranked.append((iso3, composite, coverage_ratio, metric_ranks))
    unranked.sort(key=lambda item: item[1], reverse=True)
    ranked_count = len(unranked)
    ranked = [
        EconomicCountryRanking(
            iso2=profiles[iso3].iso2,
            iso3=iso3,
            country_name=profiles[iso3].name,
            rank=index,
            ranked_country_count=ranked_count,
            composite_score=round(composite * 100, 2),
            data_coverage=coverage_ratio,
            metric_ranks=sorted(
                metric_ranks,
                key=lambda item: item.indicator_code,
            ),
        )
        for index, (iso3, composite, coverage_ratio, metric_ranks)
        in enumerate(unranked, start=1)
    ]
    selected = (
        next(
            (
                row
                for row in ranked
                if row.iso2.upper() == country_iso2.upper()
            ),
            None,
        )
        if country_iso2
        else None
    )
    visible = ranked[:top_limit]
    if selected is not None and all(row.iso2 != selected.iso2 for row in visible):
        visible.append(selected)
    return EconomicRankingResponse(
        generated_at=datetime.now(UTC),
        year=year,
        methodology=(
            "Weighted within-year percentile ranks; lower-is-better and "
            "2% inflation-target components are reversed before weighting. "
            "Incomplete coverage receives a visible score penalty."
        ),
        weights=[
            EconomicRankingWeight(
                indicator_code=code,
                name_en=indicators[code].name_en,
                name_zh=indicators[code].name_zh,
                weight=weight,
                direction=direction,
            )
            for code, (weight, direction, _) in weights.items()
        ],
        countries=visible,
    )


def _ranking_quality(
    value: float,
    *,
    direction: str,
    target: float | None,
) -> float:
    if direction == "lower":
        return -value
    if direction == "target" and target is not None:
        return -abs(value - target)
    return value


def _newest_well_covered_year(
    coverage_rows: list[tuple[int, int]],
) -> int | None:
    if not coverage_rows:
        return None
    maximum_coverage = max(count for _, count in coverage_rows)
    minimum_coverage = max(1, int(maximum_coverage * 0.6))
    return next(
        year
        for year, count in coverage_rows
        if count >= minimum_coverage
    )
