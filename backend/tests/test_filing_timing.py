"""Synthetic time-provenance tests; no external requests."""

import json
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.models import CompanyFiling, FilingTimingObservation
from app.filing_timing import archive_response, parse_accepted_at, retain_observations


@pytest.mark.parametrize(
    "raw",
    [None, "2026-07-31", "2026-07-31T16:15:00", "bad", "2026-02-31T16:15:00Z", "2026-07-31T16:15Z"],
)
def test_missing_naive_or_imprecise_time_not_guessed(raw):
    assert parse_accepted_at(raw) is None


def test_explicit_offset_normalized():
    assert parse_accepted_at("2026-08-04T16:15:00-04:00") == datetime(
        2026, 8, 4, 20, 15, tzinfo=UTC
    )


def test_archive_content_is_immutable(tmp_path):
    relative, digest = archive_response(tmp_path, b"fixture")
    assert archive_response(tmp_path, b"fixture") == (relative, digest)
    (tmp_path / relative).write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="archive_integrity"):
        archive_response(tmp_path, b"fixture")


def test_real_table_versions_append_without_overwriting(tmp_path):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CompanyFiling.__table__.create(engine)
    FilingTimingObservation.__table__.create(engine)
    now = datetime(2026, 10, 5, tzinfo=UTC)
    with Session(engine) as session:
        session.add(
            CompanyFiling(
                accession_number="fixture",
                ticker="TEST",
                form="10-Q",
                filed_at=date(2026, 8, 5),
                source_url="https://example.com",
            )
        )
        session.commit()

        def retain(raw):
            return retain_observations(
                session,
                ticker="TEST",
                content=json.dumps(
                    {
                        "filings": {
                            "recent": {
                                "accessionNumber": ["fixture", "unknown"],
                                "acceptanceDateTime": [raw],
                            }
                        }
                    }
                ).encode(),
                source_url="https://data.sec.gov/submissions/fixture.json",
                cold_root=tmp_path,
                observed_at=now,
            )

        assert retain("2026-08-05T10:00:00Z")["inserted"] == 1
        assert retain("2026-08-05T10:00:00Z")["inserted"] == 0
        assert retain(None)["missing_or_invalid"] == 1
        assert retain("2099-01-01T00:00:00Z")["missing_or_invalid"] == 1
        session.commit()
        assert session.scalar(select(func.count()).select_from(FilingTimingObservation)) == 3
        assert (
            session.scalar(
                select(func.count())
                .select_from(FilingTimingObservation)
                .where(
                    FilingTimingObservation.accepted_at.is_not(None),
                )
            )
            == 1
        )
        assert all(row.archive_path for row in session.scalars(select(FilingTimingObservation)))
    engine.dispose()
