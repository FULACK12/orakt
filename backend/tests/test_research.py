"""Local autonomous research and OpenAI second-opinion tests."""

import json
from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ai_status import build_ai_status
from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    LogicChainHypothesis,
    LogicChainReviewSignal,
    MarketObservation,
    MarketSeries,
    ResearchBatch,
    ResearchBatchItem,
    ResearchInquiry,
)
from app.research import (
    PlannedResearchQuestion,
    ResearchProviderError,
    _allowed_equity_counterparty_tickers,
    _apply_numerical_evidence_quality_gate,
    _build_episode_candidates,
    _build_historical_anchors,
    _call_local_research_model,
    _deduplicate_research_hypotheses,
    _directional_confidence_explanation,
    _duplicates_prior_question,
    _expand_plain_user_question,
    _fallback_episode_question_plan,
    _foreign_equity_subjects,
    _planned_result_needs_repair,
    _sanitize_research_result,
    _text_relevance,
    _validate_planned_question_evidence,
    _validated_research_content,
    get_research_inquiry,
    get_research_report_comparison,
    list_research_inquiry_summaries,
    list_research_report_change_alerts,
    review_logic_chain_with_openai,
    review_with_openai,
    run_research,
)
from app.research_event_table import select_preferred_research_period
from app.schemas.research import ModelResearchResult


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    engine.dispose()


def test_research_inquiry_summaries_do_not_parse_large_report_json(
    session: Session,
) -> None:
    now = datetime.now(UTC)
    session.add(
        ResearchInquiry(
            question="Can the lightweight catalog avoid loading the full report?",
            mode="user_question",
            status="completed",
            local_model="ollama:test-local",
            result={"deliberately": "not a valid full report"},
            evidence_snapshot={"large": ["payload"] * 50},
            created_at=now,
            updated_at=now,
        )
    )
    session.flush()

    summaries, total = list_research_inquiry_summaries(
        session,
        page=1,
        page_size=10,
    )

    assert total == 1
    assert len(summaries) == 1
    assert summaries[0].has_result is True
    assert summaries[0].question.startswith("Can the lightweight catalog")
    assert not hasattr(summaries[0], "result")


def test_research_catalog_filters_batch_company_market_status_and_date(
    session: Session,
) -> None:
    now = datetime.now(UTC)
    inquiry = ResearchInquiry(
        question="Can Lululemon operating evidence support the valuation?",
        mode="autonomous",
        status="completed",
        local_model="ollama:test-local",
        result={"deliberately": "not parsed by catalog"},
        evidence_snapshot={},
        created_at=now,
        updated_at=now,
    )
    batch = ResearchBatch(
        name="US catalog test",
        status="completed",
        template_version="test-v1",
        parameters={},
        target_count=1,
        completed_count=1,
        failed_count=0,
        created_at=now,
        updated_at=now,
    )
    session.add_all([inquiry, batch])
    session.flush()
    session.add(
        ResearchBatchItem(
            batch_id=batch.id,
            market_region="us",
            research_scope="sec_numeric_evidence",
            ticker="LULU",
            company_name="Lululemon Athletica Inc.",
            sector="Consumer Cyclical",
            question=inquiry.question,
            priority=1,
            status="completed",
            progress_percent=100,
            progress_stage="completed",
            inquiry_id=inquiry.id,
            data_readiness={},
            checkpoint_data={},
            created_at=now,
            updated_at=now,
        )
    )
    session.flush()

    summaries, total = list_research_inquiry_summaries(
        session,
        page=1,
        page_size=10,
        search="LULU",
        market_region="us",
        status="completed",
        created_from=now.date(),
        created_to=now.date(),
    )

    assert total == 1
    assert summaries[0].ticker == "LULU"
    assert summaries[0].company_name == "Lululemon Athletica Inc."
    assert summaries[0].market_region == "us"


