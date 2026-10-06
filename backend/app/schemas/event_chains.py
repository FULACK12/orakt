"""Contracts for conservative, reviewable event-chain suggestions."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EventRelationType = Literal["temporal_follow_up", "reported_follow_up"]
EventRelationStatus = Literal["suggested", "accepted", "rejected"]


class EventRelationView(BaseModel):
    """One proposed directed edge between extracted event candidates."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(gt=0)
    cluster_job_id: int = Field(gt=0)
    source_candidate_id: str
    source_title: str
    source_occurred_at: datetime
    target_candidate_id: str
    target_title: str
    target_occurred_at: datetime
    relation_type: EventRelationType
    confidence: float = Field(ge=0, le=1)
    rationale: str
    evidence_document_ids: list[int]
    status: EventRelationStatus
    pinned: bool
    review_note: str | None
    decided_at: datetime | None


class EventChainResponse(BaseModel):
    """Reviewable edges generated for one immutable clustering snapshot."""

    model_config = ConfigDict(extra="forbid")

    cluster_job_id: int = Field(gt=0)
    relation_count: int = Field(ge=0)
    fixed_relation_count: int = Field(ge=0)
    relations: list[EventRelationView]
    causality_is_confirmed: Literal[False] = False


class EventChainGenerationResponse(EventChainResponse):
    """Idempotent generation result."""

    generated_count: int = Field(ge=0)


class EventRelationDecisionRequest(BaseModel):
    """Human decision for one proposed relationship."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["accepted", "rejected"]
    pinned: bool = False
    review_note: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_pin_state(self) -> EventRelationDecisionRequest:
        """Only accepted evidence links can be fixed onto the map."""
        if self.pinned and self.status != "accepted":
            raise ValueError("pinned relations must be accepted")
        return self
