"""Archive official CNINFO A-share disclosures and retain evidence excerpts."""

# ruff: noqa: RUF001

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors.rss import document_hash
from app.db.enums import SourceType
from app.db.models import (
    ChinaDisclosureSyncState,
    Document,
    MarketSeries,
    Source,
)
from app.disclosure_evidence import (
    STRUCTURED_DISCLOSURE_EVIDENCE_VERSION,
    extract_structured_disclosure_evidence,
)
from app.storage.archive import ArchiveReadError, ColdArchive

CNINFO_BASE_URL = "https://www.cninfo.com.cn"
CNINFO_PDF_BASE_URL = "https://static.cninfo.com.cn/"
CNINFO_SOURCE_NAME = "CNINFO statutory A-share disclosures"
CNINFO_PERIODIC_CATEGORIES = (
    "category_ndbg_szsh;category_bndbg_szsh;category_yjdbg_szsh;category_sjdbg_szsh"
)
PERIODIC_PATTERN = re.compile(
    r"(?:年度报告|半年度报告|第一季度报告|一季度报告|第三季度报告|三季度报告)"
)
SHAREHOLDER_PATTERN = re.compile(r"(?:股东|持股|增持|减持|回购|质押|权益变动|限售|解禁|高管持股)")
OPERATING_PATTERN = re.compile(r"(?:合同|订单|中标|产销|经营情况|业绩预告|业绩快报|投资者关系活动)")
SUPPLY_CHAIN_PATTERN = re.compile(
    r"(?:供应商|客户|采购|原材料|产能|生产基地|工厂|产业链|供应链|物流|电力)"
)


@dataclass(frozen=True)
class AShareLeader:
    ticker: str
    company_name: str


@dataclass(frozen=True)
class CNInfoAnnouncement:
    announcement_id: str
    ticker: str
    company_name: str
    org_id: str
    title: str
    published_at: datetime
    adjunct_url: str
    page_column: str

    @property
    def source_url(self) -> str:
        return f"{CNINFO_PDF_BASE_URL}{self.adjunct_url.lstrip('/')}"


class AShareDisclosureSyncResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    companies_selected: int = Field(ge=0)
    companies_completed: int = Field(ge=0)
    announcements_seen: int = Field(ge=0)
    documents_upserted: int = Field(ge=0)
    documents_existing: int = Field(ge=0)
    documents_archived: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)


class AShareDisclosureEnrichmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documents_scanned: int = Field(ge=0)
    documents_enriched: int = Field(ge=0)
    archive_fallbacks: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)


def backfill_structured_disclosure_evidence(
    session: Session,
    *,
    archive: ColdArchive,
    limit: int = 50,
) -> AShareDisclosureEnrichmentResult:
    """Enrich retained CNINFO documents in restart-safe, bounded batches."""
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between one and five hundred")
    source_id = session.scalar(select(Source.id).where(Source.name == CNINFO_SOURCE_NAME))
    if source_id is None:
        return AShareDisclosureEnrichmentResult(
            documents_scanned=0,
            documents_enriched=0,
            archive_fallbacks=0,
        )
    rows = list(
        session.scalars(
            select(Document)
            .where(Document.source_id == source_id)
            .order_by(Document.id)
        )
    )
    pending: list[Document] = []
    for document in rows:
        metadata = document.raw_metadata if isinstance(document.raw_metadata, dict) else {}
        if metadata.get("structured_evidence_version") != (
            STRUCTURED_DISCLOSURE_EVIDENCE_VERSION
        ):
            pending.append(document)
        if len(pending) >= limit:
            break

    enriched = 0
    archive_fallbacks = 0
    errors: list[str] = []
    for document in pending:
        full_text = document.body or ""
        if document.raw_object_path:
            try:
                payload = archive.load_entry(
                    document.raw_object_path,
                    expected_content_hash=document.content_hash,
                )
                full_text = str(payload.get("body") or full_text)
            except ArchiveReadError as exc:
                archive_fallbacks += 1
                errors.append(f"document:{document.id}: {str(exc)[:160]}")
        metadata = dict(document.raw_metadata or {})
        metadata["structured_evidence_version"] = STRUCTURED_DISCLOSURE_EVIDENCE_VERSION
        metadata["structured_evidence"] = extract_structured_disclosure_evidence(
            full_text,
            title=document.title,
            published_at=document.published_at,
        )
        document.raw_metadata = metadata
        enriched += 1
    session.commit()
    return AShareDisclosureEnrichmentResult(
        documents_scanned=len(pending),
        documents_enriched=enriched,
        archive_fallbacks=archive_fallbacks,
        errors=errors[:20],
    )