def test_workspace_inquiry_keeps_ui_evidence_and_drops_unneeded_payload(
    session: Session,
) -> None:
    now = datetime.now(UTC)
    row = ResearchInquiry(
        question="Does the compact workspace retain the UI evidence?",
        mode="user_question",
        status="running",
        local_model="ollama:test-local",
        result=None,
        evidence_snapshot={
            "research_workflow": {"status": "running"},
            "question_assistance": {"applied": True},
            "plain_language_report": {"summary": "plain"},
            "directional_confidence": {"score": 0.5},
            "derived_equity_evidence": [{"ticker": "TEST"}],
            "unneeded_large_payload": ["discard"] * 100,
        },
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()

    view = get_research_inquiry(
        session,
        row.id,
        include_full_evidence=False,
    )

    assert view.evidence_snapshot["question_assistance"]["applied"] is True
    assert view.evidence_snapshot["derived_equity_evidence"][0]["ticker"] == "TEST"
    assert "unneeded_large_payload" not in view.evidence_snapshot


def test_same_company_report_comparison_is_compact_and_tracks_evidence_changes(
    session: Session,
) -> None:
    older_at = datetime(2026, 9, 1, tzinfo=UTC)
    newer_at = datetime(2026, 9, 8, tzinfo=UTC)
    older = ResearchInquiry(
        question="What supports the older LULU thesis?",
        mode="autonomous",
        status="completed",
        local_model="ollama:test-local",
        result={
            "summary": "Older bounded conclusion.",
            "hypotheses": [
                {
                    "confidence": 0.38,
                    "steps": [{"evidence_refs": ["fact:shared", "fact:retired"]}],
                }
            ],
            "equity_dimensions": [
                {"signal": "mixed", "evidence_refs": ["fact:shared"]}
            ],
            "equity_decision_framework": {
                "timing_assessment": "insufficient_evidence"
            },
        },
        evidence_snapshot={
            "directional_confidence": {
                "score": 0.38,
                "verified_steps": 1,
                "partially_supported_steps": 1,
                "unresolved_steps": 2,
            },
            "derived_equity_evidence": [
                {"evidence_id": "fact:shared", "category": "company_filing"},
                {
                    "evidence_id": "fact:retired",
                    "category": "company_news_document",
                    "title": "Older demand report",
                    "published_at": "2026-08-30T12:00:00Z",
                    "provider": "Test Wire",
                },
            ],
        },
        created_at=older_at,
        updated_at=older_at,
    )
    newer = ResearchInquiry(
        question="What supports the newer LULU thesis?",
        mode="autonomous",
        status="completed",
        local_model="ollama:test-local",
        result={
            "summary": "Newer bounded conclusion.",
            "hypotheses": [
                {
                    "confidence": 0.55,
                    "steps": [{"evidence_refs": ["fact:shared", "fact:new"]}],
                }
            ],
            "equity_dimensions": [
                {"signal": "bullish", "evidence_refs": ["fact:new"]},
                {"signal": "mixed", "evidence_refs": ["fact:shared"]},
            ],
            "equity_decision_framework": {"timing_assessment": "neutral"},
        },
        evidence_snapshot={
            "directional_confidence": {
                "score": 0.55,
                "verified_steps": 2,
                "partially_supported_steps": 1,
                "unresolved_steps": 1,
            },
            "derived_equity_evidence": [
                {
                    "evidence_id": "fact:shared",
                    "category": "derived_market_technical",
                    "adjusted_close": 101.0,
                    "risk_reward": {
                        "entry_reference": 100.0,
                        "stop_reference": 92.0,
                        "target_reference": 116.0,
                        "reward_risk_ratio": 2.0,
                    },
                },
                {
                    "evidence_id": "fact:new",
                    "category": "company_filing",
                    "title": "Quarterly operating update",
                    "filing_date": "2026-09-07",
                    "filing_form": "10-Q",
                },
            ],
        },
        created_at=newer_at,
        updated_at=newer_at,
    )
    older_batch = ResearchBatch(
        name="LULU older history",
        status="completed",
        template_version="test-v1",
        parameters={},
        target_count=1,
        completed_count=1,
        failed_count=0,
        created_at=older_at,
        updated_at=older_at,
    )
    newer_batch = ResearchBatch(
        name="LULU newer history",
        status="completed",
        template_version="test-v1",
        parameters={},
        target_count=1,
        completed_count=1,
        failed_count=0,
        created_at=newer_at,
        updated_at=newer_at,
    )
    session.add_all([older, newer, older_batch, newer_batch])
    session.flush()
    for batch, inquiry, score in (
        (older_batch, older, 0.6),
        (newer_batch, newer, 0.9),
    ):
        session.add(
            ResearchBatchItem(
                batch_id=batch.id,
                market_region="us",
                research_scope="sec_numeric_evidence",
                ticker="LULU",
                company_name="Lululemon Athletica Inc.",
                sector="Consumer Cyclical",
                question=inquiry.question,
                priority=1,
                status="completed",
                progress_percent=100,
                progress_stage="completed",
                inquiry_id=inquiry.id,
                data_readiness={
                    "score": score,
                    "status": "conditional_ready",
                    "directional_conclusion_allowed": score >= 0.8,
                },
                checkpoint_data={},
                created_at=inquiry.created_at,
                updated_at=inquiry.updated_at,
            )
        )
    session.flush()

    comparison = get_research_report_comparison(session, newer.id, limit=12)

    assert comparison.comparable is True
    assert comparison.ticker == "LULU"
    assert comparison.total_versions == 2
    assert [item.inquiry_id for item in comparison.versions] == [newer.id, older.id]
    latest = comparison.versions[0]
    assert latest.confidence == pytest.approx(0.55)
    assert latest.data_readiness_score == pytest.approx(0.9)
    assert latest.new_evidence_count == 1
    assert latest.retired_evidence_count == 1
    assert latest.new_evidence[0].evidence_id == "fact:new"
    assert latest.new_evidence[0].title == "Quarterly operating update"
    assert latest.new_evidence[0].source == "10-Q"
    assert latest.retired_evidence[0].evidence_id == "fact:retired"
    assert latest.retired_evidence[0].source == "Test Wire"
    assert latest.change_summary is not None
    assert latest.change_summary.confidence_delta == pytest.approx(0.17)
    assert latest.change_summary.data_readiness_delta == pytest.approx(0.3)
    assert latest.change_summary.verified_steps_delta == 1
    assert latest.change_summary.unresolved_steps_delta == -1
    assert latest.change_summary.new_category_counts == {"company_filing": 1}
    assert latest.change_summary.retired_category_counts == {
        "company_news_document": 1
    }
    assert "chain_support_increased" in latest.change_summary.driver_codes
    assert "data_readiness_improved" in latest.change_summary.driver_codes
    assert latest.reward_risk_ratio == pytest.approx(2.0)
    assert latest.summary == "Newer bounded conclusion."
    assert not hasattr(latest, "result")
    assert not hasattr(latest, "evidence_snapshot")

    alerts = list_research_report_change_alerts(session, limit=24)

    assert alerts.total_companies_with_history == 1
    assert len(alerts.alerts) == 1
    alert = alerts.alerts[0]
    assert alert.latest_inquiry_id == newer.id
    assert alert.previous_inquiry_id == older.id
    assert alert.ticker == "LULU"
    assert alert.assessment == "evidence_upgrade"
    assert alert.severity in {"critical", "high"}
    assert alert.alert_score >= 30
    assert alert.change_summary.confidence_delta == pytest.approx(0.17)
    assert alert.change_summary.new_category_counts == {"company_filing": 1}
    assert "not an investment rating" in alerts.methodology


def test_verified_supply_chain_counterparty_is_not_company_subject_drift() -> None:
    evidence = {
        "derived_equity_evidence": [
            {
                "evidence_id": "supply-edge:1",
                "category": "verified_supply_chain_edge",
                "ticker": "AMD",
                "related_ticker": "MSFT",
                "relationship_type": "customer",
            }
        ]
    }
    allowed = _allowed_equity_counterparty_tickers(evidence, ticker="AMD")

    assert allowed == {"MSFT"}
    assert (
        _foreign_equity_subjects(
            "AMD disclosed Microsoft as a customer.",
            ticker="AMD",
            allowed_tickers=allowed,
        )
        == []
    )
    assert _foreign_equity_subjects(
        "An unrelated Micron thesis was copied into the AMD report.",
        ticker="AMD",
        allowed_tickers=allowed,
    ) == ["MU"]


def test_ai_status_separates_enhanced_validation_from_retraining(
    session: Session,
) -> None:
    now = datetime.now(UTC)
    hypothesis = LogicChainHypothesis(
        cluster_job_id=1,
        title="Source-backed transmission hypothesis",
        premise_candidate_id="policy",
        outcome_candidate_id="market",
        steps=json.dumps(
            {
                "steps": [],
                "causal_validation": {
                    "validated_at": (now - timedelta(hours=1)).isoformat(),
                    "evidence_sources": [{"key": "treasury"}],
                    "evidence_facts": [{"ref": "market:US10Y:2026-08-02"}],
                },
            }
        ),
        confidence=0.4,
        rationale="Test rationale",
        evidence_document_ids="[]",
        status="suggested",
        model_name="ollama:test-local",
        prompt_version="logic-chain-v3",
        created_at=now - timedelta(hours=2),
        updated_at=now - timedelta(hours=1),
    )
    session.add(hypothesis)
    session.flush()
    session.add(
        LogicChainReviewSignal(
            hypothesis_id=hypothesis.id,
            decision="revised_accepted",
            reviewer_note="Use the observed yield change.",
            suggested_correction="Add a market expectations gate.",
            feature_snapshot="{}",
            created_at=now - timedelta(minutes=30),
        )
    )
    session.add(
        ResearchInquiry(
            question="Did the policy surprise reprice yields?",
            mode="autonomous",
            status="completed",
            local_model="ollama:test-local",
            result={},
            evidence_snapshot={"generated_at": now.isoformat()},
            created_at=now,
            updated_at=now,
        )
    )
    session.flush()

    status = build_ai_status(
        session,
        settings=Settings(
            _env_file=None,
            llm_provider="ollama",
            llm_model="test-local",
        ),
        now=now,
    )

    assert status.chains.total == 1
    assert status.chains.new_24h == 1
    assert status.chains.enhanced_evidence_validated == 1
    assert status.chains.since_last_training == 1
    assert status.model.state == "current"
    assert status.training.state == "signals_collected"
    assert status.training.review_signal_count == 1
    assert status.training.retraining_confirmed is False


def test_ai_status_confirms_training_only_from_artifact_manifest(
    session: Session,
    tmp_path: Path,
) -> None:
    trained_at = datetime.now(UTC) - timedelta(days=1)
    manifest_path = tmp_path / "training-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "training_run_id": "run-20260802-a",
                "model_name": "qwen-news-finance-v2",
                "base_model": "qwen3:14b-q4_K_M",
                "trained_at": trained_at.isoformat(),
                "training_signal_count": 18,
            }
        ),
        encoding="utf-8",
    )

    status = build_ai_status(
        session,
        settings=Settings(
            _env_file=None,
            llm_training_manifest_path=manifest_path,
        ),
    )

    assert status.training.state == "retraining_confirmed"
    assert status.training.retraining_confirmed is True
    assert status.training.training_run_id == "run-20260802-a"
    assert status.training.signal_count_used == 18


