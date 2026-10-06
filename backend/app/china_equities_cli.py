"""Scheduled CSI 800 proxy sector-leader discovery and A-share history sync."""

from __future__ import annotations

import argparse
import time
from datetime import UTC, date, datetime

from app.china_equities import sync_china_equity_leaders
from app.core.config import get_settings
from app.db.session import get_session_factory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-china-equities")
    parser.add_argument("--poll-seconds", type=float)
    parser.add_argument("--history-start-year", type=int)
    parser.add_argument("--leaders-per-sector", type=int)
    return parser


def run_once(*, history_start_year: int, leaders_per_sector: int) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        result = sync_china_equity_leaders(
            session,
            history_start=date(history_start_year, 1, 1),
            history_end=datetime.now(UTC).date(),
            leaders_per_sector=leaders_per_sector,
            ranking_days=settings.china_equity_ranking_days,
            commit_each_leader=True,
        )
        session.commit()
        print(result.model_dump_json(indent=2), flush=True)


def main() -> None:
    args = build_parser().parse_args()
    settings = get_settings()
    start_year = args.history_start_year or settings.china_equity_history_start_year
    leaders = args.leaders_per_sector or settings.china_equity_leaders_per_sector
    poll_seconds = args.poll_seconds
    if poll_seconds is None:
        run_once(history_start_year=start_year, leaders_per_sector=leaders)
        return
    if poll_seconds < 3_600:
        raise ValueError("poll-seconds must be at least 3600")
    while True:
        try:
            run_once(history_start_year=start_year, leaders_per_sector=leaders)
        except (RuntimeError, TypeError, ValueError) as exc:
            print(f"china equity synchronization failed: {exc}", flush=True)
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
