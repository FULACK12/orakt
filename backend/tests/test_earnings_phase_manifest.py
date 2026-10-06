"""Synthetic offline inputs only: no DB, cloud, market data, or research calls."""

from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest

from app.earnings_phase_manifest import (
    EarningsEvent,
    EvidenceReference,
    ManifestVersions,
    Phase,
    PhaseCutoffs,
    PhaseManifest,
    build_earnings_phase_manifest,
)

NOW = datetime(2026, 10, 5, 20, tzinfo=UTC)
EVENT = EarningsEvent(
    issuer_id="synthetic-issuer-1", security_id="synthetic-security-1", ticker="TEST_ONLY",
    exchange="SYNTHETIC_EXCHANGE", event_id="synthetic-earnings-2026q3", fiscal_period="2026-Q3",
    actual_release_at="2026-10-02T20:00:00Z", release_time_precision="exact",
)
CUTOFFS = PhaseCutoffs(
    pre_earnings_at="2026-10-02T19:59:59Z", release_at="2026-10-02T20:05:00Z",
    post_earnings_validation_at="2026-10-05T20:00:00Z", post_session_verified=True,
)
VERSIONS = ManifestVersions("synthetic-model-v1", "template-v1", "all-factor-pack-v1")


def reference(id_: str, available_at: str | None, *, content: str = "fixture") -> EvidenceReference:
    return EvidenceReference(
        id=id_, available_at=available_at, version="v1",
        content_sha256=hashlib.sha256(content.encode()).hexdigest(), kind="synthetic-fixture",
    )


EVIDENCE = (
    reference("pre", "2026-10-02T19:59:59Z"),
    reference("release", "2026-10-02T20:00:00Z"),
    reference("release-cutoff", "2026-10-02T20:05:00Z"),
    reference("post", "2026-10-05T20:00:00Z"),
)


def build(
    *, event: EarningsEvent = EVENT, cutoffs: PhaseCutoffs = CUTOFFS,
    versions: ManifestVersions = VERSIONS, evidence: tuple[EvidenceReference, ...] = EVIDENCE,
    required: dict[Phase, tuple[str, ...]] | None = None,
) -> tuple[PhaseManifest, ...]:
    return build_earnings_phase_manifest(
        event=event, cutoffs=cutoffs, versions=versions, evidence=evidence, now=NOW,
        required_evidence_refs=required,
    )


def test_same_day_release_filters_by_exact_time_inclusively() -> None:
    pre, release, post = build()
    assert [task.status for task in (pre, release, post)] == ["ready"] * 3
    assert [ref.id for ref in pre.evidence] == ["pre"]
    assert [ref.id for ref in release.evidence] == ["pre", "release", "release-cutoff"]
    assert {ref.id for ref in post.evidence} == {ref.id for ref in EVIDENCE}
    assert {ref.reason for ref in pre.excluded_evidence} == {"available_after_cutoff"}
    assert len({task.fingerprint for task in (pre, release, post)}) == 3
    assert all(task.mode == "historical_reconstruction" for task in (pre, release, post))
    assert all(task.execution_permitted is False for task in (pre, release, post))


@pytest.mark.parametrize("timestamp", [
    None, "2026-10-02", "2026-10-02T20:00:00", "2026-10-02T16:00:00-04:00",
    "2026-10-02T20:00Z", "not-a-time", "2026-02-31T20:00:00Z",
])
def test_unknown_or_imprecise_release_never_reconstructs_pre_earnings(
    timestamp: str | None,
) -> None:
    tasks = build(event=replace(EVENT, actual_release_at=timestamp))
    assert all(task.status == "blocked" for task in tasks)
    assert "actual_release_at_requires_exact_utc_timestamp" in tasks[0].reasons


@pytest.mark.parametrize("precision", ["date", "unknown", "estimated", "minute", ""])
def test_exact_looking_timestamp_does_not_override_release_precision(precision: str) -> None:
    tasks = build(event=replace(EVENT, release_time_precision=precision))
    assert all(task.status == "blocked" for task in tasks)
    assert "actual_release_time_precision_must_be_exact" in tasks[0].reasons


@pytest.mark.parametrize("timestamp", [
    None, "2026-10-02", "2026-10-02T18:00:00", "2026-10-02T18:00Z", "unknown",
])
def test_unknown_evidence_availability_is_excluded_and_explained(timestamp: str | None) -> None:
    tasks = build(evidence=(*EVIDENCE, reference("unknown", timestamp)))
    assert all(task.status == "ready" for task in tasks)
    for task in tasks:
        assert "unknown" not in {ref.id for ref in task.evidence}
        assert ("unknown", "unknown_or_non_exact_utc_available_at") in {
            (ref.id, ref.reason) for ref in task.excluded_evidence
        }


