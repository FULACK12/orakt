"""Scheduled EIA public bulk archive download and selective import."""

from __future__ import annotations

import argparse
import json
import time

import httpx

from app.collectors.cli import build_cold_archive
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.energy.bulk import sync_eia_bulk


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-energy-bulk")
    parser.add_argument("--datasets")
    parser.add_argument("--poll-seconds", type=float)
    parser.add_argument("--force-download", action="store_true")
    return parser


def run_once(
    *,
    datasets: str | None = None,
    force_download: bool = False,
) -> None:
    """Download and import one manifest-driven EIA batch."""
    settings = get_settings()
    selected = [
        item.strip()
        for item in (datasets or settings.eia_bulk_datasets).split(",")
        if item.strip()
    ]
    with httpx.Client(
        follow_redirects=True,
        timeout=settings.eia_bulk_request_timeout_seconds,
    ) as client, get_session_factory()() as session:
        result = sync_eia_bulk(
            session,
            client,
            archive=build_cold_archive(),
            dataset_keys=selected,
            max_series_per_dataset=(
                settings.eia_bulk_max_series_per_dataset
            ),
            max_observations_per_series=(
                settings.eia_bulk_max_observations_per_series
            ),
            force_download=force_download,
        )
    print(result.model_dump_json(indent=2), flush=True)


def main() -> None:
    """Run once or poll the EIA bulk manifest on a bounded interval."""
    args = build_parser().parse_args()
    if args.poll_seconds is None:
        run_once(
            datasets=args.datasets,
            force_download=args.force_download,
        )
        return
    if args.poll_seconds < 3_600:
        raise ValueError("poll_seconds must be at least 3600")
    while True:
        try:
            run_once(
                datasets=args.datasets,
                force_download=args.force_download,
            )
        except (httpx.HTTPError, OSError, TypeError, ValueError) as exc:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error": type(exc).__name__,
                    }
                ),
                flush=True,
            )
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
