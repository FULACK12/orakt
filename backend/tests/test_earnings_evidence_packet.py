"""Synthetic offline checks; no financial observations or inference."""
from dataclasses import replace
from hashlib import sha256

import pytest

from app.earnings_evidence_packet import (
    EvidenceDocument, EvidencePacketError, build_evidence_packet,
)
from app.earnings_phase_manifest import (
    EarningsEvent, PhaseCutoffs, ManifestVersions, EvidenceReference,
    build_earnings_phase_manifest,
)

TEXT = "Synthetic evidence / 合成测试证据"
DOC = EvidenceDocument("fixture", TEXT, "https://example.com/fixture")


def manifest():
    return build_earnings_phase_manifest(
        event=EarningsEvent("issuer", "security", "TEST", "TEST", "event", "2025Q1",
                            "2025-04-01T20:00:00Z", "exact"),
        cutoffs=PhaseCutoffs("2025-04-01T19:00:00Z", "2025-04-01T20:00:00Z",
                            "2025-04-02T20:00:00Z", True),
        versions=ManifestVersions("m1", "t1", "f1"),
        evidence=(EvidenceReference("fixture", "2025-04-01T18:00:00Z", "v1",
                                    sha256(TEXT.encode()).hexdigest(), "fixture"),),
        required_evidence_refs={"pre_earnings": ("fixture",)},
        now="2026-10-05T00:00:00Z",
    )[0]


def test_exact_materialization():
    task = manifest()
    packet = build_evidence_packet(task, {DOC.id: DOC})
    assert packet.documents == (DOC,)
    assert packet.total_utf8_bytes == len(TEXT.encode())
    assert packet.manifest_fingerprint == task.fingerprint
    assert packet.execution_permitted is False


@pytest.mark.parametrize("documents", [{}, {"fixture": DOC, "extra": DOC}])
def test_missing_and_extra_documents_rejected(documents):
    with pytest.raises(EvidencePacketError, match="document_set"):
        build_evidence_packet(manifest(), documents)


@pytest.mark.parametrize("document,reason", [
    (replace(DOC, text=TEXT + " newer version"), "hash_mismatch"),
    (replace(DOC, text=" "), "empty_document"),
    (replace(DOC, id="other"), "identity_mismatch"),
    (replace(DOC, source_url=""), "source_attribution"),
    (replace(DOC, source_url="https://"), "source_attribution"),
    (replace(DOC, source_url="https://user:password@example.com"), "source_attribution"),
    (replace(DOC, source_url="https://example.com/\ninvalid"), "source_attribution"),
])
def test_changed_or_unattributed_document_rejected(document, reason):
    with pytest.raises(EvidencePacketError, match=reason):
        build_evidence_packet(manifest(), {"fixture": document})


def test_byte_limit_is_utf8_not_character_count():
    with pytest.raises(EvidencePacketError, match="byte_limit_exceeded"):
        build_evidence_packet(manifest(), {DOC.id: DOC}, max_utf8_bytes=len(TEXT))


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_invalid_limits_fail_closed(limit):
    with pytest.raises(EvidencePacketError, match="invalid_context"):
        build_evidence_packet(manifest(), {DOC.id: DOC}, max_utf8_bytes=limit)


def test_blocked_manifest_cannot_be_materialized():
    with pytest.raises(EvidencePacketError, match="not_ready"):
        build_evidence_packet(replace(manifest(), status="blocked"), {DOC.id: DOC})


def test_tampered_temporal_metadata_is_rejected():
    task = manifest()
    changed = replace(task.evidence[0], available_at="2026-01-01T00:00:00Z")
    with pytest.raises(EvidencePacketError, match="after_cutoff"):
        build_evidence_packet(replace(task, evidence=(changed,)), {DOC.id: DOC})


def test_required_ref_is_never_silently_dropped():
    with pytest.raises(EvidencePacketError, match="required_evidence"):
        build_evidence_packet(replace(manifest(), required_evidence_refs=("missing",)), {DOC.id: DOC})
