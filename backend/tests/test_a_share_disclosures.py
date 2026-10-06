"""CNINFO full-text disclosure collection tests."""

# ruff: noqa: RUF001

import asyncio
from datetime import date

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.a_share_disclosures as disclosures
from app.a_share_disclosures import (
    _select_announcements,
    _title_kinds,
    backfill_structured_disclosure_evidence,
    sync_a_share_disclosures,
)
from app.db.base import Base
from app.db.models import ChinaDisclosureSyncState, Document, MarketSeries
from app.disclosure_evidence import (
    STRUCTURED_DISCLOSURE_EVIDENCE_VERSION,
    extract_structured_disclosure_evidence,
    structured_evidence_counts,
)
from app.storage.archive import ColdArchive


def test_title_classification_and_quota_selection() -> None:
    assert _title_kinds("2026年半年度报告") == {"periodic_report"}
    assert "shareholder" in _title_kinds("关于控股股东增持股份的公告")
    assert "operating" in _title_kinds("重大合同中标公告")
    assert "supply_chain" in _title_kinds("原材料采购和供应链说明")
    assert _select_announcements([], limit=14) == []


def test_structured_disclosure_evidence_keeps_exact_candidates_auditable() -> None:
    extracted = extract_structured_disclosure_evidence(
        (
            "营业收入 12,345.67 万元 上年同期 10,000.00 万元\n"
            "经营活动产生的现金流量净额 -230.50 万元\n"
            "前十名股东持股情况：机构甲持股数量 1,200万股。\n"
            "主要供应商及原材料采购额为 88.6 万元，新增重大合同。"
        ),
        title="2026年第三季度报告",
    )
    counts = structured_evidence_counts(extracted)

    assert extracted["version"] == STRUCTURED_DISCLOSURE_EVIDENCE_VERSION
    assert extracted["period_type"] == "quarter_3"
    assert counts["financial_metrics"] >= 2
    assert counts["shareholder_excerpts"] >= 1
    assert counts["supply_chain_excerpts"] >= 1
    assert extracted["financial_metrics"][0]["extraction_status"].startswith("candidate_")
    assert "12,345.67" in str(extracted["financial_metrics"])


def test_sync_archives_pdf_full_text_and_hot_evidence(tmp_path, monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    timestamp = 1_787_673_600_000

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/new/information/topSearch/query"):
            return httpx.Response(
                200,
                json=[{"code": "300750", "orgId": "GD165627"}],
                request=request,
            )
        if path.endswith("/new/hisAnnouncement/query"):
            return httpx.Response(
                200,
                json={
                    "announcements": [
                        {
                            "announcementId": "1210000001",
                            "announcementTitle": "2026年半年度报告",
                            "announcementTime": timestamp,
                            "adjunctUrl": "finalpage/2026-08-26/1210000001.PDF",
                            "secCode": "300750",
                            "secName": "宁德时代",
                            "orgId": "GD165627",
                            "pageColumn": "创业板",
                        }
                    ],
                    "hasMore": False,
                },
                request=request,
            )
        if path.endswith("1210000001.PDF"):
            return httpx.Response(200, content=b"%PDF-1.7 test", request=request)
        return httpx.Response(404, request=request)

    monkeypatch.setattr(
        disclosures,
        "_extract_pdf_text",
        lambda _: (
            "宁德时代2026年半年度报告。营业收入、净利润、经营活动产生的现金流量净额。"
            "前十名股东持股情况，主要供应商、原材料采购、产能和重大合同。\x00" * 40
        ),
    )
    with Session(engine) as session:
        session.add(
            MarketSeries(
                series_id="CN:300750",
                name="宁德时代 (300750)",
                category="equity_price",
                unit="CNY",
                frequency="daily",
                source_name="BaoStock",
                source_url="http://baostock.com/baostock/index.php/",
                region="china",
                listing_status="active",
            )
        )
        session.commit()

        async def run() -> object:
            async with httpx.AsyncClient(
                base_url="https://www.cninfo.com.cn",
                transport=httpx.MockTransport(handler),
            ) as client:
                return await sync_a_share_disclosures(
                    session,
                    client=client,
                    archive=ColdArchive(tmp_path, min_free_bytes=0, max_used_percent=99),
                    start_date=date(2024, 1, 1),
                    end_date=date(2026, 9, 8),
                    batch_size=1,
                    request_interval_seconds=0,
                )

        result = asyncio.run(run())
        state = session.get(ChinaDisclosureSyncState, "300750")
        document = session.scalar(select(Document))
        assert result.companies_completed == 1
        assert result.documents_upserted == 1
        assert state is not None and state.status == "completed"
        assert state.periodic_reports == 1
        assert state.shareholder_documents == 1
        assert state.supply_chain_documents == 1
        assert document is not None and document.raw_object_path is not None
        assert "营业收入" in (document.body or "")
        assert "\x00" not in (document.body or "")
        assert (tmp_path / document.raw_object_path).is_file()
        assert (tmp_path / document.raw_metadata["pdf_archive_path"]).is_file()
        assert document.raw_metadata["structured_evidence_version"] == (
            STRUCTURED_DISCLOSURE_EVIDENCE_VERSION
        )
        assert document.raw_metadata["structured_evidence"]["financial_metrics"]

        metadata = dict(document.raw_metadata)
        metadata.pop("structured_evidence_version")
        metadata.pop("structured_evidence")
        document.raw_metadata = metadata
        session.commit()
        enrichment = backfill_structured_disclosure_evidence(
            session,
            archive=ColdArchive(tmp_path, min_free_bytes=0, max_used_percent=99),
            limit=10,
        )
        session.refresh(document)
        assert enrichment.documents_enriched == 1
        assert document.raw_metadata["structured_evidence"]["supply_chain_excerpts"]

    engine.dispose()
