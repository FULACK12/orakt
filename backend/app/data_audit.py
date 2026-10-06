"""Generate one reproducible audit of retained research and equity data."""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import ValidationError
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.companies import COMPANY_CATALOG, company_coverage
from app.core.config import Settings, get_settings
from app.data_coverage import build_coverage_report
from app.data_quality import audit_market_rows
from app.db.models import (
    CompanyProfile,
    Document,
    MarketObservation,
    MarketSeries,
    ResearchInquiry,
)
from app.schemas.coverage import DatasetCoverage
from app.schemas.data_audit import (
    DataAuditReportView,
    EquityLeaderView,
    EvidenceCompletionView,
    FullTextBacklogView,
    SeriesQualityView,
)
from app.storage.archive import ArchiveCapacityError, ColdArchive

AUDIT_DAYS = 550


def build_data_audit_report(
    session: Session,
    *,
    settings: Settings | None = None,
    persist: bool = False,
    include_full_coverage: bool = True,
) -> DataAuditReportView:
    """Audit actual local rows, equity universes and latest evidence resolution."""
    runtime = settings or get_settings()
    generated_at = datetime.now(UTC)
    window_end = generated_at.date()
    window_start = window_end - timedelta(days=AUDIT_DAYS)
    series_rows = list(session.scalars(select(MarketSeries).order_by(MarketSeries.series_id)))
    observations = list(
        session.scalars(
            select(MarketObservation)
            .where(
                MarketObservation.observed_on >= window_start,
                MarketObservation.observed_on <= window_end,
            )
            .order_by(MarketObservation.series_id, MarketObservation.observed_on)
        )
    )
    rows_by_series: dict[str, list[MarketObservation]] = defaultdict(list)
    for observation in observations:
        rows_by_series[observation.series_id].append(observation)

    quality_by_id = {
        series.series_id: audit_market_rows(
            series,
            rows_by_series.get(series.series_id, []),
            window_start=window_start,
            window_end=window_end,
        )
        for series in series_rows
    }
    abnormal = sorted(
        (quality for quality in quality_by_id.values() if quality.flags),
        key=lambda quality: (
            quality.can_verify_claims,
            quality.quality_score,
            quality.series_id,
        ),
    )
    unusable = [quality for quality in quality_by_id.values() if not quality.can_verify_claims]
    profiles = {
        profile.ticker: profile
        for profile in session.scalars(select(CompanyProfile).order_by(CompanyProfile.ticker))
    }
    catalog = {ticker: (name, sector) for ticker, _, name, sector, _ in COMPANY_CATALOG}
    china = _china_sector_leaders(series_rows, rows_by_series, quality_by_id)
    us = _us_sector_equities(series_rows, quality_by_id, profiles, catalog)
    company_stats = company_coverage(session)
    coverage = (
        build_coverage_report(session, settings=runtime, now=generated_at)
        if include_full_coverage
        else None
    )
    expected_companies = max(int(company_stats["expected_company_count"]), 1)
    company_price_coverage = min(
        int(company_stats["priced_companies"]) / expected_companies,
        1.0,
    )
    latest_completion = _latest_completion(session)
    fulltext_backlog = _fulltext_backlog(session, now=generated_at)
    observation_count = int(
        session.scalar(select(func.count()).select_from(MarketObservation)) or 0
    )
    china_count = sum(len(items) for items in china.values())
    us_count = sum(len(items) for items in us.values())
    findings = _report_findings(
        abnormal=abnormal,
        unusable=unusable,
        company_count=int(company_stats["company_count"]),
        expected_company_count=int(company_stats["expected_company_count"]),
        company_price_coverage=company_price_coverage,
        china_count=china_count,
        latest_completion=latest_completion,
        fulltext_backlog=fulltext_backlog,
        dataset_coverage=coverage.datasets if coverage else [],
    )
    status = _report_status(
        series_count=len(series_rows),
        unusable_count=len(unusable),
        suspicious_count=len(abnormal),
        company_price_coverage=company_price_coverage,
        china_count=china_count,
    )
    report = DataAuditReportView(
        generated_at=generated_at,
        status=status,
        market_series_count=len(series_rows),
        market_observation_count=observation_count,
        company_count=int(company_stats["company_count"]),
        company_price_coverage=round(company_price_coverage, 6),
        china_leader_count=china_count,
        us_equity_count=us_count,
        suspicious_series_count=len(abnormal),
        unusable_series_count=len(unusable),
        abnormal_series=abnormal[:200],
        china_sector_leaders=china,
        us_sector_equities=us,
        latest_evidence_completion=latest_completion,
        fulltext_backlog=fulltext_backlog,
        dataset_coverage=coverage.datasets if coverage else [],
        source_coverage=coverage.sources if coverage else [],
        provider_findings=[
            "A股目录可由 Twelve Data 读取, 但当前套餐无 A 股日线权限; "
            "价格改由 BaoStock 匿名接口同步。",
            "A股龙头口径: 沪深300与中证500合并去重股票池内, 按市值20%、营收15%、净利润15%、"
            "ROE 10%、净利润增长15%、流动性15%、估值10%的行业内综合分取前十。",
            "美股公司基本面来自 SEC 原始申报, 拆股调整日线来自 Twelve Data。",
            "质量门控拒绝非有限数、价格小于等于零、可疑平线、严重稀疏或过期序列作为验证证据。",
        ],
        report_findings=findings,
        archive_status="not_configured",
    )
    return _archive_report(report, runtime) if persist else report


