"""Cross-source identity gates and audited post-delisting shareholder values."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    CompanyProfile,
    MarketAssetIdentifier,
    MarketAssetLifecycle,
    MarketDelistingEvidenceCandidate,
    MarketDelistingEvidenceState,
    MarketDelistingOutcome,
    MarketLifecycleResolution,
    MarketObservation,
    MarketPriceBackfillState,
    MarketSeries,
)
from app.storage.archive import ArchiveCapacityError, ColdArchive

OPENFIGI_MAPPING_URL = "https://api.openfigi.com/v3/mapping"
OPENFIGI_SOURCE_URL = "https://www.openfigi.com/api/documentation"
IDENTITY_RETRY_DAYS = 30
OPENFIGI_UNAUTHENTICATED_JOBS_PER_REQUEST = 5

LEGAL_NAME_TOKENS = {
    "adr",
    "ads",
    "co",
    "company",
    "corp",
    "corporation",
    "inc",
    "incorporated",
    "ltd",
    "limited",
    "ordinary",
    "plc",
    "spon",
    "sponsored",
    "the",
}
US_EXCHANGES = {"NASDAQ", "NYSE", "NYSE ARCA", "NYSEAMERICAN", "AMEX"}
ACCEPTED_OUTCOME_TYPES = {
    "cash_acquisition",
    "stock_acquisition",
    "cash_and_stock",
    "liquidation_distribution",
    "bankruptcy_worthless",
    "continued_trading",
}


class OpenFigiError(RuntimeError):
    """Sanitized identity-provider failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class MarketIdentitySyncResult(BaseModel):
    """Safe counters for one identity-resolution pass."""

    model_config = ConfigDict(extra="forbid")

    attempted_assets: int = Field(ge=0)
    verified_assets: int = Field(ge=0)
    unresolved_assets: int = Field(ge=0)
    ambiguous_assets: int = Field(ge=0)
    mismatched_assets: int = Field(ge=0)
    sec_cik_assets: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list, max_length=20)


@dataclass(frozen=True)
class IdentitySelection:
    status: str
    method: str | None
    candidate: dict[str, Any] | None
    name_similarity: float | None


