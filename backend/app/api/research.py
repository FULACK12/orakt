"""HTTP workflow for local research and optional OpenAI review."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai_status import build_ai_status
from app.data_audit import build_data_audit_report
from app.db.enums import ClusterJobStatus
from app.db.models import ClusterJob, LogicChainHypothesis
from app.db.session import get_db_session
from app.factor_experiments import factor_experiment_status, settle_factor_experiments
from app.model_workload import local_model_workload_lock
from app.research import (
    ResearchInquiryNotFoundError,
    ResearchProviderError,
    backfill_factor_research,
    get_research_inquiry,
    get_research_report_comparison,
    list_research_inquiries,
    list_research_inquiry_summaries,
    list_research_report_change_alerts,
    record_research_review,
    refresh_factor_research,
    refresh_research_forecasts,
    review_with_openai,
    run_research,
)
from app.research_audit_jobs import (
    queue_research_report_audits,
    research_audit_status,
)
from app.research_batches import (
    ResearchBatchNotFoundError,
    create_equity_research_batch,
    get_research_batch,
    list_research_batches,
    retry_failed_batch_items,
)
from app.schemas.data_audit import DataAuditReportView
from app.schemas.research import (
    AIStatusView,
    FactorExperimentSettlementView,
    FactorExperimentStatusView,
    FactorRefreshView,
    ForecastRefreshView,
    ResearchAuditQueueRequest,
    ResearchAuditQueueView,
    ResearchAuditStatusView,
    ResearchBatchCreateRequest,
    ResearchBatchListResponse,
    ResearchBatchView,
    ResearchContextView,
    ResearchInquiryListResponse,
    ResearchInquiryRequest,
    ResearchInquirySummaryListResponse,
    ResearchInquiryView,
    ResearchReportChangeAlertListResponse,
    ResearchReportComparisonResponse,
    ResearchReviewRequest,
)

router = APIRouter(prefix="/research", tags=["research"])


@router.post(
    "/batches",
    response_model=ResearchBatchView,
    status_code=status.HTTP_201_CREATED,
)
def create_research_batch(
    request: ResearchBatchCreateRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> ResearchBatchView:
    """Queue a durable US/China equity research batch without blocking HTTP."""
    try:
        return create_equity_research_batch(session, request=request)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/batches", response_model=ResearchBatchListResponse)
def research_batches(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> ResearchBatchListResponse:
    """Return recent durable research batches and per-target progress."""
    return ResearchBatchListResponse(batches=list_research_batches(session, limit=limit))


@router.get("/batches/{batch_id}", response_model=ResearchBatchView)
def research_batch(
    batch_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> ResearchBatchView:
    try:
        return get_research_batch(session, batch_id)
    except ResearchBatchNotFoundError as exc:
        raise HTTPException(status_code=404, detail="research batch not found") from exc


@router.post("/batches/{batch_id}/retry", response_model=ResearchBatchView)
def retry_research_batch(
    batch_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> ResearchBatchView:
    """Return failed targets to the queue without duplicating completed reports."""
    try:
        return retry_failed_batch_items(session, batch_id=batch_id)
    except ResearchBatchNotFoundError as exc:
        raise HTTPException(status_code=404, detail="research batch not found") from exc


@router.post("/audits/queue", response_model=ResearchAuditQueueView)
def queue_report_audits(
    request: ResearchAuditQueueRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> ResearchAuditQueueView:
    """Queue frozen-evidence audits; refresh mode must be explicitly requested."""
    return queue_research_report_audits(
        session,
        mode=request.mode,
        limit=request.limit,
        inquiry_ids=tuple(request.inquiry_ids) if request.inquiry_ids else None,
    )


@router.get("/audits/status", response_model=ResearchAuditStatusView)
def report_audit_status(
    session: Annotated[Session, Depends(get_db_session)],
) -> ResearchAuditStatusView:
    return research_audit_status(session)


@router.get("/data-audit", response_model=DataAuditReportView)
def data_audit(
    session: Annotated[Session, Depends(get_db_session)],
) -> DataAuditReportView:
    """Return a live quality report without writing a new archive on every page load."""
    return build_data_audit_report(
        session,
        persist=False,
        include_full_coverage=False,
    )


@router.post("/data-audit", response_model=DataAuditReportView)
def archive_data_audit(
    session: Annotated[Session, Depends(get_db_session)],
) -> DataAuditReportView:
    """Generate and archive one reproducible data-quality report."""
    return build_data_audit_report(session, persist=True)


@router.get("/ai-status", response_model=AIStatusView)
def ai_status(
    session: Annotated[Session, Depends(get_db_session)],
) -> AIStatusView:
    """Return auditable chain, model-upgrade, and retraining status."""
    return build_ai_status(session)


@router.get("/context", response_model=ResearchContextView)
def research_context(
    session: Annotated[Session, Depends(get_db_session)],
) -> ResearchContextView:
    """Return only the job identifiers required by the research workspace."""
    latest_cluster_job_id = session.scalar(
        select(func.max(ClusterJob.id)).where(
            ClusterJob.status == ClusterJobStatus.COMPLETED,
            ClusterJob.result.is_not(None),
        )
    )
    latest_logic_job_id = session.scalar(select(func.max(LogicChainHypothesis.cluster_job_id)))
    return ResearchContextView(
        latest_cluster_job_id=latest_cluster_job_id,
        latest_logic_job_id=latest_logic_job_id,
    )


@router.get("/inquiries", response_model=ResearchInquiryListResponse)
def research_inquiries(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 12,
) -> ResearchInquiryListResponse:
    """Return recent user-directed and autonomous research."""
    return ResearchInquiryListResponse(inquiries=list_research_inquiries(session, limit=limit))


@router.get("/inquiries/summaries", response_model=ResearchInquirySummaryListResponse)
def research_inquiry_summaries(
    session: Annotated[Session, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    q: Annotated[str | None, Query(max_length=200)] = None,
    market_region: Annotated[Literal["us", "china"] | None, Query()] = None,
    inquiry_status: Annotated[
        Literal["running", "completed", "failed"] | None,
        Query(alias="status"),
    ] = None,
    created_from: Annotated[date | None, Query()] = None,
    created_to: Annotated[date | None, Query()] = None,
) -> ResearchInquirySummaryListResponse:
    """Return a lightweight report catalog without loading report or evidence JSON."""
    if created_from and created_to and created_from > created_to:
        raise HTTPException(
            status_code=422,
            detail="created_from must be on or before created_to",
        )
    inquiries, total = list_research_inquiry_summaries(
        session,
        page=page,
        page_size=page_size,
        search=q,
        market_region=market_region,
        status=inquiry_status,
        created_from=created_from,
        created_to=created_to,
    )
    return ResearchInquirySummaryListResponse(
        inquiries=inquiries,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post("/forecasts/revalidate", response_model=ForecastRefreshView)
def revalidate_news_forecasts(
    session: Annotated[Session, Depends(get_db_session)],
) -> ForecastRefreshView:
    """Use later news and market observations to audit stored forecasts."""
    try:
        result = refresh_research_forecasts(session)
        session.commit()
        return ForecastRefreshView.model_validate(result)
    except ResearchProviderError as exc:
        session.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/factors/backfill", response_model=FactorRefreshView)
def backfill_research_factors(
    session: Annotated[Session, Depends(get_db_session)],
    force: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=24)] = 4,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> FactorRefreshView:
    """Backfill a bounded page of factor results to avoid long HTTP requests."""
    result = backfill_factor_research(
        session,
        report_limit=limit,
        report_offset=offset,
        only_missing=not force,
    )
    session.commit()
    return FactorRefreshView.model_validate(result)


@router.get("/factors/experiments", response_model=FactorExperimentStatusView)
def research_factor_experiments(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=5, le=100)] = 40,
) -> FactorExperimentStatusView:
    """Return repeated-backtest and prospective-validation state."""
    return factor_experiment_status(session, limit=limit)


@router.post("/factors/experiments/settle", response_model=FactorExperimentSettlementView)
def settle_research_factor_experiments(
    session: Annotated[Session, Depends(get_db_session)],
) -> FactorExperimentSettlementView:
    """Settle factor outcomes only after their frozen future horizon matures."""
    result = settle_factor_experiments(session)
    session.commit()
    return result


@router.get("/inquiries/{inquiry_id}", response_model=ResearchInquiryView)
def research_inquiry(
    inquiry_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> ResearchInquiryView:
    """Return one research run."""
    try:
        return get_research_inquiry(session, inquiry_id)
    except ResearchInquiryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="research inquiry not found") from exc


@router.get("/inquiries/{inquiry_id}/workspace", response_model=ResearchInquiryView)
def research_inquiry_workspace(
    inquiry_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> ResearchInquiryView:
    """Return one report with only the evidence fields required by the web workspace."""
    try:
        return get_research_inquiry(
            session,
            inquiry_id,
            include_full_evidence=False,
        )
    except ResearchInquiryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="research inquiry not found") from exc


@router.get(
    "/report-change-alerts",
    response_model=ResearchReportChangeAlertListResponse,
)
def research_report_change_alerts(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=5, le=50)] = 24,
) -> ResearchReportChangeAlertListResponse:
    """Return lightweight cross-company alerts for material report changes."""
    return list_research_report_change_alerts(session, limit=limit)


@router.get(
    "/inquiries/{inquiry_id}/comparison",
    response_model=ResearchReportComparisonResponse,
)
def research_inquiry_comparison(
    inquiry_id: int,
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=2, le=24)] = 12,
) -> ResearchReportComparisonResponse:
    """Return compact same-company history for longitudinal report review."""
    try:
        return get_research_report_comparison(session, inquiry_id, limit=limit)
    except ResearchInquiryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="research inquiry not found") from exc


@router.post(
    "/inquiries/{inquiry_id}/factor-mine",
    response_model=ResearchInquiryView,
)
def mine_research_factors(
    inquiry_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> ResearchInquiryView:
    """Rebuild nonlinear factor interactions and out-of-sample validation."""
    try:
        result = refresh_factor_research(session, inquiry_id=inquiry_id)
        session.commit()
        return result
    except ResearchInquiryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="research inquiry not found") from exc
    except ResearchProviderError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/inquiries",
    response_model=ResearchInquiryView,
    status_code=status.HTTP_201_CREATED,
)
def create_research_inquiry(
    request: ResearchInquiryRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> ResearchInquiryView:
    """Research a user question using the local model and retained evidence."""
    try:
        with local_model_workload_lock(session) as acquired:
            if not acquired:
                raise HTTPException(
                    status_code=409,
                    detail="local research model is busy; retry after the active report finishes",
                )
            result = run_research(
                session,
                question=request.question,
                mode="user_question",
            )
        session.commit()
        return result
    except ResearchProviderError as exc:
        session.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/autonomous",
    response_model=ResearchInquiryView,
    status_code=status.HTTP_201_CREATED,
)
def create_autonomous_research(
    session: Annotated[Session, Depends(get_db_session)],
) -> ResearchInquiryView:
    """Let the local model propose and investigate one grounded question."""
    try:
        with local_model_workload_lock(session) as acquired:
            if not acquired:
                raise HTTPException(
                    status_code=409,
                    detail="local research model is busy; retry after the active report finishes",
                )
            result = run_research(session, question=None, mode="autonomous")
        session.commit()
        return result
    except ResearchProviderError as exc:
        session.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/inquiries/{inquiry_id}/chatgpt-review",
    response_model=ResearchInquiryView,
)
def chatgpt_review(
    inquiry_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> ResearchInquiryView:
    """Optionally audit a local result through the OpenAI Responses API."""
    try:
        result = review_with_openai(session, inquiry_id=inquiry_id)
        session.commit()
        return result
    except ResearchInquiryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="research inquiry not found") from exc
    except ResearchProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/inquiries/{inquiry_id}/reviews",
    response_model=ResearchInquiryView,
)
def review_research_report(
    inquiry_id: int,
    request: ResearchReviewRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> ResearchInquiryView:
    """Append an explicit human decision over a completed research report."""
    try:
        result = record_research_review(
            session,
            inquiry_id=inquiry_id,
            decision=request.decision,
            reviewer_note=request.reviewer_note,
        )
        session.commit()
        return result
    except ResearchInquiryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="research inquiry not found") from exc
    except ResearchProviderError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