def test_openai_key_does_not_trigger_when_automatic_review_is_disabled(
    session: Session,
) -> None:
    openai_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal openai_calls
        if request.url.host == "api.openai.test":
            openai_calls += 1
            raise AssertionError("automatic OpenAI review must remain disabled")
        assert request.url.host == "ollama.test"
        return httpx.Response(200, json={"message": {"content": _local_result()}})

    inquiry = run_research(
        session,
        question="Will technology stocks keep rising?",
        mode="user_question",
        settings=Settings(
            _env_file=None,
            llm_provider="ollama",
            llm_base_url="http://ollama.test",
            llm_model="test-local",
            llm_max_attempts=1,
            openai_api_key=SecretStr("test-openai-key"),
            openai_auto_review_enabled=False,
            openai_review_base_url="https://api.openai.test/v1",
        ),
        transport=httpx.MockTransport(handler),
    )

    assert openai_calls == 0
    assert inquiry.chatgpt_review is None
    workflow = inquiry.evidence_snapshot["research_workflow"]
    openai_stage = next(
        item for item in workflow["stages"] if item["stage"] == "openai_review"
    )
    assert openai_stage["status"] == "skipped"
    assert openai_stage["reason"] == "automatic_review_disabled"
    assert workflow["status"] == "local_report_audited"
    assert inquiry.evidence_snapshot["local_report_audit"]["openai_used"] is False


def test_local_research_timeout_does_not_repeat_the_same_long_request() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        payload = json.loads(request.content)
        assert payload["options"]["num_predict"] == 12_288
        assert "one primary hypothesis is preferred" in payload["messages"][0]["content"]
        assert "exactly four factor_candidates" in payload["messages"][0]["content"]
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(ResearchProviderError, match="ReadTimeout"):
        _call_local_research_model(
            question="Will Apple fundamentals support its valuation?",
            mode="user_question",
            evidence={},
            settings=Settings(
                _env_file=None,
                llm_provider="ollama",
                llm_base_url="http://ollama.test",
                llm_model="test-local",
                llm_max_attempts=3,
            ),
            transport=httpx.MockTransport(handler),
        )

    assert calls == 1