async def sync_a_share_disclosures(
    session: Session,
    *,
    client: httpx.AsyncClient,
    archive: ColdArchive,
    start_date: date,
    end_date: date,
    batch_size: int = 2,
    tickers: set[str] | None = None,
    force: bool = False,
    max_documents_per_company: int = 14,
    request_interval_seconds: float = 0.45,
) -> AShareDisclosureSyncResult:
    """Synchronize one restart-safe batch of current CSI 800 proxy leaders."""
    if not 1 <= batch_size <= 20:
        raise ValueError("batch_size must be between one and twenty")
    if start_date > end_date:
        raise ValueError("start_date must not be after end_date")
    selected_tickers = {item.strip().upper() for item in (tickers or set()) if item.strip()}
    source = _get_or_create_source(session)
    leaders = _active_a_share_leaders(session, selected_tickers)
    pending: list[AShareLeader] = []
    for leader in leaders:
        state = session.get(ChinaDisclosureSyncState, leader.ticker)
        covered = bool(
            state is not None
            and state.status in {"completed", "partial"}
            and state.period_start is not None
            and state.period_start <= start_date
            and state.period_end is not None
            and state.period_end >= end_date
        )
        if force or not covered:
            pending.append(leader)

    def pending_key(item: AShareLeader) -> tuple[datetime, str]:
        state = session.get(ChinaDisclosureSyncState, item.ticker)
        last_attempt = (
            (state.last_success_at or state.last_started_at) if state is not None else None
        )
        return (last_attempt or datetime.min.replace(tzinfo=UTC), item.ticker)

    pending.sort(key=pending_key)
    selected = pending[:batch_size]
    errors: list[str] = []
    totals = {
        "completed": 0,
        "seen": 0,
        "upserted": 0,
        "existing": 0,
        "archived": 0,
    }
    for company_index, leader in enumerate(selected):
        if company_index and request_interval_seconds:
            await asyncio.sleep(request_interval_seconds)
        state = _get_or_create_state(session, leader)
        state.status = "discovering"
        state.last_started_at = datetime.now(UTC)
        state.last_error = None
        session.commit()
        company_errors: list[str] = []
        try:
            org_id = await _resolve_org_id(client, leader.ticker)
            state = session.get(ChinaDisclosureSyncState, leader.ticker) or state
            state.org_id = org_id
            periodic = await _query_announcements(
                client,
                ticker=leader.ticker,
                org_id=org_id,
                start_date=start_date,
                end_date=end_date,
                category=CNINFO_PERIODIC_CATEGORIES,
                max_pages=2,
            )
            all_recent = await _query_announcements(
                client,
                ticker=leader.ticker,
                org_id=org_id,
                start_date=start_date,
                end_date=end_date,
                category="",
                max_pages=3,
            )
            announcements = _select_announcements(
                [*periodic, *all_recent],
                limit=max_documents_per_company,
            )
            totals["seen"] += len({item.announcement_id for item in [*periodic, *all_recent]})
            kind_counts = {
                "periodic_report": 0,
                "shareholder": 0,
                "operating": 0,
                "supply_chain": 0,
            }
            archived_for_company = 0
            upserted_for_company = 0
            existing_for_company = 0
            for announcement in announcements:
                try:
                    outcome, kinds = await _retain_announcement(
                        session,
                        client=client,
                        archive=archive,
                        source=source,
                        announcement=announcement,
                    )
                except (httpx.HTTPError, OSError, TypeError, ValueError) as exc:
                    company_errors.append(
                        f"{announcement.announcement_id}: {type(exc).__name__}: {str(exc)[:160]}"
                    )
                    continue
                if outcome == "created":
                    upserted_for_company += 1
                    archived_for_company += 1
                else:
                    existing_for_company += 1
                for kind in kinds:
                    if kind in kind_counts:
                        kind_counts[kind] += 1
                if request_interval_seconds:
                    await asyncio.sleep(request_interval_seconds)
            state = session.get(ChinaDisclosureSyncState, leader.ticker) or state
            state.period_start = start_date
            state.period_end = end_date
            state.announcements_seen = len(
                {item.announcement_id for item in [*periodic, *all_recent]}
            )
            state.documents_upserted += upserted_for_company
            state.documents_archived += archived_for_company
            state.periodic_reports = kind_counts["periodic_report"]
            state.shareholder_documents = kind_counts["shareholder"]
            state.operating_documents = kind_counts["operating"]
            state.supply_chain_documents = kind_counts["supply_chain"]
            state.status = "completed" if kind_counts["periodic_report"] else "partial"
            state.last_success_at = datetime.now(UTC)
            state.last_error = "; ".join(company_errors[:6]) or None
            session.commit()
            totals["completed"] += 1
            totals["upserted"] += upserted_for_company
            totals["existing"] += existing_for_company
            totals["archived"] += archived_for_company
            errors.extend(f"{leader.ticker}: {item}" for item in company_errors)
        except (httpx.HTTPError, OSError, TypeError, ValueError) as exc:
            session.rollback()
            state = session.get(ChinaDisclosureSyncState, leader.ticker) or state
            state.status = "failed"
            state.last_error = f"{type(exc).__name__}: {str(exc)[:1_800]}"
            session.commit()
            errors.append(f"{leader.ticker}: {state.last_error}")
    return AShareDisclosureSyncResult(
        companies_selected=len(selected),
        companies_completed=totals["completed"],
        announcements_seen=totals["seen"],
        documents_upserted=totals["upserted"],
        documents_existing=totals["existing"],
        documents_archived=totals["archived"],
        errors=errors,
    )


