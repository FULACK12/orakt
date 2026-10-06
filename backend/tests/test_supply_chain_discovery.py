"""Official annual-filing archive and named-relationship discovery tests."""

import asyncio
from datetime import date

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import CompanyFiling, CompanyProfile, CompanySupplyChainCoverage
from app.storage.archive import ColdArchive
from app.supply_chain_discovery import (
    SUPPLY_CHAIN_PARSER_VERSION,
    RelatedEntity,
    discover_sec_supply_chain_candidates,
    extract_disclosed_role_relationships,
    extract_named_relationships,
)


def test_extractor_keeps_quoted_supplier_relation_but_rejects_competition() -> None:
    payload = b"""
    <html><body>
      <p>We rely on Taiwan Semiconductor Manufacturing Company Limited (TSMC)
      for wafer fabrication of advanced processors, and it is a single-source supplier.</p>
      <p>We compete with Intel and Advanced Micro Devices in several markets.</p>
    </body></html>
    """
    entities = (
        RelatedEntity(
            "Taiwan Semiconductor Manufacturing Company",
            "TSM",
            ("TSMC", "Taiwan Semiconductor Manufacturing"),
            "Taiwan",
        ),
        RelatedEntity("Intel Corporation", "INTC", ("Intel",), "United States"),
    )

    result = extract_named_relationships(
        payload,
        subject_ticker="NVDA",
        subject_name="NVIDIA Corporation",
        entities=entities,
    )

    assert len(result) == 1
    assert result[0]["related_ticker"] == "TSM"
    assert result[0]["relationship_type"] == "foundry"
    assert result[0]["dependency_level"] == "sole_source"
    assert "TSMC" in result[0]["source_excerpt"]


def test_extract_disclosed_roles_keeps_identity_gap_explicit() -> None:
    text = (
        "For certain key types of equipment, including photolithography tools, "
        "we are sometimes dependent on a single supplier. "
        "Our devices are primarily manufactured by third-party contract manufacturers."
    )

    candidates = extract_disclosed_role_relationships(text)

    assert [item["relationship_type"] for item in candidates] == [
        "equipment",
        "contract_manufacturer",
    ]
    assert all(item["related_ticker"] is None for item in candidates)
    assert all(item["related_company_name"].startswith("Undisclosed") for item in candidates)
    assert candidates[0]["dependency_level"] == "sole_source"


def test_extract_disclosed_roles_does_not_infer_generic_supplier_language() -> None:
    assert extract_disclosed_role_relationships(
        "We work with many suppliers around the world and monitor business continuity."
    ) == []


def test_discovery_archives_latest_filing_and_stores_candidates(tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    source_url = "https://www.sec.gov/Archives/edgar/data/1/filing.htm"
    payload = b"""
    <html><body><p>We rely on TSMC for wafer fabrication of our advanced
    processors.</p></body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == source_url
        return httpx.Response(200, content=payload, request=request)

    with Session(engine) as session:
        session.add(
            CompanyProfile(
                ticker="NVDA",
                cik="0000000001",
                name="NVIDIA Corporation",
                sector="Technology",
                industry="Semiconductors",
                source_url="https://www.sec.gov/edgar/browse/?CIK=1",
            )
        )
        session.add(
            CompanyFiling(
                accession_number="0000000001-26-000001",
                ticker="NVDA",
                form="20-F",
                filed_at=date(2026, 2, 20),
                report_date=date(2026, 1, 31),
                primary_document="filing.htm",
                source_url=source_url,
            )
        )
        session.commit()
        archive = ColdArchive(tmp_path, min_free_bytes=0, max_used_percent=99)

        async def run() -> object:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                return await discover_sec_supply_chain_candidates(
                    session,
                    client=client,
                    archive=archive,
                    batch_size=5,
                    request_interval_seconds=0,
                )

        result = asyncio.run(run())
        state = session.get(CompanySupplyChainCoverage, "NVDA")

        assert result.filings_completed == 1
        assert result.candidates_upserted == 1
        assert state is not None
        assert state.status == "needs_review"
        assert state.candidate_edges == 1
        assert state.latest_filing_accession == "0000000001-26-000001"
        assert state.last_parser_version == SUPPLY_CHAIN_PARSER_VERSION
        assert state.latest_raw_archive_path is not None
        assert (tmp_path / state.latest_raw_archive_path).read_bytes() == payload

    engine.dispose()
