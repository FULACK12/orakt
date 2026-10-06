"""Scheduled SEC Form 4 ownership XML archive and parser."""

from __future__ import annotations

import argparse
import asyncio

import httpx

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.insider_history import InsiderSyncResult, sync_sec_form4_filings
from app.storage.archive import ColdArchive


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-insider-history")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--poll-seconds", type=float)
    parser.add_argument(
        "--backlog-pause-seconds",
        type=float,
        default=5,
        help="Pause between full batches while historical backlog remains.",
    )
    parser.add_argument(
        "--ticker",
        action="append",
        dest="tickers",
        help="Only process this ticker; repeat to select more than one.",
    )
    return parser


async def run_once(*, batch_size: int, tickers: set[str]) -> InsiderSyncResult:
    settings = get_settings()
    sec_contact = (
        settings.sec_contact_email.get_secret_value()
        if settings.sec_contact_email is not None
        else None
    )
    sec_user_agent = (
        f"{settings.sec_user_agent} {sec_contact}"
        if sec_contact
        else settings.sec_user_agent
    )
    archive = ColdArchive(
        settings.cold_data_root,
        min_free_bytes=settings.cold_archive_min_free_gb * 1024**3,
        max_used_percent=settings.cold_archive_max_used_percent,
    )
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(90, read=90),
        follow_redirects=True,
        headers={
            "User-Agent": sec_user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.1",
        },
    ) as client:
        with get_session_factory()() as session:
            result = await sync_sec_form4_filings(
                session,
                client=client,
                archive=archive,
                tickers=tickers,
                batch_size=batch_size,
            )
    print(result.model_dump_json(indent=2), flush=True)
    return result


async def run_forever(
    *,
    batch_size: int,
    poll_seconds: float,
    backlog_pause_seconds: float,
    tickers: set[str],
) -> None:
    if poll_seconds < 60:
        raise ValueError("poll_seconds must be at least 60")
    if not 1 <= backlog_pause_seconds <= 60:
        raise ValueError("backlog_pause_seconds must be between 1 and 60")
    while True:
        try:
            result = await run_once(batch_size=batch_size, tickers=tickers)
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            print(f"Form 4 synchronization failed: {exc}", flush=True)
            await asyncio.sleep(poll_seconds)
            continue
        await asyncio.sleep(
            backlog_pause_seconds
            if result.filings_selected >= batch_size
            else poll_seconds
        )


def main() -> None:
    args = build_parser().parse_args()
    tickers = {
        ticker.strip().upper() for ticker in (args.tickers or []) if ticker.strip()
    }
    if args.poll_seconds is None:
        asyncio.run(run_once(batch_size=args.batch_size, tickers=tickers))
    else:
        asyncio.run(
            run_forever(
                batch_size=args.batch_size,
                poll_seconds=args.poll_seconds,
                backlog_pause_seconds=args.backlog_pause_seconds,
                tickers=tickers,
            )
        )


if __name__ == "__main__":
    main()
