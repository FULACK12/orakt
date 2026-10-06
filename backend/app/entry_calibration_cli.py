"""Scheduled command for the durable entry-scenario calibration loop."""

from __future__ import annotations

import argparse
import time

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.entry_calibration import run_entry_calibration


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-entry-calibration")
    parser.add_argument(
        "--poll-seconds",
        type=float,
        help="Repeat reconciliation on this interval; minimum 3600 seconds",
    )
    return parser


def run_once() -> dict[str, object]:
    settings = get_settings()
    with get_session_factory()() as session:
        result = run_entry_calibration(session, settings=settings)
        session.commit()
    print(
        "entry_calibration="
        f"forecasts:{result['forecasts_created']} "
        f"settled:{result['outcomes_settled']} "
        f"pending:{result['pending_forecasts']}",
        flush=True,
    )
    return result


def main() -> None:
    args = build_parser().parse_args()
    if args.poll_seconds is not None and args.poll_seconds < 3_600:
        raise ValueError("poll_seconds must be at least 3600")
    while True:
        run_once()
        if args.poll_seconds is None:
            return
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
