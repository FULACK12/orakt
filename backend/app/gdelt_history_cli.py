"""Download and materialize the full GDELT 1979-2013 event archive."""

from __future__ import annotations

import argparse
import time

import httpx

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.gdelt_history import sync_gdelt_daily_batch, sync_gdelt_master_history


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-gdelt-history")
    parser.add_argument("--batch-days", type=int, default=30)
    parser.add_argument("--poll-seconds", type=float)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = get_settings()
    while True:
        try:
            with httpx.Client(
                timeout=httpx.Timeout(900, read=900),
                follow_redirects=True,
                headers={"User-Agent": "NEWS-Map/0.16 historical event research"},
            ) as client, get_session_factory()() as session:
                state = sync_gdelt_master_history(
                    session,
                    client=client,
                    cold_root=settings.cold_data_root,
                    min_free_bytes=settings.cold_archive_min_free_gb * 1024**3,
                )
                daily = sync_gdelt_daily_batch(
                    session,
                    client=client,
                    cold_root=settings.cold_data_root,
                    min_free_bytes=settings.cold_archive_min_free_gb * 1024**3,
                    batch_days=args.batch_days,
                )
                print(
                    f"master={state.status} master_rows={state.rows_seen} "
                    f"daily_completed={len(daily)} "
                    f"daily_end={daily[-1].ends_at if daily else 'unchanged'}",
                    flush=True,
                )
        except (httpx.HTTPError, OSError, ValueError) as exc:
            print(f"GDELT historical synchronization failed: {exc}", flush=True)
        if args.poll_seconds is None:
            break
        if args.poll_seconds < 300:
            raise ValueError("poll_seconds must be at least 300")
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
