"""Validated GeoNames admin-1 and populated-place import."""

from __future__ import annotations

import zipfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AdministrativeArea, RegionalIndicator, RegionalObservation

SOURCE_NAME = "GeoNames"
SOURCE_URL = "https://www.geonames.org/"
DOWNLOAD_URL = "https://download.geonames.org/export/dump/"
LICENSE_NAME = "Creative Commons Attribution 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
POPULATION_INDICATOR_CODE = "GEONAMES.POPULATION"


class GeoNamesAdmin1(BaseModel):
    """One validated row from admin1CodesASCII.txt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(pattern=r"^[A-Z]{2}\.[A-Za-z0-9]+$")
    name: str = Field(min_length=1)
    ascii_name: str = Field(min_length=1)
    geoname_id: int = Field(gt=0)


class GeoNamesCity(BaseModel):
    """Relevant fields from one GeoNames populated-place row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    geoname_id: int = Field(gt=0)
    name: str = Field(min_length=1)
    ascii_name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    country_iso2: str = Field(pattern=r"^[A-Z]{2}$")
    admin1_code: str
    population: int = Field(ge=0)
    modified_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class GeoNamesImportResult(BaseModel):
    """Counts from one idempotent import."""

    model_config = ConfigDict(extra="forbid")

    admin1_upserted: int = Field(ge=0)
    cities_upserted: int = Field(ge=0)
    population_observations_upserted: int = Field(ge=0)
    countries_covered: int = Field(ge=0)


_ADMIN_ADAPTER = TypeAdapter(list[GeoNamesAdmin1])
_CITY_ADAPTER = TypeAdapter(list[GeoNamesCity])


def import_geonames(
    session: Session,
    *,
    admin1_path: Path,
    cities_zip_path: Path,
    countries: set[str] | None = None,
) -> GeoNamesImportResult:
    """Upsert global admin-1 reference centers, cities and city population."""
    selected = {code.upper() for code in countries} if countries else None
    admin_rows = [
        row
        for row in _read_admin1(admin1_path)
        if selected is None or row.code[:2] in selected
    ]
    city_rows = [
        row
        for row in _read_cities(cities_zip_path)
        if selected is None or row.country_iso2 in selected
    ]

    city_centers = _derive_admin1_reference_centers(city_rows)
    existing = {
        row.external_id: row
        for row in session.scalars(
            select(AdministrativeArea).where(
                AdministrativeArea.source_name == SOURCE_NAME
            )
        )
    }
    admin_by_code: dict[str, AdministrativeArea] = {}
    for admin in admin_rows:
        external_id = str(admin.geoname_id)
        row = existing.get(external_id)
        if row is None:
            row = AdministrativeArea(
                source_name=SOURCE_NAME,
                external_id=external_id,
                country_iso2=admin.code[:2],
                level="admin1",
                code=admin.code,
                name=admin.name,
                source_url=f"{SOURCE_URL}{external_id}",
                license_name=LICENSE_NAME,
                license_url=LICENSE_URL,
            )
            session.add(row)
            existing[external_id] = row
        row.parent_id = None
        row.country_iso2 = admin.code[:2]
        row.level = "admin1"
        row.code = admin.code
        row.name = admin.name
        row.ascii_name = admin.ascii_name
        row.population = None
        center = city_centers.get(admin.code)
        row.latitude = center[0] if center else None
        row.longitude = center[1] if center else None
        row.coordinate_precision = (
            "derived_city_weighted_center" if center else "unavailable"
        )
        row.source_url = f"{SOURCE_URL}{external_id}"
        row.license_name = LICENSE_NAME
        row.license_url = LICENSE_URL
        admin_by_code[admin.code] = row
    session.flush()

    city_area_by_id: dict[int, AdministrativeArea] = {}
    for city in city_rows:
        external_id = str(city.geoname_id)
        row = existing.get(external_id)
        if row is None:
            row = AdministrativeArea(
                source_name=SOURCE_NAME,
                external_id=external_id,
                country_iso2=city.country_iso2,
                level="city",
                code=f"{city.country_iso2}.{city.admin1_code}.{external_id}",
                name=city.name,
                source_url=f"{SOURCE_URL}{external_id}",
                license_name=LICENSE_NAME,
                license_url=LICENSE_URL,
            )
            session.add(row)
            existing[external_id] = row
        parent = admin_by_code.get(f"{city.country_iso2}.{city.admin1_code}")
        row.parent_id = parent.id if parent else None
        row.country_iso2 = city.country_iso2
        row.level = "city"
        row.code = f"{city.country_iso2}.{city.admin1_code}.{external_id}"
        row.name = city.name
        row.ascii_name = city.ascii_name or None
        row.latitude = city.latitude
        row.longitude = city.longitude
        row.coordinate_precision = "populated_place_point"
        row.population = city.population or None
        row.source_url = f"{SOURCE_URL}{external_id}"
        row.license_name = LICENSE_NAME
        row.license_url = LICENSE_URL
        city_area_by_id[city.geoname_id] = row
    session.flush()

    _upsert_population_indicator(session)
    observations = _upsert_city_population(
        session,
        city_rows=city_rows,
        city_area_by_id=city_area_by_id,
    )
    session.flush()
    return GeoNamesImportResult(
        admin1_upserted=len(admin_rows),
        cities_upserted=len(city_rows),
        population_observations_upserted=observations,
        countries_covered=len({row.country_iso2 for row in city_rows}),
    )