async def sync_openfigi_identities(
    session: Session,
    *,
    client: httpx.AsyncClient,
    archive: ColdArchive,
    api_key: str | None = None,
    max_assets: int = 10,
    now: datetime | None = None,
) -> MarketIdentitySyncResult:
    """Resolve a bounded set of priced historical assets to stable FIGI identifiers."""
    generated_at = now or datetime.now(UTC)
    _revalidate_stored_identity_matches(session, generated_at=generated_at)
    retry_before = generated_at - timedelta(days=IDENTITY_RETRY_DAYS)
    eligible = list(
        session.execute(
            select(MarketAssetLifecycle, MarketPriceBackfillState, MarketAssetIdentifier)
            .join(
                MarketPriceBackfillState,
                MarketPriceBackfillState.asset_key == MarketAssetLifecycle.asset_key,
            )
            .outerjoin(
                MarketAssetIdentifier,
                MarketAssetIdentifier.asset_key == MarketAssetLifecycle.asset_key,
            )
            .where(
                MarketPriceBackfillState.status.in_(("synced", "partial")),
                (
                    MarketAssetIdentifier.asset_key.is_(None)
                    | (
                        MarketAssetIdentifier.identity_status.in_(
                            ("unresolved", "ambiguous", "failed")
                        )
                        & (
                            MarketAssetIdentifier.last_attempt_at.is_(None)
                            | (MarketAssetIdentifier.last_attempt_at < retry_before)
                        )
                    )
                ),
            )
            .order_by(MarketPriceBackfillState.priority_score.desc())
            .limit(max_assets)
        )
    )
    if not eligible:
        session.flush()
        materialize_delisting_outcomes(session)
        return MarketIdentitySyncResult(
            attempted_assets=0,
            verified_assets=0,
            unresolved_assets=0,
            ambiguous_assets=0,
            mismatched_assets=0,
            sec_cik_assets=0,
        )

    lifecycles = [row[0] for row in eligible]
    raw_by_asset: dict[str, str] = {}
    candidates_by_asset: dict[str, list[dict[str, Any]]] = {
        lifecycle.asset_key: [] for lifecycle in lifecycles
    }
    errors: list[str] = []
    request_size = 100 if api_key else OPENFIGI_UNAUTHENTICATED_JOBS_PER_REQUEST
    for start in range(0, len(lifecycles), request_size):
        batch = lifecycles[start : start + request_size]
        try:
            payloads = await _fetch_openfigi_batch(
                client,
                lifecycles=batch,
                api_key=api_key,
            )
            archive_path = _archive_openfigi_payload(
                archive,
                lifecycles=batch,
                fetched_on=generated_at.date(),
                payload=payloads["raw"],
            )
            for lifecycle, candidates in zip(
                batch,
                payloads["candidates"],
                strict=True,
            ):
                candidates_by_asset[lifecycle.asset_key].extend(candidates)
                raw_by_asset[lifecycle.asset_key] = archive_path
        except OpenFigiError as exc:
            for lifecycle in batch:
                errors.append(f"{lifecycle.symbol}: {exc.code}")
                _record_identity_error(
                    session,
                    lifecycle=lifecycle,
                    generated_at=generated_at,
                    code=exc.code,
                    message=str(exc),
                )
        except (ArchiveCapacityError, OSError):
            for lifecycle in batch:
                errors.append(f"{lifecycle.symbol}: cold_archive_unavailable")
                _record_identity_error(
                    session,
                    lifecycle=lifecycle,
                    generated_at=generated_at,
                    code="cold_archive_unavailable",
                    message="identity response could not be archived",
                )

    verified = unresolved = ambiguous = mismatched = sec_cik_assets = 0
    failed_assets = {item.split(":", 1)[0] for item in errors}
    for lifecycle in lifecycles:
        if lifecycle.symbol in failed_assets:
            continue
        selection = select_openfigi_identity(
            lifecycle,
            candidates_by_asset[lifecycle.asset_key],
        )
        state = session.get(MarketAssetIdentifier, lifecycle.asset_key)
        if state is None:
            state = MarketAssetIdentifier(
                asset_key=lifecycle.asset_key,
                identity_status=selection.status,
                attempt_count=0,
            )
            session.add(state)
        state.identity_status = selection.status
        state.mapping_method = selection.method
        state.name_similarity = selection.name_similarity
        state.attempt_count += 1
        state.last_attempt_at = generated_at
        state.last_error_code = None
        state.last_error_message = None
        state.raw_archive_path = raw_by_asset.get(lifecycle.asset_key)
        candidate = selection.candidate or {}
        state.figi = _optional_text(candidate.get("figi"), 32)
        state.composite_figi = _optional_text(candidate.get("compositeFIGI"), 32)
        state.share_class_figi = _optional_text(candidate.get("shareClassFIGI"), 32)
        state.mapped_ticker = _optional_text(candidate.get("ticker"), 64)
        state.mapped_name = _optional_text(candidate.get("name"), 255)
        state.mapped_exchange = _optional_text(candidate.get("exchCode"), 64)
        state.security_type = _optional_text(candidate.get("securityType2"), 64)
        state.sec_cik = _match_local_sec_cik(session, lifecycle, selection)
        if selection.status == "verified":
            state.last_success_at = generated_at
            verified += 1
            sec_cik_assets += int(state.sec_cik is not None)
        elif selection.status == "mismatch":
            mismatched += 1
        elif selection.status == "ambiguous":
            ambiguous += 1
        else:
            unresolved += 1

    session.flush()
    materialize_delisting_outcomes(session)
    session.flush()
    return MarketIdentitySyncResult(
        attempted_assets=len(lifecycles),
        verified_assets=verified,
        unresolved_assets=unresolved,
        ambiguous_assets=ambiguous,
        mismatched_assets=mismatched,
        sec_cik_assets=sec_cik_assets,
        errors=errors[:20],
    )


