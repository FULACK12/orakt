"""Explainable multi-signal clustering for extracted event candidates."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import cast

from app.schemas.clusters import (
    ClusterCandidate,
    EventClusterPreview,
    PairEvaluation,
    SimilaritySignals,
)
from app.schemas.extractions import ExtractedEvent

TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)
MAGNITUDE_PATTERN = re.compile(r"\bM\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
SOURCE_TIME_PATTERN = re.compile(
    r"Time\s+(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) UTC"
)
SOURCE_LOCATION_PATTERN = re.compile(
    r"Location\s+"
    r"(?P<latitude>\d+(?:\.\d+)?)[^\dNSEW]*(?P<latitude_direction>[NS])\s+"
    r"(?P<longitude>\d+(?:\.\d+)?)[^\dNSEW]*(?P<longitude_direction>[EW])"
)

SIGNAL_WEIGHTS = {
    "embedding": 0.45,
    "title": 0.25,
    "entities": 0.12,
    "time": 0.10,
    "location": 0.08,
}


@dataclass(frozen=True)
class CandidateFeatures:
    """Internal event candidate plus its provider-generated embedding."""

    candidate_id: str
    document_id: int
    event_index: int
    extractor: str
    event: ExtractedEvent
    embedding: tuple[float, ...]
    source_occurred_at: datetime | None = None
    source_latitude: float | None = None
    source_longitude: float | None = None
    source_magnitude: float | None = None

    def public(self) -> ClusterCandidate:
        return ClusterCandidate(
            candidate_id=self.candidate_id,
            document_id=self.document_id,
            event_index=self.event_index,
            extractor=self.extractor,
            event=self.event,
        )


@dataclass(frozen=True)
class ClusteringResult:
    clusters: list[EventClusterPreview]
    merge_edges: list[PairEvaluation]
    rejected_near_matches: list[PairEvaluation]
    potential_duplicate_document_ids: list[int]


class EventClusterer:
    """Merge candidates only when semantic and factual signals agree."""

    def __init__(
        self,
        *,
        merge_threshold: float,
        time_window_hours: float,
        location_radius_km: float,
    ) -> None:
        self._merge_threshold = merge_threshold
        self._time_window_hours = time_window_hours
        self._location_radius_km = location_radius_km

    def cluster(self, candidates: list[CandidateFeatures]) -> ClusteringResult:
        parents = list(range(len(candidates)))
        merge_edges: list[PairEvaluation] = []
        rejected: list[PairEvaluation] = []

        for left_index, left in enumerate(candidates):
            for right_index in range(left_index + 1, len(candidates)):
                right = candidates[right_index]
                if left.document_id == right.document_id:
                    continue
                evaluation = self._evaluate(left, right)
                if evaluation.merged:
                    self._union(parents, left_index, right_index)
                    merge_edges.append(evaluation)
                elif evaluation.score >= max(0.5, self._merge_threshold - 0.15):
                    rejected.append(evaluation)

        grouped: dict[int, list[CandidateFeatures]] = {}
        for index, candidate in enumerate(candidates):
            root = self._find(parents, index)
            grouped.setdefault(root, []).append(candidate)

        clusters: list[EventClusterPreview] = []
        potential_duplicates: set[int] = set()
        ordered_groups = sorted(
            grouped.values(),
            key=lambda members: min(member.document_id for member in members),
        )
        for cluster_id, members in enumerate(ordered_groups, start=1):
            representative = max(members, key=self._representative_rank)
            for member in members:
                if member.document_id != representative.document_id:
                    potential_duplicates.add(member.document_id)
            clusters.append(
                EventClusterPreview(
                    cluster_id=cluster_id,
                    representative_candidate_id=representative.candidate_id,
                    members=[
                        member.public()
                        for member in sorted(
                            members,
                            key=lambda item: (item.document_id, item.event_index),
                        )
                    ],
                )
            )

        return ClusteringResult(
            clusters=clusters,
            merge_edges=sorted(
                merge_edges,
                key=lambda item: item.score,
                reverse=True,
            ),
            rejected_near_matches=sorted(
                rejected,
                key=lambda item: item.score,
                reverse=True,
            ),
            potential_duplicate_document_ids=sorted(potential_duplicates),
        )

    def _evaluate(
        self,
        left: CandidateFeatures,
        right: CandidateFeatures,
    ) -> PairEvaluation:
        embedding = _cosine_similarity(left.embedding, right.embedding)
        title = _text_similarity(left.event.title, right.event.title)
        entities = _entity_similarity(left.event, right.event)
        time = _time_similarity(
            left.source_occurred_at or left.event.occurred_at,
            right.source_occurred_at or right.event.occurred_at,
            self._time_window_hours,
        )
        location = _candidate_location_similarity(
            left,
            right,
            self._location_radius_km,
        )
        signals = SimilaritySignals(
            embedding=embedding,
            title=title,
            entities=entities,
            time=time,
            location=location,
        )
        score = _weighted_score(signals)
        blocker = self._blocker(left, right)
        merged = (
            blocker is None
            and left.event.event_type == right.event.event_type
            and score >= self._merge_threshold
        )
        if left.event.event_type != right.event.event_type:
            blocker = "different_event_type"
        reasons = [
            name
            for name, value in signals.model_dump().items()
            if value is not None and value >= 0.8
        ]
        return PairEvaluation(
            left_candidate_id=left.candidate_id,
            right_candidate_id=right.candidate_id,
            score=score,
            signals=signals,
            merged=merged,
            blocker=blocker,
            reasons=reasons,
        )

    def _blocker(
        self,
        left: CandidateFeatures,
        right: CandidateFeatures,
    ) -> str | None:
        if left.event.event_type != right.event.event_type:
            return "different_event_type"
        left_time = left.source_occurred_at or left.event.occurred_at
        right_time = right.source_occurred_at or right.event.occurred_at
        if left_time is not None and right_time is not None:
            delta_hours = _hours_between(left_time, right_time)
            limit = (
                10 / 60
                if left.event.event_type == "earthquake"
                else self._time_window_hours
            )
            if delta_hours > limit:
                return "event_time_too_far_apart"
        if left.event.event_type == "earthquake":
            left_magnitude = left.source_magnitude or _magnitude(left.event.title)
            right_magnitude = right.source_magnitude or _magnitude(right.event.title)
            if (
                left_magnitude is not None
                and right_magnitude is not None
                and abs(left_magnitude - right_magnitude) > 0.3
            ):
                return "earthquake_magnitude_mismatch"
            distance = _candidate_coordinate_distance(left, right)
            if distance is not None and distance > min(25, self._location_radius_km):
                return "earthquake_location_too_far_apart"
        return None

    @staticmethod
    def _representative_rank(candidate: CandidateFeatures) -> tuple[float, int, int]:
        completeness = (
            len(candidate.event.entities)
            + int(candidate.event.location is not None)
            + int(candidate.event.occurred_at is not None)
            + len(candidate.event.evidence_spans)
        )
        return (
            candidate.event.confidence,
            completeness,
            -candidate.document_id,
        )

    @staticmethod
    def _find(parents: list[int], index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    @classmethod
    def _union(cls, parents: list[int], left: int, right: int) -> None:
        left_root = cls._find(parents, left)
        right_root = cls._find(parents, right)
        if left_root != right_root:
            parents[right_root] = left_root


def candidate_embedding_text(event: ExtractedEvent) -> str:
    """Build the semantic representation shared by all embedding providers."""
    entities = ", ".join(entity.name for entity in event.entities)
    location = event.location.name if event.location is not None else ""
    occurred = event.occurred_at.isoformat() if event.occurred_at is not None else ""
    return "\n".join(
        (
            f"type: {event.event_type}",
            f"title: {event.title}",
            f"summary: {event.summary}",
            f"entities: {entities}",
            f"location: {location}",
            f"time: {occurred}",
        )
    )


def source_event_anchors(
    title: str,
    body: str,
) -> tuple[datetime | None, float | None, float | None, float | None]:
    """Parse high-confidence time, coordinates and magnitude from source text."""
    occurred_at: datetime | None = None
    time_match = SOURCE_TIME_PATTERN.search(body)
    if time_match is not None:
        occurred_at = datetime.strptime(
            time_match.group("timestamp"),
            "%Y-%m-%d %H:%M:%S",
        ).replace(tzinfo=UTC)

    latitude: float | None = None
    longitude: float | None = None
    location_match = SOURCE_LOCATION_PATTERN.search(body)
    if location_match is not None:
        latitude = float(location_match.group("latitude"))
        longitude = float(location_match.group("longitude"))
        if location_match.group("latitude_direction") == "S":
            latitude *= -1
        if location_match.group("longitude_direction") == "W":
            longitude *= -1
    return occurred_at, latitude, longitude, _magnitude(title)


def _tokens(text: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(text.casefold()))


def _text_similarity(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    union = left_tokens | right_tokens
    jaccard = len(left_tokens & right_tokens) / len(union) if union else 0.0
    sequence = SequenceMatcher(None, left.casefold(), right.casefold()).ratio()
    return min(1.0, (jaccard + sequence) / 2)


def _entity_similarity(
    left: ExtractedEvent,
    right: ExtractedEvent,
) -> float | None:
    left_entities = {entity.name.casefold() for entity in left.entities}
    right_entities = {entity.name.casefold() for entity in right.entities}
    if not left_entities or not right_entities:
        return None
    union = left_entities | right_entities
    return len(left_entities & right_entities) / len(union)


def _time_similarity(
    left: datetime | None,
    right: datetime | None,
    window_hours: float,
) -> float | None:
    if left is None or right is None:
        return None
    return max(0.0, 1 - (_hours_between(left, right) / window_hours))


def _hours_between(left: datetime, right: datetime) -> float:
    return abs((_as_utc(left) - _as_utc(right)).total_seconds()) / 3600


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _location_similarity(
    left: ExtractedEvent,
    right: ExtractedEvent,
    radius_km: float,
) -> float | None:
    if left.location is None or right.location is None:
        return None
    distance = _coordinate_distance(left, right)
    if distance is not None:
        return max(0.0, 1 - (distance / radius_km))
    return _text_similarity(left.location.name, right.location.name)


def _candidate_location_similarity(
    left: CandidateFeatures,
    right: CandidateFeatures,
    radius_km: float,
) -> float | None:
    distance = _candidate_coordinate_distance(left, right)
    if distance is not None:
        return max(0.0, 1 - (distance / radius_km))
    return _location_similarity(left.event, right.event, radius_km)


def _candidate_coordinate_distance(
    left: CandidateFeatures,
    right: CandidateFeatures,
) -> float | None:
    if (
        left.source_latitude is not None
        and left.source_longitude is not None
        and right.source_latitude is not None
        and right.source_longitude is not None
    ):
        return _haversine_distance(
            left.source_latitude,
            left.source_longitude,
            right.source_latitude,
            right.source_longitude,
        )
    return _coordinate_distance(left.event, right.event)


def _coordinate_distance(
    left: ExtractedEvent,
    right: ExtractedEvent,
) -> float | None:
    if left.location is None or right.location is None:
        return None
    if (
        left.location.latitude is None
        or left.location.longitude is None
        or right.location.latitude is None
        or right.location.longitude is None
    ):
        return None
    return _haversine_distance(
        left.location.latitude,
        left.location.longitude,
        right.location.latitude,
        right.location.longitude,
    )


def _haversine_distance(
    left_latitude: float,
    left_longitude: float,
    right_latitude: float,
    right_longitude: float,
) -> float:
    left_lat = math.radians(left_latitude)
    right_lat = math.radians(right_latitude)
    delta_lat = right_lat - left_lat
    delta_lon = math.radians(right_longitude - left_longitude)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(left_lat)
        * math.cos(right_lat)
        * math.sin(delta_lon / 2) ** 2
    )
    return 6_371 * 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))


def _cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    cosine = sum(a * b for a, b in zip(left, right, strict=True)) / (
        left_norm * right_norm
    )
    return max(0.0, min(1.0, cosine))


def _weighted_score(signals: SimilaritySignals) -> float:
    values = cast(dict[str, float | None], signals.model_dump())
    available = {
        name: value
        for name, value in values.items()
        if value is not None
    }
    weight_sum = sum(SIGNAL_WEIGHTS[name] for name in available)
    if not weight_sum:
        return 0.0
    score = sum(
        SIGNAL_WEIGHTS[name] * value
        for name, value in available.items()
    ) / weight_sum
    return round(max(0.0, min(1.0, score)), 6)


def _magnitude(title: str) -> float | None:
    match = MAGNITUDE_PATTERN.search(title)
    return float(match.group(1)) if match is not None else None
