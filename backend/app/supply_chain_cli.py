"""Scheduled SEC annual-filing archive and named supply-chain candidate discovery."""

from __future__ import annotations

import argparse
import asyncio

import httpx

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.storage.archive import ColdArchive
from app.supply_chain_discovery import (
    SupplyChainDiscoveryResult,
    discover_sec_supply_chain_candidates,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-supply-chain")
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--poll-seconds", type=float)
    parser.add_argument("--backlog-pause-seconds", type=float, default=5)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--ticker", action="append", dest="tickers")
    return parser


async def run_once(
    *,
    batch_size: int,
    tickers: set[str],
    force: bool,
) -> SupplyChainDiscoveryResult:
    settings = get_settings()
    sec_contact = (
        settings.sec_contact_email.get_secret_value()
        if settings.sec_contact_email is not None
        else None
    )
    user_agent = (
        f"{settings.sec_user_agent} {sec_contact}" if sec_contact else settings.sec_user_agent
    )
    archive = ColdArchive(
        settings.cold_data_root,
        min_free_bytes=settings.cold_archive_min_free_gb * 1024**3,
        max_used_percent=settings.cold_archive_max_used_percent,
    )
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(120, read=120),
        follow_redirects=True,
        headers={
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
        },
    ) as client:
        with get_session_factory()() as session:
            result = await discover_sec_supply_chain_candidates(
                session,
                client=client,
                archive=archive,
                tickers=tickers,
                batch_size=batch_size,
                force=force,
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
    if poll_seconds < 300:
        raise ValueError("poll_seconds must be at least 300")
    if not 1 <= backlog_pause_seconds <= 60:
        raise ValueError("backlog_pause_seconds must be between 1 and 60")
    while True:
        try:
            result = await run_once(
                batch_size=batch_size,
                tickers=tickers,
                force=False,
            )
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            print(f"supply-chain discovery failed: {exc}", flush=True)
            await asyncio.sleep(poll_seconds)
            continue
        await asyncio.sleep(
            backlog_pause_seconds if result.filings_selected >= batch_size else poll_seconds
        )


def main() -> None:
    args = build_parser().parse_args()
    tickers = {ticker.strip().upper() for ticker in (args.tickers or []) if ticker.strip()}
    if args.poll_seconds is None:
        asyncio.run(
            run_once(
                batch_size=args.batch_size,
                tickers=tickers,
                force=args.force,
            )
        )
    else:
        if args.force:
            raise ValueError("--force is only supported for a one-shot run")
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
