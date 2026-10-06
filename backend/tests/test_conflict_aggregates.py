"""ACLED workbook streaming and conflict-indicator query tests."""

from __future__ import annotations

import io
from collections.abc import Generator
from datetime import date
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.conflicts.acled_aggregate import (
    EXCEL_EPOCH,
    EXPECTED_HEADERS,
    import_acled_country_history_workbook,
    import_acled_workbook,
)
from app.conflicts.service import get_conflict_indicator
from app.db.base import Base
from app.db.models import (
    ConflictAggregateObservation,
    ConflictCountryIndicatorObservation,
)


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    engine.dispose()


def test_imports_recent_political_violence_and_builds_indicator(
    session: Session,
    tmp_path: Path,
) -> None:
    workbook = tmp_path / "Africa_aggregated_data_up_to_week_of-2026-07-18.xlsx"
    workbook.write_bytes(
        _workbook(
            [
                [
                    _serial(date(2026, 7, 18)),
                    "Africa",
                    "Exampleland",
                    "North",
                    "Battles",
                    "Armed clash",
                    12,
                    7,
                    25000,
                    "Political violence",
                    101,
                    12.5,
                    31.25,
                ],
                [
                    _serial(date(2026, 7, 18)),
                    "Africa",
                    "Exampleland",
                    "Capital",
                    "Protests",
                    "Peaceful protest",
                    50,
                    0,
                    100000,
                    "Demonstrations",
                    102,
                    13.0,
                    32.0,
                ],
                [
                    _serial(date(2020, 1, 4)),
                    "Africa",
                    "Exampleland",
                    "Old",
                    "Battles",
                    "Armed clash",
                    2,
                    1,
                    None,
                    "Political violence",
                    103,
                    11.0,
                    30.0,
                ],
            ]
        )
    )

    result = import_acled_workbook(
        session,
        path=workbook,
        history_days=1_095,
    )

    assert result.rows_seen == 3
    assert result.rows_imported == 1
    assert session.scalar(
        select(func.count(ConflictAggregateObservation.id))
    ) == 1
    payload = get_conflict_indicator(
        session,
        weeks=12,
        west=-180,
        south=-90,
        east=180,
        north=90,
        zoom=5,
        limit=100,
        as_of=date(2026, 8, 3),
    )
    assert payload.latest_week == date(2026, 7, 18)
    assert payload.point_count == 1
    assert payload.points[0].admin1 == "North"
    assert payload.points[0].events == 12
    assert payload.points[0].fatalities == 7
    current_week = get_conflict_indicator(
        session,
        weeks=1,
        west=-180,
        south=-90,
        east=180,
        north=90,
        zoom=5,
        limit=100,
        as_of=date(2026, 8, 3),
    )
    assert current_week.point_count == 0

    repeated = import_acled_workbook(
        session,
        path=workbook,
        history_days=1_095,
    )
    assert repeated.skipped_unchanged is True


def test_imports_country_year_history_to_its_real_source_boundary(
    session: Session,
    tmp_path: Path,
) -> None:
    workbook = (
        tmp_path
        / "number_of_political_violence_events_by_country-year_as-of-24Jul2026.xlsx"
    )
    workbook.write_bytes(
        _workbook(
            [
                ["Exampleland", 1997, 12],
                ["Exampleland", 2026, 8],
                ["Otherland", 2001, 3],
            ],
            headers=("COUNTRY", "YEAR", "EVENTS"),
        )
    )

    result = import_acled_country_history_workbook(session, path=workbook)

    assert result.rows_seen == 3
    assert result.rows_imported == 3
    rows = list(
        session.scalars(
            select(ConflictCountryIndicatorObservation).order_by(
                ConflictCountryIndicatorObservation.period
            )
        )
    )
    assert rows[0].period == date(1997, 1, 1)
    assert rows[0].metric == "political_violence_events"
    assert rows[0].frequency == "annual"
    assert rows[0].value == 12


def test_imports_country_year_fatality_history_with_official_value_header(
    session: Session,
    tmp_path: Path,
) -> None:
    workbook = (
        tmp_path
        / "number_of_reported_fatalities_by_country-year-as-of-24Jul2026.xlsx"
    )
    workbook.write_bytes(
        _workbook(
            [["Exampleland", 1997, 42]],
            headers=("COUNTRY", "YEAR", "FATALITIES"),
        )
    )

    result = import_acled_country_history_workbook(session, path=workbook)

    assert result.rows_imported == 1
    row = session.scalar(select(ConflictCountryIndicatorObservation))
    assert row is not None
    assert row.metric == "reported_fatalities"
    assert row.value == 42


def _serial(value: date) -> int:
    return (value - EXCEL_EPOCH).days


def _workbook(
    rows: list[list[object]],
    *,
    headers: tuple[str, ...] = EXPECTED_HEADERS,
) -> bytes:
    strings: list[str] = []

    def string_index(value: str) -> int:
        if value not in strings:
            strings.append(value)
        return strings.index(value)

    row_xml = [_row_xml(1, list(headers), string_index)]
    for index, row in enumerate(rows, start=2):
        row_xml.append(_row_xml(index, row, string_index))
    shared_xml = "".join(
        f"<si><t>{_xml_escape(value)}</t></si>" for value in strings
    )
    sheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(row_xml)}</sheetData></worksheet>"
    )
    shared = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"{shared_xml}</sst>"
    )
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
        archive.writestr("xl/sharedStrings.xml", shared)
    return output.getvalue()


def _row_xml(
    row_number: int,
    values: list[object],
    string_index: object,
) -> str:
    cells: list[str] = []
    for index, value in enumerate(values):
        if value is None:
            continue
        reference = f"{chr(ord('A') + index)}{row_number}"
        if isinstance(value, str):
            cells.append(
                f'<c r="{reference}" t="s"><v>{string_index(value)}</v></c>'  # type: ignore[operator]
            )
        else:
            cells.append(f'<c r="{reference}" t="n"><v>{value}</v></c>')
    return f'<row r="{row_number}">{"".join(cells)}</row>'


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
