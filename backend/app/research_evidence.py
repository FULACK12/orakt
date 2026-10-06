"""Question-directed local evidence retrieval for autonomous research."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.data_quality import audit_market_rows, valid_market_rows
from app.db.models import Document, Event, MarketObservation, MarketSeries, Source
from app.evidence_quality import can_verify_claims, document_evidence_tier
from app.storage.archive import ColdArchive
from app.storage.document_tiering import document_body_for_research

SEARCH_STOPWORDS = {
    "about",
    "after",
    "before",
    "between",
    "could",
    "during",
    "from",
    "have",
    "into",
    "more",
    "most",
    "other",
    "should",
    "than",
    "that",
    "their",
    "then",
    "there",
    "these",
    "this",
    "through",
    "whether",
    "which",
    "with",
    "would",
    "是否",
    "什么",
    "如何",
    "影响",
    "当前",
    "之间",
    "可以",
    "可能",
    "数据",
    "证据",
}

MARKET_QUERY_ALIASES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("mu", "micron", "美光"), ("EQ:MU",)),
    (("2y", "10y", "treasury", "yield", "美债", "收益率"), ("DGS2", "DGS10", "T10Y2Y")),
    (("vix", "波动率"), ("VIXCLS",)),
    (("dollar", "usd", "美元"), ("DTWEXBGS",)),
    (("s&p", "sp500", "标普"), ("SP500",)),
    (("nasdaq", "纳指"), ("NASDAQCOM",)),
    (("liquidity", "流动性"), ("M2SL", "NFCI")),
    (("oil", "crude", "原油"), ("DCOILWTICO",)),
)

MARKET_SEARCH_EXCLUDED_CATEGORIES = {
    "company_fundamental",
    "equity_factor",
    "equity_turnover",
    "equity_turnover_rate",
    "equity_volume",
    "historical_equity_price",
    "valuation",
}


def enrich_research_evidence(
    session: Session,
    evidence: dict[str, Any],
    *,
    question: str,
    episode_start: date | None = None,
    episode_end: date | None = None,
    required_refs: list[str] | None = None,
    extra_queries: list[str] | None = None,
    pass_name: str = "question_search",
) -> dict[str, Any]:
    """Retrieve local records after the question is known and retain a report."""
    required = list(dict.fromkeys(required_refs or []))
    query_text = " ".join([question, *(extra_queries or [])]).strip()
    terms = _search_terms(query_text)
    start, end = _bounded_window(episode_start, episode_end)
    before_ids = _evidence_ids(evidence)

    documents = _retrieve_documents(
        session,
        terms=terms,
        start=start,
        end=end,
        required_refs=required,
    )
    events = _retrieve_events(
        session,
        terms=terms,
        start=start,
        end=end,
        required_refs=required,
    )
    selected_market_ids = _selected_market_series(
        session,
        terms=terms,
        required_refs=required,
        target_series_id=_target_equity_series_id(evidence),
    )
    market_observations, market_windows, market_quality = _retrieve_market_windows(
        session,
        series_ids=selected_market_ids,
        start=start,
        end=end,
    )

    added_by_section = {
        "documents": _merge_evidence(evidence, "documents", documents),
        "events": _merge_evidence(evidence, "events", events),
        "market_observations": _merge_evidence(
            evidence,
            "market_observations",
            market_observations,
        ),
        "market_window_statistics": _merge_evidence(
            evidence,
            "market_window_statistics",
            market_windows,
        ),
        "market_data_quality": _merge_evidence(
            evidence,
            "market_data_quality",
            market_quality,
        ),
    }
    priority_refs = list(
        dict.fromkeys(
            [
                *required,
                *(item["evidence_id"] for item in market_windows),
                *(item["evidence_id"] for item in documents[:12]),
                *(item["evidence_id"] for item in events[:8]),
            ]
        )
    )
    evidence["priority_evidence"] = _items_for_refs(evidence, priority_refs)[:48]
    evidence["news_evidence_sequences"] = build_news_evidence_sequences(
        evidence.get("documents") or [],
        focus=query_text,
    )
    evidence["news_forecast_anchors"] = build_news_forecast_anchors(
        evidence.get("documents") or [],
        exclude_refs=set(evidence.get("forecasted_news_refs") or []),
    )

    after_ids = _evidence_ids(evidence)
    unresolved_required_refs = [ref for ref in required if ref not in after_ids]
    report = {
        "pass": pass_name,
        "searched_at": datetime.now(UTC).isoformat(),
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "search_terms": terms[:24],
        "required_ref_count": len(required),
        "required_ref_hits": len(required) - len(unresolved_required_refs),
        "unresolved_required_refs": unresolved_required_refs,
        "selected_market_series": selected_market_ids,
        "added_by_section": added_by_section,
        "added_total": len(after_ids - before_ids),
        "available_total": len(after_ids),
    }
    reports = evidence.setdefault("evidence_retrieval", [])
    if isinstance(reports, list):
        reports.append(report)
    return report


def _bounded_window(
    start: date | None,
    end: date | None,
) -> tuple[date, date]:
    today = datetime.now(UTC).date()
    resolved_end = min(end or today, today)
    resolved_start = start or (resolved_end - timedelta(days=550))
    if resolved_start > resolved_end:
        resolved_start, resolved_end = resolved_end, resolved_start
    if (resolved_end - resolved_start).days > 550:
        resolved_start = resolved_end - timedelta(days=550)
    return resolved_start, resolved_end


def _retrieve_documents(
    session: Session,
    *,
    terms: list[str],
    start: date,
    end: date,
    required_refs: list[str],
) -> list[dict[str, Any]]:
    start_at = datetime.combine(start - timedelta(days=14), datetime.min.time(), UTC)
    end_at = datetime.combine(end + timedelta(days=14), datetime.max.time(), UTC)
    rows = list(
        session.execute(
            select(Document, Source)
            .join(Source, Source.id == Document.source_id)
            .where(
                Document.published_at.is_not(None),
                Document.published_at >= start_at,
                Document.published_at <= end_at,
            )
            .order_by(desc(Document.published_at), desc(Document.id))
            .limit(4_000)
        )
    )
    required_ids = {
        int(match.group(1))
        for ref in required_refs
        if (match := re.fullmatch(r"document:(\d+)", ref))
    }
    missing_required = required_ids - {document.id for document, _ in rows}
    if missing_required:
        rows.extend(
            session.execute(
                select(Document, Source)
                .join(Source, Source.id == Document.source_id)
                .where(Document.id.in_(missing_required))
            )
        )
    ranked = sorted(
        rows,
        key=lambda row: (
            row[0].id in required_ids,
            _term_score(f"{row[0].title} {row[0].body or ''}", terms),
            row[0].published_at or row[0].fetched_at,
        ),
        reverse=True,
    )
    retained = [
        row
        for row in ranked
        if row[0].id in required_ids
        or _term_score(f"{row[0].title} {row[0].body or ''}", terms) > 0
    ][:60]
    settings = get_settings()
    archive = ColdArchive(
        settings.cold_data_root,
        min_free_bytes=settings.cold_archive_min_free_gb * 1024**3,
        max_used_percent=settings.cold_archive_max_used_percent,
    )
    result: list[dict[str, Any]] = []
    for document, source in retained:
        full_body, read_tier = document_body_for_research(document, archive)
        result.append(
            {
                "evidence_id": f"document:{document.id}",
                "category": "news_or_official_document",
                "title": document.title[:500],
                "published_at": (
                    document.published_at.isoformat() if document.published_at else None
                ),
                "source": source.name,
                "source_country": source.country,
                "language": document.language or source.language,
                "source_url": document.url,
                "excerpt": full_body[:1_200],
                "content_storage": read_tier,
                "full_body_chars": int(
                    (document.raw_metadata or {}).get("full_body_chars") or len(full_body)
                ),
                "evidence_tier": document_evidence_tier(document),
                "can_verify_claims": can_verify_claims(
                    document_evidence_tier(document)
                ),
                "retrieval_score": _term_score(f"{document.title} {document.body or ''}", terms),
            }
        )
    return result


def build_news_evidence_sequences(
    documents: list[dict[str, Any]],
    *,
    focus: str,
    max_sequences: int = 6,
) -> list[dict[str, Any]]:
    """Link strongly related dated reports without presenting chronology as causality."""
    focus_terms = set(_search_terms(focus))
    candidates: list[dict[str, Any]] = []
    for item in documents:
        if not isinstance(item, dict) or not item.get("published_at"):
            continue
        text = f"{item.get('title') or ''} {item.get('excerpt') or ''}"
        terms = set(_search_terms(text))
        if len(terms) < 2:
            continue
        try:
            published = datetime.fromisoformat(str(item["published_at"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        candidates.append({"item": item, "terms": terms, "published": published})
    candidates.sort(key=lambda value: value["published"])

    groups: list[dict[str, Any]] = []
    for candidate in candidates:
        best: dict[str, Any] | None = None
        best_score = 0
        for group in groups:
            gap_days = abs((candidate["published"] - group["latest"]).days)
            if gap_days > 120:
                continue
            shared = candidate["terms"] & group["terms"]
            focus_shared = shared & focus_terms
            score = len(shared) * 2 + len(focus_shared) * 3
            if len(shared) >= 2 and score > best_score:
                best = group
                best_score = score
        if best is None:
            groups.append(
                {
                    "items": [candidate],
                    "terms": set(candidate["terms"]),
                    "latest": candidate["published"],
                }
            )
            continue
        best["items"].append(candidate)
        best["terms"].update(candidate["terms"])
        best["latest"] = max(best["latest"], candidate["published"])

    eligible = [group for group in groups if len(group["items"]) >= 2]
    eligible.sort(
        key=lambda group: (
            len(group["items"]),
            len(group["terms"] & focus_terms),
            group["latest"],
        ),
        reverse=True,
    )
    sequences: list[dict[str, Any]] = []
    for sequence_number, group in enumerate(eligible[:max_sequences], start=1):
        ordered = sorted(group["items"], key=lambda value: value["published"])
        entries = []
        for index, candidate in enumerate(ordered):
            item = candidate["item"]
            relation = (
                "initial_report"
                if index == 0
                else "latest_report"
                if index == len(ordered) - 1
                else "follow_up_report"
            )
            entries.append(
                {
                    "sequence": index + 1,
                    "relation": relation,
                    "evidence_id": item.get("evidence_id"),
                    "title": item.get("title"),
                    "published_at": item.get("published_at"),
                    "source": item.get("source"),
                    "source_url": item.get("source_url"),
                    "evidence_status": (
                        "source_text" if item.get("can_verify_claims") else "lead_only"
                    ),
                    "content_storage": item.get("content_storage", "hot"),
                }
            )
        sequences.append(
            {
                "sequence_id": f"news-sequence:{sequence_number}",
                "title": ordered[0]["item"].get("title"),
                "starts_at": ordered[0]["item"].get("published_at"),
                "ends_at": ordered[-1]["item"].get("published_at"),
                "report_count": len(entries),
                "causal_status": "chronology_only_until_validated",
                "entries": entries,
            }
        )
    return sequences


def build_news_forecast_anchors(
    documents: list[dict[str, Any]],
    *,
    limit: int = 4,
    exclude_refs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Select substantive dated news items for timestamped possibility analysis."""
    retained = [
        item
        for item in documents
        if isinstance(item, dict)
        and item.get("published_at")
        and item.get("can_verify_claims")
        and item.get("evidence_id")
    ]
    excluded = exclude_refs or set()
    retained.sort(
        key=lambda item: (
            str(item.get("evidence_id")) not in excluded,
            str(item["published_at"]),
        ),
        reverse=True,
    )
    return [
        {
            "evidence_id": item["evidence_id"],
            "title": item.get("title"),
            "published_at": item.get("published_at"),
            "source": item.get("source"),
            "source_url": item.get("source_url"),
            "excerpt": str(item.get("excerpt") or "")[:1_200],
            "instruction": (
                "Use only evidence available at or before published_at when drafting "
                "the forecast; later observations belong only to walk-forward validation."
            ),
        }
        for item in retained[:limit]
    ]


