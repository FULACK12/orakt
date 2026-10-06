"""Validated JSON configuration import for RSS feeds."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import SourceType
from app.db.models import RSSFeed, Source


class RSSFeedConfig(BaseModel):
    """Operator-reviewed policy and schedule for one feed URL."""

    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    enabled: bool = False
    license_name: str = Field(min_length=1, max_length=255)
    license_url: HttpUrl | None = None
    rate_limit_per_minute: Decimal = Field(gt=0, le=60)
    fetch_interval_seconds: int = Field(ge=60, default=900)
    request_timeout_seconds: Decimal = Field(ge=1, le=120, default=Decimal("30"))
    user_agent: str = Field(min_length=1, max_length=255, default="NEWS-App/0.5")


class RSSSourceConfig(BaseModel):
    """Source metadata plus one or more configured feed endpoints."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    country: str | None = None
    language: str | None = Field(default=None, max_length=16)
    ownership: str | None = Field(default=None, max_length=255)
    credibility_baseline: Decimal = Field(ge=0, le=1, default=Decimal("0.500"))
    political_bias_metadata: dict[str, Any] = Field(default_factory=dict)
    feeds: list[RSSFeedConfig] = Field(min_length=1)

    @field_validator("country")
    @classmethod
    def validate_country(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.upper()
        if len(normalized) != 2 or not normalized.isalpha():
            raise ValueError("country must be a two-letter code")
        return normalized


class RSSConfigFile(BaseModel):
    """Top-level import file."""

    model_config = ConfigDict(extra="forbid")

    sources: list[RSSSourceConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def feed_urls_are_unique(self) -> RSSConfigFile:
        urls = [str(feed.url) for source in self.sources for feed in source.feeds]
        if len(urls) != len(set(urls)):
            raise ValueError("feed URLs must be unique")
        return self


class ConfigImportResult(BaseModel):
    """Counts produced by an idempotent configuration import."""

    sources_created: int = 0
    sources_updated: int = 0
    feeds_created: int = 0
    feeds_updated: int = 0


def load_rss_config(path: Path) -> RSSConfigFile:
    """Load and validate an operator-provided UTF-8 JSON file."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return RSSConfigFile.model_validate(payload)


def apply_rss_config(session: Session, config: RSSConfigFile) -> ConfigImportResult:
    """Idempotently create or update source and feed rows."""
    result = ConfigImportResult()
    for source_config in config.sources:
        source = session.scalar(
            select(Source).where(
                Source.name == source_config.name,
                Source.country == source_config.country,
            )
        )
        if source is None:
            source = Source(name=source_config.name, country=source_config.country)
            session.add(source)
            result.sources_created += 1
        else:
            result.sources_updated += 1

        source.language = source_config.language
        source.ownership = source_config.ownership
        source.source_type = SourceType.RSS
        source.credibility_baseline = source_config.credibility_baseline
        source.political_bias_metadata = source_config.political_bias_metadata
        session.flush()

        for feed_config in source_config.feeds:
            feed_url = str(feed_config.url)
            feed = session.scalar(select(RSSFeed).where(RSSFeed.url == feed_url))
            if feed is None:
                feed = RSSFeed(source_id=source.id, url=feed_url)
                session.add(feed)
                result.feeds_created += 1
            else:
                result.feeds_updated += 1

            feed.source_id = source.id
            feed.enabled = feed_config.enabled
            feed.license_name = feed_config.license_name
            feed.license_url = (
                str(feed_config.license_url) if feed_config.license_url else None
            )
            feed.rate_limit_per_minute = feed_config.rate_limit_per_minute
            feed.fetch_interval_seconds = feed_config.fetch_interval_seconds
            feed.request_timeout_seconds = feed_config.request_timeout_seconds
            feed.user_agent = feed_config.user_agent

    session.flush()
    return result
