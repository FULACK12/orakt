"""Archive and parse official SEC Form 4 ownership XML filings."""

from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, delete, desc, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    CompanyFiling,
    CompanyInsiderFilingState,
    CompanyInsiderTransaction,
)
from app.storage.archive import ColdArchive

FORM4_PARSER_VERSION = "sec_form4_xml_v1"
FORM4_FORMS = ("4", "4/A")
MAX_FORM4_BYTES = 2_000_000
EQUIVALENT_ISSUER_TICKERS = {
    "BRK.B": {"BRK.A", "BRK.B", "BRKA", "BRKB"},
    "GOOGL": {"GOOG", "GOOGL"},
}


class NonTargetIssuerError(ValueError):
    """The submitter CIK filed Form 4 for a different public issuer."""


class InsiderSyncResult(BaseModel):
    """Bounded summary for one restart-safe synchronization pass."""

    model_config = ConfigDict(extra="forbid")

    filings_selected: int = Field(ge=0)
    filings_completed: int = Field(ge=0)
    filings_ignored: int = Field(default=0, ge=0)
    filings_failed: int = Field(ge=0)
    transactions_upserted: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)
    ignored_reasons: list[str] = Field(default_factory=list)


async def sync_sec_form4_filings(
    session: Session,
    *,
    client: httpx.AsyncClient,
    archive: ColdArchive,
    tickers: set[str] | None = None,
    batch_size: int = 50,
    request_interval_seconds: float = 0.15,
    max_attempts: int = 3,
) -> InsiderSyncResult:
    """Download and parse the next Form 4 filings, newest first."""
    if not 1 <= batch_size <= 200:
        raise ValueError("batch_size must be between one and two hundred")
    if request_interval_seconds < 0:
        raise ValueError("request_interval_seconds cannot be negative")
    selected_tickers = {
        ticker.strip().upper() for ticker in (tickers or set()) if ticker.strip()
    }
    _reconcile_legacy_ticker_mismatches(session)
    eligible_state = or_(
        CompanyInsiderFilingState.accession_number.is_(None),
        and_(
            CompanyInsiderFilingState.status == "completed",
            or_(
                CompanyInsiderFilingState.parser_version.is_(None),
                CompanyInsiderFilingState.parser_version != FORM4_PARSER_VERSION,
            ),
        ),
        CompanyInsiderFilingState.status.in_(("pending", "downloading", "parsing")),
        and_(
            CompanyInsiderFilingState.status == "failed",
            CompanyInsiderFilingState.attempt_count < max_attempts,
        ),
    )
    statement = (
        select(CompanyFiling)
        .outerjoin(
            CompanyInsiderFilingState,
            CompanyInsiderFilingState.accession_number
            == CompanyFiling.accession_number,
        )
        .where(CompanyFiling.form.in_(FORM4_FORMS), eligible_state)
        .order_by(desc(CompanyFiling.filed_at), desc(CompanyFiling.accession_number))
        .limit(batch_size)
    )
    if selected_tickers:
        statement = statement.where(CompanyFiling.ticker.in_(selected_tickers))
    filings = list(session.scalars(statement))
    completed = 0
    ignored = 0
    failed = 0
    transactions = 0
    errors: list[str] = []
    ignored_reasons: list[str] = []
    for index, filing in enumerate(filings):
        if index and request_interval_seconds:
            await asyncio.sleep(request_interval_seconds)
        state_before = session.get(
            CompanyInsiderFilingState,
            filing.accession_number,
        )
        attempt_before = state_before.attempt_count if state_before is not None else 0
        try:
            transaction_count = await _sync_one_filing(
                session,
                client=client,
                archive=archive,
                filing=filing,
            )
            completed += 1
            transactions += transaction_count
        except NonTargetIssuerError as exc:
            session.rollback()
            state = session.get(
                CompanyInsiderFilingState,
                filing.accession_number,
            )
            if state is None:
                state = CompanyInsiderFilingState(
                    accession_number=filing.accession_number,
                    ticker=filing.ticker,
                    source_url=_failure_source_url(filing.source_url),
                    status="ignored",
                    raw_bytes=0,
                    transactions_upserted=0,
                    attempt_count=attempt_before + 1,
                )
                session.add(state)
            else:
                state.status = "ignored"
            state.parser_version = FORM4_PARSER_VERSION
            state.last_error = f"{type(exc).__name__}: {str(exc)[:1_800]}"
            session.commit()
            ignored += 1
            ignored_reasons.append(f"{filing.accession_number}: {state.last_error}")
        except Exception as exc:
            session.rollback()
            state = session.get(
                CompanyInsiderFilingState,
                filing.accession_number,
            )
            if state is None:
                state = CompanyInsiderFilingState(
                    accession_number=filing.accession_number,
                    ticker=filing.ticker,
                    source_url=_failure_source_url(filing.source_url),
                    status="failed",
                    raw_bytes=0,
                    transactions_upserted=0,
                    attempt_count=1,
                )
                session.add(state)
            else:
                state.status = "failed"
                if state.attempt_count <= attempt_before:
                    state.attempt_count = attempt_before + 1
            state.last_error = f"{type(exc).__name__}: {str(exc)[:1_800]}"
            session.commit()
            failed += 1
            errors.append(f"{filing.accession_number}: {state.last_error}")
    return InsiderSyncResult(
        filings_selected=len(filings),
        filings_completed=completed,
        filings_ignored=ignored,
        filings_failed=failed,
        transactions_upserted=transactions,
        errors=errors,
        ignored_reasons=ignored_reasons,
    )


