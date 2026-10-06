"""NASA FIRMS parsing, aggregation and canonical persistence tests."""

from collections.abc import Generator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.collectors.firms import FIRMSCollector, aggregate_detections, parse_firms_csv
from app.db.base import Base
from app.db.models import Document, Event
from app.storage.archive import ColdArchive

FIRMS_CSV = """\
latitude,longitude,acq_date,acq_time,satellite,instrument,confidence,frp,daynight
43.6500,-79.3800,2026-07-30,0312,N20,VIIRS,n,12.5,N
43.6600,-79.3900,2026-07-30,0320,N20,VIIRS,h,42.0,N
999,-79.3900,2026-07-30,0320,N20,VIIRS,h,42.0,N
"""


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    engine.dispose()


def test_parse_and_aggregate_firms_csv() -> None:
    detections, invalid = parse_firms_csv(FIRMS_CSV)

    assert len(detections) == 2
    assert invalid == 1
    clusters = aggregate_detections(
        detections,
        grid_degrees=0.25,
        limit=10,
    )
    assert len(clusters) == 1
    assert clusters[0]["detection_count"] == 2
    assert clusters[0]["max_frp"] == 42
    assert clusters[0]["confidence"] > 0.7


def test_collector_archives_and_upserts_map_event(
    session: Session,
    tmp_path: Path,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "test-map-key" in str(request.url)
        return httpx.Response(200, text=FIRMS_CSV)

    archive = ColdArchive(
        tmp_path,
        min_free_bytes=0,
        max_used_percent=99,
        disk_usage_provider=lambda _: (10_000_000, 0, 10_000_000),
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        collector = FIRMSCollector(
            client,
            map_key="test-map-key",
            source="VIIRS_NOAA20_NRT",
            grid_degrees=0.25,
            archive=archive,
        )
        first = collector.collect(session)
        second = collector.collect(session)

    assert first.events_created == 1
    assert second.events_created == 0
    assert second.events_updated == 1
    assert session.scalar(select(func.count(Event.id))) == 1
    assert session.scalar(select(func.count(Document.id))) == 1
    event = session.scalar(select(Event))
    assert event is not None
    assert event.event_type == "thermal_anomaly"
    assert first.raw_archive_path is not None
    assert (tmp_path / first.raw_archive_path).is_file()
