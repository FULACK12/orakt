"""Scheduled SEC Form 13F cold archive and reviewed-issuer import."""

from __future__ import annotations

import argparse
import asyncio

import httpx

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.institutional_history import sync_sec_13f_archives


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-institutional-history")
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--poll-seconds", type=float)
    parser.add_argument("--backlog-pause-seconds", type=float, default=5)
    return parser


async def run_once(*, batch_size: int) -> int:
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
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(900, read=900),
        follow_redirects=True,
        headers={"User-Agent": sec_user_agent},
    ) as client:
        with get_session_factory()() as session:
            states = await sync_sec_13f_archives(
                session,
                client=client,
                cold_root=settings.cold_data_root,
                min_free_bytes=settings.cold_archive_min_free_gb * 1024**3,
                batch_size=batch_size,
            )
    print(
        " ".join(
            f"{state.archive_key}={state.status}:{state.holdings_upserted}"
            for state in states
        )
        or "SEC 13F source boundary already reached",
        flush=True,
    )
    return len(states)


async def run_forever(
    *,
    batch_size: int,
    poll_seconds: float,
    backlog_pause_seconds: float,
) -> None:
    if poll_seconds < 300:
        raise ValueError("poll_seconds must be at least 300")
    if not 1 <= backlog_pause_seconds <= 60:
        raise ValueError("backlog_pause_seconds must be between 1 and 60")
    while True:
        processed = await run_once(batch_size=batch_size)
        await asyncio.sleep(
            backlog_pause_seconds if processed >= batch_size else poll_seconds
        )


def main() -> None:
    args = build_parser().parse_args()
    if args.poll_seconds is None:
        asyncio.run(run_once(batch_size=args.batch_size))
    else:
        asyncio.run(
            run_forever(
                batch_size=args.batch_size,
                poll_seconds=args.poll_seconds,
                backlog_pause_seconds=args.backlog_pause_seconds,
            )
        )


if __name__ == "__main__":
    main()
