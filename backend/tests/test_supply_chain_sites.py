"""Source-bounded supply-chain site and exposure tests."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    AdministrativeArea,
    CompanyProfile,
    CompanySupplyChainEdge,
    CompanySupplyChainSite,
    ConflictAggregateObservation,
    Event,
)
from app.supply_chain_site_import import (
    ReviewedSupplyChainSite,
    import_reviewed_supply_chain_sites,
    load_reviewed_sites,
)
from app.supply_chain_sites import (
    materialize_supply_chain_sites,
    parse_reported_geography,
    supply_chain_site_exposure,
)


def test_parse_reported_geography_keeps_region_scope() -> None:
    assert parse_reported_geography(
        "Texas, Oregon - United States | Taiwan - Taiwan | Leinster - Ireland"
    ) == [
        ("Texas", "United States", "US"),
        ("Oregon", "United States", "US"),
        ("Taiwan", "Taiwan", "TW"),
        ("Leinster", "Ireland", "IE"),
    ]


def test_parse_reported_geography_repairs_known_supplier_list_ocr() -> None:
    assert parse_reported_geography(
        "Lexilip - Ireland | Por tugal - Portugal"
    ) == [
        ("Leixlip", "Ireland", "IE"),
        ("Portugal", "Portugal", "PT"),
    ]


def test_reviewed_micron_facilities_are_source_bounded() -> None:
    config_path = (
        Path(__file__).resolve().parents[1]
        / "config"
        / "supply_chain_sites_reviewed_20260831_micron.json"
    )
    sites = load_reviewed_sites(config_path)
    assert len(sites) == 8
    assert {item.related_ticker for item in sites} == {"MU"}
    assert all(
        item.association_scope == "supplier_facility_not_customer_linked"
        for item in sites
    )
    assert all(item.available_at == date(2026, 8, 31) for item in sites)
    assert len({item.facility_name for item in sites}) == len(sites)


def test_reviewed_intel_facilities_are_source_bounded() -> None:
    config_path = (
        Path(__file__).resolve().parents[1]
        / "config"
        / "supply_chain_sites_reviewed_20260831_intel.json"
    )
    sites = load_reviewed_sites(config_path)
    assert len(sites) == 4
    assert {item.related_ticker for item in sites} == {"INTC"}
    assert all(
        item.association_scope == "supplier_facility_not_customer_linked"
        for item in sites
    )
    assert all(item.available_at == date(2026, 8, 31) for item in sites)
    assert len({item.facility_name for item in sites}) == len(sites)


def test_materializes_region_and_joins_nearby_risk_signals() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    as_of = date(2026, 8, 30)
    with Session(engine) as session:
        session.add(
            CompanyProfile(
                ticker="TEST",
                cik="0000000001",
                name="Test Company",
                sector="Technology",
                industry="Semiconductors",
                source_url="https://example.test/company",
            )
        )
        session.add(
            AdministrativeArea(
                country_iso2="US",
                level="admin1",
                code="US.TX",
                name="Texas",
                ascii_name="Texas",
                latitude=Decimal("31.000000"),
                longitude=Decimal("-99.000000"),
                coordinate_precision="reference_point",
                population=30_000_000,
                source_name="GeoNames",
                external_id="US.TX",
                source_url="https://www.geonames.org/",
                license_name="CC BY 4.0",
                license_url="https://creativecommons.org/licenses/by/4.0/",
            )
        )
        session.flush()
        edge = CompanySupplyChainEdge(
            subject_ticker="TEST",
            related_company_name="Supplier One",
            related_ticker="SUP",
            relationship_type="supplier",
            product_or_input="chips",
            geography="Texas - United States | Taiwan - Taiwan",
            dependency_level="unknown",
            review_status="verified",
            confidence=0.8,
            source_kind="issuer_supplier_list",
            source_ref="supplier-list:test:1",
            source_url="https://example.test/suppliers",
            source_excerpt="Supplier One has manufacturing locations in Texas and Taiwan.",
            observed_at=date(2026, 1, 1),
            available_at=date(2026, 2, 1),
        )
        session.add(edge)
        session.flush()
        session.add(
            ConflictAggregateObservation(
                week=date(2026, 8, 24),
                region="Northern America",
                country="United States",
                admin1="Texas",
                event_type="Protests",
                sub_event_type="Violent demonstration",
                events=4,
                fatalities=1,
                population_exposure=None,
                disorder_type="Political violence",
                area_external_id=None,
                latitude=31.05,
                longitude=-99.05,
                source_file="test.xlsx",
                imported_at=datetime(2026, 8, 30, tzinfo=UTC),
            )
        )
        session.add(
            Event(
                event_type="hurricane",
                title="Hurricane disrupts regional transport",
                summary="Power outages were also reported.",
                severity=Decimal("0.700"),
                novelty=Decimal("0.500"),
                confidence=Decimal("0.800"),
                start_at=datetime(2026, 8, 27, tzinfo=UTC),
                latitude=Decimal("31.100000"),
                longitude=Decimal("-99.100000"),
                country_code="US",
            )
        )
        session.commit()

        result = materialize_supply_chain_sites(session, ticker="TEST")
        session.commit()
        assert result == {
            "edges_scanned": 1,
            "sites_replaced": 0,
            "sites_inserted": 2,
            "coordinate_mapped": 1,
            "coordinate_unresolved": 1,
        }
        sites = list(session.scalars(select(CompanySupplyChainSite)))
        assert len(sites) == 2
        texas = next(item for item in sites if item.site_name == "Texas")
        assert texas.coordinate_precision == "admin1_centroid"
        assert texas.verification_status == "verified_region"
        assert texas.association_scope == "issuer_reported_manufacturing_region"

        exposure = supply_chain_site_exposure(
            session,
            ticker="TEST",
            as_of=as_of,
            weeks=12,
        )
        assert exposure["site_count"] == 2
        assert exposure["returned_site_count"] == 2
        assert exposure["geocoded_site_count"] == 1
        assert exposure["exact_facility_count"] == 0
        assert exposure["regional_location_count"] == 2
        assert exposure["company_facility_count"] == 0
        assert exposure["supplier_location_count"] == 2
        assert exposure["conflict_exposed_count"] == 1
        assert exposure["disaster_exposed_count"] == 1
        assert exposure["power_signal_count"] == 1
        texas_exposure = next(
            item for item in exposure["sites"] if item["site_name"] == "Texas"
        )
        assert texas_exposure["conflict_events"] == 4
        assert texas_exposure["conflict_fatalities"] == 1
        assert texas_exposure["disaster_event_count"] == 1
        assert texas_exposure["nearest_port"] is not None
        assert texas_exposure["port_route_status"] == "nearest_reference_not_confirmed"

        truncated = supply_chain_site_exposure(
            session,
            ticker="TEST",
            as_of=as_of,
            weeks=12,
            limit=1,
        )
        assert truncated["returned_site_count"] == 1
        assert truncated["truncated"] is True
        assert truncated["supplier_location_count"] == 2

        repeated = materialize_supply_chain_sites(session, ticker="TEST")
        session.commit()
        assert repeated["sites_replaced"] == 2
        assert session.query(CompanySupplyChainSite).count() == 2


def test_imports_exact_supplier_facility_without_claiming_customer_assignment() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
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
        session.flush()
        session.add(
            CompanySupplyChainEdge(
                subject_ticker="AAPL",
                related_company_name="Taiwan Semiconductor Manufacturing Company",
                related_ticker="TSM",
                relationship_type="supplier",
                product_or_input="manufacturing",
                geography="Taiwan - Taiwan",
                dependency_level="unknown",
                review_status="verified",
                confidence=0.82,
                source_kind="issuer_supplier_list",
                source_ref="apple-supplier-list:tsm",
                source_url="https://www.apple.com/supplier-list.pdf",
                source_excerpt="Apple lists TSMC as a supplier with Taiwan manufacturing.",
                observed_at=date(2023, 9, 30),
                available_at=date(2024, 4, 1),
            )
        )
        session.commit()
        site = ReviewedSupplyChainSite(
            subject_ticker="AAPL",
            related_ticker="TSM",
            facility_name="TSMC Fab 12A",
            country_name="Taiwan",
            country_iso2="TW",
            admin1_name="Hsinchu",
            latitude=24.7727316,
            longitude=121.0142216,
            source_url="https://www.tsmc.com/english/aboutTSMC/TSMC_Fabs",
            source_excerpt=(
                "TSMC lists Fab 12A at Hsinchu Science Park and links this map point."
            ),
            observed_at=date(2026, 8, 31),
            available_at=date(2026, 8, 31),
        )
        first = import_reviewed_supply_chain_sites(session, sites=[site])
        session.commit()
        assert first.inserted == 1
        stored = session.scalar(select(CompanySupplyChainSite))
        assert stored is not None
        assert stored.coordinate_precision == "exact_facility"
        assert stored.verification_status == "verified_exact"
        assert stored.association_scope == "supplier_facility_not_customer_linked"

        subject_exposure = supply_chain_site_exposure(
            session,
            ticker="AAPL",
            as_of=date(2026, 8, 31),
        )
        assert subject_exposure["company_facility_count"] == 0
        assert subject_exposure["supplier_location_count"] == 1
        assert subject_exposure["sites"][0]["facility_role"] == (
            "upstream_supplier_location"
        )

        owner_exposure = supply_chain_site_exposure(
            session,
            ticker="TSM",
            as_of=date(2026, 8, 31),
        )
        assert owner_exposure["site_count"] == 1
        assert owner_exposure["company_facility_count"] == 1
        assert owner_exposure["supplier_location_count"] == 0
        assert owner_exposure["sites"][0]["context_ticker"] == "TSM"
        assert owner_exposure["sites"][0]["facility_role"] == "company_facility"

        second = import_reviewed_supply_chain_sites(session, sites=[site])
        session.commit()
        assert second.inserted == 0
        assert second.updated == 1
        assert session.query(CompanySupplyChainSite).count() == 1
