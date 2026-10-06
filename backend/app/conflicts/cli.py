"""Watch the local ACLED download directory and import changed workbooks."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from app.conflicts.acled_aggregate import import_acled_directory
from app.core.config import get_settings
from app.db.session import get_session_factory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-acled-aggregate")
    parser.add_argument("--directory")
    parser.add_argument("--history-days", type=int)
    parser.add_argument("--poll-seconds", type=float)
    return parser


def run_once(*, directory: str | None = None, history_days: int | None = None) -> None:
    """Import all changed ACLED aggregate workbooks once."""
    settings = get_settings()
    root = Path(directory) if directory else settings.cold_data_root / "raw" / "acled"
    with get_session_factory()() as session:
        results = import_acled_directory(
            session,
            directory=root,
            history_days=history_days or settings.acled_aggregate_history_days,
        )
    print(
        json.dumps(
            [result.model_dump(mode="json") for result in results],
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


def main() -> None:
    """Import once or poll for browser-downloaded workbook updates."""
    args = build_parser().parse_args()
    if args.poll_seconds is None:
        run_once(directory=args.directory, history_days=args.history_days)
        return
    if args.poll_seconds < 300:
        raise ValueError("poll_seconds must be at least 300")
    while True:
        try:
            run_once(directory=args.directory, history_days=args.history_days)
        except (OSError, TypeError, ValueError) as exc:
            print(
                json.dumps({"status": "error", "error": type(exc).__name__}),
                flush=True,
            )
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
