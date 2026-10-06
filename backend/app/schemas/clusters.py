"""Strict request and response contracts for event-cluster previews."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.extractions import ExtractedEvent


class ClusterPreviewRequest(BaseModel):
    """Controls a side-effect-free clustering run over stored documents."""

    model_config = ConfigDict(extra="forbid")

    document_ids: list[int] = Field(min_length=2, max_length=1_000)
    merge_threshold: float = Field(default=0.86, ge=0.5, le=1)
    time_window_hours: float = Field(default=48, ge=0.1, le=720)
    location_radius_km: float = Field(default=100, ge=1, le=5_000)

    @field_validator("document_ids")
    @classmethod
    def positive_unique_ids(cls, value: list[int]) -> list[int]:
        if any(document_id <= 0 for document_id in value):
            raise ValueError("document_ids must be positive")
        if len(set(value)) != len(value):
            raise ValueError("document_ids must be unique")
        return value


class ClusterCandidate(BaseModel):
    """One extracted event candidate participating in clustering."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    document_id: int = Field(gt=0)
    event_index: int = Field(ge=0)
    extractor: str
    event: ExtractedEvent


class SimilaritySignals(BaseModel):
    """Normalized similarities used in one pair decision."""

    model_config = ConfigDict(extra="forbid")

    embedding: float = Field(ge=0, le=1)
    title: float = Field(ge=0, le=1)
    entities: float | None = Field(default=None, ge=0, le=1)
    time: float | None = Field(default=None, ge=0, le=1)
    location: float | None = Field(default=None, ge=0, le=1)


class PairEvaluation(BaseModel):
    """Explain why two candidates were merged or kept separate."""

    model_config = ConfigDict(extra="forbid")

    left_candidate_id: str
    right_candidate_id: str
    score: float = Field(ge=0, le=1)
    signals: SimilaritySignals
    merged: bool
    blocker: str | None = None
    reasons: list[str] = Field(default_factory=list)


class EventClusterPreview(BaseModel):
    """One proposed canonical event and its supporting candidates."""

    model_config = ConfigDict(extra="forbid")

    cluster_id: int = Field(gt=0)
    representative_candidate_id: str
    members: list[ClusterCandidate] = Field(min_length=1)

    @model_validator(mode="after")
    def representative_is_a_member(self) -> Self:
        member_ids = {member.candidate_id for member in self.members}
        if self.representative_candidate_id not in member_ids:
            raise ValueError("representative_candidate_id must identify a member")
        return self


class ClusterPreviewResponse(BaseModel):
    """Reviewable clustering output that never performs deletion."""

    model_config = ConfigDict(extra="forbid")

    embedding_provider: str
    requested_document_ids: list[int]
    document_fingerprints: list[ClusterDocumentFingerprint]
    candidate_count: int = Field(ge=0)
    clusters: list[EventClusterPreview]
    merge_edges: list[PairEvaluation]
    rejected_near_matches: list[PairEvaluation]
    potential_duplicate_document_ids: list[int]
    safe_to_delete_document_ids: list[int] = Field(default_factory=list)
    deletions_performed: Literal[False] = False
    review_signature: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )


class ClusterDocumentFingerprint(BaseModel):
    """Binds a reviewed preview to one immutable stored document version."""

    model_config = ConfigDict(extra="forbid")

    document_id: int = Field(gt=0)
    content_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )


class ClusterApplyRequest(BaseModel):
    """Explicitly confirms persistence of selected signed preview clusters."""

    model_config = ConfigDict(extra="forbid")

    preview: ClusterPreviewResponse
    selected_cluster_ids: list[int] = Field(min_length=1)
    confirm_persistence: Literal[True]

    @field_validator("selected_cluster_ids")
    @classmethod
    def unique_positive_cluster_ids(cls, value: list[int]) -> list[int]:
        if any(cluster_id <= 0 for cluster_id in value):
            raise ValueError("selected_cluster_ids must be positive")
        if len(set(value)) != len(value):
            raise ValueError("selected_cluster_ids must be unique")
        return value


class AppliedEventCluster(BaseModel):
    """One canonical event created or reused by an apply operation."""

    model_config = ConfigDict(extra="forbid")

    cluster_id: int = Field(gt=0)
    event_id: int = Field(gt=0)
    created: bool
    document_ids: list[int] = Field(min_length=1)


class ClusterApplyResponse(BaseModel):
    """Persistence outcome; cold archive deletion remains a separate review."""

    model_config = ConfigDict(extra="forbid")

    applied_clusters: list[AppliedEventCluster]
    created_event_count: int = Field(ge=0)
    linked_document_count: int = Field(ge=0)
    cold_archive_review_candidates: list[int]
    deletions_performed: Literal[False] = False
