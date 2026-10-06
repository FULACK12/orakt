"""Validated contracts for the human clustering review queue."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.enums import ClusterJobStatus, ClusterReviewDecision
from app.schemas.clusters import ClusterCandidate, SimilaritySignals


class ClusterReviewDocument(BaseModel):
    """Source metadata shown beside an extracted event candidate."""

    model_config = ConfigDict(extra="forbid")

    document_id: int = Field(gt=0)
    title: str
    url: str
    source_name: str
    source_country: str | None
    language: str | None
    published_at: datetime | None
    raw_object_path: str | None


class ClusterReviewCandidate(BaseModel):
    """A candidate and its original source document."""

    model_config = ConfigDict(extra="forbid")

    cluster_id: int = Field(gt=0)
    candidate: ClusterCandidate
    document: ClusterReviewDocument


class ClusterReviewDecisionView(BaseModel):
    """Latest persisted decision for one review pair."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(gt=0)
    decision: ClusterReviewDecision
    note: str | None
    applied_event_ids: list[int]
    created_at: datetime


class ClusterReviewItem(BaseModel):
    """One rejected near-match comparison awaiting a human decision."""

    model_config = ConfigDict(extra="forbid")

    review_key: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )
    left: ClusterReviewCandidate
    right: ClusterReviewCandidate
    score: float = Field(ge=0, le=1)
    signals: SimilaritySignals
    blocker: str | None
    reasons: list[str]
    decision: ClusterReviewDecisionView | None


class ClusterReviewSummary(BaseModel):
    """Current decision counts across a job's review queue."""

    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    pending: int = Field(ge=0)
    merged: int = Field(ge=0)
    independent: int = Field(ge=0)
    ignored: int = Field(ge=0)


class ClusterReviewQueueResponse(BaseModel):
    """Complete review queue for one completed clustering job."""

    model_config = ConfigDict(extra="forbid")

    job_id: int = Field(gt=0)
    job_status: ClusterJobStatus
    completed_at: datetime | None
    summary: ClusterReviewSummary
    items: list[ClusterReviewItem]


class ClusterReviewDecisionRequest(BaseModel):
    """A deliberate local review action."""

    model_config = ConfigDict(extra="forbid")

    decision: ClusterReviewDecision
    note: str | None = Field(default=None, max_length=1_000)
    confirm_merge: Literal[True] | bool = False

    @model_validator(mode="after")
    def merge_is_explicitly_confirmed(self) -> Self:
        if (
            self.decision is ClusterReviewDecision.MERGE
            and self.confirm_merge is not True
        ):
            raise ValueError("confirm_merge must be true for a merge decision")
        return self


class ClusterReviewDecisionResponse(BaseModel):
    """Persisted review decision and its canonical-event effects."""

    model_config = ConfigDict(extra="forbid")

    review_key: str
    decision: ClusterReviewDecisionView
    created_event_count: int = Field(ge=0)
    linked_document_count: int = Field(ge=0)
    deletions_performed: Literal[False] = False
