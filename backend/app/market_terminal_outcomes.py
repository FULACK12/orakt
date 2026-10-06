"""Audited lifecycle corrections and multi-stage shareholder terminal cashflows."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    MarketAssetLifecycle,
    MarketDelistingEvidenceCandidate,
    MarketDelistingOutcome,
    MarketLifecycleResolution,
    MarketTerminalCashflow,
)
from app.market_identity import verify_delisting_outcome

LIFECYCLE_RESOLUTION_TYPES = {
    "provider_conflict_active",
    "adr_program_terminated",
    "bankruptcy_pending",
    "liquidation_pending",
    "verified_delisted",
}
AUTHORITATIVE_STATUSES = {"active", "delisted", "bankruptcy", "liquidation"}
CASHFLOW_TYPES = {
    "liquidation_distribution",
    "bankruptcy_recovery",
    "adr_cash_distribution",
    "stock_distribution_cash_value",
    "other_terminal_distribution",
}
MULTI_STAGE_OUTCOME_TYPES = {
    "liquidation_distribution",
    "bankruptcy_worthless",
    "cash_and_stock",
}


def record_lifecycle_resolution(
    session: Session,
    *,
    asset_key: str,
    resolution_type: str,
    authoritative_status: str,
    authoritative_delisting_date: date | None,
    evidence_url: str,
    evidence_note: str,
    now: datetime | None = None,
) -> MarketLifecycleResolution:
    """Layer an authoritative review over provider lifecycle metadata."""
    lifecycle = session.get(MarketAssetLifecycle, asset_key)
    if lifecycle is None:
        raise ValueError("historical asset was not found")
    if resolution_type not in LIFECYCLE_RESOLUTION_TYPES:
        raise ValueError("unsupported lifecycle resolution type")
    if authoritative_status not in AUTHORITATIVE_STATUSES:
        raise ValueError("unsupported authoritative lifecycle status")
    if resolution_type == "provider_conflict_active":
        if authoritative_status != "active" or authoritative_delisting_date is not None:
            raise ValueError("active provider conflicts cannot have a delisting date")
    elif authoritative_delisting_date is None:
        raise ValueError("a reviewed non-active lifecycle requires a delisting date")
    if len(evidence_note.strip()) < 20:
        raise ValueError("lifecycle evidence note is too short")
    normalized_url = evidence_url.strip()
    if not normalized_url.startswith("https://"):
        raise ValueError("lifecycle evidence must cite an HTTPS primary source")
    reviewed_at = now or datetime.now(UTC)
    identity_material = "|".join(
        (
            asset_key,
            resolution_type,
            authoritative_status,
            authoritative_delisting_date.isoformat()
            if authoritative_delisting_date
            else "active",
            normalized_url,
            evidence_note.strip(),
        )
    )
    resolution = session.get(MarketLifecycleResolution, asset_key)
    if resolution is None:
        resolution = MarketLifecycleResolution(
            asset_key=asset_key,
            resolution_type=resolution_type,
            authoritative_status=authoritative_status,
            evidence_url=normalized_url,
            evidence_note=evidence_note.strip()[:2_000],
            evidence_hash=hashlib.sha256(identity_material.encode()).hexdigest(),
            reviewed_at=reviewed_at,
        )
        session.add(resolution)
    else:
        resolution.resolution_type = resolution_type
        resolution.authoritative_status = authoritative_status
        resolution.evidence_url = normalized_url
        resolution.evidence_note = evidence_note.strip()[:2_000]
        resolution.evidence_hash = hashlib.sha256(identity_material.encode()).hexdigest()
        resolution.reviewed_at = reviewed_at
    resolution.authoritative_delisting_date = authoritative_delisting_date
    session.flush()
    return resolution


def record_terminal_cashflow(
    session: Session,
    *,
    asset_key: str,
    evidence_key: str,
    cashflow_type: str,
    amount_per_share: float,
    payment_date: date,
    status: str,
    is_final: bool,
    evidence_note: str,
    now: datetime | None = None,
) -> MarketTerminalCashflow:
    """Store one reviewed distribution without prematurely finalizing an outcome."""
    if cashflow_type not in CASHFLOW_TYPES:
        raise ValueError("unsupported terminal cashflow type")
    if status not in {"confirmed", "estimated"}:
        raise ValueError("terminal cashflow status must be confirmed or estimated")
    if amount_per_share < 0:
        raise ValueError("terminal cashflow amount cannot be negative")
    if len(evidence_note.strip()) < 20:
        raise ValueError("terminal cashflow evidence note is too short")
    candidate = session.get(MarketDelistingEvidenceCandidate, evidence_key)
    if candidate is None or candidate.asset_key != asset_key:
        raise ValueError("reviewed terminal cashflow evidence was not found for asset")
    expected_role = "terminal_outcome" if status == "confirmed" else "supporting_evidence"
    if candidate.review_status != "accepted" or candidate.review_role != expected_role:
        raise ValueError(f"{status} cashflow requires accepted {expected_role} evidence")
    if candidate.value_unit != "USD_per_share":
        raise ValueError("terminal cashflow evidence must use USD_per_share")
    value_mismatch = (
        candidate.candidate_value is None
        or abs(candidate.candidate_value - amount_per_share) > 1e-9
    )
    if value_mismatch:
        raise ValueError("cashflow amount does not match reviewed evidence")
    if is_final and status != "confirmed":
        raise ValueError("an estimated cashflow cannot be marked final")
    identity_material = "|".join(
        (
            asset_key,
            evidence_key,
            cashflow_type,
            f"{amount_per_share:.12g}",
            payment_date.isoformat(),
        )
    )
    cashflow_key = hashlib.sha256(identity_material.encode()).hexdigest()
    existing = session.get(MarketTerminalCashflow, cashflow_key)
    if existing is not None:
        return existing
    sequence = int(
        session.scalar(
            select(func.max(MarketTerminalCashflow.sequence)).where(
                MarketTerminalCashflow.asset_key == asset_key
            )
        )
        or 0
    ) + 1
    reviewed_at = now or datetime.now(UTC)
    cashflow = MarketTerminalCashflow(
        cashflow_key=cashflow_key,
        asset_key=asset_key,
        evidence_key=evidence_key,
        sequence=sequence,
        cashflow_type=cashflow_type,
        amount_per_share=amount_per_share,
        payment_date=payment_date,
        status=status,
        is_final=is_final,
        evidence_url=candidate.source_url,
        evidence_note=evidence_note.strip()[:2_000],
        evidence_hash=hashlib.sha256(
            f"{identity_material}|{candidate.source_url}|{evidence_note.strip()}".encode()
        ).hexdigest(),
        reviewed_at=reviewed_at,
    )
    session.add(cashflow)
    session.flush()
    return cashflow


def finalize_multi_stage_outcome(
    session: Session,
    *,
    asset_key: str,
    outcome_type: str,
    evidence_note: str,
    now: datetime | None = None,
) -> MarketDelistingOutcome:
    """Admit a terminal return only after all confirmed stages include a final one."""
    if outcome_type not in MULTI_STAGE_OUTCOME_TYPES:
        raise ValueError("unsupported multi-stage outcome type")
    resolution = session.get(MarketLifecycleResolution, asset_key)
    if resolution is None or resolution.resolution_type not in {
        "bankruptcy_pending",
        "liquidation_pending",
        "verified_delisted",
    }:
        raise ValueError("a compatible reviewed lifecycle resolution is required")
    cashflows = list(
        session.scalars(
            select(MarketTerminalCashflow)
            .where(MarketTerminalCashflow.asset_key == asset_key)
            .order_by(MarketTerminalCashflow.payment_date, MarketTerminalCashflow.sequence)
        )
    )
    if not cashflows:
        raise ValueError("at least one reviewed terminal cashflow is required")
    if any(cashflow.status != "confirmed" for cashflow in cashflows):
        raise ValueError("estimated cashflows must be resolved before finalization")
    if not any(cashflow.is_final for cashflow in cashflows):
        raise ValueError("the final shareholder distribution has not been confirmed")
    if any(cashflow.is_final for cashflow in cashflows[:-1]):
        raise ValueError("only the last chronological cashflow may be marked final")
    if outcome_type == "bankruptcy_worthless" and any(
        cashflow.amount_per_share != 0 for cashflow in cashflows
    ):
        raise ValueError("bankruptcy_worthless cannot contain a positive recovery")
    total_value = sum(cashflow.amount_per_share for cashflow in cashflows)
    last_cashflow = cashflows[-1]
    outcome = verify_delisting_outcome(
        session,
        asset_key=asset_key,
        outcome_type=outcome_type,
        terminal_value_per_share=total_value,
        payment_date=last_cashflow.payment_date,
        evidence_url=last_cashflow.evidence_url,
        evidence_note=evidence_note,
        evidence_key=last_cashflow.evidence_key,
        now=now,
    )
    outcome.resolution_method = "reviewed_multi_stage_cashflow_v1"
    outcome.cashflow_count = len(cashflows)
    outcome.terminal_is_final = True
    resolution.resolution_type = {
        "bankruptcy_worthless": "bankruptcy_final",
        "liquidation_distribution": "liquidation_final",
        "cash_and_stock": "verified_delisted",
    }[outcome_type]
    session.flush()
    return outcome
