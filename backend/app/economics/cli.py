"""Command-line synchronization for official World Bank economic data."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime

import httpx
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.models import EconomicObservation, EconomicSyncState
from app.db.session import get_session_factory
from app.economics.world_bank import (
    SOURCE_KEY,
    WorldBankClient,
    record_sync_failure,
    sync_world_bank,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the economic data command-line interface."""
    settings = get_settings()
    parser = argparse.ArgumentParser(prog="newsapp-economics")
    subparsers = parser.add_subparsers(dest="command", required=True)
    sync_parser = subparsers.add_parser(
        "sync",
        help="Synchronize a validated historical date range once",
    )
    sync_parser.add_argument(
        "--start-year",
        type=int,
        default=settings.economic_history_start_year,
    )
    sync_parser.add_argument(
        "--end-year",
        type=int,
        default=datetime.now(UTC).year,
    )
    run_parser = subparsers.add_parser(
        "run",
        help="Run an initial backfill followed by periodic refreshes",
    )
    run_parser.add_argument(
        "--poll-seconds",
        type=float,
        default=float(settings.economic_sync_interval_seconds),
    )
    return parser


async def run_sync(*, start_year: int, end_year: int) -> None:
    """Run one transactionally safe provider synchronization."""
    settings = get_settings()
    timeout = httpx.Timeout(settings.economic_request_timeout_seconds)
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "NEWS-App/0.15 (+local economic research)"},
    ) as http_client:
        client = WorldBankClient(
            http_client,
            base_url=str(settings.economic_base_url),
        )
        with get_session_factory()() as session:
            try:
                result = await sync_world_bank(
                    session,
                    client,
                    start_year=start_year,
                    end_year=end_year,
                )
                session.commit()
            except Exception as exc:
                session.rollback()
                record_sync_failure(
                    session,
                    start_year=start_year,
                    end_year=end_year,
                    error=exc,
                )
                session.commit()
                raise
        print(result.model_dump_json(indent=2))


async def run_forever(*, poll_seconds: float) -> None:
    """Backfill once, then refresh the most recent five years."""
    if poll_seconds < 300:
        raise ValueError("poll_seconds must be at least 300")
    settings = get_settings()
    while True:
        current_year = datetime.now(UTC).year
        with get_session_factory()() as session:
            observation_count = session.scalar(
                select(func.count()).select_from(EconomicObservation)
            )
            oldest_year = session.scalar(select(func.min(EconomicObservation.year)))
            sync_state = session.get(EconomicSyncState, SOURCE_KEY)
        needs_source_boundary_backfill = (
            not observation_count
            or oldest_year is None
            or oldest_year > settings.economic_history_start_year
            or (sync_state is not None and sync_state.last_error is not None)
        )
        start_year = (
            settings.economic_history_start_year
            if needs_source_boundary_backfill
            else current_year - 5
        )
        try:
            await run_sync(start_year=start_year, end_year=current_year)
        except (httpx.HTTPError, ValueError) as exc:
            print(f"economic synchronization failed: {exc}")
        await asyncio.sleep(poll_seconds)


def main() -> None:
    """Parse arguments and start one-shot or scheduled synchronization."""
    args = build_parser().parse_args()
    if args.command == "sync":
        asyncio.run(
            run_sync(
                start_year=args.start_year,
                end_year=args.end_year,
            )
        )
        return
    asyncio.run(run_forever(poll_seconds=args.poll_seconds))


if __name__ == "__main__":
    main()
