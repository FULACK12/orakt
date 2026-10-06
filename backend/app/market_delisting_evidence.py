"""Conservative SEC filing discovery for post-delisting shareholder value."""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    MarketAssetIdentifier,
    MarketAssetLifecycle,
    MarketDelistingEvidenceCandidate,
    MarketDelistingEvidenceState,
    MarketDelistingOutcome,
    MarketPriceBackfillState,
)
from app.storage.archive import ArchiveCapacityError, ColdArchive

SEC_EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
SEC_ARCHIVE_ROOT = "https://www.sec.gov/Archives/edgar/data"
SEC_API_DOCUMENTATION_URL = (
    "https://www.sec.gov/search-filings/edgar-application-programming-interfaces"
)
TARGET_FORMS = (
    "8-K",
    "DEFM14A",
    "PREM14A",
    "SC 13E3",
    "SC 14D9",
    "25-NSE",
    "15-12B",
    "15-12G",
    "15F-12G",
    "6-K",
    "20-F",
)
RETRY_DAYS = 14

LEGAL_NAME_TOKENS = {
    "adr",
    "ads",
    "co",
    "company",
    "corp",
    "corporation",
    "inc",
    "incorporated",
    "ltd",
    "limited",
    "ordinary",
    "plc",
    "spon",
    "sponsored",
    "the",
}


