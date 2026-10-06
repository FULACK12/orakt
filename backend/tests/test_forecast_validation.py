"""Walk-forward news forecast and human report review tests."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.db.enums import SourceType
from app.db.models import Document, ResearchInquiry, Source
from app.research import (
    _sanitize_research_result,
    record_research_review,
    refresh_research_forecasts,
)
from app.schemas.research import ModelNewsForecast, ModelResearchResult


def _research_result(*, anchor: Document, as_of: datetime) -> ModelResearchResult:
    return ModelResearchResult.model_validate(
        {
            "question": "Did the conflict announcement affect Brent oil?",
            "summary": "A timestamped possibility requires later evidence.",
            "hypotheses": [
                {
                    "title": "Conflict risk and Brent oil",
                    "premise": "The government announced possible military action.",
                    "outcome": "Brent oil could rise.",
                    "scope": {
                        "companies": [],
                        "sectors": ["energy"],
                        "products": ["Brent oil"],
                        "supply_chain_inputs": ["crude oil"],
                        "infrastructure": ["shipping lanes"],
                        "policies": [],
                        "geographies": ["Iran", "United States"],
                    },
                    "steps": [
                        {
                            "sequence": 1,
                            "label": "Military action was announced",
                            "status": "verified",
                            "confidence": 0.6,
                            "evidence_refs": [f"document:{anchor.id}"],
                        },
                        {
                            "sequence": 2,
                            "label": "Supply risk premium may increase",
                            "status": "hypothesis",
                            "confidence": 0.4,
                            "evidence_refs": [],
                        },
                        {
                            "sequence": 3,
                            "label": "Brent oil may rise",
                            "status": "hypothesis",
                            "confidence": 0.4,
                            "evidence_refs": [],
                        },
                    ],
                    "counterarguments": ["Demand expectations may dominate supply risk."],
                    "evidence_gaps": ["Post-announcement Brent observations"],
                    "confidence": 0.4,
                }
            ],
            "suggested_next_questions": [],
            "news_forecasts": [
                ModelNewsForecast(
                    forecast_id="forecast:iran-brent",
                    anchor_evidence_ref=f"document:{anchor.id}",
                    anchor_title=anchor.title,
                    as_of=as_of,
                    hypothesis="Conflict risk could add an oil supply premium.",
                    mechanism_chain=[
                        "Military risk raises disruption probability",
                        "Expected supply tightens and risk premium rises",
                    ],
                    expected_outcome="Brent oil price rises within 30 days.",
                    horizon_days=30,
                    falsification_conditions=["Brent does not rise within 30 days"],
                    confidence=0.45,
                ).model_dump(mode="json")
            ],
        }
    )


def test_later_news_can_update_a_timestamped_forecast() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    anchor_time = datetime.now(UTC) - timedelta(days=10)
    with Session(engine) as session:
        source = Source(
            name="Test News",
            country="US",
            language="en",
            source_type=SourceType.NEWS,
            credibility_baseline=Decimal("0.800"),
        )
        anchor = Document(
            source=source,
            url="https://example.test/anchor",
            title="United States announces possible military action against Iran",
            body="Officials announced that military action against Iran was possible. " * 3,
            published_at=anchor_time,
            content_hash="a" * 64,
        )
        later = Document(
            source=source,
            url="https://example.test/later",
            title="Brent oil price rises as Iran conflict risk increases",
            body="Brent oil prices rose while reports cited increased Iran conflict risk. " * 3,
            published_at=anchor_time + timedelta(days=3),
            content_hash="b" * 64,
        )
        session.add_all([anchor, later])
        session.flush()
        result = _research_result(anchor=anchor, as_of=anchor_time)
        row = ResearchInquiry(
            question=result.question,
            mode="user_question",
            status="completed",
            local_model="ollama:test-local",
            result=result.model_dump(mode="json"),
            evidence_snapshot={},
        )
        session.add(row)
        session.flush()

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/chat"
            return httpx.Response(
                200,
                json={
                    "message": {
                        "content": json.dumps(
                            {
                                "decisions": [
                                    {
                                        "forecast_id": "forecast:iran-brent",
                                        "status": "partially_supported",
                                        "validation_summary": (
                                            "Later reporting supports the predicted direction, "
                                            "but does not isolate the causal mechanism."
                                        ),
                                        "supporting_evidence_refs": [f"document:{later.id}"],
                                        "contradicting_evidence_refs": [],
                                        "confidence": 0.55,
                                    }
                                ]
                            }
                        )
                    }
                },
            )

        refresh = refresh_research_forecasts(
            session,
            settings=Settings(
                llm_provider="ollama",
                llm_model="test-local",
                llm_max_attempts=1,
            ),
            transport=httpx.MockTransport(handler),
        )

        assert refresh["forecasts_checked"] == 1
        assert refresh["forecasts_updated"] == 1
        stored = ModelResearchResult.model_validate(row.result)
        forecast = stored.news_forecasts[0]
        assert forecast.status == "partially_supported"
        assert forecast.supporting_evidence_refs == [f"document:{later.id}"]
        assert row.evidence_snapshot["forecast_validation_cases"]

        view = record_research_review(
            session,
            inquiry_id=row.id,
            decision="revised_accepted",
            reviewer_note="Keep the direction but weaken the causal wording.",
        )
        assert view.review_signals[-1].decision == "revised_accepted"
        assert "weaken" in (view.review_signals[-1].reviewer_note or "")
    engine.dispose()


def test_missing_model_forecasts_receive_a_low_confidence_fallback() -> None:
    anchor_time = datetime.now(UTC) - timedelta(days=1)
    anchor = Document(
        id=12,
        source_id=1,
        url="https://example.test/fallback",
        title="A policy shock is reported",
        body="Substantive policy reporting " * 10,
        published_at=anchor_time,
        content_hash="c" * 64,
    )
    result = _research_result(anchor=anchor, as_of=anchor_time)
    result.news_forecasts = []

    sanitized = _sanitize_research_result(
        result,
        evidence={
            "documents": [
                {
                    "evidence_id": "document:12",
                    "published_at": anchor_time.isoformat(),
                }
            ],
            "news_forecast_anchors": [
                {
                    "evidence_id": "document:12",
                    "title": anchor.title,
                    "published_at": anchor_time.isoformat(),
                }
            ],
        },
    )

    assert len(sanitized.news_forecasts) == 1
    assert sanitized.news_forecasts[0].status == "unresolved"
    assert sanitized.news_forecasts[0].confidence <= 0.3
    assert sanitized.news_forecasts[0].falsification_conditions
