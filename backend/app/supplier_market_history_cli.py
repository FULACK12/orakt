"""Continuously fill market history for verified public suppliers."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, date, datetime

import httpx

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.supplier_company_discovery import sync_supplier_company_profiles_from_sec
from app.supplier_market_history import sync_missing_supplier_market_history


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-supplier-market-history")
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--poll-seconds", type=float)
    parser.add_argument("--backlog-pause-seconds", type=float, default=60)
    return parser


async def run_once(*, batch_size: int) -> dict[str, object]:
    settings = get_settings()
    if settings.twelve_data_api_key is None:
        raise RuntimeError("NEWSAPP_TWELVE_DATA_API_KEY is not configured")
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
        timeout=90,
        follow_redirects=True,
        headers={
            "User-Agent": sec_user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json",
        },
    ) as sec_client:
        with get_session_factory()() as session:
            profile_result = await sync_supplier_company_profiles_from_sec(
                session,
                client=sec_client,
            )
            session.commit()
    async with httpx.AsyncClient(
        timeout=90,
        follow_redirects=True,
        headers={"User-Agent": "NEWS-Map/0.22 local supplier market research"},
    ) as client:
        with get_session_factory()() as session:
            market_result = await sync_missing_supplier_market_history(
                session,
                client=client,
                api_key=settings.twelve_data_api_key.get_secret_value(),
                history_start=date(settings.company_price_history_start_year, 1, 1),
                history_end=datetime.now(UTC).date(),
                batch_size=batch_size,
                request_interval_seconds=16.0,
                commit_each_ticker=True,
            )
            session.commit()
    return {
        "profile_discovery": profile_result.model_dump(),
        "market_history": market_result.model_dump(),
    }


async def run_forever(
    *,
    batch_size: int,
    poll_seconds: float,
    backlog_pause_seconds: float,
) -> None:
    if poll_seconds < 3_600:
        raise ValueError("poll_seconds must be at least 3600")
    if backlog_pause_seconds < 5:
        raise ValueError("backlog_pause_seconds must be at least 5")
    while True:
        try:
            result = await run_once(batch_size=batch_size)
            print(result, flush=True)
            selected = result["market_history"]["selected_tickers"]
            delay = backlog_pause_seconds if selected else poll_seconds
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            print(f"supplier market synchronization failed: {exc}", flush=True)
            delay = poll_seconds
        await asyncio.sleep(delay)


def main() -> None:
    args = build_parser().parse_args()
    if args.poll_seconds is None:
        print(asyncio.run(run_once(batch_size=args.batch_size)), flush=True)
        return
    asyncio.run(
        run_forever(
            batch_size=args.batch_size,
            poll_seconds=args.poll_seconds,
            backlog_pause_seconds=args.backlog_pause_seconds,
        )
    )


if __name__ == "__main__":
    main()