async def _fetch_openfigi_batch(
    client: httpx.AsyncClient,
    *,
    lifecycles: list[MarketAssetLifecycle],
    api_key: str | None,
) -> dict[str, Any]:
    combined: list[list[dict[str, Any]]] = [[] for _ in lifecycles]
    raw_responses: dict[str, Any] = {}
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-OPENFIGI-APIKEY"] = api_key
    for security_type in ("Common Stock", "Depositary Receipt"):
        jobs = [
            {
                "idType": "BASE_TICKER",
                "idValue": lifecycle.symbol,
                "marketSecDes": "Equity",
                "securityType2": security_type,
                "includeUnlistedEquities": True,
            }
            for lifecycle in lifecycles
        ]
        try:
            response = await client.post(
                OPENFIGI_MAPPING_URL,
                headers=headers,
                json=jobs,
            )
        except httpx.HTTPError as exc:
            raise OpenFigiError(
                "provider_http",
                f"OpenFIGI mapping request failed ({type(exc).__name__})",
            ) from None
        if response.status_code == 429:
            raise OpenFigiError("rate_limited", "OpenFIGI request limit reached")
        if response.status_code != 200:
            raise OpenFigiError(
                "provider_http",
                f"OpenFIGI mapping returned HTTP {response.status_code}",
            )
        try:
            payload = response.json()
        except json.JSONDecodeError:
            raise OpenFigiError("invalid_json", "OpenFIGI returned invalid JSON") from None
        if not isinstance(payload, list) or len(payload) != len(lifecycles):
            raise OpenFigiError("invalid_shape", "OpenFIGI response did not match request order")
        raw_responses[security_type] = payload
        for index, item in enumerate(payload):
            if isinstance(item, dict) and isinstance(item.get("data"), list):
                combined[index].extend(
                    candidate for candidate in item["data"] if isinstance(candidate, dict)
                )
    raw = json.dumps(raw_responses, ensure_ascii=False, separators=(",", ":")).encode()
    return {"candidates": combined, "raw": raw}


def select_openfigi_identity(
    lifecycle: MarketAssetLifecycle,
    candidates: list[dict[str, Any]],
) -> IdentitySelection:
    """Choose only a name-consistent security, never ticker-only first-match output."""
    scored: list[tuple[float, float, dict[str, Any]]] = []
    for candidate in candidates:
        name = str(candidate.get("name") or "")
        ticker = str(candidate.get("ticker") or "").upper()
        if not name or ticker != lifecycle.symbol.upper():
            continue
        similarity = _name_similarity(lifecycle.name, name)
        exchange = str(candidate.get("exchCode") or "").upper()
        security_type = str(candidate.get("securityType2") or "")
        score = similarity * 100
        score += 18 if exchange == "US" else 0
        score += 4 if security_type in {"Common Stock", "Depositary Receipt"} else 0
        scored.append((score, similarity, candidate))
    if not scored:
        return IdentitySelection("unresolved", None, None, None)
    scored.sort(key=lambda item: item[0], reverse=True)
    _, similarity, candidate = scored[0]
    us_required = lifecycle.exchange.upper() in US_EXCHANGES
    exchange_ok = not us_required or str(candidate.get("exchCode") or "").upper() == "US"
    if similarity >= 0.82 and exchange_ok:
        return IdentitySelection(
            "verified",
            "openfigi_base_ticker_name_exchange",
            candidate,
            similarity,
        )
    if similarity < 0.45:
        return IdentitySelection("mismatch", "openfigi_name_rejected", candidate, similarity)
    return IdentitySelection("ambiguous", "openfigi_manual_review", candidate, similarity)