def test_local_research_and_openai_review_are_stored(session: Session) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "ollama.test":
            return httpx.Response(
                200,
                json={"message": {"content": _local_result()}},
            )
        assert request.url.host == "api.openai.test"
        assert request.headers["authorization"] == "Bearer test-openai-key"
        payload = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": _openai_review(),
                        }
                    ],
                }
            ]
        }
        return httpx.Response(200, json=payload)

    settings = Settings(
        _env_file=None,
        llm_provider="ollama",
        llm_base_url="http://ollama.test",
        llm_model="test-local",
        llm_max_attempts=1,
        openai_api_key=SecretStr("test-openai-key"),
        openai_auto_review_enabled=True,
        openai_review_model="gpt-test",
        openai_review_base_url="https://api.openai.test/v1",
    )
    transport = httpx.MockTransport(handler)

    inquiry = run_research(
        session,
        question="Will technology stocks keep rising?",
        mode="user_question",
        settings=settings,
        transport=transport,
    )
    session.commit()

    assert inquiry.status == "completed"
    assert inquiry.result is not None
    assert inquiry.result.hypotheses[0].steps[1].status == "evidence_missing"
    assert inquiry.chatgpt_review is not None
    assert inquiry.evidence_snapshot["research_workflow"]["stages"][0][
        "stage"
    ] == "local_draft"
    reviewed = review_with_openai(
        session,
        inquiry_id=inquiry.id,
        settings=settings,
        transport=transport,
    )
    session.commit()
    assert reviewed.chatgpt_review is not None
    assert reviewed.chatgpt_review.recommendation == "defer_for_evidence"
    assert reviewed.chatgpt_review.model == "gpt-test"

    hypothesis = LogicChainHypothesis(
        cluster_job_id=1,
        title="Local policy-to-market hypothesis",
        premise_candidate_id="premise",
        outcome_candidate_id="outcome",
        steps=json.dumps(
            {
                "steps": [
                    {
                        "step_type": "reported_event",
                        "text": "Policy event",
                        "confidence": 0.5,
                        "evidence_refs": [],
                    },
                    {
                        "step_type": "inferred_mechanism",
                        "text": "Possible repricing",
                        "confidence": 0.4,
                        "evidence_refs": [],
                    },
                    {
                        "step_type": "possible_outcome",
                        "text": "Possible market response",
                        "confidence": 0.4,
                        "evidence_refs": [],
                    },
                ],
                "association_score": 0.4,
                "evidence_coverage_score": 0.0,
                "counterevidence": ["Alternative explanation"],
            }
        ),
        confidence=0.4,
        rationale="A local model proposal.",
        evidence_document_ids="[]",
        status="suggested",
        model_name="ollama:test-local",
        prompt_version="test",
    )
    session.add(hypothesis)
    session.commit()
    chain_review = review_logic_chain_with_openai(
        session,
        hypothesis_id=hypothesis.id,
        settings=settings,
        transport=transport,
    )
    session.commit()
    assert chain_review.recommendation == "defer_for_evidence"
    assert "chatgpt_review" in json.loads(hypothesis.steps)


def test_autonomous_research_uses_question_planner_before_analysis(
    session: Session,
) -> None:
    session.add(
        MarketSeries(
            series_id="TEST10Y",
            name="Test 10-year sovereign yield",
            category="sovereign_yield",
            unit="percent",
            frequency="daily",
            source_name="Test official source",
            source_url="https://example.test/yield",
        )
    )
    session.add(
        MarketSeries(
            series_id="TESTEQ",
            name="Test equity valuation index",
            category="equity_index",
            unit="index",
            frequency="daily",
            source_name="Test official source",
            source_url="https://example.test/equity",
        )
    )
    session.add_all(
        [
            MarketObservation(
                series_id="TEST10Y",
                observed_on=observed_on,
                value=value,
                fetched_at=datetime.now(UTC),
            )
            for observed_on, value in (
                (date(2016, 1, 4), 2.1),
                (date(2021, 1, 4), 1.2),
                (date(2021, 3, 4), 1.7),
                (date(2026, 1, 5), 4.4),
            )
        ]
    )
    session.add_all(
        [
            MarketObservation(
                series_id="TESTEQ",
                observed_on=observed_on,
                value=value,
                fetched_at=datetime.now(UTC),
            )
            for observed_on, value in (
                (date(2016, 1, 4), 100.0),
                (date(2021, 1, 4), 150.0),
                (date(2021, 3, 4), 140.0),
                (date(2026, 1, 5), 210.0),
            )
        ]
    )
    session.flush()
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                200,
                json={
                    "message": {
                        "content": json.dumps(
                            {
                                "question": (
                                    "During the January-March 2021 episode, did a "
                                    "50-basis-point yield rise affect equity "
                                    "valuations through discount rates?"
                                ),
                                "episode_start": "2021-01-01",
                                "episode_end": "2021-03-31",
                                "trigger_evidence_refs": [
                                    "market:TEST10Y:2021-01-04",
                                ],
                                "outcome_evidence_refs": [
                                    "market:TESTEQ:2021-03-04",
                                ],
                                "historical_context_refs": [
                                    "market:TEST10Y:2016-01-04",
                                    "market:TEST10Y:2026-01-05",
                                ],
                            }
                        )
                    }
                },
            )
        return httpx.Response(
            200,
            json={"message": {"content": _local_result()}},
        )

    result = run_research(
        session,
        question=None,
        mode="autonomous",
        settings=Settings(
            _env_file=None,
            llm_provider="ollama",
            llm_base_url="http://ollama.test",
            llm_model="test-local",
            llm_max_attempts=1,
        ),
        transport=httpx.MockTransport(handler),
    )

    assert calls == 3
    assert result.status == "completed"
    assert result.question.startswith("During the January-March 2021")
    assert result.evidence_snapshot["planned_question_evidence_refs"] == [
        "market:TEST10Y:2021-01-04",
        "market:TESTEQ:2021-03-04",
        "market:TEST10Y:2016-01-04",
        "market:TEST10Y:2026-01-05",
    ]
    assert result.evidence_snapshot["episode_window"] == {
        "start": "2021-01-01",
        "end": "2021-03-31",
        "duration_days": 90,
        "trigger_evidence_refs": ["market:TEST10Y:2021-01-04"],
        "outcome_evidence_refs": ["market:TESTEQ:2021-03-04"],
        "relationship_mode": "mediated_linear",
        "bridge_hypotheses": [],
    }
    assert result.evidence_snapshot["question_search_summary"]["required_ref_hits"] == 4
    assert result.evidence_snapshot["market_window_statistics"]
    revision_stage = next(
        stage
        for stage in result.evidence_snapshot["research_workflow"]["stages"]
        if stage["stage"] == "local_episode_repair"
    )
    assert revision_stage["reason"] == "deterministic_evidence_guard"
    cited_refs = {
        ref
        for hypothesis in result.result.hypotheses
        for step in hypothesis.steps
        for ref in step.evidence_refs
    }
    assert "market:TEST10Y:2021-01-04" in cited_refs
    assert "market:TESTEQ:2021-03-04" in cited_refs
    session.commit()
    inquiry_id = result.id
    session.expire_all()
    persisted = session.get(ResearchInquiry, inquiry_id)
    assert persisted is not None
    assert persisted.evidence_snapshot["planned_question_evidence_refs"] == [
        "market:TEST10Y:2021-01-04",
        "market:TESTEQ:2021-03-04",
        "market:TEST10Y:2016-01-04",
        "market:TEST10Y:2026-01-05",
    ]


