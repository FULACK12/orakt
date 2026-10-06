"""Read-only public provenance; explicitly enabled, token-protected local operator writes."""

from __future__ import annotations

import secrets
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import ProvenanceRecord
from app.db.session import get_db_session
from app.provenance import DISCLAIMER, prepare, snapshot, view
from app.solana_provenance import DevnetRPC, build_transaction, submit, verify

router = APIRouter(prefix="/provenance", tags=["provenance"])
DB = Annotated[Session, Depends(get_db_session)]
Kind = Literal["event", "report"]


def operator(authorization: Annotated[str | None, Header()] = None):
    settings = get_settings()
    secret = settings.solana_operator_token
    if not secret or len(secret.get_secret_value()) < 32:
        raise HTTPException(503, "Provenance operator token is not configured")
    expected = "Bearer " + secret.get_secret_value()
    if not authorization or not secrets.compare_digest(authorization.encode(), expected.encode()):
        raise HTTPException(403, "Operator authorization required")


def publisher():
    settings = get_settings()
    if not settings.solana_writes_enabled or not settings.solana_publisher:
        raise HTTPException(503, "Devnet publishing disabled or publisher not configured")
    return settings.solana_publisher


def record(session, record_id):
    row = session.scalar(
        select(ProvenanceRecord).where(ProvenanceRecord.id == record_id).with_for_update()
    )
    if not row:
        raise HTTPException(404, "Provenance revision not found")
    return row


@router.get("/health")
def health():
    settings = get_settings()
    return {
        "network": "devnet",
        "program": "official-memo",
        "writes_enabled": settings.solana_writes_enabled and bool(settings.solana_publisher),
        "publisher": settings.solana_publisher or None,
        "disclaimer": DISCLAIMER,
    }


@router.get("/{kind}/{object_id}")
def provenance(kind: Kind, object_id: int, session: DB):
    try:
        key, _, current_hash, source_hash = snapshot(
            session, kind, object_id, get_settings().solana_namespace
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    rows = session.scalars(
        select(ProvenanceRecord)
        .where(ProvenanceRecord.object_key == key)
        .order_by(ProvenanceRecord.revision.desc())
    ).all()
    return {
        "object_key": key,
        "current_payload_hash": current_hash,
        "current_source_set_hash": source_hash,
        "disclaimer": DISCLAIMER,
        "current_version_anchored": any(
            r.payload_hash == current_hash and r.status == "finalized" for r in rows
        ),
        "revisions": [view(row) for row in rows],
    }


@router.post("/{kind}/{object_id}/prepare", dependencies=[Depends(operator)])
def prepare_revision(kind: Kind, object_id: int, session: DB):
    try:
        row = prepare(session, kind, object_id, get_settings().solana_namespace)
        session.commit()
        return view(row)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/revisions/{record_id}/transaction", dependencies=[Depends(operator)])
def transaction(record_id: int, session: DB):
    try:
        row = record(session, record_id)
        result = build_transaction(row, publisher(), DevnetRPC())
        session.commit()
        return result
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(409, "Unable to build devnet transaction; check publisher/RPC") from exc


class SignedTransaction(BaseModel):
    transaction: str = Field(min_length=50, max_length=2200)


@router.post("/revisions/{record_id}/submit", dependencies=[Depends(operator)])
def publish(record_id: int, body: SignedTransaction, session: DB):
    try:
        row = record(session, record_id)
        submit(session, row, body.transaction, publisher(), DevnetRPC())
        return view(row)
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(
            409, "Submission not confirmed; verify saved attempt before retrying"
        ) from exc


@router.post("/revisions/{record_id}/verify", dependencies=[Depends(operator)])
def verify_revision(record_id: int, session: DB):
    try:
        row = record(session, record_id)
        outcome = verify(row, DevnetRPC())
        session.commit()
        return {"verification": outcome, "record": view(row)}
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(409, "RPC receipt verification failed; not marked anchored") from exc


@router.post("/revisions/{record_id}/retry", dependencies=[Depends(operator)])
def retry_submission(record_id: int, session: DB):
    """Recover after browser/process loss without requesting a new signature."""
    try:
        row = record(session, record_id)
        configured_publisher = publisher()
        if not row.signed_transaction:
            raise ValueError("No signed attempt to retry")
        rpc = DevnetRPC()
        outcome = verify(row, rpc)
        if outcome["state"] == "finalized":
            session.commit()
            return view(row)
        if outcome["state"] == "execution_failed":
            raise ValueError("Failed execution requires operator investigation")
        submit(session, row, row.signed_transaction, configured_publisher, rpc)
        return view(row)
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(
            409, "Same-signature retry not confirmed; inspect existing attempt"
        ) from exc