def _reconcile_legacy_ticker_mismatches(session: Session) -> None:
    """Upgrade mismatch failures created before non-target issuers were explicit."""
    states = list(
        session.scalars(
            select(CompanyInsiderFilingState).where(
                CompanyInsiderFilingState.status.in_(("failed", "ignored")),
                CompanyInsiderFilingState.last_error.ilike(
                    "%ownership XML ticker mismatch:%"
                ),
            )
        )
    )
    changed = False
    for state in states:
        match = re.search(
            r"ticker mismatch:\s*(\S+)\s*!=\s*(\S+)",
            state.last_error or "",
            flags=re.IGNORECASE,
        )
        if match is None:
            continue
        issuer_ticker = match.group(1)
        if _issuer_ticker_matches(state.ticker, issuer_ticker):
            state.status = "pending"
            state.attempt_count = 0
            state.parser_version = None
            state.last_error = "Retrying equivalent issuer share class"
            changed = True
        elif state.status == "failed":
            state.status = "ignored"
            state.parser_version = FORM4_PARSER_VERSION
            changed = True
    if changed:
        session.commit()


def _issuer_ticker_matches(expected_ticker: str, issuer_ticker: str) -> bool:
    expected = expected_ticker.upper().replace("-", ".")
    issuer = issuer_ticker.upper().replace("-", ".")
    return issuer in EQUIVALENT_ISSUER_TICKERS.get(expected, {expected})


def _failure_source_url(source_url: str) -> str:
    """Return the best traceable URL without masking the original failure."""
    try:
        return _raw_ownership_url(source_url)
    except ValueError:
        return source_url