def _active_a_share_leaders(
    session: Session,
    selected_tickers: set[str],
) -> list[AShareLeader]:
    series = list(
        session.scalars(
            select(MarketSeries)
            .where(
                MarketSeries.category == "equity_price",
                MarketSeries.region == "china",
                MarketSeries.listing_status == "active",
                MarketSeries.series_id.like("CN:%"),
            )
            .order_by(MarketSeries.series_id)
        )
    )
    leaders: list[AShareLeader] = []
    for item in series:
        ticker = item.series_id.split(":", 1)[1]
        if selected_tickers and ticker not in selected_tickers:
            continue
        marker = f" ({ticker})"
        name = item.name.split(marker, 1)[0].strip()
        leaders.append(AShareLeader(ticker=ticker, company_name=name))
    return leaders


def _get_or_create_source(session: Session) -> Source:
    source = session.scalar(
        select(Source).where(
            Source.name == CNINFO_SOURCE_NAME,
            Source.country == "CN",
        )
    )
    if source is not None:
        return source
    source = Source(
        name=CNINFO_SOURCE_NAME,
        country="CN",
        language="zh",
        source_type=SourceType.OFFICIAL,
        ownership="Shenzhen Securities Information Co., Ltd. / SZSE",
        credibility_baseline=Decimal("0.970"),
        political_bias_metadata={
            "kind": "statutory_exchange_disclosure_platform",
            "platform": "CNINFO",
            "homepage": CNINFO_BASE_URL,
            "full_text_archive": True,
            "point_in_time_publication_timestamp": True,
        },
    )
    session.add(source)
    session.flush()
    return source


def _get_or_create_state(
    session: Session,
    leader: AShareLeader,
) -> ChinaDisclosureSyncState:
    state = session.get(ChinaDisclosureSyncState, leader.ticker)
    if state is None:
        state = ChinaDisclosureSyncState(
            ticker=leader.ticker,
            company_name=leader.company_name,
            status="pending",
            announcements_seen=0,
            documents_upserted=0,
            documents_archived=0,
            periodic_reports=0,
            shareholder_documents=0,
            operating_documents=0,
            supply_chain_documents=0,
        )
        session.add(state)
        session.flush()
    else:
        state.company_name = leader.company_name
    return state