def _china_sector_leaders(
    series_rows: list[MarketSeries],
    rows_by_series: dict[str, list[MarketObservation]],
    quality_by_id: dict[str, SeriesQualityView],
) -> dict[str, list[EquityLeaderView]]:
    price_series = [
        series
        for series in series_rows
        if series.series_id.startswith("CN:") and series.category == "equity_price"
    ]
    score_rows = [
        row
        for series_id, rows in rows_by_series.items()
        if series_id.startswith("CNSCORE:")
        for row in rows
    ]
    latest_score_date = max((row.observed_on for row in score_rows), default=None)
    current_scores = {
        series_id.split(":", 1)[1]: float(row.value)
        for series_id, rows in rows_by_series.items()
        if series_id.startswith("CNSCORE:")
        for row in rows
        if latest_score_date is not None and row.observed_on == latest_score_date
    }
    grouped: dict[str, list[tuple[float, MarketSeries]]] = defaultdict(list)
    for series in price_series:
        symbol = series.series_id.split(":", 1)[1]
        if current_scores:
            if symbol not in current_scores:
                continue
            ranking_value = current_scores[symbol]
        else:
            amount_rows = rows_by_series.get(f"CNAMT:{symbol}", [])[-90:]
            ranking_value = (
                sum(float(row.value) for row in amount_rows) / len(amount_rows)
                if amount_rows
                else 0.0
            )
        grouped[series.sector or "Unclassified"].append((ranking_value, series))
    result: dict[str, list[EquityLeaderView]] = {}
    for sector, values in sorted(grouped.items()):
        result[sector] = [
            _equity_view(
                market="CN",
                series=series,
                rank=rank,
                ranking_metric=(
                    "CSI 800 proxy sector composite score (market cap, revenue, profit, "
                    "ROE, growth, liquidity and valuation)"
                    if current_scores
                    else "90-day average traded amount fallback"
                ),
                ranking_value=ranking_value,
                quality=quality_by_id[series.series_id],
            )
            for rank, (ranking_value, series) in enumerate(
                sorted(values, key=lambda item: (-item[0], item[1].series_id))[:10],
                start=1,
            )
        ]
    return result


def _us_sector_equities(
    series_rows: list[MarketSeries],
    quality_by_id: dict[str, SeriesQualityView],
    profiles: dict[str, CompanyProfile],
    catalog: dict[str, tuple[str, str]],
) -> dict[str, list[EquityLeaderView]]:
    grouped: dict[str, list[MarketSeries]] = defaultdict(list)
    for series in series_rows:
        if not series.series_id.startswith("EQ:") or series.category != "equity_price":
            continue
        ticker = series.series_id.split(":", 1)[1]
        profile = profiles.get(ticker)
        sector = series.sector or (profile.sector if profile else None)
        sector = sector or catalog.get(ticker, ("", "Unclassified"))[1]
        grouped[sector].append(series)
    result: dict[str, list[EquityLeaderView]] = {}
    for sector, values in sorted(grouped.items()):
        result[sector] = [
            _equity_view(
                market="US",
                series=series,
                rank=rank,
                ranking_metric="reviewed SEC/Twelve Data large-cap universe",
                ranking_value=None,
                quality=quality_by_id[series.series_id],
            )
            for rank, series in enumerate(sorted(values, key=lambda item: item.series_id), start=1)
        ]
    return result


