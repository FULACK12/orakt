"""Major trading-index catalog and optional provider observations."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alpha_vantage_prices import price_backfill_coverage, rank_price_backfill_candidates
from app.core.config import Settings, get_settings
from app.cycle_models import build_cycle_model_suite
from app.db.models import (
    MarketAssetIdentifier,
    MarketAssetLifecycle,
    MarketDelistingEvidenceCandidate,
    MarketDelistingEvidenceState,
    MarketDelistingOutcome,
    MarketLifecycleResolution,
    MarketPriceBackfillState,
    MarketTerminalCashflow,
)
from app.db.session import get_db_session
from app.market_delisting_evidence import (
    SEC_API_DOCUMENTATION_URL,
    ingest_supplemental_evidence,
    market_delisting_evidence_coverage,
    review_evidence_candidate,
)
from app.market_history import build_cycle_snapshot, persist_twelve_market_snapshot
from app.market_identity import (
    OPENFIGI_SOURCE_URL,
    market_identity_coverage,
    verify_delisting_outcome,
    verify_sec_primary_identity,
    verify_stock_delisting_outcome,
)
from app.market_lifecycle_segmentation import (
    segment_price_series_from_terminal_evidence,
)
from app.market_terminal_outcomes import (
    finalize_multi_stage_outcome,
    record_lifecycle_resolution,
    record_terminal_cashflow,
)
from app.markets import list_market_indices
from app.schemas.cycle_models import CycleModelSuiteResponse
from app.schemas.market_cycle import MarketCycleResponse
from app.schemas.markets import (
    DelistingEvidenceCandidateView,
    DelistingEvidenceReviewRequest,
    DelistingOutcomeEvidenceRequest,
    HistoricalDelistingEvidenceAssetView,
    HistoricalDelistingEvidenceResponse,
    HistoricalIdentityAuditResponse,
    HistoricalPriceBackfillCandidateView,
    HistoricalPriceBackfillQueueResponse,
    HistoricalSecurityIdentityView,
    LifecycleResolutionRequest,
    LifecycleResolutionView,
    LifecycleSegmentRequest,
    LifecycleSegmentResponse,
    MarketIndexResponse,
    MultiStageOutcomeRequest,
    SecPrimaryIdentityRequest,
    StockDelistingOutcomeEvidenceRequest,
    SupplementalDelistingEvidenceRequest,
    TerminalCashflowRequest,
    TerminalCashflowView,
)

router = APIRouter(prefix="/markets", tags=["markets"])


@router.get(
    "/indices",
    response_model=MarketIndexResponse,
    summary="List major trading indices and optional current observations",
)
async def market_indices(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_db_session)],
    country_iso2: Annotated[
        str | None,
        Query(min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$"),
    ] = None,
) -> MarketIndexResponse:
    """Return reviewed definitions even when the quote API key is absent."""
    response = await list_market_indices(settings, country_iso2=country_iso2)
    if country_iso2 is None and response.fetched_at is not None:
        persist_twelve_market_snapshot(session, response)
        session.commit()
    return response


@router.get(
    "/cycle",
    response_model=MarketCycleResponse,
    summary="Classify the current US economic cycle from retained primary data",
)
def market_cycle(
    session: Annotated[Session, Depends(get_db_session)],
) -> MarketCycleResponse:
    """Return an auditable regime score rather than an opaque model label."""
    return MarketCycleResponse(
        generated_at=datetime.now(UTC),
        **build_cycle_snapshot(session),
    )


@router.get(
    "/historical-identity-audit",
    response_model=HistoricalIdentityAuditResponse,
    summary="Inspect FIGI/CIK identity gates and post-delisting value coverage",
)
def historical_identity_audit(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> HistoricalIdentityAuditResponse:
    coverage = market_identity_coverage(session)
    rows = list(
        session.execute(
            select(
                MarketAssetLifecycle,
                MarketPriceBackfillState,
                MarketAssetIdentifier,
                MarketDelistingOutcome,
            )
            .join(
                MarketPriceBackfillState,
                MarketPriceBackfillState.asset_key == MarketAssetLifecycle.asset_key,
            )
            .outerjoin(
                MarketAssetIdentifier,
                MarketAssetIdentifier.asset_key == MarketAssetLifecycle.asset_key,
            )
            .outerjoin(
                MarketDelistingOutcome,
                MarketDelistingOutcome.asset_key == MarketAssetLifecycle.asset_key,
            )
            .where(MarketPriceBackfillState.series_id.is_not(None))
            .order_by(MarketPriceBackfillState.priority_score.desc())
            .limit(limit)
        )
    )
    return HistoricalIdentityAuditResponse(
        generated_at=datetime.now(UTC),
        source=OPENFIGI_SOURCE_URL,
        assets=[
            _historical_identity_view(lifecycle, price, identity, outcome)
            for lifecycle, price, identity, outcome in rows
            if lifecycle.delisting_date is not None
        ],
        **{
            key: int(coverage[key])
            for key in (
                "verified_identity_assets",
                "unresolved_identity_assets",
                "ambiguous_identity_assets",
                "mismatched_identity_assets",
                "lifecycle_conflict_identity_assets",
                "sec_cik_assets",
                "verified_outcomes",
                "outcomes_requiring_evidence",
                "outcomes_requiring_identity",
            )
        },
    )


@router.post(
    "/historical-identity-audit/{asset_key}/outcome",
    response_model=HistoricalSecurityIdentityView,
    summary="Verify a post-delisting shareholder value from cited evidence",
)
def record_delisting_outcome(
    asset_key: str,
    payload: DelistingOutcomeEvidenceRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> HistoricalSecurityIdentityView:
    lifecycle = session.get(MarketAssetLifecycle, asset_key)
    price = session.get(MarketPriceBackfillState, asset_key)
    if lifecycle is None or price is None:
        raise HTTPException(status_code=404, detail="historical asset was not found")
    candidate = session.get(MarketDelistingEvidenceCandidate, payload.evidence_key)
    if candidate is None or candidate.asset_key != asset_key:
        raise HTTPException(status_code=422, detail="reviewed evidence was not found for asset")
    if candidate.review_status != "accepted" or candidate.review_role != "terminal_outcome":
        raise HTTPException(
            status_code=422,
            detail="evidence is not accepted as a terminal outcome",
        )
    if candidate.value_unit != "USD_per_share":
        raise HTTPException(
            status_code=422,
            detail="stock consideration must be valued before terminal return admission",
        )
    if candidate.candidate_value != payload.terminal_value_per_share:
        raise HTTPException(
            status_code=422,
            detail="terminal value does not match reviewed evidence",
        )
    try:
        outcome = verify_delisting_outcome(
            session,
            asset_key=asset_key,
            outcome_type=payload.outcome_type,
            terminal_value_per_share=payload.terminal_value_per_share,
            payment_date=payload.payment_date,
            evidence_url=str(payload.evidence_url),
            evidence_note=payload.evidence_note,
            evidence_key=payload.evidence_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    identity = session.get(MarketAssetIdentifier, asset_key)
    return _historical_identity_view(lifecycle, price, identity, outcome)


@router.post(
    "/historical-identity-audit/{asset_key}/stock-outcome",
    response_model=HistoricalSecurityIdentityView,
    summary="Verify fixed-ratio stock consideration from two reviewed SEC facts",
)
def record_stock_delisting_outcome(
    asset_key: str,
    payload: StockDelistingOutcomeEvidenceRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> HistoricalSecurityIdentityView:
    lifecycle = session.get(MarketAssetLifecycle, asset_key)
    price = session.get(MarketPriceBackfillState, asset_key)
    if lifecycle is None or price is None:
        raise HTTPException(status_code=404, detail="historical asset was not found")
    try:
        outcome = verify_stock_delisting_outcome(
            session,
            asset_key=asset_key,
            exchange_ratio_evidence_key=payload.exchange_ratio_evidence_key,
            valuation_evidence_key=payload.valuation_evidence_key,
            acquirer_symbol=payload.acquirer_symbol,
            payment_date=payload.payment_date,
            evidence_note=payload.evidence_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    identity = session.get(MarketAssetIdentifier, asset_key)
    return _historical_identity_view(lifecycle, price, identity, outcome)


@router.post(
    "/historical-identity-audit/{asset_key}/sec-identity",
    response_model=HistoricalSecurityIdentityView,
    summary="Resolve an automated identity miss from a cited SEC filing",
)
def record_sec_primary_identity(
    asset_key: str,
    payload: SecPrimaryIdentityRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> HistoricalSecurityIdentityView:
    lifecycle = session.get(MarketAssetLifecycle, asset_key)
    price = session.get(MarketPriceBackfillState, asset_key)
    if lifecycle is None or price is None:
        raise HTTPException(status_code=404, detail="historical asset was not found")
    try:
        identity = verify_sec_primary_identity(
            session,
            asset_key=asset_key,
            sec_cik=payload.sec_cik,
            subject_name=payload.subject_name,
            evidence_url=str(payload.evidence_url),
            evidence_note=payload.evidence_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    outcome = session.get(MarketDelistingOutcome, asset_key)
    return _historical_identity_view(lifecycle, price, identity, outcome)


@router.get(
    "/historical-lifecycle-resolutions",
    response_model=list[LifecycleResolutionView],
    summary="List primary-source lifecycle corrections",
)
def historical_lifecycle_resolutions(
    session: Annotated[Session, Depends(get_db_session)],
) -> list[LifecycleResolutionView]:
    rows = list(
        session.execute(
            select(MarketLifecycleResolution, MarketAssetLifecycle)
            .join(
                MarketAssetLifecycle,
                MarketAssetLifecycle.asset_key == MarketLifecycleResolution.asset_key,
            )
            .order_by(MarketLifecycleResolution.reviewed_at.desc())
        )
    )
    return [_lifecycle_resolution_view(resolution, lifecycle) for resolution, lifecycle in rows]


@router.post(
    "/historical-lifecycle-resolutions/{asset_key}",
    response_model=LifecycleResolutionView,
    summary="Record a primary-source lifecycle correction",
)
def review_historical_lifecycle(
    asset_key: str,
    payload: LifecycleResolutionRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> LifecycleResolutionView:
    try:
        resolution = record_lifecycle_resolution(
            session,
            asset_key=asset_key,
            resolution_type=payload.resolution_type,
            authoritative_status=payload.authoritative_status,
            authoritative_delisting_date=payload.authoritative_delisting_date,
            evidence_url=str(payload.evidence_url),
            evidence_note=payload.evidence_note,
        )
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc) else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    session.commit()
    lifecycle = session.get(MarketAssetLifecycle, asset_key)
    if lifecycle is None:
        raise HTTPException(status_code=404, detail="historical asset was not found")
    return _lifecycle_resolution_view(resolution, lifecycle)


@router.get(
    "/historical-terminal-cashflows/{asset_key}",
    response_model=list[TerminalCashflowView],
    summary="List reviewed terminal cashflow stages",
)
def historical_terminal_cashflows(
    asset_key: str,
    session: Annotated[Session, Depends(get_db_session)],
) -> list[TerminalCashflowView]:
    cashflows = list(
        session.scalars(
            select(MarketTerminalCashflow)
            .where(MarketTerminalCashflow.asset_key == asset_key)
            .order_by(MarketTerminalCashflow.payment_date, MarketTerminalCashflow.sequence)
        )
    )
    return [_terminal_cashflow_view(cashflow) for cashflow in cashflows]


@router.post(
    "/historical-terminal-cashflows/{asset_key}",
    response_model=TerminalCashflowView,
    summary="Record one reviewed terminal cashflow stage",
)
def review_terminal_cashflow(
    asset_key: str,
    payload: TerminalCashflowRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> TerminalCashflowView:
    try:
        cashflow = record_terminal_cashflow(
            session,
            asset_key=asset_key,
            evidence_key=payload.evidence_key,
            cashflow_type=payload.cashflow_type,
            amount_per_share=payload.amount_per_share,
            payment_date=payload.payment_date,
            status=payload.status,
            is_final=payload.is_final,
            evidence_note=payload.evidence_note,
        )
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc) else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    session.commit()
    return _terminal_cashflow_view(cashflow)


@router.post(
    "/historical-identity-audit/{asset_key}/multi-stage-outcome",
    response_model=HistoricalSecurityIdentityView,
    summary="Finalize a shareholder outcome from reviewed cashflow stages",
)
def record_multi_stage_outcome(
    asset_key: str,
    payload: MultiStageOutcomeRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> HistoricalSecurityIdentityView:
    lifecycle = session.get(MarketAssetLifecycle, asset_key)
    price = session.get(MarketPriceBackfillState, asset_key)
    if lifecycle is None or price is None:
        raise HTTPException(status_code=404, detail="historical asset was not found")
    try:
        outcome = finalize_multi_stage_outcome(
            session,
            asset_key=asset_key,
            outcome_type=payload.outcome_type,
            evidence_note=payload.evidence_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    identity = session.get(MarketAssetIdentifier, asset_key)
    return _historical_identity_view(lifecycle, price, identity, outcome)


def _historical_identity_view(
    lifecycle: MarketAssetLifecycle,
    price: MarketPriceBackfillState,
    identity: MarketAssetIdentifier | None,
    outcome: MarketDelistingOutcome | None,
) -> HistoricalSecurityIdentityView:
    if lifecycle.delisting_date is None:
        raise ValueError("historical identity view requires a delisting date")
    return HistoricalSecurityIdentityView(
        asset_key=lifecycle.asset_key,
        symbol=lifecycle.symbol,
        name=lifecycle.name,
        exchange=lifecycle.exchange,
        delisting_date=lifecycle.delisting_date,
        series_id=price.series_id,
        identity_status=identity.identity_status if identity else "not_checked",
        mapping_method=identity.mapping_method if identity else None,
        figi=identity.figi if identity else None,
        composite_figi=identity.composite_figi if identity else None,
        share_class_figi=identity.share_class_figi if identity else None,
        sec_cik=identity.sec_cik if identity else None,
        mapped_name=identity.mapped_name if identity else None,
        mapped_exchange=identity.mapped_exchange if identity else None,
        name_similarity=identity.name_similarity if identity else None,
        outcome_status=outcome.status if outcome else "not_materialized",
        outcome_type=outcome.outcome_type if outcome else "unknown",
        last_trade_date=outcome.last_trade_date if outcome else None,
        last_trade_price=outcome.last_trade_price if outcome else None,
        terminal_value_per_share=(outcome.terminal_value_per_share if outcome else None),
        exchange_ratio=outcome.exchange_ratio if outcome else None,
        acquirer_symbol=outcome.acquirer_symbol if outcome else None,
        acquirer_price_on_payment=(outcome.acquirer_price_on_payment if outcome else None),
        acquirer_price_observed_on=(
            outcome.acquirer_price_observed_on if outcome else None
        ),
        resolution_method=outcome.resolution_method if outcome else None,
        cashflow_count=outcome.cashflow_count if outcome else 0,
        terminal_is_final=outcome.terminal_is_final if outcome else False,
        payment_date=outcome.payment_date if outcome else None,
        delisting_return=outcome.delisting_return if outcome else None,
        evidence_url=outcome.evidence_url if outcome else None,
        verified_at=outcome.verified_at if outcome else None,
    )


def _lifecycle_resolution_view(
    resolution: MarketLifecycleResolution,
    lifecycle: MarketAssetLifecycle,
) -> LifecycleResolutionView:
    return LifecycleResolutionView(
        asset_key=lifecycle.asset_key,
        symbol=lifecycle.symbol,
        provider_status=lifecycle.listing_status,
        provider_delisting_date=lifecycle.delisting_date,
        resolution_type=resolution.resolution_type,
        authoritative_status=resolution.authoritative_status,
        authoritative_delisting_date=resolution.authoritative_delisting_date,
        evidence_url=resolution.evidence_url,
        evidence_note=resolution.evidence_note,
        reviewed_at=resolution.reviewed_at,
    )


def _terminal_cashflow_view(cashflow: MarketTerminalCashflow) -> TerminalCashflowView:
    return TerminalCashflowView(
        cashflow_key=cashflow.cashflow_key,
        asset_key=cashflow.asset_key,
        evidence_key=cashflow.evidence_key,
        sequence=cashflow.sequence,
        cashflow_type=cashflow.cashflow_type,
        amount_per_share=cashflow.amount_per_share,
        payment_date=cashflow.payment_date,
        status=cashflow.status,
        is_final=cashflow.is_final,
        evidence_url=cashflow.evidence_url,
        evidence_note=cashflow.evidence_note,
        reviewed_at=cashflow.reviewed_at,
    )


@router.get(
    "/historical-delisting-evidence",
    response_model=HistoricalDelistingEvidenceResponse,
    summary="Inspect SEC filing candidates for post-delisting shareholder value",
)
def historical_delisting_evidence(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> HistoricalDelistingEvidenceResponse:
    coverage = market_delisting_evidence_coverage(session)
    rows = list(
        session.execute(
            select(
                MarketAssetLifecycle,
                MarketAssetIdentifier,
                MarketDelistingEvidenceState,
                MarketPriceBackfillState,
                MarketDelistingOutcome,
                MarketLifecycleResolution,
            )
            .join(
                MarketDelistingEvidenceState,
                MarketDelistingEvidenceState.asset_key == MarketAssetLifecycle.asset_key,
            )
            .outerjoin(
                MarketAssetIdentifier,
                MarketAssetIdentifier.asset_key == MarketAssetLifecycle.asset_key,
            )
            .outerjoin(
                MarketPriceBackfillState,
                MarketPriceBackfillState.asset_key == MarketAssetLifecycle.asset_key,
            )
            .outerjoin(
                MarketDelistingOutcome,
                MarketDelistingOutcome.asset_key == MarketAssetLifecycle.asset_key,
            )
            .outerjoin(
                MarketLifecycleResolution,
                MarketLifecycleResolution.asset_key == MarketAssetLifecycle.asset_key,
            )
            .order_by(MarketDelistingEvidenceState.last_attempt_at.desc())
            .limit(limit)
        )
    )
    asset_keys = [
        lifecycle.asset_key
        for lifecycle, _identity, _state, _price, _outcome, _resolution in rows
    ]
    candidates_by_asset: dict[str, list[MarketDelistingEvidenceCandidate]] = {
        asset_key: [] for asset_key in asset_keys
    }
    if asset_keys:
        candidates = list(
            session.scalars(
                select(MarketDelistingEvidenceCandidate)
                .where(MarketDelistingEvidenceCandidate.asset_key.in_(asset_keys))
                .order_by(
                    MarketDelistingEvidenceCandidate.filed_on.desc(),
                    MarketDelistingEvidenceCandidate.confidence.desc(),
                )
            )
        )
        for candidate in candidates:
            if len(candidates_by_asset[candidate.asset_key]) < 20:
                candidates_by_asset[candidate.asset_key].append(candidate)
    return HistoricalDelistingEvidenceResponse(
        generated_at=datetime.now(UTC),
        source=SEC_API_DOCUMENTATION_URL,
        body_retrieval_ready=settings.sec_contact_email is not None,
        assets=[
            _delisting_evidence_asset_view(
                lifecycle,
                identity,
                state,
                price,
                outcome,
                resolution,
                candidates_by_asset[lifecycle.asset_key],
            )
            for lifecycle, identity, state, price, outcome, resolution in rows
            if lifecycle.delisting_date is not None
        ],
        **coverage,
    )


@router.post(
    "/historical-delisting-evidence/{evidence_key}/review",
    response_model=DelistingEvidenceCandidateView,
    summary="Review one SEC evidence candidate without writing a terminal return",
)
def review_delisting_evidence(
    evidence_key: str,
    payload: DelistingEvidenceReviewRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> DelistingEvidenceCandidateView:
    try:
        candidate = review_evidence_candidate(
            session,
            evidence_key=evidence_key,
            decision=payload.decision,
            review_role=payload.review_role,
            review_note=payload.review_note,
        )
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc) else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    session.commit()
    return _delisting_evidence_candidate_view(candidate)


@router.post(
    "/historical-delisting-evidence/{asset_key}/supplement",
    response_model=DelistingEvidenceCandidateView,
    summary="Store a reviewer extract from an SEC completion filing or exhibit",
)
def supplement_delisting_evidence(
    asset_key: str,
    payload: SupplementalDelistingEvidenceRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> DelistingEvidenceCandidateView:
    if session.get(MarketAssetLifecycle, asset_key) is None:
        raise HTTPException(status_code=404, detail="historical asset was not found")
    try:
        candidate = ingest_supplemental_evidence(
            session,
            asset_key=asset_key,
            accession_number=payload.accession_number,
            form=payload.form,
            filed_on=payload.filed_on,
            observed_on=payload.observed_on,
            source_url=str(payload.source_url),
            evidence_type=payload.evidence_type,
            candidate_value=payload.candidate_value,
            value_unit=payload.value_unit,
            evidence_excerpt=payload.evidence_excerpt,
            confidence=payload.confidence,
            subject_symbol=payload.subject_symbol,
            subject_sec_cik=payload.subject_sec_cik,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return _delisting_evidence_candidate_view(candidate)


@router.post(
    "/historical-delisting-evidence/{asset_key}/segment",
    response_model=LifecycleSegmentResponse,
    summary="Create an SEC-anchored pre-terminal segment without altering raw prices",
)
def segment_historical_price_lifecycle(
    asset_key: str,
    payload: LifecycleSegmentRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> LifecycleSegmentResponse:
    try:
        result = segment_price_series_from_terminal_evidence(
            session,
            asset_key=asset_key,
            evidence_key=payload.evidence_key,
        )
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc) else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    session.commit()
    return result


def _delisting_evidence_asset_view(
    lifecycle: MarketAssetLifecycle,
    identity: MarketAssetIdentifier | None,
    state: MarketDelistingEvidenceState,
    price: MarketPriceBackfillState | None,
    outcome: MarketDelistingOutcome | None,
    resolution: MarketLifecycleResolution | None,
    candidates: list[MarketDelistingEvidenceCandidate],
) -> HistoricalDelistingEvidenceAssetView:
    if lifecycle.delisting_date is None:
        raise ValueError("delisting evidence view requires a delisting date")
    identity_status = identity.identity_status if identity else "not_checked"
    outcome_status = outcome.status if outcome else "not_materialized"
    factor_block_reason: str | None = None
    if outcome_status == "verified":
        factor_block_reason = "terminal_outcome_already_verified"
    elif resolution is not None and resolution.resolution_type not in {
        "verified_delisted",
        "bankruptcy_final",
        "liquidation_final",
    }:
        factor_block_reason = "lifecycle_resolution_pending"
    elif identity_status != "verified":
        factor_block_reason = "identity_not_verified"
    elif price is None or price.series_id is None:
        factor_block_reason = "price_series_not_ready"
    elif not any(
        candidate.review_status == "accepted"
        and candidate.review_role == "terminal_outcome"
        and candidate.value_unit == "USD_per_share"
        for candidate in candidates
    ):
        factor_block_reason = "terminal_evidence_not_accepted"
    return HistoricalDelistingEvidenceAssetView(
        asset_key=lifecycle.asset_key,
        symbol=lifecycle.symbol,
        name=lifecycle.name,
        delisting_date=lifecycle.delisting_date,
        sec_cik=state.sec_cik or (identity.sec_cik if identity else None),
        identity_status=identity_status,
        outcome_status=outcome_status,
        factor_eligible=factor_block_reason is None,
        factor_block_reason=factor_block_reason,
        terminal_value_per_share=(outcome.terminal_value_per_share if outcome else None),
        lifecycle_resolution_type=(resolution.resolution_type if resolution else None),
        authoritative_status=(resolution.authoritative_status if resolution else None),
        authoritative_delisting_date=(
            resolution.authoritative_delisting_date if resolution else None
        ),
        search_status=state.status,
        cik_name=state.cik_name,
        cik_name_similarity=state.cik_name_similarity,
        filing_count=state.filing_count,
        extracted_candidate_count=state.extracted_candidate_count,
        body_access_status=state.body_access_status,
        search_start=state.search_start,
        search_end=state.search_end,
        last_attempt_at=state.last_attempt_at,
        candidates=[_delisting_evidence_candidate_view(item) for item in candidates],
    )


def _delisting_evidence_candidate_view(
    candidate: MarketDelistingEvidenceCandidate,
) -> DelistingEvidenceCandidateView:
    return DelistingEvidenceCandidateView(
        evidence_key=candidate.evidence_key,
        accession_number=candidate.accession_number,
        observed_on=candidate.observed_on,
        subject_symbol=candidate.subject_symbol,
        subject_sec_cik=candidate.subject_sec_cik,
        form=candidate.form,
        filed_on=candidate.filed_on,
        source_url=candidate.source_url,
        evidence_type=candidate.evidence_type,
        evidence_basis=candidate.evidence_basis,
        candidate_value=candidate.candidate_value,
        value_unit=candidate.value_unit,
        evidence_excerpt=candidate.evidence_excerpt,
        confidence=candidate.confidence,
        body_status=candidate.body_status,
        review_status=candidate.review_status,
        review_role=candidate.review_role,
        review_note=candidate.review_note,
        reviewed_at=candidate.reviewed_at,
    )


@router.get(
    "/cycle-models",
    response_model=CycleModelSuiteResponse,
    summary="Compare transparent economic-cycle theories and proxy models",
)
def market_cycle_models(
    session: Annotated[Session, Depends(get_db_session)],
) -> CycleModelSuiteResponse:
    return build_cycle_model_suite(session)


@router.get(
    "/historical-price-backfill",
    response_model=HistoricalPriceBackfillQueueResponse,
    summary="Inspect the prioritized delisted-asset price backfill queue",
)
def historical_price_backfill_queue(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> HistoricalPriceBackfillQueueResponse:
    """Expose priorities and safe error codes without credentials or provider URLs."""
    coverage = price_backfill_coverage(session)
    candidates = rank_price_backfill_candidates(
        session,
        limit=limit,
        include_terminal=True,
    )
    return HistoricalPriceBackfillQueueResponse(
        generated_at=datetime.now(UTC),
        provider="Alpha Vantage TIME_SERIES_WEEKLY_ADJUSTED",
        provider_daily_request_limit=25,
        configured_daily_price_budget=settings.alpha_vantage_price_backfill_per_day,
        queued_assets=int(coverage["queued_assets"]),
        pending_assets=int(coverage["pending_assets"]),
        synced_assets=int(coverage["synced_assets"]),
        partial_assets=int(coverage["partial_assets"]),
        unavailable_assets=int(coverage["unavailable_assets"]),
        ticker_reused_assets=int(coverage["ticker_reused_assets"]),
        factor_ready_assets=int(coverage["factor_ready_assets"]),
        candidates=[
            HistoricalPriceBackfillCandidateView(
                asset_key=item.lifecycle.asset_key,
                symbol=item.lifecycle.symbol,
                name=item.lifecycle.name,
                exchange=item.lifecycle.exchange,
                asset_type=item.lifecycle.asset_type,
                ipo_date=item.lifecycle.ipo_date,
                delisting_date=item.lifecycle.delisting_date,
                priority_score=item.priority_score,
                priority_reasons=item.priority_reasons,
                status=item.state.status if item.state is not None else "not_queued",
                attempt_count=item.state.attempt_count if item.state is not None else 0,
                observations_upserted=(
                    item.state.observations_upserted if item.state is not None else 0
                ),
                observed_start=item.state.observed_start if item.state is not None else None,
                observed_end=item.state.observed_end if item.state is not None else None,
                last_attempt_at=item.state.last_attempt_at if item.state is not None else None,
                last_error_code=(
                    item.state.last_error_code if item.state is not None else None
                ),
            )
            for item in candidates
            if item.lifecycle.delisting_date is not None
        ],
    )