async def _resolve_org_id(client: httpx.AsyncClient, ticker: str) -> str:
    response = await client.post(
        "/new/information/topSearch/query",
        data={"keyWord": ticker, "maxSecNum": "10"},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise TypeError("CNINFO company search did not return a list")
    for item in payload:
        if isinstance(item, dict) and str(item.get("code")) == ticker:
            org_id = str(item.get("orgId") or "").strip()
            if org_id:
                return org_id
    raise ValueError(f"CNINFO orgId was not resolved for {ticker}")


async def _query_announcements(
    client: httpx.AsyncClient,
    *,
    ticker: str,
    org_id: str,
    start_date: date,
    end_date: date,
    category: str,
    max_pages: int,
) -> list[CNInfoAnnouncement]:
    is_shanghai = ticker.startswith(("6", "68"))
    result: list[CNInfoAnnouncement] = []
    for page_number in range(1, max_pages + 1):
        response = await client.post(
            "/new/hisAnnouncement/query",
            data={
                "pageNum": str(page_number),
                "pageSize": "30",
                "column": "sse" if is_shanghai else "szse",
                "tabName": "fulltext",
                "plate": "sh" if is_shanghai else "sz",
                "stock": f"{ticker},{org_id}",
                "searchkey": "",
                "secid": "",
                "category": category,
                "trade": "",
                "seDate": f"{start_date.isoformat()}~{end_date.isoformat()}",
                "sortName": "",
                "sortType": "",
                "isHLtitle": "true",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise TypeError("CNINFO announcement query did not return an object")
        announcements = payload.get("announcements") or []
        if not isinstance(announcements, list):
            raise TypeError("CNINFO announcements must be a list")
        result.extend(
            parsed
            for item in announcements
            if isinstance(item, dict) and (parsed := _announcement(item)) is not None
        )
        if not payload.get("hasMore"):
            break
    return result


def _announcement(raw: dict[str, Any]) -> CNInfoAnnouncement | None:
    announcement_id = str(raw.get("announcementId") or "").strip()
    adjunct_url = str(raw.get("adjunctUrl") or "").strip()
    timestamp = raw.get("announcementTime")
    if not announcement_id or not adjunct_url or not isinstance(timestamp, (int, float)):
        return None
    title = re.sub(r"<[^>]+>", "", str(raw.get("announcementTitle") or ""))
    title = re.sub(r"\s+", " ", title).strip()
    if not title:
        return None
    return CNInfoAnnouncement(
        announcement_id=announcement_id,
        ticker=str(raw.get("secCode") or "").strip(),
        company_name=str(raw.get("secName") or "").strip(),
        org_id=str(raw.get("orgId") or "").strip(),
        title=title,
        published_at=datetime.fromtimestamp(float(timestamp) / 1_000, tz=UTC),
        adjunct_url=adjunct_url,
        page_column=str(raw.get("pageColumn") or "").strip(),
    )


def _title_kinds(title: str) -> set[str]:
    kinds: set[str] = set()
    if PERIODIC_PATTERN.search(title) and "摘要" not in title:
        kinds.add("periodic_report")
    if SHAREHOLDER_PATTERN.search(title):
        kinds.add("shareholder")
    if OPERATING_PATTERN.search(title):
        kinds.add("operating")
    if SUPPLY_CHAIN_PATTERN.search(title):
        kinds.add("supply_chain")
    return kinds


def _select_announcements(
    announcements: list[CNInfoAnnouncement],
    *,
    limit: int,
) -> list[CNInfoAnnouncement]:
    unique = {
        item.announcement_id: item
        for item in sorted(
            announcements,
            key=lambda row: row.published_at,
            reverse=True,
        )
    }
    quotas = {
        "periodic_report": 6,
        "shareholder": 3,
        "operating": 3,
        "supply_chain": 3,
    }
    selected: dict[str, CNInfoAnnouncement] = {}
    for kind, quota in quotas.items():
        matches = [item for item in unique.values() if kind in _title_kinds(item.title)]
        for item in matches[:quota]:
            selected[item.announcement_id] = item
    return sorted(selected.values(), key=lambda row: row.published_at, reverse=True)[:limit]


async def _retain_announcement(
    session: Session,
    *,
    client: httpx.AsyncClient,
    archive: ColdArchive,
    source: Source,
    announcement: CNInfoAnnouncement,
) -> tuple[str, set[str]]:
    existing = session.scalar(select(Document).where(Document.url == announcement.source_url))
    if existing is not None:
        metadata = existing.raw_metadata if isinstance(existing.raw_metadata, dict) else {}
        kinds = set(metadata.get("evidence_kinds") or _title_kinds(existing.title))
        return "existing", kinds
    response = await client.get(announcement.source_url)
    response.raise_for_status()
    payload = response.content
    if not payload.startswith(b"%PDF"):
        raise ValueError("CNINFO attachment is not a PDF")
    pdf_archive_path = archive.store_bytes(
        (
            f"raw/cninfo/{announcement.ticker}/"
            f"{announcement.published_at:%Y}/"
            f"{announcement.announcement_id}.pdf"
        ),
        payload,
    )
    # PDF font maps occasionally decode embedded padding as U+0000. PostgreSQL
    # text/jsonb cannot represent NUL, so clean at the persistence boundary even
    # when a different extractor is injected or introduced later.
    full_text = _postgres_text(await asyncio.to_thread(_extract_pdf_text, payload))
    kinds = _title_kinds(announcement.title) | _content_kinds(full_text)
    body = _hot_evidence_text(
        full_text,
        ticker=announcement.ticker,
        company_name=announcement.company_name,
    )
    digest = document_hash(announcement.title, full_text or announcement.source_url)
    conflicting = session.scalar(select(Document).where(Document.content_hash == digest))
    if conflicting is not None:
        digest = document_hash(
            announcement.title,
            f"{full_text}\nsource-url:{announcement.source_url}",
        )
    metadata = {
        "content_collector": "cninfo_disclosure",
        "announcement_id": announcement.announcement_id,
        "ticker": announcement.ticker,
        "company_name": announcement.company_name,
        "org_id": announcement.org_id,
        "page_column": announcement.page_column,
        "evidence_kinds": sorted(kinds),
        "pdf_archive_path": pdf_archive_path,
        "full_text_characters": len(full_text),
        "hot_excerpt_characters": len(body),
        "metadata_only": not bool(full_text),
        "evidence_tier": "official_fulltext" if len(full_text) >= 1_200 else "official_pdf",
        "structured_evidence_version": STRUCTURED_DISCLOSURE_EVIDENCE_VERSION,
        "structured_evidence": extract_structured_disclosure_evidence(
            full_text,
            title=announcement.title,
            published_at=announcement.published_at,
        ),
    }
    raw_object_path = archive.store_entry(
        content_hash=digest,
        source_id=source.id,
        url=announcement.source_url,
        title=announcement.title,
        body=full_text,
        published_at=announcement.published_at,
        metadata=metadata,
    )
    document_title = _postgres_text(
        f"{announcement.company_name}（{announcement.ticker}）· {announcement.title}"
    )
    session.add(
        Document(
            source_id=source.id,
            url=announcement.source_url,
            title=document_title,
            body=body or None,
            language="zh",
            published_at=announcement.published_at,
            fetched_at=datetime.now(UTC),
            content_hash=digest,
            credibility_score=source.credibility_baseline,
            raw_object_path=raw_object_path,
            raw_metadata=metadata,
        )
    )
    session.flush()
    return "created", kinds


def _extract_pdf_text(payload: bytes) -> str:
    reader = PdfReader(BytesIO(payload), strict=False)
    pages: list[str] = []
    for page in reader.pages[:600]:
        try:
            text = page.extract_text() or ""
        except (KeyError, TypeError, ValueError):
            text = ""
        if text:
            pages.append(text)
    return _postgres_text(re.sub(r"[ \t]+", " ", "\n".join(pages)).strip())


def _postgres_text(value: str) -> str:
    """Remove characters PostgreSQL text/jsonb cannot store safely."""
    return value.replace("\x00", "")


def _content_kinds(text: str) -> set[str]:
    sample = text[:1_500_000]
    kinds: set[str] = set()
    if SHAREHOLDER_PATTERN.search(sample):
        kinds.add("shareholder")
    if OPERATING_PATTERN.search(sample):
        kinds.add("operating")
    if SUPPLY_CHAIN_PATTERN.search(sample):
        kinds.add("supply_chain")
    return kinds


def _hot_evidence_text(
    full_text: str,
    *,
    ticker: str,
    company_name: str,
    limit: int = 48_000,
) -> str:
    if not full_text:
        return f"{company_name}（{ticker}）官方公告 PDF；当前未提取到可检索文本。"
    segments = [full_text[:8_000]]
    keywords = (
        "营业收入",
        "净利润",
        "经营活动产生的现金流量净额",
        "前十名股东",
        "股东持股",
        "主要客户",
        "主要供应商",
        "原材料",
        "产能",
        "合同",
        "订单",
        "采购",
        "销售量",
    )
    for keyword in keywords:
        for match in list(re.finditer(re.escape(keyword), full_text))[:4]:
            start = max(0, match.start() - 500)
            end = min(len(full_text), match.end() + 1_500)
            segments.append(full_text[start:end])
    result = "\n\n--- evidence excerpt ---\n".join(segments)
    return result[:limit]
