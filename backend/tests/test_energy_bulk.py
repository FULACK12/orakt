"""EIA bulk download, archive, materialization and model tests."""

import io
import json
from collections.abc import Generator
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import EnergyObservation, EnergySeries, EnergySyncState
from app.energy.bulk import sync_eia_bulk
from app.energy.service import get_energy_series_detail
from app.storage.archive import ColdArchive


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    engine.dispose()


def test_eia_bulk_archive_catalog_and_model(
    session: Session,
    tmp_path: Path,
) -> None:
    archive_payload = _energy_zip()
    manifest = {
        "dataset": {
            "TOTAL": {
                "accessURL": "https://www.eia.gov/opendata/bulk/TOTAL.zip",
                "last_updated": "2026-07-23T13:02:48-04:00",
            }
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("manifest.txt"):
            return httpx.Response(200, json=manifest)
        if str(request.url).endswith("TOTAL.zip"):
            return httpx.Response(
                200,
                content=archive_payload,
                headers={"content-length": str(len(archive_payload))},
            )
        return httpx.Response(404)

    archive = ColdArchive(
        tmp_path,
        min_free_bytes=0,
        max_used_percent=99,
        disk_usage_provider=lambda _: (100_000_000, 0, 100_000_000),
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = sync_eia_bulk(
            session,
            client,
            archive=archive,
            dataset_keys=["TOTAL"],
            max_series_per_dataset=1,
            max_observations_per_series=100,
        )

    assert result.datasets[0].downloaded is True
    assert result.datasets[0].series_cataloged == 2
    assert result.datasets[0].series_materialized == 1
    assert session.scalar(select(func.count(EnergySeries.series_id))) == 2
    assert session.scalar(select(func.count(EnergyObservation.period))) == 14
    state = session.get(EnergySyncState, "TOTAL")
    assert state is not None
    assert state.archive_sha256 is not None
    detail = get_energy_series_detail(
        session,
        series_id="TOTAL.CRUDE_PRODUCTION.M",
        limit=100,
    )
    assert detail is not None
    assert detail.model.latest_value == 113
    assert detail.model.period_change_percent is not None
    assert detail.model.trend == "rising"


def _energy_zip() -> bytes:
    focused = {
        "series_id": "TOTAL.CRUDE_PRODUCTION.M",
        "name": "United States Total Crude Oil Production, Monthly",
        "units": "Thousand Barrels per Day",
        "f": "M",
        "start": "202501",
        "end": "202602",
        "last_updated": "2026-07-23T13:02:48-04:00",
        "data": [
            [f"2025{month:02d}", 99 + month]
            for month in range(1, 13)
        ]
        + [["202601", 112], ["202602", 113]],
    }
    unfocused = {
        "series_id": "TOTAL.UNRELATED.A",
        "name": "Administrative code",
        "units": "Count",
        "f": "A",
        "start": "2024",
        "end": "2025",
        "data": [["2024", 1], ["2025", 2]],
    }
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "TOTAL.txt",
            "\n".join(json.dumps(row) for row in (focused, unfocused)),
        )
    return output.getvalue()
