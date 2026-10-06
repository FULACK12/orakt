"""Materialize a frozen earnings manifest into a verified, offline model input.

No fetching, inference, database writes or launch permissions live here. This
boundary intentionally excludes the legacy latest-data research pack. Document
hashes cover exact UTF-8 text; callers must archive those exact bytes. Passing
these checks establishes integrity/time eligibility, not factual truth or rights
to upload content to a third party.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

from .earnings_phase_manifest import PhaseManifest


class EvidencePacketError(ValueError):
    """A frozen input cannot safely be materialized."""


@dataclass(frozen=True)
class EvidenceDocument:
    id: str
    text: str
    source_url: str


@dataclass(frozen=True)
class EarningsEvidencePacket:
    manifest_fingerprint: str
    phase: str
    cutoff: str
    mode: str
    documents: tuple[EvidenceDocument, ...]
    total_utf8_bytes: int
    execution_permitted: bool = False


def build_evidence_packet(
    manifest: PhaseManifest,
    documents: Mapping[str, EvidenceDocument],
    *,
    max_utf8_bytes: int = 1_000_000,
) -> EarningsEvidencePacket:
    """Accept exactly the manifest's evidence; reject drift instead of truncating.

    Source URLs are attribution only, never fetched. A caller must select a
    smaller evidence manifest upstream if the context budget is exceeded, so
    required evidence is never silently dropped. This byte limit is not a token
    budget: the eventual model adapter must additionally check token capacity.
    """
    if manifest.status != "ready" or manifest.reasons:
        raise EvidencePacketError("manifest_not_ready")
    if manifest.mode != "historical_reconstruction" or not manifest.cutoff:
        raise EvidencePacketError("unsupported_manifest")
    if type(max_utf8_bytes) is not int or max_utf8_bytes <= 0:
        raise EvidencePacketError("invalid_context_byte_limit")
    expected_ids = {ref.id for ref in manifest.evidence}
    if not expected_ids or len(expected_ids) != len(manifest.evidence):
        raise EvidencePacketError("empty_or_duplicate_manifest_evidence")
    if set(documents) != expected_ids:
        raise EvidencePacketError("document_set_does_not_match_manifest")
    if not set(manifest.required_evidence_refs).issubset(expected_ids):
        raise EvidencePacketError("required_evidence_missing")
    verified: list[EvidenceDocument] = []
    total = 0
    for ref in manifest.evidence:
        # Defense in depth: never trust a modified dataclass's status alone.
        if datetime.fromisoformat(ref.available_at) > datetime.fromisoformat(manifest.cutoff):
            raise EvidencePacketError("evidence_after_cutoff")
        document = documents[ref.id]
        if not isinstance(document, EvidenceDocument) or document.id != ref.id:
            raise EvidencePacketError("document_identity_mismatch")
        if not isinstance(document.text, str) or not document.text.strip():
            raise EvidencePacketError("empty_document")
        if not isinstance(document.source_url, str):
            raise EvidencePacketError("missing_https_source_attribution")
        try:
            source = urlsplit(document.source_url)
            valid_source = (
                source.scheme == "https" and bool(source.hostname)
                and source.username is None and source.password is None
                and not any(char.isspace() for char in document.source_url)
            )
        except ValueError:
            valid_source = False
        if not valid_source:
            raise EvidencePacketError("missing_https_source_attribution")
        encoded = document.text.encode("utf-8")
        if hashlib.sha256(encoded).hexdigest() != ref.content_sha256:
            raise EvidencePacketError("document_hash_mismatch")
        total += len(encoded)
        if total > max_utf8_bytes:
            raise EvidencePacketError("context_byte_limit_exceeded")
        verified.append(document)
    return EarningsEvidencePacket(
        manifest_fingerprint=manifest.fingerprint, phase=manifest.phase,
        cutoff=manifest.cutoff, mode=manifest.mode,
        documents=tuple(verified), total_utf8_bytes=total,
    )
