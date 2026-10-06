"""Event-extraction schema, mock and API tests."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient, Response
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.extractions import get_event_extractor
from app.db.base import Base
from app.db.enums import SourceType
from app.db.models import Document, Source
from app.db.session import get_db_session
from app.extractors.mock import MockEventExtractor
from app.main import app
from app.schemas.extractions import (
    DocumentExtractionInput,
    EvidenceSpan,
    ExtractedLocation,
)

ExtractionAPI = tuple[int, Callable[[str], Response]]


@pytest.fixture
def extraction_api(tmp_path: Path) -> Generator[ExtractionAPI, None, None]:
    """Provide a stored document behind the real extraction route."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source = Source(
            name="USGS test source",
            country="US",
            language="en",
            source_type=SourceType.OFFICIAL,
        )
        document = Document(
            source=source,
            url="https://example.test/earthquake",
            title="M 4.3 - 8 km ESE of Cloverdale, CA",
            body=(
                "Time 2026-07-29 02:40:06 UTC at epicenter "
                "Location 38.777°N 122.936°W Depth 5.92 km"
            ),
            language="en",
            published_at=datetime(2026, 7, 29, 2, 40, 6, tzinfo=UTC),
            content_hash="e" * 64,
            raw_object_path=str(tmp_path / "unused.json.gz"),
        )
        session.add(document)
        session.commit()
        document_id = document.id

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    def post(path: str) -> Response:
        async def send() -> Response:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.post(path)

        return asyncio.run(send())

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_event_extractor] = MockEventExtractor
    try:
        yield document_id, post
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_event_extractor, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def earthquake_input() -> DocumentExtractionInput:
    return DocumentExtractionInput(
        document_id=31,
        title="M 5.4 - 11 km N of Tsunagi, Japan",
        body=(
            "PAGER - GREEN Time 2026-07-29 13:19:36 UTC at epicenter "
            "Location 32.340°N 130.488°E Depth 10.00 km"
        ),
        published_at=datetime(2026, 7, 29, 13, 19, 36, tzinfo=UTC),
        language="en",
        source_country="US",
    )


def test_mock_extracts_structured_earthquake_with_verbatim_evidence() -> None:
    document = earthquake_input()

    result = MockEventExtractor().extract(document)

    assert result.schema_version == "1.0"
    assert result.extractor == "mock-v1"
    assert len(result.events) == 1
    event = result.events[0]
    assert event.event_type == "earthquake"
    assert event.severity == pytest.approx(0.54)
    assert event.confidence == 0.98
    assert event.occurred_at == datetime(2026, 7, 29, 13, 19, 36, tzinfo=UTC)
    assert event.location is not None
    assert event.location.country_code == "JP"
    assert event.location.latitude == pytest.approx(32.340)
    assert event.location.longitude == pytest.approx(130.488)
    for span in event.evidence_spans:
        source = document.title if span.source_field == "title" else document.body
        assert source[span.start_char : span.end_char] == span.quote


def test_mock_classifies_generic_official_announcement() -> None:
    document = DocumentExtractionInput(
        document_id=1,
        title="Government announces new climate cooperation",
        body="Ministers committed to international climate action.",
        published_at=datetime(2026, 7, 29, tzinfo=UTC),
        source_country="GB",
    )

    event = MockEventExtractor().extract(document).events[0]

    assert event.event_type == "climate_policy"
    assert event.location is None
    assert event.confidence == 0.55
    assert event.evidence_spans[0].quote == document.title


def test_extraction_schemas_reject_unpaired_coordinates_and_invalid_span() -> None:
    with pytest.raises(ValidationError):
        ExtractedLocation(
            name="Incomplete point",
            latitude=10,
            confidence=0.5,
        )
    with pytest.raises(ValidationError):
        EvidenceSpan(
            field="location",
            source_field="body",
            start_char=5,
            end_char=5,
            quote="x",
        )


def test_extraction_api_returns_validated_mock_output(
    extraction_api: ExtractionAPI,
) -> None:
    document_id, post = extraction_api

    response = post(f"/documents/{document_id}/extract")

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == document_id
    assert payload["extractor"] == "mock-v1"
    assert payload["events"][0]["event_type"] == "earthquake"
    assert payload["events"][0]["location"]["latitude"] == 38.777
    assert payload["events"][0]["location"]["longitude"] == -122.936


def test_extraction_api_returns_404_for_unknown_document(
    extraction_api: ExtractionAPI,
) -> None:
    _, post = extraction_api

    response = post("/documents/999999/extract")

    assert response.status_code == 404
    assert response.json()["detail"] == "document not found"
