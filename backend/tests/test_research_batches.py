"""Durable equity research batches and frozen-evidence audit queue tests."""

# ruff: noqa: RUF001

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.enums import SourceType
from app.db.models import (
    CompanyProfile,
    Document,
    MarketObservation,
    MarketSeries,
    ResearchBatch,
    ResearchBatchItem,
    ResearchInquiry,
    ResearchReportAuditJob,
    Source,
)
from app.equity_research import build_equity_research_pack
from app.research import LOCAL_REPORT_AUDIT_VERSION, audit_local_report
from app.research_audit_jobs import (
    ResearchAuditWorker,
    queue_research_report_audits,
)
from app.research_batches import (
    ResearchBatchWorker,
    create_equity_research_batch,
    get_research_batch,
    retry_failed_batch_items,
)
from app.schemas.research import ResearchBatchCreateRequest
from app.task_controls import research_checkpoint_response


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def test_china_equity_pack_is_explicitly_market_factor_only(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        _seed_china_equity(session)
        context, evidence = build_equity_research_pack(
            session,
            question="宁德时代 300750 未来还能上涨吗？",
        )

    assert context is not None
    assert context["market_region"] == "china"
    assert context["research_scope"] == "market_factor_evidence"
    assert context["sec_ticker"] is None
    assert "not equivalent" in context["evidence_scope_warning"]
    valuation = next(item for item in evidence if item["category"] == "derived_company_valuation")
    assert valuation["trailing_price_to_earnings"] == 24.5
    assert valuation["price_to_book"] == 5.2
    assert valuation["valuation_basis_period_end"] is None
    technical = next(item for item in evidence if item["category"] == "derived_market_technical")
    assert "BaoStock" in technical["source"]


def test_equity_batch_is_durable_bounded_and_idempotent(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        _seed_us_equity(session)
        _seed_china_equity(session)
        request = ResearchBatchCreateRequest(
            regions=["us", "china"],
            limit_per_region=1,
        )
        first = create_equity_research_batch(session, request=request)
        second = create_equity_research_batch(session, request=request)

    assert first.id == second.id
    assert first.target_count == 2
    assert {item.market_region for item in first.items} == {"us", "china"}
    assert {item.research_scope for item in first.items} == {
        "sec_numeric_evidence",
        "market_factor_evidence",
    }
    china_item = next(item for item in first.items if item.market_region == "china")
    assert "not filing-audited" in china_item.data_readiness["quality_warning"]


def test_retry_failed_items_preserves_running_batch_status(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        batch = ResearchBatch(
            name="partly running batch",
            status="running",
            template_version="test-v1",
            parameters={},
            target_count=2,
            completed_count=0,
            failed_count=1,
            started_at=datetime.now(UTC),
        )
        session.add(batch)
        session.flush()
        session.add_all(
            [
                ResearchBatchItem(
                    batch_id=batch.id,
                    market_region="us",
                    research_scope="sec_numeric_evidence",
                    ticker="AAPL",
                    company_name="Apple",
                    question="running report",
                    priority=1,
                    status="running",
                    progress_percent=5,
                    progress_stage="preparing_evidence",
                    data_readiness={},
                ),
                ResearchBatchItem(
                    batch_id=batch.id,
                    market_region="us",
                    research_scope="sec_numeric_evidence",
                    ticker="MSFT",
                    company_name="Microsoft",
                    question="failed report",
                    priority=2,
                    status="failed",
                    progress_percent=100,
                    progress_stage="failed",
                    error_message="temporary failure",
                    data_readiness={},
                ),
            ]
        )
        session.commit()
        batch_id = batch.id

        retried = retry_failed_batch_items(session, batch_id=batch_id)

    assert retried.status == "running"
    assert retried.failed_count == 0
    assert next(item for item in retried.items if item.ticker == "AAPL").status == "running"
    retried_item = next(item for item in retried.items if item.ticker == "MSFT")
    assert retried_item.status == "queued"
    assert retried_item.error_message is None


def test_batch_status_counts_current_item_with_autoflush_disabled(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as setup:
        no_flush_factory = sessionmaker(
            setup.get_bind(),
            expire_on_commit=False,
            autoflush=False,
        )
    with no_flush_factory() as session:
        batch = ResearchBatch(
            name="two item batch",
            status="running",
            template_version="test-v1",
            parameters={},
            target_count=2,
            completed_count=1,
            failed_count=0,
            started_at=datetime.now(UTC),
        )
        session.add(batch)
        session.flush()
        session.add_all(
            [
                ResearchBatchItem(
                    batch_id=batch.id,
                    market_region="us",
                    research_scope="sec_numeric_evidence",
                    ticker="NVDA",
                    company_name="NVIDIA",
                    question="test one",
                    priority=1,
                    status="completed",
                    data_readiness={},
                ),
                ResearchBatchItem(
                    batch_id=batch.id,
                    market_region="china",
                    research_scope="market_factor_evidence",
                    ticker="300251",
                    company_name="光线传媒",
                    question="test two",
                    priority=2,
                    status="running",
                    data_readiness={},
                ),
            ]
        )
        session.commit()
        batch_id = batch.id

    with no_flush_factory() as session:
        current = session.scalar(
            select(ResearchBatchItem).where(ResearchBatchItem.ticker == "300251")
        )
        assert current is not None
        current.status = "completed"
        current.completed_at = datetime.now(UTC)
        ResearchBatchWorker._update_batch_status(
            session,
            batch_id,
            now=datetime.now(UTC),
        )
        session.commit()

    with no_flush_factory() as session:
        repaired = session.get(ResearchBatch, batch_id)
        assert repaired is not None
        assert repaired.status == "completed"
        assert repaired.completed_count == 2
        assert repaired.failed_count == 0
        assert repaired.completed_at is not None


def test_worker_startup_reconciles_stale_terminal_batch(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        batch = ResearchBatch(
            name="stale batch",
            status="running",
            template_version="test-v1",
            parameters={},
            target_count=1,
            completed_count=0,
            failed_count=0,
            started_at=datetime.now(UTC),
        )
        session.add(batch)
        session.flush()
        session.add(
            ResearchBatchItem(
                batch_id=batch.id,
                market_region="us",
                research_scope="sec_numeric_evidence",
                ticker="NVDA",
                company_name="NVIDIA",
                question="test",
                priority=1,
                status="completed",
                data_readiness={},
            )
        )
        session.commit()
        batch_id = batch.id

    worker = ResearchBatchWorker(session_factory)
    assert worker.recover_interrupted_items() == 0
    with session_factory() as session:
        repaired = session.get(ResearchBatch, batch_id)
        assert repaired is not None
        assert repaired.status == "completed"
        assert repaired.completed_count == 1


def test_running_item_exposes_durable_stage_and_partial_batch_progress(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        batch = ResearchBatch(
            name="observable batch",
            status="running",
            template_version="test-v1",
            parameters={},
            target_count=2,
            completed_count=1,
            failed_count=0,
            started_at=datetime.now(UTC),
        )
        session.add(batch)
        session.flush()
        session.add_all(
            [
                ResearchBatchItem(
                    batch_id=batch.id,
                    market_region="us",
                    research_scope="sec_numeric_evidence",
                    ticker="AAPL",
                    company_name="Apple",
                    question="completed report",
                    priority=1,
                    status="completed",
                    progress_percent=100,
                    progress_stage="completed",
                    data_readiness={},
                ),
                ResearchBatchItem(
                    batch_id=batch.id,
                    market_region="us",
                    research_scope="sec_numeric_evidence",
                    ticker="MSFT",
                    company_name="Microsoft",
                    question="running report",
                    priority=2,
                    status="running",
                    progress_percent=30,
                    progress_stage="local_draft",
                    data_readiness={},
                ),
            ]
        )
        session.commit()
        batch_id = batch.id
        running_id = session.scalar(
            select(ResearchBatchItem.id).where(ResearchBatchItem.ticker == "MSFT")
        )

    worker = ResearchBatchWorker(session_factory)
    worker._report_progress(
        running_id,
        stage="bridge_evidence_completion",
        percent=62,
        message="正在核对因果链各环节",
    )

    with session_factory() as session:
        view = get_research_batch(session, batch_id)
    running = next(item for item in view.items if item.ticker == "MSFT")
    assert view.progress_percent == 81
    assert running.progress_percent == 62
    assert running.progress_stage == "bridge_evidence_completion"
    assert running.progress_message == "正在核对因果链各环节"
    assert running.heartbeat_at is not None


def test_failed_item_keeps_last_real_progress_in_batch_view(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        batch = ResearchBatch(
            name="truthful failed progress",
            status="failed",
            template_version="test-v1",
            parameters={},
            target_count=1,
            completed_count=0,
            failed_count=1,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        session.add(batch)
        session.flush()
        session.add(
            ResearchBatchItem(
                batch_id=batch.id,
                market_region="us",
                research_scope="sec_numeric_evidence",
                ticker="AAPL",
                company_name="Apple",
                question="failed report",
                priority=1,
                status="failed",
                progress_percent=42,
                progress_stage="failed",
                data_readiness={},
            )
        )
        session.commit()
        view = get_research_batch(session, batch.id)

    assert view.progress_percent == 42
    assert view.items[0].progress_percent == 42


def test_worker_recovery_requeues_interrupted_report_from_zero(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        batch = ResearchBatch(
            name="interrupted batch",
            status="running",
            template_version="test-v1",
            parameters={},
            target_count=1,
            completed_count=0,
            failed_count=0,
            started_at=datetime.now(UTC),
        )
        session.add(batch)
        session.flush()
        item = ResearchBatchItem(
            batch_id=batch.id,
            market_region="us",
            research_scope="sec_numeric_evidence",
            ticker="MSFT",
            company_name="Microsoft",
            question="interrupted report",
            priority=1,
            status="running",
            attempt_count=1,
            progress_percent=72,
            progress_stage="local_evidence_revision",
            data_readiness={},
        )
        session.add(item)
        session.commit()
        item_id = item.id

    worker = ResearchBatchWorker(session_factory, max_attempts=3)
    assert worker.recover_interrupted_items() == 1

    with session_factory() as session:
        recovered = session.get(ResearchBatchItem, item_id)
        assert recovered is not None
        assert recovered.status == "queued"
        assert recovered.progress_percent == 0
        assert recovered.progress_stage == "recovered_after_restart"


def test_worker_recovery_stops_after_retry_limit_without_fake_completion(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        batch = ResearchBatch(
            name="retry limited batch",
            status="running",
            template_version="test-v1",
            parameters={},
            target_count=1,
            completed_count=0,
            failed_count=0,
            started_at=datetime.now(UTC),
        )
        session.add(batch)
        session.flush()
        item = ResearchBatchItem(
            batch_id=batch.id,
            market_region="us",
            research_scope="sec_numeric_evidence",
            ticker="NVDA",
            company_name="NVIDIA",
            question="stuck report",
            priority=1,
            status="running",
            attempt_count=3,
            progress_percent=55,
            progress_stage="local_draft_complete",
            data_readiness={},
        )
        session.add(item)
        session.commit()
        item_id = item.id
        batch_id = batch.id

    worker = ResearchBatchWorker(session_factory, max_attempts=3)
    assert worker.recover_interrupted_items() == 1

    with session_factory() as session:
        stopped = session.get(ResearchBatchItem, item_id)
        batch = session.get(ResearchBatch, batch_id)
        assert stopped is not None
        assert batch is not None
        assert stopped.status == "failed"
        assert stopped.progress_percent == 55
        assert stopped.progress_stage == "watchdog_failed"
        assert batch.status == "failed"


def test_report_checkpoint_is_durable_inspectable_and_resumable(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        batch = ResearchBatch(
            name="checkpoint batch",
            status="running",
            template_version="test-v1",
            parameters={},
            target_count=1,
            completed_count=0,
            failed_count=0,
            started_at=datetime.now(UTC),
        )
        session.add(batch)
        session.flush()
        item = ResearchBatchItem(
            batch_id=batch.id,
            market_region="us",
            research_scope="sec_numeric_evidence",
            ticker="AAPL",
            company_name="Apple",
            question="checkpoint report",
            priority=1,
            status="running",
            attempt_count=1,
            progress_percent=30,
            progress_stage="local_draft",
            data_readiness={},
        )
        session.add(item)
        session.commit()
        item_id = item.id

    worker = ResearchBatchWorker(session_factory)
    worker._report_checkpoint(
        item_id,
        stage="local_draft_complete",
        percent=55,
        message="draft saved",
        payload={
            "schema_version": 1,
            "question": "checkpoint report",
            "model_question": "checkpoint report",
            "percent": 55,
            "evidence": {"documents": [{"id": 1}], "events": []},
            "result": {"summary": "saved draft", "hypotheses": []},
        },
    )

    with session_factory() as session:
        item = session.get(ResearchBatchItem, item_id)
        response = research_checkpoint_response(session, item_id=item_id)
        assert item is not None
        assert item.progress_percent == 55
        assert item.checkpoint_at is not None
        assert item.checkpoint_data["resume"]["result"]["summary"] == "saved draft"
        assert response.resumable is True
        assert response.latest_stage == "local_draft_complete"
        assert len(response.entries) == 1
        assert response.entries[0].summary["evidence_counts"]["documents"] == 1


def test_frozen_audit_queue_is_idempotent_and_does_not_refresh_equity(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with session_factory() as session:
        row = ResearchInquiry(
            question="Will a test company rise?",
            mode="user_question",
            status="completed",
            local_model="ollama:test",
            result=json.loads(_local_result()),
            evidence_snapshot={
                "generated_at": "2024-01-02T00:00:00+00:00",
                "frozen_marker": "keep-original-cutoff",
                "research_workflow": {"status": "local_draft", "stages": []},
            },
        )
        session.add(row)
        session.commit()
        inquiry_id = row.id
        queued = queue_research_report_audits(session, mode="audit_only", limit=100)
        duplicate = queue_research_report_audits(session, mode="audit_only", limit=100)

    assert queued.queued_jobs == 1
    assert duplicate.existing_jobs == 1

    def fail_if_refreshed(*_: object, **__: object) -> object:
        raise AssertionError("frozen audit must not rebuild equity evidence")

    monkeypatch.setattr(
        "app.research.build_equity_research_pack",
        fail_if_refreshed,
    )
    worker = ResearchAuditWorker(session_factory, worker_id="test-worker")
    assert worker.run_next() is True

    with session_factory() as session:
        row = session.get(ResearchInquiry, inquiry_id)
        job = session.scalar(select(ResearchReportAuditJob))
        assert row is not None
        assert job is not None
        assert job.status == "completed"
        assert job.before_evidence_snapshot["frozen_marker"] == "keep-original-cutoff"
        assert row.evidence_snapshot["frozen_marker"] == "keep-original-cutoff"
        assert row.evidence_snapshot["local_report_audit_refresh"] == {
            "mode": "audit_only",
            "frozen_evidence": True,
            "audited_at": row.evidence_snapshot["local_report_audit_refresh"]["audited_at"],
        }
        assert row.evidence_snapshot["local_report_audit"]["openai_used"] is False
        assert job.output_fingerprint
        assert job.before_result == json.loads(_local_result())


def test_targeted_audit_queue_only_enqueues_requested_inquiry(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        first = ResearchInquiry(
            question="First report",
            mode="user_question",
            status="completed",
            local_model="ollama:test",
            result=json.loads(_local_result()),
            evidence_snapshot={},
        )
        second = ResearchInquiry(
            question="Second report",
            mode="user_question",
            status="completed",
            local_model="ollama:test",
            result=json.loads(_local_result()),
            evidence_snapshot={},
        )
        session.add_all([first, second])
        session.commit()
        queued = queue_research_report_audits(
            session,
            mode="refresh_and_audit",
            inquiry_ids=(second.id,),
        )
        job = session.scalar(select(ResearchReportAuditJob))

    assert queued.scanned_reports == 1
    assert queued.queued_jobs == 1
    assert job is not None
    assert job.inquiry_id == second.id


def test_refresh_and_audit_rebuilds_point_in_time_hypothesis_refs(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_ref = "derived:valuation:NVDA:2026-08-25"
    new_ref = "derived:valuation:NVDA:2026-08-26"
    payload = json.loads(_local_result())
    payload["question"] = "NVIDIA NVDA未来6至12个月的驱动是否获得证据支持？"
    payload["hypotheses"][0]["title"] = "NVIDIA NVDA多因子条件链"
    payload["hypotheses"][0]["scope"]["companies"] = ["NVIDIA Corp."]
    payload["hypotheses"][0]["steps"][0].update(
        {
            "label": "点时SEC数据与2026-08-25估值共同界定NVDA当前状态。",
            "status": "verified",
            "evidence_refs": [old_ref],
        }
    )
    context = {
        "market_region": "us",
        "ticker": "NVDA",
        "company": "NVIDIA Corp.",
        "sector": "Technology",
        "industry": "Semiconductors",
        "point_in_time_cutoff": "2026-08-26",
        "reviewed_search_plan_not_evidence": {},
    }
    refreshed_evidence = [
        {
            "evidence_id": new_ref,
            "category": "derived_company_valuation",
            "ticker": "NVDA",
            "price": 210.0,
            "price_observed_on": "2026-08-26",
            "basis_revenue": 100.0,
            "basis_net_income": 10.0,
            "basis_diluted_eps_proxy": 2.0,
            "gross_margin": 0.55,
            "operating_margin": 0.3,
            "research_and_development_to_revenue": 0.15,
            "market_cap": 1_000.0,
            "trailing_price_to_sales": 10.0,
            "trailing_price_to_earnings": 100.0,
        }
    ]

    def refreshed_pack(
        *_: object,
        **__: object,
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        return context, refreshed_evidence

    monkeypatch.setattr("app.research.build_equity_research_pack", refreshed_pack)
    with session_factory() as session:
        row = ResearchInquiry(
            question=payload["question"],
            mode="user_question",
            status="completed",
            local_model="ollama:test",
            result=payload,
            evidence_snapshot={
                "equity_research_context": {**context, "point_in_time_cutoff": "2026-08-25"},
                "derived_equity_evidence": [
                    {
                        **refreshed_evidence[0],
                        "evidence_id": old_ref,
                        "price_observed_on": "2026-08-25",
                    }
                ],
                "documents": [],
                "events": [],
                "market_observations": [],
                "economic_observations": [],
                "company_financials": [],
                "research_workflow": {"status": "completed", "stages": []},
            },
        )
        session.add(row)
        session.commit()
        audited = audit_local_report(
            session,
            inquiry_id=row.id,
            refresh_equity_evidence=True,
        )

    first_step = audited.result.hypotheses[0].steps[0]
    assert first_step.status == "verified"
    assert first_step.evidence_refs == [new_ref]
    assert "2026-08-26" in first_step.label
    assert old_ref not in json.dumps(audited.result.model_dump(mode="json"))
    assert {
        "section": "hypotheses",
        "reason": "point_in_time_chain_refs_refreshed",
    } in audited.evidence_snapshot["local_report_repairs"]


def test_explicit_document_refresh_upgrades_only_retained_snapshot_rows(
    session_factory: sessionmaker[Session],
) -> None:
    body = "Verified publisher report with substantive details. " * 30
    with session_factory() as session:
        source = Source(
            name="Test publisher",
            country="US",
            language="en",
            source_type=SourceType.NEWS,
        )
        session.add(source)
        session.flush()
        document = Document(
            source_id=source.id,
            url="https://example.com/full-report",
            title="Full report",
            body=body,
            language="en",
            content_hash="d" * 64,
            raw_metadata={
                "collector": "gdelt_doc_discovery",
                "full_text_status": "complete",
                "full_body_chars": len(body),
            },
        )
        session.add(document)
        session.flush()
        evidence_ref = f"document:{document.id}"
        payload = json.loads(_local_result())
        payload["hypotheses"][0]["steps"][0]["status"] = "verified"
        payload["hypotheses"][0]["steps"][0]["evidence_refs"] = [evidence_ref]
        row = ResearchInquiry(
            question="Does the retained report support the claim?",
            mode="user_question",
            status="completed",
            local_model="ollama:test",
            result=payload,
            evidence_snapshot={
                "documents": [
                    {
                        "evidence_id": evidence_ref,
                        "category": "news_or_official_document",
                        "title": document.title,
                        "source": source.name,
                        "source_url": document.url,
                        "excerpt": "",
                        "full_body_chars": 0,
                        "content_storage": "hot",
                        "evidence_tier": "headline_only",
                        "can_verify_claims": False,
                    }
                ],
                "research_workflow": {"status": "local_draft", "stages": []},
            },
        )
        session.add(row)
        session.commit()
        audited = audit_local_report(
            session,
            inquiry_id=row.id,
            refresh_document_evidence=True,
        )

    refreshed = audited.evidence_snapshot["documents"][0]
    assert refreshed["evidence_tier"] == "full_text"
    assert refreshed["can_verify_claims"] is True
    assert refreshed["full_body_chars"] == len(body)
    assert refreshed["excerpt"].startswith("Verified publisher report")
    assert audited.evidence_snapshot["local_report_audit_refresh"] == {
        "mode": "refresh_documents_and_audit",
        "refreshed_at": audited.evidence_snapshot["local_report_audit_refresh"][
            "refreshed_at"
        ],
        "new_point_in_time_cutoff": None,
        "refreshed_document_refs": [evidence_ref],
    }
    assert (
        audited.evidence_snapshot["local_report_audit"]["checks"][
            "headline_only_reference_count"
        ]
        == 0
    )


def test_expired_audit_lease_is_recovered_but_active_lease_is_not(
    session_factory: sessionmaker[Session],
) -> None:
    now = datetime.now(UTC)
    with session_factory() as session:
        first = ResearchInquiry(
            question="First report",
            mode="user_question",
            status="completed",
            local_model="ollama:test",
            result=json.loads(_local_result()),
            evidence_snapshot={},
        )
        second = ResearchInquiry(
            question="Second report",
            mode="user_question",
            status="completed",
            local_model="ollama:test",
            result=json.loads(_local_result()),
            evidence_snapshot={},
        )
        session.add_all([first, second])
        session.flush()
        session.add_all(
            [
                ResearchReportAuditJob(
                    inquiry_id=first.id,
                    audit_version="v1",
                    mode="audit_only",
                    status="running",
                    priority=1,
                    attempt_count=1,
                    max_attempts=3,
                    available_at=now,
                    lease_expires_at=now - timedelta(minutes=1),
                    worker_id="dead-worker",
                    source_fingerprint="a" * 64,
                ),
                ResearchReportAuditJob(
                    inquiry_id=second.id,
                    audit_version="v1",
                    mode="audit_only",
                    status="running",
                    priority=2,
                    attempt_count=1,
                    max_attempts=3,
                    available_at=now,
                    lease_expires_at=now + timedelta(minutes=10),
                    worker_id="live-worker",
                    source_fingerprint="b" * 64,
                ),
            ]
        )
        session.commit()

    worker = ResearchAuditWorker(session_factory, worker_id="recovery-worker")
    assert worker.recover_expired_jobs() == 1
    with session_factory() as session:
        statuses = list(
            session.execute(
                select(
                    ResearchReportAuditJob.worker_id,
                    ResearchReportAuditJob.status,
                ).order_by(ResearchReportAuditJob.priority)
            )
        )
    assert statuses == [(None, "queued"), ("live-worker", "running")]


def test_v2_audit_removes_foreign_company_prose_and_blocks_bad_valuation(
    session_factory: sessionmaker[Session],
) -> None:
    payload = json.loads(_local_result())
    payload["summary"] = "Apple AAPL and 美光 MU may rise together."
    payload["hypotheses"][0]["title"] = "Apple and Micron shared template"
    payload["hypotheses"][0]["steps"][0]["label"] = "MU liquidity template"
    payload["hypotheses"][0]["scope"]["companies"] = ["NVIDIA", "Micron"]
    with session_factory() as session:
        row = ResearchInquiry(
            question="Apple AAPL未来6至12个月的驱动是否获得证据支持？",
            mode="user_question",
            status="completed",
            local_model="ollama:test",
            result=payload,
            evidence_snapshot={
                "equity_research_context": {
                    "market_region": "us",
                    "ticker": "AAPL",
                    "company": "Apple Inc.",
                    "sector": "Technology",
                    "industry": "Consumer electronics",
                    "point_in_time_cutoff": "2026-08-26",
                    "reviewed_search_plan_not_evidence": {
                        "products": ["iPhone", "Services"],
                        "competitors_to_verify": ["Google", "Microsoft"],
                    },
                },
                "derived_equity_evidence": [
                    {
                        "evidence_id": "derived:valuation:AAPL:2026-08-26",
                        "category": "derived_company_valuation",
                        "ticker": "AAPL",
                        "price": 210.0,
                        "price_observed_on": "2026-08-26",
                        "basis_revenue": 26.9,
                        "basis_net_income": 120.0,
                        "gross_margin": 5.7,
                        "operating_margin": 4.8,
                        "research_and_development_to_revenue": 0.68,
                        "market_cap": 5_000.0,
                        "question_price_scenarios": [{"target_price": 12.0}],
                    },
                    {
                        "evidence_id": "derived:technical:AAPL:2026-08-26",
                        "category": "derived_market_technical",
                        "ticker": "AAPL",
                        "observed_on": "2026-08-26",
                        "adjusted_close": 210.0,
                        "sma_20": 205.0,
                        "sma_50": 200.0,
                        "sma_200": 180.0,
                        "rsi_14": 55.0,
                        "macd_histogram": 1.0,
                        "return_21d": 0.05,
                        "drawdown_from_52_week_high": -0.1,
                    },
                ],
                "market_observations": [],
                "economic_observations": [],
                "company_financials": [],
                "documents": [],
                "events": [],
                "research_workflow": {"status": "completed", "stages": []},
            },
        )
        session.add(row)
        session.commit()
        audited = audit_local_report(session, inquiry_id=row.id)
        session.commit()

    serialized = json.dumps(audited.result.model_dump(mode="json"), ensure_ascii=False)
    assert "美光" not in serialized
    assert "Micron" not in serialized
    assert "Google" in serialized
    assert "Microsoft" in serialized
    audit = audited.evidence_snapshot["local_report_audit"]
    assert audit["audit_version"] == LOCAL_REPORT_AUDIT_VERSION
    assert audit["checks"]["foreign_subject_count"] == 0
    assert audit["checks"]["valuation_quality_issue_count"] == 1
    assert audit["status"] == "data_quality_blocked"
    assert audit["recommendation"] == "defer_pending_data_repair"


def _seed_us_equity(session: Session) -> None:
    session.add(
        CompanyProfile(
            ticker="NVDA",
            cik="0001045810",
            name="NVIDIA Corp.",
            sector="Technology",
            industry="Semiconductors",
            source_url="https://www.sec.gov/edgar/browse/?CIK=1045810",
        )
    )
    session.add(
        MarketSeries(
            series_id="EQ:NVDA",
            name="NVIDIA split-adjusted close",
            category="equity_price",
            unit="USD",
            frequency="daily",
            source_name="Test",
            source_url="https://example.test/nvda",
        )
    )
    session.add(
        MarketObservation(
            series_id="EQ:NVDA",
            observed_on=date(2026, 8, 26),
            value=200,
            fetched_at=datetime.now(UTC),
        )
    )
    session.flush()


def _seed_china_equity(session: Session) -> None:
    ticker = "300750"
    session.add(
        MarketSeries(
            series_id=f"CN:{ticker}",
            name=f"宁德时代 ({ticker}) 前复权收盘价",
            category="equity_price",
            unit="CNY",
            frequency="daily",
            source_name="BaoStock",
            source_url="https://www.baostock.com/",
            listing_status="active",
            sector="Industrials",
            region="china",
        )
    )
    start = date(2026, 3, 1)
    session.add_all(
        [
            MarketObservation(
                series_id=f"CN:{ticker}",
                observed_on=start + timedelta(days=index),
                value=200 + index,
                fetched_at=datetime.now(UTC),
            )
            for index in range(120)
        ]
    )
    snapshot_date = start + timedelta(days=119)
    for prefix, value, category, unit in (
        ("CNSCORE", 89.1, "equity_factor", "score_0_100"),
        ("CNMCAP", 1_500_000_000_000, "company_fundamental", "CNY"),
        ("CNREV", 400_000_000_000, "company_fundamental", "CNY"),
        ("CNNP", 55_000_000_000, "company_fundamental", "CNY"),
        ("CNROE", 0.22, "company_fundamental", "ratio"),
        ("CNYOYNI", 0.18, "company_fundamental", "ratio"),
        ("CNPE", 24.5, "valuation", "ratio"),
        ("CNPB", 5.2, "valuation", "ratio"),
    ):
        series_id = f"{prefix}:{ticker}"
        session.add(
            MarketSeries(
                series_id=series_id,
                name=series_id,
                category=category,
                unit=unit,
                frequency="snapshot",
                source_name="BaoStock",
                source_url="https://www.baostock.com/",
                sector="Industrials",
                region="china",
            )
        )
        session.add(
            MarketObservation(
                series_id=series_id,
                observed_on=snapshot_date,
                value=value,
                fetched_at=datetime.now(UTC),
            )
        )
    session.flush()


def _local_result() -> str:
    return """{
      "question": "Will the company rise?",
      "summary": "The direction remains conditional on evidence.",
      "hypotheses": [{
        "title": "A bounded company hypothesis",
        "premise": "Demand may remain strong",
        "outcome": "Equity performance may change",
        "scope": {
          "companies": ["Example"],
          "sectors": ["Technology"],
          "products": [],
          "supply_chain_inputs": [],
          "infrastructure": [],
          "policies": [],
          "geographies": []
        },
        "steps": [
          {
            "sequence": 1, "label": "Demand is a premise",
            "status": "hypothesis", "confidence": 0.4, "evidence_refs": []
          },
          {
            "sequence": 2, "label": "Earnings may respond",
            "status": "evidence_missing", "confidence": 0.3,
            "evidence_refs": []
          },
          {
            "sequence": 3, "label": "Price may respond",
            "status": "hypothesis", "confidence": 0.3, "evidence_refs": []
          }
        ],
        "counterarguments": ["Other factors may dominate"],
        "evidence_gaps": ["Company filings"],
        "confidence": 0.3
      }],
      "suggested_next_questions": ["Which evidence is missing?"]
    }"""