def test_duplicate_research_hypotheses_are_removed() -> None:
    result = ModelResearchResult.model_validate_json(_local_result())
    duplicate = result.hypotheses[0].model_copy(deep=True)
    duplicate.title = "Capacity constraints could limit continued gains"
    duplicate.confidence = 0.7

    retained = _deduplicate_research_hypotheses(
        [result.hypotheses[0], duplicate]
    )

    assert len(retained) == 1


def test_plain_equity_question_is_expanded_without_extra_model_call() -> None:
    expanded = _expand_plain_user_question(
        "苹果还能涨吗？",
        evidence={
            "equity_research_context": {
                "ticker": "AAPL",
                "company": "Apple Inc.",
            }
        },
    )

    assert expanded is not None
    assert "用户原始问题：苹果还能涨吗？" in expanded
    assert "Apple Inc.（AAPL）" in expanded
    assert "产品与竞争" in expanded
    assert "供应商—工厂—原料—物流" in expanded


def test_directional_confidence_is_step_support_not_upside_probability() -> None:
    result = ModelResearchResult.model_validate_json(_local_result())
    explanation = _directional_confidence_explanation(
        result,
        validated_alpha=False,
    )

    assert explanation["score_kind"] == "directional_chain_support_not_price_probability"
    assert explanation["score"] == 0.47
    assert result.hypotheses[0].confidence == 0.47
    assert explanation["validated_alpha_supported"] is False
    assert explanation["blockers_zh"]


def test_episode_planning_keeps_history_as_context_only() -> None:
    market = [
        {
            "evidence_id": f"market:DGS10:{year}-01-02",
            "category": "sovereign_yield",
            "series_id": "DGS10",
            "name": "10-Year Treasury Yield",
            "observed_on": f"{year}-01-02",
            "value": value,
        }
        for year, value in ((2010, 3.8), (2018, 2.7), (2026, 4.2))
    ]
    market.extend(
        [
            {
                "evidence_id": f"market:PPIACO:{year}-01-01",
                "category": "inflation",
                "series_id": "PPIACO",
                "name": "Producer Price Index",
                "observed_on": f"{year}-01-01",
                "value": value,
            }
            for year, value in ((1913, 12.1), (2026, 269.4))
        ]
    )
    unrelated = [
        {
            "evidence_id": f"document:{year}",
            "category": "news_or_official_document",
            "title": "General policy news",
            "published_at": f"{year}-06-01T00:00:00Z",
        }
        for year in range(2011, 2026)
    ]

    anchors = _build_historical_anchors(
        {"market_observations": market, "documents": unrelated},
        focus="sovereign yields and asset valuation",
        limit=8,
    )
    episodes = _build_episode_candidates(
        {"market_observations": market, "documents": unrelated},
        focus="sovereign yields and asset valuation",
        limit=12,
    )
    plan = _fallback_episode_question_plan(
        episode_candidates=episodes,
        historical_anchors=anchors,
        focus="sovereign yields and asset valuation",
    )

    assert 7 <= (plan.episode_end - plan.episode_start).days + 1 <= 550
    assert plan.episode_start.isoformat() in plan.question
    assert plan.episode_end.isoformat() in plan.question
    assert plan.historical_context_refs


