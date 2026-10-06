"""Archived SEC product-operating evidence extraction tests."""

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import CompanyFiling, CompanyProfile, CompanySupplyChainCoverage
from app.product_evidence import (
    build_product_operating_evidence,
    summarize_product_operating_evidence,
)


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_filing(
    session: Session,
    *,
    ticker: str,
    accession: str,
    relative_path: str,
) -> None:
    session.add(
        CompanyProfile(
            ticker=ticker,
            cik=accession[:10],
            name="Micron Technology" if ticker == "MU" else "Microsoft Corporation",
            sector="Technology",
            industry="Semiconductors" if ticker == "MU" else "Software",
            source_url="https://www.sec.gov/",
        )
    )
    session.add(
        CompanyFiling(
            accession_number=accession,
            ticker=ticker,
            form="10-K",
            filed_at=date(2026, 8, 1),
            report_date=date(2026, 6, 30),
            fiscal_year=2026,
            fiscal_period="FY",
            primary_document=relative_path.rsplit("/", 1)[-1],
            source_url=f"https://www.sec.gov/Archives/{accession}",
        )
    )
    session.add(
        CompanySupplyChainCoverage(
            ticker=ticker,
            status="verified_partial",
            latest_filing_accession=accession,
            latest_filing_date=date(2026, 8, 1),
            latest_raw_archive_path=relative_path,
            gaps=[],
        )
    )
    session.commit()


def test_mu_product_evidence_preserves_reported_ranges_and_plan_status(tmp_path) -> None:
    relative = "raw/sec/company-filings/MU/filing.htm"
    filing_path = tmp_path / relative
    filing_path.parent.mkdir(parents=True)
    filing_path.write_text(
        """
        <html><body>
        <p>Total reported DRAM revenue was $28.58 billion in 2025, $17.60 billion in
        2024, and $10.98 billion in 2023.</p>
        <p>Sales of DRAM products increased 62% primarily due to a low-40% range
        increase in average selling prices and a mid-teen percentage increase in bit
        shipments.</p>
        <p>Our HBM4 technology is advancing and remains on schedule for volume
        production in calendar 2026.</p>
        </body></html>
        """,
        encoding="utf-8",
    )
    with _session() as session:
        _seed_filing(
            session,
            ticker="MU",
            accession="0000723125-26-000001",
            relative_path=relative,
        )
        evidence = build_product_operating_evidence(
            session,
            ticker="MU",
            as_of=date(2026, 9, 1),
            cold_data_root=tmp_path,
        )

    asp = next(item for item in evidence if item["metric_type"] == "price_and_volume_change")
    assert asp["evidence_status"] == "reported_actual"
    assert "62%" in asp["reported_values"]
    assert "low-40% range" in asp["reported_values"]
    assert "mid-teen percentage" in asp["reported_values"]
    assert "40%" not in asp["reported_values"]
    plan = next(item for item in evidence if item["product"] == "HBM4")
    assert plan["evidence_status"] == "forward_looking_plan"
    assert any("not counted as realized" in value for value in plan["limitations"])
    coverage = summarize_product_operating_evidence(evidence)
    assert coverage["reported_actual_count"] == 2
    assert coverage["forward_looking_plan_count"] == 1
    assert coverage["status"] == "partial"


def test_msft_rpo_is_retained_with_contract_limitation(tmp_path) -> None:
    relative = "raw/sec/company-filings/MSFT/filing.htm"
    filing_path = tmp_path / relative
    filing_path.parent.mkdir(parents=True)
    filing_path.write_text(
        """
        <html><body>
        <p>Commercial remaining performance obligation increased 84% to $678 billion.</p>
        <p>We expect to recognize approximately 30% of total and commercial RPO
        revenue over the next 12 months.</p>
        </body></html>
        """,
        encoding="utf-8",
    )
    with _session() as session:
        _seed_filing(
            session,
            ticker="MSFT",
            accession="0001193125-26-000001",
            relative_path=relative,
        )
        evidence = build_product_operating_evidence(
            session,
            ticker="MSFT",
            as_of=date(2026, 9, 1),
            cold_data_root=tmp_path,
        )

    rpo = next(item for item in evidence if item["metric_name"].startswith("commercial remaining"))
    assert rpo["reported_values"] == ["84%", "$678 billion"]
    assert any("not treated as an irrevocable" in value for value in rpo["limitations"])
    plan = next(item for item in evidence if item["metric_type"] == "contract_timing")
    assert plan["evidence_status"] == "forward_looking_plan"


