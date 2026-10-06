"""Local-only preparation queue CLI; no API route or inference side effects."""

import argparse
import json
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_session_factory
from app.earnings_evidence_packet import EvidenceDocument
from app.earnings_inventory import earnings_inventory
from app.earnings_phase_manifest import (
    EarningsEvent,
    EvidenceReference,
    ManifestVersions,
    PhaseCutoffs,
)
from app.earnings_tasks import cancel_earnings_task, earnings_queue_summary, enqueue_earnings_event


def load_request(path: Path) -> dict:
    if path.stat().st_size > 12_000_000:
        raise ValueError("input_too_large")

    def unique_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_field")
            result[key] = value
        return result

    payload = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_fields)
    expected = {
        "event",
        "cutoffs",
        "versions",
        "evidence",
        "documents",
        "release_source_url",
        "required_evidence_refs",
    }
    if not isinstance(payload, dict) or set(payload) - expected:
        raise ValueError("invalid_fields")
    documents = [EvidenceDocument(**value) for value in payload["documents"]]
    if len({doc.id for doc in documents}) != len(documents):
        raise ValueError("duplicate_document_id")
    return dict(
        event=EarningsEvent(**payload["event"]),
        cutoffs=PhaseCutoffs(**payload["cutoffs"]),
        versions=ManifestVersions(**payload["versions"]),
        evidence=[EvidenceReference(**ref) for ref in payload["evidence"]],
        documents={doc.id: doc for doc in documents},
        release_source_url=payload["release_source_url"],
        required_evidence_refs=payload.get("required_evidence_refs"),
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_mutually_exclusive_group(required=True)
    commands.add_argument("--status", action="store_true")
    commands.add_argument(
        "--inventory", action="store_true", help="Read first-batch source coverage"
    )
    commands.add_argument("--enqueue", type=Path, help="Stage a trusted evidence JSON request")
    commands.add_argument(
        "--cancel", type=int, help="Cancel an unstarted task, preserving metadata"
    )
    args = parser.parse_args(argv)
    try:
        request = load_request(args.enqueue) if args.enqueue else None
        with get_session_factory()() as session:
            if request is not None:
                tasks = enqueue_earnings_event(session, **request)
                result = {"task_ids": [t.id for t in tasks], "execution_permitted": False}
                session.commit()
            elif args.cancel is not None:
                result = {"cancelled": cancel_earnings_task(session, args.cancel)}
                session.commit()
            elif args.inventory:
                result = earnings_inventory(session)
            else:
                result = earnings_queue_summary(session)
    except SQLAlchemyError:
        # Never print connection strings, credentials or raw SQL parameters.
        result = {
            "error": "database_unavailable_or_migration_required",
            "execution_permitted": False,
        }
        print(json.dumps(result))
        return 2
    except (ValueError, TypeError, KeyError, OSError):
        print(json.dumps({"error": "invalid_input", "execution_permitted": False}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