def _equity_view(
    *,
    market: Literal["CN", "US"],
    series: MarketSeries,
    rank: int,
    ranking_metric: str,
    ranking_value: float | None,
    quality: SeriesQualityView,
) -> EquityLeaderView:
    symbol = series.series_id.split(":", 1)[1]
    name = series.name.split(" split-adjusted", 1)[0]
    name = name.split(" 前复权", 1)[0]
    return EquityLeaderView(
        market=market,
        symbol=symbol,
        name=name,
        sector=series.sector or "Unclassified",
        rank=rank,
        ranking_metric=ranking_metric,
        ranking_value=round(ranking_value, 2) if ranking_value is not None else None,
        price_series_id=series.series_id,
        price_start=quality.first_observed_on,
        price_end=quality.last_observed_on,
        observation_count=quality.observation_count,
        quality_score=quality.quality_score,
        flags=quality.flags,
    )


def _latest_completion(session: Session) -> EvidenceCompletionView | None:
    row = session.scalar(
        select(ResearchInquiry)
        .where(
            ResearchInquiry.status == "completed",
            ResearchInquiry.evidence_snapshot.is_not(None),
        )
        .order_by(ResearchInquiry.created_at.desc(), ResearchInquiry.id.desc())
        .limit(1)
    )
    if row is None:
        return None
    payload = (row.evidence_snapshot or {}).get("bridge_evidence_completion")
    try:
        return EvidenceCompletionView.model_validate(payload) if payload else None
    except ValidationError:
        return None


def _report_findings(
    *,
    abnormal: list[SeriesQualityView],
    unusable: list[SeriesQualityView],
    company_count: int,
    expected_company_count: int,
    company_price_coverage: float,
    china_count: int,
    latest_completion: EvidenceCompletionView | None,
    fulltext_backlog: FullTextBacklogView,
    dataset_coverage: list[DatasetCoverage],
) -> list[str]:
    findings = [
        f"数值序列异常/不完整 {len(abnormal)} 条, "
        f"其中 {len(unusable)} 条当前禁止用于因果验证。",
        f"美股公司目录 {company_count}/{expected_company_count}, "
        f"有价格覆盖比例 {company_price_coverage:.1%}。",
        f"本地已形成 {china_count} 个中证800代理池板块龙头价格序列。",
        (
            f"新闻全文积压 {fulltext_backlog.headline_only_count} 条: "
            f"未尝试 {fulltext_backlog.never_attempted_count}、"
            f"当前可重试 {fulltext_backlog.retryable_now_count}、"
            f"永久阻止 {fulltext_backlog.permanent_block_count}。"
        ),
    ]
    if latest_completion is None:
        findings.append("最近研究尚无新版证据补全快照, 需要重新执行因子挖掘或新建研究。")
    else:
        findings.append(
            "最近证据补全: "
            f"{latest_completion.candidate_data_segments}/"
            f"{latest_completion.segment_count} 个相邻步骤找到可用候选数据, "
            f"{latest_completion.rejected_anomaly_segments} 个步骤命中异常数据, "
            f"{latest_completion.missing_segments} 个步骤仍缺数据。"
        )
    if abnormal:
        top_flags: dict[str, int] = defaultdict(int)
        for quality in abnormal:
            for flag in quality.flags:
                top_flags[flag] += 1
        findings.append(
            "主要异常类型: "
            + "、".join(
                f"{flag}={count}"
                for flag, count in sorted(top_flags.items(), key=lambda item: -item[1])[:6]
            )
            + "。"
        )
    if dataset_coverage:
        incomplete = [item for item in dataset_coverage if item.status != "complete"]
        missing = [item for item in dataset_coverage if item.status == "missing"]
        headline_only = sum(int(item.headline_only_count or 0) for item in dataset_coverage)
        findings.append(
            f"全域数据覆盖审计: {len(dataset_coverage)} 类数据中 "
            f"{len(incomplete)} 类不完整, {len(missing)} 类完全缺失; "
            f"仅标题记录 {headline_only} 条。"
        )
    return findings