def test_autonomous_episode_candidates_start_with_complete_unused_period() -> None:
    periods = [
        {
            "year": year,
            "start": f"{year}-01-01",
            "end": f"{year}-12-31",
            "eligible": eligible,
            "coverage_score": score,
            "evidence_domains": domains,
        }
        for year, eligible, score, domains in (
            (2007, True, 0.82, 4),
            (2008, True, 0.84, 4),
            (2025, True, 0.95, 5),
            (2026, False, 0.70, 4),
        )
    ]
    event_table = {
        "reliable_start": "2007-01-01",
        "reliable_end": "2025-12-31",
        "eligible_years": [2007, 2008, 2025],
        "periods": periods,
    }
    preferred = select_preferred_research_period(
        event_table,
        prior_questions=[],
    )
    assert preferred is not None
    assert preferred["year"] == 2007
    market = [
        {
            "evidence_id": f"market:{series}:{year}-{month_day}",
            "category": category,
            "series_id": series,
            "name": name,
            "observed_on": f"{year}-{month_day}",
            "value": value,
        }
        for year in (2007, 2008, 2025, 2026)
        for series, month_day, category, name, value in (
            ("DGS10", "01-03", "sovereign_yield", "10-Year Treasury Yield", 4.0),
            ("SP500", "03-30", "equity_index", "S&P 500", 1_500.0),
        )
    ]
    candidates = _build_episode_candidates(
        {
            "market_observations": market,
            "research_event_table": event_table,
            "preferred_research_period": preferred,
        },
        focus="sovereign yields and asset valuation",
        limit=12,
    )

    assert candidates
    assert candidates[0]["preferred_period_overlap"] is True
    assert date.fromisoformat(candidates[0]["episode_start"]).year == 2007
    assert all(
        date.fromisoformat(candidate["episode_end"]).year <= 2025
        for candidate in candidates
    )

    next_preferred = select_preferred_research_period(
        event_table,
        prior_questions=["During 2007-2008, did the yield shock affect equities?"],
    )
    assert next_preferred is not None
    assert next_preferred["year"] == 2008


def test_planner_rejects_a_series_causing_itself() -> None:
    episode_items = [
        {
            "evidence_id": "market:DGS10:2025-01-02",
            "episode_section": "market_observations",
            "series_id": "DGS10",
            "name": "10-Year Treasury Yield",
            "observed_on": "2025-01-02",
            "category": "sovereign_yield",
        },
        {
            "evidence_id": "market:DGS10:2025-03-03",
            "episode_section": "market_observations",
            "series_id": "DGS10",
            "name": "10-Year Treasury Yield",
            "observed_on": "2025-03-03",
            "category": "sovereign_yield",
        },
    ]
    plan = PlannedResearchQuestion(
        question="Did the 10-year yield cause the 10-year yield during this episode?",
        episode_start=date(2025, 1, 1),
        episode_end=date(2025, 3, 31),
        trigger_evidence_refs=["market:DGS10:2025-01-02"],
        outcome_evidence_refs=["market:DGS10:2025-03-03"],
        historical_context_refs=[],
    )

    with pytest.raises(ValueError, match="same measured series"):
        _validate_planned_question_evidence(
            plan,
            episode_candidates=[{"items": episode_items}],
            historical_anchors=[],
        )


def test_planner_rejects_unrelated_country_pairing() -> None:
    episode_items = [
        {
            "evidence_id": "market:INDPRO:2024-01-01",
            "episode_section": "market_observations",
            "series_id": "INDPRO",
            "name": "U.S. Industrial Production",
            "observed_on": "2024-01-01",
            "category": "industrial_production",
        },
        {
            "evidence_id": "economic:NLD:CPI:2024",
            "episode_section": "economic_observations",
            "country": "Netherlands",
            "indicator_code": "CPI",
            "indicator": "Inflation, consumer prices",
            "year": 2024,
            "category": "economic",
        },
    ]
    plan = PlannedResearchQuestion(
        question="Did U.S. industrial production affect Dutch inflation in 2024?",
        episode_start=date(2024, 1, 1),
        episode_end=date(2024, 12, 31),
        trigger_evidence_refs=["market:INDPRO:2024-01-01"],
        outcome_evidence_refs=["economic:NLD:CPI:2024"],
        historical_context_refs=[],
    )

    with pytest.raises(ValueError, match="unrelated geographies"):
        _validate_planned_question_evidence(
            plan,
            episode_candidates=[{"items": episode_items}],
            historical_anchors=[],
        )


def test_nonlinear_plan_requires_measurable_bridge_hypotheses() -> None:
    episode_items = [
        {
            "evidence_id": "market:HYOAS:2025-01-02",
            "episode_section": "market_observations",
            "series_id": "HYOAS",
            "name": "High Yield Credit Spread",
            "observed_on": "2025-01-02",
            "category": "credit_spread",
        },
        {
            "evidence_id": "market:COAL:2025-03-03",
            "episode_section": "market_observations",
            "series_id": "COAL",
            "name": "Steam Coal Import Price",
            "observed_on": "2025-03-03",
            "category": "commodity_price",
        },
    ]
    plan = PlannedResearchQuestion(
        question="Did credit conditions interact with trade conditions to affect coal prices?",
        episode_start=date(2025, 1, 1),
        episode_end=date(2025, 3, 31),
        trigger_evidence_refs=["market:HYOAS:2025-01-02"],
        outcome_evidence_refs=["market:COAL:2025-03-03"],
        historical_context_refs=[],
        relationship_mode="nonlinear_exploratory",
    )

    with pytest.raises(ValueError, match="at least two measurable bridge"):
        _validate_planned_question_evidence(
            plan,
            episode_candidates=[{"items": episode_items}],
            historical_anchors=[],
        )

    plan.bridge_hypotheses = [
        "Corporate funding costs and working-capital conditions",
        "Coal inventory, procurement and import demand",
        "Freight, foreign-exchange and trade-flow transmission",
    ]
    _validate_planned_question_evidence(
        plan,
        episode_candidates=[{"items": episode_items}],
        historical_anchors=[],
    )
    assert len(plan.bridge_hypotheses) == 3


