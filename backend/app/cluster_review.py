"""Tamper-evident signatures for reviewed clustering previews."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, cast

from app.schemas.clusters import ClusterPreviewResponse


def sign_cluster_preview(
    preview: ClusterPreviewResponse,
    secret: str,
) -> ClusterPreviewResponse:
    """Return a copy carrying an HMAC over every reviewable field."""
    signature = _signature(preview, secret)
    return preview.model_copy(update={"review_signature": signature})


def verify_cluster_preview(
    preview: ClusterPreviewResponse,
    secret: str,
) -> bool:
    """Verify that a submitted preview is exactly the server-signed snapshot."""
    expected = _signature(preview, secret)
    if hmac.compare_digest(preview.review_signature, expected):
        return True
    legacy_expected = _signature(
        preview,
        secret,
        omit_empty_impact=True,
    )
    return hmac.compare_digest(preview.review_signature, legacy_expected)


def _signature(
    preview: ClusterPreviewResponse,
    secret: str,
    *,
    omit_empty_impact: bool = False,
) -> str:
    payload = preview.model_dump(
        mode="json",
        exclude={"review_signature"},
    )
    if omit_empty_impact:
        payload = cast(dict[str, Any], _remove_empty_impact(payload))
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hmac.new(
        secret.encode("utf-8"),
        canonical,
        hashlib.sha256,
    ).hexdigest()


def _remove_empty_impact(value: object) -> object:
    """Reproduce the v0.13 payload shape for stored signed previews."""
    if isinstance(value, list):
        return [_remove_empty_impact(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _remove_empty_impact(item)
            for key, item in value.items()
            if key != "impact" or item is not None
        }
    return value