def _retrieve_events(
    session: Session,
    *,
    terms: list[str],
    start: date,
    end: date,
    required_refs: list[str],
) -> list[dict[str, Any]]:
    start_at = datetime.combine(start, datetime.min.time(), UTC)
    end_at = datetime.combine(end, datetime.max.time(), UTC)
    rows = list(
        session.scalars(
            select(Event)
            .where(Event.start_at >= start_at, Event.start_at <= end_at)
            .order_by(desc(Event.start_at), desc(Event.id))
            .limit(2_000)
        )
    )
    required_ids = {
        int(match.group(1)) for ref in required_refs if (match := re.fullmatch(r"event:(\d+)", ref))
    }
    missing_required = required_ids - {event.id for event in rows}
    if missing_required:
        rows.extend(session.scalars(select(Event).where(Event.id.in_(missing_required))))
    rows.sort(
        key=lambda event: (
            event.id in required_ids,
            _term_score(f"{event.title} {event.summary or ''} {event.event_type}", terms),
            event.start_at,
        ),
        reverse=True,
    )
    retained = [
        event
        for event in rows
        if event.id in required_ids
        or _term_score(f"{event.title} {event.summary or ''} {event.event_type}", terms) > 0
    ][:50]
    return [
        {
            "evidence_id": f"event:{event.id}",
            "category": "canonical_event",
            "title": event.title,
            "summary": (event.summary or "")[:1_000],
            "event_type": event.event_type,
            "occurred_at": event.start_at.isoformat(),
            "country_code": event.country_code,
            "latitude": float(event.latitude) if event.latitude is not None else None,
            "longitude": float(event.longitude) if event.longitude is not None else None,
            "confidence": float(event.confidence),
        }
        for event in retained
    ]


