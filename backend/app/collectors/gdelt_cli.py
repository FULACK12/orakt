"""Command-line scheduler for thirty-day GDELT news discovery."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cluster_queue import ensure_incremental_cluster_job
from app.collectors.cli import build_cold_archive
from app.collectors.gdelt import (
    GDELT_DOC_BACKFILL_STATE_KEY,
    GDELT_DOC_ENDPOINT,
    GDELT_DOC_SOURCE_BOUNDARY,
    GDELTCollectionResult,
    GDELTRecentNewsCollector,
)
from app.core.config import get_settings
from app.db.models import Document, GdeltArchiveState
from app.db.session import get_session_factory
from app.embeddings import build_embedding_client
from app.extractors import build_event_extractor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-recent")
    parser.add_argument("--poll-seconds", type=float)
    parser.add_argument(
        "--initial-delay-seconds",
        type=float,
        default=0,
    )
    parser.add_argument(
        "--backfill-months",
        type=int,
        default=0,
        help="Maximum 30-day windows to backfill toward the source boundary",
    )
    parser.add_argument(
        "--backfill-skip-months",
        type=int,
        default=0,
        help="Resume before already completed recent windows",
    )
    parser.add_argument(
        "--backfill-floor-date",
        type=date.fromisoformat,
        default=GDELT_DOC_SOURCE_BOUNDARY,
        help="Official earliest searchable DOC 2.0 date",
    )
    parser.add_argument(
        "--backfill-window-delay-seconds",
        type=float,
        default=300,
        help="Provider cooldown between 30-day historical windows",
    )
    return parser


async def run_once(
    *,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    queue_analysis: bool = True,
) -> GDELTCollectionResult:
    """Import one month of broad discovery metadata and queue local analysis."""
    settings = get_settings()
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=settings.gdelt_request_timeout_seconds,
    ) as client:
        collector = GDELTRecentNewsCollector(
            client,
            archive=build_cold_archive(),
            records_per_topic=settings.gdelt_records_per_topic,
            request_interval_seconds=settings.gdelt_request_interval_seconds,
            max_attempts=settings.gdelt_max_attempts,
            progress_callback=lambda topic: print(
                topic.model_dump_json(),
                flush=True,
            ),
        )
        with get_session_factory()() as session:
            result = await collector.collect_range(
                session,
                starts_at=starts_at,
                ends_at=ends_at,
            )
            job_id = (
                ensure_incremental_cluster_job(
                    session,
                    extractor_name=build_event_extractor(settings).name,
                    embedding_provider=build_embedding_client(settings).name,
                )
                if queue_analysis
                else None
            )
            session.commit()
        print(
            result.model_dump_json(indent=2),
            f"\nqueued_cluster_job={job_id}",
            flush=True,
        )
    return result


async def run_forever(
    poll_seconds: float,
    *,
    initial_delay_seconds: float = 0,
    backfill_months: int = 0,
    backfill_skip_months: int = 0,
    backfill_window_delay_seconds: float = 300,
    backfill_floor_date: date = GDELT_DOC_SOURCE_BOUNDARY,
) -> None:
    if poll_seconds < 900:
        raise ValueError("poll_seconds must be at least 900")
    if initial_delay_seconds < 0:
        raise ValueError("initial_delay_seconds cannot be negative")
    if initial_delay_seconds:
        await asyncio.sleep(initial_delay_seconds)
    if backfill_months:
        await run_backfill(
            months=backfill_months,
            skip_months=backfill_skip_months,
            window_delay_seconds=backfill_window_delay_seconds,
            floor_date=backfill_floor_date,
        )
    while True:
        await run_once()
        await asyncio.sleep(poll_seconds)


async def run_backfill(
    *,
    months: int,
    skip_months: int = 0,
    window_delay_seconds: float = 300,
    floor_date: date = GDELT_DOC_SOURCE_BOUNDARY,
) -> None:
    """Cover history in bounded windows instead of sampling only the latest day."""
    if not 1 <= months <= 180:
        raise ValueError("backfill_months must be between 1 and 180")
    if not 0 <= skip_months <= 180:
        raise ValueError("backfill_skip_months must be between 0 and 180")
    if window_delay_seconds < 0:
        raise ValueError("window_delay_seconds cannot be negative")
    if floor_date < GDELT_DOC_SOURCE_BOUNDARY:
        raise ValueError("backfill floor predates the official DOC 2.0 boundary")
    window_end = datetime.now(UTC) - timedelta(days=30 * skip_months)
    with get_session_factory()() as session:
        earliest_retained = _earliest_gdelt_publication(session)
        state = session.get(GdeltArchiveState, GDELT_DOC_BACKFILL_STATE_KEY)
        if state is not None and state.starts_at is not None:
            state_checkpoint = datetime.combine(
                state.starts_at,
                datetime.min.time(),
                tzinfo=UTC,
            )
            window_end = min(window_end, state_checkpoint)
    if earliest_retained is not None and earliest_retained < window_end:
        window_end = earliest_retained
    for index in range(months):
        boundary = datetime.combine(floor_date, datetime.min.time(), tzinfo=UTC)
        if window_end <= boundary:
            _record_backfill_checkpoint(
                checkpoint=floor_date,
                status="completed_source_boundary",
            )
            break
        window_start = max(window_end - timedelta(days=30), boundary)
        result = await run_once(
            starts_at=window_start,
            ends_at=window_end,
            queue_analysis=index == months - 1,
        )
        errors = [topic.error for topic in result.topics if topic.error]
        if errors:
            _record_backfill_checkpoint(
                checkpoint=window_end.date(),
                status="failed",
                error="; ".join(errors)[:1_800],
            )
            break
        _record_backfill_checkpoint(
            checkpoint=window_start.date(),
            status=(
                "completed_source_boundary"
                if window_start <= boundary
                else "backfilling"
            ),
            rows=result.documents_created,
        )
        window_end = window_start
        if index < months - 1 and window_delay_seconds:
            await asyncio.sleep(window_delay_seconds)


def _record_backfill_checkpoint(
    *,
    checkpoint: date,
    status: str,
    rows: int = 0,
    error: str | None = None,
) -> None:
    with get_session_factory()() as session:
        state = session.get(GdeltArchiveState, GDELT_DOC_BACKFILL_STATE_KEY)
        if state is None:
            state = GdeltArchiveState(
                archive_key=GDELT_DOC_BACKFILL_STATE_KEY,
                source_url=GDELT_DOC_ENDPOINT,
                status=status,
                starts_at=checkpoint,
                ends_at=datetime.now(UTC).date(),
                rows_seen=0,
                aggregates_upserted=0,
                archive_bytes=0,
            )
            session.add(state)
        state.status = status
        state.starts_at = checkpoint
        state.rows_seen += rows
        state.last_started_at = datetime.now(UTC)
        state.last_error = error
        if status in {"backfilling", "completed_source_boundary"}:
            state.last_success_at = datetime.now(UTC)
        session.commit()


def _earliest_gdelt_publication(session: Session) -> datetime | None:
    """Use measured coverage as a restart-safe historical checkpoint."""
    collector_column = Document.raw_metadata["collector"].as_string()
    value = session.scalar(
        select(func.min(Document.published_at)).where(
            collector_column == "gdelt_doc_discovery"
        )
    )
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def main() -> None:
    """Run one discovery pass or the six-hour scheduler."""
    args = build_parser().parse_args()
    if args.poll_seconds is None:
        if args.backfill_months:
            asyncio.run(
                run_backfill(
                    months=args.backfill_months,
                    skip_months=args.backfill_skip_months,
                    window_delay_seconds=args.backfill_window_delay_seconds,
                    floor_date=args.backfill_floor_date,
                )
            )
        else:
            asyncio.run(run_once())
    else:
        asyncio.run(
            run_forever(
                args.poll_seconds,
                initial_delay_seconds=args.initial_delay_seconds,
                backfill_months=args.backfill_months,
                backfill_skip_months=args.backfill_skip_months,
                backfill_window_delay_seconds=args.backfill_window_delay_seconds,
                backfill_floor_date=args.backfill_floor_date,
            )
        )


if __name__ == "__main__":
    main()
