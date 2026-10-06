"""Build offline, point-in-time earnings task manifests without executing research.

All identities, actual release times, trading-session cutoffs, and evidence
availability metadata must be supplied by the caller. This module does not load
configuration, inspect a database, guess a trading calendar, or contact a cloud.
``ready`` means only that these manifest checks pass; it is not permission to run
an existing research pipeline. Evidence hashes are caller-supplied SHA-256 values,
not independently verified document contents.

The only supported mode is ``historical_reconstruction``. A reconstructed pre-
earnings snapshot is NOT a prospectively recorded prediction or proof that a
model trained later has no future knowledge.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

Phase = Literal["pre_earnings", "release", "post_earnings_validation"]
Timestamp = str | datetime | None
PHASES: tuple[Phase, ...] = ("pre_earnings", "release", "post_earnings_validation")
MANIFEST_VERSION = "earnings-phase-manifest/v1"
_UTC_TIMESTAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)"
)
_SHA256 = re.compile(r"[0-9a-fA-F]{64}")


@dataclass(frozen=True)
class EarningsEvent:
    issuer_id: str
    security_id: str
    ticker: str
    exchange: str
    event_id: str
    fiscal_period: str
    actual_release_at: Timestamp
    release_time_precision: str


@dataclass(frozen=True)
class PhaseCutoffs:
    pre_earnings_at: Timestamp
    release_at: Timestamp
    post_earnings_validation_at: Timestamp
    # Caller attests that post cutoff is a verified trading-session observation.
    # This boolean does not verify an exchange calendar on its own.
    post_session_verified: bool


@dataclass(frozen=True)
class ManifestVersions:
    model_version: str
    template_version: str
    factor_version: str


@dataclass(frozen=True)
class EvidenceReference:
    id: str
    available_at: Timestamp
    version: str
    content_sha256: str
    kind: str


@dataclass(frozen=True)
class FrozenEvidence:
    id: str
    available_at: str
    version: str
    content_sha256: str
    kind: str


@dataclass(frozen=True)
class ExcludedEvidence:
    id: str
    reason: str


@dataclass(frozen=True)
class PhaseManifest:
    manifest_version: str
    mode: Literal["historical_reconstruction"]
    execution_permitted: Literal[False]
    issuer_id: str
    security_id: str
    ticker: str
    exchange: str
    event_id: str
    fiscal_period: str
    actual_release_at: str | None
    release_time_precision: str
    phase: Phase
    cutoff: str | None
    model_version: str
    template_version: str
    factor_version: str
    required_evidence_refs: tuple[str, ...]
    evidence: tuple[FrozenEvidence, ...]
    excluded_evidence: tuple[ExcludedEvidence, ...]
    post_session_verified: bool | None
    status: Literal["ready", "blocked"]
    reasons: tuple[str, ...]
    fingerprint: str


def _utc_timestamp(value: Timestamp) -> datetime | None:
    """Reject date-only, naive, non-UTC, and imprecise string timestamps."""
    if isinstance(value, str):
        if not _UTC_TIMESTAMP.fullmatch(value):
            return None
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        return None
    return value.astimezone(UTC)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _freeze_evidence(
    evidence: Sequence[EvidenceReference], cutoff: datetime | None, duplicate_ids: set[str],
) -> tuple[tuple[FrozenEvidence, ...], tuple[ExcludedEvidence, ...]]:
    eligible: list[FrozenEvidence] = []
    excluded: list[ExcludedEvidence] = []
    for ref in evidence:
        available_at = _utc_timestamp(ref.available_at)
        if not _nonempty(ref.id):
            reason = "invalid_evidence_id"
        elif ref.id in duplicate_ids:
            reason = "ambiguous_duplicate_evidence_id"
        elif available_at is None:
            reason = "unknown_or_non_exact_utc_available_at"
        elif cutoff is None:
            reason = "invalid_phase_cutoff"
        elif available_at > cutoff:
            reason = "available_after_cutoff"
        elif not _nonempty(ref.version) or not _nonempty(ref.kind):
            reason = "missing_evidence_version_or_kind"
        elif not isinstance(ref.content_sha256, str) or not _SHA256.fullmatch(ref.content_sha256):
            reason = "invalid_evidence_content_sha256"
        else:
            stamp = _iso(available_at)
            assert stamp is not None
            eligible.append(FrozenEvidence(
                id=ref.id, available_at=stamp, version=ref.version,
                content_sha256=ref.content_sha256.lower(), kind=ref.kind,
            ))
            continue
        excluded.append(ExcludedEvidence(id=str(ref.id), reason=reason))
    return (
        tuple(sorted(eligible, key=lambda ref: ref.id)),
        tuple(sorted(excluded, key=lambda ref: (ref.id, ref.reason))),
    )


def build_earnings_phase_manifest(
    *,
    event: EarningsEvent,
    cutoffs: PhaseCutoffs,
    versions: ManifestVersions,
    evidence: Sequence[EvidenceReference],
    now: Timestamp,
    required_evidence_refs: Mapping[Phase, Sequence[str]] | None = None,
) -> tuple[PhaseManifest, ...]:
    """Return three immutable manifests, never dispatch jobs or fetch evidence.

    ``now`` is explicit for reproducible offline validation. Callers must supply a
    trusted current UTC clock, not an invented future validation date. Timestamp
    strings require seconds and ``Z`` or ``+00:00``; aware zero-offset datetimes
    are also accepted. ``release_time_precision`` must be exactly ``"exact"``.
    No source publication date or event date is promoted to an availability time.

    Invalid event/cutoff relationships block the complete three-stage request.
    Missing post-session attestation blocks post validation only. Missing required
    evidence blocks its own phase; references never override temporal filtering.
    Evidence IDs must identify unique immutable versions; duplicate IDs block all
    phases rather than choosing an arbitrary version. Unknown optional evidence
    is excluded with a reason. At least one eligible evidence item is required.

    Fingerprints cover issuer AND security AND earnings-event identity, canonical
    timestamps, phase, versioned model/template/factor pack, required references,
    frozen evidence metadata/hashes, and validation gates. Optional evidence that
    is unavailable at a cutoff does not change that phase's task fingerprint.
    ``now`` is not an input to task identity once the same validation gates pass.
    """
    required = {} if required_evidence_refs is None else required_evidence_refs
    if set(required) - set(PHASES):
        raise ValueError("required_evidence_refs contains an unknown phase")
    for refs in required.values():
        if isinstance(refs, (str, bytes)) or any(not _nonempty(ref) for ref in refs):
            raise ValueError("required evidence references must be sequences of nonempty IDs")

    common_reasons: list[str] = []
    identity = {
        "issuer_id": event.issuer_id,
        "security_id": event.security_id,
        "ticker": event.ticker,
        "exchange": event.exchange,
        "event_id": event.event_id,
        "fiscal_period": event.fiscal_period,
        "model_version": versions.model_version,
        "template_version": versions.template_version,
        "factor_version": versions.factor_version,
    }
    for field, value in identity.items():
        if not _nonempty(value):
            common_reasons.append(f"missing_or_invalid_{field}")

    release = _utc_timestamp(event.actual_release_at)
    clock = _utc_timestamp(now)
    parsed_cutoffs = {
        "pre_earnings": _utc_timestamp(cutoffs.pre_earnings_at),
        "release": _utc_timestamp(cutoffs.release_at),
        "post_earnings_validation": _utc_timestamp(cutoffs.post_earnings_validation_at),
    }
    if event.release_time_precision != "exact":
        common_reasons.append("actual_release_time_precision_must_be_exact")
    if release is None:
        common_reasons.append("actual_release_at_requires_exact_utc_timestamp")
    if clock is None:
        common_reasons.append("now_requires_exact_utc_timestamp")
    for phase, cutoff in parsed_cutoffs.items():
        if cutoff is None:
            common_reasons.append(f"{phase}_cutoff_requires_exact_utc_timestamp")
        elif clock is not None and cutoff > clock:
            common_reasons.append(f"{phase}_cutoff_is_in_future")
    pre, at_release, post = (parsed_cutoffs[phase] for phase in PHASES)
    if release is not None and pre is not None and pre >= release:
        common_reasons.append("pre_earnings_cutoff_must_precede_actual_release")
    if release is not None and at_release is not None and at_release < release:
        common_reasons.append("release_cutoff_must_be_at_or_after_actual_release")
    if at_release is not None and post is not None and post <= at_release:
        common_reasons.append("post_cutoff_must_follow_release_cutoff")

    # Take one copy; caller mutations of an input list cannot alter returned tasks.
    references = tuple(evidence)
    if any(not isinstance(ref, EvidenceReference) for ref in references):
        raise TypeError("evidence must contain EvidenceReference values")
    counts = Counter(ref.id for ref in references if isinstance(ref.id, str))
    duplicates = {id_ for id_, count in counts.items() if count > 1}
    common_reasons.extend(f"duplicate_evidence_id:{id_}" for id_ in sorted(duplicates))

    manifests: list[PhaseManifest] = []
    for phase in PHASES:
        cutoff = parsed_cutoffs[phase]
        frozen, excluded = _freeze_evidence(references, cutoff, duplicates)
        phase_required = tuple(sorted(set(required.get(phase, ()))))
        eligible_ids = {ref.id for ref in frozen}
        reasons = list(common_reasons)
        if not frozen:
            reasons.append("no_eligible_evidence")
        reasons.extend(
            f"required_evidence_not_available:{ref_id}"
            for ref_id in phase_required if ref_id not in eligible_ids
        )
        session_verified = None
        if phase == "post_earnings_validation":
            session_verified = cutoffs.post_session_verified is True
            if not session_verified:
                reasons.append("post_trading_session_not_explicitly_verified")
        blocked_reasons = tuple(sorted(set(reasons)))
        status: Literal["ready", "blocked"] = "blocked" if blocked_reasons else "ready"
        payload = {
            "manifest_version": MANIFEST_VERSION,
            "mode": "historical_reconstruction",
            "execution_permitted": False,
            **identity,
            "actual_release_at": _iso(release),
            "release_time_precision": event.release_time_precision,
            "phase": phase,
            "cutoff": _iso(cutoff),
            "required_evidence_refs": phase_required,
            "evidence": [asdict(ref) for ref in frozen],
            "post_session_verified": session_verified,
            "status": status,
            "reasons": blocked_reasons,
        }
        digest = hashlib.sha256(json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("utf-8")).hexdigest()
        manifests.append(PhaseManifest(
            manifest_version=MANIFEST_VERSION, mode="historical_reconstruction",
            execution_permitted=False, issuer_id=event.issuer_id,
            security_id=event.security_id, ticker=event.ticker, exchange=event.exchange,
            event_id=event.event_id, fiscal_period=event.fiscal_period,
            actual_release_at=_iso(release), release_time_precision=event.release_time_precision,
            phase=phase, cutoff=_iso(cutoff), model_version=versions.model_version,
            template_version=versions.template_version, factor_version=versions.factor_version,
            required_evidence_refs=phase_required, evidence=frozen, excluded_evidence=excluded,
            post_session_verified=session_verified, status=status, reasons=blocked_reasons,
            fingerprint=f"sha256:{digest}",
        ))
    return tuple(manifests)
