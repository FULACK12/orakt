"""SEC Form 4 ownership XML archive and parser tests."""

from __future__ import annotations

import asyncio
from datetime import date

import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    CompanyFiling,
    CompanyInsiderFilingState,
    CompanyInsiderTransaction,
    CompanyProfile,
)
from app.insider_history import (
    FORM4_PARSER_VERSION,
    NonTargetIssuerError,
    build_insider_evidence,
    insider_coverage,
    parse_form4_xml,
    sync_sec_form4_filings,
)
from app.storage.archive import ColdArchive

FORM4_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<ownershipDocument>
  <documentType>4</documentType>
  <periodOfReport>2026-08-25</periodOfReport>
  <aff10b5One>1</aff10b5One>
  <issuer>
    <issuerCik>0000320193</issuerCik>
    <issuerName>Apple Inc.</issuerName>
    <issuerTradingSymbol>AAPL</issuerTradingSymbol>
  </issuer>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerCik>0000000001</rptOwnerCik>
      <rptOwnerName>Example Officer</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>0</isDirector>
      <isOfficer>1</isOfficer>
      <isTenPercentOwner>0</isTenPercentOwner>
      <isOther>0</isOther>
      <officerTitle>Chief Test Officer</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2026-08-25</value></transactionDate>
      <transactionCoding>
        <transactionFormType>4</transactionFormType>
        <transactionCode>S</transactionCode>
        <equitySwapInvolved>0</equitySwapInvolved>
        <footnoteId id="F1"/>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>1439</value></transactionShares>
        <transactionPricePerShare><value>310.95</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts>
        <sharesOwnedFollowingTransaction><value>37229</value></sharesOwnedFollowingTransaction>
      </postTransactionAmounts>
      <ownershipNature>
        <directOrIndirectOwnership><value>D</value></directOrIndirectOwnership>
      </ownershipNature>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2026-08-25</value></transactionDate>
      <transactionCoding>
        <transactionFormType>4</transactionFormType>
        <transactionCode>M</transactionCode>
        <equitySwapInvolved>0</equitySwapInvolved>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>100</value></transactionShares>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts>
        <sharesOwnedFollowingTransaction><value>37329</value></sharesOwnedFollowingTransaction>
      </postTransactionAmounts>
      <ownershipNature>
        <directOrIndirectOwnership><value>D</value></directOrIndirectOwnership>
      </ownershipNature>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
  <derivativeTable>
    <derivativeTransaction>
      <securityTitle><value>Restricted Stock Unit</value></securityTitle>
      <conversionOrExercisePrice><value>0</value></conversionOrExercisePrice>
      <transactionDate><value>2026-08-25</value></transactionDate>
      <transactionCoding>
        <transactionFormType>4</transactionFormType>
        <transactionCode>M</transactionCode>
        <equitySwapInvolved>0</equitySwapInvolved>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>100</value></transactionShares>
        <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <exerciseDate><value>2026-08-25</value></exerciseDate>
      <expirationDate><value>2027-08-25</value></expirationDate>
      <underlyingSecurity>
        <underlyingSecurityTitle><value>Common Stock</value></underlyingSecurityTitle>
        <underlyingSecurityShares><value>100</value></underlyingSecurityShares>
      </underlyingSecurity>
      <postTransactionAmounts>
        <valueOwnedFollowingTransaction><value>0</value></valueOwnedFollowingTransaction>
      </postTransactionAmounts>
      <ownershipNature>
        <directOrIndirectOwnership><value>D</value></directOrIndirectOwnership>
      </ownershipNature>
    </derivativeTransaction>
  </derivativeTable>
  <footnotes>
    <footnote id="F1">Sale under a Rule 10b5-1 plan.</footnote>
  </footnotes>
  <remarks>Filed for test coverage.</remarks>
