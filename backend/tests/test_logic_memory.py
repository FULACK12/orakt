"""Verified logic memory and external training quarantine tests."""

from __future__ import annotations

import json
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import LogicChainHypothesis
from app.logic_memory import (
    build_training_dataset,
    import_external_training_examples,
    list_external_training_examples,
    qualified_logic_memories,
    review_external_training_example,
)
from app.schemas.logic_chains import ExternalTrainingImportRequest


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    engine.dispose()


def test_only_human_approved_evidence_sufficient_chain_becomes_memory(
    session: Session,
) -> None:
    qualified = _logic_chain(status="accepted", conclusion="mechanism_supported_not_causal")
    correlation_only = _logic_chain(
        status="accepted",
        conclusion="temporal_correlation_only",
        premise="other-premise",
        outcome="other-outcome",
    )
    suggested = _logic_chain(
        status="suggested",
        conclusion="mechanism_supported_not_causal",
        premise="third-premise",
        outcome="third-outcome",
    )
    session.add_all([qualified, correlation_only, suggested])
    session.flush()

    memories = qualified_logic_memories(session)

    assert [memory.hypothesis_id for memory in memories] == [qualified.id]
    assert memories[0].validated_confidence == 0.62
    assert len(memories[0].evidence_facts) == 2


def test_external_examples_are_quarantined_until_human_approval(
    session: Session,
) -> None:
    request = ExternalTrainingImportRequest.model_validate(
        {
            "examples": [
                {
                    "title": "Policy repricing and equity valuation",
                    "instruction": "Build a dated and auditable transmission chain.",
                    "input_context": "A policy statement and market observations are supplied.",
                    "ideal_response": "Separate the decision, expectations, yields and valuation.",
                    "evidence": [
                        {
                            "label": "Official policy statement",
                            "source_url": "https://example.org/policy",
                            "observed_at": "2024-03-01",
                            "excerpt": "The official statement reported the dated decision.",
                        }
                    ],
                    "source_name": "Licensed research set",
                    "source_url": "https://example.org/dataset",
                    "license_name": "CC-BY-4.0",
                }
            ]
        }
    )

    first = import_external_training_examples(session, request)
    repeated = import_external_training_examples(session, request)
    inventory = list_external_training_examples(session)
    before = build_training_dataset(session)

    assert first.imported_count == 1
    assert repeated.duplicate_count == 1
    assert inventory.pending_count == 1
    assert before.approved_external_count == 0

    review_external_training_example(
        session,
        example_id=inventory.examples[0].id,
        status="approved",
        quality_score=0.8,
        review_note="Evidence and license checked.",
    )
    after = build_training_dataset(session)

    assert after.approved_external_count == 1
    assert after.example_count == 1
    assert after.training_performed is False
    assert after.examples[0].metadata["license"] == "CC-BY-4.0"


def _logic_chain(
    *,
    status: str,
    conclusion: str,
    premise: str = "premise",
    outcome: str = "outcome",
) -> LogicChainHypothesis:
    checks = [
        {
            "check_key": key,
            "status": "passed",
            "explanation_en": "Supported by retained evidence.",
            "explanation_zh": "有本地证据支持。",
            "evidence_refs": ["fact:1"],
        }
        for key in (
            "premise_reported",
            "outcome_time_window",
            "mechanism_evidence",
            "market_expectations",
            "alternative_explanations",
            "causal_sufficiency",
        )
    ]
    analysis = {
        "steps": [
            {"sequence": 1, "text": "Reported premise", "evidence_refs": ["fact:1"]},
            {"sequence": 2, "text": "Supported mechanism", "evidence_refs": ["fact:2"]},
            {"sequence": 3, "text": "Measured outcome", "evidence_refs": ["fact:2"]},
        ],
        "association_score": 0.7,
        "evidence_coverage_score": 0.8,
        "counterevidence": ["An alternative explanation remains possible."],
        "causal_validation": {
            "validated_at": "2024-01-01T00:00:00Z",
            "conclusion": conclusion,
            "recalculated_confidence": 0.62,
            "checks": checks,
            "evidence_facts": [
                {"evidence_id": "fact:1", "label": "Premise fact"},
                {"evidence_id": "fact:2", "label": "Outcome fact"},
            ],
            "summary_en": "The mechanism is supported but causality is not proven.",
            "summary_zh": "机制得到支持, 但没有证明因果关系。",
        },
    }
    return LogicChainHypothesis(
        cluster_job_id=1,
        title=f"{premise} to {outcome}",
        premise_candidate_id=premise,
        outcome_candidate_id=outcome,
        steps=json.dumps(analysis, ensure_ascii=False),
        confidence=0.7,
        rationale="Auditable mechanism",
        evidence_document_ids="[1, 2]",
        status=status,
        model_name="ollama:test",
        prompt_version="test-v1",
        decided_at=datetime.now(UTC) if status != "suggested" else None,
    )
