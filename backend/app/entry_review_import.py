"""Import hosted parameter-review records into the local append-only audit ledger."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EntryParameterCandidate, EntryParameterCandidateReview

SOURCE_SYSTEM = "sites_review_feedback"
VALID_DECISIONS = {"accept", "revise", "hold", "reject"}


def import_candidate_reviews(session: Session, payload: object) -> dict[str, Any]:
    """Idempotently import reviews without changing candidate or production status."""
    records = _records(payload)
    imported = 0
    duplicates = 0
    for record in records:
        external_id = _required_text(record, "id", limit=128)
        report_id = _required_text(record, "report_id", limit=320)
        decision = _required_text(record, "decision", limit=16)
        if decision not in VALID_DECISIONS:
            raise ValueError(f"unsupported review decision: {decision}")
        base_model_version, candidate_version = _candidate_identity(report_id)
        candidate = session.scalar(
            select(EntryParameterCandidate).where(
                EntryParameterCandidate.base_model_version == base_model_version,
                EntryParameterCandidate.candidate_version == candidate_version,
            )
        )
        if candidate is None:
            raise ValueError(f"candidate does not exist locally: {candidate_version}")
        duplicate = session.scalar(
            select(EntryParameterCandidateReview.id).where(
                EntryParameterCandidateReview.source_system == SOURCE_SYSTEM,
                EntryParameterCandidateReview.external_review_id == external_id,
            )
        )
        if duplicate is not None:
            duplicates += 1
            continue
        created_at = _parse_datetime(record.get("created_at"))
        source_payload = {str(key): value for key, value in record.items()}
        session.add(
            EntryParameterCandidateReview(
                candidate_id=candidate.id,
                source_system=SOURCE_SYSTEM,
                external_review_id=external_id,
                decision=decision,
                comment=str(record.get("comment") or "")[:10_000],
                confidence=max(0, min(100, int(record.get("confidence") or 0))),
                source_created_at=created_at,
                source_payload=source_payload,
                payload_fingerprint=_fingerprint(source_payload),
                imported_at=datetime.now(UTC),
            )
        )
        imported += 1
    return {
        "source": SOURCE_SYSTEM,
        "records_received": len(records),
        "records_imported": imported,
        "duplicates_skipped": duplicates,
        "production_model_changed": False,
        "policy": "append_only_review_import_requires_separate_promotion_decision",
    }


def _records(payload: object) -> list[dict[str, Any]]:
    value = payload
    if isinstance(value, dict):
        value = value.get("reviews", value.get("results", value.get("rows")))
    if not isinstance(value, list):
        raise ValueError("review payload must be a list or contain reviews/results/rows")
    if not all(isinstance(item, dict) for item in value):
        raise ValueError("every review record must be an object")
    return value


def _candidate_identity(report_id: str) -> tuple[str, str]:
    parts = report_id.split(":", 2)
    if len(parts) != 3 or parts[0] != "entry-candidate" or not all(parts[1:]):
        raise ValueError(f"not an entry-candidate review id: {report_id}")
    return parts[1], parts[2]


def _required_text(record: dict[str, Any], key: str, *, limit: int) -> str:
    value = str(record.get(key) or "").strip()
    if not value:
        raise ValueError(f"review record is missing {key}")
    return value[:limit]


def _parse_datetime(value: object) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    if not text:
        raise ValueError("review record is missing created_at")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _fingerprint(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
