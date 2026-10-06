"""Quality-gated bridge-evidence resolver tests."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.data_quality import audit_market_rows
from app.db.base import Base
from app.db.models import MarketObservation, MarketSeries
from app.evidence_completion import complete_research_evidence
from app.schemas.research import ModelResearchResult


def _research_result() -> ModelResearchResult:
    return ModelResearchResult.model_validate(
        {
            "question": "Can credit conditions transmit into steam coal prices?",
            "summary": "A quality-gated bridge test.",
            "hypotheses": [
                {
                    "title": "Credit and coal bridge",
                    "premise": "Credit spreads change.",
                    "outcome": "Steam coal import prices change.",
                    "scope": {
                        "companies": [],
                        "sectors": ["Energy"],
                        "products": ["Steam coal"],
                        "supply_chain_inputs": [],
                        "infrastructure": ["Rail and port"],
                        "policies": [],
                        "geographies": ["United States"],
                    },
                    "steps": [
                        {
                            "sequence": 1,
                            "label": "High-yield credit spreads change",
                            "status": "verified",
                            "confidence": 0.6,
                            "evidence_refs": [],
                        },
                        {
                            "sequence": 2,
                            "label": "Funding and coal procurement conditions change",
                            "status": "evidence_missing",
                            "confidence": 0.2,
                            "evidence_refs": [],
                        },
                        {
                            "sequence": 3,
                            "label": "Steam coal import price changes",
                            "status": "evidence_missing",
                            "confidence": 0.2,
                            "evidence_refs": [],
                        },
                    ],
                    "counterarguments": [],
                    "evidence_gaps": [],
                    "confidence": 0.25,
                }
            ],
            "suggested_next_questions": [],
        }
    )


def test_price_quality_gate_rejects_zero_placeholders() -> None:
    series = MarketSeries(
        series_id="COAL",
        name="Steam coal import price",
        category="commodity_price",
        unit="USD/short ton",
        frequency="daily",
        source_name="Test",
        source_url="https://example.test/coal",
    )
    rows = [
        MarketObservation(
            series_id="COAL",
            observed_on=date(2025, 1, 1) + timedelta(days=index),
            value=0.0,
            fetched_at=datetime.now(UTC),
        )
        for index in range(10)
    ]

    quality = audit_market_rows(
        series,
        rows,
        window_start=date(2025, 1, 1),
        window_end=date(2025, 1, 10),
    )

    assert quality.can_verify_claims is False
    assert quality.invalid_value_count == 10
    assert "no_valid_observations" in quality.flags


def test_financial_condition_index_accepts_negative_values_and_flat_periods() -> None:
    series = MarketSeries(
        series_id="NFCI",
        name="National Financial Conditions Index",
        category="financial_conditions",
        unit="index",
        frequency="weekly",
        source_name="FRED",
        source_url="https://fred.test/nfci",
    )
    rows = [
        MarketObservation(
            series_id="NFCI",
            observed_on=date(2025, 1, 1) + timedelta(days=index * 7),
            value=-0.4,
            fetched_at=datetime.now(UTC),
        )
        for index in range(10)
    ]

    quality = audit_market_rows(
        series,
        rows,
        window_start=date(2025, 1, 1),
        window_end=date(2025, 3, 8),
    )

    assert quality.invalid_value_count == 0
    assert "suspicious_flatline" not in quality.flags
    assert quality.can_verify_claims is True


def test_bridge_resolver_keeps_valid_credit_data_and_rejects_zero_coal() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                MarketSeries(
                    series_id="BAMLH0A0HYM2",
                    name="U.S. High Yield Option-Adjusted Spread",
                    category="credit_spread",
                    unit="percent",
                    frequency="daily",
                    source_name="FRED",
                    source_url="https://fred.test/spread",
                ),
                MarketSeries(
                    series_id="COAL",
                    name="Steam coal import price",
                    category="commodity_price",
                    unit="USD/short ton",
                    frequency="daily",
                    source_name="Test",
                    source_url="https://example.test/coal",
                ),
                MarketSeries(
                    series_id="HIST:TRUE",
                    name="Truecar historical price",
                    category="equity_price",
                    unit="USD",
                    frequency="daily",
                    source_name="Fixture",
                    source_url="https://example.test/true",
                ),
            ]
        )
        for index in range(60):
            observed_on = date(2025, 1, 1) + timedelta(days=index)
            session.add_all(
                [
                    MarketObservation(
                        series_id="BAMLH0A0HYM2",
                        observed_on=observed_on,
                        value=3.0 + index / 100,
                        fetched_at=datetime.now(UTC),
                    ),
                    MarketObservation(
                        series_id="COAL",
                        observed_on=observed_on,
                        value=0.0,
                        fetched_at=datetime.now(UTC),
                    ),
                    MarketObservation(
                        series_id="HIST:TRUE",
                        observed_on=observed_on,
                        value=5 + index / 10,
                        fetched_at=datetime.now(UTC),
                    ),
                ]
            )
        session.flush()
        evidence: dict[str, object] = {}

        completion = complete_research_evidence(
            session,
            result=_research_result(),
            evidence=evidence,
            window_start=date(2025, 1, 1),
            window_end=date(2025, 3, 1),
        )

        assert completion.segment_count == 2
        assert completion.candidate_data_segments >= 1
        coal_candidates = [
            candidate
            for segment in completion.segments
            for candidate in segment.candidates
            if candidate.series_id == "COAL"
        ]
        assert coal_candidates
        assert all(not candidate.quality.can_verify_claims for candidate in coal_candidates)
        assert all(not ref.startswith("market:COAL:") for ref in completion.added_evidence_refs)
        assert all(
            candidate.series_id != "HIST:TRUE"
            for segment in completion.segments
            for candidate in segment.candidates
        )
        assert any(
            ref.startswith("market:BAMLH0A0HYM2:")
            for ref in completion.added_evidence_refs
        )
    engine.dispose()