def test_fallback_planner_prefers_a_dated_documented_trigger() -> None:
    candidate = {
        "episode_start": "2024-03-01",
        "episode_end": "2024-04-01",
        "preferred_period_overlap": True,
        "coverage_score": 1.0,
        "evidence_domains": 5,
        "evidence_section_count": 2,
        "narrative_evidence_count": 1,
        "substantive_document_count": 1,
        "items": [
            {
                "evidence_id": "document:policy-cut",
                "episode_section": "documents",
                "title": "Federal Reserve policy rate cut lowers borrowing costs",
                "excerpt": (
                    "The dated policy announcement details the decision and "
                    "transmission channel. " * 3
                ),
                "published_at": "2024-03-01T00:00:00Z",
            },
            {
                "evidence_id": "market:DGS10:2024-03-01",
                "episode_section": "market_observations",
                "series_id": "DGS10",
                "name": "10-Year Treasury Yield",
                "category": "sovereign_yield",
                "observed_on": "2024-03-01",
            },
            {
                "evidence_id": "market:SP500:2024-04-01",
                "episode_section": "market_observations",
                "series_id": "SP500",
                "name": "S&P 500",
                "category": "equity_index",
                "observed_on": "2024-04-01",
            },
        ],
    }

    plan = _fallback_episode_question_plan(
        episode_candidates=[candidate],
        historical_anchors=[],
        focus="policy rates borrowing costs equity valuation",
        preferred_research_period={"year": 2024},
    )

    assert plan.trigger_evidence_refs == ["document:policy-cut"]
    assert plan.outcome_evidence_refs == ["market:SP500:2024-04-01"]


def test_financial_keyword_matching_does_not_use_latin_substrings() -> None:
    assert _text_relevance("restore polluted waterways", "oil rate") == 0
    assert _text_relevance("oil prices rose after the policy rate decision", "oil rate") == 2


def test_question_deduplication_allows_replication_in_disjoint_event_periods() -> None:
    prior = [
        "During 2009-2010, did industrial production affect CPI through energy costs?"
    ]

    assert not _duplicates_prior_question(
        "During 2011-2012, did industrial production affect CPI through energy costs?",
        prior,
    )
    assert _duplicates_prior_question(
        "During 2009-2010, did industrial production affect CPI through energy costs?",
        prior,
    )


def test_local_research_formatting_errors_are_safely_bounded() -> None:
    payload = json.loads(_local_result())
    payload["hypotheses"][0]["confidence"] = 0.95
    payload["hypotheses"][0]["steps"][0]["confidence"] = 0.8
    payload["hypotheses"][0]["steps"][0]["evidence_refs"] = [
        f"evidence:{index}" for index in range(14)
    ]
    payload["factor_candidates"] = [
        {
            "factor_id": f"company-demand-{index}",
            "name": "Company demand factor",
            "factor_type": "company",
            "direction": "positive",
            "transformation": "change",
            "lag_days": 400,
            "hypothesis": "Demand growth may affect forward returns.",
            "evidence_refs": [f"evidence:{ref}" for ref in range(24)],
            "confidence": 0.8,
            "training_p_value": 1.2,
            "adjusted_q_value": -0.1,
        }
        for index in range(18)
    ]
    payload["factor_research"] = {
        "factors": [{"confidence": 0.8}],
        "profit_validations": [{"forecast_horizon_days": 365}],
    }

    result = _validated_research_content(json.dumps(payload))

    assert result.hypotheses[0].confidence == 0.75
    assert result.hypotheses[0].steps[0].confidence == 0.75
    assert len(result.hypotheses[0].steps[0].evidence_refs) == 10
    assert len(result.factor_candidates) == 16
    assert result.factor_candidates[0].confidence == 0.75
    assert result.factor_candidates[0].lag_days == 365
    assert len(result.factor_candidates[0].evidence_refs) == 20
    assert result.factor_candidates[0].training_p_value == 1.0
    assert result.factor_candidates[0].adjusted_q_value == 0.0
    assert result.factor_research is None


def test_episode_sanitizer_removes_out_of_window_citations_and_caps_confidence() -> None:
    result = ModelResearchResult.model_validate_json(_local_result())
    result.hypotheses[0].steps[0].status = "verified"
    result.hypotheses[0].steps[0].evidence_refs = [
        "market:IN:2010-01-02",
        "economic:OUT:CPI:2025",
    ]
    sanitized = _sanitize_research_result(
        result,
        evidence={
            "episode_window": {
                "start": "2010-01-01",
                "end": "2010-12-31",
            },
            "planned_question_evidence_refs": ["market:IN:2010-01-02"],
            "market_observations": [
                {
                    "evidence_id": "market:IN:2010-01-02",
                    "observed_on": "2010-01-02",
                }
            ],
            "economic_observations": [
                {
                    "evidence_id": "economic:OUT:CPI:2025",
                    "year": 2025,
                }
            ],
        },
    )

    assert sanitized.hypotheses[0].steps[0].evidence_refs == [
        "market:IN:2010-01-02"
    ]
    assert sanitized.hypotheses[0].confidence < 0.4


def test_market_curves_alone_cannot_verify_an_intermediate_causal_mechanism() -> None:
    payload = json.loads(_local_result())
    payload["question"] = "Did industrial production affect the oil price?"
    payload["summary"] = "Industrial production and the oil price moved in the episode."
    hypothesis = payload["hypotheses"][0]
    hypothesis["title"] = "Industrial production and the oil price"
    hypothesis["premise"] = "Industrial production declined."
    hypothesis["outcome"] = "The oil price declined."
    hypothesis["steps"] = [
        {
            "sequence": 1,
            "label": "Industrial production declined",
            "status": "verified",
            "confidence": 0.7,
            "evidence_refs": ["market:INDPRO:2024-01-01"],
        },
        {
            "sequence": 2,
            "label": "Oil demand declined",
            "status": "verified",
            "confidence": 0.7,
            "evidence_refs": ["derived:market-window:WTI:2024"],
        },
        {
            "sequence": 3,
            "label": "The oil price declined",
            "status": "verified",
            "confidence": 0.7,
            "evidence_refs": ["market:WTI:2024-12-31"],
        },
    ]
    result = ModelResearchResult.model_validate(payload)
    evidence = {
        "planned_question_evidence_refs": [
            "market:INDPRO:2024-01-01",
            "market:WTI:2024-12-31",
        ],
        "market_window_statistics": [
            {"evidence_id": "derived:market-window:WTI:2024"}
        ],
    }

    assert _planned_result_needs_repair(result, evidence=evidence)

    result.hypotheses[0].steps[1].evidence_refs.append("document:oil-demand")
    assert not _planned_result_needs_repair(result, evidence=evidence)