def _selected_market_series(
    session: Session,
    *,
    terms: list[str],
    required_refs: list[str],
    target_series_id: str | None = None,
) -> list[str]:
    required_series = {
        match.group(1)
        for ref in required_refs
        if (match := re.fullmatch(r"market:(.+):\d{4}-\d{2}-\d{2}", ref))
    }
    joined_terms = " ".join(terms)
    alias_series = [
        series_id
        for aliases, series_ids in MARKET_QUERY_ALIASES
        if any(alias in joined_terms for alias in aliases)
        for series_id in series_ids
    ]
    series = list(
        session.scalars(
            select(MarketSeries).where(
                ~MarketSeries.category.in_(MARKET_SEARCH_EXCLUDED_CATEGORIES)
            )
        )
    )
    series.sort(
        key=lambda item: (
            item.series_id in required_series,
            _term_score(
                f"{item.series_id} {item.name} {item.category}",
                terms,
            ),
        ),
        reverse=True,
    )
    available_ids = {item.series_id for item in series}
    selected = list(required_series)
    if target_series_id in available_ids and target_series_id not in selected:
        selected.insert(0, target_series_id)
    series_by_id = {item.series_id: item for item in series}
    selected.extend(
        series_id
        for series_id in alias_series
        if series_id in available_ids
        and series_id not in selected
        and not _is_unrelated_equity_series(
            series_by_id[series_id],
            target_series_id=target_series_id,
        )
    )
    if any(series_id.startswith("EQ:") for series_id in selected) and len(selected) >= 6:
        return selected[:12]
    for item in series:
        if item.series_id in selected:
            continue
        if _is_unrelated_equity_series(item, target_series_id=target_series_id):
            continue
        score = _term_score(
            f"{item.series_id} {item.name} {item.category}", terms
        )
        if score <= 0:
            continue
        selected.append(item.series_id)
        if len(selected) >= 12:
            break
    return selected[:12]