def _fulltext_backlog(session: Session, *, now: datetime) -> FullTextBacklogView:
    """Measure title-only rows and whether the respectful fetcher can act on them."""
    status = Document.raw_metadata["full_text_status"].as_string()
    retry_class = Document.raw_metadata["full_text_retry_class"].as_string()
    retry_at = Document.raw_metadata["full_text_retry_after"].as_string()
    attempted_at = Document.raw_metadata["full_text_attempted_at"].as_string()
    collector = Document.raw_metadata["collector"].as_string()
    headline_only = func.length(func.coalesce(Document.body, "")) < 100
    now_value = now.isoformat()
    retry_before = (now - timedelta(days=7)).isoformat()
    is_permanent = retry_class == "permanent"
    is_scheduled = and_(retry_at.is_not(None), retry_at > now_value)
    is_retryable = and_(
        or_(retry_class.is_(None), retry_class != "permanent"),
        or_(
            attempted_at.is_(None),
            and_(retry_at.is_not(None), retry_at <= now_value),
            and_(
                retry_at.is_(None),
                attempted_at.is_not(None),
                attempted_at <= retry_before,
            ),
        ),
    )
    (
        headline_count,
        never_attempted,
        retryable_now,
        scheduled_retry,
        permanent_block,
    ) = session.execute(
        select(
            func.count(Document.id),
            func.count(Document.id).filter(attempted_at.is_(None)),
            func.count(Document.id).filter(is_retryable),
            func.count(Document.id).filter(is_scheduled),
            func.count(Document.id).filter(is_permanent),
        ).where(headline_only)
    ).one()
    completed = int(
        session.scalar(
            select(func.count(Document.id)).where(status == "complete")
        )
        or 0
    )
    collector_rows = session.execute(
        select(func.coalesce(collector, "unknown"), func.count(Document.id))
        .where(headline_only)
        .group_by(collector)
        .order_by(func.count(Document.id).desc())
    ).all()
    status_rows = session.execute(
        select(func.coalesce(status, "never_attempted"), func.count(Document.id))
        .where(headline_only)
        .group_by(status)
        .order_by(func.count(Document.id).desc())
        .limit(20)
    ).all()
    return FullTextBacklogView(
        headline_only_count=int(headline_count or 0),
        never_attempted_count=int(never_attempted or 0),
        retryable_now_count=int(retryable_now or 0),
        scheduled_retry_count=int(scheduled_retry or 0),
        permanent_block_count=int(permanent_block or 0),
        completed_expansion_count=completed,
        by_collector={str(key): int(count) for key, count in collector_rows},
        by_status={str(key): int(count) for key, count in status_rows},
    )


def _report_status(
    *,
    series_count: int,
    unusable_count: int,
    suspicious_count: int,
    company_price_coverage: float,
    china_count: int,
) -> str:
    unusable_ratio = unusable_count / max(series_count, 1)
    if unusable_ratio >= 0.25 or company_price_coverage < 0.25:
        return "critical"
    if suspicious_count or company_price_coverage < 0.9 or china_count == 0:
        return "warning"
    return "healthy"


def _archive_report(report: DataAuditReportView, settings: Settings) -> DataAuditReportView:
    payload = report.model_dump(mode="json")
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    relative = (
        f"model-outputs/data-audits/{report.generated_at:%Y/%m/%d}/"
        f"{report.generated_at:%H%M%S}-{digest[:16]}.json.gz"
    )
    try:
        archive = ColdArchive(
            settings.cold_data_root,
            min_free_bytes=settings.cold_archive_min_free_gb * 1024**3,
            max_used_percent=settings.cold_archive_max_used_percent,
        )
        path = archive.store_bytes(relative, gzip.compress(encoded, compresslevel=6, mtime=0))
        return report.model_copy(update={"archive_path": path, "archive_status": "stored"})
    except (ArchiveCapacityError, OSError, ValueError):
        return report.model_copy(update={"archive_status": "write_failed"})
