"""SQL-backed integration tests using synthetic earnings and in-memory SQLite."""

from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.models.earnings_task import EarningsResearchTask
from app.earnings_evidence_packet import EvidenceDocument
from app.earnings_phase_manifest import (
    EarningsEvent,
    EvidenceReference,
    ManifestVersions,
    PhaseCutoffs,
)
from app.earnings_tasks import cancel_earnings_task, earnings_queue_summary, enqueue_earnings_event


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    EarningsResearchTask.__table__.create(engine)
    with Session(engine) as connection:
        yield connection
    engine.dispose()


def inputs():
    return dict(
        event=EarningsEvent(
            "issuer", "security", "TEST", "TEST", "e1", "2025Q1", "2025-04-01T20:00:00Z", "exact"
        ),
        cutoffs=PhaseCutoffs(
            "2025-04-01T19:00:00Z", "2025-04-01T20:00:00Z", "2025-04-02T20:00:00Z", True
        ),
        versions=ManifestVersions("m1", "t1", "f1"),
        evidence=(
            EvidenceReference(
                "test", "2025-04-01T18:00:00Z", "v1", sha256(b"synthetic").hexdigest(), "fixture"
            ),
        ),
        documents={"test": EvidenceDocument("test", "synthetic", "https://example.com/doc")},
        release_source_url="https://example.com/release",
        now=datetime(2026, 10, 5, tzinfo=UTC),
    )


def test_three_phases_durable_and_idempotent(session):
    first = enqueue_earnings_event(session, **inputs())
    session.commit()
    second = enqueue_earnings_event(session, **inputs())
    assert [t.id for t in first] == [t.id for t in second]
    assert len({t.fingerprint for t in first}) == 3
    assert all(t.status == "awaiting_dispatch" for t in first)
    assert all(t.readiness["execution_permitted"] is False for t in first)
    assert session.scalar(select(func.count()).select_from(EarningsResearchTask)) == 3


@pytest.mark.parametrize("version", ["model_version", "template_version", "factor_version"])
def test_changed_version_creates_new_tasks_without_overwriting_old(session, version):
    args = inputs()
    original = enqueue_earnings_event(session, **args)
    args["versions"] = replace(args["versions"], **{version: "v2"})
    changed = enqueue_earnings_event(session, **args)
    assert not set(t.id for t in original) & set(t.id for t in changed)
    assert earnings_queue_summary(session)["total"] == 6


def test_missing_body_blocks_and_repaired_body_promotes_same_tasks(session):
    args = inputs()
    args["documents"] = {}
    blocked = enqueue_earnings_event(session, **args)
    ids = [t.id for t in blocked]
    assert all(t.status == "blocked" for t in blocked)
    assert all("document_set_does_not_match_manifest" in t.readiness["reasons"] for t in blocked)
    ready = enqueue_earnings_event(session, **inputs())
    assert [t.id for t in ready] == ids
    assert all(t.status == "awaiting_dispatch" for t in ready)


def test_cancellation_is_preserved_on_reimport(session):
    tasks = enqueue_earnings_event(session, **inputs())
    assert cancel_earnings_task(session, tasks[0].id)
    assert not cancel_earnings_task(session, tasks[0].id)
    assert not cancel_earnings_task(session, 99999)
    session.commit()
    again = enqueue_earnings_event(session, **inputs())
    assert again[0].status == "cancelled"


def test_unknown_announcement_time_is_visible_as_blocked(session):
    args = inputs()
    args["event"] = replace(args["event"], actual_release_at=None)
    tasks = enqueue_earnings_event(session, **args)
    assert all(t.status == "blocked" for t in tasks)
    assert "actual_release_at_requires_exact_utc_timestamp" in tasks[0].readiness["reasons"]


def test_post_evidence_never_leaks_into_pre_phase(session):
    args = inputs()
    args["evidence"] += (
        EvidenceReference(
            "later", "2025-04-01T20:00:00Z", "v1", sha256(b"later").hexdigest(), "fixture"
        ),
    )
    args["documents"]["later"] = EvidenceDocument("later", "later", "https://example.com/later")
    tasks = enqueue_earnings_event(session, **args)
    assert [e["id"] for e in tasks[0].manifest["evidence"]] == ["test"]
    assert tasks[0].readiness["verified_utf8_bytes"] == len(b"synthetic")
    assert tasks[1].readiness["verified_utf8_bytes"] == len(b"syntheticlater")


def test_body_mismatch_does_not_queue_model_work(session):
    args = inputs()
    args["documents"]["test"] = replace(args["documents"]["test"], text="changed")
    tasks = enqueue_earnings_event(session, **args)
    assert all(t.status == "blocked" for t in tasks)
    assert all("document_hash_mismatch" in t.readiness["reasons"] for t in tasks)


def test_summary_total_not_truncated_to_display_limit(session):
    enqueue_earnings_event(session, **inputs())
    summary = earnings_queue_summary(session, limit=1)
    assert summary["total"] == 3
    assert summary["counts"] == {"awaiting_dispatch": 3}
    assert len(summary["items"]) == 1


def test_no_full_documents_persisted_in_queue(session):
    tasks = enqueue_earnings_event(session, **inputs())
    assert "synthetic" not in str(tasks[0].manifest)
    assert "documents" not in tasks[0].readiness


def test_release_source_required(session):
    args = inputs()
    args["release_source_url"] = ""
    assert all(t.status == "blocked" for t in enqueue_earnings_event(session, **args))
