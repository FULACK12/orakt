"""Local-AI logic hypotheses and append-only feedback tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.causal_validation import build_rule_validation
from app.core.config import Settings
from app.db.base import Base
from app.db.enums import ClusterJobStatus, SourceType
from app.db.models import ClusterJob, Document, Source
from app.logic_chains import (
    _fit_logic_prompt_context,
    _human_review_guidance,
    _select_candidates,
    _validated_model_batch,
    list_logic_hypotheses,
    list_training_signals,
    persist_logic_hypotheses,
    refresh_recent_logic_hypotheses,
    review_logic_hypothesis,
    validate_logic_hypotheses,
)
from app.schemas.cluster_jobs import ClusterJobResult
from app.schemas.clusters import (
    ClusterCandidate,
    ClusterDocumentFingerprint,
    ClusterPreviewResponse,
    EventClusterPreview,
)
from app.schemas.extractions import EvidenceSpan, ExtractedEvent
from app.schemas.logic_chains import (
    ModelLogicHypothesis,
    ModelLogicHypothesisBatch,
    ModelLogicStep,
)


def _candidate(
    candidate_id: str,
    document: Document,
    event_type: str,
) -> ClusterCandidate:
    return ClusterCandidate(
        candidate_id=candidate_id,
        document_id=document.id,
        event_index=0,
        extractor="test",
        event=ExtractedEvent(
            event_type=event_type,
            title=document.title,
            summary=document.body,
            entities=[],
            location=None,
            occurred_at=document.published_at,
            severity=0.5,
            confidence=0.8,
            evidence_spans=[
                EvidenceSpan(
                    field="summary",
                    source_field="title",
                    start_char=0,
                    end_char=len(document.title),
                    quote=document.title,
                )
            ],
        ),
    )


def test_review_feedback_is_append_only_training_data() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with Session(engine) as session:
        source = Source(
            name="Logic test source",
            language="en",
            source_type=SourceType.RSS,
            credibility_baseline=Decimal("0.800"),
        )
        premise_document = Document(
            source=source,
            url="https://example.test/rate",
            title="Central bank raises policy rate",
            body="Central bank raises policy rate.",
            language="en",
            published_at=now,
            content_hash="1" * 64,
        )
        outcome_document = Document(
            source=source,
            url="https://example.test/equities",
            title="Equity index closes lower",
            body="Equity index closes lower.",
            language="en",
            published_at=now + timedelta(hours=4),
            content_hash="2" * 64,
        )
        session.add_all([premise_document, outcome_document])
        session.flush()
        candidates = [
            _candidate("premise", premise_document, "monetary_policy"),
            _candidate("outcome", outcome_document, "market_move"),
        ]
        preview = ClusterPreviewResponse(
            embedding_provider="test",
            requested_document_ids=[
                premise_document.id,
                outcome_document.id,
            ],
            document_fingerprints=[
                ClusterDocumentFingerprint(
                    document_id=document.id,
                    content_hash=document.content_hash,
                )
                for document in [premise_document, outcome_document]
            ],
            candidate_count=2,
            clusters=[
                EventClusterPreview(
                    cluster_id=index,
                    representative_candidate_id=candidate.candidate_id,
                    members=[candidate],
                )
                for index, candidate in enumerate(candidates, start=1)
            ],
            merge_edges=[],
            rejected_near_matches=[],
            potential_duplicate_document_ids=[],
            review_signature="f" * 64,
        )
        job = ClusterJob(
            status=ClusterJobStatus.COMPLETED,
            total_documents=2,
            processed_documents=2,
            batch_size=2,
            parameters={
                "document_ids": [
                    premise_document.id,
                    outcome_document.id,
                ],
                "batch_size": 2,
                "merge_threshold": 0.86,
                "time_window_hours": 48,
                "location_radius_km": 100,
            },
            result=ClusterJobResult(
                preview=preview,
                merge_cluster_ids=[],
                review_cluster_ids=[],
                independent_cluster_ids=[1, 2],
            ).model_dump(mode="json"),
            completed_at=now,
        )
        session.add(job)
        session.flush()
        batch = ModelLogicHypothesisBatch(
            hypotheses=[
                ModelLogicHypothesis(
                    title="Rate decision and possible equity response",
                    premise_candidate_id="premise",
                    outcome_candidate_id="outcome",
                    steps=[
                        ModelLogicStep(
                            step_type="reported_event",
                            text=premise_document.title,
                            candidate_id="premise",
                        ),
                        ModelLogicStep(
                            step_type="inferred_mechanism",
                            text="Tighter funding conditions may reduce liquidity.",
                        ),
                        ModelLogicStep(
                            step_type="possible_outcome",
                            text=outcome_document.title,
                            candidate_id="outcome",
                        ),
                    ],
                    confidence=0.66,
                    rationale="A hypothesis for review, not proof of causality.",
                    evidence_document_ids=[
                        premise_document.id,
                        outcome_document.id,
                    ],
                )
            ]
        )

        assert (
            persist_logic_hypotheses(
                session,
                job_id=job.id,
                batch=batch,
                model_name="ollama:test",
            )
            == 1
        )
        hypothesis = list_logic_hypotheses(
            session,
            job_id=job.id,
        ).hypotheses[0]
        assert hypothesis.steps[0].candidate_id == "premise"
        assert hypothesis.steps[-1].candidate_id == "outcome"
        assert hypothesis.steps[-1].step_type == "possible_outcome"
        assert (
            validate_logic_hypotheses(
                session,
                job_id=job.id,
                settings=Settings(llm_provider="mock", _env_file=None),
                include_external_evidence=False,
            )
            == 1
        )
        hypothesis = list_logic_hypotheses(
            session,
            job_id=job.id,
        ).hypotheses[0]
        assert hypothesis.causal_validation is not None
        assert hypothesis.causal_validation.conclusion == "temporal_correlation_only"
        assert len(hypothesis.causal_validation.checks) == 6
        assert (
            next(
                check
                for check in hypothesis.causal_validation.checks
                if check.check_key == "market_expectations"
            ).status
            == "missing_evidence"
        )
        assert hypothesis.causal_validation.recalculated_confidence <= 0.45
        assert hypothesis.causal_validation.confidence_breakdown is not None
        assert (
            hypothesis.causal_validation.confidence_breakdown.final_confidence
            == hypothesis.causal_validation.recalculated_confidence
        )
        assert len(hypothesis.causal_validation.reasoning_trace) == 6
        assert hypothesis.causal_validation.reviewer_recommendation == "deferred"
        assert any(
            item.key == "rate_expectations"
            for item in hypothesis.causal_validation.next_data_suggestions
        )
        review_logic_hypothesis(
            session,
            hypothesis_id=hypothesis.id,
            decision="rejected",
            reviewer_note="Mechanism needs a funding-market source.",
            suggested_correction="Add evidence for the liquidity step.",
        )
        review_logic_hypothesis(
            session,
            hypothesis_id=hypothesis.id,
            decision="deferred",
            reviewer_note="Waiting for rate-path and Treasury evidence.",
            suggested_correction="Add 2Y/10Y yields and alternative causes.",
        )
        review_logic_hypothesis(
            session,
            hypothesis_id=hypothesis.id,
            decision="revised_accepted",
            reviewer_note="Direction accepted after adding the missing steps.",
            suggested_correction="Keep the outcome phrased as possible.",
        )
        session.commit()

        response = list_logic_hypotheses(session, job_id=job.id)
        signals = list_training_signals(session)
        assert response.hypotheses[0].status == "revised_accepted"
        assert response.training_signal_count == 3
        assert len(response.hypotheses[0].historical_cases) == 3
        assert response.hypotheses[0].historical_cases[0].similarity_score > 0.95
        assert signals.signal_count == 3
        assert {signal.suggested_correction for signal in signals.signals} == {
            "Add evidence for the liquidity step.",
            "Add 2Y/10Y yields and alternative causes.",
            "Keep the outcome phrased as possible.",
        }
        guidance = _human_review_guidance(session)
        assert guidance[0]["decision"] == "revised_accepted"
        assert guidance[0]["suggested_correction"] == ("Keep the outcome phrased as possible.")
    engine.dispose()


def test_logic_candidate_selection_mixes_signal_priority_with_recency() -> None:
    candidates = [
        {
            "candidate_id": "latest",
            "event_type": "celebration",
            "title": "Community festival opens",
            "summary": "Community festival opens",
            "occurred_at": "2026-07-29T12:00:00+00:00",
        },
        {
            "candidate_id": "policy",
            "event_type": "central_bank_policy",
            "title": "Central bank raises rate",
            "summary": "The policy rate changed",
            "occurred_at": "2026-07-28T12:00:00+00:00",
        },
        {
            "candidate_id": "market",
            "event_type": "market_move",
            "title": "Equity market closes lower",
            "summary": "Stock market report",
            "occurred_at": "2026-07-27T12:00:00+00:00",
        },
    ]

    selected = _select_candidates(candidates, 3)

    assert {row["candidate_id"] for row in selected[:2]} == {
        "policy",
        "market",
    }
    assert selected[2]["candidate_id"] == "latest"


def test_logic_candidate_selection_uses_one_substantive_event_per_document() -> None:
    candidates = [
        {
            "candidate_id": "policy:0",
            "document_id": 1,
            "evidence_tier": "feed_content",
            "event_type": "central_bank_policy",
            "title": "Central bank raises rate",
            "summary": "Inflation pressure changes the policy rate",
            "occurred_at": "2026-07-28T12:00:00+00:00",
        },
        {
            "candidate_id": "policy:1",
            "document_id": 1,
            "evidence_tier": "feed_content",
            "event_type": "market_commentary",
            "title": "The same article discusses bond yields",
            "summary": "Bond and currency markets repriced",
            "occurred_at": "2026-07-28T13:00:00+00:00",
        },
        {
            "candidate_id": "market:0",
            "document_id": 2,
            "evidence_tier": "feed_content",
            "event_type": "market_move",
            "title": "Equity market closes lower",
            "summary": "Stock market report",
            "occurred_at": "2026-07-29T12:00:00+00:00",
        },
        {
            "candidate_id": "headline:0",
            "document_id": 3,
            "evidence_tier": "headline_only",
            "event_type": "market_move",
            "title": "Market headline without article text",
            "summary": "Market headline without article text",
            "occurred_at": "2026-07-30T12:00:00+00:00",
        },
    ]

    selected = _select_candidates(candidates, 2)

    assert len(selected) == 2
    assert {row["document_id"] for row in selected} == {1, 2}
    assert all(row["evidence_tier"] == "feed_content" for row in selected)


def test_logic_refresh_marks_empty_completed_snapshot_as_audited() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with Session(engine) as session:
        preview = ClusterPreviewResponse(
            embedding_provider="test",
            requested_document_ids=[],
            document_fingerprints=[],
            candidate_count=0,
            clusters=[],
            merge_edges=[],
            rejected_near_matches=[],
            potential_duplicate_document_ids=[],
            review_signature="a" * 64,
        )
        job = ClusterJob(
            status=ClusterJobStatus.COMPLETED,
            total_documents=2,
            processed_documents=2,
            batch_size=2,
            parameters={
                "document_ids": [1, 2],
                "batch_size": 2,
                "merge_threshold": 0.86,
                "time_window_hours": 48,
                "location_radius_km": 100,
            },
            result=ClusterJobResult(
                preview=preview,
                merge_cluster_ids=[],
                review_cluster_ids=[],
                independent_cluster_ids=[],
            ).model_dump(mode="json"),
            completed_at=now,
        )
        session.add(job)
        session.flush()

        first = refresh_recent_logic_hypotheses(
            session,
            settings=Settings(llm_provider="mock", _env_file=None),
            limit=1,
        )
        session.commit()
        second = refresh_recent_logic_hypotheses(
            session,
            settings=Settings(llm_provider="mock", _env_file=None),
            limit=1,
        )

        assert first["jobs_completed"] == 1
        assert first["jobs_attempted"] == 1
        assert second["jobs_attempted"] == 0
        assert job.result["logic_generation"]["status"] == "completed"
        assert job.result["logic_generation"]["hypotheses"] == 0
        parsed_result = ClusterJobResult.model_validate(job.result)
        assert parsed_result.logic_generation is not None
        assert parsed_result.logic_generation.status == "completed"
    engine.dispose()


def test_model_batch_validation_clamps_scores_and_skips_bad_items() -> None:
    payload = _validated_model_batch(
        """
        {
          "hypotheses": [
            {
              "title": "Policy path repricing chain",
              "premise_candidate_id": "premise",
              "outcome_candidate_id": "outcome",
              "steps": [
                {
                  "step_type": "reported_event",
                  "text": "The central bank published its decision.",
                  "candidate_id": "premise",
                  "confidence": 0.95,
                  "relevance": 1.2,
                  "evidence_refs": ["document:1"]
                },
                {
                  "step_type": "inferred_mechanism",
                  "text": "The expected policy path was repriced.",
                  "confidence": 0.82,
                  "relevance": 0.9
                },
                {
                  "step_type": "possible_outcome",
                  "text": "The equity index moved.",
                  "candidate_id": "outcome"
                }
              ],
              "confidence": 0.9,
              "association_score": 1.4,
              "evidence_coverage_score": -0.2,
              "rationale": "Reviewable but not causal.",
              "evidence_document_ids": [1, 2],
              "counterevidence": []
            },
            {"bad": "item"}
          ]
        }
        """
    )

    assert len(payload.hypotheses) == 1
    hypothesis = payload.hypotheses[0]
    assert hypothesis.confidence == 0.75
    assert hypothesis.association_score == 1
    assert hypothesis.evidence_coverage_score == 0
    assert hypothesis.steps[0].confidence == 0.75
    assert hypothesis.steps[0].relevance == 1


def test_logic_prompt_context_enforces_input_budget() -> None:
    candidates = [
        {
            "candidate_id": f"{index}:0",
            "document_id": index,
            "event_type": "market_move",
            "title": "Equity and credit market repricing " * 20,
            "summary": "Detailed financial context " * 100,
            "occurred_at": "2026-07-30T12:00:00+00:00",
            "country_code": "US",
            "entities": ["Federal Reserve"] * 12,
        }
        for index in range(36)
    ]
    evidence = {
        "market_observations": [
            {
                "evidence_id": f"market:DGS10:{index}",
                "value": 4.2 + index / 100,
                "description": "Verbose market observation " * 40,
            }
            for index in range(80)
        ],
        "economic_cycle": {
            "regime": "late_cycle",
            "components": [{"series": "DGS10", "score": 0.5}] * 7,
        },
        "evidence_rules": ["Do not claim causality."] * 8,
    }

    result = _fit_logic_prompt_context(candidates, evidence, max_chars=12_000)
    serialized = __import__("json").dumps(
        result,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    assert len(serialized) <= 12_000
    assert 8 <= len(result["candidates"]) <= 18


def test_fed_chain_requires_expectations_yields_and_primary_communication() -> None:
    hypothesis = ModelLogicHypothesis(
        title="FOMC rate path repricing and Nasdaq response",
        premise_candidate_id="fomc",
        outcome_candidate_id="nasdaq",
        steps=[
            ModelLogicStep(
                step_type="reported_event",
                text="The FOMC published its rate decision.",
                candidate_id="fomc",
                evidence_refs=["document:1"],
            ),
            ModelLogicStep(
                step_type="inferred_mechanism",
                text="Fed Funds Futures repriced a higher-for-longer path.",
                evidence_refs=["expectations:after"],
            ),
            ModelLogicStep(
                step_type="market_observation",
                text="Both 2Y and 10Y Treasury yields rose.",
                evidence_refs=[
                    "treasury-yields:2026-06-16",
                    "treasury-yields:2026-06-17",
                ],
            ),
            ModelLogicStep(
                step_type="inferred_mechanism",
                text="Higher discount rates pressured growth-stock valuation.",
                evidence_refs=["treasury-yields:2026-06-17"],
            ),
            ModelLogicStep(
                step_type="possible_outcome",
                text="The Nasdaq closed lower.",
                candidate_id="nasdaq",
                evidence_refs=["document:2"],
            ),
        ],
        confidence=0.7,
        association_score=0.8,
        evidence_coverage_score=0.9,
        rationale="A fully enumerated but still observational mechanism.",
        evidence_document_ids=[1, 2],
        counterevidence=["Weak technology earnings may explain the decline."],
    )
    evidence = {
        "market_expectations": [
            {
                "evidence_id": "expectations:before",
                "category": "market_expectation",
                "observed_on": "2026-06-16",
                "reference_start": "2026-09-01",
                "mean_rate_bps": 375.0,
                "source": "Atlanta Fed MPT",
                "source_url": "https://example.test/mpt",
            },
            {
                "evidence_id": "expectations:after",
                "category": "market_expectation",
                "observed_on": "2026-06-18",
                "reference_start": "2026-09-01",
                "mean_rate_bps": 388.0,
                "source": "Atlanta Fed MPT",
                "source_url": "https://example.test/mpt",
            },
        ],
        "treasury_yields": [
            {
                "evidence_id": "treasury-yields:2026-06-16",
                "category": "treasury_yield",
                "observed_on": "2026-06-16",
                "two_year": 3.71,
                "ten_year": 4.19,
                "source": "U.S. Treasury",
                "source_url": "https://example.test/treasury",
            },
            {
                "evidence_id": "treasury-yields:2026-06-17",
                "category": "treasury_yield",
                "observed_on": "2026-06-17",
                "two_year": 3.78,
                "ten_year": 4.24,
                "source": "U.S. Treasury",
                "source_url": "https://example.test/treasury",
            },
        ],
        "federal_reserve_items": [
            {
                "evidence_id": "fed:test",
                "category": "official_policy_communication",
            }
        ],
        "fred_observations": [
            {
                "evidence_id": "fred:NASDAQCOM:2026-06-16",
                "category": "market_index",
                "series_id": "NASDAQCOM",
                "observed_on": "2026-06-16",
                "value": 19_500,
            },
            {
                "evidence_id": "fred:NASDAQCOM:2026-06-17",
                "category": "market_index",
                "series_id": "NASDAQCOM",
                "observed_on": "2026-06-17",
                "value": 19_200,
            },
        ],
    }

    result = build_rule_validation(
        hypothesis,
        premise={
            "candidate_id": "fomc",
            "document_id": 1,
            "event_type": "monetary_policy",
            "title": "FOMC rate decision",
            "summary": "The FOMC published its statement.",
            "occurred_at": "2026-06-17T18:00:00+00:00",
        },
        outcome={
            "candidate_id": "nasdaq",
            "document_id": 2,
            "event_type": "market_move",
            "title": "Nasdaq closes lower",
            "summary": "The stock market declined.",
            "occurred_at": "2026-06-17T21:00:00+00:00",
        },
        structured_evidence=evidence,
        settings=Settings(_env_file=None),
        validator_model="rules:test",
    )

    assert result.conclusion == "mechanism_supported_not_causal"
    assert (
        next(check for check in result.checks if check.check_key == "causal_sufficiency").status
        == "passed"
    )
    assert result.causality_is_confirmed is False
    assert result.confidence_breakdown is not None
    assert len(result.confidence_breakdown.components) == 6
    assert result.reviewer_recommendation == "revised_accepted"
    assert len(result.reasoning_trace) == 6
    assert any(fact.used_by_checks for fact in result.evidence_facts)