def test_planned_result_rejects_prior_episode_subject_drift() -> None:
    payload = json.loads(_local_result())
    payload["question"] = (
        "Did U.S. High Yield Option-Adjusted Spread affect Cleveland steam coal "
        "import prices?"
    )
    payload["summary"] = (
        "High yield spreads did not directly explain renewable diesel exports."
    )
    hypothesis = payload["hypotheses"][0]
    hypothesis["title"] = "High yield spreads and renewable diesel exports"
    hypothesis["premise"] = "High yield spreads changed."
    hypothesis["outcome"] = "Renewable diesel exports changed."
    hypothesis["steps"][0]["evidence_refs"] = [
        "market:HYOAS:2024-12-31"
    ]
    hypothesis["steps"][1]["evidence_refs"] = [
        "market:COAL-CLE:2025-08-22"
    ]
    result = ModelResearchResult.model_validate(payload)
    evidence = {
        "episode_window": {
            "trigger_evidence_refs": ["market:HYOAS:2024-12-31"],
            "outcome_evidence_refs": ["market:COAL-CLE:2025-08-22"],
        },
        "planned_question_evidence_refs": [
            "market:HYOAS:2024-12-31",
            "market:COAL-CLE:2025-08-22",
        ],
        "market_observations": [
            {
                "evidence_id": "market:HYOAS:2024-12-31",
                "name": "U.S. High Yield Option-Adjusted Spread",
            },
            {
                "evidence_id": "market:COAL-CLE:2025-08-22",
                "name": (
                    "Import price: steam coal: total world: Cleveland, OH: quarterly"
                ),
            },
        ],
    }

    assert _planned_result_needs_repair(result, evidence=evidence)


def test_numerical_quality_gate_downgrades_nonpositive_price_claim() -> None:
    result = ModelResearchResult.model_validate_json(_local_result())
    rejected_ref = "energy:COAL.IMPORT_PRICE.TEST.Q:2025Q4"
    result.hypotheses[0].steps[-1].status = "verified"
    result.hypotheses[0].steps[-1].confidence = 0.72
    result.hypotheses[0].steps[-1].evidence_refs = [rejected_ref]
    evidence = {
        "energy_observations": [
            {
                "evidence_id": rejected_ref,
                "category": "energy_or_commodity",
                "name": "Import price: steam coal: quarterly",
                "value": 0.0,
                "unit": "$/short ton",
            }
        ],
        "planned_question_evidence_refs": [rejected_ref],
        "priority_evidence": [{"evidence_id": rejected_ref, "value": 0.0}],
        "episode_window": {"outcome_evidence_refs": [rejected_ref]},
    }

    gated = _apply_numerical_evidence_quality_gate(result, evidence=evidence)

    step = gated.hypotheses[0].steps[-1]
    assert step.status == "evidence_missing"
    assert step.evidence_refs == []
    assert step.confidence == 0.1
    assert gated.hypotheses[0].confidence <= 0.2
    assert "not verified" in gated.summary
    assert evidence["energy_observations"] == []
    assert evidence["planned_question_evidence_refs"] == []
    assert evidence["episode_window"]["outcome_evidence_refs"] == []
    assert evidence["research_quality_gate"]["status"] == "claims_downgraded"
    assert evidence["quality_rejected_evidence"][0]["evidence_id"] == rejected_ref


def _local_result() -> str:
    return """{
      "question": "Will technology stocks keep rising?",
      "summary": "The direction remains conditional on demand and physical capacity.",
      "hypotheses": [{
        "title": "Capacity constraints could limit continued gains",
        "premise": "AI demand remains strong",
        "outcome": "Technology equity performance may diverge",
        "scope": {
          "companies": ["Example Chip"],
          "sectors": ["Semiconductors"],
          "products": ["Accelerators"],
          "supply_chain_inputs": ["Electricity", "Copper"],
          "infrastructure": ["Data centers"],
          "policies": ["Export controls"],
          "geographies": ["East Asia"]
        },
        "steps": [
          {
            "sequence": 1,
            "label": "Demand is the proposed premise",
            "status": "hypothesis",
            "confidence": 0.55,
            "evidence_refs": []
          },
          {
            "sequence": 2,
            "label": "Power capacity may constrain deployments",
            "status": "evidence_missing",
            "confidence": 0.4,
            "evidence_refs": ["invented:reference"]
          },
          {
            "sequence": 3,
            "label": "Valuations may respond to capacity and earnings",
            "status": "hypothesis",
            "confidence": 0.45,
            "evidence_refs": []
          }
        ],
        "counterarguments": ["Software efficiency could reduce power intensity"],
        "evidence_gaps": ["Company guidance", "Regional power capacity"],
        "confidence": 0.45
      }],
      "suggested_next_questions": ["Which regions have binding grid constraints?"]
    }"""


def _openai_review() -> str:
    return """{
      "recommendation": "defer_for_evidence",
      "overall_assessment": "The chain is plausible but not yet evidenced.",
      "revised_summary": "Treat the result as a scenario pending capacity data.",
      "confidence_adjustment": -0.1,
      "findings": [{
        "severity": "high",
        "finding": "The power constraint is unsupported.",
        "suggested_revision": "Add regional grid and company demand evidence.",
        "evidence_refs": []
      }],
      "missing_evidence": ["Regional grid capacity", "Company guidance"]
    }"""