async def _sync_one_filing(
    session: Session,
    *,
    client: httpx.AsyncClient,
    archive: ColdArchive,
    filing: CompanyFiling,
) -> int:
    raw_url = _raw_ownership_url(filing.source_url)
    relative_path = _raw_archive_path(filing)
    state = session.get(CompanyInsiderFilingState, filing.accession_number)
    if state is None:
        state = CompanyInsiderFilingState(
            accession_number=filing.accession_number,
            ticker=filing.ticker,
            source_url=raw_url,
            status="pending",
            raw_bytes=0,
            transactions_upserted=0,
            attempt_count=0,
        )
        session.add(state)
    state.source_url = raw_url
    state.status = "downloading"
    state.attempt_count += 1
    state.last_started_at = datetime.now(UTC)
    state.last_error = None
    session.commit()

    archived_path = archive.root / relative_path
    if archived_path.is_file():
        payload = archived_path.read_bytes()
    else:
        response = await client.get(raw_url)
        response.raise_for_status()
        payload = response.content
    if not payload or len(payload) > MAX_FORM4_BYTES:
        raise ValueError(f"ownership XML size is outside the allowed range: {len(payload)}")
    parsed = parse_form4_xml(
        payload,
        ticker=filing.ticker,
        accession_number=filing.accession_number,
        form=filing.form,
        filed_at=filing.filed_at,
        source_url=raw_url,
    )
    raw_sha256 = hashlib.sha256(payload).hexdigest()
    stored_path = archive.store_bytes(relative_path, payload)

    state = session.get(CompanyInsiderFilingState, filing.accession_number) or state
    state.status = "parsing"
    state.raw_archive_path = stored_path
    state.raw_sha256 = raw_sha256
    state.raw_bytes = len(payload)
    session.commit()

    session.execute(
        delete(CompanyInsiderTransaction).where(
            CompanyInsiderTransaction.accession_number == filing.accession_number
        )
    )
    session.add_all(CompanyInsiderTransaction(**item) for item in parsed)
    state = session.get(CompanyInsiderFilingState, filing.accession_number) or state
    state.transactions_upserted = len(parsed)
    state.parser_version = FORM4_PARSER_VERSION
    state.status = "completed"
    state.last_success_at = datetime.now(UTC)
    state.last_error = None
    session.commit()
    return len(parsed)