class SecEvidenceError(RuntimeError):
    """Sanitized SEC discovery error safe for logs and API state."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class SecDelistingEvidenceSyncResult(BaseModel):
    """Safe counters for one bounded SEC evidence-discovery pass."""

    model_config = ConfigDict(extra="forbid")

    attempted_assets: int = Field(ge=0)
    cik_resolved_assets: int = Field(ge=0)
    metadata_candidate_filings: int = Field(ge=0)
    extracted_value_candidates: int = Field(ge=0)
    body_contact_required_assets: int = Field(ge=0)
    no_evidence_assets: int = Field(ge=0)
    lifecycle_conflict_assets: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list, max_length=20)


@dataclass(frozen=True)
class CikSelection:
    status: str
    cik: str | None
    name: str | None
    similarity: float | None


async def sync_sec_delisting_evidence(
    session: Session,
    *,
    client: httpx.AsyncClient,
    archive: ColdArchive,
    user_agent: str,
    contact_email: str | None = None,
    max_assets: int = 3,
    request_interval_seconds: float = 0.25,
    now: datetime | None = None,
) -> SecDelistingEvidenceSyncResult:
    """Find SEC filing candidates without turning extraction into a verified return."""
    if max_assets < 1:
        raise ValueError("max_assets must be positive")
    if request_interval_seconds < 0:
        raise ValueError("request interval cannot be negative")
    if contact_email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", contact_email):
        raise ValueError("SEC contact email is invalid")
    generated_at = now or datetime.now(UTC)
    retry_before = generated_at - timedelta(days=RETRY_DAYS)
    retry_condition = (
        MarketDelistingEvidenceState.asset_key.is_(None)
        | MarketDelistingEvidenceState.last_attempt_at.is_(None)
        | (MarketDelistingEvidenceState.last_attempt_at < retry_before)
    )
    if contact_email:
        retry_condition |= (
            MarketDelistingEvidenceState.body_access_status == "contact_required"
        )
    rows = list(
        session.execute(
            select(
                MarketAssetLifecycle,
                MarketAssetIdentifier,
                MarketDelistingOutcome,
                MarketDelistingEvidenceState,
            )
            .join(
                MarketAssetIdentifier,
                MarketAssetIdentifier.asset_key == MarketAssetLifecycle.asset_key,
            )
            .join(
                MarketDelistingOutcome,
                MarketDelistingOutcome.asset_key == MarketAssetLifecycle.asset_key,
            )
            .outerjoin(
                MarketDelistingEvidenceState,
                MarketDelistingEvidenceState.asset_key == MarketAssetLifecycle.asset_key,
            )
            .where(
                MarketAssetIdentifier.identity_status.in_(
                    ("verified", "lifecycle_conflict")
                ),
                MarketDelistingOutcome.status.in_(
                    ("evidence_required", "identity_required")
                ),
                retry_condition,
            )
            .order_by(MarketAssetLifecycle.delisting_date.desc())
            .limit(max_assets)
        )
    )
    counters = {
        "cik": 0,
        "filings": 0,
        "values": 0,
        "contact": 0,
        "none": 0,
        "conflict": 0,
    }
    errors: list[str] = []
    for lifecycle, identity, outcome, state in rows:
        state = _ensure_state(session, lifecycle.asset_key, state)
        state.attempt_count += 1
        state.last_attempt_at = generated_at
        search_start = (lifecycle.delisting_date or generated_at.date()) - timedelta(
            days=1_825
        )
        search_end = (lifecycle.delisting_date or generated_at.date()) + timedelta(days=365)
        state.search_start = search_start
        state.search_end = search_end
        try:
            payload = await _search_company_filings(
                client,
                company_name=lifecycle.name,
                start=search_start,
                end=search_end,
                user_agent=user_agent,
            )
            archive_path = _archive_search_payload(
                archive,
                asset_key=lifecycle.asset_key,
                fetched_on=generated_at.date(),
                payload=payload,
            )
            state.raw_archive_path = archive_path
            selection = select_sec_cik(lifecycle.name, payload, preferred_cik=identity.sec_cik)
            state.cik_name = selection.name
            state.cik_name_similarity = selection.similarity
            if selection.status != "verified" or selection.cik is None:
                state.status = selection.status
                state.sec_cik = None
                state.filing_count = 0
                state.extracted_candidate_count = 0
                state.body_access_status = "not_attempted"
                state.last_error_code = selection.status
                state.last_error_message = "SEC company identity was not uniquely resolved"
                errors.append(f"{lifecycle.symbol}: {selection.status}")
                continue
            identity.sec_cik = selection.cik
            state.sec_cik = selection.cik
            counters["cik"] += 1
            hits = _matching_hits(payload, selection.cik)
            metadata_candidates = 0
            extracted_candidates = 0
            body_access_status = "contact_required" if not contact_email else "downloaded"
            for hit in hits:
                filing = _filing_from_hit(hit, selection.cik)
                if filing is None or not _is_terminal_candidate_filing(filing):
                    continue
                candidate = _upsert_metadata_candidate(
                    session,
                    lifecycle=lifecycle,
                    filing=filing,
                    archive_path=archive_path,
                    body_status=body_access_status,
                )
                metadata_candidates += 1
                if contact_email:
                    body_status, body_archive, body_text = await _fetch_filing_body(
                        client,
                        archive=archive,
                        filing=filing,
                        user_agent=user_agent,
                        contact_email=contact_email,
                        fetched_on=generated_at.date(),
                    )
                    candidate.body_status = body_status
                    if body_archive:
                        candidate.raw_archive_path = body_archive
                    if body_text:
                        extracted_candidates += _store_extracted_candidates(
                            session,
                            lifecycle=lifecycle,
                            filing=filing,
                            body_text=body_text,
                            body_archive_path=body_archive,
                        )
                    if body_status != "downloaded":
                        body_access_status = body_status
                    if request_interval_seconds:
                        await asyncio.sleep(request_interval_seconds)
            state.filing_count = metadata_candidates
            state.extracted_candidate_count = extracted_candidates
            state.body_access_status = body_access_status
            state.last_error_code = None
            state.last_error_message = None
            state.last_success_at = generated_at
            conflict_date = _terminal_lifecycle_conflict_date(
                hits,
                cik=selection.cik,
                last_trade_date=outcome.last_trade_date,
            )
            if conflict_date is not None:
                state.status = "lifecycle_conflict_ticker_reuse"
                state.last_error_code = "sec_terminal_event_before_price_end"
                state.last_error_message = (
                    f"SEC terminal filings dated {conflict_date.isoformat()} precede "
                    "the retained price-series end; series quarantined"
                )
                identity.identity_status = "lifecycle_conflict"
                identity.last_error_code = "sec_terminal_event_before_price_end"
                identity.last_error_message = state.last_error_message
                outcome.status = "identity_required"
                price_state = session.get(MarketPriceBackfillState, lifecycle.asset_key)
                if price_state is not None:
                    price_state.status = "ticker_reused"
                    price_state.last_error_code = "sec_terminal_event_before_price_end"
                    price_state.last_error_message = state.last_error_message
                counters["conflict"] += 1
            elif metadata_candidates == 0:
                state.status = "no_candidate_filings"
                state.body_access_status = "not_needed"
                counters["none"] += 1
            elif not contact_email:
                state.status = "metadata_found_body_contact_required"
                counters["contact"] += 1
            elif extracted_candidates:
                state.status = "value_candidates_found"
            else:
                state.status = "metadata_found_no_value_extracted"
            counters["filings"] += metadata_candidates
            counters["values"] += extracted_candidates
            session.flush()
        except SecEvidenceError as exc:
            state.status = "provider_error"
            state.last_error_code = exc.code
            state.last_error_message = str(exc)[:500]
            errors.append(f"{lifecycle.symbol}: {exc.code}")
        except (ArchiveCapacityError, OSError):
            state.status = "archive_error"
            state.last_error_code = "cold_archive_unavailable"
            state.last_error_message = "SEC discovery response could not be archived"
            errors.append(f"{lifecycle.symbol}: cold_archive_unavailable")
        session.flush()
        if request_interval_seconds:
            await asyncio.sleep(request_interval_seconds)
    return SecDelistingEvidenceSyncResult(
        attempted_assets=len(rows),
        cik_resolved_assets=counters["cik"],
        metadata_candidate_filings=counters["filings"],
        extracted_value_candidates=counters["values"],
        body_contact_required_assets=counters["contact"],
        no_evidence_assets=counters["none"],
        lifecycle_conflict_assets=counters["conflict"],
        errors=errors[:20],
    )


async def _search_company_filings(
    client: httpx.AsyncClient,
    *,
    company_name: str,
    start: date,
    end: date,
    user_agent: str,
) -> dict[str, Any]:
    query_name = re.sub(r'["\\]+', " ", company_name).strip()
    try:
        response = await client.get(
            SEC_EFTS_URL,
            params={
                "q": f'"{query_name}"',
                "dateRange": "custom",
                "startdt": start.isoformat(),
                "enddt": end.isoformat(),
                "forms": ",".join(TARGET_FORMS),
                "from": 0,
                "size": 100,
            },
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
        )
    except httpx.HTTPError as exc:
        raise SecEvidenceError(
            "sec_search_http",
            f"SEC filing search failed ({type(exc).__name__})",
        ) from None
    if response.status_code == 429:
        raise SecEvidenceError("sec_rate_limited", "SEC filing search rate limit reached")
    if response.status_code != 200:
        raise SecEvidenceError(
            "sec_search_http",
            f"SEC filing search returned HTTP {response.status_code}",
        )
    try:
        payload = response.json()
    except json.JSONDecodeError:
        raise SecEvidenceError(
            "sec_invalid_json",
            "SEC filing search returned invalid JSON",
        ) from None
    if not isinstance(payload, dict) or not isinstance(payload.get("hits"), dict):
        raise SecEvidenceError("sec_invalid_shape", "SEC filing search response was incomplete")
    return payload


def select_sec_cik(
    company_name: str,
    payload: dict[str, Any],
    *,
    preferred_cik: str | None = None,
) -> CikSelection:
    """Resolve a CIK only from exact-company search hits with consistent filing identity."""
    scored: dict[str, tuple[float, str, int]] = {}
    for hit in _raw_hits(payload):
        source = hit.get("_source")
        if not isinstance(source, dict):
            continue
        ciks = [str(value).zfill(10) for value in source.get("ciks", []) if str(value).isdigit()]
        names = [str(value) for value in source.get("display_names", []) if str(value).strip()]
        if len(ciks) != 1 or not names:
            continue
        cik = ciks[0]
        display_name = _clean_sec_display_name(names[0])
        similarity = _name_similarity(company_name, display_name)
        current = scored.get(cik)
        count = (current[2] if current else 0) + 1
        if current is None or similarity > current[0]:
            scored[cik] = (similarity, display_name, count)
        else:
            scored[cik] = (current[0], current[1], count)
    if preferred_cik:
        normalized = str(preferred_cik).zfill(10)
        match = scored.get(normalized)
        if match is not None and match[0] >= 0.82:
            return CikSelection("verified", normalized, match[1], match[0])
    ordered = sorted(scored.items(), key=lambda item: (item[1][0], item[1][2]), reverse=True)
    if not ordered:
        return CikSelection("cik_unresolved", None, None, None)
    cik, best = ordered[0]
    runner_score = ordered[1][1][0] if len(ordered) > 1 else 0.0
    if best[0] >= 0.88 and (len(ordered) == 1 or best[0] - runner_score >= 0.08):
        return CikSelection("verified", cik, best[1], best[0])
    status = "cik_name_mismatch" if best[0] < 0.55 else "cik_ambiguous"
    return CikSelection(status, None, best[1], best[0])


def _raw_hits(payload: dict[str, Any]) -> list[dict[str, Any]]:
    hits = payload.get("hits", {}).get("hits", [])
    return [hit for hit in hits if isinstance(hit, dict)] if isinstance(hits, list) else []


def _matching_hits(payload: dict[str, Any], cik: str) -> list[dict[str, Any]]:
    return [
        hit
        for hit in _raw_hits(payload)
        if cik in [str(value).zfill(10) for value in hit.get("_source", {}).get("ciks", [])]
    ]


def _filing_from_hit(hit: dict[str, Any], cik: str) -> dict[str, Any] | None:
    source = hit.get("_source")
    hit_id = str(hit.get("_id") or "")
    if not isinstance(source, dict) or ":" not in hit_id:
        return None
    if source.get("sequence") not in {1, "1"}:
        return None
    accession, document_name = hit_id.split(":", 1)
    if not re.fullmatch(r"[0-9-]{18,24}", accession):
        return None
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,255}", document_name):
        return None
    form = str(source.get("form") or "")[:32]
    if form not in TARGET_FORMS:
        return None
    try:
        filed_on = date.fromisoformat(str(source.get("file_date")))
    except ValueError:
        return None
    accession_compact = accession.replace("-", "")
    source_url = (
        f"{SEC_ARCHIVE_ROOT}/{int(cik)}/{accession_compact}/{document_name}"
    )
    items = source.get("items") if isinstance(source.get("items"), list) else []
    return {
        "cik": cik,
        "accession": accession,
        "document_name": document_name,
        "form": form,
        "filed_on": filed_on,
        "source_url": source_url,
        "items": [str(item) for item in items],
        "description": str(source.get("file_description") or "")[:255],
    }


def _is_terminal_candidate_filing(filing: dict[str, Any]) -> bool:
    form = filing["form"]
    if form == "8-K":
        return bool({"2.01", "3.01"} & set(filing["items"]))
    if form in {"6-K", "20-F"}:
        return bool(
            re.search(
                r"merger|acquisition|delist|deregister|termination|liquidat|tender",
                filing["description"],
                re.IGNORECASE,
            )
        )
    return True


def _upsert_metadata_candidate(
    session: Session,
    *,
    lifecycle: MarketAssetLifecycle,
    filing: dict[str, Any],
    archive_path: str,
    body_status: str,
) -> MarketDelistingEvidenceCandidate:
    evidence_type, confidence = _metadata_evidence_type(filing)
    evidence_key = _evidence_key(
        lifecycle.asset_key,
        filing["accession"],
        filing["document_name"],
        evidence_type,
        "filing_metadata",
    )
    candidate = session.get(MarketDelistingEvidenceCandidate, evidence_key)
    if candidate is None:
        candidate = MarketDelistingEvidenceCandidate(
            evidence_key=evidence_key,
            asset_key=lifecycle.asset_key,
            sec_cik=filing["cik"],
            accession_number=filing["accession"],
            document_name=filing["document_name"],
            form=filing["form"],
            filed_on=filing["filed_on"],
            source_url=filing["source_url"],
            evidence_type=evidence_type,
            evidence_basis="filing_metadata",
            confidence=confidence,
            body_status=body_status,
            review_status="candidate",
            raw_archive_path=archive_path,
        )
        session.add(candidate)
    elif candidate.review_status == "candidate":
        candidate.body_status = body_status
        candidate.raw_archive_path = archive_path
    return candidate


def _metadata_evidence_type(filing: dict[str, Any]) -> tuple[str, float]:
    form = filing["form"]
    items = set(filing["items"])
    if form in {"DEFM14A", "PREM14A"}:
        return "merger_consideration_filing", 0.72
    if form == "SC 13E3":
        return "going_private_terms_filing", 0.72
    if form == "SC 14D9":
        return "tender_offer_response_filing", 0.68
    if form == "25-NSE":
        return "exchange_delisting_notice", 0.62
    if form in {"15-12B", "15-12G"}:
        return "registration_termination", 0.58
    if form == "15F-12G":
        return "foreign_issuer_registration_termination", 0.58
    if form in {"6-K", "20-F"}:
        return "foreign_issuer_event_filing", 0.45
    if "2.01" in items:
        return "transaction_completion_filing", 0.78
    if "3.01" in items:
        return "delisting_event_filing", 0.68
    return "corporate_event_filing", 0.45


async def _fetch_filing_body(
    client: httpx.AsyncClient,
    *,
    archive: ColdArchive,
    filing: dict[str, Any],
    user_agent: str,
    contact_email: str,
    fetched_on: date,
) -> tuple[str, str | None, str | None]:
    headers = {
        "User-Agent": f"{user_agent} {contact_email}",
        "Accept-Encoding": "gzip, deflate",
    }
    try:
        response = await client.get(filing["source_url"], headers=headers)
    except httpx.HTTPError:
        return "download_error", None, None
    if response.status_code == 403:
        return "access_denied", None, None
    if response.status_code == 429:
        return "rate_limited", None, None
    if response.status_code != 200:
        return "download_error", None, None
    raw = response.content
    digest = hashlib.sha256(raw).hexdigest()
    relative = (
        f"raw/sec/delisting-evidence/{fetched_on:%Y/%m/%d}/"
        f"filings/{digest}.html.gz"
    )
    archive_path = archive.store_bytes(relative, gzip.compress(raw, compresslevel=6, mtime=0))
    return "downloaded", archive_path, _html_to_text(response.text)


def extract_terminal_value_candidates(body_text: str) -> list[dict[str, Any]]:
    """Extract narrowly worded candidates; all outputs still require human review."""
    normalized = re.sub(r"\s+", " ", body_text).strip()
    candidates: list[dict[str, Any]] = []
    cash_patterns = (
        re.compile(
            r"(?:each|every)\s+(?:outstanding\s+)?share.{0,260}?"
            r"(?:entitled to receive|converted into the right to receive|right to receive)"
            r".{0,120}?\$\s*([0-9]{1,6}(?:\.[0-9]{1,4})?)"
            r".{0,30}?(?:in\s+cash|cash\s+consideration)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:cash\s+consideration|per[- ]share\s+merger\s+consideration|"
            r"merger\s+consideration|offer\s+price).{0,140}?"
            r"\$\s*([0-9]{1,6}(?:\.[0-9]{1,4})?)",
            re.IGNORECASE,
        ),
        re.compile(
            r"\$\s*([0-9]{1,6}(?:\.[0-9]{1,4})?)\s+"
            r"(?:in\s+cash\s+)?per\s+share",
            re.IGNORECASE,
        ),
    )
    seen_cash: set[float] = set()
    for pattern_index, pattern in enumerate(cash_patterns):
        for match in pattern.finditer(normalized):
            value = float(match.group(1))
            context = _context(normalized, match.start(), match.end())
            value_prefix = normalized[max(0, match.start(1) - 90) : match.start(1)]
            value_suffix = normalized[match.end(1) : match.end(1) + 90]
            local_value_context = f"{value_prefix[-65:]}{match.group(1)}{value_suffix[:65]}"
            table_context = normalized[
                max(0, match.start(1) - 260) : match.end(1) + 180
            ]
            if value <= 0 or not re.search(
                r"converted\s+into\s+the\s+right\s+to\s+receive|"
                r"entitled\s+to\s+receive|cash\s+consideration|"
                r"per[- ]share\s+merger\s+consideration|"
                r"merger\s+consideration|offer\s+price",
                context,
                re.IGNORECASE,
            ):
                continue
            if not re.search(
                r"per\s+share|each\s+(?:outstanding\s+)?share|"
                r"right\s+to\s+receive|entitled\s+to\s+receive",
                context,
                re.IGNORECASE,
            ):
                continue
            if re.search(r"par\s+value\s+\$\s*$", value_prefix, re.IGNORECASE):
                continue
            if re.match(r"\s*(?:million|billion)\b", value_suffix, re.IGNORECASE):
                continue
            if re.search(
                r"(?:closing|trading|market)\s+price(?:\s+of)?\s+\$\s*$",
                value_prefix,
                re.IGNORECASE,
            ):
                continue
            if re.search(
                r"closing\s+price.{0,100}closing\s+price.{0,140}"
                r"exchange\s+ratio.{0,100}implied\s+per\s+share\s+value",
                table_context,
                re.IGNORECASE,
            ):
                continue
            if pattern_index > 0 and not re.search(
                r"per\s+share|offer\s+price|right\s+to\s+receive|"
                r"entitled\s+to\s+receive",
                local_value_context,
                re.IGNORECASE,
            ):
                continue
            if pattern_index > 0 and re.search(
                r"financial\s+advisor|discounted\s+cash\s+flow|"
                r"selected\s+(?:companies|transactions)|price\s+target|"
                r"trading\s+prices|range\s+of|sensitivity\s+analysis|"
                r"premiums?\s+paid",
                context,
                re.IGNORECASE,
            ):
                continue
            if pattern_index == 2:
                nearby_values = {
                    float(item)
                    for item in re.findall(
                        r"\$\s*([0-9]{1,6}(?:\.[0-9]{1,4})?)\s+"
                        r"(?:in\s+cash\s+)?per\s+share",
                        context,
                        re.IGNORECASE,
                    )
                }
                if len(nearby_values) > 1:
                    continue
            if value in seen_cash:
                continue
            seen_cash.add(value)
            evidence_type = "cash_consideration_per_share"
            confidence = 0.82
            sentence_start = normalized.rfind(
                ". ", max(0, match.start(1) - 500), match.start(1)
            )
            sentence_end = normalized.find(". ", match.end(1), match.end(1) + 500)
            classification_context = normalized[
                sentence_start + 2 if sentence_start >= 0 else max(0, match.start(1) - 220) :
                sentence_end if sentence_end >= 0 else match.end(1) + 160
            ]
            if re.search(
                r"(?:implied|exchange\s+ratio|stock\s+consideration|"
                r"market\s+value|value\s+of\s+the\s+per\s+share\s+merger)",
                classification_context,
                re.IGNORECASE,
            ) and not re.search(
                rf"(?:\$\s*{re.escape(match.group(1))}.{{0,35}}in\s+cash|"
                rf"in\s+cash.{{0,35}}\$\s*{re.escape(match.group(1))})",
                local_value_context,
                re.IGNORECASE,
            ):
                evidence_type = "implied_stock_consideration_per_share"
                confidence = 0.74
            elif re.search(
                r"(?:draft|propos(?:ed|ing)|potential|would\s+be|"
                r"if\s+the\s+merger\s+consideration|offer\s+letter|"
                r"reduced\s+to)",
                classification_context,
                re.IGNORECASE,
            ):
                evidence_type = "historical_offer_per_share"
                confidence = 0.72
            candidates.append(
                {
                    "evidence_type": evidence_type,
                    "candidate_value": value,
                    "value_unit": "USD_per_share",
                    "excerpt": context,
                    "confidence": confidence,
                }
            )
    exchange_pattern = re.compile(
        r"exchange\s+ratio(?:\s+of|\s+is)?\s+([0-9]{1,4}(?:\.[0-9]{1,8})?)",
        re.IGNORECASE,
    )
    seen_exchange: set[float] = set()
    for match in exchange_pattern.finditer(normalized):
        value = float(match.group(1))
        if 0 < value <= 100 and value not in seen_exchange:
            seen_exchange.add(value)
            candidates.append(
                {
                    "evidence_type": "share_exchange_ratio",
                    "candidate_value": value,
                    "value_unit": "acquirer_shares_per_share",
                    "excerpt": _context(normalized, match.start(), match.end()),
                    "confidence": 0.78,
                }
            )
    worthless_pattern = re.compile(
        r"(?:common\s+(?:stock|shares?).{0,100}?(?:worthless|no\s+value)|"
        r"no\s+distribution.{0,100}?(?:stockholders|shareholders))",
        re.IGNORECASE,
    )
    for match in worthless_pattern.finditer(normalized):
        candidates.append(
            {
                "evidence_type": "possible_worthlessness",
                "candidate_value": 0.0,
                "value_unit": "USD_per_share",
                "excerpt": _context(normalized, match.start(), match.end()),
                "confidence": 0.7,
            }
        )
    return candidates[:12]


def _store_extracted_candidates(
    session: Session,
    *,
    lifecycle: MarketAssetLifecycle,
    filing: dict[str, Any],
    body_text: str,
    body_archive_path: str | None,
) -> int:
    created = 0
    for ordinal, extracted in enumerate(extract_terminal_value_candidates(body_text)):
        basis = f"body_extract_{ordinal}"
        evidence_key = _evidence_key(
            lifecycle.asset_key,
            filing["accession"],
            filing["document_name"],
            extracted["evidence_type"],
            basis,
        )
        candidate = session.get(MarketDelistingEvidenceCandidate, evidence_key)
        if candidate is None:
            candidate = MarketDelistingEvidenceCandidate(
                evidence_key=evidence_key,
                asset_key=lifecycle.asset_key,
                sec_cik=filing["cik"],
                accession_number=filing["accession"],
                document_name=filing["document_name"],
                form=filing["form"],
                filed_on=filing["filed_on"],
                source_url=filing["source_url"],
                evidence_type=extracted["evidence_type"],
                evidence_basis="filing_body_extract",
                candidate_value=extracted["candidate_value"],
                value_unit=extracted["value_unit"],
                evidence_excerpt=extracted["excerpt"][:1_500],
                confidence=extracted["confidence"],
                body_status="downloaded",
                review_status="candidate",
                raw_archive_path=body_archive_path,
            )
            session.add(candidate)
            created += 1
    return created


def review_evidence_candidate(
    session: Session,
    *,
    evidence_key: str,
    decision: str,
    review_role: str | None = None,
    review_note: str,
    now: datetime | None = None,
) -> MarketDelistingEvidenceCandidate:
    """Record a review signal without silently writing a terminal return."""
    if decision not in {"accepted", "rejected", "needs_more_evidence"}:
        raise ValueError("unsupported evidence review decision")
    candidate = session.get(MarketDelistingEvidenceCandidate, evidence_key)
    if candidate is None:
        raise ValueError("evidence candidate was not found")
    if len(review_note.strip()) < 10:
        raise ValueError("review note must explain the decision")
    if review_role not in {None, "terminal_outcome", "supporting_evidence"}:
        raise ValueError("unsupported evidence review role")
    if decision == "accepted":
        assigned_role = review_role or "supporting_evidence"
        if assigned_role == "terminal_outcome":
            if candidate.evidence_basis not in {
                "filing_body_extract",
                "human_primary_source_extract",
            }:
                raise ValueError("terminal evidence must be extracted from the filing body")
            if candidate.form not in {"8-K", "6-K", "20-F"}:
                raise ValueError("terminal evidence requires a reviewed issuer filing")
            if candidate.evidence_type not in {
                "cash_consideration_per_share",
                "share_exchange_ratio",
                "zero_recovery_per_share",
                "liquidation_distribution_per_share",
                "adr_cash_distribution_per_share",
            }:
                raise ValueError("this evidence type cannot establish a terminal outcome")
        candidate.review_role = assigned_role
    else:
        candidate.review_role = None
    candidate.review_status = decision
    candidate.review_note = review_note.strip()[:2_000]
    candidate.reviewed_at = now or datetime.now(UTC)
    session.flush()
    return candidate


def ingest_supplemental_evidence(
    session: Session,
    *,
    asset_key: str,
    accession_number: str,
    form: str,
    filed_on: date,
    source_url: str,
    evidence_type: str,
    candidate_value: float,
    value_unit: str,
    evidence_excerpt: str,
    confidence: float,
    observed_on: date | None = None,
    subject_symbol: str | None = None,
    subject_sec_cik: str | None = None,
) -> MarketDelistingEvidenceCandidate:
    """Store a reviewer extract from an SEC completion exhibit with an audit trail."""
    state = session.get(MarketDelistingEvidenceState, asset_key)
    if state is None or state.sec_cik is None:
        raise ValueError("SEC company identity must be resolved before supplemental evidence")
    normalized_url = source_url.strip()
    if not normalized_url.startswith("https://www.sec.gov/Archives/edgar/data/"):
        raise ValueError("supplemental evidence must cite an SEC Archives URL")
    normalized_accession = accession_number.strip()
    if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", normalized_accession):
        raise ValueError("invalid SEC accession number")
    normalized_excerpt = " ".join(evidence_excerpt.split())
    if len(normalized_excerpt) < 40:
        raise ValueError("supplemental evidence excerpt is too short")
    if evidence_type == "cash_consideration_per_share" and value_unit != "USD_per_share":
        raise ValueError("cash consideration must use USD_per_share")
    if evidence_type == "share_exchange_ratio" and value_unit != "acquirer_shares_per_share":
        raise ValueError("share exchange evidence must use acquirer_shares_per_share")
    if evidence_type in {
        "zero_recovery_per_share",
        "liquidation_distribution_per_share",
        "adr_cash_distribution_per_share",
    } and value_unit != "USD_per_share":
        raise ValueError("shareholder distribution evidence must use USD_per_share")
    if evidence_type == "zero_recovery_per_share" and candidate_value != 0:
        raise ValueError("zero-recovery evidence must have a value of zero")
    if evidence_type != "zero_recovery_per_share" and candidate_value <= 0:
        raise ValueError("non-zero terminal evidence must have a positive value")
    normalized_subject_symbol = (subject_symbol or "").strip().upper() or None
    normalized_subject_cik = (
        str(subject_sec_cik).strip().zfill(10) if subject_sec_cik else None
    )
    if evidence_type == "acquirer_closing_price":
        if value_unit != "USD_per_acquirer_share":
            raise ValueError("acquirer price must use USD_per_acquirer_share")
        if observed_on is None or observed_on > filed_on:
            raise ValueError("acquirer price requires an observation date on or before filing")
        if normalized_subject_symbol is None or normalized_subject_cik is None:
            raise ValueError("acquirer symbol and SEC CIK are required")
        cik_path = str(int(normalized_subject_cik))
        if f"/edgar/data/{cik_path}/" not in normalized_url:
            raise ValueError("SEC source URL does not match the acquirer CIK")
    elif normalized_subject_symbol is not None or normalized_subject_cik is not None:
        raise ValueError("counterparty subject fields are only valid for acquirer prices")
    identity = "|".join(
        (
            asset_key,
            normalized_accession,
            normalized_url,
            evidence_type,
            f"{candidate_value:.12g}",
            observed_on.isoformat() if observed_on else "not_observed",
            normalized_subject_symbol or "asset",
            normalized_subject_cik or state.sec_cik,
            normalized_excerpt,
        )
    )
    evidence_key = hashlib.sha256(identity.encode()).hexdigest()
    existing = session.get(MarketDelistingEvidenceCandidate, evidence_key)
    if existing is not None:
        return existing
    candidate = MarketDelistingEvidenceCandidate(
        evidence_key=evidence_key,
        asset_key=asset_key,
        sec_cik=state.sec_cik,
        accession_number=normalized_accession,
        subject_symbol=normalized_subject_symbol,
        subject_sec_cik=normalized_subject_cik,
        document_name=normalized_url.rsplit("/", 1)[-1][:255],
        form=form,
        filed_on=filed_on,
        observed_on=observed_on,
        source_url=normalized_url,
        evidence_type=evidence_type,
        evidence_basis="human_primary_source_extract",
        candidate_value=candidate_value,
        value_unit=value_unit,
        evidence_excerpt=normalized_excerpt[:2_000],
        confidence=confidence,
        body_status="human_verified",
        review_status="candidate",
    )
    session.add(candidate)
    state.extracted_candidate_count += 1
    session.flush()
    return candidate


def market_delisting_evidence_coverage(session: Session) -> dict[str, int]:
    """Return measured SEC discovery and human-review coverage."""
    state_counts = {
        str(status): int(count)
        for status, count in session.execute(
            select(MarketDelistingEvidenceState.status, func.count()).group_by(
                MarketDelistingEvidenceState.status
            )
        )
    }
    candidate_count = int(
        session.scalar(select(func.count()).select_from(MarketDelistingEvidenceCandidate)) or 0
    )
    value_evidence_bases = (
        "filing_body_extract",
        "human_primary_source_extract",
    )
    extracted_count = int(
        session.scalar(
            select(func.count())
            .select_from(MarketDelistingEvidenceCandidate)
            .where(MarketDelistingEvidenceCandidate.evidence_basis.in_(value_evidence_bases))
        )
        or 0
    )
    review_ready = int(
        session.scalar(
            select(func.count())
            .select_from(MarketDelistingEvidenceCandidate)
            .where(
                MarketDelistingEvidenceCandidate.evidence_basis.in_(value_evidence_bases),
                MarketDelistingEvidenceCandidate.review_status == "candidate",
            )
        )
        or 0
    )
    terminal_accepted = int(
        session.scalar(
            select(func.count())
            .select_from(MarketDelistingEvidenceCandidate)
            .where(
                MarketDelistingEvidenceCandidate.review_status == "accepted",
                MarketDelistingEvidenceCandidate.review_role == "terminal_outcome",
            )
        )
        or 0
    )
    supporting_accepted = int(
        session.scalar(
            select(func.count())
            .select_from(MarketDelistingEvidenceCandidate)
            .where(
                MarketDelistingEvidenceCandidate.review_status == "accepted",
                MarketDelistingEvidenceCandidate.review_role == "supporting_evidence",
            )
        )
        or 0
    )
    needs_more = int(
        session.scalar(
            select(func.count())
            .select_from(MarketDelistingEvidenceCandidate)
            .where(
                MarketDelistingEvidenceCandidate.review_status == "needs_more_evidence"
            )
        )
        or 0
    )
    body_contact_required = int(
        session.scalar(
            select(func.count())
            .select_from(MarketDelistingEvidenceState)
            .where(
                MarketDelistingEvidenceState.body_access_status == "contact_required",
                MarketDelistingEvidenceState.filing_count > 0,
            )
        )
        or 0
    )
    lifecycle_segmented = int(
        session.scalar(
            select(func.count())
            .select_from(MarketPriceBackfillState)
            .where(MarketPriceBackfillState.lifecycle_segmented_at.is_not(None))
        )
        or 0
    )
    return {
        "evidence_assets_searched": sum(state_counts.values()),
        "evidence_assets_cik_resolved": int(
            session.scalar(
                select(func.count())
                .select_from(MarketDelistingEvidenceState)
                .where(MarketDelistingEvidenceState.sec_cik.is_not(None))
            )
            or 0
        ),
        "evidence_metadata_candidates": candidate_count - extracted_count,
        "evidence_value_candidates": extracted_count,
        "evidence_review_ready": review_ready,
        "evidence_terminal_accepted": terminal_accepted,
        "evidence_supporting_accepted": supporting_accepted,
        "evidence_needs_more": needs_more,
        "evidence_lifecycle_segmented_assets": lifecycle_segmented,
        "evidence_body_contact_required_assets": body_contact_required,
        "evidence_provider_error_assets": state_counts.get("provider_error", 0),
        "evidence_lifecycle_conflict_assets": state_counts.get(
            "lifecycle_conflict_ticker_reuse", 0
        ),
    }


def _terminal_lifecycle_conflict_date(
    hits: list[dict[str, Any]],
    *,
    cik: str,
    last_trade_date: date | None,
) -> date | None:
    """Require two SEC terminal signals before quarantining a later price series."""
    if last_trade_date is None:
        return None
    filings = [
        filing
        for hit in hits
        if (filing := _filing_from_hit(hit, cik)) is not None
    ]
    deregistration = [
        filing["filed_on"]
        for filing in filings
        if filing["form"] in {"25-NSE", "15-12B", "15-12G", "15F-12G"}
    ]
    transaction = [
        filing["filed_on"]
        for filing in filings
        if filing["form"] == "8-K" and "2.01" in filing["items"]
    ]
    if not deregistration:
        return None
    for terminal_date in sorted(deregistration):
        corroborated = any(
            abs((transaction_date - terminal_date).days) <= 60
            for transaction_date in transaction
        ) or any(
            other != terminal_date and abs((other - terminal_date).days) <= 60
            for other in deregistration
        )
        if corroborated and last_trade_date > terminal_date + timedelta(days=45):
            return terminal_date
    return None


def _ensure_state(
    session: Session,
    asset_key: str,
    state: MarketDelistingEvidenceState | None,
) -> MarketDelistingEvidenceState:
    if state is not None:
        return state
    state = MarketDelistingEvidenceState(
        asset_key=asset_key,
        status="pending",
        attempt_count=0,
        filing_count=0,
        extracted_candidate_count=0,
        body_access_status="contact_required",
    )
    session.add(state)
    return state


def _archive_search_payload(
    archive: ColdArchive,
    *,
    asset_key: str,
    fetched_on: date,
    payload: dict[str, Any],
) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    digest_input = asset_key + "|" + hashlib.sha256(encoded).hexdigest()
    digest = hashlib.sha256(digest_input.encode()).hexdigest()
    relative = (
        f"raw/sec/delisting-evidence/{fetched_on:%Y/%m/%d}/search/{digest}.json.gz"
    )
    return archive.store_bytes(relative, gzip.compress(encoded, compresslevel=6, mtime=0))


def _evidence_key(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _clean_sec_display_name(value: str) -> str:
    return re.sub(r"\s*\([^)]*(?:CIK|[A-Z]{1,8})[^)]*\)\s*", " ", value).strip()


def _name_similarity(left: str, right: str) -> float:
    left_tokens = _name_tokens(left)
    right_tokens = _name_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    jaccard = intersection / union if union else 0.0
    sequence = SequenceMatcher(
        None,
        " ".join(sorted(left_tokens)),
        " ".join(sorted(right_tokens)),
    ).ratio()
    return max(jaccard, sequence)


def _name_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.casefold())
        if token not in LEGAL_NAME_TOKENS
    }


def _html_to_text(value: str) -> str:
    without_scripts = re.sub(
        r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>",
        " ",
        value,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", without_scripts))).strip()


def _context(text: str, start: int, end: int, radius: int = 260) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)].strip()
