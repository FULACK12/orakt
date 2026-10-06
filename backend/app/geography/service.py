"""Read services for zoom-aware administrative geography."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AdministrativeArea, RegionalIndicator, RegionalObservation
from app.schemas.geography import (
    AdministrativeAreaDetailResponse,
    AdministrativeAreaListResponse,
    AdministrativeAreaView,
    AdministrativeLevel,
    RegionalMetricView,
)


class AdministrativeAreaNotFoundError(LookupError):
    """Raised when a requested region does not exist."""


def list_areas(
    session: Session,
    *,
    country_iso2: str,
    level: AdministrativeLevel,
    parent_id: int | None,
    minimum_population: int,
    limit: int,
) -> AdministrativeAreaListResponse:
    """Return coordinate-bearing areas ordered by map relevance."""
    statement = select(AdministrativeArea).where(
        AdministrativeArea.country_iso2 == country_iso2.upper(),
        AdministrativeArea.level == level,
        AdministrativeArea.latitude.is_not(None),
        AdministrativeArea.longitude.is_not(None),
    )
    if parent_id is not None:
        statement = statement.where(AdministrativeArea.parent_id == parent_id)
    if minimum_population > 0:
        statement = statement.where(
            AdministrativeArea.population >= minimum_population
        )
    rows = list(
        session.scalars(
            statement.order_by(
                AdministrativeArea.population.desc().nullslast(),
                AdministrativeArea.name,
            ).limit(limit)
        )
    )
    return AdministrativeAreaListResponse(
        generated_at=datetime.now(UTC),
        country_iso2=country_iso2.upper(),
        level=level,
        count=len(rows),
        areas=[_area_view(row) for row in rows],
    )


def get_area_detail(
    session: Session,
    *,
    area_id: int,
) -> AdministrativeAreaDetailResponse:
    """Return a region and its latest observation for every known metric."""
    area = session.get(AdministrativeArea, area_id)
    if area is None:
        raise AdministrativeAreaNotFoundError(str(area_id))

    latest_period = (
        select(
            RegionalObservation.indicator_code.label("indicator_code"),
            func.max(RegionalObservation.period).label("period"),
        )
        .where(RegionalObservation.area_id == area_id)
        .group_by(RegionalObservation.indicator_code)
        .subquery()
    )
    rows = session.execute(
        select(RegionalObservation, RegionalIndicator)
        .join(
            latest_period,
            (latest_period.c.indicator_code == RegionalObservation.indicator_code)
            & (latest_period.c.period == RegionalObservation.period),
        )
        .join(
            RegionalIndicator,
            RegionalIndicator.code == RegionalObservation.indicator_code,
        )
        .where(RegionalObservation.area_id == area_id)
        .order_by(RegionalIndicator.code)
    ).all()
    child_count = session.scalar(
        select(func.count())
        .select_from(AdministrativeArea)
        .where(AdministrativeArea.parent_id == area_id)
    )
    return AdministrativeAreaDetailResponse(
        area=_area_view(area),
        metrics=[
            RegionalMetricView(
                indicator_code=indicator.code,
                name_en=indicator.name_en,
                name_zh=indicator.name_zh,
                unit=indicator.unit,
                period=observation.period,
                value=observation.value,
                source_name=indicator.source_name,
                source_url=indicator.source_url,
                license_name=indicator.license_name,
                license_url=indicator.license_url,
            )
            for observation, indicator in rows
        ],
        child_count=int(child_count or 0),
    )


def _area_view(area: AdministrativeArea) -> AdministrativeAreaView:
    return AdministrativeAreaView(
        id=area.id,
        parent_id=area.parent_id,
        country_iso2=area.country_iso2,
        level=cast(AdministrativeLevel, area.level),
        code=area.code,
        name=area.name,
        ascii_name=area.ascii_name,
        latitude=float(area.latitude) if area.latitude is not None else None,
        longitude=float(area.longitude) if area.longitude is not None else None,
        coordinate_precision=area.coordinate_precision,
        population=area.population,
        source_name=area.source_name,
        source_url=area.source_url,
        license_name=area.license_name,
        license_url=area.license_url,
    )
