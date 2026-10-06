"""Source-reviewed supplier graph and factor bridge tests."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    CompanyProfile,
    CompanySupplyChainCoverage,
    CompanySupplyChainEdge,
    MarketObservation,
    MarketSeries,
)
from app.factor_mining import _factors_from_supplier_evidence
from app.supply_chain import (
    build_supply_chain_evidence,
    count_verified_supply_chain_edges,
    refresh_supply_chain_coverage,
    supply_chain_coverage_rows,
)


def test_verified_supplier_edge_becomes_dated_evidence_and_exploratory_factor() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            CompanyProfile(
                ticker="AAPL",
                cik="0000320193",
                name="Apple Inc.",
                sector="Technology",
                industry="Consumer electronics",
                source_url="https://www.sec.gov/edgar/browse/?CIK=320193",
            )
        )
        session.add_all(
            [
                MarketSeries(
                    series_id="EQ:AAPL",
                    name="Apple adjusted close",
                    category="equity_price",
                    unit="USD",
                    frequency="daily",
                    source_name="Twelve Data",
                    source_url="https://twelvedata.com/",
                ),
                MarketSeries(
                    series_id="EQ:TSM",
                    name="TSMC adjusted close",
                    category="equity_price",
                    unit="USD",
                    frequency="daily",
                    source_name="Twelve Data",
                    source_url="https://twelvedata.com/",
                ),
            ]
        )
        start = date(2026, 1, 1)
        fetched = datetime(2026, 8, 30, tzinfo=UTC)
        for offset in range(150):
            observed_on = start + timedelta(days=offset)
            supplier_price = 100 + offset * 0.35 + (offset % 7) * 0.2
            target_price = 200 + offset * 0.5 + ((offset - 1) % 7) * 0.25
            session.add_all(
                [
                    MarketObservation(
                        series_id="EQ:AAPL",
                        observed_on=observed_on,
                        value=target_price,
                        fetched_at=fetched,
                    ),
                    MarketObservation(
                        series_id="EQ:TSM",
                        observed_on=observed_on,
                        value=supplier_price,
                        fetched_at=fetched,
                    ),
                ]
            )
        edge = CompanySupplyChainEdge(
            subject_ticker="AAPL",
            related_company_name="Taiwan Semiconductor Manufacturing Co.",
            related_ticker="TSM",
            relationship_type="foundry",
            product_or_input="advanced application processors",
            geography="Taiwan",
            dependency_level="high",
            review_status="verified",
            confidence=0.9,
            source_kind="issuer_supplier_disclosure",
            source_ref="supplier-list:2025:tsmc",
            source_url="https://example.test/official-supplier-list",
            source_excerpt="The issuer lists Taiwan Semiconductor Manufacturing as a supplier.",
            observed_at=date(2025, 12, 31),
            available_at=date(2026, 2, 1),
            valid_from=date(2025, 1, 1),
            valid_to=None,
        )
        session.add(edge)
        session.commit()

        edges, factors = build_supply_chain_evidence(
            session,
            ticker="AAPL",
            as_of=date(2026, 5, 30),
        )
        verified_total = count_verified_supply_chain_edges(
            session,
            ticker="AAPL",
            as_of=date(2026, 5, 30),
        )
        evidence = {"derived_equity_evidence": [*edges, *factors]}
        allowed_refs = {
            item["evidence_id"] for item in evidence["derived_equity_evidence"]
        }
        mined = _factors_from_supplier_evidence(evidence, allowed_refs)
        refresh_supply_chain_coverage(session, ticker="AAPL")
        coverage = supply_chain_coverage_rows(session)

    assert len(edges) == 1
    assert verified_total == 1
    assert edges[0]["review_status"] == "verified"
    assert len(factors) == 1
    assert factors[0]["supplier_series_id"] == "EQ:TSM"
    assert factors[0]["sample_size"] >= 60
    assert mined[0].factor_type == "supply_chain"
    assert mined[0].lag_days == 1
    assert mined[0].evidence_refs == [factors[0]["evidence_id"], edges[0]["evidence_id"]]
    assert coverage[0]["verified_edges"] == 1
    assert coverage[0]["related_companies_with_market_data"] == 1
    engine.dispose()


def test_unreviewed_supplier_candidate_cannot_enter_research_evidence() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            CompanyProfile(
                ticker="MSFT",
                cik="0000789019",
                name="Microsoft Corp.",
                sector="Technology",
                industry="Software",
                source_url="https://www.sec.gov/edgar/browse/?CIK=789019",
            )
        )
        session.add(
            CompanySupplyChainEdge(
                subject_ticker="MSFT",
                related_company_name="Unverified Vendor",
                related_ticker=None,
                relationship_type="supplier",
                product_or_input="data-center equipment",
                geography=None,
                dependency_level="unknown",
                review_status="candidate",
                confidence=0.4,
                source_kind="news_candidate",
                source_ref="document:1",
                source_url="https://example.test/candidate",
                source_excerpt="A report speculates about a vendor relationship.",
                observed_at=date(2026, 1, 1),
                available_at=date(2026, 1, 2),
            )
        )
        session.commit()

        edges, factors = build_supply_chain_evidence(
            session,
            ticker="MSFT",
            as_of=date(2026, 8, 30),
        )

    assert edges == []
    assert factors == []
    engine.dispose()


def test_unnamed_dependency_uses_category_basket_without_inventing_supplier() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            CompanyProfile(
                ticker="MU",
                cik="0000723125",
                name="Micron Technology, Inc.",
                sector="Technology",
                industry="Semiconductors",
                source_url="https://www.sec.gov/edgar/browse/?CIK=723125",
            )
        )
        session.add_all(
            [
                MarketSeries(
                    series_id=series_id,
                    name=name,
                    category="equity_price",
                    unit="USD",
                    frequency="daily",
                    source_name="Twelve Data",
                    source_url="https://twelvedata.com/",
                )
                for series_id, name in (
                    ("EQ:MU", "Micron adjusted close"),
                    ("EQ:ASML", "ASML adjusted close"),
                    ("EQ:AMAT", "Applied Materials adjusted close"),
                )
            ]
        )
        start = date(2026, 1, 1)
        fetched = datetime(2026, 8, 30, tzinfo=UTC)
        for offset in range(150):
            observed_on = start + timedelta(days=offset)
            session.add_all(
                [
                    MarketObservation(
                        series_id="EQ:MU",
                        observed_on=observed_on,
                        value=80 + offset * 0.25 + (offset % 5) * 0.1,
                        fetched_at=fetched,
                    ),
                    MarketObservation(
                        series_id="EQ:ASML",
                        observed_on=observed_on,
                        value=600 + offset * 0.6 + (offset % 7) * 0.3,
                        fetched_at=fetched,
                    ),
                    MarketObservation(
                        series_id="EQ:AMAT",
                        observed_on=observed_on,
                        value=140 + offset * 0.3 + (offset % 3) * 0.2,
                        fetched_at=fetched,
                    ),
                ]
            )
        session.add(
            CompanySupplyChainEdge(
                subject_ticker="MU",
                related_company_name="Undisclosed photolithography equipment supplier",
                related_ticker=None,
                relationship_type="equipment",
                product_or_input="photolithography tools",
                geography=None,
                dependency_level="sole_source",
                review_status="verified",
                confidence=0.88,
                source_kind="issuer_filing",
                source_ref="sec:mu:10-k:equipment-risk",
                source_url="https://www.sec.gov/Archives/edgar/data/723125/example.htm",
                source_excerpt=(
                    "The issuer states that it is sometimes dependent on a single supplier "
                    "for photolithography equipment."
                ),
                observed_at=date(2025, 12, 31),
                available_at=date(2026, 1, 20),
            )
        )
        session.commit()

        edges, factors = build_supply_chain_evidence(
            session,
            ticker="MU",
            as_of=date(2026, 5, 30),
        )
        evidence = {"derived_equity_evidence": [*edges, *factors]}
        allowed_refs = {
            item["evidence_id"] for item in evidence["derived_equity_evidence"]
        }
        mined = _factors_from_supplier_evidence(evidence, allowed_refs)

    assert len(edges) == 1
    assert edges[0]["related_ticker"] is None
    assert len(factors) == 1
    assert factors[0]["proxy_type"] == "category_basket"
    assert factors[0]["identity_status"] == "unnamed_dependency_not_supplier_identification"
    assert factors[0]["supplier_series_id"] == "BASKET:semiconductor_manufacturing_equipment"
    assert {item["series_id"] for item in factors[0]["basket_components"]} == {
        "EQ:ASML",
        "EQ:AMAT",
    }
    assert "not asserted to be suppliers" in factors[0]["limitations"][0]
    assert mined[0].factor_id.startswith("supply-category:")
    assert "并未披露具体供应商" in mined[0].hypothesis
    assert mined[0].confidence <= 0.4
    engine.dispose()


def test_coverage_read_removes_stale_review_gap_when_candidates_are_zero() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            CompanyProfile(
                ticker="AAPL",
                cik="0000320193",
                name="Apple Inc.",
                sector="Technology",
                industry="Consumer electronics",
                source_url="https://www.sec.gov/edgar/browse/?CIK=320193",
            )
        )
        session.add(
            CompanySupplyChainCoverage(
                ticker="AAPL",
                status="pending",
                candidate_edges=0,
                verified_edges=0,
                related_companies_with_market_data=0,
                gaps=[
                    "candidate relationships require source review",
                    "facility and production-line mapping",
                ],
            )
        )
        session.commit()

        rows = supply_chain_coverage_rows(session)

    assert rows[0]["gaps"] == ["facility and production-line mapping"]
    engine.dispose()
