"""SEC filing discovery and terminal-value candidate safety tests."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    MarketAssetIdentifier,
    MarketAssetLifecycle,
    MarketDelistingEvidenceCandidate,
    MarketDelistingEvidenceState,
    MarketDelistingOutcome,
    MarketObservation,
    MarketPriceBackfillState,
    MarketSeries,
)
from app.market_delisting_evidence import (
    extract_terminal_value_candidates,
    ingest_supplemental_evidence,
    review_evidence_candidate,
    select_sec_cik,
    sync_sec_delisting_evidence,
)
from app.market_lifecycle_segmentation import (
    segment_price_series_from_terminal_evidence,
)
from app.storage.archive import ColdArchive


def _session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _seed_asset(session: Session, *, symbol: str = "SP") -> str:
    asset_key = f"av:test:{symbol}"
    session.add(
        MarketAssetLifecycle(
            asset_key=asset_key,
            provider_key="alpha_vantage_listing_status",
            symbol=symbol,
            name="SP Plus Corp",
            exchange="NASDAQ",
            asset_type="Stock",
            ipo_date=date(2004, 6, 2),
            delisting_date=date(2024, 5, 16),
            listing_status="delisted",
            snapshot_date=date(2026, 8, 24),
            fetched_at=datetime(2026, 8, 24, tzinfo=UTC),
            source_url="https://www.alphavantage.co/documentation/",
        )
    )
    session.add(
        MarketAssetIdentifier(
            asset_key=asset_key,
            identity_status="verified",
            mapping_method="test",
            figi="BBG000BJ91B1",
            composite_figi="BBG000BJ91B1",
            mapped_ticker=symbol,
            mapped_name="SP PLUS CORP",
            mapped_exchange="US",
            security_type="Common Stock",
            name_similarity=1.0,
            attempt_count=1,
        )
    )
    session.add(
        MarketDelistingOutcome(
            asset_key=asset_key,
            status="evidence_required",
            outcome_type="unknown",
            last_trade_date=date(2024, 5, 10),
            last_trade_price=53.99,
        )
    )
    session.commit()
    return asset_key


def _search_payload() -> dict[str, object]:
    return {
        "hits": {
            "total": {"value": 1, "relation": "eq"},
            "hits": [
                {
                    "_id": "0001193125-24-140235:d833024d8k.htm",
                    "_source": {
                        "ciks": ["0001059262"],
                        "display_names": [
                            "SP Plus Corp  (CRLKP)  (CIK 0001059262)"
                        ],
                        "form": "8-K",
                        "file_date": "2024-05-16",
                        "sequence": 1,
                        "items": ["2.01", "3.01", "5.01", "8.01", "9.01"],
                    },
                }
            ],
        }
    }


def test_sec_metadata_discovery_resolves_cik_but_never_verifies_return(
    tmp_path: Path,
) -> None:
    with next(_session()) as session:
        asset_key = _seed_asset(session)

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.host == "efts.sec.gov"
            return httpx.Response(200, json=_search_payload())

        async def synchronize() -> None:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                result = await sync_sec_delisting_evidence(
                    session,
                    client=client,
                    archive=ColdArchive(tmp_path, min_free_bytes=0, max_used_percent=99),
                    user_agent="NEWS-Map test research",
                    max_assets=1,
                    request_interval_seconds=0,
                    now=datetime(2026, 8, 24, tzinfo=UTC),
                )
            assert result.cik_resolved_assets == 1
            assert result.metadata_candidate_filings == 1
            assert result.extracted_value_candidates == 0
            assert result.body_contact_required_assets == 1

        asyncio.run(synchronize())
        session.commit()

        identity = session.get(MarketAssetIdentifier, asset_key)
        outcome = session.get(MarketDelistingOutcome, asset_key)
        state = session.get(MarketDelistingEvidenceState, asset_key)
        candidate = session.scalar(select(MarketDelistingEvidenceCandidate))
        assert identity is not None and identity.sec_cik == "0001059262"
        assert outcome is not None and outcome.status == "evidence_required"
        assert outcome.delisting_return is None
        assert state is not None
        assert state.status == "metadata_found_body_contact_required"
        assert candidate is not None
        assert candidate.evidence_type == "transaction_completion_filing"
        assert candidate.candidate_value is None
        assert candidate.body_status == "contact_required"
        assert len(list(tmp_path.rglob("*.json.gz"))) == 1


def test_full_text_extracts_candidates_and_review_does_not_write_outcome(
    tmp_path: Path,
) -> None:
    with next(_session()) as session:
        asset_key = _seed_asset(session)
        filing_html = """
        <html><body><p>At the effective time, each outstanding share was converted
        into the right to receive $54.00 in cash as merger consideration.</p>
        <p>The exchange ratio of 0.125 shares applies to the separate rollover award.</p>
        </body></html>
        """

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "efts.sec.gov":
                return httpx.Response(200, json=_search_payload())
            assert request.url.host == "www.sec.gov"
            assert "project@example.org" in request.headers["user-agent"]
            return httpx.Response(200, text=filing_html, headers={"content-type": "text/html"})

        async def synchronize() -> None:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                result = await sync_sec_delisting_evidence(
                    session,
                    client=client,
                    archive=ColdArchive(tmp_path, min_free_bytes=0, max_used_percent=99),
                    user_agent="NEWS-Map test research",
                    contact_email="project@example.org",
                    max_assets=1,
                    request_interval_seconds=0,
                    now=datetime(2026, 8, 24, tzinfo=UTC),
                )
            assert result.extracted_value_candidates == 2

        asyncio.run(synchronize())
        session.commit()
        extracted = list(
            session.scalars(
                select(MarketDelistingEvidenceCandidate).where(
                    MarketDelistingEvidenceCandidate.evidence_basis
                    == "filing_body_extract"
                )
            )
        )
        assert {item.evidence_type for item in extracted} == {
            "cash_consideration_per_share",
            "share_exchange_ratio",
        }
        cash = next(item for item in extracted if item.evidence_type.startswith("cash"))
        assert cash.candidate_value == 54.0
        review_evidence_candidate(
            session,
            evidence_key=cash.evidence_key,
            decision="accepted",
            review_role="terminal_outcome",
            review_note="Confirmed as the merger cash consideration in the cited filing.",
            now=datetime(2026, 8, 24, tzinfo=UTC),
        )
        assert cash.review_role == "terminal_outcome"
        outcome = session.get(MarketDelistingOutcome, asset_key)
        assert outcome is not None and outcome.status == "evidence_required"
        assert outcome.delisting_return is None
        assert len(list(tmp_path.rglob("*.html.gz"))) == 1


def test_extractor_rejects_unrelated_per_share_number() -> None:
    body = "Quarterly diluted earnings were $5.00 per share after higher revenue."
    assert extract_terminal_value_candidates(body) == []


def test_supplemental_sec_completion_evidence_requires_separate_review() -> None:
    with next(_session()) as session:
        asset_key = _seed_asset(session)
        session.add(
            MarketDelistingEvidenceState(
                asset_key=asset_key,
                status="metadata_found_no_value_extracted",
                sec_cik="0001059262",
                attempt_count=1,
                filing_count=1,
                extracted_candidate_count=0,
                body_access_status="downloaded",
            )
        )
        session.flush()
        candidate = ingest_supplemental_evidence(
            session,
            asset_key=asset_key,
            accession_number="0001193125-24-140235",
            form="8-K",
            filed_on=date(2024, 5, 16),
            source_url=(
                "https://www.sec.gov/Archives/edgar/data/1059262/"
                "000119312524140235/d833024d8k.htm"
            ),
            evidence_type="cash_consideration_per_share",
            candidate_value=54.0,
            value_unit="USD_per_share",
            evidence_excerpt=(
                "At the effective time each outstanding share was converted into "
                "the right to receive $54.00 per share in cash."
            ),
            confidence=0.97,
        )
        assert candidate.review_status == "candidate"
        assert candidate.evidence_basis == "human_primary_source_extract"
        review_evidence_candidate(
            session,
            evidence_key=candidate.evidence_key,
            decision="accepted",
            review_role="terminal_outcome",
            review_note="Confirmed against the cited SEC completion filing.",
        )
        assert candidate.review_role == "terminal_outcome"
        price_candidate = ingest_supplemental_evidence(
            session,
            asset_key=asset_key,
            accession_number="0001193125-26-057080",
            form="8-K/A",
            filed_on=date(2026, 2, 18),
            observed_on=date(2026, 2, 13),
            source_url=(
                "https://www.sec.gov/Archives/edgar/data/1481582/"
                "000119312526057080/d31485dex991.htm"
            ),
            evidence_type="acquirer_closing_price",
            candidate_value=27.03,
            value_unit="USD_per_acquirer_share",
            subject_symbol="RYI",
            subject_sec_cik="0001481582",
            evidence_excerpt=(
                "The purchase price was measured using the closing market price "
                "of Ryerson common stock of $27.03 on February 13, 2026."
            ),
            confidence=0.99,
        )
        review_evidence_candidate(
            session,
            evidence_key=price_candidate.evidence_key,
            decision="accepted",
            review_role="supporting_evidence",
            review_note="Confirmed against the Ryerson SEC 8-K/A exhibit.",
        )
        assert price_candidate.subject_symbol == "RYI"
        assert price_candidate.subject_sec_cik == "0001481582"
        assert price_candidate.observed_on == date(2026, 2, 13)


def test_extractor_rejects_par_value_and_financial_advisor_ranges() -> None:
    body = (
        "Each share of acquirer common stock, par value $0.01, will be issued as "
        "merger consideration. The financial advisor reviewed a range of $3.00 per "
        "share to $7.00 per share in its discounted cash flow analysis."
    )
    assert extract_terminal_value_candidates(body) == []


def test_extractor_separates_final_historical_and_implied_terms() -> None:
    body = (
        "Each outstanding share was converted into the right to receive $9.00 per "
        "share in cash as the Merger Consideration. An earlier draft proposed an "
        "offer price of $8.25 per share. Based on the exchange ratio, the implied "
        "per share merger consideration value was approximately $10.40 per share. "
        "The common stock had par value $0.01 per share and the offer was funded "
        "by $164 million of committed equity financing."
    )

    extracted = extract_terminal_value_candidates(body)

    assert {(item["evidence_type"], item["candidate_value"]) for item in extracted} == {
        ("cash_consideration_per_share", 9.0),
        ("historical_offer_per_share", 8.25),
        ("implied_stock_consideration_per_share", 10.4),
    }


def test_two_terminal_filings_quarantine_prices_that_continue_later(
    tmp_path: Path,
) -> None:
    with next(_session()) as session:
        asset_key = _seed_asset(session)
        outcome = session.get(MarketDelistingOutcome, asset_key)
        assert outcome is not None
        outcome.last_trade_date = date(2026, 8, 21)
        payload = _search_payload()
        payload["hits"]["hits"].append(  # type: ignore[index,union-attr]
            {
                "_id": "0001354457-24-000001:primary_doc.xml",
                "_source": {
                    "ciks": ["0001059262", "0001354457"],
                    "display_names": ["SP Plus Corp (CIK 0001059262)"],
                    "form": "25-NSE",
                    "file_date": "2024-05-16",
                    "sequence": 1,
                    "items": [],
                },
            }
        )

        async def synchronize() -> None:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
            ) as client:
                result = await sync_sec_delisting_evidence(
                    session,
                    client=client,
                    archive=ColdArchive(tmp_path, min_free_bytes=0, max_used_percent=99),
                    user_agent="NEWS-Map test research",
                    max_assets=1,
                    request_interval_seconds=0,
                    now=datetime(2026, 8, 24, tzinfo=UTC),
                )
            assert result.lifecycle_conflict_assets == 1

        asyncio.run(synchronize())
        session.commit()
        identity = session.get(MarketAssetIdentifier, asset_key)
        state = session.get(MarketDelistingEvidenceState, asset_key)
        assert identity is not None and identity.identity_status == "lifecycle_conflict"
        assert state is not None and state.status == "lifecycle_conflict_ticker_reuse"
        assert outcome.status == "identity_required"


def test_sec_cik_selection_rejects_two_equally_matching_entities() -> None:
    payload = _search_payload()
    hits = payload["hits"]["hits"]  # type: ignore[index]
    hits.append(  # type: ignore[union-attr]
        {
            "_id": "0000000000-24-000001:other.htm",
            "_source": {
                "ciks": ["0009999999"],
                "display_names": ["SP Plus Corp (CIK 0009999999)"],
                "form": "8-K",
                "file_date": "2024-05-17",
                "sequence": 1,
                "items": ["2.01"],
            },
        }
    )
    selection = select_sec_cik("SP Plus Corp", payload)
    assert selection.status == "cik_ambiguous"
    assert selection.cik is None


def test_reviewed_sec_completion_segments_raw_series_without_overwrite() -> None:
    with next(_session()) as session:
        asset_key = _seed_asset(session)
        raw_series_id = "HIST:SP:raw"
        session.add(
            MarketSeries(
                series_id=raw_series_id,
                name="SP Plus raw weekly adjusted close",
                category="historical_equity_price",
                unit="USD",
                frequency="weekly",
                source_name="Alpha Vantage weekly adjusted",
                source_url="https://www.alphavantage.co/documentation/",
                listing_status="delisted",
            )
        )
        start = date(2023, 1, 6)
        session.add_all(
            [
                MarketObservation(
                    series_id=raw_series_id,
                    observed_on=start + timedelta(weeks=index),
                    value=40 + index / 10,
                    fetched_at=datetime(2026, 8, 24, tzinfo=UTC),
                )
                for index in range(70)
            ]
            + [
                MarketObservation(
                    series_id=raw_series_id,
                    observed_on=date(2024, 5, 24) + timedelta(weeks=index),
                    value=46.9,
                    fetched_at=datetime(2026, 8, 24, tzinfo=UTC),
                )
                for index in range(3)
            ]
        )
        session.add(
            MarketPriceBackfillState(
                asset_key=asset_key,
                provider_key="alpha_vantage_weekly_adjusted",
                status="ticker_reused",
                priority_score=100,
                priority_reasons=["recent_delisting"],
                observations_upserted=73,
                observed_start=start,
                observed_end=date(2024, 6, 7),
                series_id=raw_series_id,
            )
        )
        identity = session.get(MarketAssetIdentifier, asset_key)
        assert identity is not None
        identity.identity_status = "lifecycle_conflict"
        identity.sec_cik = "0001059262"
        identity.last_error_code = "sec_terminal_event_before_price_end"
        session.add(
            MarketDelistingEvidenceState(
                asset_key=asset_key,
                status="lifecycle_conflict_ticker_reuse",
                sec_cik="0001059262",
                cik_name="SP Plus Corp",
                cik_name_similarity=1.0,
                attempt_count=1,
                filing_count=1,
                extracted_candidate_count=1,
                body_access_status="human_verified",
            )
        )
        evidence_key = "a" * 64
        session.add(
            MarketDelistingEvidenceCandidate(
                evidence_key=evidence_key,
                asset_key=asset_key,
                sec_cik="0001059262",
                accession_number="0001193125-24-140235",
                document_name="d833024d8k.htm",
                form="8-K",
                filed_on=date(2024, 5, 16),
                source_url=(
                    "https://www.sec.gov/Archives/edgar/data/1059262/"
                    "000119312524140235/d833024d8k.htm"
                ),
                evidence_type="cash_consideration_per_share",
                evidence_basis="human_primary_source_extract",
                candidate_value=54,
                value_unit="USD_per_share",
                evidence_excerpt="Each share converted to the right to receive $54 cash.",
                confidence=0.97,
                body_status="human_verified",
                review_status="accepted",
                review_role="terminal_outcome",
            )
        )
        session.flush()

        result = segment_price_series_from_terminal_evidence(
            session,
            asset_key=asset_key,
            evidence_key=evidence_key,
            now=datetime(2026, 8, 24, tzinfo=UTC),
        )

        assert result.source_series_id == raw_series_id
        assert result.retained_observations == 70
        assert result.excluded_observations == 3
        assert session.scalar(
            select(MarketObservation).where(
                MarketObservation.series_id == raw_series_id
            )
        ) is not None
        state = session.get(MarketPriceBackfillState, asset_key)
        assert state is not None
        assert state.source_series_id == raw_series_id
        assert state.series_id == result.segmented_series_id
        assert state.status == "synced"
        assert identity.identity_status == "verified"
        outcome = session.get(MarketDelistingOutcome, asset_key)
        assert outcome is not None
        assert outcome.last_trade_date == result.last_trade_date
        assert outcome.series_id == result.segmented_series_id