def test_required_references_cannot_bypass_cutoff_or_unknown_availability() -> None:
    tasks = build(
        evidence=(*EVIDENCE, reference("unknown", None)),
        required={
            "pre_earnings": ("release", "unknown", "missing"),
            "release": ("post",), "post_earnings_validation": ("post",),
        },
    )
    assert [task.status for task in tasks] == ["blocked", "blocked", "ready"]
    assert "required_evidence_not_available:release" in tasks[0].reasons
    assert "required_evidence_not_available:unknown" in tasks[0].reasons
    assert "required_evidence_not_available:missing" in tasks[0].reasons
    assert [ref.id for ref in tasks[0].evidence] == ["pre"]


@pytest.mark.parametrize(("field", "value", "reason"), [
    ("pre_earnings_at", EVENT.actual_release_at,
     "pre_earnings_cutoff_must_precede_actual_release"),
    ("release_at", CUTOFFS.pre_earnings_at,
     "release_cutoff_must_be_at_or_after_actual_release"),
    ("post_earnings_validation_at", CUTOFFS.release_at,
     "post_cutoff_must_follow_release_cutoff"),
    ("post_earnings_validation_at", "2026-10-05T20:00:01Z",
     "post_earnings_validation_cutoff_is_in_future"),
    ("release_at", "2026-10-06T20:00:00Z", "release_cutoff_is_in_future"),
    ("pre_earnings_at", "2026-10-06T20:00:00Z", "pre_earnings_cutoff_is_in_future"),
    ("pre_earnings_at", "2026-10-02", "pre_earnings_cutoff_requires_exact_utc_timestamp"),
    ("release_at", None, "release_cutoff_requires_exact_utc_timestamp"),
    ("post_earnings_validation_at", "2026-10-05",
     "post_earnings_validation_cutoff_requires_exact_utc_timestamp"),
])
def test_invalid_cutoffs_fail_closed(field: str, value: str | None, reason: str) -> None:
    tasks = build(cutoffs=replace(CUTOFFS, **{field: value}))
    assert all(task.status == "blocked" and reason in task.reasons for task in tasks)


def test_release_cutoff_may_equal_actual_release() -> None:
    tasks = build(cutoffs=replace(CUTOFFS, release_at=EVENT.actual_release_at))
    assert all(task.status == "ready" for task in tasks)
    assert {ref.id for ref in tasks[1].evidence} == {"pre", "release"}


@pytest.mark.parametrize("attestation", [False, None, "true", 1])
def test_post_requires_literal_true_trading_session_attestation(attestation: object) -> None:
    tasks = build(cutoffs=replace(CUTOFFS, post_session_verified=attestation))
    assert [task.status for task in tasks] == ["ready", "ready", "blocked"]
    assert "post_trading_session_not_explicitly_verified" in tasks[2].reasons


def test_builder_does_not_invent_post_trading_sessions() -> None:
    tasks = build(cutoffs=replace(
        CUTOFFS, post_earnings_validation_at="2026-10-03T20:00:00Z", post_session_verified=False,
    ))
    assert tasks[2].cutoff == "2026-10-03T20:00:00.000000Z"
    assert tasks[2].status == "blocked"


@pytest.mark.parametrize("field", ["model_version", "template_version", "factor_version"])
def test_version_change_creates_new_task_fingerprints(field: str) -> None:
    baseline = build()
    updated = build(versions=replace(VERSIONS, **{field: "v2"}))
    assert all(old.fingerprint != new.fingerprint for old, new in zip(baseline, updated, strict=True))


@pytest.mark.parametrize("field", ["issuer_id", "security_id", "event_id", "fiscal_period"])
def test_identity_is_not_ticker_only(field: str) -> None:
    baseline = build()
    updated = build(event=replace(EVENT, **{field: "different-identity"}))
    assert all(old.ticker == new.ticker for old, new in zip(baseline, updated, strict=True))
    assert all(old.fingerprint != new.fingerprint for old, new in zip(baseline, updated, strict=True))


