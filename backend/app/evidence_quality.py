"""Shared evidence-quality labels for documents and model prompts."""

from __future__ import annotations

from typing import Any, Literal

from app.db.models import Document

DocumentEvidenceTier = Literal[
    "headline_only",
    "feed_snippet",
    "feed_content",
    "full_text",
    "official_or_structured",
]


def document_evidence_tier(document: Document) -> DocumentEvidenceTier:
    """Classify what the locally retained document can actually support."""
    metadata = document.raw_metadata or {}
    collector = str(metadata.get("collector") or "")
    body = (document.body or "").strip()
    if collector in {"ucdp_gedevents", "sec_edgar"}:
        return "official_or_structured"
    if metadata.get("full_text_status") == "complete" and len(body) >= 100:
        return "full_text"
    if len(body) >= 100:
        return "feed_content"
    if body:
        return "feed_snippet"
    return "headline_only"


def can_verify_claims(tier: str) -> bool:
    """Only substantive or structured records can independently verify a claim."""
    return tier in {"feed_content", "full_text", "official_or_structured"}


def headline_only_evidence_ids(evidence: dict[str, Any]) -> set[str]:
    """Return news references that may guide discovery but not verification."""
    documents = evidence.get("documents")
    if not isinstance(documents, list):
        return set()
    return {
        str(item["evidence_id"])
        for item in documents
        if isinstance(item, dict)
        and item.get("evidence_tier") == "headline_only"
        and item.get("evidence_id")
    }
