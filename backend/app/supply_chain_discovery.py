"""Archive issuer annual filings and discover quoted, reviewable company relationships."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.db.models import (
    CompanyFiling,
    CompanyProfile,
    CompanySupplyChainCoverage,
    CompanySupplyChainEdge,
)
from app.storage.archive import ColdArchive
from app.supply_chain import ensure_supply_chain_coverage, refresh_supply_chain_coverage

SUPPLY_CHAIN_PARSER_VERSION = "sec_relationship_v3_named_and_disclosed_roles"
ANNUAL_SUPPLY_CHAIN_FORMS = ("10-K", "10-K/A", "20-F", "20-F/A")
MAX_FILING_BYTES = 40_000_000


@dataclass(frozen=True)
class RelatedEntity:
    name: str
    ticker: str | None
    aliases: tuple[str, ...]
    geography: str | None = None


KNOWN_RELATED_ENTITIES = (
    RelatedEntity(
        "Taiwan Semiconductor Manufacturing Company",
        "TSM",
        ("TSMC", "Taiwan Semiconductor Manufacturing"),
        "Taiwan",
    ),
    RelatedEntity("ASML Holding N.V.", "ASML", ("ASML", "ASML Holding"), "Netherlands"),
    RelatedEntity("Samsung Electronics", None, ("Samsung Electronics",), "South Korea"),
    RelatedEntity("SK hynix", None, ("SK hynix", "SK Hynix"), "South Korea"),
    RelatedEntity("Hon Hai Precision Industry", None, ("Foxconn", "Hon Hai Precision"), "Taiwan"),
    RelatedEntity("Pegatron Corporation", None, ("Pegatron",), "Taiwan"),
    RelatedEntity("Quanta Computer", None, ("Quanta Computer",), "Taiwan"),
    RelatedEntity("Wistron Corporation", None, ("Wistron",), "Taiwan"),
    RelatedEntity("Compal Electronics", None, ("Compal Electronics",), "Taiwan"),
    RelatedEntity(
        "Corning Incorporated", "GLW", ("Corning Incorporated", "Corning"), "United States"
    ),
    RelatedEntity("GlobalFoundries", "GFS", ("GlobalFoundries",), "United States"),
    RelatedEntity(
        "United Microelectronics Corporation", "UMC", ("United Microelectronics", "UMC"), "Taiwan"
    ),
    RelatedEntity("Amkor Technology", "AMKR", ("Amkor Technology", "Amkor"), "United States"),
    RelatedEntity(
        "ASE Technology Holding",
        "ASX",
        ("ASE Technology", "Advanced Semiconductor Engineering"),
        "Taiwan",
    ),
    RelatedEntity("Arm Holdings", "ARM", ("Arm Holdings", "Arm Limited"), "United Kingdom"),
    RelatedEntity("Cadence Design Systems", "CDNS", ("Cadence Design Systems",), "United States"),
    RelatedEntity("Synopsys", "SNPS", ("Synopsys",), "United States"),
    RelatedEntity("Amazon Web Services", "AMZN", ("Amazon Web Services", "AWS"), "United States"),
    RelatedEntity("Microsoft Azure", "MSFT", ("Microsoft Azure", "Azure"), "United States"),
    RelatedEntity(
        "Google Cloud", "GOOGL", ("Google Cloud Platform", "Google Cloud"), "United States"
    ),
    RelatedEntity(
        "Oracle Cloud", "ORCL", ("Oracle Cloud Infrastructure", "Oracle Cloud"), "United States"
    ),
)

RELATION_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "customer",
        re.compile(
            r"\b(customer|customers|customer concentration|revenue (?:from|with)|sell\w* to)\b",
            re.I,
        ),
        "named customer or revenue concentration disclosed in filing",
    ),
    (
        "foundry",
        re.compile(r"\b(foundr(?:y|ies)|wafer fabrication|fabricat(?:e|es|ed|ion))\b", re.I),
        "semiconductor wafer fabrication disclosed in filing",
    ),
    (
        "contract_manufacturer",
        re.compile(
            r"\b(contract manufactur|manufacturing partner|assembly partner|"
            r"assemble\w* (?:our|for us))\b",
            re.I,
        ),
        "contract manufacturing or assembly disclosed in filing",
    ),
    (
        "equipment",
        re.compile(
            r"\b(equipment supplier|manufacturing equipment|production equipment|lithography)\b",
            re.I,
        ),
        "manufacturing equipment disclosed in filing",
    ),
    (
        "materials",
        re.compile(
            r"\b(raw material|materials supplier|substrate|silicon wafer|rare earth|"
            r"battery material)\b",
            re.I,
        ),
        "production material or component disclosed in filing",
    ),
    (
        "logistics",
        re.compile(
            r"\b(logistics provider|freight|shipping provider|air cargo|ocean carrier)\b", re.I
        ),
        "logistics or freight service disclosed in filing",
    ),
    (
        "energy",
        re.compile(
            r"\b(power supplier|electricity supplier|energy provider|utility provider)\b", re.I
        ),
        "energy or electricity dependency disclosed in filing",
    ),
    (
        "cloud",
        re.compile(
            r"\b(cloud provider|cloud infrastructure|hosting provider|data center provider)\b", re.I
        ),
        "cloud or hosting dependency disclosed in filing",
    ),
    (
        "distributor",
        re.compile(r"\b(distributor|distribution partner|reseller)\b", re.I),
        "distribution relationship disclosed in filing",
    ),
    (
        "supplier",
        re.compile(
            r"\b(supplier|vendor|source\w* from|procure\w* from|purchase\w* from|"
            r"supplied by|provided by|rely on|depend\w* on)\b",
            re.I,
        ),
        "supplier or purchased input disclosed in filing",
    ),
)

DEPENDENCY_SOLE = re.compile(r"\b(sole[- ]source|single[- ]source|only supplier)\b", re.I)
DEPENDENCY_HIGH = re.compile(
    r"\b(rely heavily|substantially dependent|significant supplier|limited number of suppliers)\b",
    re.I,
)
STRONG_RELATION = re.compile(
    r"\b(rely on|depend\w* on|supplied by|provided by|manufactured by|"
    r"purchase\w* from|procure\w* from|customer concentration)\b",
    re.I,
)


@dataclass(frozen=True)
class DisclosedRoleRule:
    entity_key: str
    related_company_name: str
    relationship_type: str
    product_or_input: str
    pattern: re.Pattern[str]
    dependency_level: str
    confidence: float


# Some issuers disclose an operational dependency but deliberately do not name the
# counterparty. These narrow rules preserve the missing identity instead of guessing
# a company from industry knowledge.
DISCLOSED_ROLE_RULES = (
    DisclosedRoleRule(
        "undisclosed-photolithography-equipment-supplier",
        "Undisclosed photolithography equipment supplier",
        "equipment",
        "photolithography tools",
        re.compile(
            r"\bphotolithography tools\b.*\b(?:single|sole)[- ]supplier\b|"
            r"\b(?:single|sole)[- ]supplier\b.*\bphotolithography tools\b",
            re.I,
        ),
        "sole_source",
        0.82,
    ),
    DisclosedRoleRule(
        "undisclosed-contract-manufacturers",
        "Undisclosed third-party contract manufacturers",
        "contract_manufacturer",
        "company devices",
        re.compile(
            r"\b(?:our|the company(?:'s)?) devices\b.{0,120}\b"
            r"manufactured by third-party contract manufacturers\b",
            re.I,
        ),
        "high",
        0.78,
    ),
    DisclosedRoleRule(
        "undisclosed-datacenter-component-suppliers",
        "Undisclosed datacenter component suppliers",
        "materials",
        "servers, GPUs and datacenter components",
        re.compile(
            r"\bdepend on the timely availability of critical hardware, equipment, "
            r"and components\b",
            re.I,
        ),
        "high",
        0.76,
    ),
    DisclosedRoleRule(
        "undisclosed-controller-and-assembly-providers",
        "Undisclosed controller, foundry, assembly and test providers",
        "contract_manufacturer",
        "controllers, analog integrated circuits, foundry, assembly and test services",
        re.compile(
            r"\bdependent on our relationships with third-party manufacturers of "
            r"controllers, analog integrated circuits\b",
            re.I,
        ),
        "high",
        0.76,
    ),
    DisclosedRoleRule(
        "undisclosed-manufacturing-utilities",
        "Undisclosed utilities serving manufacturing facilities",
        "energy",
        "electricity, gas and water",
        re.compile(
            r"\boperations are dependent on a reliable and uninterrupted supply of "
            r"electrical power, gas, and water\b",
            re.I,
        ),
        "high",
        0.76,
    ),
)


class SupplyChainDiscoveryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filings_selected: int = Field(ge=0)
    filings_completed: int = Field(ge=0)
    filings_failed: int = Field(ge=0)
    candidates_upserted: int = Field(ge=0)
    tickers_completed: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "head"}:
            self.hidden_depth += 1
        elif not self.hidden_depth and tag in {
            "p",
            "div",
            "li",
            "tr",
            "br",
            "h1",
            "h2",
            "h3",
            "h4",
        }:
            self.parts.append(". ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "head"} and self.hidden_depth:
            self.hidden_depth -= 1
        elif not self.hidden_depth and tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.parts.append(". ")

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)
            self.parts.append(" ")


async def discover_sec_supply_chain_candidates(
    session: Session,
    *,
    client: httpx.AsyncClient,
    archive: ColdArchive,
    tickers: set[str] | None = None,
    batch_size: int = 5,
    request_interval_seconds: float = 0.25,
    force: bool = False,
) -> SupplyChainDiscoveryResult:
    """Archive the latest 10-K/20-F per issuer and extract named review candidates."""
    if not 1 <= batch_size <= 100:
        raise ValueError("batch_size must be between one and one hundred")
    selected_tickers = {item.strip().upper() for item in (tickers or set()) if item.strip()}
    ensure_supply_chain_coverage(session)
    session.commit()
    profiles = {item.ticker: item for item in session.scalars(select(CompanyProfile))}
    filings = list(
        session.scalars(
            select(CompanyFiling)
            .where(CompanyFiling.form.in_(ANNUAL_SUPPLY_CHAIN_FORMS))
            .order_by(
                CompanyFiling.ticker,
                desc(CompanyFiling.filed_at),
                CompanyFiling.form,
                desc(CompanyFiling.accession_number),
            )
        )
    )
    latest: dict[str, CompanyFiling] = {}
    for filing in filings:
        latest.setdefault(filing.ticker, filing)
    queue: list[CompanyFiling] = []
    for ticker in sorted(latest):
        if selected_tickers and ticker not in selected_tickers:
            continue
        state = session.get(CompanySupplyChainCoverage, ticker)
        filing = latest[ticker]
        if (
            not force
            and state is not None
            and state.latest_filing_accession == filing.accession_number
            and state.last_parser_version == SUPPLY_CHAIN_PARSER_VERSION
            and state.last_completed_at is not None
        ):
            continue
        queue.append(filing)
        if len(queue) >= batch_size:
            break

    completed = 0
    failed = 0
    candidates = 0
    completed_tickers: list[str] = []
    errors: list[str] = []
    entities = _entity_catalog(profiles.values())
    for index, filing in enumerate(queue):
        if index and request_interval_seconds:
            await asyncio.sleep(request_interval_seconds)
        try:
            count = await _discover_one_filing(
                session,
                client=client,
                archive=archive,
                filing=filing,
                profile=profiles[filing.ticker],
                entities=entities,
            )
            completed += 1
            candidates += count
            completed_tickers.append(filing.ticker)
        except Exception as exc:
            session.rollback()
            state = session.get(CompanySupplyChainCoverage, filing.ticker)
            if state is not None:
                state.status = "failed"
                state.last_error = f"{type(exc).__name__}: {str(exc)[:1_800]}"
                session.commit()
            failed += 1
            errors.append(f"{filing.ticker} {filing.accession_number}: {type(exc).__name__}: {exc}")
    return SupplyChainDiscoveryResult(
        filings_selected=len(queue),
        filings_completed=completed,
        filings_failed=failed,
        candidates_upserted=candidates,
        tickers_completed=completed_tickers,
        errors=errors,
    )


async def _discover_one_filing(
    session: Session,
    *,
    client: httpx.AsyncClient,
    archive: ColdArchive,
    filing: CompanyFiling,
    profile: CompanyProfile,
    entities: tuple[RelatedEntity, ...],
) -> int:
    state = session.get(CompanySupplyChainCoverage, filing.ticker)
    if state is None:
        raise ValueError(f"missing supply-chain coverage state for {filing.ticker}")
    state.status = "discovering"
    state.last_started_at = datetime.now(UTC)
    state.last_error = None
    session.commit()

    relative_path = _archive_path(filing)
    archived_path = archive.root / relative_path
    if archived_path.is_file():
        payload = archived_path.read_bytes()
    else:
        response = await client.get(filing.source_url)
        response.raise_for_status()
        payload = response.content
    if not payload or len(payload) > MAX_FILING_BYTES:
        raise ValueError(
            f"annual filing response size is outside the allowed range: {len(payload)}"
        )
    stored_path = archive.store_bytes(relative_path, payload)
    extracted = extract_named_relationships(
        payload,
        subject_ticker=filing.ticker,
        subject_name=profile.name,
        entities=entities,
    )
    prefix = f"sec-filing:{filing.ticker}:{filing.accession_number}:"
    session.execute(
        delete(CompanySupplyChainEdge).where(
            CompanySupplyChainEdge.subject_ticker == filing.ticker,
            CompanySupplyChainEdge.review_status == "candidate",
            CompanySupplyChainEdge.source_kind == "sec_filing_candidate",
            CompanySupplyChainEdge.source_ref.like(f"{prefix}%"),
        )
    )
    upserted = 0
    for item in extracted:
        source_ref = f"{prefix}{item['relationship_type']}:{item['entity_key']}"
        existing = session.scalar(
            select(CompanySupplyChainEdge.id).where(
                CompanySupplyChainEdge.subject_ticker == filing.ticker,
                CompanySupplyChainEdge.related_company_name == item["related_company_name"],
                CompanySupplyChainEdge.relationship_type == item["relationship_type"],
                CompanySupplyChainEdge.product_or_input == item["product_or_input"],
                CompanySupplyChainEdge.source_ref == source_ref,
            )
        )
        if existing is not None:
            continue
        session.add(
            CompanySupplyChainEdge(
                subject_ticker=filing.ticker,
                related_company_name=item["related_company_name"],
                related_ticker=item["related_ticker"],
                relationship_type=item["relationship_type"],
                product_or_input=item["product_or_input"],
                geography=item["geography"],
                dependency_level=item["dependency_level"],
                review_status="candidate",
                confidence=item["confidence"],
                source_kind="sec_filing_candidate",
                source_ref=source_ref,
                source_url=filing.source_url,
                source_excerpt=item["source_excerpt"],
                observed_at=filing.report_date or filing.filed_at,
                available_at=filing.filed_at,
                valid_from=filing.report_date,
            )
        )
        upserted += 1
    state = session.get(CompanySupplyChainCoverage, filing.ticker) or state
    state.latest_filing_accession = filing.accession_number
    state.latest_filing_date = filing.filed_at
    state.latest_raw_archive_path = stored_path
    state.last_parser_version = SUPPLY_CHAIN_PARSER_VERSION
    state.last_completed_at = datetime.now(UTC)
    state.last_error = None
    state.gaps = (
        [
            "candidate relationships require source review",
            "facility and production-line mapping",
            "capacity, volume, contract and delivery series",
        ]
        if extracted
        else [
            "latest annual filing had no named relationship in the supported entity catalog",
            "facility and production-line mapping",
            "capacity, volume, contract and delivery series",
        ]
    )
    refresh_supply_chain_coverage(session, ticker=filing.ticker)
    session.commit()
    return upserted


def extract_named_relationships(
    payload: bytes,
    *,
    subject_ticker: str,
    subject_name: str,
    entities: tuple[RelatedEntity, ...] = KNOWN_RELATED_ENTITIES,
) -> list[dict[str, Any]]:
    """Return conservative, quoted candidates; this function never verifies an edge."""
    parser = _VisibleTextParser()
    text = payload.decode("utf-8", errors="replace")
    parser.feed(text)
    normalized = re.sub(r"\s+", " ", unescape("".join(parser.parts))).strip()
    sentences = re.split(r"(?<=[.!?])\s+|(?<=;)\s+(?=[A-Z])", normalized)
    subject_tokens = {subject_ticker.casefold(), subject_name.casefold()}
    found: dict[tuple[str, str], dict[str, Any]] = {}
    for sentence in sentences:
        sentence = sentence.strip(" .")
        if not 25 <= len(sentence) <= 2_000:
            continue
        relation = _relationship(sentence)
        if relation is None:
            continue
        relationship_type, product_or_input = relation
        for entity in entities:
            if entity.ticker and entity.ticker.casefold() == subject_ticker.casefold():
                continue
            if entity.name.casefold() in subject_tokens:
                continue
            alias = next((item for item in entity.aliases if _contains_alias(sentence, item)), None)
            if alias is None:
                continue
            dependency_level = (
                "sole_source"
                if DEPENDENCY_SOLE.search(sentence)
                else "high"
                if DEPENDENCY_HIGH.search(sentence)
                else "unknown"
            )
            confidence = (
                0.78
                if dependency_level == "sole_source"
                else 0.72
                if STRONG_RELATION.search(sentence)
                else 0.58
            )
            key = (entity.name, relationship_type)
            candidate = {
                "entity_key": (
                    entity.ticker or re.sub(r"[^a-z0-9]+", "-", entity.name.casefold()).strip("-")
                )[:64],
                "related_company_name": entity.name,
                "related_ticker": entity.ticker,
                "relationship_type": relationship_type,
                "product_or_input": product_or_input,
                "geography": entity.geography,
                "dependency_level": dependency_level,
                "confidence": confidence,
                "source_excerpt": sentence[:1_800],
                "matched_alias": alias,
            }
            previous = found.get(key)
            if previous is None or candidate["confidence"] > previous["confidence"]:
                found[key] = candidate
    for item in extract_disclosed_role_relationships(normalized):
        found.setdefault(
            (str(item["related_company_name"]), str(item["relationship_type"])),
            item,
        )
    return sorted(
        found.values(),
        key=lambda item: (-float(item["confidence"]), str(item["related_company_name"])),
    )


def extract_disclosed_role_relationships(text: str) -> list[dict[str, Any]]:
    """Extract direct but unnamed issuer dependencies without guessing identities."""
    sentences = re.split(r"(?<=[.!?])\s+|(?<=;)\s+(?=[A-Z])", text)
    found: dict[str, dict[str, Any]] = {}
    for sentence in sentences:
        sentence = sentence.strip(" .")
        if not 25 <= len(sentence) <= 2_000:
            continue
        for rule in DISCLOSED_ROLE_RULES:
            if rule.entity_key in found or rule.pattern.search(sentence) is None:
                continue
            found[rule.entity_key] = {
                "entity_key": rule.entity_key,
                "related_company_name": rule.related_company_name,
                "related_ticker": None,
                "relationship_type": rule.relationship_type,
                "product_or_input": rule.product_or_input,
                "geography": None,
                "dependency_level": rule.dependency_level,
                "confidence": rule.confidence,
                "source_excerpt": sentence[:1_800],
                "matched_alias": "issuer-disclosed unnamed counterparty role",
            }
    return list(found.values())


def _relationship(sentence: str) -> tuple[str, str] | None:
    for relationship_type, pattern, product in RELATION_RULES:
        if pattern.search(sentence):
            return relationship_type, product
    return None


def _contains_alias(sentence: str, alias: str) -> bool:
    escaped = re.escape(alias)
    return re.search(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", sentence, re.I) is not None


def _entity_catalog(profiles: Any) -> tuple[RelatedEntity, ...]:
    entities: dict[tuple[str | None, str], RelatedEntity] = {
        (item.ticker, item.name): item for item in KNOWN_RELATED_ENTITIES
    }
    for profile in profiles:
        shortened = re.sub(
            r"[, ]+(Inc\.?|Incorporated|Corporation|Corp\.?|Company|Co\.?|Ltd\.?)$",
            "",
            profile.name,
            flags=re.I,
        ).strip()
        aliases = tuple(dict.fromkeys(item for item in (profile.name, shortened) if len(item) >= 4))
        entities[(profile.ticker, profile.name)] = RelatedEntity(
            profile.name,
            profile.ticker,
            aliases,
        )
    return tuple(entities.values())


def _archive_path(filing: CompanyFiling) -> str:
    filename = Path(urlsplit(filing.source_url).path).name or "primary-document.htm"
    accession = filing.accession_number.replace("-", "")
    return f"raw/sec/company-filings/{filing.ticker}/{accession}/{filename}"
