"""GeoNames import and zoom-aware regional query tests."""

from __future__ import annotations

import zipfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import AdministrativeArea, RegionalObservation
from app.geography.geonames import import_geonames
from app.geography.regional_population import import_statcan_population
from app.geography.service import get_area_detail, list_areas


def _city_row(
    geoname_id: int,
    name: str,
    latitude: float,
    longitude: float,
    population: int,
) -> str:
    return "\t".join(
        [
            str(geoname_id),
            name,
            name,
            "",
            str(latitude),
            str(longitude),
            "P",
            "PPLA",
            "CA",
            "",
            "08",
            "",
            "",
            "",
            str(population),
            "",
            "",
            "America/Toronto",
            datetime.now(UTC).date().isoformat(),
        ]
    )


def test_geonames_import_is_idempotent_and_exposes_precision(
    tmp_path: Path,
) -> None:
    admin1_path = tmp_path / "admin1CodesASCII.txt"
    admin1_path.write_text(
        "CA.08\tOntario\tOntario\t6093943\n",
        encoding="utf-8",
    )
    cities_path = tmp_path / "cities15000.zip"
    with zipfile.ZipFile(cities_path, "w") as archive:
        archive.writestr(
            "cities15000.txt",
            "\n".join(
                [
                    _city_row(6167865, "Toronto", 43.70011, -79.4163, 2600000),
                    _city_row(6094817, "Ottawa", 45.41117, -75.69812, 812129),
                ]
            ),
        )

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        first = import_geonames(
            session,
            admin1_path=admin1_path,
            cities_zip_path=cities_path,
        )
        session.commit()
        second = import_geonames(
            session,
            admin1_path=admin1_path,
            cities_zip_path=cities_path,
        )
        session.commit()

        assert first.admin1_upserted == 1
        assert first.cities_upserted == 2
        assert second.cities_upserted == 2
        assert session.scalar(
            select(func.count()).select_from(AdministrativeArea)
        ) == 3
        assert session.scalar(
            select(func.count()).select_from(RegionalObservation)
        ) == 2

        provinces = list_areas(
            session,
            country_iso2="ca",
            level="admin1",
            parent_id=None,
            minimum_population=0,
            limit=100,
        )
        assert provinces.count == 1
        assert (
            provinces.areas[0].coordinate_precision
            == "derived_city_weighted_center"
        )

        toronto = session.scalar(
            select(AdministrativeArea).where(
                AdministrativeArea.name == "Toronto"
            )
        )
        assert toronto is not None
        detail = get_area_detail(session, area_id=toronto.id)
        assert detail.area.coordinate_precision == "populated_place_point"
        assert detail.metrics[0].value == 2_600_000

    engine.dispose()


def test_statcan_import_keeps_latest_provider_period(tmp_path: Path) -> None:
    archive_path = tmp_path / "17100005-eng.zip"
    header = (
        '"REF_DATE","GEO","DGUID","Gender","Age group","UOM","UOM_ID",'
        '"SCALAR_FACTOR","SCALAR_ID","VECTOR","COORDINATE","VALUE",'
        '"STATUS","SYMBOL","TERMINATED","DECIMALS"'
    )
    rows = [
        header,
        (
            '"2024/10","Ontario","x","Total - gender","All ages",'
            '"Persons","249","units","0","v1","1","16000000","","","","0"'
        ),
        (
            '"2025/01","Ontario","x","Total - gender","All ages",'
            '"Persons","249","units","0","v1","1","16100000","","","","0"'
        ),
        (
            '"2025/01","Ontario","x","Men+","All ages","Persons","249",'
            '"units","0","v1","1","8000000","","","","0"'
        ),
    ]
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("17100005.csv", "\n".join(rows))

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            AdministrativeArea(
                country_iso2="CA",
                level="admin1",
                code="CA.08",
                name="Ontario",
                ascii_name="Ontario",
                coordinate_precision="derived_city_weighted_center",
                source_name="GeoNames",
                external_id="6093943",
                source_url="https://www.geonames.org/6093943",
                license_name="CC BY 4.0",
                license_url="https://creativecommons.org/licenses/by/4.0/",
            )
        )
        session.commit()
        result = import_statcan_population(
            session,
            archive_path=archive_path,
        )
        session.commit()

        assert result.observations_upserted == 1
        observation = session.scalar(select(RegionalObservation))
        assert observation is not None
        assert observation.period == "2025/01"
        assert observation.value == 16_100_000

    engine.dispose()
