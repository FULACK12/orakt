"""Queries and transparent deterministic models for EIA energy series."""

from __future__ import annotations

import math
import statistics

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import EnergyObservation, EnergySeries, EnergySyncState
from app.schemas.energy import (
    EnergyDatasetStatus,
    EnergyObservationView,
    EnergySeriesDetail,
    EnergySeriesModel,
    EnergySeriesSummary,
)


def list_dataset_status(session: Session) -> list[EnergyDatasetStatus]:
    """Return persisted EIA archive/import status without secrets."""
    rows = session.scalars(
        select(EnergySyncState).order_by(EnergySyncState.dataset_key)
    )
    return [
        EnergyDatasetStatus(
            dataset_key=row.dataset_key,
            source_url=row.source_url,
            source_last_updated=row.source_last_updated,
            archive_path=row.archive_path,
            archive_bytes=row.archive_bytes,
            series_cataloged=row.series_cataloged,
            series_materialized=row.series_materialized,
            observations_upserted=row.observations_upserted,
            last_success_at=row.last_success_at,
            last_error=row.last_error,
        )
        for row in rows
    ]


def search_energy_series(
    session: Session,
    *,
    dataset: str | None,
    query: str | None,
    materialized: bool | None,
    limit: int,
) -> list[EnergySeriesSummary]:
    """Search the local EIA catalog by dataset, ID or title."""
    statement = select(EnergySeries)
    if dataset:
        statement = statement.where(
            EnergySeries.dataset_key == dataset.strip().upper()
        )
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(
            or_(
                EnergySeries.series_id.ilike(pattern),
                EnergySeries.name.ilike(pattern),
            )
        )
    if materialized is not None:
        statement = statement.where(EnergySeries.materialized == materialized)
    rows = session.scalars(
        statement.order_by(
            EnergySeries.materialized.desc(),
            EnergySeries.dataset_key,
            EnergySeries.series_id,
        ).limit(limit)
    )
    return [_summary(row) for row in rows]


def get_energy_series_detail(
    session: Session,
    *,
    series_id: str,
    limit: int,
) -> EnergySeriesDetail | None:
    """Return recent observations and a reproducible trend/anomaly model."""
    series = session.get(EnergySeries, series_id)
    if series is None:
        return None
    rows = list(
        session.scalars(
            select(EnergyObservation)
            .where(EnergyObservation.series_id == series_id)
            .order_by(EnergyObservation.period.desc())
            .limit(limit)
        )
    )
    rows.reverse()
    observations = [
        EnergyObservationView(period=row.period, value=row.value)
        for row in rows
    ]
    return EnergySeriesDetail(
        series=_summary(series),
        observations=observations,
        model=_model(observations, frequency=series.frequency),
    )


def _summary(row: EnergySeries) -> EnergySeriesSummary:
    return EnergySeriesSummary(
        series_id=row.series_id,
        dataset_key=row.dataset_key,
        name=row.name,
        units=row.units,
        frequency=row.frequency,
        start_period=row.start_period,
        end_period=row.end_period,
        observation_count=row.observation_count,
        materialized=row.materialized,
        source_url=row.source_url,
    )


def _model(
    observations: list[EnergyObservationView],
    *,
    frequency: str | None,
) -> EnergySeriesModel:
    if not observations:
        return EnergySeriesModel(
            latest_period=None,
            latest_value=None,
            previous_value=None,
            period_change_percent=None,
            year_change_percent=None,
            rolling_mean=None,
            rolling_z_score=None,
            anomaly_score=0,
            trend="insufficient_data",
            method="No materialized observations are available.",
        )
    values = [row.value for row in observations]
    latest = values[-1]
    previous = values[-2] if len(values) >= 2 else None
    period_change = _percent_change(latest, previous)
    lag = {
        "daily": 365,
        "weekly": 52,
        "monthly": 12,
        "quarterly": 4,
        "annual": 1,
    }.get(frequency or "", 12)
    year_change = (
        _percent_change(latest, values[-lag - 1])
        if len(values) > lag
        else None
    )
    rolling = values[-min(60, len(values)) :]
    mean = statistics.fmean(rolling)
    deviation = statistics.pstdev(rolling) if len(rolling) >= 2 else 0
    z_score = (latest - mean) / deviation if deviation > 0 else 0.0
    anomaly = min(1.0, abs(z_score) / 4)
    if period_change is None or abs(period_change) < 0.25:
        trend = "stable"
    elif period_change > 0:
        trend = "rising"
    else:
        trend = "falling"
    return EnergySeriesModel(
        latest_period=observations[-1].period,
        latest_value=latest,
        previous_value=previous,
        period_change_percent=period_change,
        year_change_percent=year_change,
        rolling_mean=mean,
        rolling_z_score=z_score if math.isfinite(z_score) else None,
        anomaly_score=anomaly,
        trend=trend,
        method=(
            "Deterministic local model: latest period change, frequency-aware "
            "year-over-year change, and absolute z-score against up to 60 "
            "materialized observations. No causal claim is made."
        ),
    )


def _percent_change(current: float, previous: float | None) -> float | None:
    if previous is None or previous == 0:
        return None
    return ((current - previous) / abs(previous)) * 100
