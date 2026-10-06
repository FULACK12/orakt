"""Validated collector result contracts."""

from typing import Literal

from pydantic import BaseModel, Field

CollectionStatus = Literal[
    "success",
    "not_modified",
    "skipped_disabled",
    "skipped_not_due",
    "error",
]


class FeedCollectionResult(BaseModel):
    """Outcome of one isolated feed attempt."""

    feed_id: int | None
    feed_url: str
    status: CollectionStatus
    http_status: int | None = None
    entries_seen: int = 0
    documents_created: int = 0
    documents_enriched: int = 0
    duplicates_skipped: int = 0
    invalid_entries: int = 0
    error: str | None = None


class BatchCollectionResult(BaseModel):
    """Outcomes from one scheduler pass."""

    results: list[FeedCollectionResult] = Field(default_factory=list)

    @property
    def documents_created(self) -> int:
        """Return total new documents across successful feed attempts."""
        return sum(result.documents_created for result in self.results)

    @property
    def documents_enriched(self) -> int:
        """Return discovery records upgraded with licensed feed text."""
        return sum(result.documents_enriched for result in self.results)

    @property
    def errors(self) -> int:
        """Return the number of isolated feed failures."""
        return sum(result.status == "error" for result in self.results)
