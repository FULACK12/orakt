"""Bounded SEC acceptance-time backfill; never equate acceptance with earnings release.

Raw API responses are content-addressed on cold storage. Timestamps without an
explicit offset remain unknown. Each API payload version is append-only. Neither
an SEC acceptance clock nor today's copy alone certifies historical availability
of an issuer's earlier press release or a mutable news page.
"""

import argparse
import asyncio
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import CompanyFiling, CompanyProfile, FilingTimingObservation
from app.db.session import get_session_factory


def parse_accepted_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value
    ):
        return None
    try:
        return datetime.fromisoformat(value).astimezone(UTC)
    except ValueError:
        return None


def archive_response(root: Path, content: bytes) -> tuple[str, str]:
    digest = hashlib.sha256(content).hexdigest()
    relative = Path("raw/sec/submission-timing") / f"{digest}.json"
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as output:
            output.write(content)
    except FileExistsError:
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("archive_integrity_error") from None
    return relative.as_posix(), digest


def retain_observations(
    session: Session,
    *,
    ticker: str,
    content: bytes,
    source_url: str,
    cold_root: Path,
    observed_at: datetime,
) -> dict:
    if observed_at.tzinfo is None:
        raise ValueError("aware_observation_clock_required")
    payload = json.loads(content)
    columns = payload.get("filings", {}).get("recent", payload)
    accessions = columns.get("accessionNumber")
    timestamps = columns.get("acceptanceDateTime", [])
    if not isinstance(accessions, list) or not isinstance(timestamps, list):
        raise ValueError("invalid_sec_columns")
    archive_path, digest = archive_response(cold_root, content)
    retained = set(
        session.scalars(
            select(CompanyFiling.accession_number).where(
                CompanyFiling.ticker == ticker,
            )
        )
    )
    insert = sqlite_insert if session.get_bind().dialect.name == "sqlite" else pg_insert
    result = {
        "ticker": ticker,
        "inserted": 0,
        "valid_observations": 0,
        "missing_or_invalid": 0,
        "not_in_local_filings": 0,
    }
    for i, accession in enumerate(accessions):
        if not isinstance(accession, str) or accession not in retained:
            result["not_in_local_filings"] += 1
            continue
        raw = timestamps[i] if i < len(timestamps) else None
        accepted = parse_accepted_at(raw)
        status = "valid" if accepted else "missing_or_invalid"
        if accepted and accepted > observed_at:
            accepted, status = None, "future_timestamp"
        result["valid_observations" if accepted else "missing_or_invalid"] += 1
        statement = (
            insert(FilingTimingObservation)
            .values(
                accession_number=accession,
                accepted_at=accepted,
                raw_timestamp=raw if isinstance(raw, str) and len(raw) <= 128 else None,
                timestamp_status=status,
                source_url=source_url,
                payload_sha256=digest,
                archive_path=archive_path,
                observed_at=observed_at,
            )
            .on_conflict_do_nothing(index_elements=["accession_number", "payload_sha256"])
            .returning(FilingTimingObservation.id)
        )
        # Some psycopg/SQLAlchemy combinations report rowcount=-1. RETURNING
        # distinguishes a new row from ON CONFLICT without guessed counters.
        result["inserted"] += int(session.execute(statement).scalar_one_or_none() is not None)
    return result


async def backfill(tickers: list[str], historical_files: int) -> dict:
    settings = get_settings()
    user_agent = settings.sec_user_agent
    if settings.sec_contact_email:
        user_agent += " " + settings.sec_contact_email.get_secret_value()
    results, errors = [], []
    async with httpx.AsyncClient(timeout=60, headers={"User-Agent": user_agent}) as client:
        for ticker in tickers:
            pending_results = []
            try:
                with get_session_factory()() as session:
                    profile = session.get(CompanyProfile, ticker)
                    if profile is None or not re.fullmatch(r"\d{10}", profile.cik):
                        raise ValueError("unknown_ticker_or_cik")
                    url = f"https://data.sec.gov/submissions/CIK{profile.cik}.json"
                    response = await client.get(url)
                    response.raise_for_status()
                    observed = datetime.now(UTC)
                    pending_results.append(
                        retain_observations(
                            session,
                            ticker=ticker,
                            content=response.content,
                            source_url=url,
                            cold_root=settings.cold_data_root,
                            observed_at=observed,
                        )
                    )
                    files = response.json().get("filings", {}).get("files", [])
                    for entry in files[:historical_files]:
                        name = entry.get("name", "")
                        if not re.fullmatch(r"CIK\d{10}-submissions-\d{3}\.json", name):
                            raise ValueError("unexpected_history_filename")
                        await asyncio.sleep(0.25)
                        history_url = f"https://data.sec.gov/submissions/{name}"
                        history = await client.get(history_url)
                        history.raise_for_status()
                        pending_results.append(
                            retain_observations(
                                session,
                                ticker=ticker,
                                content=history.content,
                                source_url=history_url,
                                cold_root=settings.cold_data_root,
                                observed_at=datetime.now(UTC),
                            )
                        )
                    session.commit()
                    results.extend(pending_results)
            except (httpx.HTTPError, ValueError) as exc:
                # Do not echo request headers or source payloads.
                errors.append({"ticker": ticker, "error": type(exc).__name__})
            await asyncio.sleep(0.25)
    return {"results": results, "errors": errors, "earnings_release_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", action="append", required=True)
    parser.add_argument("--historical-files", type=int, default=0)
    args = parser.parse_args()
    tickers = list(dict.fromkeys(t.upper().strip() for t in args.ticker))
    if len(tickers) > 10 or not 0 <= args.historical_files <= 5:
        parser.error("maximum 10 tickers and 5 historical files per ticker")
    result = asyncio.run(backfill(tickers, args.historical_files))
    print(json.dumps(result, indent=2))
    return 2 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
