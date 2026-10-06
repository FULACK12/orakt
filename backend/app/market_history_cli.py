"""Synchronize retained FRED market history on a bounded schedule."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, date, datetime

import httpx

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.market_history import sync_fred_history, sync_twelve_data_history


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-market-history")
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2000, 1, 1))
    parser.add_argument("--poll-seconds", type=float)
    parser.add_argument(
        "--provider",
        choices=("all", "fred", "twelve"),
        default="all",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="For Twelve Data, backfill catalog symbols with no local observations only",
    )
    parser.add_argument(
        "--twelve-request-interval-seconds",
        type=float,
        default=16.0,
        help="Pacing between Twelve Data requests; minimum 8 seconds",
    )
    return parser


async def run_once(
    *,
    start_date: date,
    provider: str = "all",
    only_missing: bool = False,
    twelve_request_interval_seconds: float = 16.0,
) -> None:
    if twelve_request_interval_seconds < 8:
        raise ValueError("twelve_request_interval_seconds must be at least 8")
    settings = get_settings()
    fred_key = (
        settings.fred_api_key.get_secret_value() if settings.fred_api_key is not None else None
    )
    twelve_key = (
        settings.twelve_data_api_key.get_secret_value()
        if settings.twelve_data_api_key is not None
        else None
    )
    if provider in {"all", "fred"} and fred_key is None:
        raise RuntimeError("NEWSAPP_FRED_API_KEY is not configured")
    if provider in {"all", "twelve"} and twelve_key is None:
        raise RuntimeError("NEWSAPP_TWELVE_DATA_API_KEY is not configured")
    async with httpx.AsyncClient(
        timeout=90,
        follow_redirects=True,
        headers={"User-Agent": "NEWS-Map/0.15 (+local market research)"},
    ) as client:
        with get_session_factory()() as session:
            results = []
            try:
                if provider in {"all", "fred"}:
                    results.append(
                        await sync_fred_history(
                            session,
                            client=client,
                            api_key=fred_key or "",
                            history_start=start_date,
                            history_end=datetime.now(UTC).date(),
                        )
                    )
                if provider in {"all", "twelve"}:
                    results.append(
                        await sync_twelve_data_history(
                            session,
                            client=client,
                            api_key=twelve_key or "",
                            history_start=start_date,
                            history_end=datetime.now(UTC).date(),
                            request_interval_seconds=twelve_request_interval_seconds,
                            only_missing=only_missing,
                            commit_each_series=True,
                        )
                    )
                session.commit()
            except Exception:
                session.rollback()
                raise
    for result in results:
        print(result.model_dump_json(indent=2), flush=True)


async def run_forever(
    *,
    start_date: date,
    poll_seconds: float,
    provider: str = "all",
    only_missing: bool = False,
    twelve_request_interval_seconds: float = 16.0,
) -> None:
    if poll_seconds < 3_600:
        raise ValueError("poll_seconds must be at least 3600")
    while True:
        try:
            await run_once(
                start_date=start_date,
                provider=provider,
                only_missing=only_missing,
                twelve_request_interval_seconds=twelve_request_interval_seconds,
            )
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            print(f"market history synchronization failed: {exc}", flush=True)
        await asyncio.sleep(poll_seconds)


def main() -> None:
    args = build_parser().parse_args()
    if args.poll_seconds is None:
        asyncio.run(
            run_once(
                start_date=args.start_date,
                provider=args.provider,
                only_missing=args.only_missing,
                twelve_request_interval_seconds=args.twelve_request_interval_seconds,
            )
        )
    else:
        asyncio.run(
            run_forever(
                start_date=args.start_date,
                poll_seconds=args.poll_seconds,
                provider=args.provider,
                only_missing=args.only_missing,
                twelve_request_interval_seconds=args.twelve_request_interval_seconds,
            )
        )


if __name__ == "__main__":
    main()
