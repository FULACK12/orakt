"""SQLAlchemy model and integrity tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.enums import DocumentStance, EventStatus, SourceType
from app.db.models import Document, Event, EventDocument, Source


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    engine.dispose()


def test_event_can_be_linked_to_source_document(session: Session) -> None:
    source = Source(
        name="Bank of Japan",
        country="JP",
        language="ja",
        source_type=SourceType.CENTRAL_BANK,
        credibility_baseline=Decimal("0.950"),
    )
    document = Document(
        source=source,
        url="https://example.test/boj/rate-decision",
        title="Policy rate decision",
        body="The policy rate was changed.",
        language="en",
        published_at=datetime(2026, 7, 29, tzinfo=UTC),
        content_hash="a" * 64,
    )
    event = Event(
        event_type="interest_rate_change",
        title="Bank of Japan raises policy rate",
        status=EventStatus.CONFIRMED,
        severity=Decimal("0.700"),
        novelty=Decimal("0.600"),
        confidence=Decimal("0.950"),
        start_at=datetime(2026, 7, 29, tzinfo=UTC),
        latitude=Decimal("35.676200"),
        longitude=Decimal("139.650300"),
        country_code="JP",
    )
    event.document_links.append(
        EventDocument(
            document=document,
            relevance_score=Decimal("1.000"),
            stance=DocumentStance.SUPPORTS,
            is_primary_source=True,
        )
    )
    session.add(event)
    session.commit()

    stored_event = session.scalar(select(Event).where(Event.country_code == "JP"))

    assert stored_event is not None
    assert stored_event.status is EventStatus.CONFIRMED
    assert len(stored_event.document_links) == 1
    assert stored_event.document_links[0].document.source.name == "Bank of Japan"
    assert stored_event.document_links[0].stance is DocumentStance.SUPPORTS


def test_event_score_constraints_are_enforced(session: Session) -> None:
    session.add(
        Event(
            event_type="test",
            title="Invalid confidence",
            severity=Decimal("0.500"),
            novelty=Decimal("0.500"),
            confidence=Decimal("1.500"),
            start_at=datetime(2026, 7, 29, tzinfo=UTC),
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()
