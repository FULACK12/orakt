"""Capacity protection and cold-archive cleanup tests."""

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.storage.archive import ArchiveCapacityError, ArchiveReadError, ColdArchive

CONTENT_HASH = "a" * 64


def roomy_usage(_: Path) -> tuple[int, int, int]:
    """Return a deterministic 10 TB disk with 9 TB free."""
    tebibyte = 1024**4
    return 10 * tebibyte, 1 * tebibyte, 9 * tebibyte


def test_archive_stores_deterministic_compressed_json(tmp_path: Path) -> None:
    archive = ColdArchive(
        tmp_path,
        min_free_bytes=1024**3,
        max_used_percent=85,
        disk_usage_provider=roomy_usage,
    )

    relative_path = archive.store_entry(
        content_hash=CONTENT_HASH,
        source_id=7,
        url="https://example.test/news/1",
        title="Validated headline",
        body="Validated body",
        published_at=datetime(2026, 7, 29, tzinfo=UTC),
        metadata={"license_name": "Test licence"},
    )
    repeated_path = archive.store_entry(
        content_hash=CONTENT_HASH,
        source_id=7,
        url="https://example.test/news/1",
        title="Validated headline",
        body="Validated body",
        published_at=datetime(2026, 7, 29, tzinfo=UTC),
        metadata={"license_name": "Test licence"},
    )

    stored_path = tmp_path / relative_path
    payload = json.loads(gzip.decompress(stored_path.read_bytes()))
    assert repeated_path == relative_path
    assert payload["content_hash"] == CONTENT_HASH
    assert payload["title"] == "Validated headline"
    assert payload["metadata"]["license_name"] == "Test licence"
    assert archive.load_entry(
        relative_path,
        expected_content_hash=CONTENT_HASH,
    )["body"] == "Validated body"


def test_archive_read_rejects_paths_outside_managed_root(tmp_path: Path) -> None:
    archive = ColdArchive(
        tmp_path,
        min_free_bytes=0,
        max_used_percent=99,
        disk_usage_provider=roomy_usage,
    )

    with pytest.raises(ArchiveReadError):
        archive.load_entry("../outside.json.gz")


def test_archive_refuses_write_before_reserve_is_breached(tmp_path: Path) -> None:
    gibibyte = 1024**3

    def nearly_full(_: Path) -> tuple[int, int, int]:
        return 10 * gibibyte, 9 * gibibyte, 1 * gibibyte

    archive = ColdArchive(
        tmp_path,
        min_free_bytes=2 * gibibyte,
        max_used_percent=85,
        disk_usage_provider=nearly_full,
    )

    with pytest.raises(ArchiveCapacityError):
        archive.store_entry(
            content_hash=CONTENT_HASH,
            source_id=1,
            url="https://example.test/news/1",
            title="Capacity protected",
            body="",
            published_at=None,
            metadata={},
        )


def test_cleanup_deletes_only_unreferenced_managed_files(tmp_path: Path) -> None:
    archive = ColdArchive(
        tmp_path,
        min_free_bytes=0,
        max_used_percent=99,
        disk_usage_provider=roomy_usage,
    )
    referenced = archive.store_entry(
        content_hash="a" * 64,
        source_id=1,
        url="https://example.test/a",
        title="A",
        body="",
        published_at=None,
        metadata={},
    )
    orphaned = archive.store_entry(
        content_hash="b" * 64,
        source_id=1,
        url="https://example.test/b",
        title="B",
        body="",
        published_at=None,
        metadata={},
    )

    dry_run = archive.cleanup_orphans([referenced])

    assert dry_run.orphaned_files == 1
    assert dry_run.files_deleted == 0
    assert (tmp_path / orphaned).exists()

    applied = archive.cleanup_orphans([referenced], apply=True)

    assert applied.files_deleted == 1
    assert applied.bytes_reclaimed > 0
    assert (tmp_path / referenced).exists()
    assert not (tmp_path / orphaned).exists()
