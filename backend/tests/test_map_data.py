"""Interactive map candidate/canonical layers and page tests."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.cluster_review import sign_cluster_preview
from app.core.config import get_settings
from app.db.base import Base
from app.db.enums import (
    ClusterJobStatus,
    DocumentStance,
    EventStatus,
    SourceType,
)
from app.db.models import (
    ClusterJob,
    CountryProfile,
    Document,
    Event,
    EventDocument,
    Source,
)
from app.db.session import get_db_session
from app.main import app
from app.map_service import (
    _aggregate_earthquake_series,
    _annotate_conflict_theaters,
    _build_conflict_situations,
    _infer_country_from_text,
)
from app.schemas.cluster_jobs import ClusterJobParameters, ClusterJobResult
from app.schemas.clusters import (
    ClusterCandidate,
    ClusterDocumentFingerprint,
    ClusterPreviewResponse,
    EventClusterPreview,
)
from app.schemas.extractions import (
    EvidenceSpan,
    ExtractedEvent,
    ExtractedLocation,
)
from app.schemas.map_data import MapEventMarker


def test_country_text_inference_requires_location_like_context() -> None:
    profiles = {
        "UA": CountryProfile(
            iso3="UKR",
            iso2="UA",
            name="Ukraine",
            region="Europe",
            latitude=50.45,
            longitude=30.52,
            source_url="https://example.test/ua",
        ),
        "IL": CountryProfile(
            iso3="ISR",
            iso2="IL",
            name="Israel",
            region="Middle East",
            latitude=31.77,
            longitude=35.22,
            source_url="https://example.test/il",
        ),
        "IR": CountryProfile(
            iso3="IRN",
            iso2="IR",
            name="Iran, Islamic Rep.",
            region="Middle East",
            latitude=35.69,
            longitude=51.42,
            source_url="https://example.test/ir",
        ),
    }

    assert _infer_country_from_text(
        "Security Council briefing on Ukraine as strikes hit cities",
        country_profiles=profiles,
    ) == "UA"
    assert _infer_country_from_text(
        "Talks between Israel and Iran continue",
        country_profiles=profiles,
    ) is None


def test_nearby_earthquakes_become_one_expandable_series() -> None:
    base = {
        "kind": "candidate",
        "cluster_job_id": 1,
        "cluster_id": 1,
        "event_type": "earthquake",
        "is_conflict": False,
        "geolocation_precision": "point",
        "country_code": "US",
        "published_at": None,
        "confidence": 0.9,
        "severity": 0.8,
        "status": None,
        "review_category": "independent",
        "source_name": "USGS",
    }
    markers = [
        MapEventMarker(
            **base,
            id="candidate:1:0",
            document_id=1,
            title="M 4.3 - 8 km ESE of Cloverdale, CA",
            summary=None,
            latitude=38.777,
            longitude=-122.936,
            occurred_at=datetime(2026, 7, 29, 2, 40, 6, tzinfo=UTC),
            source_url="https://example.test/1",
        ),
        MapEventMarker(
            **base,
            id="candidate:2:0",
            document_id=2,
            title="M 2.5 - 8 km ESE of Cloverdale, CA",
            summary=None,
            latitude=38.787,
            longitude=-122.923,
            occurred_at=datetime(2026, 7, 29, 2, 40, 44, tzinfo=UTC),
            source_url="https://example.test/2",
        ),
        MapEventMarker(
            **base,
            id="candidate:3:0",
            document_id=3,
            title="M 5.0 - 900 km away",
            summary=None,
            latitude=30,
            longitude=-110,
            occurred_at=datetime(2026, 7, 29, 3, tzinfo=UTC),
            source_url="https://example.test/3",
        ),
    ]

    aggregated = _aggregate_earthquake_series(markers)

    assert len(aggregated) == 2
    cloverdale = next(marker for marker in aggregated if marker.series_count == 2)
    assert cloverdale.title.startswith("M 4.3")
    assert [wave.magnitude for wave in cloverdale.series_events] == [4.3, 2.5]


def test_conflict_sites_are_ranked_by_report_density_not_country_center() -> None:
    base = {
        "kind": "candidate",
        "cluster_job_id": 1,
        "cluster_id": 1,
        "event_type": "airstrike",
        "is_conflict": True,
        "country_code": "UA",
        "published_at": None,
        "confidence": 0.7,
        "severity": 0.7,
        "status": None,
        "review_category": "review",
        "source_url": "https://example.test/conflict",
    }
    sites = [
        ("a", "Source A", 48.0, 37.8, 0, "city"),
        ("b", "Source B", 48.1, 37.9, 1, "city"),
        ("c", "Source C", 48.2, 38.0, 2, "admin1"),
        ("d", "Source D", 50.4, 30.5, 3, "city"),
        ("e", "Source E", 50.5, 30.6, 4, "city"),
        ("unknown", "Source F", 50.45, 30.52, 5, "country"),
    ]
    markers = [
        MapEventMarker(
            **base,
            id=f"candidate:{marker_id}",
            document_id=index,
            title=f"Reported strike {marker_id}",
            summary=None,
            latitude=latitude,
            longitude=longitude,
            geolocation_precision=precision,
            occurred_at=datetime(2026, 7, 20 + offset, tzinfo=UTC),
            source_name=source,
        )
        for index, (
            marker_id,
            source,
            latitude,
            longitude,
            offset,
            precision,
        ) in enumerate(sites, start=1)
    ]

    _annotate_conflict_theaters(markers)

    assert {marker.conflict_zone_role for marker in markers[:3]} == {
        "primary_theater"
    }
    assert {marker.conflict_zone_role for marker in markers[3:5]} == {
        "secondary_theater"
    }
    assert markers[-1].conflict_zone_role == "location_unconfirmed"
    assert markers[-1].theater_confidence == 0.2


def test_conflict_situations_are_local_and_actor_linked() -> None:
    base = {
        "kind": "canonical",
        "event_type": "armed_conflict",
        "is_conflict": True,
        "country_code": "UA",
        "geolocation_precision": "point",
        "published_at": None,
        "confidence": 0.75,
        "severity": 0.8,
        "status": EventStatus.CONFIRMED,
        "review_category": None,
        "source_url": "https://example.test/conflict",
        "actors": ["Actor A", "Actor B"],
    }
    coordinates = [
        (48.0, 37.8, 0),
        (48.1, 37.9, 1),
        (49.5, 34.8, 10),
        (49.6, 34.9, 11),
    ]
    markers = [
        MapEventMarker(
            **base,
            id=f"canonical:{index}",
            event_id=index,
            document_id=index,
            title=f"Conflict report {index}",
            summary=None,
            latitude=latitude,
            longitude=longitude,
            occurred_at=datetime(2026, 7, 1 + offset, tzinfo=UTC),
            source_name=f"Source {index}",
        )
        for index, (latitude, longitude, offset) in enumerate(
            coordinates,
            start=1,
        )
    ]

    zones, movements = _build_conflict_situations(markers)

    assert len(zones) == 2
    assert all(zone.radius_km < 220 for zone in zones)
    assert {zone.role for zone in zones} == {
        "primary_theater",
        "secondary_theater",
    }
    assert len(movements) == 1
    assert movements[0].actor == "Actor A"
    assert movements[0].inference_kind == "reported_activity_shift"
    assert movements[0].confidence <= 0.6


def test_large_conflict_zone_keeps_bounded_representative_marker_ids() -> None:
    base_time = datetime(2026, 7, 1, tzinfo=UTC)
    markers = [
        MapEventMarker(
            kind="canonical",
            id=f"canonical:{index}",
            event_id=index,
            document_id=index,
            event_type="armed_conflict",
            title=f"Conflict report {index}",
            summary=None,
            is_conflict=True,
            latitude=48 + (index % 5) * 0.001,
            longitude=37.8 + (index % 5) * 0.001,
            geolocation_precision="point",
            country_code="UA",
            occurred_at=base_time + timedelta(minutes=index),
            published_at=None,
            confidence=0.7,
            severity=0.5 + (index % 10) * 0.04,
            status=EventStatus.CONFIRMED,
            review_category=None,
            source_name=f"Source {index % 4}",
            source_url=f"https://example.test/conflict/{index}",
            actors=["Actor A"],
        )
        for index in range(1, 301)
    ]

    zones, _ = _build_conflict_situations(markers)

    assert len(zones) == 1
    assert zones[0].event_count == 300
    assert len(zones[0].marker_ids) == 250
    assert "canonical:299" in zones[0].marker_ids


@pytest.fixture
def map_api() -> Generator[None, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        earthquake_source = Source(
            name="U.S. Geological Survey Earthquakes",
            country="US",
            language="en",
            source_type=SourceType.OFFICIAL,
        )
        canonical_source = Source(
            name="Canonical source",
            country="CA",
            language="en",
            source_type=SourceType.OFFICIAL,
        )
        earthquake = Document(
            source=earthquake_source,
            url="https://example.test/earthquake",
            title="M 5.1 - south of Tonga",
            body=(
                "Time 2026-07-29 20:52:10 UTC at epicenter "
                "Location 24.628°S 175.272°W Depth 10.00 km"
            ),
            language="en",
            published_at=datetime(2026, 7, 29, 21, tzinfo=UTC),
            content_hash="a" * 64,
        )
        older_earthquake = Document(
            source=earthquake_source,
            url="https://example.test/older-earthquake",
            title="M 4.2 - near Tokyo, Japan",
            body=None,
            language="en",
            published_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
            content_hash="c" * 64,
        )
        canonical_document = Document(
            source=canonical_source,
            url="https://example.test/canonical",
            title="Port closure",
            body="Port closure",
            language="en",
            published_at=datetime(2026, 7, 29, 20, tzinfo=UTC),
            content_hash="b" * 64,
        )
        canonical = Event(
            event_type="port_closure",
            title="Port closure",
            status=EventStatus.CONFIRMED,
            severity=Decimal("0.500"),
            novelty=Decimal("0.500"),
            confidence=Decimal("0.900"),
            start_at=datetime(2026, 7, 29, 20, tzinfo=UTC),
            country_code="CA",
        )
        canada = CountryProfile(
            iso3="CAN",
            iso2="CA",
            name="Canada",
            region="North America",
            income_level="High income",
            capital_city="Ottawa",
            latitude=Decimal("45.421500"),
            longitude=Decimal("-75.691900"),
            source_url="https://data.worldbank.org/country/ca",
        )
        canonical.document_links.append(
            EventDocument(
                document=canonical_document,
                relevance_score=Decimal("1.000"),
                stance=DocumentStance.SUPPORTS,
                is_primary_source=True,
            )
        )
        session.add_all([earthquake, older_earthquake, canonical, canada])
        session.flush()
        title = "Magnitude 5.1 earthquake south of Tonga"
        candidate = ClusterCandidate(
            candidate_id=f"{earthquake.id}:0",
            document_id=earthquake.id,
            event_index=0,
            extractor="map-test",
            event=ExtractedEvent(
                event_type="earthquake",
                title=title,
                summary=title,
                severity=0.6,
                confidence=0.92,
                evidence_spans=[
                    EvidenceSpan(
                        field="summary",
                        source_field="title",
                        start_char=0,
                        end_char=len(earthquake.title),
                        quote=earthquake.title,
                    )
                ],
            ),
        )
        unsigned = ClusterPreviewResponse(
            embedding_provider="map-test",
            requested_document_ids=[earthquake.id],
            document_fingerprints=[
                ClusterDocumentFingerprint(
                    document_id=earthquake.id,
                    content_hash=earthquake.content_hash,
                )
            ],
            candidate_count=1,
            clusters=[
                EventClusterPreview(
                    cluster_id=1,
                    representative_candidate_id=candidate.candidate_id,
                    members=[candidate],
                )
            ],
            merge_edges=[],
            rejected_near_matches=[],
            potential_duplicate_document_ids=[],
            review_signature="0" * 64,
        )
        result = ClusterJobResult(
            preview=sign_cluster_preview(
                unsigned,
                get_settings().cluster_review_secret,
            ),
            merge_cluster_ids=[],
            review_cluster_ids=[],
            independent_cluster_ids=[1],
        )
        session.add(
            ClusterJob(
                status=ClusterJobStatus.COMPLETED,
                total_documents=1,
                processed_documents=1,
                batch_size=1,
                parameters=ClusterJobParameters.model_construct(
                    document_ids=[earthquake.id],
                    batch_size=1,
                    merge_threshold=0.86,
                    time_window_hours=48,
                    location_radius_km=100,
                ).model_dump(mode="json"),
                result=result.model_dump(mode="json"),
                completed_at=datetime(2026, 7, 29, 22, tzinfo=UTC),
            )
        )
        older_title = "Magnitude 4.2 earthquake near Tokyo"
        older_candidate = ClusterCandidate(
            candidate_id=f"{older_earthquake.id}:0",
            document_id=older_earthquake.id,
            event_index=0,
            extractor="map-test",
            event=ExtractedEvent(
                event_type="earthquake",
                title=older_title,
                summary=older_title,
                location=ExtractedLocation(
                    name="Tokyo",
                    country_code="JP",
                    latitude=35.6762,
                    longitude=139.6503,
                    confidence=0.95,
                ),
                severity=0.5,
                confidence=0.9,
                evidence_spans=[
                    EvidenceSpan(
                        field="summary",
                        source_field="title",
                        start_char=0,
                        end_char=len(older_earthquake.title),
                        quote=older_earthquake.title,
                    )
                ],
            ),
        )
        older_unsigned = ClusterPreviewResponse(
            embedding_provider="map-test",
            requested_document_ids=[older_earthquake.id],
            document_fingerprints=[
                ClusterDocumentFingerprint(
                    document_id=older_earthquake.id,
                    content_hash=older_earthquake.content_hash,
                )
            ],
            candidate_count=1,
            clusters=[
                EventClusterPreview(
                    cluster_id=1,
                    representative_candidate_id=older_candidate.candidate_id,
                    members=[older_candidate],
                )
            ],
            merge_edges=[],
            rejected_near_matches=[],
            potential_duplicate_document_ids=[],
            review_signature="0" * 64,
        )
        older_result = ClusterJobResult(
            preview=sign_cluster_preview(
                older_unsigned,
                get_settings().cluster_review_secret,
            ),
            merge_cluster_ids=[],
            review_cluster_ids=[],
            independent_cluster_ids=[1],
        )
        session.add(
            ClusterJob(
                status=ClusterJobStatus.COMPLETED,
                total_documents=1,
                processed_documents=1,
                batch_size=1,
                parameters=ClusterJobParameters.model_construct(
                    document_ids=[older_earthquake.id],
                    batch_size=1,
                    merge_threshold=0.86,
                    time_window_hours=48,
                    location_radius_km=100,
                ).model_dump(mode="json"),
                result=older_result.model_dump(mode="json"),
                completed_at=datetime(2026, 7, 28, 20, tzinfo=UTC),
            )
        )
        session.commit()

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_map_data_separates_canonical_and_candidate_layers(
    map_api: None,
) -> None:
    async def request() -> tuple[dict[str, object], str]:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            data = await client.get("/map-data")
            page = await client.get("/map")
        assert data.status_code == 200
        assert page.status_code == 200
        return data.json(), page.text

    payload, page = asyncio.run(request())

    assert payload["canonical_count"] == 1
    assert payload["candidate_count"] == 2
    canonical_marker = next(
        item for item in payload["markers"] if item["kind"] == "canonical"
    )
    candidates = [
        item for item in payload["markers"] if item["kind"] == "candidate"
    ]
    assert canonical_marker["event_id"] is not None
    assert canonical_marker["geolocation_precision"] == "country"
    assert canonical_marker["latitude"] == pytest.approx(45.4215)
    assert all(item["review_category"] == "independent" for item in candidates)
    tonga = next(item for item in candidates if item["latitude"] < 0)
    assert tonga["latitude"] == pytest.approx(-24.628)
    assert tonga["longitude"] == pytest.approx(-175.272)
    assert any(item["country_code"] == "JP" for item in candidates)
    assert "全球事件地图" in page
    assert "language-toggle" in page
