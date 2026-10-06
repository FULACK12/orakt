"""Official subnational population imports with provider-specific definitions."""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AdministrativeArea, RegionalIndicator, RegionalObservation

STATCAN_CODE = "STATCAN.17-10-0005-01.POPULATION"
STATCAN_SOURCE = "Statistics Canada"
STATCAN_SOURCE_URL = (
    "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1710000501"
)
STATCAN_LICENSE = "Statistics Canada Open Licence"
STATCAN_LICENSE_URL = "https://www.statcan.gc.ca/en/reference/licence"

CHINA_CENSUS_CODE = "NBS.CN.CENSUS2020.POPULATION"
CHINA_CENSUS_SOURCE = "National Bureau of Statistics of China"
CHINA_CENSUS_URL = (
    "https://www.stats.gov.cn/english/PressRelease/"
    "202105/t20210510_1817188.html"
)
CHINA_CENSUS_LICENSE = (
    "Official statistical publication; reuse terms not explicitly stated"
)


class RegionalPopulationRecord(BaseModel):
    """One source-period population value matched by admin-1 name."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    area_name: str = Field(min_length=1)
    period: str = Field(min_length=4, max_length=16)
    value: int = Field(ge=0)


class RegionalPopulationImportResult(BaseModel):
    """Counts and unmatched provider names from one import."""

    model_config = ConfigDict(extra="forbid")

    indicator_code: str
    observations_upserted: int = Field(ge=0)
    unmatched_area_names: list[str]


_POPULATION_ADAPTER = TypeAdapter(list[RegionalPopulationRecord])

_CHINA_CENSUS_2020 = _POPULATION_ADAPTER.validate_python(
    [
        {"area_name": "Beijing", "period": "2020-11-01", "value": 21_893_095},
        {"area_name": "Tianjin", "period": "2020-11-01", "value": 13_866_009},
        {"area_name": "Hebei", "period": "2020-11-01", "value": 74_610_235},
        {"area_name": "Shanxi", "period": "2020-11-01", "value": 34_915_616},
        {
            "area_name": "Inner Mongolia",
            "period": "2020-11-01",
            "value": 24_049_155,
        },
        {"area_name": "Liaoning", "period": "2020-11-01", "value": 42_591_407},
        {"area_name": "Jilin", "period": "2020-11-01", "value": 24_073_453},
        {
            "area_name": "Heilongjiang",
            "period": "2020-11-01",
            "value": 31_850_088,
        },
        {"area_name": "Shanghai", "period": "2020-11-01", "value": 24_870_895},
        {"area_name": "Jiangsu", "period": "2020-11-01", "value": 84_748_016},
        {"area_name": "Zhejiang", "period": "2020-11-01", "value": 64_567_588},
        {"area_name": "Anhui", "period": "2020-11-01", "value": 61_027_171},
        {"area_name": "Fujian", "period": "2020-11-01", "value": 41_540_086},
        {"area_name": "Jiangxi", "period": "2020-11-01", "value": 45_188_635},
        {"area_name": "Shandong", "period": "2020-11-01", "value": 101_527_453},
        {"area_name": "Henan", "period": "2020-11-01", "value": 99_365_519},
        {"area_name": "Hubei", "period": "2020-11-01", "value": 57_752_557},
        {"area_name": "Hunan", "period": "2020-11-01", "value": 66_444_864},
        {"area_name": "Guangdong", "period": "2020-11-01", "value": 126_012_510},
        {"area_name": "Guangxi", "period": "2020-11-01", "value": 50_126_804},
        {"area_name": "Hainan", "period": "2020-11-01", "value": 10_081_232},
        {"area_name": "Chongqing", "period": "2020-11-01", "value": 32_054_159},
        {"area_name": "Sichuan", "period": "2020-11-01", "value": 83_674_866},
        {"area_name": "Guizhou", "period": "2020-11-01", "value": 38_562_148},
        {"area_name": "Yunnan", "period": "2020-11-01", "value": 47_209_277},
        {"area_name": "Tibet", "period": "2020-11-01", "value": 3_648_100},
        {"area_name": "Shaanxi", "period": "2020-11-01", "value": 39_528_999},
        {"area_name": "Gansu", "period": "2020-11-01", "value": 25_019_831},
        {"area_name": "Qinghai", "period": "2020-11-01", "value": 5_923_957},
        {"area_name": "Ningxia", "period": "2020-11-01", "value": 7_202_654},
        {"area_name": "Xinjiang", "period": "2020-11-01", "value": 25_852_345},
    ]
)


def import_statcan_population(
    session: Session,
    *,
    archive_path: Path,
) -> RegionalPopulationImportResult:
    """Import the latest all-ages, all-genders provincial population rows."""
    latest_by_area: dict[str, RegionalPopulationRecord] = {}
    with zipfile.ZipFile(archive_path) as archive:
        names = [
            name
            for name in archive.namelist()
            if name.endswith(".csv") and "MetaData" not in name
        ]
        if len(names) != 1:
            raise ValueError("Statistics Canada archive must contain one data CSV")
        with archive.open(names[0]) as binary_handle:
            text_handle = io.TextIOWrapper(binary_handle, encoding="utf-8-sig")
            for row in csv.DictReader(text_handle):
                if (
                    row.get("GEO") == "Canada"
                    or row.get("Gender") != "Total - gender"
                    or row.get("Age group") != "All ages"
                    or row.get("UOM") != "Persons"
                    or not row.get("VALUE")
                ):
                    continue
                record = RegionalPopulationRecord(
                    area_name=row["GEO"],
                    period=row["REF_DATE"],
                    value=int(str(row["VALUE"])),
                )
                current = latest_by_area.get(record.area_name)
                if current is None or record.period > current.period:
                    latest_by_area[record.area_name] = record

    _upsert_indicator(
        session,
        code=STATCAN_CODE,
        name_en="Population estimate",
        name_zh="人口估计",
        source_name=STATCAN_SOURCE,
        source_url=STATCAN_SOURCE_URL,
        license_name=STATCAN_LICENSE,
        license_url=STATCAN_LICENSE_URL,
    )
    return _upsert_population_records(
        session,
        country_iso2="CA",
        indicator_code=STATCAN_CODE,
        records=list(latest_by_area.values()),
    )


def import_china_census_population(
    session: Session,
) -> RegionalPopulationImportResult:
    """Import the 31 official 2020 province-level permanent-resident counts."""
    _upsert_indicator(
        session,
        code=CHINA_CENSUS_CODE,
        name_en="Permanent resident population (2020 census)",
        name_zh="常住人口 (2020 年人口普查)",
        source_name=CHINA_CENSUS_SOURCE,
        source_url=CHINA_CENSUS_URL,
        license_name=CHINA_CENSUS_LICENSE,
        license_url=CHINA_CENSUS_URL,
    )
    return _upsert_population_records(
        session,
        country_iso2="CN",
        indicator_code=CHINA_CENSUS_CODE,
        records=_CHINA_CENSUS_2020,
    )


def _upsert_indicator(
    session: Session,
    *,
    code: str,
    name_en: str,
    name_zh: str,
    source_name: str,
    source_url: str,
    license_name: str,
    license_url: str,
) -> None:
    indicator = session.get(RegionalIndicator, code)
    if indicator is None:
        indicator = RegionalIndicator(code=code)
        session.add(indicator)
    indicator.name_en = name_en
    indicator.name_zh = name_zh
    indicator.unit = "people"
    indicator.source_name = source_name
    indicator.source_url = source_url
    indicator.license_name = license_name
    indicator.license_url = license_url


def _upsert_population_records(
    session: Session,
    *,
    country_iso2: str,
    indicator_code: str,
    records: list[RegionalPopulationRecord],
) -> RegionalPopulationImportResult:
    areas = list(
        session.scalars(
            select(AdministrativeArea).where(
                AdministrativeArea.country_iso2 == country_iso2,
                AdministrativeArea.level == "admin1",
            )
        )
    )
    area_by_name = {
        (area.ascii_name or area.name).casefold(): area
        for area in areas
    }
    existing = {
        (observation.area_id, observation.period): observation
        for observation in session.scalars(
            select(RegionalObservation).where(
                RegionalObservation.indicator_code == indicator_code
            )
        )
    }
    fetched_at = datetime.now(UTC)
    unmatched: list[str] = []
    upserted = 0
    for record in records:
        area = area_by_name.get(record.area_name.casefold())
        if area is None:
            unmatched.append(record.area_name)
            continue
        key = (area.id, record.period)
        observation = existing.get(key)
        if observation is None:
            observation = RegionalObservation(
                area_id=area.id,
                indicator_code=indicator_code,
                period=record.period,
            )
            session.add(observation)
            existing[key] = observation
        observation.value = float(record.value)
        observation.fetched_at = fetched_at
        upserted += 1
    session.flush()
    return RegionalPopulationImportResult(
        indicator_code=indicator_code,
        observations_upserted=upserted,
        unmatched_area_names=sorted(unmatched),
    )
