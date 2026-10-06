"""Scheduled NASA FIRMS thermal-anomaly synchronization."""

from __future__ import annotations

import argparse
import json
import time

import httpx

from app.collectors.cli import build_cold_archive
from app.collectors.firms import FIRMSCollector
from app.core.config import get_settings
from app.db.session import get_session_factory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-firms")
    parser.add_argument("--sources")
    parser.add_argument("--poll-seconds", type=float)
    return parser


def run_once(*, sources: str | None = None) -> None:
    """Collect each configured FIRMS satellite source once."""
    settings = get_settings()
    if settings.nasa_firms_map_key is None:
        raise RuntimeError("NEWSAPP_NASA_FIRMS_MAP_KEY is not configured")
    selected = [
        item.strip()
        for item in (sources or settings.firms_sources).split(",")
        if item.strip()
    ]
    results = []
    with httpx.Client(
        follow_redirects=True,
        timeout=settings.firms_request_timeout_seconds,
    ) as client, get_session_factory()() as session:
        for source in selected:
            collector = FIRMSCollector(
                client,
                map_key=settings.nasa_firms_map_key.get_secret_value(),
                source=source,
                area=settings.firms_area,
                history_days=settings.firms_history_days,
                grid_degrees=settings.firms_grid_degrees,
                max_clusters=settings.firms_max_clusters,
                archive=build_cold_archive(),
            )
            results.append(collector.collect(session).model_dump())
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str), flush=True)


def main() -> None:
    """Run one FIRMS pass or a bounded polling loop."""
    args = build_parser().parse_args()
    if args.poll_seconds is None:
        run_once(sources=args.sources)
        return
    if args.poll_seconds < 300:
        raise ValueError("poll_seconds must be at least 300")
    while True:
        try:
            run_once(sources=args.sources)
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
