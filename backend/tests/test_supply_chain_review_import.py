"""Auditable supply-chain candidate decision import tests."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    CompanyProfile,
    CompanySupplyChainCoverage,
    CompanySupplyChainEdge,
)
from app.supply_chain_review_import import (
    SupplyChainReviewDecision,
    apply_supply_chain_review_decisions,
)


def test_checked_review_decision_verifies_edge_and_records_audit() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            CompanyProfile(
                ticker="ADI",
                cik="0000006281",
                name="Analog Devices Inc.",
                sector="Technology",
                industry="Semiconductors",
                source_url="https://www.sec.gov/edgar/browse/?CIK=6281",
            )
        )
        edge = _candidate()
        session.add(
            CompanySupplyChainCoverage(
                ticker="ADI",
                status="needs_review",
                candidate_edges=1,
                verified_edges=0,
                related_companies_with_market_data=0,
                gaps=[
                    "candidate relationships require source review",
                    "facility and production-line mapping",
                ],
            )
        )
        session.add(edge)
        session.commit()
        result = apply_supply_chain_review_decisions(
            session,
            decisions=[
                SupplyChainReviewDecision(
                    edge_id=edge.id,
                    subject_ticker="ADI",
                    related_ticker="TSM",
                    relationship_type="foundry",
                    decision="verified",
                    rationale="The filing explicitly says ADI sources wafers from TSMC.",
                )
            ],
            reviewed_by="test_reviewer",
        )
        session.refresh(edge)
        coverage = session.get(CompanySupplyChainCoverage, "ADI")

    assert result.verified == 1
    assert edge.review_status == "verified"
    assert edge.reviewed_by == "test_reviewer"
    assert edge.reviewed_at is not None
    assert "explicitly" in str(edge.review_note)
    assert coverage is not None
    assert coverage.candidate_edges == 0
    assert coverage.verified_edges == 1
    assert "candidate relationships require source review" not in coverage.gaps
    engine.dispose()


def test_review_import_rejects_identity_mismatch() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        edge = _candidate()
        session.add(edge)
        session.commit()
        with pytest.raises(ValueError, match="identity changed"):
            apply_supply_chain_review_decisions(
                session,
                decisions=[
                    SupplyChainReviewDecision(
                        edge_id=edge.id,
                        subject_ticker="ADI",
                        related_ticker="GFS",
                        relationship_type="foundry",
                        decision="verified",
                        rationale="This deliberately mismatches the retained ticker identity.",
                    )
                ],
                reviewed_by="test_reviewer",
            )
    engine.dispose()


def _candidate() -> CompanySupplyChainEdge:
    return CompanySupplyChainEdge(
        subject_ticker="ADI",
        related_company_name="Taiwan Semiconductor Manufacturing Company",
        related_ticker="TSM",
        relationship_type="foundry",
        product_or_input="wafer fabrication",
        geography="Taiwan",
        dependency_level="unknown",
        review_status="candidate",
        confidence=0.58,
        source_kind="sec_filing_candidate",
        source_ref="sec-filing:ADI:test:foundry:TSM",
        source_url="https://example.test/adi-10k.htm",
        source_excerpt="We source wafer requirements from TSMC.",
        observed_at=date(2025, 12, 31),
        available_at=date(2026, 2, 1),
    )
