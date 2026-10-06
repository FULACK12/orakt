"""Synchronize SEC fundamentals and reviewed US equity prices."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, date, datetime

import httpx

from app.companies import (
    CompanySyncResult,
    sync_company_price_history,
    sync_sec_company_history,
)
from app.core.config import get_settings
from app.db.session import get_session_factory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-companies")
    parser.add_argument(
        "--provider",
        choices=("all", "sec", "prices"),
        default="all",
    )
    parser.add_argument("--poll-seconds", type=float)
    parser.add_argument(
        "--ticker",
        action="append",
        dest="tickers",
        help="Only synchronize the selected ticker; repeat for multiple tickers.",
    )
    return parser


async def run_once(
    *,
    provider: str,
    tickers: set[str] | None = None,
) -> list[CompanySyncResult]:
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
    results: list[CompanySyncResult] = []
    session_factory = get_session_factory()
    if provider in {"all", "sec"}:
        async with httpx.AsyncClient(
            base_url="https://data.sec.gov",
            timeout=120,
            follow_redirects=True,
            headers={
                "User-Agent": sec_user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Accept": "application/json",
            },
        ) as client:
            with session_factory() as session:
                result = await sync_sec_company_history(
                    session,
                    client=client,
                    commit_each_company=True,
                    tickers=tickers,
                )
                session.commit()
                results.append(result)
    if provider in {"all", "prices"}:
        if settings.twelve_data_api_key is None:
            raise RuntimeError("NEWSAPP_TWELVE_DATA_API_KEY is not configured")
        async with httpx.AsyncClient(
            timeout=90,
            follow_redirects=True,
            headers={"User-Agent": "NEWS-Map/0.16 local company research"},
        ) as client:
            with session_factory() as session:
                result = await sync_company_price_history(
                    session,
                    client=client,
                    api_key=settings.twelve_data_api_key.get_secret_value(),
                    history_start=date(
                        settings.company_price_history_start_year,
                        1,
                        1,
                    ),
                    history_end=datetime.now(UTC).date(),
                    commit_each_company=True,
                    tickers=tickers,
                )
                session.commit()
                results.append(result)
    return results


async def run_forever(
    *,
    provider: str,
    poll_seconds: float,
    tickers: set[str] | None = None,
) -> None:
    if poll_seconds < 3_600:
        raise ValueError("poll_seconds must be at least 3600")
    while True:
        try:
            for result in await run_once(provider=provider, tickers=tickers):
                print(result.model_dump_json(indent=2), flush=True)
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            print(f"company synchronization failed: {exc}", flush=True)
        await asyncio.sleep(poll_seconds)


def main() -> None:
    args = build_parser().parse_args()
    tickers = {ticker.strip().upper() for ticker in (args.tickers or []) if ticker.strip()}
    if args.poll_seconds is None:
        for result in asyncio.run(run_once(provider=args.provider, tickers=tickers)):
            print(result.model_dump_json(indent=2), flush=True)
    else:
        asyncio.run(
            run_forever(
                provider=args.provider,
                poll_seconds=args.poll_seconds,
                tickers=tickers,
            )
        )


if __name__ == "__main__":
    main()
