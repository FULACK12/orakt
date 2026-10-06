"""Archive SEC annual and quarterly filings used by product-operating evidence."""

from __future__ import annotations

import argparse
import asyncio
from datetime import date

import httpx

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.product_evidence import archive_product_operating_filings
from app.storage.archive import ColdArchive


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-product-evidence")
    parser.add_argument("--ticker", action="append", dest="tickers", required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--quarterly-periods", type=int, default=4)
    return parser


async def run_once(
    *,
    tickers: set[str],
    as_of: date,
    quarterly_periods: int,
) -> None:
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
            result = await archive_product_operating_filings(
                session,
                client=client,
                archive=archive,
                tickers=tickers,
                as_of=as_of,
                quarterly_periods=quarterly_periods,
            )
    print(result.model_dump_json(indent=2), flush=True)


def main() -> None:
    args = build_parser().parse_args()
    tickers = {item.strip().upper() for item in args.tickers if item.strip()}
    asyncio.run(
        run_once(
            tickers=tickers,
            as_of=args.as_of,
            quarterly_periods=args.quarterly_periods,
        )
    )


if __name__ == "__main__":
    main()
