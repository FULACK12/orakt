"""Contracts for the local real-time task console."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

TaskKind = Literal["research_batch_item", "cluster_job"]
TaskState = Literal[
    "queued",
    "running",
    "cancelling",
    "cancelled",
    "skipped",
    "completed",
    "failed",
]


class TaskCancelRequest(BaseModel):
    """Require the exact task key so accidental requests cannot stop work."""

    model_config = ConfigDict(extra="forbid")

    confirmation: str = Field(min_length=3, max_length=96)


class TaskConsoleItem(BaseModel):
    """One normalized report or clustering task."""

    model_config = ConfigDict(extra="forbid")

    key: str
    kind: TaskKind
    task_id: int = Field(gt=0)
    parent_id: int | None = Field(default=None, gt=0)
    title: str
    subtitle: str
    state: TaskState
    raw_status: str
    progress_percent: float = Field(ge=0, le=100)
    stage: str
    message: str | None
    queue_position: int | None = Field(default=None, ge=1)
    can_cancel: bool
    cancel_requested_at: datetime | None
    cancel_acknowledged_at: datetime | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    heartbeat_at: datetime | None
    elapsed_seconds: float = Field(ge=0)
    stale_seconds: float | None = Field(default=None, ge=0)
    watchdog_threshold_seconds: int = Field(ge=60)
    details: dict[str, Any]


class TaskConsoleSummary(BaseModel):
    """Headline counters for the operator console."""

    model_config = ConfigDict(extra="forbid")

    queued: int = Field(ge=0)
    running: int = Field(ge=0)
    cancelling: int = Field(ge=0)
    completed: int = Field(ge=0)
    failed: int = Field(ge=0)
    cancelled: int = Field(ge=0)
    skipped: int = Field(ge=0)
    model_busy: bool


class TaskConsoleResponse(BaseModel):
    """Current task snapshot refreshed by the local console."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    refresh_after_seconds: int = Field(ge=1, le=60)
    summary: TaskConsoleSummary
    tasks: list[TaskConsoleItem]


class TaskCancelResponse(BaseModel):
    """State returned after an idempotent cancellation request."""

    model_config = ConfigDict(extra="forbid")

    accepted: bool
    safe_checkpoint: bool
    task: TaskConsoleItem


class ResearchCheckpointEntry(BaseModel):
    """Compact, inspectable state saved at one report boundary."""

    model_config = ConfigDict(extra="forbid")

    stage: str
    percent: float = Field(ge=0, le=100)
    saved_at: datetime
    attempt_count: int = Field(ge=0)
    summary: dict[str, Any]


class ResearchCheckpointResponse(BaseModel):
    """Checkpoint history and resume capability for one report task."""

    model_config = ConfigDict(extra="forbid")

    task_id: int = Field(gt=0)
    latest_stage: str | None
    latest_at: datetime | None
    resumable: bool
    entries: list[ResearchCheckpointEntry]
