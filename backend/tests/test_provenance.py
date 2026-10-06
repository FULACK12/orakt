"""Offline provenance/signature tests. Synthetic keys, never funded accounts."""

import base64
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from solders.hash import Hash
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api import provenance as api
from app.core.config import Settings
from app.db.models import ProvenanceRecord, ResearchInquiry
from app.provenance import canonical_bytes, digest, object_key, prepare
from app.solana_provenance import (
    DEVNET_GENESIS,
    DevnetRPC,
    build_transaction,
    build_unsigned,
    decode_transaction,
    submit,
    validate_signed,
    verify,
)


def test_canonical_reordering_unicode_numbers_and_timezone():
    a = {"b": Decimal("0.500"), "a": "e\u0301", "time": datetime(2025, 1, 1, tzinfo=UTC)}
    b = {
        "time": datetime(2024, 12, 31, 19, tzinfo=timezone(timedelta(hours=-5))),
        "a": "é",
        "b": 0.5,
    }
    assert canonical_bytes(a) == canonical_bytes(b)
    assert digest(a) != digest({**a, "a": "changed"})
    assert digest([1, 2]) != digest([2, 1])  # reasoning step order is meaningful


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), datetime(2025, 1, 1), {"é": 1, "e\u0301": 2}, {1: "bad"}]
)
def test_invalid_canonical_inputs(value):
    with pytest.raises(ValueError):
        canonical_bytes(value)


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    ResearchInquiry.__table__.create(engine)
    ProvenanceRecord.__table__.create(engine)
    with Session(engine, expire_on_commit=False) as db:
        yield db
    engine.dispose()


def report(session):
    row = ResearchInquiry(
        question="fixture",
        mode="user_question",
        status="completed",
        local_model="fixture-only",
        result={"summary": "test"},
        evidence_snapshot={"x": "fixture"},
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    session.add(row)
    session.commit()
    return row


def test_revision_idempotency_and_namespace(session):
    source = report(session)
    first = prepare(session, "report", source.id, "test")
    assert prepare(session, "report", source.id, "test").id == first.id
    source.result = {"summary": "changed"}
    session.flush()
    second = prepare(session, "report", source.id, "test")
    assert second.revision == 2 and second.previous_hash == first.payload_hash
    assert first.canonical_payload["content"]["result"]["summary"] == "test"
    assert first.object_key != object_key("report", source.id, "other-deployment")
    assert len(second.memo.encode()) < 450


def test_reject_incomplete_report(session):
    source = report(session)
    source.status = "running"
    with pytest.raises(ValueError, match="completed"):
        prepare(session, "report", source.id, "test")


def signed_fixture():
    key = Keypair.from_seed(bytes(range(32)))
    unsigned = build_unsigned(
        "ORAKT1|synthetic-not-published", str(key.pubkey()), str(Hash.default())
    )
    tx = VersionedTransaction(decode_transaction(unsigned).message, [key])
    encoded = base64.b64encode(bytes(tx)).decode()
    return key, unsigned, encoded, str(tx.signatures[0])


def test_valid_signature_and_tamper_detection():
    key, unsigned, encoded, signature = signed_fixture()
    assert validate_signed(encoded, unsigned, str(key.pubkey())) == signature
    other = build_unsigned("ORAKT1|changed", str(key.pubkey()), str(Hash.default()))
    with pytest.raises(ValueError, match="changed"):
        validate_signed(encoded, other, str(key.pubkey()))
    with pytest.raises(ValueError, match="Invalid publisher"):
        validate_signed(unsigned, unsigned, str(key.pubkey()))
    with pytest.raises(ValueError, match="mismatch"):
        validate_signed(encoded, unsigned, str(Keypair().pubkey()))


class RPC:
    def __init__(self, receipt=None, fail=False):
        self.receipt, self.fail, self.calls = receipt, fail, []

    def verify_network(self):
        pass

    def call(self, method, params=None):
        self.calls.append((method, params))
        if self.fail:
            raise httpx.ConnectError("synthetic offline")
        if method == "getTransaction":
            return self.receipt
        if method == "sendTransaction":
            return str(decode_transaction(params[0]).signatures[0])
        if method == "getLatestBlockhash":
            return {"value": {"blockhash": str(Hash.default()), "lastValidBlockHeight": 10}}
        raise AssertionError(method)


def test_no_false_confirmation_and_exact_finalized_receipt():
    key, unsigned, encoded, signature = signed_fixture()
    row = SimpleNamespace(
        signature=signature,
        unsigned_transaction=unsigned,
        signed_transaction=encoded,
        publisher=str(key.pubkey()),
        status="submitted",
    )
    assert verify(row, RPC())["state"] == "not_finalized"
    assert row.status == "submitted"
    receipt = {"meta": {"err": {"failure": 1}}, "transaction": [encoded, "base64"], "slot": 7}
    assert verify(row, RPC(receipt))["state"] == "execution_failed"
    assert row.status == "submitted"
    receipt["meta"]["err"] = None
    rpc = RPC(receipt)
    assert verify(row, rpc)["state"] == "finalized"
    assert rpc.calls[0][1][1]["commitment"] == "finalized"
    assert row.receipt["slot"] == 7


def test_uncertain_submission_is_durable_and_same_bytes_retry(session):
    source = report(session)
    row = prepare(session, "report", source.id, "test")
    key = Keypair.from_seed(bytes(range(32)))
    build_transaction(row, str(key.pubkey()), RPC())
    tx = VersionedTransaction(decode_transaction(row.unsigned_transaction).message, [key])
    signed = base64.b64encode(bytes(tx)).decode()
    with pytest.raises(httpx.ConnectError):
        submit(session, row, signed, str(key.pubkey()), RPC(fail=True))
    session.expire_all()
    saved = session.scalar(select(ProvenanceRecord))
    assert saved.signature == str(tx.signatures[0]) and saved.status == "submitted"
    retry = RPC()
    submit(session, saved, signed, str(key.pubkey()), retry)
    assert retry.calls[0][1][0] == signed
    with pytest.raises(ValueError, match="Already submitted"):
        build_transaction(saved, str(key.pubkey()), RPC())


def test_network_identity_rejects_mainnet():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"result": "mainnet"}))
    with pytest.raises(ValueError, match="not Solana devnet"):
        DevnetRPC(transport).verify_network()
    ok = httpx.MockTransport(lambda request: httpx.Response(200, json={"result": DEVNET_GENESIS}))
    DevnetRPC(ok).verify_network()


def test_operator_and_disabled_write_gates(monkeypatch):
    monkeypatch.setattr(api, "get_settings", lambda: Settings(_env_file=None))
    with pytest.raises(HTTPException) as missing:
        api.operator()
    assert missing.value.status_code == 503
    with pytest.raises(HTTPException):
        api.publisher()
    settings = Settings(_env_file=None, solana_operator_token="x" * 32)
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    with pytest.raises(HTTPException) as invalid:
        api.operator("Bearer wrong")
    assert invalid.value.status_code == 403
    api.operator("Bearer " + "x" * 32)


def test_provenance_migration_is_additive_and_reversible():
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect, text

    path = Path(__file__).parents[1] / "alembic/versions/20261006_0049_add_provenance_records.py"
    spec = importlib.util.spec_from_file_location("migration49", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE existing_data (id INTEGER)"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert "provenance_records" in inspect(connection).get_table_names()
        migration.downgrade()
        assert inspect(connection).get_table_names() == ["existing_data"]
    engine.dispose()