def _read_admin1(path: Path) -> list[GeoNamesAdmin1]:
    raw_rows: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            fields = line.rstrip("\r\n").split("\t")
            if len(fields) != 4:
                raise ValueError("GeoNames admin1 row must contain four tab fields")
            raw_rows.append(
                {
                    "code": fields[0],
                    "name": fields[1],
                    "ascii_name": fields[2],
                    "geoname_id": fields[3],
                }
            )
    return _ADMIN_ADAPTER.validate_python(raw_rows)


def _read_cities(path: Path) -> list[GeoNamesCity]:
    raw_rows: list[dict[str, object]] = []
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.endswith(".txt")]
        if len(names) != 1:
            raise ValueError("GeoNames city archive must contain exactly one text file")
        with archive.open(names[0]) as binary_handle:
            for binary_line in binary_handle:
                fields = binary_line.decode("utf-8").rstrip("\r\n").split("\t")
                if len(fields) != 19:
                    raise ValueError(
                        "GeoNames populated-place row must contain 19 tab fields"
                    )
                raw_rows.append(
                    {
                        "geoname_id": fields[0],
                        "name": fields[1],
                        "ascii_name": fields[2],
                        "latitude": fields[4],
                        "longitude": fields[5],
                        "country_iso2": fields[8],
                        "admin1_code": fields[10],
                        "population": fields[14] or "0",
                        "modified_date": fields[18],
                    }
                )
    return _CITY_ADAPTER.validate_python(raw_rows)


def _derive_admin1_reference_centers(
    cities: list[GeoNamesCity],
) -> dict[str, tuple[float, float]]:
    totals: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    for city in cities:
        code = f"{city.country_iso2}.{city.admin1_code}"
        weight = float(max(city.population, 1))
        totals[code][0] += city.latitude * weight
        totals[code][1] += city.longitude * weight
        totals[code][2] += weight
    return {
        code: (values[0] / values[2], values[1] / values[2])
        for code, values in totals.items()
        if values[2] > 0
    }


def _upsert_population_indicator(session: Session) -> None:
    indicator = session.get(RegionalIndicator, POPULATION_INDICATOR_CODE)
    if indicator is None:
        indicator = RegionalIndicator(code=POPULATION_INDICATOR_CODE)
        session.add(indicator)
    indicator.name_en = "Population (populated place)"
    indicator.name_zh = "人口 (城市/聚居地)"
    indicator.unit = "people"
    indicator.source_name = SOURCE_NAME
    indicator.source_url = DOWNLOAD_URL
    indicator.license_name = LICENSE_NAME
    indicator.license_url = LICENSE_URL


def _upsert_city_population(
    session: Session,
    *,
    city_rows: list[GeoNamesCity],
    city_area_by_id: dict[int, AdministrativeArea],
) -> int:
    area_ids = [row.id for row in city_area_by_id.values()]
    existing = {
        (row.area_id, row.period): row
        for row in session.scalars(
            select(RegionalObservation).where(
                RegionalObservation.indicator_code == POPULATION_INDICATOR_CODE,
                RegionalObservation.area_id.in_(area_ids),
            )
        )
    }
    fetched_at = datetime.now(UTC)
    upserted = 0
    for city in city_rows:
        if city.population <= 0:
            continue
        area = city_area_by_id[city.geoname_id]
        key = (area.id, city.modified_date)
        observation = existing.get(key)
        if observation is None:
            observation = RegionalObservation(
                area_id=area.id,
                indicator_code=POPULATION_INDICATOR_CODE,
                period=city.modified_date,
            )
            session.add(observation)
            existing[key] = observation
        observation.value = float(city.population)
        observation.fetched_at = fetched_at
        upserted += 1
    return upserted