def materialize_delisting_outcomes(session: Session) -> int:
    """Create terminal-value audit rows without inventing missing shareholder value."""
    rows = list(
        session.execute(
            select(MarketPriceBackfillState, MarketAssetIdentifier)
            .outerjoin(
                MarketAssetIdentifier,
                MarketAssetIdentifier.asset_key == MarketPriceBackfillState.asset_key,
            )
            .where(
                MarketPriceBackfillState.series_id.is_not(None),
                MarketPriceBackfillState.status.in_(("synced", "partial")),
            )
        )
    )
    created = 0
    for price_state, identity in rows:
        outcome = session.get(MarketDelistingOutcome, price_state.asset_key)
        latest = session.execute(
            select(MarketObservation.observed_on, MarketObservation.value)
            .where(MarketObservation.series_id == price_state.series_id)
            .order_by(MarketObservation.observed_on.desc())
            .limit(1)
        ).one_or_none()
        if outcome is None:
            outcome = MarketDelistingOutcome(
                asset_key=price_state.asset_key,
                series_id=price_state.series_id,
                status="evidence_required",
                outcome_type="unknown",
            )
            session.add(outcome)
            created += 1
        if outcome.status != "verified":
            outcome.series_id = price_state.series_id
            outcome.status = (
                "evidence_required"
                if identity is not None and identity.identity_status == "verified"
                else "identity_required"
            )
            if latest is not None:
                outcome.last_trade_date = latest[0]
                outcome.last_trade_price = float(latest[1])
    session.flush()
    return created


def verify_delisting_outcome(
    session: Session,
    *,
    asset_key: str,
    outcome_type: str,
    terminal_value_per_share: float | None,
    payment_date: date,
    evidence_url: str,
    evidence_note: str,
    evidence_key: str | None = None,
    now: datetime | None = None,
) -> MarketDelistingOutcome:
    """Calculate a final return only from an identity-verified, evidenced terminal value."""
    if outcome_type not in ACCEPTED_OUTCOME_TYPES:
        raise ValueError("unsupported delisting outcome type")
    identity = session.get(MarketAssetIdentifier, asset_key)
    if identity is None or identity.identity_status != "verified":
        raise ValueError("cross-source security identity must be verified first")
    outcome = session.get(MarketDelistingOutcome, asset_key)
    if outcome is None or outcome.series_id is None:
        raise ValueError("historical price series is not ready")
    if outcome.last_trade_date is None or outcome.last_trade_price is None:
        raise ValueError("last trading price is unavailable")
    if outcome.last_trade_price <= 0:
        raise ValueError("last trading price must be positive")
    if payment_date < outcome.last_trade_date:
        raise ValueError("payment date cannot precede the last trading date")
    terminal_value = 0.0 if outcome_type == "bankruptcy_worthless" else terminal_value_per_share
    if terminal_value is None or terminal_value < 0:
        raise ValueError("a non-negative terminal value per share is required")
    delisting_return = terminal_value / outcome.last_trade_price - 1.0
    if not -1.0 <= delisting_return <= 10.0:
        raise ValueError("derived delisting return is outside the accepted audit range")
    verified_at = now or datetime.now(UTC)
    evidence_identity = "|".join(
        (
            asset_key,
            outcome_type,
            f"{terminal_value:.12g}",
            payment_date.isoformat(),
            evidence_url.strip(),
            evidence_note.strip(),
        )
    )
    outcome.status = "verified"
    outcome.outcome_type = outcome_type
    outcome.terminal_value_per_share = terminal_value
    outcome.payment_date = payment_date
    outcome.delisting_return = delisting_return
    outcome.evidence_url = evidence_url.strip()
    outcome.evidence_key = evidence_key
    outcome.evidence_note = evidence_note.strip()[:2_000]
    outcome.evidence_hash = hashlib.sha256(evidence_identity.encode()).hexdigest()
    outcome.verification_method = "human_reviewed_primary_source"
    outcome.resolution_method = "single_terminal_value_v1"
    outcome.cashflow_count = 1
    outcome.terminal_is_final = True
    outcome.verified_at = verified_at
    series = session.get(MarketSeries, outcome.series_id)
    if series is None:
        raise ValueError("historical price series metadata is unavailable")
    series.delisting_return = delisting_return
    session.flush()
    return outcome


