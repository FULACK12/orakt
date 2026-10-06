"""Command-line import for externally licensed historical equity files."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.db.session import get_session_factory
from app.survivorship_import import import_survivorship_csv


def main() -> None:
    parser = argparse.ArgumentParser(prog="newsapp-survivorship-import")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    session_factory = get_session_factory()
    with session_factory() as session:
        try:
            result = import_survivorship_csv(session, args.path)
            session.commit()
        except Exception:
            session.rollback()
            raise
    print(json.dumps(asdict(result), default=str, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