</ownershipDocument>
"""


def test_form4_xml_is_archived_parsed_and_exposed_as_bounded_evidence(tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.path.endswith("/000114036126034741/form4.xml")
        return httpx.Response(200, content=FORM4_XML)

    async def synchronize(session: Session, archive: ColdArchive) -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as client:
            first = await sync_sec_form4_filings(
                session,
                client=client,
                archive=archive,
                tickers={"AAPL"},
                batch_size=10,
                request_interval_seconds=0,
            )
            second = await sync_sec_form4_filings(
                session,
                client=client,
                archive=archive,
                tickers={"AAPL"},
                batch_size=10,
                request_interval_seconds=0,
            )
        assert first.filings_completed == 1
        assert first.transactions_upserted == 3
        assert second.filings_selected == 0

    archive = ColdArchive(
        tmp_path,
        min_free_bytes=0,
        max_used_percent=99,
        disk_usage_provider=lambda _: (100_000_000, 0, 100_000_000),
    )
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
            CompanyFiling(
                accession_number="0001140361-26-034741",
                ticker="AAPL",
                form="4",
                filed_at=date(2026, 8, 27),
                report_date=date(2026, 8, 25),
                primary_document="xslF345X06/form4.xml",
                source_url=(
                    "https://www.sec.gov/Archives/edgar/data/320193/"
                    "000114036126034741/xslF345X06/form4.xml"
                ),
            )
        )
        session.commit()
        asyncio.run(synchronize(session, archive))
        state = session.get(
            CompanyInsiderFilingState,
            "0001140361-26-034741",
        )
        evidence = build_insider_evidence(
            session,
            ticker="AAPL",
            as_of=date(2026, 8, 28),
        )
        coverage = insider_coverage(session, ticker="AAPL")
        count = session.scalar(
            select(func.count()).select_from(CompanyInsiderTransaction)
        )

    assert calls == 1
    assert count == 3
    assert state is not None
    assert state.status == "completed"
    assert state.parser_version == FORM4_PARSER_VERSION
    assert state.raw_sha256
    assert state.raw_archive_path
    assert (tmp_path / state.raw_archive_path).read_bytes() == FORM4_XML
    sale = next(item for item in evidence if item["transaction_code"] == "S")
    assert sale["transaction_classification"] == "open_market_sale"
    assert sale["shares"] == 1439
    assert sale["price_per_share"] == 310.95
    assert sale["shares_owned_following"] == 37229
    assert sale["is_10b5_1"] is True
    assert sale["reporting_owners"][0]["roles"] == ["officer"]
    assert "motive" in " ".join(sale["limitations"])
    exercise_legs = [item for item in evidence if item["transaction_code"] == "M"]
    assert len(exercise_legs) == 2
    assert {item["transaction_kind"] for item in exercise_legs} == {
        "derivative",
        "non_derivative",
    }
    assert all(item["paired_derivative_and_nonderivative_legs"] for item in exercise_legs)
    assert len({item["transaction_group_id"] for item in exercise_legs}) == 1
    assert all(item["related_leg_count"] == 3 for item in exercise_legs)
    assert all("do not sum" in item["interpretation_guardrail"] for item in exercise_legs)
    assert coverage["transaction_count"] == 3
    assert coverage["filings_completed"] == 1
    engine.dispose()


def test_non_xml_primary_document_is_bounded_and_does_not_abort_batch(tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/000114036126034741/form4.xml")
        return httpx.Response(200, content=FORM4_XML)

    archive = ColdArchive(
        tmp_path,
        min_free_bytes=0,
        max_used_percent=99,
        disk_usage_provider=lambda _: (100_000_000, 0, 100_000_000),
    )
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
                CompanyFiling(
                    accession_number="0001140361-26-034741",
                    ticker="AAPL",
                    form="4",
                    filed_at=date(2026, 8, 27),
                    report_date=date(2026, 8, 25),
                    primary_document="xslF345X06/form4.xml",
                    source_url=(
                        "https://www.sec.gov/Archives/edgar/data/320193/"
                        "000114036126034741/xslF345X06/form4.xml"
                    ),
                ),
                CompanyFiling(
                    accession_number="0000320193-02-000001",
                    ticker="AAPL",
                    form="4",
                    filed_at=date(2026, 8, 28),
                    report_date=date(2002, 1, 1),
                    primary_document="ownership.txt",
                    source_url=(
                        "https://www.sec.gov/Archives/edgar/data/320193/"
                        "000032019302000001/ownership.txt"
                    ),
                ),
            ]
        )
        session.commit()

        async def synchronize() -> list[object]:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
            ) as client:
                return [
                    await sync_sec_form4_filings(
                        session,
                        client=client,
                        archive=archive,
                        tickers={"AAPL"},
                        batch_size=10,
                        request_interval_seconds=0,
                    )
                    for _ in range(4)
                ]

        results = asyncio.run(synchronize())
        failed_state = session.get(
            CompanyInsiderFilingState,
            "0000320193-02-000001",
        )

    assert results[0].filings_completed == 1
    assert results[0].filings_failed == 1
    assert results[1].filings_failed == 1
    assert results[2].filings_failed == 1
    assert results[3].filings_selected == 0
    assert failed_state is not None
    assert failed_state.attempt_count == 3
    assert failed_state.source_url.endswith("ownership.txt")
    assert "no XML primary document" in (failed_state.last_error or "")
    engine.dispose()


def test_form4_accepts_equivalent_share_class_and_rejects_other_issuer() -> None:
    berkshire_xml = FORM4_XML.replace(
        b"<issuerTradingSymbol>AAPL</issuerTradingSymbol>",
        b"<issuerTradingSymbol>BRK.A</issuerTradingSymbol>",
    )
    rows = parse_form4_xml(
        berkshire_xml,
        ticker="BRK.B",
        accession_number="test-brk-share-class",
        form="4",
        filed_at=date(2026, 8, 28),
        source_url="https://www.sec.gov/test-brk.xml",
    )
    assert rows
    assert {row["ticker"] for row in rows} == {"BRK.B"}

    undotted_rows = parse_form4_xml(
        berkshire_xml.replace(
            b"<issuerTradingSymbol>BRK.A</issuerTradingSymbol>",
            b"<issuerTradingSymbol>BRKB</issuerTradingSymbol>",
        ),
        ticker="BRK.B",
        accession_number="test-brk-undotted-share-class",
        form="4",
        filed_at=date(2026, 8, 28),
        source_url="https://www.sec.gov/test-brk-undotted.xml",
    )
    assert undotted_rows

    other_issuer_xml = FORM4_XML.replace(
        b"<issuerTradingSymbol>AAPL</issuerTradingSymbol>",
        b"<issuerTradingSymbol>PML</issuerTradingSymbol>",
    )
    with pytest.raises(NonTargetIssuerError, match="PML != BAC"):
        parse_form4_xml(
            other_issuer_xml,
            ticker="BAC",
            accession_number="test-non-target-issuer",
            form="4",
            filed_at=date(2026, 8, 28),
            source_url="https://www.sec.gov/test-other.xml",
        )