def verify_stock_delisting_outcome(
    session: Session,
    *,
    asset_key: str,
    exchange_ratio_evidence_key: str,
    valuation_evidence_key: str,
    acquirer_symbol: str,
    payment_date: date,
    evidence_note: str,
    now: datetime | None = None,
) -> MarketDelistingOutcome:
    """Value a fixed-ratio stock merger from two separately reviewed SEC facts."""
    ratio = session.get(MarketDelistingEvidenceCandidate, exchange_ratio_evidence_key)
    valuation = session.get(MarketDelistingEvidenceCandidate, valuation_evidence_key)
    if ratio is None or ratio.asset_key != asset_key:
        raise ValueError("reviewed exchange-ratio evidence was not found for asset")
    if (
        ratio.review_status != "accepted"
        or ratio.review_role != "terminal_outcome"
        or ratio.evidence_type != "share_exchange_ratio"
        or ratio.value_unit != "acquirer_shares_per_share"
        or ratio.candidate_value is None
    ):
        raise ValueError("exchange ratio is not accepted terminal evidence")
    if valuation is None or valuation.asset_key != asset_key:
        raise ValueError("reviewed acquirer-price evidence was not found for asset")
    if (
        valuation.review_status != "accepted"
        or valuation.review_role != "supporting_evidence"
        or valuation.evidence_type != "acquirer_closing_price"
        or valuation.value_unit != "USD_per_acquirer_share"
        or valuation.candidate_value is None
        or valuation.observed_on is None
    ):
        raise ValueError("acquirer closing price is not accepted supporting evidence")
    normalized_symbol = acquirer_symbol.strip().upper()
    if not normalized_symbol or valuation.subject_symbol != normalized_symbol:
        raise ValueError("acquirer symbol does not match valuation evidence")
    if payment_date != valuation.observed_on:
        raise ValueError("payment date must match the cited acquirer price observation")
    if ratio.filed_on > payment_date:
        raise ValueError("exchange-ratio evidence was filed after the payment date")
    terminal_value = float(ratio.candidate_value) * float(valuation.candidate_value)
    outcome = verify_delisting_outcome(
        session,
        asset_key=asset_key,
        outcome_type="stock_acquisition",
        terminal_value_per_share=terminal_value,
        payment_date=payment_date,
        evidence_url=ratio.source_url,
        evidence_note=evidence_note,
        evidence_key=ratio.evidence_key,
        now=now,
    )
    outcome.valuation_evidence_key = valuation.evidence_key
    outcome.exchange_ratio = float(ratio.candidate_value)
    outcome.acquirer_symbol = normalized_symbol
    outcome.acquirer_price_on_payment = float(valuation.candidate_value)
    outcome.acquirer_price_observed_on = valuation.observed_on
    outcome.verification_method = "human_reviewed_sec_exchange_ratio_and_closing_price"
    session.flush()
    return outcome


def market_identity_coverage(session: Session) -> dict[str, Any]:
    """Return cross-source identity and terminal-outcome coverage counts."""
    identity_rows = list(
        session.execute(
            select(MarketAssetIdentifier.identity_status, func.count())
            .group_by(MarketAssetIdentifier.identity_status)
        )
    )
    outcome_rows = list(
        session.execute(
            select(MarketDelistingOutcome.status, func.count())
            .group_by(MarketDelistingOutcome.status)
        )
    )
    identity_counts = {str(status): int(count) for status, count in identity_rows}
    outcome_counts = {str(status): int(count) for status, count in outcome_rows}
    sec_cik_assets = int(
        session.scalar(
            select(func.count())
            .select_from(MarketAssetIdentifier)
            .where(MarketAssetIdentifier.sec_cik.is_not(None))
        )
        or 0
    )
    return {
        "identity_status_counts": identity_counts,
        "outcome_status_counts": outcome_counts,
        "verified_identity_assets": identity_counts.get("verified", 0),
        "unresolved_identity_assets": identity_counts.get("unresolved", 0),
        "ambiguous_identity_assets": identity_counts.get("ambiguous", 0),
        "mismatched_identity_assets": identity_counts.get("mismatch", 0),
        "lifecycle_conflict_identity_assets": identity_counts.get(
            "lifecycle_conflict", 0
        ),
        "sec_cik_assets": sec_cik_assets,
        "verified_outcomes": outcome_counts.get("verified", 0),
        "outcomes_requiring_evidence": outcome_counts.get("evidence_required", 0),
        "outcomes_requiring_identity": outcome_counts.get("identity_required", 0),
    }