def parse_form4_xml(
    payload: bytes,
    *,
    ticker: str,
    accession_number: str,
    form: str,
    filed_at: date,
    source_url: str,
) -> list[dict[str, Any]]:
    """Extract non-derivative and derivative transaction rows from ownership XML."""
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise ValueError("SEC ownership document is not valid XML") from exc
    if _local_name(root.tag) != "ownershipDocument":
        raise ValueError("SEC document root is not ownershipDocument")
    document_type = _nested_text(root, "documentType")
    if document_type not in FORM4_FORMS:
        raise ValueError(f"SEC ownership document type is not Form 4: {document_type}")
    issuer_ticker = (_nested_text(root, "issuer", "issuerTradingSymbol") or "").upper()
    if issuer_ticker and not _issuer_ticker_matches(ticker, issuer_ticker):
        raise NonTargetIssuerError(
            f"ownership XML ticker mismatch: {issuer_ticker} != {ticker}"
        )

    owners = _reporting_owners(root)
    remarks = _nested_text(root, "remarks")
    footnotes = _footnote_map(root)
    root_10b5 = _truthy(_nested_text(root, "aff10b5One"))
    rows: list[dict[str, Any]] = []
    tables = (
        ("non_derivative", "nonDerivativeTable", "nonDerivativeTransaction"),
        ("derivative", "derivativeTable", "derivativeTransaction"),
    )
    for transaction_kind, table_name, row_name in tables:
        table = _child(root, table_name)
        transactions = [] if table is None else _children(table, row_name)
        for transaction_index, transaction in enumerate(transactions):
            referenced_footnotes = _referenced_footnotes(transaction, footnotes)
            footnote_text = "\n".join(referenced_footnotes) or None
            combined_notes = " ".join(
                value for value in (footnote_text, remarks) if value
            ).casefold()
            rows.append(
                {
                    "ticker": ticker.upper(),
                    "accession_number": accession_number,
                    "form": form,
                    "filed_at": filed_at,
                    "transaction_kind": transaction_kind,
                    "transaction_index": transaction_index,
                    "transaction_date": _parse_date(
                        _nested_text(transaction, "transactionDate")
                    ),
                    "deemed_execution_date": _parse_date(
                        _nested_text(transaction, "deemedExecutionDate")
                    ),
                    "security_title": (
                        _nested_text(transaction, "securityTitle") or "Unknown security"
                    )[:255],
                    "transaction_code": (
                        _nested_text(transaction, "transactionCoding", "transactionCode")
                        or None
                    ),
                    "acquired_disposed": (
                        _nested_text(
                            transaction,
                            "transactionAmounts",
                            "transactionAcquiredDisposedCode",
                        )
                        or None
                    ),
                    "shares": _parse_number(
                        _nested_text(
                            transaction,
                            "transactionAmounts",
                            "transactionShares",
                        )
                    ),
                    "price_per_share": _parse_number(
                        _nested_text(
                            transaction,
                            "transactionAmounts",
                            "transactionPricePerShare",
                        )
                    ),
                    "shares_owned_following": _parse_number(
                        _nested_text(
                            transaction,
                            "postTransactionAmounts",
                            (
                                "sharesOwnedFollowingTransaction"
                                if transaction_kind == "non_derivative"
                                else "valueOwnedFollowingTransaction"
                            ),
                        )
                    ),
                    "direct_or_indirect": (
                        _nested_text(
                            transaction,
                            "ownershipNature",
                            "directOrIndirectOwnership",
                        )
                        or None
                    ),
                    "ownership_nature": (
                        _nested_text(
                            transaction,
                            "ownershipNature",
                            "natureOfOwnership",
                        )
                        or None
                    ),
                    "derivative_exercise_price": _parse_number(
                        _nested_text(transaction, "conversionOrExercisePrice")
                    ),
                    "derivative_exercise_date": _parse_date(
                        _nested_text(transaction, "exerciseDate")
                    ),
                    "derivative_expiration_date": _parse_date(
                        _nested_text(transaction, "expirationDate")
                    ),
                    "underlying_security_title": (
                        _nested_text(
                            transaction,
                            "underlyingSecurity",
                            "underlyingSecurityTitle",
                        )
                        or None
                    ),
                    "underlying_shares": _parse_number(
                        _nested_text(
                            transaction,
                            "underlyingSecurity",
                            "underlyingSecurityShares",
                        )
                    ),
                    "equity_swap_involved": _truthy(
                        _nested_text(
                            transaction,
                            "transactionCoding",
                            "equitySwapInvolved",
                        )
                    ),
                    "is_10b5_1": root_10b5 or "10b5-1" in combined_notes,
                    "reporting_owners": owners,
                    "footnote_text": footnote_text,
                    "remarks": remarks,
                    "source_url": source_url,
                }
            )
    return rows


