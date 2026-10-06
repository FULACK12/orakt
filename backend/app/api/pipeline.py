"""Live status for the collection, archive and local-AI pipeline."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import Select, distinct, func, select
from sqlalchemy.orm import Session

from app.db.enums import ClusterJobStatus
from app.db.models import (
    ClusterJob,
    Document,
    DocumentAnalysis,
    EventDocument,
    RSSFeed,
    Source,
)
from app.db.session import get_db_session
from app.embeddings import build_embedding_client
from app.extractors import build_event_extractor
from app.schemas.pipeline import (
    PipelineFeedStatus,
    PipelineSourceStatus,
    PipelineStatusResponse,
)

router = APIRouter(prefix="/pipeline", tags=["operations"])


@router.get(
    "/status",
    response_model=PipelineStatusResponse,
    summary="Inspect collection, archive and local-AI processing status",
)
def get_pipeline_status(
    session: Annotated[Session, Depends(get_db_session)],
) -> PipelineStatusResponse:
    """Return validated live counters without exposing stored article bodies."""
    analysis_extractor = build_event_extractor().name
    embedding_provider = build_embedding_client().name
    total_documents = _count(session, select(func.count()).select_from(Document))
    cold_archived_documents = _count(
        session,
        select(func.count())
        .select_from(Document)
        .where(Document.raw_object_path.is_not(None)),
    )
    linked_documents = _count(
        session,
        select(func.count(distinct(EventDocument.document_id))).select_from(
            EventDocument
        ),
    )
    analysis_match = (
        (DocumentAnalysis.document_id == Document.id)
        & (DocumentAnalysis.content_hash == Document.content_hash)
        & (DocumentAnalysis.extractor_name == analysis_extractor)
        & (DocumentAnalysis.embedding_provider == embedding_provider)
        & (DocumentAnalysis.last_cluster_job_id.is_not(None))
    )
    analyzed_documents = _count(
        session,
        select(func.count())
        .select_from(Document)
        .join(DocumentAnalysis, analysis_match),
    )
    pending_analysis_documents = _count(
        session,
        select(func.count())
        .select_from(Document)
        .outerjoin(DocumentAnalysis, analysis_match)
        .where(
            ~select(EventDocument.document_id)
            .where(EventDocument.document_id == Document.id)
            .exists(),
            DocumentAnalysis.document_id.is_(None),
        ),
    )
    active_cluster_jobs = _count(
        session,
        select(func.count())
        .select_from(ClusterJob)
        .where(
            ClusterJob.status.in_(
                [ClusterJobStatus.QUEUED, ClusterJobStatus.RUNNING]
            )
        ),
    )
    latest_completed_job_id = session.scalar(
        select(ClusterJob.id)
        .where(ClusterJob.status == ClusterJobStatus.COMPLETED)
        .order_by(ClusterJob.completed_at.desc(), ClusterJob.id.desc())
        .limit(1)
    )
    source_rows = list(
        session.scalars(select(Source).order_by(Source.name, Source.id))
    )
    configured_sources = len(source_rows)
    configured_countries = [
        country
        for country in session.scalars(
            select(distinct(Source.country))
            .where(Source.country.is_not(None))
            .order_by(Source.country)
        )
        if country is not None
    ]
    global_sources = _count(
        session,
        select(func.count())
        .select_from(Source)
        .where(Source.country.is_(None)),
    )
    feed_rows = session.execute(
        select(RSSFeed, Source)
        .join(Source, RSSFeed.source_id == Source.id)
        .order_by(Source.name, RSSFeed.id)
    ).all()
    document_counts = {
        source_id: int(count)
        for source_id, count in session.execute(
            select(Document.source_id, func.count())
            .select_from(Document)
            .group_by(Document.source_id)
        )
    }
    feed_counts: dict[int, tuple[int, int]] = {}
    for feed, _source in feed_rows:
        total, enabled_count = feed_counts.get(feed.source_id, (0, 0))
        feed_counts[feed.source_id] = (
            total + 1,
            enabled_count + int(feed.enabled),
        )
    sources = [
        PipelineSourceStatus(
            source_name=source.name,
            country=source.country,
            language=source.language,
            source_type=source.source_type.value,
            ownership=source.ownership,
            credibility_baseline=float(source.credibility_baseline),
            document_count=document_counts.get(source.id, 0),
            total_feeds=feed_counts.get(source.id, (0, 0))[0],
            enabled_feeds=feed_counts.get(source.id, (0, 0))[1],
        )
        for source in source_rows
    ]
    feeds = [
        PipelineFeedStatus(
            source_name=source.name,
            country=source.country,
            language=source.language,
            url=feed.url,
            enabled=feed.enabled,
            license_name=feed.license_name,
            last_fetched_at=feed.last_fetched_at,
            last_success_at=feed.last_success_at,
            consecutive_failures=feed.consecutive_failures,
            last_error=feed.last_error,
        )
        for feed, source in feed_rows
    ]
    enabled = [feed for feed in feeds if feed.enabled]
    healthy = [
        feed
        for feed in enabled
        if feed.last_success_at is not None and feed.consecutive_failures == 0
    ]
    pending = [
        feed
        for feed in enabled
        if feed.last_success_at is None and feed.consecutive_failures == 0
    ]
    failing = [
        feed
        for feed in enabled
        if feed.consecutive_failures > 0 or feed.last_error is not None
    ]
    return PipelineStatusResponse(
        total_documents=total_documents,
        cold_archived_documents=cold_archived_documents,
        linked_documents=linked_documents,
        analyzed_documents=analyzed_documents,
        pending_analysis_documents=pending_analysis_documents,
        analysis_extractor=analysis_extractor,
        embedding_provider=embedding_provider,
        active_cluster_jobs=active_cluster_jobs,
        latest_completed_job_id=latest_completed_job_id,
        configured_sources=configured_sources,
        configured_countries=configured_countries,
        global_sources=global_sources,
        enabled_feeds=len(enabled),
        healthy_feeds=len(healthy),
        pending_feeds=len(pending),
        failing_feeds=len(failing),
        sources=sources,
        feeds=feeds,
    )


def _count(session: Session, statement: Select[tuple[int]]) -> int:
    value = session.scalar(statement)
    return int(value or 0)
