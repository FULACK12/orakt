"""Versioned canonical commitments. No network calls and no private keys."""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select

from app.db.models import Event, ProvenanceRecord, ResearchInquiry

PROTOCOL = "orakt-provenance/1"
DISCLAIMER = "存证证明该哈希版本被记录，不证明新闻、因果关系或投资结论真实。"


def normalize(value):
    """Protocol v1: NFC strings, UTC datetimes, decimal strings, sorted object keys.

    Ordered arrays (steps, paragraphs) retain order; the source SET is explicitly
    sorted below. No timestamps are removed from the committed payload.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("Naive timestamp cannot be canonicalized")
        return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, (float, Decimal)):
        if not math.isfinite(value):
            raise ValueError("Non-finite number")
        d = Decimal(str(value)).normalize()
        return "0" if d == 0 else format(d, "f")
    if isinstance(value, (list, tuple)):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        if any(not isinstance(k, str) for k in value):
            raise ValueError("Canonical keys must be strings")
        result = {normalize(k): normalize(v) for k, v in value.items()}
        if len(result) != len(value):
            raise ValueError("Normalized key collision")
        return result
    raise ValueError(f"Unsupported canonical type {type(value).__name__}")


def canonical_bytes(value):
    return json.dumps(
        normalize(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def object_key(kind, object_id, namespace):
    if kind not in {"event", "report"} or object_id < 1 or not namespace.strip():
        raise ValueError("Invalid provenance object")
    return digest({"namespace": namespace, "type": kind, "id": str(object_id)})


def snapshot(session, kind, object_id, namespace):
    key = object_key(kind, object_id, namespace)
    if kind == "event":
        event = session.get(Event, object_id)
        if event is None:
            raise LookupError("Event not found")
        sources = [
            {
                "id": str(link.document_id),
                "url": link.document.url,
                "content_hash": link.document.content_hash,
                "published_at": link.document.published_at,
                "stance": str(link.stance),
                "primary": link.is_primary_source,
            }
            for link in event.document_links
        ]
        content = {
            "title": event.title,
            "summary": event.summary,
            "event_type": event.event_type,
            "claim_status": str(event.status),
            "confidence": event.confidence,
            "start_at": event.start_at,
            "end_at": event.end_at,
            "latitude": event.latitude,
            "longitude": event.longitude,
            "country_code": event.country_code,
        }
    else:
        report = session.get(ResearchInquiry, object_id)
        if report is None:
            raise LookupError("Report not found")
        if report.status != "completed" or not report.result:
            raise ValueError("Only completed reports can be committed")
        # Commit full evidence without publishing its contents. A single snapshot
        # digest avoids claiming a source-merkle-tree that we have not built.
        sources = [{"id": "evidence_snapshot", "content_hash": digest(report.evidence_snapshot)}]
        content = {
            "question": report.question,
            "result": report.result,
            "model": report.local_model,
            "created_at": report.created_at,
            "claim_status": "research_not_truth_verified",
        }
    sources = sorted(sources, key=lambda item: canonical_bytes(item))
    payload = normalize(
        {
            "protocol": PROTOCOL,
            "object_key": key,
            "object_type": kind,
            "content": content,
            "sources": sources,
        }
    )
    return key, payload, digest(payload), digest(sources)


def prepare(session, kind, object_id, namespace):
    # Serialize by source object row, including the first revision. SQLite tests
    # have no concurrent writers; production PostgreSQL provides FOR UPDATE.
    source_model = Event if kind == "event" else ResearchInquiry
    session.execute(select(source_model).where(source_model.id == object_id).with_for_update())
    key, payload, content_hash, source_hash = snapshot(session, kind, object_id, namespace)
    existing = session.scalar(
        select(ProvenanceRecord).where(
            ProvenanceRecord.object_key == key, ProvenanceRecord.payload_hash == content_hash
        )
    )
    if existing:
        return existing
    previous = session.scalar(
        select(ProvenanceRecord)
        .where(ProvenanceRecord.object_key == key)
        .order_by(ProvenanceRecord.revision.desc())
        .limit(1)
    )
    revision = previous.revision + 1 if previous else 1
    prior = previous.payload_hash if previous else None
    memo = f"ORAKT1|{key}|{revision}|{content_hash}|{source_hash}|{prior or '-'}"
    row = ProvenanceRecord(
        object_key=key,
        object_type=kind,
        object_id=str(object_id),
        revision=revision,
        payload_hash=content_hash,
        source_set_hash=source_hash,
        previous_hash=prior,
        canonical_payload=payload,
        memo=memo,
        status="prepared",
    )
    session.add(row)
    session.flush()
    return row


def view(row):
    return {
        "id": row.id,
        "object_type": row.object_type,
        "object_id": row.object_id,
        "revision": row.revision,
        "payload_hash": row.payload_hash,
        "source_set_hash": row.source_set_hash,
        "previous_hash": row.previous_hash,
        "status": row.status,
        "network": "devnet",
        "memo": row.memo,
        "signature": row.signature,
        "publisher": row.publisher,
        "receipt": row.receipt,
        "created_at": row.created_at,
        "explorer_url": (
            f"https://explorer.solana.com/tx/{row.signature}?cluster=devnet"
            if row.signature
            else None
        ),
        "disclaimer": DISCLAIMER,
    }
