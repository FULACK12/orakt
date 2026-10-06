"""SEC Form 13F archive extraction and quarter-comparison tests."""

from datetime import date
from zipfile import ZipFile

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.companies import COMPANY_CATALOG, seed_company_catalog
from app.db.base import Base
from app.db.models import CompanyInstitutionalHolding
from app.institutional_history import (
    REVIEWED_CUSIPS,
    _known_sec_13f_archive_urls,
    _materialize_archive,
    build_institutional_evidence,
)


def test_reviewed_13f_universe_covers_company_catalog_without_name_guessing() -> None:
    assert set(REVIEWED_CUSIPS.values()) == {ticker for ticker, *_ in COMPANY_CATALOG}
    assert REVIEWED_CUSIPS["G54950103"] == "LIN"
    assert REVIEWED_CUSIPS["550021109"] == "LULU"
    assert "53566V106" not in REVIEWED_CUSIPS


def test_13f_official_name_fallback_spans_source_boundary() -> None:
    urls = _known_sec_13f_archive_urls(as_of=date(2026, 8, 2))

    assert len(urls) == 53
    assert urls[0].endswith("01mar2026-31may2026_form13f.zip")
    assert urls[-1].endswith("2013q2_form13f.zip")


def test_13f_archive_extracts_reviewed_issuers_and_calculates_reported_change(
    tmp_path,
) -> None:
    archive_path = tmp_path / "form13f.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "SUBMISSION.tsv",
            "ACCESSION_NUMBER\tFILING_DATE\tCIK\tPERIODOFREPORT\n"
            "0001-26-000001\t15-MAY-2026\t1001\t31-MAR-2026\n"
            "0001-25-000001\t14-FEB-2026\t1001\t31-DEC-2025\n"
            "0002-26-000001\t15-MAY-2026\t1002\t31-MAR-2026\n",
        )
        archive.writestr(
            "COVERPAGE.tsv",
            "ACCESSION_NUMBER\tFILINGMANAGER_NAME\n"
            "0001-26-000001\tExample Index Manager\n"
            "0001-25-000001\tExample Index Manager\n"
            "0002-26-000001\tOther Manager\n",
        )
        archive.writestr(
            "INFOTABLE.tsv",
            "ACCESSION_NUMBER\tINFOTABLE_SK\tNAMEOFISSUER\tTITLEOFCLASS\t"
            "CUSIP\tVALUE\tSSHPRNAMT\tSSHPRNAMTTYPE\tPUTCALL\t"
            "INVESTMENTDISCRETION\n"
            "0001-26-000001\t1\tMICRON TECHNOLOGY INC\tCOM\t595112103\t"
            "1500\t120\tSH\t\tSOLE\n"
            "0001-25-000001\t1\tMICRON TECHNOLOGY INC\tCOM\t595112103\t"
            "900\t100\tSH\t\tSOLE\n"
            "0002-26-000001\t1\tMICRON TECHNOLOGY INC\tCOM\t595112103\t"
            "500\t40\tSH\t\tSOLE\n"
            "0001-26-000001\t2\tAPPLE INC\tCOM\t037833100\t"
            "2500\t10\tSH\t\tSOLE\n"
            "0001-25-000001\t2\tAPPLE INC\tCOM\t037833100\t"
            "1800\t8\tSH\t\tSOLE\n"
            "0002-26-000001\t2\tOTHER ISSUER\tCOM\t000000000\t500\t40\t"
            "SH\t\tSOLE\n",
        )

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_company_catalog(session)
        session.commit()
        rows_seen, retained = _materialize_archive(session, archive_path)
        evidence = build_institutional_evidence(session, ticker="MU")
        apple_evidence = build_institutional_evidence(session, ticker="AAPL")
        count = session.scalar(select(func.count()).select_from(CompanyInstitutionalHolding))

    assert rows_seen == 6
    assert retained == 5
    assert count == 5
    example = next(item for item in evidence if item["manager_name"] == "Example Index Manager")
    assert example["report_period"] == date(2026, 3, 31).isoformat()
    assert example["reported_share_change"] == 20
    assert "cost basis" in " ".join(example["limitations"])
    assert apple_evidence[0]["ticker"] == "AAPL"
    assert apple_evidence[0]["reported_share_change"] == 2
    engine.dispose()