def test_aapl_product_evidence_combines_latest_10q_with_annual_filing(tmp_path) -> None:
    annual_accession = "0000320193-25-000079"
    annual_relative = (
        "raw/sec/company-filings/AAPL/000032019325000079/aapl-20250927.htm"
    )
    quarter_accession = "0000320193-26-000020"
    quarter_relative = (
        "raw/sec/company-filings/AAPL/000032019326000020/aapl-20260627.htm"
    )
    for relative, text in (
        (
            annual_relative,
            "<p>Services net sales increased 14% during 2025 compared to 2024.</p>",
        ),
        (
            quarter_relative,
            "<p>iPhone net sales increased 9% during the third quarter of 2026.</p>",
        ),
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    with _session() as session:
        session.add(
            CompanyProfile(
                ticker="AAPL",
                cik="0000320193",
                name="Apple Inc.",
                sector="Technology",
                industry="Consumer electronics",
                source_url="https://www.sec.gov/",
            )
        )
        session.add_all(
            [
                CompanyFiling(
                    accession_number=annual_accession,
                    ticker="AAPL",
                    form="10-K",
                    filed_at=date(2025, 10, 31),
                    report_date=date(2025, 9, 27),
                    fiscal_year=2025,
                    fiscal_period="FY",
                    primary_document="aapl-20250927.htm",
                    source_url="https://www.sec.gov/aapl-20250927.htm",
                ),
                CompanyFiling(
                    accession_number=quarter_accession,
                    ticker="AAPL",
                    form="10-Q",
                    filed_at=date(2026, 7, 31),
                    report_date=date(2026, 6, 27),
                    fiscal_year=2026,
                    fiscal_period="Q3",
                    primary_document="aapl-20260627.htm",
                    source_url="https://www.sec.gov/aapl-20260627.htm",
                ),
            ]
        )
        session.commit()
        evidence = build_product_operating_evidence(
            session,
            ticker="AAPL",
            as_of=date(2026, 9, 1),
            cold_data_root=tmp_path,
        )

    assert {item["source_periodicity"] for item in evidence} == {"annual", "quarterly"}
    quarter = next(item for item in evidence if item["source_periodicity"] == "quarterly")
    assert quarter["filing_form"] == "10-Q"
    assert quarter["fiscal_period"] == "Q3"
    assert quarter["reported_values"] == ["9%"]
    coverage = summarize_product_operating_evidence(evidence)
    assert coverage["annual_evidence_count"] == 1
    assert coverage["quarterly_evidence_count"] == 1
    assert coverage["latest_period_end"] == "2026-06-27"


def test_lulu_annual_filing_yields_operating_and_supply_exposure(tmp_path) -> None:
    relative = "raw/sec/company-filings/LULU/lulu-20260201.htm"
    filing_path = tmp_path / relative
    filing_path.parent.mkdir(parents=True)
    filing_path.write_text(
        """
        <html><body>
        <p>During 2025, our women's, men's, and accessories and other categories
        represented 63%, 24%, and 13% of net revenue, respectively.</p>
        <p>Approximately 40% of our products were manufactured in Vietnam, 18% in
        Cambodia, 11% in Sri Lanka, 11% in Indonesia, and 7% in Bangladesh.</p>
        <p>Approximately 34% of the fabric used in our products originated from
        Taiwan, 29% from China Mainland, 10% from South Korea, 10% from Vietnam.</p>
        <p>We do not, however, have any long-term contracts with the majority of our
        suppliers or manufacturing sources.</p>
        </body></html>
        """,
        encoding="utf-8",
    )
    with _session() as session:
        _seed_filing(
            session,
            ticker="LULU",
            accession="0001397187-26-000020",
            relative_path=relative,
        )
        evidence = build_product_operating_evidence(
            session,
            ticker="LULU",
            as_of=date(2026, 9, 1),
            cold_data_root=tmp_path,
        )

    assert len(evidence) == 4
    assert sum(item["evidence_status"] == "reported_actual" for item in evidence) == 3
    assert any(item["metric_type"] == "fabric_origin_mix" for item in evidence)
    coverage = summarize_product_operating_evidence(evidence)
    assert coverage["status"] == "partial"
    assert coverage["risk_disclosure_count"] == 1


def test_product_evidence_rejects_archive_path_outside_root(tmp_path) -> None:
    with _session() as session:
        _seed_filing(
            session,
            ticker="MU",
            accession="0000723125-26-000002",
            relative_path="../outside.htm",
        )
        evidence = build_product_operating_evidence(
            session,
            ticker="MU",
            as_of=date(2026, 9, 1),
            cold_data_root=tmp_path,
        )

    assert evidence == []


def test_product_evidence_respects_point_in_time_cutoff(tmp_path) -> None:
    relative = "raw/sec/company-filings/MU/filing.htm"
    filing_path = tmp_path / relative
    filing_path.parent.mkdir(parents=True)
    filing_path.write_text(
        "<p>Total reported DRAM revenue was $28.58 billion in 2025.</p>",
        encoding="utf-8",
    )
    with _session() as session:
        _seed_filing(
            session,
            ticker="MU",
            accession="0000723125-26-000003",
            relative_path=relative,
        )
        evidence = build_product_operating_evidence(
            session,
            ticker="MU",
            as_of=date(2026, 7, 31),
            cold_data_root=tmp_path,
        )

    assert evidence == []
