"""Capacity-aware, content-addressed cold archive."""

from __future__ import annotations

import gzip
import json
import os
import shutil
import tempfile
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

DiskUsageProvider = Callable[[Path], tuple[int, int, int]]


class ArchiveCapacityError(RuntimeError):
    """Raised before an archive write would breach the configured reserve."""


class ArchiveReadError(RuntimeError):
    """Raised when a managed cold object cannot be safely read or verified."""


class ArchiveCleanupResult(BaseModel):
    """Auditable result of a cold-archive reconciliation pass."""

    model_config = ConfigDict(extra="forbid")

    dry_run: bool
    files_scanned: int
    referenced_files: int
    orphaned_files: int
    files_deleted: int
    bytes_reclaimed: int


class ColdArchive:
    """Store unique feed entries as deterministic gzip-compressed JSON."""

    def __init__(
        self,
        root: Path,
        *,
        min_free_bytes: int,
        max_used_percent: int,
        disk_usage_provider: DiskUsageProvider = shutil.disk_usage,
    ) -> None:
        if min_free_bytes < 0:
            raise ValueError("min_free_bytes must be non-negative")
        if not 1 <= max_used_percent <= 99:
            raise ValueError("max_used_percent must be between 1 and 99")
        self.root = root
        self.min_free_bytes = min_free_bytes
        self.max_used_percent = max_used_percent
        self.disk_usage_provider = disk_usage_provider

    def store_entry(
        self,
        *,
        content_hash: str,
        source_id: int,
        url: str,
        title: str,
        body: str,
        published_at: datetime | None,
        metadata: Mapping[str, Any],
    ) -> str:
        """Atomically archive one validated, unique feed entry."""
        relative_path = self._relative_path(content_hash)
        destination = self.root / Path(relative_path)
        if destination.is_file():
            return relative_path

        payload = {
            "schema_version": 1,
            "content_hash": content_hash,
            "source_id": source_id,
            "url": url,
            "title": title,
            "body": body,
            "published_at": published_at.isoformat() if published_at else None,
            "metadata": dict(metadata),
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        compressed = gzip.compress(encoded, compresslevel=6, mtime=0)
        self._assert_capacity(len(compressed))

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=destination.parent,
                prefix=f".{content_hash}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary.write(compressed)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, destination)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
        return relative_path

    def load_entry(
        self,
        relative_path: str,
        *,
        expected_content_hash: str | None = None,
    ) -> dict[str, Any]:
        """Read and validate one managed JSON document below the archive root."""
        normalized = Path(relative_path)
        if (
            normalized.is_absolute()
            or ".." in normalized.parts
            or normalized.suffixes[-2:] != [".json", ".gz"]
        ):
            raise ArchiveReadError("invalid managed archive path")
        source = self.root / normalized
        try:
            payload = json.loads(gzip.decompress(source.read_bytes()))
        except (OSError, EOFError, gzip.BadGzipFile, json.JSONDecodeError) as exc:
            raise ArchiveReadError(f"cold archive object is unreadable: {relative_path}") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ArchiveReadError("unsupported cold archive document schema")
        content_hash = payload.get("content_hash")
        if not isinstance(content_hash, str):
            raise ArchiveReadError("cold archive document has no content hash")
        if expected_content_hash is not None and content_hash != expected_content_hash:
            raise ArchiveReadError("cold archive content hash does not match database")
        if not isinstance(payload.get("body"), str):
            raise ArchiveReadError("cold archive document has no text body")
        return payload

    def cleanup_orphans(
        self,
        referenced_paths: Iterable[str],
        *,
        apply: bool = False,
    ) -> ArchiveCleanupResult:
        """Delete only managed archive files with no database reference."""
        referenced = {Path(path).as_posix() for path in referenced_paths if path}
        files_scanned = 0
        referenced_files = 0
        orphaned_files = 0
        files_deleted = 0
        bytes_reclaimed = 0
        managed_root = self.root / "raw" / "documents"

        if managed_root.exists():
            for path in managed_root.rglob("*.json.gz"):
                if not path.is_file():
                    continue
                files_scanned += 1
                relative = path.relative_to(self.root).as_posix()
                if relative in referenced:
                    referenced_files += 1
                    continue
                orphaned_files += 1
                size = path.stat().st_size
                if apply:
                    path.unlink()
                    files_deleted += 1
                    bytes_reclaimed += size

        return ArchiveCleanupResult(
            dry_run=not apply,
            files_scanned=files_scanned,
            referenced_files=referenced_files,
            orphaned_files=orphaned_files,
            files_deleted=files_deleted,
            bytes_reclaimed=bytes_reclaimed,
        )

    def ensure_capacity(self, incoming_bytes: int) -> None:
        """Check the configured disk reserve before a bulk archive write."""
        self._assert_capacity(incoming_bytes)

    def store_bytes(self, relative_path: str, payload: bytes) -> str:
        """Atomically store one caller-named blob below the archive root."""
        normalized = Path(relative_path)
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError("archive relative_path must stay below the root")
        destination = self.root / normalized
        if destination.is_file():
            return normalized.as_posix()
        self._assert_capacity(len(payload))
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary.write(payload)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, destination)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
        return normalized.as_posix()

    def _assert_capacity(self, incoming_bytes: int) -> None:
        total, _, free = self.disk_usage_provider(self.root)
        percent_reserve = total * (100 - self.max_used_percent) // 100
        required_reserve = max(self.min_free_bytes, percent_reserve)
        if free - incoming_bytes < required_reserve:
            raise ArchiveCapacityError(
                "cold archive reserve reached; "
                f"free={free}, incoming={incoming_bytes}, reserve={required_reserve}"
            )

    @staticmethod
    def _relative_path(content_hash: str) -> str:
        if len(content_hash) != 64 or any(
            character not in "0123456789abcdef" for character in content_hash
        ):
            raise ValueError("content_hash must be a lowercase SHA-256 hexadecimal digest")
        return (
            f"raw/documents/{content_hash[:2]}/{content_hash[2:4]}/"
            f"{content_hash}.json.gz"
        )
