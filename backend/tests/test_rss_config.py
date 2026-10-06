"""RSS configuration validation and idempotent import tests."""

from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.collectors.config import RSSConfigFile, apply_rss_config
from app.db.base import Base
from app.db.models import RSSFeed, Source


def valid_payload() -> dict[str, object]:
    return {
        "sources": [
            {
                "name": "Test central bank",
                "country": "jp",
                "language": "ja",
                "ownership": "Public institution",
                "credibility_baseline": "0.950",
                "political_bias_metadata": {},
                "feeds": [
                    {
                        "url": "https://feeds.test/central-bank.xml",
                        "enabled": True,
                        "license_name": "Official publication terms",
                        "license_url": "https://feeds.test/terms",
                        "rate_limit_per_minute": "0.500",
                        "fetch_interval_seconds": 900,
                        "request_timeout_seconds": "10.00",
                        "user_agent": "NEWS-App-Test/0.3",
                    }
                ],
            }
        ]
    }


def test_enabled_feed_requires_explicit_license_metadata() -> None:
    payload = valid_payload()
    feed = payload["sources"][0]["feeds"][0]  # type: ignore[index]
    del feed["license_name"]  # type: ignore[index]

    with pytest.raises(ValidationError):
        RSSConfigFile.model_validate(payload)


def test_config_import_is_idempotent() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    config = RSSConfigFile.model_validate(valid_payload())

    with Session(engine) as session:
        created = apply_rss_config(session, config)
        session.commit()
        updated = apply_rss_config(session, config)
        session.commit()

        source = session.scalar(select(Source))
        feed = session.scalar(select(RSSFeed))

    assert created.sources_created == 1
    assert created.feeds_created == 1
    assert updated.sources_updated == 1
    assert updated.feeds_updated == 1
    assert source is not None
    assert source.country == "JP"
    assert feed is not None
    assert feed.license_name == "Official publication terms"
    assert feed.rate_limit_per_minute == Decimal("0.500")
    engine.dispose()

