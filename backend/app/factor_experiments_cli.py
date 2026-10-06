"""Scheduled settlement of frozen factor experiments."""

from __future__ import annotations

import argparse
import time

from app.db.session import get_session_factory
from app.factor_experiments import settle_factor_experiments


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=86_400)
    args = parser.parse_args()
    while True:
        with get_session_factory()() as session:
            result = settle_factor_experiments(session)
            session.commit()
            print(
                "factor_experiments="
                f"scanned:{result.scanned},settled:{result.settled},"
                f"pending:{result.still_pending}",
                flush=True,
            )
        if not args.loop:
            return
        time.sleep(max(3_600, args.interval_seconds))


if __name__ == "__main__":
    main()