def _target_equity_series_id(evidence: dict[str, Any]) -> str | None:
    context = evidence.get("equity_research_context")
    if not isinstance(context, dict):
        return None
    value = context.get("price_series_id")
    return str(value) if isinstance(value, str) and value.strip() else None


def _is_unrelated_equity_series(
    series: MarketSeries,
    *,
    target_series_id: str | None,
) -> bool:
    """Keep fuzzy macro search from silently adding other companies to a report."""
    return bool(
        target_series_id
        and series.series_id != target_series_id
        and series.category in {"equity_price", "historical_equity_price"}
    )


def _retrieve_market_windows(
    session: Session,
    *,
    series_ids: list[str],
    start: date,
    end: date,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    observations: list[dict[str, Any]] = []
    windows: list[dict[str, Any]] = []
    quality_reports: list[dict[str, Any]] = []
    for series_id in series_ids:
        series = session.get(MarketSeries, series_id)
        if series is None:
            continue
        rows = list(
            session.scalars(
                select(MarketObservation)
                .where(
                    MarketObservation.series_id == series_id,
                    MarketObservation.observed_on >= start,
                    MarketObservation.observed_on <= end,
                )
                .order_by(MarketObservation.observed_on)
                .limit(4_000)
            )
        )
        quality = audit_market_rows(
            series,
            rows,
            window_start=start,
            window_end=end,
        )
        quality_item = quality.model_dump(mode="json")
        quality_item["evidence_id"] = f"quality:market:{series_id}:{start}:{end}"
        quality_reports.append(quality_item)
        valid_rows, _ = valid_market_rows(series, rows)
        if not quality.can_verify_claims or not valid_rows:
            continue
        representative = _representative_market_rows(valid_rows)
        observations.extend(
            {
                "evidence_id": (f"market:{series_id}:{row.observed_on.isoformat()}"),
                "category": series.category,
                "series_id": series_id,
                "name": series.name,
                "observed_on": row.observed_on.isoformat(),
                "value": row.value,
                "unit": series.unit,
                "source": series.source_name,
                "source_url": series.source_url,
            }
            for row in representative
        )
        values = [float(row.value) for row in valid_rows]
        first_value = values[0]
        last_value = values[-1]
        windows.append(
            {
                "evidence_id": (
                    f"derived:market-window:{series_id}:"
                    f"{valid_rows[0].observed_on.isoformat()}:"
                    f"{valid_rows[-1].observed_on.isoformat()}"
                ),
                "category": "derived_market_window",
                "series_id": series_id,
                "name": series.name,
                "window_start": valid_rows[0].observed_on.isoformat(),
                "window_end": valid_rows[-1].observed_on.isoformat(),
                "observation_count": len(valid_rows),
                "first_value": first_value,
                "last_value": last_value,
                "absolute_change": last_value - first_value,
                "percent_change": ((last_value / first_value - 1) if first_value != 0 else None),
                "minimum": min(values),
                "maximum": max(values),
                "mean": sum(values) / len(values),
                "unit": series.unit,
                "source": series.source_name,
                "source_url": series.source_url,
                "calculation": "Local descriptive statistics from retained observations",
                "can_verify_claims": True,
            }
        )
    return observations, windows, quality_reports


def _representative_market_rows(
    rows: list[MarketObservation],
) -> list[MarketObservation]:
    if len(rows) <= 8:
        return rows
    indices = {0, len(rows) - 1, len(rows) // 4, len(rows) // 2, 3 * len(rows) // 4}
    indices.add(min(range(len(rows)), key=lambda index: float(rows[index].value)))
    indices.add(max(range(len(rows)), key=lambda index: float(rows[index].value)))
    return [rows[index] for index in sorted(indices)]


def _merge_evidence(
    evidence: dict[str, Any],
    section: str,
    new_items: list[dict[str, Any]],
) -> int:
    existing = evidence.get(section)
    values = existing if isinstance(existing, list) else []
    known = {
        item.get("evidence_id")
        for item in values
        if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
    }
    additions = [item for item in new_items if item.get("evidence_id") not in known]
    evidence[section] = [*additions, *values]
    return len(additions)


def _items_for_refs(
    evidence: dict[str, Any],
    refs: list[str],
) -> list[dict[str, Any]]:
    items_by_id: dict[str, dict[str, Any]] = {}
    for value in evidence.values():
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            evidence_id = item.get("evidence_id")
            if isinstance(evidence_id, str) and evidence_id in refs:
                items_by_id.setdefault(evidence_id, dict(item))
    return [items_by_id[ref] for ref in refs if ref in items_by_id]


def _evidence_ids(evidence: dict[str, Any]) -> set[str]:
    return {
        item["evidence_id"]
        for value in evidence.values()
        if isinstance(value, list)
        for item in value
        if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
    }


def _search_terms(text: str) -> list[str]:
    raw = re.findall(
        r"[a-zA-Z][a-zA-Z0-9._/-]{1,30}|[\u4e00-\u9fff]{2,8}",
        text.casefold(),
    )
    terms: list[str] = []
    for value in raw:
        term = value.strip("._-/")
        if len(term) < 2 or term in SEARCH_STOPWORDS or term in terms:
            continue
        terms.append(term)
    return terms[:48]


def _term_score(text: str, terms: list[str]) -> int:
    lowered = text.casefold()
    latin_counts = Counter(re.findall(r"[a-z0-9][a-z0-9._/-]{1,}", lowered))
    score = 0
    for term in terms:
        count = latin_counts.get(term, 0) if term.isascii() else lowered.count(term)
        if count:
            score += 3 if count > 1 else 1
    return score


def evidence_subject_key(item: dict[str, Any]) -> str:
    """Return the measured subject so a series cannot cause itself."""
    section = str(item.get("episode_section") or "")
    if section == "market_observations":
        return f"market:{item.get('series_id') or item.get('name')}"
    if section == "economic_observations":
        return f"economic:{item.get('country')}:{item.get('indicator_code')}"
    if section == "energy_observations":
        return f"energy:{item.get('series_id') or item.get('name')}"
    if section == "company_financials":
        return f"company:{item.get('ticker')}:{item.get('concept')}"
    return str(item.get("evidence_id") or json.dumps(item, sort_keys=True))
