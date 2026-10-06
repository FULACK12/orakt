"""Walk-forward retrieval for timestamped post-news forecasts."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import Document, MarketObservation, MarketSeries, Source
from app.evidence_quality import document_evidence_tier
from app.schemas.research import ModelNewsForecast

STOPWORDS = {
    "after",
    "could",
    "expected",
    "from",
    "into",
    "might",
    "outcome",
    "through",
    "within",
    "would",
    "可能",
    "导致",
    "通过",
    "之后",
    "结果",
}


def build_forecast_validation_cases(
    session: Session,
    forecasts: list[ModelNewsForecast],
) -> list[dict[str, Any]]:
    """Retrieve only evidence timestamped after each forecast cutoff."""
    now = datetime.now(UTC)
    cases: list[dict[str, Any]] = []
    for forecast in forecasts:
        horizon_end = min(
            forecast.as_of + timedelta(days=forecast.horizon_days),
            now,
        )
        if horizon_end <= forecast.as_of:
            continue
        query = " ".join(
            [
                forecast.anchor_title,
                forecast.hypothesis,
                *forecast.mechanism_chain,
                forecast.expected_outcome,
            ]
        )
        terms = _terms(query)
        later_documents = _later_documents(
            session,
            terms=terms,
            start=forecast.as_of,
            end=horizon_end,
        )
        market_changes = _market_changes(
            session,
            terms=terms,
            start=forecast.as_of,
            end=horizon_end,
        )
        candidates = [*later_documents, *market_changes]
        if not candidates:
            continue
        cases.append(
            {
                "forecast": forecast.model_dump(mode="json"),
                "validation_window": {
                    "start": forecast.as_of.isoformat(),
                    "end": horizon_end.isoformat(),
                    "horizon_complete": now
                    >= forecast.as_of + timedelta(days=forecast.horizon_days),
                },
                "candidate_evidence": candidates[:30],
            }
        )
    return cases


def _later_documents(
    session: Session,
    *,
    terms: list[str],
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    rows = list(
        session.execute(
            select(Document, Source)
            .join(Source, Source.id == Document.source_id)
            .where(
                Document.published_at > start,
                Document.published_at <= end,
            )
            .order_by(desc(Document.published_at), desc(Document.id))
            .limit(4_000)
        )
    )
    ranked = sorted(
        rows,
        key=lambda row: _score(f"{row[0].title} {row[0].body or ''}", terms),
        reverse=True,
    )
    result: list[dict[str, Any]] = []
    for document, source in ranked:
        score = _score(f"{document.title} {document.body or ''}", terms)
        if score < 2:
            continue
        tier = document_evidence_tier(document)
        result.append(
            {
                "evidence_id": f"document:{document.id}",
                "type": "later_news",
                "title": document.title[:500],
                "published_at": document.published_at.isoformat()
                if document.published_at
                else None,
                "source": source.name,
                "source_url": document.url,
                "excerpt": (document.body or "")[:900],
                "can_verify_claims": tier in {"feed_content", "official_or_structured"},
                "retrieval_score": score,
            }
        )
        if len(result) >= 18:
            break
    return result


def _market_changes(
    session: Session,
    *,
    terms: list[str],
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    start_date = start.date()
    end_date = end.date()
    series = list(session.scalars(select(MarketSeries)))
    series.sort(
        key=lambda item: _score(
            f"{item.series_id} {item.name} {item.category}",
            terms,
        ),
        reverse=True,
    )
    result: list[dict[str, Any]] = []
    for item in series[:12]:
        if _score(f"{item.series_id} {item.name} {item.category}", terms) <= 0:
            continue
        before = session.scalar(
            select(MarketObservation)
            .where(
                MarketObservation.series_id == item.series_id,
                MarketObservation.observed_on <= start_date,
            )
            .order_by(desc(MarketObservation.observed_on))
            .limit(1)
        )
        after = session.scalar(
            select(MarketObservation)
            .where(
                MarketObservation.series_id == item.series_id,
                MarketObservation.observed_on > start_date,
                MarketObservation.observed_on <= end_date,
            )
            .order_by(desc(MarketObservation.observed_on))
            .limit(1)
        )
        if before is None or after is None:
            continue
        first = float(before.value)
        last = float(after.value)
        result.append(
            {
                "evidence_id": (
                    f"forecast-market:{item.series_id}:"
                    f"{before.observed_on.isoformat()}:{after.observed_on.isoformat()}"
                ),
                "type": "post_forecast_market_change",
                "series_id": item.series_id,
                "name": item.name,
                "window_start": before.observed_on.isoformat(),
                "window_end": after.observed_on.isoformat(),
                "first_value": first,
                "last_value": last,
                "absolute_change": last - first,
                "percent_change": (last / first - 1) if first else None,
                "unit": item.unit,
                "source": item.source_name,
                "source_url": item.source_url,
                "can_verify_claims": True,
            }
        )
    return result[:12]


def _terms(text: str) -> list[str]:
    values = re.findall(
        r"[a-zA-Z][a-zA-Z0-9._/-]{1,30}|[\u4e00-\u9fff]{2,8}",
        text.casefold(),
    )
    return list(
        dict.fromkeys(
            value.strip("._-/")
            for value in values
            if len(value.strip("._-/")) >= 2 and value.strip("._-/") not in STOPWORDS
        )
    )[:48]


def _score(text: str, terms: list[str]) -> int:
    lowered = text.casefold()
    words = set(re.findall(r"[a-z0-9][a-z0-9._/-]{1,}", lowered))
    return sum(1 for term in terms if (term in words if term.isascii() else term in lowered))
