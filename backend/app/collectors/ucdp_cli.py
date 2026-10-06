"""Scheduled synchronization for versioned UCDP conflict events."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, date, datetime, timedelta

import httpx

from app.collectors.cli import build_cold_archive
from app.collectors.ucdp import UCDPConflictCollector
from app.core.config import get_settings
from app.db.session import get_session_factory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-ucdp")
    parser.add_argument("--poll-seconds", type=float)
    parser.add_argument("--initial-delay-seconds", type=float, default=0)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    return parser


async def run_once(
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> None:
    """Import one bounded UCDP Candidate interval."""
    settings = get_settings()
    if settings.ucdp_access_token is None:
        raise RuntimeError("NEWSAPP_UCDP_ACCESS_TOKEN is not configured")
    selected_end = end_date or datetime.now(UTC).date()
    selected_start = start_date or (
        selected_end - timedelta(days=settings.ucdp_history_days)
    )
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=settings.ucdp_request_timeout_seconds,
    ) as client:
        collector = UCDPConflictCollector(
            client,
            access_token=settings.ucdp_access_token.get_secret_value(),
            dataset_version=settings.ucdp_dataset_version,
            page_size=settings.ucdp_page_size,
            archive=build_cold_archive(),
        )
        with get_session_factory()() as session:
            result = await collector.collect(
                session,
                start_date=selected_start,
                end_date=selected_end,
            )
    print(result.model_dump_json(indent=2), flush=True)


async def run_forever(
    poll_seconds: float,
    *,
    initial_delay_seconds: float = 0,
    start_date: date | None = None,
    end_date: date | None = None,
) -> None:
    if poll_seconds < 3_600:
        raise ValueError("poll_seconds must be at least 3600")
    if initial_delay_seconds < 0:
        raise ValueError("initial_delay_seconds cannot be negative")
    if initial_delay_seconds:
        await asyncio.sleep(initial_delay_seconds)
    while True:
        if start_date is not None and end_date is not None:
            for year in range(start_date.year, end_date.year + 1):
                selected_start = max(start_date, date(year, 1, 1))
                selected_end = min(end_date, date(year, 12, 31))
                await run_once(
                    start_date=selected_start,
                    end_date=selected_end,
                )
        else:
            await run_once()
        await asyncio.sleep(poll_seconds)


def main() -> None:
    """Run one UCDP pass or the configured scheduler."""
    args = build_parser().parse_args()
    if args.poll_seconds is None:
        asyncio.run(
            run_once(
                start_date=args.start_date,
                end_date=args.end_date,
            )
        )
        return
    if (args.start_date is None) != (args.end_date is None):
        raise ValueError("both fixed dates are required when polling historical data")
    asyncio.run(
        run_forever(
            args.poll_seconds,
            initial_delay_seconds=args.initial_delay_seconds,
            start_date=args.start_date,
            end_date=args.end_date,
        )
    )


if __name__ == "__main__":
    main()
