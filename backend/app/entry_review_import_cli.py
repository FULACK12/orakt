"""CLI for importing Sites parameter-review exports into the local database."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.db.session import get_session_factory
from app.entry_review_import import import_candidate_reviews


def main() -> None:
    parser = argparse.ArgumentParser(prog="newsapp-entry-review-import")
    parser.add_argument("path", type=Path, help="JSON export containing review rows")
    args = parser.parse_args()
    payload = json.loads(args.path.read_text(encoding="utf-8-sig"))
    with get_session_factory()() as session:
        result = import_candidate_reviews(session, payload)
        session.commit()
    print("entry_candidate_review_import=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