def verified_provider_history_series_ids(session: Session) -> set[str]:
    """Series IDs allowed through the provider-history identity gate."""
    return {
        series_id
        for series_id in session.scalars(
            select(MarketPriceBackfillState.series_id)
            .join(
                MarketAssetIdentifier,
                MarketAssetIdentifier.asset_key == MarketPriceBackfillState.asset_key,
            )
            .outerjoin(
                MarketLifecycleResolution,
                MarketLifecycleResolution.asset_key == MarketPriceBackfillState.asset_key,
            )
            .where(
                MarketAssetIdentifier.identity_status == "verified",
                MarketPriceBackfillState.series_id.is_not(None),
                (
                    MarketLifecycleResolution.asset_key.is_(None)
                    | MarketLifecycleResolution.resolution_type.in_(
                        ("verified_delisted", "bankruptcy_final", "liquidation_final")
                    )
                ),
            )
        )
        if series_id is not None
    }


def verify_sec_primary_identity(
    session: Session,
    *,
    asset_key: str,
    sec_cik: str,
    subject_name: str,
    evidence_url: str,
    evidence_note: str,
    now: datetime | None = None,
) -> MarketAssetIdentifier:
    """Resolve an OpenFIGI miss from a reviewer-cited SEC filing identity."""
    lifecycle = session.get(MarketAssetLifecycle, asset_key)
    if lifecycle is None:
        raise ValueError("historical asset was not found")
    normalized_cik = sec_cik.strip().zfill(10)
    if not normalized_cik.isdigit():
        raise ValueError("SEC CIK must be numeric")
    normalized_url = evidence_url.strip()
    if f"/edgar/data/{int(normalized_cik)}/" not in normalized_url:
        raise ValueError("SEC identity URL does not match the cited CIK")
    similarity = _name_similarity(lifecycle.name, subject_name)
    if similarity < 0.82:
        raise ValueError("SEC subject name does not match the provider lifecycle")
    if len(evidence_note.strip()) < 20:
        raise ValueError("SEC identity evidence note is too short")
    verified_at = now or datetime.now(UTC)
    identity = session.get(MarketAssetIdentifier, asset_key)
    if identity is None:
        identity = MarketAssetIdentifier(
            asset_key=asset_key,
            identity_status="verified",
            attempt_count=0,
        )
        session.add(identity)
    identity.identity_status = "verified"
    identity.mapping_method = "human_reviewed_sec_primary_identity"
    identity.sec_cik = normalized_cik
    identity.mapped_ticker = lifecycle.symbol
    identity.mapped_name = subject_name.strip()[:255]
    identity.mapped_exchange = "US"
    identity.security_type = "Common Stock"
    identity.name_similarity = similarity
    identity.attempt_count += 1
    identity.last_attempt_at = verified_at
    identity.last_success_at = verified_at
    identity.last_error_code = None
    identity.last_error_message = None
    state = session.get(MarketDelistingEvidenceState, asset_key)
    if state is None:
        state = MarketDelistingEvidenceState(
            asset_key=asset_key,
            status="identity_resolved",
            body_access_status="downloaded",
        )
        session.add(state)
    state.sec_cik = normalized_cik
    state.cik_name = subject_name.strip()[:255]
    state.cik_name_similarity = similarity
    state.last_success_at = verified_at
    state.last_error_code = None
    state.last_error_message = None
    outcome = session.get(MarketDelistingOutcome, asset_key)
    if outcome is not None and outcome.status != "verified":
        outcome.status = "evidence_required"
    session.flush()
    return identity


