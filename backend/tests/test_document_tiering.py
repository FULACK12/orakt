"""Verified cold-full/hot-excerpt document storage tests."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.enums import SourceType
from app.db.models import Document, Source
from app.evidence_quality import can_verify_claims, document_evidence_tier
from app.storage.archive import ColdArchive
from app.storage.document_tiering import (
    document_body_for_research,
    tier_document_batch,
)


def roomy_usage(_: Path) -> tuple[int, int, int]:
    tebibyte = 1024**4
    return 10 * tebibyte, tebibyte, 9 * tebibyte


def test_tiering_archives_full_body_before_trimming_hot_copy(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    archive = ColdArchive(
        tmp_path,
        min_free_bytes=0,
        max_used_percent=99,
        disk_usage_provider=roomy_usage,
    )
    full_body = "complete evidence text " * 300
    with Session(engine) as session:
        source = Source(
            name="Test News",
            country="CA",
            language="en",
            source_type=SourceType.NEWS,
            credibility_baseline=Decimal("0.800"),
        )
        document = Document(
            source=source,
            url="https://example.test/full-story",
            title="A continuing evidence story",
            body=full_body,
            language="en",
            published_at=datetime(2026, 8, 14, tzinfo=UTC),
            content_hash="c" * 64,
            raw_metadata={"collector": "test"},
        )
        session.add(document)
        session.flush()

        result = tier_document_batch(
            session,
            archive,
            hot_body_chars=600,
            apply=True,
        )
        session.flush()

        assert result.archived == 1
        assert result.hot_bodies_trimmed == 1
        assert len(document.body or "") == 600
        assert document.raw_object_path
        hydrated, tier = document_body_for_research(document, archive)
        assert tier == "cold"
        assert hydrated == full_body
        assert document.raw_metadata["full_body_chars"] == len(full_body)
    engine.dispose()


def test_completed_publisher_expansion_is_labeled_full_text() -> None:
    document = Document(
        source_id=1,
        url="https://example.test/full-text",
        title="Expanded article",
        body="Verified publisher article body. " * 20,
        content_hash="f" * 64,
        raw_metadata={"collector": "gdelt_doc_discovery", "full_text_status": "complete"},
    )

    tier = document_evidence_tier(document)

    assert tier == "full_text"
    assert can_verify_claims(tier)


def test_tiering_dry_run_does_not_mutate_document(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    archive = ColdArchive(
        tmp_path,
        min_free_bytes=0,
        max_used_percent=99,
        disk_usage_provider=roomy_usage,
    )
    with Session(engine) as session:
        source = Source(
            name="Test News",
            country="CA",
            language="en",
            source_type=SourceType.NEWS,
            credibility_baseline=Decimal("0.800"),
        )
        document = Document(
            source=source,
            url="https://example.test/dry-run",
            title="Dry run story",
            body="x" * 1_000,
            content_hash="d" * 64,
        )
        session.add(document)
        session.flush()

        result = tier_document_batch(
            session,
            archive,
            hot_body_chars=500,
            apply=False,
        )

        assert result.dry_run is True
        assert result.hot_bodies_trimmed == 1
        assert document.raw_object_path is None
        assert document.body == "x" * 1_000
    engine.dispose()
