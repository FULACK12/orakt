"""Synchronize the Alpha Vantage listing lifecycle catalog."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, time, timedelta

import httpx
from sqlalchemy import func, select

from app.alpha_vantage_listings import (
    ALPHA_VANTAGE_PROVIDER_KEY,
    alpha_vantage_listing_coverage,
    sync_alpha_vantage_lifecycles,
)
from app.alpha_vantage_prices import (
    sync_alpha_vantage_price_backfill,
)
from app.core.config import get_settings
from app.db.models import MarketPriceBackfillState
from app.db.session import get_session_factory
from app.market_delisting_evidence import sync_sec_delisting_evidence
from app.market_identity import sync_openfigi_identities
from app.storage.archive import ColdArchive


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-alpha-listings")
    parser.add_argument("--poll-seconds", type=float)
    return parser


async def run_once() -> None:
    settings = get_settings()
    if settings.alpha_vantage_api_key is None:
        raise RuntimeError("NEWSAPP_ALPHA_VANTAGE_API_KEY is not configured")
    async with httpx.AsyncClient(
        timeout=settings.alpha_vantage_request_timeout_seconds,
        follow_redirects=True,
        headers={"User-Agent": "NEWS-Map/0.19 (+local survivorship research)"},
    ) as client:
        with get_session_factory()() as session:
            try:
                today = datetime.now(UTC).date()
                listing_coverage = alpha_vantage_listing_coverage(session)
                listing_success = listing_coverage["last_success_at"]
                listing_already_synced = bool(
                    listing_coverage["record_count"]
                    and listing_success is not None
                    and listing_success.date() == today
                )
                listing_result = None
                if not listing_already_synced:
                    listing_result = await sync_alpha_vantage_lifecycles(
                        session,
                        client=client,
                        api_key=settings.alpha_vantage_api_key.get_secret_value(),
                        request_interval_seconds=(
                            settings.alpha_vantage_request_interval_seconds
                        ),
                    )
                    session.commit()
                    if not listing_result.errors:
                        await asyncio.sleep(settings.alpha_vantage_request_interval_seconds)

                attempted_today = int(
                    session.scalar(
                        select(func.count())
                        .select_from(MarketPriceBackfillState)
                        .where(
                            MarketPriceBackfillState.last_attempt_at
                            >= datetime.combine(today, time.min, tzinfo=UTC),
                            MarketPriceBackfillState.last_attempt_at
                            < datetime.combine(today, time.min, tzinfo=UTC)
                            + timedelta(days=1),
                        )
                    )
                    or 0
                )
                remaining_budget = max(
                    settings.alpha_vantage_price_backfill_per_day - attempted_today,
                    0,
                )
                archive = ColdArchive(
                    settings.cold_data_root,
                    min_free_bytes=settings.cold_archive_min_free_gb * 1024**3,
                    max_used_percent=settings.cold_archive_max_used_percent,
                )
                price_result = await sync_alpha_vantage_price_backfill(
                    session,
                    client=client,
                    api_key=settings.alpha_vantage_api_key.get_secret_value(),
                    archive=archive,
                    max_assets=remaining_budget,
                    queue_size=settings.alpha_vantage_price_queue_size,
                    request_interval_seconds=settings.alpha_vantage_request_interval_seconds,
                    commit_each_asset=True,
                )
                session.commit()
                identity_result = await sync_openfigi_identities(
                    session,
                    client=client,
                    archive=archive,
                    api_key=(
                        settings.openfigi_api_key.get_secret_value()
                        if settings.openfigi_api_key is not None
                        else None
                    ),
                    max_assets=settings.openfigi_identity_batch_size,
                )
                session.commit()
                evidence_result = await sync_sec_delisting_evidence(
                    session,
                    client=client,
                    archive=archive,
                    user_agent=settings.sec_user_agent,
                    contact_email=(
                        settings.sec_contact_email.get_secret_value()
                        if settings.sec_contact_email is not None
                        else None
                    ),
                    max_assets=settings.sec_delisting_evidence_per_day,
                    request_interval_seconds=(
                        settings.sec_delisting_request_interval_seconds
                    ),
                )
                session.commit()
            except Exception:
                session.rollback()
                raise
    if listing_result is None:
        print(
            f"listing_sync=skipped provider={ALPHA_VANTAGE_PROVIDER_KEY} "
            "reason=already_synced_today",
            flush=True,
        )
    else:
        print(listing_result.model_dump_json(indent=2), flush=True)
    print(price_result.model_dump_json(indent=2), flush=True)
    print(identity_result.model_dump_json(indent=2), flush=True)
    print(evidence_result.model_dump_json(indent=2), flush=True)


async def run_forever(*, poll_seconds: float) -> None:
    if poll_seconds < 3_600:
        raise ValueError("poll_seconds must be at least 3600")
    while True:
        try:
            await run_once()
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            print(f"Alpha Vantage listing synchronization failed: {type(exc).__name__}", flush=True)
        await asyncio.sleep(poll_seconds)


def main() -> None:
    args = build_parser().parse_args()
    if args.poll_seconds is None:
        asyncio.run(run_once())
    else:
        asyncio.run(run_forever(poll_seconds=args.poll_seconds))


if __name__ == "__main__":
    main()
