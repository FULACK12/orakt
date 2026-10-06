"""Cross-source identity and delisting terminal-value audit tests."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    MarketAssetIdentifier,
    MarketAssetLifecycle,
    MarketDelistingEvidenceCandidate,
    MarketDelistingEvidenceState,
    MarketDelistingOutcome,
    MarketLifecycleResolution,
    MarketObservation,
    MarketPriceBackfillState,
    MarketSeries,
)
from app.market_identity import (
    materialize_delisting_outcomes,
    select_openfigi_identity,
    sync_openfigi_identities,
    verified_provider_history_series_ids,
    verify_delisting_outcome,
    verify_sec_primary_identity,
    verify_stock_delisting_outcome,
)
from app.market_terminal_outcomes import (
    finalize_multi_stage_outcome,
    record_lifecycle_resolution,
    record_terminal_cashflow,
)
from app.storage.archive import ColdArchive


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    engine.dispose()


def test_openfigi_mapping_requires_name_and_exchange_consistency(
    session: Session,
    tmp_path: Path,
) -> None:
    _priced_lifecycle(session, "GOOD", "Good Holdings Inc")
    _priced_lifecycle(session, "BAD", "Original Manufacturing Corp")
    _priced_lifecycle(session, "MISS", "Missing Identity Inc")
    session.flush()

    def handler(request: httpx.Request) -> httpx.Response:
        jobs = json.loads(request.content)
        results = []
        for job in jobs:
            if job["securityType2"] == "Depositary Receipt":
                results.append({"warning": "No identifier found."})
            elif job["idValue"] == "GOOD":
                results.append(
                    {
                        "data": [
                            {
                                "ticker": "GOOD",
                                "name": "GOOD HOLDINGS INC",
                                "figi": "BBG000GOOD01",
                                "compositeFIGI": "BBG000GOOD01",
                                "shareClassFIGI": "BBG001GOOD02",
                                "exchCode": "US",
                                "securityType2": "Common Stock",
                            }
                        ]
                    }
                )
            elif job["idValue"] == "BAD":
                results.append(
                    {
                        "data": [
                            {
                                "ticker": "BAD",
                                "name": "UNRELATED SOFTWARE PLC",
                                "figi": "BBG000BAD001",
                                "compositeFIGI": "BBG000BAD001",
                                "shareClassFIGI": "BBG001BAD002",
                                "exchCode": "US",
                                "securityType2": "Common Stock",
                            }
                        ]
                    }
                )
            else:
                results.append({"warning": "No identifier found."})
        return httpx.Response(200, json=results)

    async def synchronize() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await sync_openfigi_identities(
                session,
                client=client,
                archive=ColdArchive(tmp_path, min_free_bytes=0, max_used_percent=99),
                max_assets=3,
                now=datetime(2026, 8, 24, tzinfo=UTC),
            )
        assert result.attempted_assets == 3
        assert result.verified_assets == 1
        assert result.mismatched_assets == 1
        assert result.unresolved_assets == 1

    asyncio.run(synchronize())
    session.commit()

    identities = {
        identity.asset_key: identity
        for identity in session.scalars(select(MarketAssetIdentifier))
    }
    assert identities["av:test:GOOD"].identity_status == "verified"
    assert identities["av:test:BAD"].identity_status == "mismatch"
    assert identities["av:test:MISS"].identity_status == "unresolved"
    assert verified_provider_history_series_ids(session) == {"HIST:GOOD:test"}
    assert len(list(tmp_path.rglob("*.json.gz"))) == 1
    outcomes = {
        outcome.asset_key: outcome
        for outcome in session.scalars(select(MarketDelistingOutcome))
    }
    assert outcomes["av:test:GOOD"].status == "evidence_required"
    assert outcomes["av:test:BAD"].status == "identity_required"


def test_verified_terminal_value_updates_factor_return(session: Session) -> None:
    _priced_lifecycle(session, "CASH", "Cash Deal Inc", last_price=40.0)
    session.add(
        MarketAssetIdentifier(
            asset_key="av:test:CASH",
            identity_status="verified",
            mapping_method="test",
            figi="BBG000CASH01",
            composite_figi="BBG000CASH01",
            mapped_ticker="CASH",
            mapped_name="CASH DEAL INC",
            mapped_exchange="US",
            security_type="Common Stock",
            name_similarity=1.0,
            attempt_count=1,
        )
    )
    session.flush()
    materialize_delisting_outcomes(session)

    outcome = verify_delisting_outcome(
        session,
        asset_key="av:test:CASH",
        outcome_type="cash_acquisition",
        terminal_value_per_share=50.0,
        payment_date=date(2026, 8, 24),
        evidence_url="https://www.sec.gov/Archives/example",
        evidence_note="The cited merger filing states a final cash value of 50 per share.",
        evidence_key="b" * 64,
        now=datetime(2026, 8, 24, tzinfo=UTC),
    )

    assert outcome.status == "verified"
    assert outcome.delisting_return == pytest.approx(0.25)
    assert outcome.evidence_hash is not None
    assert outcome.evidence_key == "b" * 64
    series = session.get(MarketSeries, "HIST:CASH:test")
    assert series is not None
    assert series.delisting_return == pytest.approx(0.25)


def test_terminal_value_rejects_unverified_identity(session: Session) -> None:
    _priced_lifecycle(session, "WAIT", "Wait Corp")
    session.flush()
    materialize_delisting_outcomes(session)

    with pytest.raises(ValueError, match="identity must be verified"):
        verify_delisting_outcome(
            session,
            asset_key="av:test:WAIT",
            outcome_type="bankruptcy_worthless",
            terminal_value_per_share=None,
            payment_date=date(2026, 8, 24),
            evidence_url="https://www.sec.gov/Archives/example",
            evidence_note="A primary-source court filing declares the common shares worthless.",
        )


def test_stock_terminal_value_requires_ratio_and_acquirer_price_evidence(
    session: Session,
) -> None:
    _priced_lifecycle(session, "ZEUS", "Olympic Steel Inc", last_price=47.86)
    session.add(
        MarketAssetIdentifier(
            asset_key="av:test:ZEUS",
            identity_status="verified",
            mapping_method="test",
            sec_cik="0000917470",
            mapped_ticker="ZEUS",
            mapped_name="OLYMPIC STEEL INC",
            mapped_exchange="US",
            name_similarity=1.0,
            attempt_count=1,
        )
    )
    ratio_key = "c" * 64
    price_key = "d" * 64
    session.add_all(
        [
            MarketDelistingEvidenceCandidate(
                evidence_key=ratio_key,
                asset_key="av:test:ZEUS",
                sec_cik="0000917470",
                accession_number="0001193125-26-051373",
                document_name="d37005d8k.htm",
                form="8-K",
                filed_on=date(2026, 2, 13),
                observed_on=date(2026, 2, 13),
                source_url="https://www.sec.gov/Archives/edgar/data/917470/ratio.htm",
                evidence_type="share_exchange_ratio",
                evidence_basis="human_primary_source_extract",
                candidate_value=1.7105,
                value_unit="acquirer_shares_per_share",
                evidence_excerpt="Each share was converted into 1.7105 Ryerson shares.",
                confidence=0.99,
                body_status="human_verified",
                review_status="accepted",
                review_role="terminal_outcome",
            ),
            MarketDelistingEvidenceCandidate(
                evidence_key=price_key,
                asset_key="av:test:ZEUS",
                sec_cik="0000917470",
                subject_symbol="RYI",
                subject_sec_cik="0001481582",
                accession_number="0001193125-26-057080",
                document_name="d31485dex991.htm",
                form="8-K/A",
                filed_on=date(2026, 2, 18),
                observed_on=date(2026, 2, 13),
                source_url="https://www.sec.gov/Archives/edgar/data/1481582/price.htm",
                evidence_type="acquirer_closing_price",
                evidence_basis="human_primary_source_extract",
                candidate_value=27.03,
                value_unit="USD_per_acquirer_share",
                evidence_excerpt="Ryerson common stock price per share was $27.03.",
                confidence=0.99,
                body_status="human_verified",
                review_status="accepted",
                review_role="supporting_evidence",
            ),
        ]
    )
    session.flush()
    materialize_delisting_outcomes(session)
    outcome = session.get(MarketDelistingOutcome, "av:test:ZEUS")
    assert outcome is not None
    outcome.last_trade_date = date(2026, 2, 13)
    outcome.last_trade_price = 47.86

    verified = verify_stock_delisting_outcome(
        session,
        asset_key="av:test:ZEUS",
        exchange_ratio_evidence_key=ratio_key,
        valuation_evidence_key=price_key,
        acquirer_symbol="RYI",
        payment_date=date(2026, 2, 13),
        evidence_note=(
            "SEC completion ratio multiplied by the SEC-reported closing-date "
            "Ryerson common-stock price."
        ),
        now=datetime(2026, 8, 26, tzinfo=UTC),
    )

    assert verified.terminal_value_per_share == pytest.approx(46.234815)
    assert verified.exchange_ratio == pytest.approx(1.7105)
    assert verified.acquirer_price_on_payment == pytest.approx(27.03)
    assert verified.delisting_return == pytest.approx(46.234815 / 47.86 - 1)
    assert verified.valuation_evidence_key == price_key


def test_depositary_receipt_abbreviation_does_not_create_false_ambiguity() -> None:
    lifecycle = MarketAssetLifecycle(
        asset_key="av:test:TTM",
        provider_key="alpha_vantage_listing_status",
        symbol="TTM",
        name="Tata Motors Ltd",
        exchange="NYSE",
        asset_type="Stock",
        ipo_date=date(2004, 9, 27),
        delisting_date=date(2026, 8, 21),
        listing_status="delisted",
        snapshot_date=date(2026, 8, 24),
        fetched_at=datetime(2026, 8, 24, tzinfo=UTC),
        source_url="https://www.alphavantage.co/documentation/",
    )
    selection = select_openfigi_identity(
        lifecycle,
        [
            {
                "ticker": "TTM",
                "name": "TATA MOTORS LTD-SPON ADR",
                "figi": "BBG000TEST01",
                "compositeFIGI": "BBG000TEST01",
                "shareClassFIGI": "BBG001TEST02",
                "exchCode": "US",
                "securityType2": "Depositary Receipt",
            }
        ],
    )

    assert selection.status == "verified"
    assert selection.name_similarity == 1.0


def test_lifecycle_resolution_blocks_provider_conflict_from_factor_gate(
    session: Session,
) -> None:
    _priced_lifecycle(session, "SLSR", "Solaris Resources Inc")
    session.add(
        MarketAssetIdentifier(
            asset_key="av:test:SLSR",
            identity_status="verified",
            mapping_method="test",
            mapped_ticker="SLSR",
            mapped_name="SOLARIS RESOURCES INC",
            mapped_exchange="US",
            name_similarity=1.0,
            attempt_count=1,
        )
    )
    session.flush()
    assert verified_provider_history_series_ids(session) == {"HIST:SLSR:test"}

    resolution = record_lifecycle_resolution(
        session,
        asset_key="av:test:SLSR",
        resolution_type="provider_conflict_active",
        authoritative_status="active",
        authoritative_delisting_date=None,
        evidence_url="https://example.com/solaris-investor",
        evidence_note="Issuer investor page still identifies the security as exchange listed.",
        now=datetime(2026, 8, 26, tzinfo=UTC),
    )

    assert resolution.authoritative_status == "active"
    assert verified_provider_history_series_ids(session) == set()


def test_sec_primary_identity_can_resolve_automated_provider_miss(
    session: Session,
) -> None:
    _priced_lifecycle(session, "SNBR", "Sleep Number Corp", last_price=0.125)
    session.flush()

    identity = verify_sec_primary_identity(
        session,
        asset_key="av:test:SNBR",
        sec_cik="827187",
        subject_name="SLEEP NUMBER CORPORATION",
        evidence_url=(
            "https://www.sec.gov/Archives/edgar/data/827187/"
            "000082718726000053/snbr-20260616.htm"
        ),
        evidence_note="Issuer Form 8-K identifies the registrant and the SNBR common stock.",
        now=datetime(2026, 8, 26, tzinfo=UTC),
    )

    assert identity.identity_status == "verified"
    assert identity.sec_cik == "0000827187"
    state = session.get(MarketDelistingEvidenceState, "av:test:SNBR")
    assert state is not None
    assert state.sec_cik == "0000827187"


def test_multi_stage_terminal_value_requires_confirmed_final_cashflow(
    session: Session,
) -> None:
    _priced_lifecycle(session, "LIQ", "Liquidating Holdings Inc", last_price=4.0)
    session.add(
        MarketAssetIdentifier(
            asset_key="av:test:LIQ",
            identity_status="verified",
            mapping_method="test",
            sec_cik="0000000123",
            mapped_ticker="LIQ",
            mapped_name="LIQUIDATING HOLDINGS INC",
            mapped_exchange="US",
            name_similarity=1.0,
            attempt_count=1,
        )
    )
    evidence_rows = []
    for index, value in enumerate((2.0, 3.0), start=1):
        evidence_rows.append(
            MarketDelistingEvidenceCandidate(
                evidence_key=str(index) * 64,
                asset_key="av:test:LIQ",
                sec_cik="0000000123",
                accession_number=f"0000000123-26-00000{index}",
                document_name=f"distribution-{index}.htm",
                form="8-K",
                filed_on=date(2026, 8, 21 + index),
                source_url=f"https://www.sec.gov/Archives/edgar/data/123/distribution-{index}.htm",
                evidence_type="liquidation_distribution_per_share",
                evidence_basis="human_primary_source_extract",
                candidate_value=value,
                value_unit="USD_per_share",
                evidence_excerpt=f"Liquidation distribution {index} was ${value:.2f} per share.",
                confidence=0.99,
                body_status="human_verified",
                review_status="accepted",
                review_role="terminal_outcome",
            )
        )
    session.add_all(evidence_rows)
    session.flush()
    materialize_delisting_outcomes(session)
    record_lifecycle_resolution(
        session,
        asset_key="av:test:LIQ",
        resolution_type="liquidation_pending",
        authoritative_status="liquidation",
        authoritative_delisting_date=date(2026, 8, 21),
        evidence_url="https://www.sec.gov/Archives/edgar/data/123/liquidation.htm",
        evidence_note="Stockholders approved a complete liquidation and staged distributions.",
        now=datetime(2026, 8, 26, tzinfo=UTC),
    )
    for index, value in enumerate((2.0, 3.0), start=1):
        record_terminal_cashflow(
            session,
            asset_key="av:test:LIQ",
            evidence_key=str(index) * 64,
            cashflow_type="liquidation_distribution",
            amount_per_share=value,
            payment_date=date(2026, 8, 21 + index),
            status="confirmed",
            is_final=index == 2,
            evidence_note=f"Confirmed liquidation distribution stage {index} from issuer filing.",
            now=datetime(2026, 8, 26, tzinfo=UTC),
        )

    outcome = finalize_multi_stage_outcome(
        session,
        asset_key="av:test:LIQ",
        outcome_type="liquidation_distribution",
        evidence_note="Two confirmed distributions include the issuer-designated final payment.",
        now=datetime(2026, 8, 26, tzinfo=UTC),
    )

    assert outcome.terminal_value_per_share == pytest.approx(5.0)
    assert outcome.delisting_return == pytest.approx(0.25)
    assert outcome.cashflow_count == 2
    assert outcome.terminal_is_final is True
    assert outcome.resolution_method == "reviewed_multi_stage_cashflow_v1"
    resolution = session.get(MarketLifecycleResolution, "av:test:LIQ")
    assert resolution is not None
    assert resolution.resolution_type == "liquidation_final"


def _priced_lifecycle(
    session: Session,
    symbol: str,
    name: str,
    *,
    last_price: float = 25.0,
) -> None:
    asset_key = f"av:test:{symbol}"
    series_id = f"HIST:{symbol}:test"
    session.add(
        MarketAssetLifecycle(
            asset_key=asset_key,
            provider_key="alpha_vantage_listing_status",
            symbol=symbol,
            name=name,
            exchange="NASDAQ",
            asset_type="Stock",
            ipo_date=date(2010, 1, 4),
            delisting_date=date(2026, 8, 21),
            listing_status="delisted",
            snapshot_date=date(2026, 8, 24),
            fetched_at=datetime(2026, 8, 24, tzinfo=UTC),
            source_url="https://www.alphavantage.co/documentation/",
        )
    )
    session.add(
        MarketSeries(
            series_id=series_id,
            name=name,
            category="historical_equity_price",
            unit="USD",
            frequency="weekly",
            source_name="Alpha Vantage weekly adjusted",
            source_url="https://www.alphavantage.co/documentation/",
            listing_status="delisted",
            listed_from=date(2010, 1, 4),
            listed_until=date(2026, 8, 21),
        )
    )
    for index in range(65):
        session.add(
            MarketObservation(
                series_id=series_id,
                observed_on=date(2026, 8, 21) - timedelta(days=7 * index),
                value=last_price - index / 10,
                fetched_at=datetime(2026, 8, 24, tzinfo=UTC),
            )
        )
    session.add(
        MarketPriceBackfillState(
            asset_key=asset_key,
            provider_key="alpha_vantage_listing_status",
            status="synced",
            priority_score=100.0,
            priority_reasons=["test"],
            attempt_count=1,
            observations_upserted=65,
            observed_start=date(2025, 5, 30),
            observed_end=date(2026, 8, 21),
            series_id=series_id,
        )
    )
