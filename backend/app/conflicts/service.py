"""Bounded spatial queries for the conflict indicator."""

from __future__ import annotations

import math
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ConflictAggregateObservation
from app.schemas.conflicts import ConflictIndicatorPoint, ConflictIndicatorResponse


def get_conflict_indicator(
    session: Session,
    *,
    weeks: int,
    west: float,
    south: float,
    east: float,
    north: float,
    zoom: float,
    limit: int,
    as_of: date | None = None,
) -> ConflictIndicatorResponse:
    """Aggregate current conflict intensity by Admin1 and visible map bounds."""
    latest_week = session.scalar(select(func.max(ConflictAggregateObservation.week)))
    if latest_week is None:
        return ConflictIndicatorResponse(
            weeks=weeks,
            latest_week=None,
            point_count=0,
            truncated=False,
            points=[],
        )
    # A UI range named "last week" must be relative to now, not relative to
    # the newest retained row. Otherwise a stale import is silently presented
    # as current conflict activity.
    period_start = (as_of or date.today()) - timedelta(days=weeks * 7 - 1)
    conditions = [
        ConflictAggregateObservation.week >= period_start,
        ConflictAggregateObservation.week <= latest_week,
        ConflictAggregateObservation.latitude >= south,
        ConflictAggregateObservation.latitude <= north,
    ]
    if west <= east:
        conditions.extend(
            [
                ConflictAggregateObservation.longitude >= west,
                ConflictAggregateObservation.longitude <= east,
            ]
        )
    else:
        conditions.append(
            (ConflictAggregateObservation.longitude >= west)
            | (ConflictAggregateObservation.longitude <= east)
        )
    event_count = func.sum(ConflictAggregateObservation.events).label("event_count")
    fatality_count = func.sum(ConflictAggregateObservation.fatalities).label(
        "fatality_count"
    )
    population_exposure = func.sum(
        ConflictAggregateObservation.population_exposure
    ).label("population_exposure")
    query_limit = min(limit, 350 if zoom < 4 else 700 if zoom < 7 else 1_200)
    rows = session.execute(
        select(
            ConflictAggregateObservation.country,
            ConflictAggregateObservation.admin1,
            func.avg(ConflictAggregateObservation.latitude).label("latitude"),
            func.avg(ConflictAggregateObservation.longitude).label("longitude"),
            event_count,
            fatality_count,
            population_exposure,
        )
        .where(*conditions)
        .group_by(
            ConflictAggregateObservation.country,
            ConflictAggregateObservation.admin1,
        )
        .order_by(fatality_count.desc(), event_count.desc())
        .limit(query_limit + 1)
    ).all()
    truncated = len(rows) > query_limit
    points = [
        _indicator_point(
            row,
            period_start=period_start,
            period_end=latest_week,
        )
        for row in rows[:query_limit]
    ]
    return ConflictIndicatorResponse(
        weeks=weeks,
        latest_week=latest_week,
        point_count=len(points),
        truncated=truncated,
        points=points,
    )


def current_conflict_hotspots(
    session: Session,
    *,
    weeks: int = 12,
    limit: int = 30,
) -> list[dict[str, object]]:
    """Return compact globally ranked conflict context for local research."""
    payload = get_conflict_indicator(
        session,
        weeks=weeks,
        west=-180,
        south=-90,
        east=180,
        north=90,
        zoom=2,
        limit=limit,
    )
    return [
        {
            "evidence_id": f"acled:{point.country}:{point.admin1}",
            "category": "conflict",
            "country": point.country,
            "admin1": point.admin1,
            "events": point.events,
            "fatalities": point.fatalities,
            "urgency_score": point.urgency_score,
            "period_start": point.period_start.isoformat(),
            "period_end": point.period_end.isoformat(),
            "latitude": point.latitude,
            "longitude": point.longitude,
            "source": "ACLED",
            "source_url": "https://acleddata.com/",
        }
        for point in payload.points
    ]


def _indicator_point(
    row: object,
    *,
    period_start: date,
    period_end: date,
) -> ConflictIndicatorPoint:
    events = int(row.event_count or 0)  # type: ignore[attr-defined]
    fatalities = int(row.fatality_count or 0)  # type: ignore[attr-defined]
    exposure = (
        float(row.population_exposure)  # type: ignore[attr-defined]
        if row.population_exposure is not None  # type: ignore[attr-defined]
        else None
    )
    urgency = min(
        1,
        0.12
        + min(1, math.log1p(events) / math.log(101)) * 0.38
        + min(1, math.log1p(fatalities) / math.log(251)) * 0.5,
    )
    role = (
        "primary_theater"
        if urgency >= 0.68 or fatalities >= 25
        else "secondary_theater"
        if urgency >= 0.4 or fatalities >= 5
        else "reported_site"
    )
    return ConflictIndicatorPoint(
        country=row.country,  # type: ignore[attr-defined]
        admin1=row.admin1,  # type: ignore[attr-defined]
        latitude=float(row.latitude),  # type: ignore[attr-defined]
        longitude=float(row.longitude),  # type: ignore[attr-defined]
        events=events,
        fatalities=fatalities,
        population_exposure=exposure,
        urgency_score=round(urgency, 4),
        role=role,
        event_types=[
            "Battles / Explosions / Violence against civilians",
        ],
        period_start=period_start,
        period_end=period_end,
    )
