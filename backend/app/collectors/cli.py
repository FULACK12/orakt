"""Command-line entrypoint for feed configuration and collection."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import httpx
from sqlalchemy import select

from app.cluster_queue import ensure_incremental_cluster_job
from app.collectors.config import apply_rss_config, load_rss_config
from app.collectors.fulltext import expand_full_text_batch
from app.collectors.rss import RSSCollector
from app.collectors.scheduler import RSSScheduler
from app.core.config import get_settings
from app.db.models import Document
from app.db.session import get_session_factory
from app.embeddings import build_embedding_client
from app.extractors import build_event_extractor
from app.storage.archive import ColdArchive
from app.storage.document_tiering import tier_document_batch


def build_parser() -> argparse.ArgumentParser:
    """Build the RSS command-line interface."""
    parser = argparse.ArgumentParser(prog="newsapp-rss")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser(
        "import-config",
        help="Validate and import a JSON feed configuration",
    )
    import_parser.add_argument("path", type=Path)

    once_parser = subparsers.add_parser("run-once", help="Collect all due feeds once")
    once_parser.add_argument("--force", action="store_true")

    run_parser = subparsers.add_parser("run", help="Run the local polling scheduler")
    run_parser.add_argument("--poll-seconds", type=float, default=30)

    cleanup_parser = subparsers.add_parser(
        "cleanup-archive",
        help="Reconcile cold archive files against database references",
    )
    cleanup_parser.add_argument(
        "--apply",
        action="store_true",
        help="Delete unreferenced managed archive files; default is a dry run",
    )
    tier_parser = subparsers.add_parser(
        "tier-documents",
        help="Archive complete bodies, verify them, then retain hot excerpts",
    )
    tier_parser.add_argument("--apply", action="store_true")
    tier_parser.add_argument("--batch-size", type=int, default=500)
    tier_parser.add_argument("--limit", type=int, default=0)
    tier_parser.add_argument("--hot-body-chars", type=int, default=None)
    fulltext_parser = subparsers.add_parser(
        "expand-fulltext",
        help="Retrieve permitted publisher pages and archive expanded article text",
    )
    fulltext_parser.add_argument("--batch-size", type=int, default=None)
    fulltext_parser.add_argument("--poll-seconds", type=float, default=None)
    fulltext_parser.add_argument("--domain", action="append", default=None)
    fulltext_parser.add_argument(
        "--document-id",
        action="append",
        type=int,
        default=None,
        help="Expand only the specified document id; repeat for a bounded repair set",
    )
    fulltext_parser.add_argument("--force", action="store_true")
    return parser


def build_cold_archive() -> ColdArchive:
    """Build the capacity-aware archive from validated settings."""
    settings = get_settings()
    return ColdArchive(
        settings.cold_data_root,
        min_free_bytes=settings.cold_archive_min_free_gb * 1024**3,
        max_used_percent=settings.cold_archive_max_used_percent,
    )


async def run_collection(*, force: bool = False, poll_seconds: float | None = None) -> None:
    """Run one pass or a long-lived scheduler with one shared HTTP client."""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        scheduler = RSSScheduler(
            get_session_factory(),
            RSSCollector(
                client,
                archive=build_cold_archive(),
                hot_body_chars=get_settings().hot_document_body_chars,
            ),
            analysis_extractor_name=build_event_extractor().name,
            analysis_embedding_provider=build_embedding_client().name,
        )
        if poll_seconds is None:
            result = await scheduler.run_once(force=force)
            print(result.model_dump_json(indent=2))
            return

        stop_event = asyncio.Event()
        try:
            await scheduler.run_forever(stop_event, poll_seconds=poll_seconds)
        except KeyboardInterrupt:
            stop_event.set()


async def run_fulltext_expansion(
    *,
    batch_size: int | None,
    poll_seconds: float | None,
    publisher_domains: tuple[str, ...] | None,
    document_ids: tuple[int, ...] | None,
    force: bool,
) -> None:
    """Continuously expand short feed records from ordinary publisher pages."""
    settings = get_settings()
    interval = poll_seconds or settings.fulltext_sync_interval_seconds
    timeout = httpx.Timeout(settings.fulltext_request_timeout_seconds)
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        while True:
            with get_session_factory()() as session:
                result = await expand_full_text_batch(
                    session,
                    client=client,
                    archive=build_cold_archive(),
                    batch_size=batch_size or settings.fulltext_batch_size,
                    min_full_text_chars=settings.fulltext_min_chars,
                    verified_short_min_chars=settings.fulltext_verified_short_min_chars,
                    hot_body_chars=settings.hot_document_body_chars,
                    user_agent=settings.fulltext_user_agent,
                    max_response_bytes=settings.fulltext_max_response_bytes,
                    retry_after_days=settings.fulltext_retry_after_days,
                    max_concurrency=settings.fulltext_max_concurrency,
                    domain_delay_seconds=settings.fulltext_domain_delay_seconds,
                    publisher_domains=publisher_domains,
                    document_ids=document_ids,
                    force=force,
                )
                cluster_job_id = ensure_incremental_cluster_job(
                    session,
                    extractor_name=build_event_extractor(settings).name,
                    embedding_provider=build_embedding_client(settings).name,
                )
                session.commit()
            print(
                json.dumps(
                    {
                        **result.model_dump(mode="json"),
                        "cluster_job_id": cluster_job_id,
                    }
                )
            )
            if poll_seconds is None:
                return
            await asyncio.sleep(interval)


def main() -> None:
    """Parse arguments and run the selected operation."""
    args = build_parser().parse_args()
    if args.command == "import-config":
        config = load_rss_config(args.path)
        with get_session_factory()() as session:
            import_result = apply_rss_config(session, config)
            session.commit()
        print(import_result.model_dump_json(indent=2))
        return
    if args.command == "run-once":
        asyncio.run(run_collection(force=args.force))
        return
    if args.command == "cleanup-archive":
        with get_session_factory()() as session:
            referenced_paths = session.scalars(
                select(Document.raw_object_path).where(Document.raw_object_path.is_not(None))
            ).all()
        cleanup_result = build_cold_archive().cleanup_orphans(
            (path for path in referenced_paths if path is not None),
            apply=args.apply,
        )
        print(cleanup_result.model_dump_json(indent=2))
        return
    if args.command == "tier-documents":
        settings = get_settings()
        archive = build_cold_archive()
        after_id = 0
        total_scanned = 0
        totals = {
            "archived": 0,
            "verified_existing": 0,
            "hot_bodies_trimmed": 0,
            "hot_characters_released": 0,
            "failures": 0,
        }
        with get_session_factory()() as session:
            while True:
                remaining = max(0, args.limit - total_scanned) if args.limit else args.batch_size
                if args.limit and remaining == 0:
                    break
                result = tier_document_batch(
                    session,
                    archive,
                    after_id=after_id,
                    batch_size=min(args.batch_size, remaining),
                    hot_body_chars=(args.hot_body_chars or settings.hot_document_body_chars),
                    apply=args.apply,
                )
                total_scanned += result.scanned
                for key in totals:
                    totals[key] += int(getattr(result, key))
                if args.apply:
                    session.commit()
                else:
                    session.rollback()
                if result.last_document_id is None or result.scanned == 0:
                    break
                after_id = result.last_document_id
                if result.scanned < min(args.batch_size, remaining):
                    break
        print(
            json.dumps(
                {
                    "dry_run": not args.apply,
                    "scanned": total_scanned,
                    **totals,
                    "last_document_id": after_id or None,
                },
                indent=2,
            )
        )
        return
    if args.command == "expand-fulltext":
        asyncio.run(
            run_fulltext_expansion(
                batch_size=args.batch_size,
                poll_seconds=args.poll_seconds,
                publisher_domains=tuple(args.domain) if args.domain else None,
                document_ids=tuple(args.document_id) if args.document_id else None,
                force=args.force,
            )
        )
        return
    asyncio.run(run_collection(poll_seconds=args.poll_seconds))


if __name__ == "__main__":
    main()