def build_insider_evidence(
    session: Session,
    *,
    ticker: str,
    as_of: date,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Return recent point-in-time Form 4 facts without inferring insider intent."""
    rows = list(
        session.scalars(
            select(CompanyInsiderTransaction)
            .where(
                CompanyInsiderTransaction.ticker == ticker.upper(),
                CompanyInsiderTransaction.filed_at <= as_of,
                or_(
                    CompanyInsiderTransaction.transaction_date.is_(None),
                    CompanyInsiderTransaction.transaction_date <= as_of,
                ),
            )
            .order_by(
                desc(CompanyInsiderTransaction.transaction_date),
                desc(CompanyInsiderTransaction.filed_at),
                desc(CompanyInsiderTransaction.id),
            )
            .limit(limit)
        )
    )
    accessions = {row.accession_number for row in rows}
    related_rows = (
        list(
            session.scalars(
                select(CompanyInsiderTransaction).where(
                    CompanyInsiderTransaction.accession_number.in_(accessions)
                )
            )
        )
        if accessions
        else []
    )
    transaction_groups: dict[tuple[str, date | None], list[CompanyInsiderTransaction]] = {}
    for related in related_rows:
        transaction_groups.setdefault(
            (related.accession_number, related.transaction_date),
            [],
        ).append(related)
    evidence: list[dict[str, Any]] = []
    for row in rows:
        group = transaction_groups.get(
            (row.accession_number, row.transaction_date),
            [row],
        )
        paired_conversion_legs = (
            row.transaction_code in {"C", "M"}
            and any(
                item.transaction_code == row.transaction_code
                and item.transaction_kind != row.transaction_kind
                for item in group
            )
        )
        open_market_signal = row.transaction_code in {"P", "S"}
        gross_value = (
            row.shares * row.price_per_share
            if row.shares is not None and row.price_per_share is not None
            else None
        )
        evidence.append(
            {
                "evidence_id": (
                    f"sec-form4:{row.ticker}:{row.accession_number}:"
                    f"{row.transaction_kind}:{row.transaction_index}"
                ),
                "category": "insider_transaction",
                "ticker": row.ticker,
                "form": row.form,
                "filed_at": row.filed_at.isoformat(),
                "transaction_date": (
                    row.transaction_date.isoformat() if row.transaction_date else None
                ),
                "transaction_kind": row.transaction_kind,
                "security_title": row.security_title,
                "transaction_code": row.transaction_code,
                "transaction_classification": _transaction_classification(
                    row.transaction_code
                ),
                "transaction_group_id": (
                    f"sec-form4-group:{row.ticker}:{row.accession_number}:"
                    f"{row.transaction_date.isoformat() if row.transaction_date else 'undated'}"
                ),
                "related_leg_count": len(group),
                "paired_derivative_and_nonderivative_legs": paired_conversion_legs,
                "market_signal_scope": (
                    "open_market_purchase_or_sale"
                    if open_market_signal
                    else "non_open_market_transaction_mechanics"
                ),
                "acquired_disposed": row.acquired_disposed,
                "shares": row.shares,
                "price_per_share": row.price_per_share,
                "gross_transaction_value_usd": gross_value,
                "shares_owned_following": row.shares_owned_following,
                "direct_or_indirect": row.direct_or_indirect,
                "is_10b5_1": row.is_10b5_1,
                "reporting_owners": row.reporting_owners,
                "source": "SEC Form 4 ownership XML",
                "source_url": row.source_url,
                "can_verify_transaction_details": True,
                "interpretation_guardrail": (
                    "This is one leg of a paired derivative conversion or exercise; "
                    "do not sum it with the related security leg as a second independent "
                    "economic trade."
                    if paired_conversion_legs
                    else (
                        "Only transaction codes P and S are treated as open-market "
                        "directional activity; awards, exercises, withholding and gifts "
                        "are disclosed mechanics, not independent buy/sell signals."
                    )
                ),
                "limitations": [
                    "Form 4 reports disclosed transactions, not the insider's motive or forecast.",
                    (
                        "Equity awards, option exercises, tax withholding and gifts are "
                        "not open-market trades."
                    ),
                    (
                        "A Rule 10b5-1 plan may have been adopted well before the "
                        "reported execution date."
                    ),
                ],
            }
        )
    return evidence


def insider_coverage(session: Session, *, ticker: str | None = None) -> dict[str, Any]:
    """Summarize parsed transaction and filing-state coverage."""
    transaction_filter = ()
    state_filter = ()
    if ticker:
        transaction_filter = (CompanyInsiderTransaction.ticker == ticker.upper(),)
        state_filter = (CompanyInsiderFilingState.ticker == ticker.upper(),)
    count, start, end = session.execute(
        select(
            func.count(CompanyInsiderTransaction.id),
            func.min(CompanyInsiderTransaction.transaction_date),
            func.max(CompanyInsiderTransaction.transaction_date),
        ).where(*transaction_filter)
    ).one()
    completed = session.scalar(
        select(func.count())
        .select_from(CompanyInsiderFilingState)
        .where(CompanyInsiderFilingState.status == "completed", *state_filter)
    )
    failed = session.scalar(
        select(func.count())
        .select_from(CompanyInsiderFilingState)
        .where(CompanyInsiderFilingState.status == "failed", *state_filter)
    )
    return {
        "transaction_count": int(count or 0),
        "starts_at": start,
        "ends_at": end,
        "filings_completed": int(completed or 0),
        "filings_failed": int(failed or 0),
        "parser_version": FORM4_PARSER_VERSION,
    }


def _raw_ownership_url(source_url: str) -> str:
    parsed = urlsplit(source_url)
    path = re.sub(r"/xslF345X\d+/", "/", parsed.path, flags=re.IGNORECASE)
    if not path.casefold().endswith(".xml"):
        raise ValueError("Form 4 filing has no XML primary document")
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ""))


def _raw_archive_path(filing: CompanyFiling) -> str:
    filename = Path(urlsplit(_raw_ownership_url(filing.source_url)).path).name
    return (
        f"raw/sec/form4/{filing.ticker}/{filing.accession_number.replace('-', '')}/"
        f"{filename}"
    )


def _reporting_owners(root: ElementTree.Element) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for owner in _children(root, "reportingOwner"):
        relationship = _child(owner, "reportingOwnerRelationship")
        roles: list[str] = []
        role_fields = (
            ("isDirector", "director"),
            ("isOfficer", "officer"),
            ("isTenPercentOwner", "ten_percent_owner"),
            ("isOther", "other"),
        )
        for field, label in role_fields:
            if relationship is not None and _truthy(_nested_text(relationship, field)):
                roles.append(label)
        result.append(
            {
                "cik": _nested_text(owner, "reportingOwnerId", "rptOwnerCik"),
                "name": _nested_text(owner, "reportingOwnerId", "rptOwnerName"),
                "roles": roles,
                "officer_title": (
                    _nested_text(relationship, "officerTitle")
                    if relationship is not None
                    else None
                ),
                "other_text": (
                    _nested_text(relationship, "otherText")
                    if relationship is not None
                    else None
                ),
            }
        )
    return result


def _footnote_map(root: ElementTree.Element) -> dict[str, str]:
    footnotes = _child(root, "footnotes")
    if footnotes is None:
        return {}
    return {
        str(item.attrib.get("id") or ""): " ".join("".join(item.itertext()).split())
        for item in _children(footnotes, "footnote")
        if item.attrib.get("id")
    }


def _referenced_footnotes(
    transaction: ElementTree.Element,
    footnotes: dict[str, str],
) -> list[str]:
    references = []
    for element in transaction.iter():
        if _local_name(element.tag) != "footnoteId":
            continue
        reference = str(element.attrib.get("id") or (element.text or "")).strip()
        if reference and reference in footnotes:
            references.append(footnotes[reference])
    return list(dict.fromkeys(references))


def _transaction_classification(code: str | None) -> str:
    return {
        "P": "open_market_purchase",
        "S": "open_market_sale",
        "A": "grant_or_award",
        "M": "option_exercise_or_conversion",
        "F": "tax_or_exercise_price_withholding",
        "G": "gift",
        "C": "conversion",
        "D": "issuer_disposition",
        "J": "other",
    }.get((code or "").upper(), "unclassified")


def _nested_text(root: ElementTree.Element | None, *names: str) -> str | None:
    current = root
    for name in names:
        if current is None:
            return None
        current = _child(current, name)
    if current is None:
        return None
    value = _child(current, "value")
    selected = value if value is not None else current
    text = " ".join("".join(selected.itertext()).split())
    return text or None


def _child(root: ElementTree.Element, name: str) -> ElementTree.Element | None:
    return next((item for item in root if _local_name(item.tag) == name), None)


def _children(root: ElementTree.Element, name: str) -> list[ElementTree.Element]:
    return [item for item in root if _local_name(item.tag) == name]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_number(value: str | None) -> float | None:
    if not value:
        return None
    normalized = re.sub(r"[$,\s]", "", value)
    if normalized in {"", "-", "--"}:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for pattern in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value.strip(), pattern).date()
        except ValueError:
            continue
    return None


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "y", "x"}
