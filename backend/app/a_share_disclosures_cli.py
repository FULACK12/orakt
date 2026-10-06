"""Continuously archive official CNINFO disclosures for active A-share leaders."""

from __future__ import annotations

import argparse
import asyncio
from datetime import date

import httpx

from app.a_share_disclosures import (
    CNINFO_BASE_URL,
    backfill_structured_disclosure_evidence,
    sync_a_share_disclosures,
)
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.storage.archive import ColdArchive


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-a-share-disclosures")
    parser.add_argument("--ticker", action="append", dest="tickers")
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2024, 1, 1))
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--poll-seconds", type=int, default=21_600)
    parser.add_argument("--backlog-pause-seconds", type=int, default=10)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--enrichment-batch-size", type=int, default=50)
    return parser


async def run_forever(args: argparse.Namespace) -> None:
    settings = get_settings()
    archive = ColdArchive(
        settings.cold_data_root,
        min_free_bytes=settings.cold_archive_min_free_gb * 1024**3,
        max_used_percent=settings.cold_archive_max_used_percent,
    )
    headers = {
        "User-Agent": "Mozilla/5.0 NEWS-Map/0.23 personal-local-research",
        "Referer": f"{CNINFO_BASE_URL}/new/index",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    }
    async with httpx.AsyncClient(
        base_url=CNINFO_BASE_URL,
        timeout=httpx.Timeout(120, read=120),
        follow_redirects=True,
        headers=headers,
    ) as client:
        while True:
            with get_session_factory()() as session:
                enrichment = backfill_structured_disclosure_evidence(
                    session,
                    archive=archive,
                    limit=args.enrichment_batch_size,
                )
                result = await sync_a_share_disclosures(
                    session,
                    client=client,
                    archive=archive,
                    start_date=args.start_date,
                    end_date=args.end_date or date.today(),
                    batch_size=args.batch_size,
                    tickers={item.strip() for item in (args.tickers or []) if item.strip()},
                    force=args.force,
                )
            print(
                {
                    "structured_enrichment": enrichment.model_dump(),
                    "disclosure_sync": result.model_dump(),
                },
                flush=True,
            )
            if (
                result.companies_selected >= args.batch_size
                or enrichment.documents_enriched >= args.enrichment_batch_size
            ):
                await asyncio.sleep(max(args.backlog_pause_seconds, 1))
            else:
                await asyncio.sleep(max(args.poll_seconds, 300))


def main() -> None:
    asyncio.run(run_forever(build_parser().parse_args()))


if __name__ == "__main__":
    main()