def test_evidence_content_version_and_availability_changes_create_new_fingerprints() -> None:
    baseline = build()[0].fingerprint
    for changed in (
        replace(EVIDENCE[0], content_sha256="a" * 64),
        replace(EVIDENCE[0], version="v2"),
        replace(EVIDENCE[0], available_at="2026-10-02T19:59:58Z"),
    ):
        assert build(evidence=(changed, *EVIDENCE[1:]))[0].fingerprint != baseline


@pytest.mark.parametrize(("field", "value", "index"), [
    ("pre_earnings_at", "2026-10-02T19:59:58Z", 0),
    ("release_at", "2026-10-02T20:05:01Z", 1),
    ("post_earnings_validation_at", "2026-10-05T19:59:59Z", 2),
])
def test_cutoff_change_creates_new_fingerprint(field: str, value: str, index: int) -> None:
    old = build()[index]
    new = build(cutoffs=replace(CUTOFFS, **{field: value}))[index]
    assert old.fingerprint != new.fingerprint


def test_evidence_and_required_reference_order_do_not_change_fingerprints() -> None:
    old = build(required={"release": ("release", "pre")})
    new = build(evidence=tuple(reversed(EVIDENCE)), required={"release": ("pre", "release")})
    assert old == new


def test_unavailable_optional_evidence_does_not_change_pre_task_identity() -> None:
    original = build()[0]
    additional = build(evidence=(*EVIDENCE, reference("future", "2026-10-06T00:00:00Z")))[0]
    assert additional.fingerprint == original.fingerprint
    assert additional.evidence == original.evidence
    assert len(additional.excluded_evidence) == len(original.excluded_evidence) + 1


def test_equivalent_utc_representations_have_same_fingerprints() -> None:
    original = build()
    normalized = build(
        event=replace(EVENT, actual_release_at=datetime(2026, 10, 2, 20, tzinfo=UTC)),
        cutoffs=replace(CUTOFFS, release_at="2026-10-02T20:05:00+00:00"),
    )
    assert original == normalized


def test_duplicate_evidence_ids_fail_closed_instead_of_choosing_a_version() -> None:
    tasks = build(evidence=(*EVIDENCE, replace(EVIDENCE[0], version="v2")))
    assert all(task.status == "blocked" for task in tasks)
    assert all("duplicate_evidence_id:pre" in task.reasons for task in tasks)
    assert all("pre" not in {ref.id for ref in task.evidence} for task in tasks)


def test_empty_evidence_never_produces_a_ready_task() -> None:
    assert all("no_eligible_evidence" in task.reasons for task in build(evidence=()))


@pytest.mark.parametrize(("field", "value"), [
    ("version", ""), ("kind", ""), ("content_sha256", "not-a-content-hash"), ("id", ""),
])
def test_incomplete_evidence_is_not_frozen(field: str, value: str) -> None:
    tasks = build(evidence=(replace(EVIDENCE[0], **{field: value}),))
    assert all(task.status == "blocked" and not task.evidence for task in tasks)
    assert all(task.excluded_evidence for task in tasks)


def test_missing_issuer_or_version_blocks_task() -> None:
    assert all(task.status == "blocked" for task in build(event=replace(EVENT, issuer_id="")))
    assert all(task.status == "blocked" for task in build(versions=replace(VERSIONS, factor_version="")))


def test_naive_clock_fails_closed() -> None:
    tasks = build_earnings_phase_manifest(
        event=EVENT, cutoffs=CUTOFFS, versions=VERSIONS, evidence=EVIDENCE,
        now=NOW.replace(tzinfo=None),
    )
    assert all("now_requires_exact_utc_timestamp" in task.reasons for task in tasks)


def test_manifests_and_frozen_evidence_are_immutable() -> None:
    task = build()[0]
    with pytest.raises(FrozenInstanceError):
        task.fingerprint = "rewritten"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        task.evidence[0].content_sha256 = "rewritten"  # type: ignore[misc]
    assert isinstance(task.reasons, tuple)
    assert isinstance(task.evidence, tuple)


def test_input_list_mutation_does_not_change_existing_task() -> None:
    references = list(EVIDENCE)
    tasks = build_earnings_phase_manifest(
        event=EVENT, cutoffs=CUTOFFS, versions=VERSIONS, evidence=references, now=NOW,
    )
    references.clear()
    assert tasks == build()


def test_unknown_required_phase_is_not_silently_ignored() -> None:
    with pytest.raises(ValueError, match="unknown phase"):
        build(required={"typo_phase": ("pre",)})  # type: ignore[dict-item]
