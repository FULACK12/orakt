"""Constrained string values persisted by the first database migration."""

from enum import StrEnum

from sqlalchemy import Enum


class SourceType(StrEnum):
    """Supported source acquisition and ownership categories."""

    RSS = "rss"
    NEWS = "news"
    OFFICIAL = "official"
    GOVERNMENT = "government"
    CENTRAL_BANK = "central_bank"
    RESEARCH = "research"
    API = "api"


class EventStatus(StrEnum):
    """Current factual verification state of an event."""

    CONFIRMED = "confirmed"
    PARTIALLY_CONFIRMED = "partially_confirmed"
    RUMOUR = "rumour"
    DENIED = "denied"


class DocumentStance(StrEnum):
    """How one document relates to the current event claim."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


class ClusterJobStatus(StrEnum):
    """Lifecycle states for persistent background clustering jobs."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ClusterReviewDecision(StrEnum):
    """Human decisions for one rejected near-match pair."""

    MERGE = "merge"
    INDEPENDENT = "independent"
    IGNORED = "ignored"


def persisted_enum[EnumT: StrEnum](
    enum_class: type[EnumT],
    name: str,
) -> Enum:
    """Build a portable VARCHAR-backed enum storing StrEnum values."""
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )
