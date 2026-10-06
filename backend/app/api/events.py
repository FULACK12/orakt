"""GeoJSON event map endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.models import Event
from app.db.session import get_db_session
from app.schemas.events import (
    EventFeature,
    EventFeatureCollection,
    EventProperties,
    EventQuery,
    GeoJSONPoint,
)

router = APIRouter(tags=["events"])


def _apply_filters(statement: Select[tuple[Event]], filters: EventQuery) -> Select[tuple[Event]]:
    """Apply validated map filters to an event query."""
    if filters.start is not None:
        statement = statement.where(Event.start_at >= filters.start)
    if filters.end is not None:
        statement = statement.where(Event.start_at <= filters.end)
    if filters.country is not None:
        statement = statement.where(Event.country_code == filters.country)
    if filters.event_type is not None:
        statement = statement.where(Event.event_type == filters.event_type)
    return statement


def _to_feature(event: Event) -> EventFeature:
    """Convert a geolocated database event to a strict GeoJSON feature."""
    if event.longitude is None or event.latitude is None:
        raise ValueError("event must be geolocated")

    return EventFeature(
        id=event.id,
        geometry=GeoJSONPoint(
            coordinates=(float(event.longitude), float(event.latitude)),
        ),
        properties=EventProperties(
            event_type=event.event_type,
            title=event.title,
            summary=event.summary,
            status=event.status,
            severity=float(event.severity),
            novelty=float(event.novelty),
            confidence=float(event.confidence),
            start_at=event.start_at,
            end_at=event.end_at,
            country_code=event.country_code,
        ),
    )


@router.get(
    "/events",
    response_model=EventFeatureCollection,
    summary="List geolocated events as GeoJSON",
)
def list_events(
    filters: Annotated[EventQuery, Query()],
    session: Annotated[Session, Depends(get_db_session)],
) -> EventFeatureCollection:
    """Return matching geolocated events, newest first."""
    statement = select(Event).where(
        Event.latitude.is_not(None),
        Event.longitude.is_not(None),
    )
    statement = _apply_filters(statement, filters)
    statement = statement.order_by(Event.start_at.desc(), Event.id.desc()).limit(filters.limit)
    events = session.scalars(statement).all()
    return EventFeatureCollection(features=[_to_feature(event) for event in events])
