"""Resolve proposed causal segments to quality-gated local numerical evidence."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data_quality import audit_market_rows, valid_market_rows
from app.db.models import EnergyObservation, EnergySeries, MarketObservation, MarketSeries
from app.schemas.data_audit import (
    BridgeEvidenceCandidateView,
    BridgeEvidenceSegmentView,
    EvidenceCompletionView,
    SeriesQualityView,
)
from app.schemas.research import ModelResearchResult

TOKEN_PATTERN = re.compile(r"[a-z][a-z0-9.-]{2,}|[\u4e00-\u9fff]{2,10}")
STOPWORDS = {
    "from",
    "into",
    "through",
    "with",
    "是否",
    "影响",
    "变化",
    "检验",
    "传导",
    "数据",
}
SERIES_HINTS: tuple[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("credit", "spread", "funding", "financing", "信用", "融资"),
        ("BAMLH0A0HYM2", "NFCI", "DGS2", "DFF", "TDSP"),
        ("credit spread", "financial conditions", "debt service"),
    ),
    (
        ("industrial", "electricity", "demand", "需求", "工业", "电力"),
        ("INDPRO", "TCU", "CFNAI", "PAYEMS"),
        ("industrial production", "electric power", "coal consumption"),
    ),
    (
        ("inventory", "procurement", "库存", "采购"),
        ("BUSINV", "ISRATIO"),
        ("coal stocks", "inventory", "receipts"),
    ),
    (
        ("freight", "shipping", "rail", "port", "运费", "海运", "铁路", "港口"),
        (),
        ("freight", "rail", "transportation", "port"),
    ),
    (
        ("foreign exchange", "fx", "currency", "汇率", "美元"),
        ("DTWEXBGS",),
        ("trade weighted", "exchange rate"),
    ),
    (
        ("coal", "steam coal", "煤", "焦炭"),
        (),
        ("coal price", "steam coal", "coal imports", "coal production"),
    ),
    (
        ("oil", "crude", "原油", "石油"),
        ("DCOILWTICO",),
        ("crude oil", "brent", "petroleum"),
    ),
)
MINIMUM_CANDIDATE_RELEVANCE = 16.0


def complete_research_evidence(
    session: Session,
    *,
    result: ModelResearchResult,
    evidence: dict[str, Any],
    window_start: date,
    window_end: date,
) -> EvidenceCompletionView:
    """Match every adjacent hypothesis step to measured local candidate data."""
    market_series = list(session.scalars(select(MarketSeries)))
    energy_series = list(
        session.scalars(select(EnergySeries).where(EnergySeries.materialized.is_(True)))
    )
    segments: list[BridgeEvidenceSegmentView] = []
    added_refs: list[str] = []
    nonlinear_by_hypothesis = {
        int(match.group(1)): link.linear_segments
        for link in (result.factor_research.nonlinear_links if result.factor_research else [])
        if (match := re.search(r"h(\d+)$", link.link_id)) and link.linear_segments
    }
    for hypothesis_index, hypothesis in enumerate(result.hypotheses, start=1):
        factor_segments = nonlinear_by_hypothesis.get(hypothesis_index, [])
        raw_segments = (
            [(item.source, item.target) for item in factor_segments]
            if factor_segments
            else [
                (source.label, target.label)
                for source, target in zip(
                    hypothesis.steps,
                    hypothesis.steps[1:],
                    strict=False,
                )
            ]
        )
        for sequence, (source_label, target_label) in enumerate(raw_segments, start=1):
            text = f"{source_label} {target_label}"
            terms, hinted_ids, hinted_names = _query_plan(text)
            ranked_market = sorted(
                market_series,
                key=lambda series: _series_score(
                    series.series_id,
                    f"{series.name} {series.category}",
                    terms=terms,
                    hinted_ids=hinted_ids,
                    hinted_names=hinted_names,
                ),
                reverse=True,
            )
            ranked_energy = sorted(
                energy_series,
                key=lambda series: _series_score(
                    series.series_id,
                    f"{series.name} {series.units or ''}",
                    terms=terms,
                    hinted_ids=hinted_ids,
                    hinted_names=hinted_names,
                ),
                reverse=True,
            )
            candidates: list[BridgeEvidenceCandidateView] = []
            for market_item in ranked_market[:8]:
                relevance = _series_score(
                    market_item.series_id,
                    f"{market_item.name} {market_item.category}",
                    terms=terms,
                    hinted_ids=hinted_ids,
                    hinted_names=hinted_names,
                )
                if relevance < MINIMUM_CANDIDATE_RELEVANCE:
                    continue
                candidate, refs = _market_candidate(
                    session,
                    series=market_item,
                    relevance=relevance,
                    window_start=window_start,
                    window_end=window_end,
                    evidence=evidence,
                )
                candidates.append(candidate)
                added_refs.extend(refs)
                if len(candidates) >= 4:
                    break
            if len(candidates) < 6:
                for energy_item in ranked_energy[:8]:
                    relevance = _series_score(
                        energy_item.series_id,
                        f"{energy_item.name} {energy_item.units or ''}",
                        terms=terms,
                        hinted_ids=hinted_ids,
                        hinted_names=hinted_names,
                    )
                    if relevance < MINIMUM_CANDIDATE_RELEVANCE:
                        continue
                    candidate, refs = _energy_candidate(
                        session,
                        series=energy_item,
                        relevance=relevance,
                        window_start=window_start,
                        window_end=window_end,
                        evidence=evidence,
                    )
                    candidates.append(candidate)
                    added_refs.extend(refs)
                    if len(candidates) >= 6:
                        break
            usable = [item for item in candidates if item.quality.can_verify_claims]
            rejected = [item for item in candidates if not item.quality.can_verify_claims]
            status: Literal[
                "candidate_data_found",
                "partial_data",
                "missing_data",
                "rejected_anomaly",
            ]
            if usable and rejected:
                status = "partial_data"
            elif usable:
                status = "candidate_data_found"
            elif candidates:
                status = "rejected_anomaly"
            else:
                status = "missing_data"
            missing: list[str] = []
            if not usable:
                missing.append("没有通过质量门控的本地时间序列")
            if not candidates:
                missing.extend(f"建议接入: {name}" for name in hinted_names[:4])
            segments.append(
                BridgeEvidenceSegmentView(
                    hypothesis_index=hypothesis_index,
                    sequence=sequence,
                    source=source_label,
                    target=target_label,
                    search_terms=terms[:24],
                    status=status,
                    candidates=candidates[:6],
                    missing_data=missing,
                )
            )
    unique_refs = list(dict.fromkeys(added_refs))[:200]
    report = EvidenceCompletionView(
        generated_at=datetime.now(UTC),
        window_start=window_start,
        window_end=window_end,
        segment_count=len(segments),
        candidate_data_segments=sum(
            item.status in {"candidate_data_found", "partial_data"} for item in segments
        ),
        rejected_anomaly_segments=sum(item.status == "rejected_anomaly" for item in segments),
        missing_segments=sum(item.status == "missing_data" for item in segments),
        added_evidence_refs=unique_refs,
        segments=segments,
    )
    evidence["bridge_evidence_completion"] = report.model_dump(mode="json")
    priority = list(evidence.get("priority_evidence") or [])
    priority_ids = {
        item.get("evidence_id")
        for item in priority
        if isinstance(item, dict)
    }
    for item in _items_for_refs(evidence, unique_refs):
        if item.get("evidence_id") not in priority_ids:
            priority.append(item)
    evidence["priority_evidence"] = priority[:72]
    return report


def _query_plan(text: str) -> tuple[list[str], set[str], list[str]]:
    lowered = text.casefold()
    terms = list(
        dict.fromkeys(
            token
            for token in TOKEN_PATTERN.findall(lowered)
            if token not in STOPWORDS
        )
    )[:18]
    ids: set[str] = set()
    names: list[str] = []
    for triggers, hinted_ids, hinted_names in SERIES_HINTS:
        if any(trigger in lowered for trigger in triggers):
            ids.update(hinted_ids)
            names.extend(hinted_names)
    return terms, ids, list(dict.fromkeys(names))


def _series_score(
    series_id: str,
    text: str,
    *,
    terms: list[str],
    hinted_ids: set[str],
    hinted_names: list[str],
) -> float:
    lowered = f"{series_id} {text}".casefold()
    score = 100.0 if series_id in hinted_ids else 0.0
    score += sum(8.0 for term in terms if term in lowered)
    score += sum(20.0 for name in hinted_names if name.casefold() in lowered)
    return score


def _market_candidate(
    session: Session,
    *,
    series: MarketSeries,
    relevance: float,
    window_start: date,
    window_end: date,
    evidence: dict[str, Any],
) -> tuple[BridgeEvidenceCandidateView, list[str]]:
    rows = list(
        session.scalars(
            select(MarketObservation)
            .where(
                MarketObservation.series_id == series.series_id,
                MarketObservation.observed_on >= window_start,
                MarketObservation.observed_on <= window_end,
            )
            .order_by(MarketObservation.observed_on)
        )
    )
    quality = audit_market_rows(
        series,
        rows,
        window_start=window_start,
        window_end=window_end,
    )
    valid, _ = valid_market_rows(series, rows)
    refs: list[str] = []
    if quality.can_verify_claims and valid:
        selected = list(dict.fromkeys((valid[0], valid[-1])))
        section = evidence.setdefault("market_observations", [])
        for row in selected:
            item = {
                "evidence_id": f"market:{series.series_id}:{row.observed_on.isoformat()}",
                "category": series.category,
                "series_id": series.series_id,
                "name": series.name,
                "observed_on": row.observed_on.isoformat(),
                "value": float(row.value),
                "unit": series.unit,
                "source": series.source_name,
                "source_url": series.source_url,
            }
            _merge_item(section, item)
            refs.append(str(item["evidence_id"]))
        window_item = _window_item(series, valid)
        _merge_item(evidence.setdefault("market_window_statistics", []), window_item)
        refs.append(str(window_item["evidence_id"]))
    return (
        BridgeEvidenceCandidateView(
            series_id=series.series_id,
            name=series.name,
            relevance_score=relevance,
            evidence_refs=refs,
            quality=quality,
        ),
        refs,
    )


def _energy_candidate(
    session: Session,
    *,
    series: EnergySeries,
    relevance: float,
    window_start: date,
    window_end: date,
    evidence: dict[str, Any],
) -> tuple[BridgeEvidenceCandidateView, list[str]]:
    raw_rows = list(
        session.scalars(
            select(EnergyObservation)
            .where(EnergyObservation.series_id == series.series_id)
            .order_by(EnergyObservation.period)
        )
    )
    parsed = [
        (observed_on, row)
        for row in raw_rows
        if (observed_on := _period_date(row.period)) is not None
        and window_start <= observed_on <= window_end
    ]
    price_like = any(
        token in f"{series.name} {series.units or ''}".casefold()
        for token in ("price", "$/", "dollar", "价格")
    )
    valid = [
        (observed_on, row)
        for observed_on, row in parsed
        if (not price_like or float(row.value) > 0)
    ]
    invalid_count = len(parsed) - len(valid)
    expected = max(round(max((window_end - window_start).days, 1) / 91), 1)
    coverage = min(len(valid) / expected, 1.0)
    values = [float(row.value) for _, row in valid]
    flags = []
    if not parsed:
        flags.append("no_observations")
    if invalid_count:
        flags.append("invalid_or_nonpositive_price_values")
    if parsed and not valid:
        flags.append("no_valid_observations")
    can_verify = len(valid) >= 2 and coverage >= 0.2 and not invalid_count
    quality = SeriesQualityView(
        series_id=series.series_id,
        name=series.name,
        category="energy_or_commodity",
        source_name="U.S. EIA bulk data",
        unit=series.units,
        frequency=series.frequency,
        window_start=window_start,
        window_end=window_end,
        first_observed_on=valid[0][0] if valid else None,
        last_observed_on=valid[-1][0] if valid else None,
        observation_count=len(valid),
        expected_observations=expected,
        coverage_ratio=coverage,
        invalid_value_count=invalid_count,
        zero_value_count=sum(abs(float(row.value)) <= 1e-12 for _, row in parsed),
        unique_value_count=len(set(values)),
        maximum_absolute_change_ratio=None,
        quality_score=coverage if can_verify else min(coverage, 0.25),
        can_verify_claims=can_verify,
        flags=flags,
    )
    refs: list[str] = []
    if can_verify:
        section = evidence.setdefault("energy_observations", [])
        for observed_on, row in (valid[0], valid[-1]):
            item = {
                "evidence_id": f"energy:{series.series_id}:{row.period}",
                "category": "energy_or_commodity",
                "series_id": series.series_id,
                "name": series.name,
                "period": row.period,
                "observed_on": observed_on.isoformat(),
                "value": float(row.value),
                "unit": series.units,
                "source": "U.S. EIA bulk data",
                "source_url": series.source_url,
            }
            _merge_item(section, item)
            refs.append(str(item["evidence_id"]))
    return (
        BridgeEvidenceCandidateView(
            series_id=series.series_id,
            name=series.name,
            relevance_score=relevance,
            evidence_refs=refs,
            quality=quality,
        ),
        refs,
    )


def _window_item(series: MarketSeries, rows: list[MarketObservation]) -> dict[str, Any]:
    values = [float(row.value) for row in rows]
    first = rows[0]
    last = rows[-1]
    return {
        "evidence_id": (
            f"derived:market-window:{series.series_id}:"
            f"{first.observed_on.isoformat()}:{last.observed_on.isoformat()}"
        ),
        "category": "derived_market_window",
        "series_id": series.series_id,
        "name": series.name,
        "window_start": first.observed_on.isoformat(),
        "window_end": last.observed_on.isoformat(),
        "observation_count": len(rows),
        "first_value": values[0],
        "last_value": values[-1],
        "absolute_change": values[-1] - values[0],
        "percent_change": values[-1] / values[0] - 1 if values[0] else None,
        "minimum": min(values),
        "maximum": max(values),
        "mean": sum(values) / len(values),
        "unit": series.unit,
        "source": series.source_name,
        "source_url": series.source_url,
        "calculation": "Quality-gated local descriptive statistics",
        "can_verify_claims": True,
    }


def _period_date(value: str) -> date | None:
    normalized = value.strip()
    for pattern, replacement in (
        (r"^(\d{4})$", r"\1-12-31"),
        (r"^(\d{4})-Q([1-4])$", None),
        (r"^(\d{4})-(\d{2})$", r"\1-\2-01"),
    ):
        match = re.fullmatch(pattern, normalized)
        if match is None:
            continue
        if replacement is None:
            quarter_month = int(match.group(2)) * 3
            normalized = f"{match.group(1)}-{quarter_month:02d}-01"
        else:
            normalized = match.expand(replacement)
        break
    try:
        return date.fromisoformat(normalized[:10])
    except ValueError:
        return None


def _merge_item(section: list[Any], item: dict[str, Any]) -> None:
    evidence_id = item.get("evidence_id")
    if not any(
        isinstance(existing, dict) and existing.get("evidence_id") == evidence_id
        for existing in section
    ):
        section.append(item)


def _items_for_refs(evidence: dict[str, Any], refs: list[str]) -> list[dict[str, Any]]:
    wanted = set(refs)
    return [
        item
        for section in evidence.values()
        if isinstance(section, list)
        for item in section
        if isinstance(item, dict) and item.get("evidence_id") in wanted
    ]
