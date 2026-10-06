"""SEC-anchored repair of provider histories that continue after a terminal event."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    MarketAssetIdentifier,
    MarketAssetLifecycle,
    MarketDelistingEvidenceCandidate,
    MarketDelistingEvidenceState,
    MarketDelistingOutcome,
    MarketObservation,
    MarketPriceBackfillState,
    MarketSeries,
)
from app.schemas.markets import LifecycleSegmentResponse

SEGMENT_METHOD = "sec_completion_filing_last_observation_v1"
MIN_SEGMENT_OBSERVATIONS = 60


def segment_price_series_from_terminal_evidence(
    session: Session,
    *,
    asset_key: str,
    evidence_key: str,
    now: datetime | None = None,
) -> LifecycleSegmentResponse:
    """Preserve a raw series and materialize only its pre-terminal lifecycle."""
    lifecycle = session.get(MarketAssetLifecycle, asset_key)
    state = session.get(MarketPriceBackfillState, asset_key)
    identity = session.get(MarketAssetIdentifier, asset_key)
    evidence_state = session.get(MarketDelistingEvidenceState, asset_key)
    candidate = session.get(MarketDelistingEvidenceCandidate, evidence_key)
    if lifecycle is None or state is None:
        raise ValueError("historical asset or price state was not found")
    if candidate is None or candidate.asset_key != asset_key:
        raise ValueError("terminal evidence was not found for asset")
    if candidate.review_status != "accepted" or candidate.review_role != "terminal_outcome":
        raise ValueError("terminal evidence must be accepted before lifecycle segmentation")
    if candidate.form != "8-K":
        raise ValueError("lifecycle segmentation requires a reviewed SEC completion 8-K")
    if identity is None or not identity.sec_cik:
        raise ValueError("SEC/OpenFIGI identity is not available")
    if evidence_state is None or evidence_state.sec_cik != identity.sec_cik:
        raise ValueError("SEC filing identity does not match the mapped security")
    if (identity.name_similarity or 0) < 0.82:
        raise ValueError("security name similarity is below the lifecycle threshold")
    if (evidence_state.cik_name_similarity or 0) < 0.82:
        raise ValueError("SEC company name similarity is below the lifecycle threshold")

    generated_at = now or datetime.now(UTC)
    raw_series_id = state.source_series_id or state.series_id
    if raw_series_id is None:
        raise ValueError("raw historical price series is unavailable")
    raw_series = session.get(MarketSeries, raw_series_id)
    if raw_series is None:
        raise ValueError("raw historical price metadata is unavailable")
    raw_rows = list(
        session.scalars(
            select(MarketObservation)
            .where(MarketObservation.series_id == raw_series_id)
            .order_by(MarketObservation.observed_on)
        )
    )
    retained = [row for row in raw_rows if row.observed_on <= candidate.filed_on]
    excluded = [row for row in raw_rows if row.observed_on > candidate.filed_on]
    if len(retained) < MIN_SEGMENT_OBSERVATIONS:
        raise ValueError("fewer than 60 pre-terminal observations are available")
    if not excluded:
        raise ValueError("provider series does not extend beyond the terminal filing")
    last_trade = retained[-1]
    first_contaminated = excluded[0]
    if first_contaminated.observed_on <= last_trade.observed_on:
        raise ValueError("provider series has no auditable terminal boundary")

    identity_material = "|".join(
        (raw_series_id, candidate.evidence_key, last_trade.observed_on.isoformat())
    )
    suffix = hashlib.sha256(identity_material.encode()).hexdigest()[:16]
    segmented_series_id = f"HISTSEC:{lifecycle.symbol}:{suffix}"[:64]
    segmented = session.get(MarketSeries, segmented_series_id)
    if segmented is None:
        segmented = MarketSeries(
            series_id=segmented_series_id,
            name=f"{lifecycle.name} SEC-anchored historical close",
            category="historical_equity_price",
            unit=raw_series.unit,
            frequency=raw_series.frequency,
            source_name=f"{raw_series.source_name} + SEC completion filing",
            source_url=candidate.source_url,
            listing_status="delisted",
            listed_from=retained[0].observed_on,
            listed_until=last_trade.observed_on,
            delisting_return=None,
            sector=raw_series.sector,
            region=raw_series.region,
            neutralization_group=raw_series.neutralization_group,
        )
        session.add(segmented)
        session.flush()
        session.add_all(
            [
                MarketObservation(
                    series_id=segmented_series_id,
                    observed_on=row.observed_on,
                    value=row.value,
                    fetched_at=row.fetched_at,
                )
                for row in retained
            ]
        )

    if state.source_series_id is None:
        state.source_series_id = raw_series_id
    if state.provider_delisting_date is None:
        state.provider_delisting_date = lifecycle.delisting_date
    state.series_id = segmented_series_id
    state.status = "synced"
    state.observations_upserted = len(retained)
    state.observed_start = retained[0].observed_on
    state.observed_end = last_trade.observed_on
    state.lifecycle_evidence_key = candidate.evidence_key
    state.lifecycle_terminal_date = candidate.filed_on
    state.lifecycle_segment_method = SEGMENT_METHOD
    state.lifecycle_segmented_at = generated_at
    state.last_error_code = None
    state.last_error_message = None
    lifecycle.delisting_date = last_trade.observed_on

    identity.identity_status = "verified"
    if "sec_completion_segment" not in (identity.mapping_method or ""):
        identity.mapping_method = (
            f"{identity.mapping_method}+sec_completion_segment"
            if identity.mapping_method
            else "sec_completion_segment"
        )
    identity.last_success_at = generated_at
    identity.last_error_code = None
    identity.last_error_message = None
    evidence_state.status = "reviewed_terminal_segment_ready"
    evidence_state.last_error_code = None
    evidence_state.last_error_message = None

    outcome = session.get(MarketDelistingOutcome, asset_key)
    if outcome is None:
        outcome = MarketDelistingOutcome(
            asset_key=asset_key,
            series_id=segmented_series_id,
            status="evidence_required",
            outcome_type="unknown",
        )
        session.add(outcome)
    outcome.series_id = segmented_series_id
    outcome.last_trade_date = last_trade.observed_on
    outcome.last_trade_price = float(last_trade.value)
    if outcome.status != "verified":
        outcome.status = "evidence_required"
    session.flush()

    return LifecycleSegmentResponse(
        asset_key=asset_key,
        symbol=lifecycle.symbol,
        source_series_id=raw_series_id,
        segmented_series_id=segmented_series_id,
        evidence_key=candidate.evidence_key,
        provider_delisting_date=state.provider_delisting_date,
        terminal_filing_date=candidate.filed_on,
        last_trade_date=last_trade.observed_on,
        first_contaminated_date=first_contaminated.observed_on,
        retained_observations=len(retained),
        excluded_observations=len(excluded),
        segment_method=SEGMENT_METHOD,
        segmented_at=generated_at,
    )
