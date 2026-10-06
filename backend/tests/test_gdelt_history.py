"""Historical GDELT event parsing, aggregation and checkpoint tests."""

import io
from datetime import date
from zipfile import ZipFile

import httpx
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import GdeltArchiveState, GdeltEventAggregate
from app.gdelt_history import (
    _flush_buckets,
    _parse_event_row,
    sync_gdelt_daily_batch,
)


def test_gdelt_event_row_is_materialized_as_monthly_cameo_bucket() -> None:
    row = [""] * 58
    row[1] = "19790115"
    row[2] = "197901"
    row[7] = "USA"
    row[28] = "14"
    row[29] = "4"
    row[30] = "-5.0"
    row[31] = "12"
    row[32] = "4"
    row[33] = "7"
    row[34] = "-2.5"
    row[51] = "CAN"

    parsed = _parse_event_row(row)

    assert parsed is not None
    assert parsed[:4] == (date(1979, 1, 1), "CAN", "14", 4)

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        buckets = {parsed[:4]: list(parsed[4:])}
        assert _flush_buckets(session, buckets) == 1
        session.commit()
        aggregate = session.scalar(select(GdeltEventAggregate))
        count = session.scalar(
            select(func.count()).select_from(GdeltEventAggregate)
        )
    assert count == 1
    assert aggregate is not None
    assert aggregate.total_mentions == 12
    assert aggregate.total_articles == 7
    engine.dispose()


def test_master_reduced_row_uses_event_and_article_counts() -> None:
    parsed = _parse_event_row(
        [
            "19790101",
            "AFR",
            "FRAGOV",
            "043",
            "2",
            "19",
            "1",
            "2.8",
            "1",
            "46",
            "2",
            "1",
            "46",
            "2",
            "1",
            "46",
            "2",
        ]
    )

    assert parsed is not None
    assert parsed[:4] == (date(1979, 1, 1), "FRA", "04", 1)
    assert parsed[4] == 2
    assert parsed[7] == 19
    assert parsed[8] == 5.6


def test_daily_archive_backfill_is_checkpointed_and_idempotent(tmp_path) -> None:
    row = [""] * 58
    row[1] = "20140101"
    row[2] = "201401"
    row[7] = "USA"
    row[28] = "04"
    row[29] = "1"
    row[30] = "3.0"
    row[31] = "2"
    row[32] = "1"
    row[33] = "1"
    row[34] = "0.5"
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("20140101.export.CSV", "\t".join(row))
    payload = buffer.getvalue()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/20140101.export.CSV.zip")
        return httpx.Response(200, content=payload)

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session, httpx.Client(
        transport=httpx.MockTransport(handler)
    ) as client:
        first = sync_gdelt_daily_batch(
            session,
            client=client,
            cold_root=tmp_path,
            min_free_bytes=0,
            batch_days=1,
            end_date=date(2014, 1, 1),
            request_interval_seconds=0,
        )
        second = sync_gdelt_daily_batch(
            session,
            client=client,
            cold_root=tmp_path,
            min_free_bytes=0,
            batch_days=1,
            end_date=date(2014, 1, 1),
            request_interval_seconds=0,
        )
        aggregate = session.scalar(select(GdeltEventAggregate))
        state = session.get(GdeltArchiveState, "gdelt_events_daily_20140101")

    assert len(first) == 1
    assert second == []
    assert state is not None
    assert state.status == "completed"
    assert aggregate is not None
    assert aggregate.event_count == 1
    engine.dispose()


def test_daily_archive_records_404_gap_and_continues(tmp_path) -> None:
    row = [""] * 58
    row[1] = "20140124"
    row[2] = "201401"
    row[7] = "USA"
    row[28] = "04"
    row[29] = "1"
    row[30] = "3.0"
    row[31] = "2"
    row[32] = "1"
    row[33] = "1"
    row[34] = "0.5"
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("20140124.export.CSV", "\t".join(row))
    payload = buffer.getvalue()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/20140123.export.CSV.zip"):
            return httpx.Response(404, request=request)
        assert request.url.path.endswith("/20140124.export.CSV.zip")
        return httpx.Response(200, content=payload, request=request)

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session, httpx.Client(
        transport=httpx.MockTransport(handler)
    ) as client:
        session.add(
            GdeltArchiveState(
                archive_key="gdelt_events_daily_20140122",
                source_url="https://example.test/20140122.zip",
                status="completed",
                starts_at=date(2014, 1, 22),
                ends_at=date(2014, 1, 22),
                rows_seen=1,
                aggregates_upserted=1,
                archive_bytes=1,
            )
        )
        session.commit()
        states = sync_gdelt_daily_batch(
            session,
            client=client,
            cold_root=tmp_path,
            min_free_bytes=0,
            batch_days=2,
            end_date=date(2014, 1, 24),
            request_interval_seconds=0,
        )
        missing = session.get(
            GdeltArchiveState,
            "gdelt_events_daily_20140123",
        )
        imported = session.get(
            GdeltArchiveState,
            "gdelt_events_daily_20140124",
        )

    assert [state.status for state in states] == ["unavailable", "completed"]
    assert missing is not None
    assert missing.status == "unavailable"
    assert missing.last_error is not None
    assert imported is not None
    assert imported.status == "completed"
    engine.dispose()