def _record_identity_error(
    session: Session,
    *,
    lifecycle: MarketAssetLifecycle,
    generated_at: datetime,
    code: str,
    message: str,
) -> None:
    state = session.get(MarketAssetIdentifier, lifecycle.asset_key)
    if state is None:
        state = MarketAssetIdentifier(
            asset_key=lifecycle.asset_key,
            identity_status="failed",
            attempt_count=0,
        )
        session.add(state)
    state.identity_status = "failed"
    state.attempt_count += 1
    state.last_attempt_at = generated_at
    state.last_error_code = code
    state.last_error_message = message[:500]


def _revalidate_stored_identity_matches(
    session: Session,
    *,
    generated_at: datetime,
) -> None:
    """Reapply deterministic name rules after a matcher-version improvement."""
    rows = list(
        session.execute(
            select(MarketAssetLifecycle, MarketAssetIdentifier)
            .join(
                MarketAssetIdentifier,
                MarketAssetIdentifier.asset_key == MarketAssetLifecycle.asset_key,
            )
            .where(MarketAssetIdentifier.identity_status.in_(("ambiguous", "mismatch")))
        )
    )
    for lifecycle, identity in rows:
        if not identity.mapped_ticker or not identity.mapped_name:
            continue
        selection = select_openfigi_identity(
            lifecycle,
            [
                {
                    "ticker": identity.mapped_ticker,
                    "name": identity.mapped_name,
                    "figi": identity.figi,
                    "compositeFIGI": identity.composite_figi,
                    "shareClassFIGI": identity.share_class_figi,
                    "exchCode": identity.mapped_exchange,
                    "securityType2": identity.security_type,
                }
            ],
        )
        if selection.status == "verified":
            identity.identity_status = "verified"
            identity.mapping_method = selection.method
            identity.name_similarity = selection.name_similarity
            identity.last_success_at = generated_at


def _archive_openfigi_payload(
    archive: ColdArchive,
    *,
    lifecycles: list[MarketAssetLifecycle],
    fetched_on: date,
    payload: bytes,
) -> str:
    identity = "|".join(sorted(lifecycle.asset_key for lifecycle in lifecycles))
    archive_key = hashlib.sha256(identity.encode()).hexdigest()
    relative = f"raw/openfigi/mapping/{fetched_on:%Y/%m/%d}/{archive_key}.json.gz"
    return archive.store_bytes(relative, gzip.compress(payload, compresslevel=6, mtime=0))


def _match_local_sec_cik(
    session: Session,
    lifecycle: MarketAssetLifecycle,
    selection: IdentitySelection,
) -> str | None:
    if selection.status != "verified":
        return None
    ticker_match = session.get(CompanyProfile, lifecycle.symbol.upper())
    if ticker_match is not None and _name_similarity(lifecycle.name, ticker_match.name) >= 0.82:
        return ticker_match.cik
    profiles = list(session.scalars(select(CompanyProfile)))
    matches = [
        profile for profile in profiles if _name_similarity(lifecycle.name, profile.name) >= 0.94
    ]
    return matches[0].cik if len(matches) == 1 else None


def _name_similarity(left: str, right: str) -> float:
    left_tokens = _name_tokens(left)
    right_tokens = _name_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    jaccard = intersection / union if union else 0.0
    left_text = " ".join(sorted(left_tokens))
    right_text = " ".join(sorted(right_tokens))
    sequence = SequenceMatcher(None, left_text, right_text).ratio()
    return max(jaccard, sequence)


def _name_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.casefold())
        if token not in LEGAL_NAME_TOKENS
    }


def _optional_text(value: Any, limit: int) -> str | None:
    text = str(value or "").strip()
    return text[:limit] if text else None
