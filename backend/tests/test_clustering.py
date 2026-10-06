"""Multi-signal event clustering and safety-gate tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.clustering import (
    CandidateFeatures,
    EventClusterer,
    source_event_anchors,
)
from app.schemas.extractions import (
    EvidenceSpan,
    ExtractedEntity,
    ExtractedEvent,
    ExtractedLocation,
)


def earthquake_event(
    *,
    title: str,
    occurred_at: datetime,
    latitude: float,
    longitude: float,
) -> ExtractedEvent:
    return ExtractedEvent(
        event_type="earthquake",
        title=title,
        summary=title,
        entities=[
            ExtractedEntity(
                name="Tonga",
                entity_type="location",
                confidence=0.95,
            )
        ],
        location=ExtractedLocation(
            name="south of Tonga",
            country_code="TO",
            latitude=latitude,
            longitude=longitude,
            confidence=0.95,
        ),
        occurred_at=occurred_at,
        severity=0.5,
        confidence=0.9,
        evidence_spans=[
            EvidenceSpan(
                field="summary",
                source_field="title",
                start_char=0,
                end_char=len(title),
                quote=title,
            )
        ],
    )


def candidate(
    document_id: int,
    event: ExtractedEvent,
    embedding: tuple[float, ...] = (1.0, 0.0, 0.0),
) -> CandidateFeatures:
    return CandidateFeatures(
        candidate_id=f"{document_id}:0",
        document_id=document_id,
        event_index=0,
        extractor="test",
        event=event,
        embedding=embedding,
    )


def clusterer() -> EventClusterer:
    return EventClusterer(
        merge_threshold=0.86,
        time_window_hours=48,
        location_radius_km=100,
    )


def test_same_earthquake_reports_merge_but_different_magnitude_does_not() -> None:
    occurred = datetime(2026, 7, 29, 17, 7, 35, tzinfo=UTC)
    first = candidate(
        1,
        earthquake_event(
            title="M 5.0 - south of Tonga",
            occurred_at=occurred,
            latitude=-24.696,
            longitude=-175.290,
        ),
    )
    second = candidate(
        2,
        earthquake_event(
            title="M 5.0 earthquake south of Tonga",
            occurred_at=occurred + timedelta(seconds=2),
            latitude=-24.695,
            longitude=-175.291,
        ),
        (0.999, 0.001, 0.0),
    )
    separate = candidate(
        3,
        earthquake_event(
            title="M 4.3 earthquake south of Tonga",
            occurred_at=occurred + timedelta(seconds=30),
            latitude=-24.694,
            longitude=-175.292,
        ),
        (0.999, 0.001, 0.0),
    )

    result = clusterer().cluster([first, second, separate])

    assert len(result.clusters) == 2
    assert result.clusters[0].representative_candidate_id == "1:0"
    assert {member.document_id for member in result.clusters[0].members} == {1, 2}
    assert result.potential_duplicate_document_ids == [2]
    blocked = next(
        item
        for item in result.rejected_near_matches
        if item.right_candidate_id == "3:0"
    )
    assert blocked.blocker == "earthquake_magnitude_mismatch"


def test_identical_earthquake_titles_hours_apart_are_not_merged() -> None:
    occurred = datetime(2026, 7, 29, 3, 52, 22, tzinfo=UTC)
    first = candidate(
        22,
        earthquake_event(
            title="M 5.0 - south of Tonga",
            occurred_at=occurred,
            latitude=-24.636,
            longitude=-174.924,
        ),
    )
    second = candidate(
        45,
        earthquake_event(
            title="M 5.0 - south of Tonga",
            occurred_at=occurred + timedelta(hours=13),
            latitude=-24.696,
            longitude=-175.290,
        ),
    )

    result = clusterer().cluster([first, second])

    assert len(result.clusters) == 2
    assert result.merge_edges == []
    assert result.rejected_near_matches[0].blocker == "event_time_too_far_apart"
    assert result.potential_duplicate_document_ids == []


def test_naive_provider_time_is_normalized_before_comparison() -> None:
    aware = datetime(2026, 7, 29, 3, 52, 22, tzinfo=UTC)
    first = candidate(
        1,
        earthquake_event(
            title="M 5.0 - south of Tonga",
            occurred_at=aware,
            latitude=-24.696,
            longitude=-175.290,
        ),
    )
    second = candidate(
        2,
        earthquake_event(
            title="M 5.0 earthquake south of Tonga",
            occurred_at=aware.replace(tzinfo=None),
            latitude=-24.695,
            longitude=-175.291,
        ),
        (0.999, 0.001, 0.0),
    )

    result = clusterer().cluster([first, second])

    assert second.event.occurred_at == aware
    assert result.merge_edges[0].merged is True


def test_source_coordinates_block_false_merge_when_model_omits_location() -> None:
    first_time, first_lat, first_lon, first_magnitude = source_event_anchors(
        "M 5.0 - 48 km SW of Balangonan, Philippines",
        (
            "Time 2026-07-29 13:23:56 UTC at epicenter "
            "Location 5.318°N 124.995°E"
        ),
    )
    second_time, second_lat, second_lon, second_magnitude = source_event_anchors(
        "M 5.0 - 4 km NNE of Balangonan, Philippines",
        (
            "Time 2026-07-29 13:16:59 UTC at epicenter "
            "Location 5.616°N 125.365°E"
        ),
    )
    assert first_time is not None
    assert second_time is not None
    first_event = earthquake_event(
        title="M 5.0 - 48 km SW of Balangonan, Philippines",
        occurred_at=first_time,
        latitude=5.6,
        longitude=125.3,
    ).model_copy(update={"location": None})
    second_event = earthquake_event(
        title="M 5.0 - 4 km NNE of Balangonan, Philippines",
        occurred_at=second_time,
        latitude=5.6,
        longitude=125.3,
    ).model_copy(update={"location": None})
    first = CandidateFeatures(
        candidate_id="30:0",
        document_id=30,
        event_index=0,
        extractor="ollama",
        event=first_event,
        embedding=(1.0, 0.0),
        source_occurred_at=first_time,
        source_latitude=first_lat,
        source_longitude=first_lon,
        source_magnitude=first_magnitude,
    )
    second = CandidateFeatures(
        candidate_id="32:0",
        document_id=32,
        event_index=0,
        extractor="ollama",
        event=second_event,
        embedding=(0.999, 0.001),
        source_occurred_at=second_time,
        source_latitude=second_lat,
        source_longitude=second_lon,
        source_magnitude=second_magnitude,
    )

    result = clusterer().cluster([first, second])

    assert result.merge_edges == []
    assert result.rejected_near_matches[0].blocker == (
        "earthquake_location_too_far_apart"
    )
    assert result.potential_duplicate_document_ids == []
