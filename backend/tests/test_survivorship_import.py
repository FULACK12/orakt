"""Validated external historical-equity import tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import MarketObservation, MarketSeries
from app.survivorship_import import import_survivorship_csv


def test_survivorship_csv_import_retains_lifecycle_and_prices(tmp_path: Path) -> None:
    csv_path = tmp_path / "historical.csv"
    csv_path.write_text(
        "series_id,name,observed_on,close,listing_status,source_name,source_url,"
        "listed_from,listed_until,delisting_return,sector,region,neutralization_group\n"
        "HIST:EXAMPLE:NASDAQ:2020-01-03,Example Corp,2020-01-01,10,delisted,"
        "Licensed test,https://example.test/data,2019-01-01,2020-01-03,-0.4,Technology,"
        "north_america,industry:Technology\n"
        "HIST:EXAMPLE:NASDAQ:2020-01-03,Example Corp,2020-01-03,8,delisted,"
        "Licensed test,https://example.test/data,2019-01-01,2020-01-03,-0.4,Technology,"
        "north_america,industry:Technology\n",
        encoding="utf-8",
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = import_survivorship_csv(session, csv_path)
        session.commit()
        series = session.get(MarketSeries, "HIST:EXAMPLE:NASDAQ:2020-01-03")
        assert series is not None
        assert series.category == "historical_equity_price"
        assert series.listing_status == "delisted"
        assert series.listed_until == date(2020, 1, 3)
        assert series.delisting_return == -0.4
        assert series.neutralization_group == "industry:Technology"
        assert result.series_upserted == 1
        assert result.observations_upserted == 2
        assert result.delisting_returns_covered == 1
        assert session.scalar(select(func.count()).select_from(MarketObservation)) == 2
    engine.dispose()


def test_survivorship_import_rejects_reused_unscoped_ticker(tmp_path: Path) -> None:
    csv_path = tmp_path / "invalid.csv"
    csv_path.write_text(
        "series_id,name,observed_on,close,listing_status,source_name,source_url\n"
        "EMC,Old EMC,2016-01-01,10,delisted,Unknown,https://example.test/data\n",
        encoding="utf-8",
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session, pytest.raises(ValueError, match="HIST"):
        import_survivorship_csv(session, csv_path)
    engine.dispose()
