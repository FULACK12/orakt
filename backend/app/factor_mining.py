"""Auditable local factor mining with chronological profit validation."""

# ruff: noqa: RUF001

from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
from bisect import bisect_left, bisect_right
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, date, datetime
from itertools import pairwise
from statistics import fmean, median, pstdev
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.alpha_vantage_listings import alpha_vantage_listing_coverage
from app.companies import COMPANY_CATALOG
from app.core.config import Settings
from app.db.models import MarketObservation, MarketPriceBackfillState, MarketSeries
from app.factor_assets import FACTOR_ASSET_BY_SYMBOL
from app.factor_experiments import register_factor_experiments
from app.market_identity import verified_provider_history_series_ids
from app.markets import MARKET_INDICES
from app.schemas.research import (
    ModelCrossSectionalValidation,
    ModelCrossSectionAssetExposure,
    ModelCrossSectionRobustness,
    ModelFactorCandidate,
    ModelFactorReplication,
    ModelFactorReplicationTrial,
    ModelFactorResearch,
    ModelLinearTransmissionSegment,
    ModelNonlinearFactorLink,
    ModelPortfolioContribution,
    ModelProfitValidation,
    ModelResearchHypothesis,
    ModelResearchResult,
    ModelSurvivorshipAudit,
    ResearchStepStatus,
)
from app.storage.archive import ArchiveCapacityError, ColdArchive

FACTOR_METHOD_VERSION = "dual_track_factor_v10_product_operating_bridge"
FACTOR_HORIZONS = (1, 5, 20, 60)
TRADABLE_CATEGORIES = (
    "equity_price",
    "equity_index",
    "global_market_proxy",
    "market_index",
    "commodity_price",
    "sector_etf",
    "bond_proxy",
    "commodity_proxy",
    "currency_proxy",
    "global_equity_price",
    "historical_equity_price",
)
COMPANY_SECTOR_BY_TICKER = {ticker: sector for ticker, _, _, sector, _ in COMPANY_CATALOG}
COUNTRY_BY_PROXY = {
    definition.provider_symbol: definition.country_iso2 for definition in MARKET_INDICES
}
REGION_BY_COUNTRY = {
    "US": "north_america",
    "CA": "north_america",
    "GB": "europe",
    "DE": "europe",
    "FR": "europe",
    "JP": "asia_pacific",
    "HK": "asia_pacific",
    "KR": "asia_pacific",
    "AU": "asia_pacific",
    "CN": "emerging_markets",
    "IN": "emerging_markets",
    "BR": "emerging_markets",
    "ZA": "emerging_markets",
}
FACTOR_RESEARCH_CAVEAT = (
    "因子结果属于研究性统计检验，不是投资建议。样本外正收益不代表未来可复制；"
    "新闻可得时间、幸存者偏差、交易成本、流动性和数据修订仍可能改变结果。"
)
TOKEN_PATTERN = re.compile(r"[a-z0-9:.^-]{2,}|[\u4e00-\u9fff]{2,}", re.IGNORECASE)
GENERIC_MARKET_TOKENS = {
    "and",
    "close",
    "co",
    "co.",
    "company",
    "corp",
    "corporation",
    "inc",
    "inc.",
    "ltd",
    "proxy",
    "split-adjusted",
    "price",
    "index",
    "market",
    "stock",
    "equity",
    "return",
    "future",
    "asset",
    "all",
    "average",
    "composite",
    "fund",
    "industrial",
    "share",
}


def build_factor_research(
    session: Session,
    *,
    result: ModelResearchResult,
    evidence: dict[str, Any],
    settings: Settings,
    inquiry_id: int,
    persist_artifact: bool = True,
) -> ModelFactorResearch:
    """Build a dual-track factor graph and validate it without look-ahead."""
    allowed_refs = _evidence_refs(evidence)
    factors = _sanitized_ai_factors(result.factor_candidates, allowed_refs)
    if not factors:
        factors = _factors_from_linear_hypotheses(result, allowed_refs)
    product_factors = _factors_from_product_evidence(evidence, allowed_refs)
    supplier_factors = _factors_from_supplier_evidence(evidence, allowed_refs)
    known_factor_ids = {factor.factor_id for factor in factors}
    factors.extend(
        factor for factor in product_factors if factor.factor_id not in known_factor_ids
    )
    known_factor_ids = {factor.factor_id for factor in factors}
    factors.extend(
        factor for factor in supplier_factors if factor.factor_id not in known_factor_ids
    )
    supplier_context = " ".join(
        str(item.get(key) or "")
        for item in evidence.get("derived_equity_evidence", [])
        if isinstance(item, dict)
        and item.get("category")
        in {"verified_supply_chain_edge", "derived_supplier_factor"}
        for key in (
            "related_company_name",
            "related_ticker",
            "supplier_name",
            "supplier_series_id",
            "product_or_input",
        )
    )
    product_context = " ".join(
        str(item.get(key) or "")
        for item in evidence.get("derived_equity_evidence", [])
        if isinstance(item, dict) and item.get("category") == "product_operating_evidence"
        for key in ("product", "metric_name", "source_excerpt")
    )
    factor_question_text = (
        f"{result.question} {result.summary} {supplier_context} {product_context}"
    ).strip()

    target = _select_target_series(session, result)
    validations: list[ModelProfitValidation] = []
    cross_sectional_validations: list[ModelCrossSectionalValidation] = []
    nonlinear_links = _ai_nonlinear_links(result, factors, allowed_refs)
    if target is not None:
        for horizon in FACTOR_HORIZONS:
            mined_factors, mined_links, validation = _mine_market_interaction(
                session,
                target=target,
                question_text=factor_question_text,
                horizon=horizon,
            )
            known_ids = {factor.factor_id for factor in factors}
            factors.extend(
                factor for factor in mined_factors if factor.factor_id not in known_ids
            )
            if horizon == FACTOR_HORIZONS[0]:
                nonlinear_links.extend(mined_links)
            validations.append(validation)
    else:
        fallback_id = factors[0].factor_id if factors else "factor:no_market_target"
        for horizon in FACTOR_HORIZONS:
            validations.append(
                ModelProfitValidation(
                    target_series_id="unresolved",
                    target_name="未匹配到可交易目标序列",
                    factor_ids=[fallback_id],
                    start_date=None,
                    end_date=None,
                    train_end_date=None,
                    forecast_horizon_days=horizon,
                    train_observations=0,
                    test_observations=0,
                    transaction_cost_bps=10,
                    status="insufficient_data",
                    signal_rule="仅保留因子假设，等待与问题对应的可交易价格序列。",
                    leakage_guard="尚未执行回测，因此没有用未来数据确认该因子。",
                    limitations=["缺少与研究问题匹配且具有足够历史长度的市场序列。"],
                )
            )

    for horizon in FACTOR_HORIZONS:
        cross_factors, cross_links, cross_validation = _mine_cross_sectional_factors(
            session,
            question_text=factor_question_text,
            horizon=horizon,
        )
        known_ids = {factor.factor_id for factor in factors}
        factors.extend(
            factor for factor in cross_factors if factor.factor_id not in known_ids
        )
        if horizon == FACTOR_HORIZONS[0]:
            nonlinear_links.extend(cross_links)
        cross_sectional_validations.append(cross_validation)

    research = ModelFactorResearch(
        method_version=FACTOR_METHOD_VERSION,
        generated_at=datetime.now(UTC),
        linear_chain_retained=True,
        factors=factors[:24],
        nonlinear_links=_deduplicate_links(nonlinear_links)[:12],
        profit_validations=validations[:6],
        cross_sectional_validations=cross_sectional_validations[:4],
        archive_status="not_configured",
        research_caveat=FACTOR_RESEARCH_CAVEAT,
    )
    if persist_artifact:
        register_factor_experiments(
            session,
            research=research,
            inquiry_id=inquiry_id,
        )
        _archive_factor_research(
            research,
            settings=settings,
            inquiry_id=inquiry_id,
            question=result.question,
        )
    return research


def _sanitized_ai_factors(
    candidates: Iterable[ModelFactorCandidate],
    allowed_refs: set[str],
) -> list[ModelFactorCandidate]:
    retained: list[ModelFactorCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate.factor_id in seen:
            continue
        candidate.evidence_refs = [ref for ref in candidate.evidence_refs if ref in allowed_refs]
        if not candidate.evidence_refs:
            candidate.confidence = min(candidate.confidence, 0.2)
        candidate.confidence = min(candidate.confidence, 0.75)
        retained.append(candidate)
        seen.add(candidate.factor_id)
    return retained[:16]


def _factors_from_linear_hypotheses(
    result: ModelResearchResult,
    allowed_refs: set[str],
) -> list[ModelFactorCandidate]:
    factors: list[ModelFactorCandidate] = []
    for hypothesis_index, hypothesis in enumerate(result.hypotheses[:4], start=1):
        for step in hypothesis.steps[:4]:
            refs = [ref for ref in step.evidence_refs if ref in allowed_refs]
            factors.append(
                ModelFactorCandidate(
                    factor_id=f"ai:h{hypothesis_index}:s{step.sequence}",
                    name=step.label[:300],
                    factor_type=_factor_type(refs),
                    direction="regime_dependent",
                    transformation="binary_event",
                    lag_days=0,
                    hypothesis=(f"线性链步骤可能作为条件因子影响后续结果：{hypothesis.outcome}")[
                        :1_500
                    ],
                    evidence_refs=refs,
                    confidence=min(step.confidence, 0.75) if refs else min(step.confidence, 0.2),
                )
            )
    if factors:
        return factors[:16]
    return [
        ModelFactorCandidate(
            factor_id="ai:unresolved:1",
            name="待证据化研究因子",
            factor_type="interaction",
            direction="regime_dependent",
            transformation="interaction",
            lag_days=0,
            hypothesis=result.question,
            evidence_refs=[],
            confidence=0.1,
        )
    ]


def _factors_from_supplier_evidence(
    evidence: dict[str, Any],
    allowed_refs: set[str],
) -> list[ModelFactorCandidate]:
    """Promote only reviewed supplier edges with dated market calculations."""
    factors: list[ModelFactorCandidate] = []
    for item in evidence.get("derived_equity_evidence", []):
        if not isinstance(item, dict) or item.get("category") != "derived_supplier_factor":
            continue
        evidence_id = str(item.get("evidence_id") or "")
        source_ref = str(item.get("source_edge_ref") or "")
        refs = [ref for ref in (evidence_id, source_ref) if ref in allowed_refs]
        if not refs:
            continue
        supplier_series = str(item.get("supplier_series_id") or "unknown")
        supplier_name = str(item.get("supplier_name") or supplier_series)
        product = str(item.get("product_or_input") or "disclosed input")
        is_category_proxy = item.get("proxy_type") == "category_basket"
        lag_correlation = item.get("supplier_lag1_target_return_correlation")
        if isinstance(lag_correlation, (int, float)) and lag_correlation > 0.05:
            direction = "positive"
        elif isinstance(lag_correlation, (int, float)) and lag_correlation < -0.05:
            direction = "negative"
        else:
            direction = "regime_dependent"
        sample_size = int(item.get("sample_size") or 0)
        if is_category_proxy:
            factor_id = f"supply-category:{supplier_series}:lag1"[:160]
            name = f"{supplier_name}（{product}）"[:300]
            hypothesis = (
                f"申报文件只披露了{product}依赖类别，并未披露具体供应商。"
                f"{supplier_name}仅用于衡量该行业类别的市场共振，篮子成分不代表"
                "实际供应商，也不能替代订单、价格、交付或产能证据。"
            )[:1_500]
            confidence = min(0.4, 0.2 + min(sample_size, 252) / 1_260)
        else:
            factor_id = f"supplier:{supplier_series}:lag1"[:160]
            name = f"{supplier_name}供应链市场代理（{product}）"[:300]
            hypothesis = (
                f"经来源审核的供应链关系允许把{supplier_name}的滞后市场变化作为"
                f"{product}风险的探索性代理；它不等于实际订单、价格、交付或产能。"
            )[:1_500]
            confidence = min(0.55, 0.3 + min(sample_size, 252) / 1_008)
        factors.append(
            ModelFactorCandidate(
                factor_id=factor_id,
                name=name,
                factor_type="supply_chain",
                direction=direction,
                transformation="return",
                lag_days=1,
                hypothesis=hypothesis,
                evidence_refs=refs,
                confidence=confidence,
            )
        )
    return factors[:8]


def _factors_from_product_evidence(
    evidence: dict[str, Any],
    allowed_refs: set[str],
) -> list[ModelFactorCandidate]:
    """Promote filing operating facts as low-confidence company factors."""
    factors: list[ModelFactorCandidate] = []
    for item in evidence.get("derived_equity_evidence", []):
        if not isinstance(item, dict) or item.get("category") != "product_operating_evidence":
            continue
        evidence_id = str(item.get("evidence_id") or "")
        if evidence_id not in allowed_refs:
            continue
        status = str(item.get("evidence_status") or "")
        metric_type = str(item.get("metric_type") or "operating_metric")
        metric_name = str(item.get("metric_name") or metric_type)
        product = str(item.get("product") or "product")
        reported_values = "、".join(str(value) for value in item.get("reported_values") or [])
        source_signal = str(item.get("signal") or "regime_dependent")
        direction = (
            source_signal if source_signal in {"positive", "negative"} else "regime_dependent"
        )
        transformation = (
            "change"
            if metric_type
            in {
                "price_and_volume_change",
                "volume_change",
                "revenue_growth",
                "margin_change",
            }
            else "binary_event"
            if status == "forward_looking_plan"
            else "level"
        )
        if status == "reported_actual":
            confidence = 0.65
            status_text = "已申报经营结果"
        elif status == "risk_disclosure":
            confidence = 0.4
            status_text = "风险披露"
        else:
            confidence = 0.3
            status_text = "前瞻计划"
        hypothesis = (
            f"{product}的{metric_name}来自年报中的{status_text}"
            + (f"（原文保留值：{reported_values}）" if reported_values else "")
            + "。该证据可作为公司经营因子，但不能单独证明未来股价方向；前瞻计划"
            "不得当作已实现收入、产量或产能。"
        )
        factors.append(
            ModelFactorCandidate(
                factor_id=f"product:{item.get('ticker')}:{metric_type}:{len(factors) + 1}"[:160],
                name=f"{product}：{metric_name}"[:300],
                factor_type="company",
                direction=direction,
                transformation=transformation,
                lag_days=0,
                hypothesis=hypothesis[:1_500],
                evidence_refs=[evidence_id],
                confidence=confidence,
            )
        )
    return factors[:8]


def _factor_type(refs: list[str]) -> str:
    prefixes = {ref.split(":", 1)[0] for ref in refs}
    if "market" in prefixes:
        return "market"
    if "economic" in prefixes or "energy" in prefixes:
        return "economic"
    if "company" in prefixes:
        return "company"
    if "conflict" in prefixes:
        return "geopolitical"
    return "news_event"


def _ai_nonlinear_links(
    result: ModelResearchResult,
    factors: list[ModelFactorCandidate],
    allowed_refs: set[str],
) -> list[ModelNonlinearFactorLink]:
    links: list[ModelNonlinearFactorLink] = []
    for index, hypothesis in enumerate(result.hypotheses[:4], start=1):
        factor_ids = [
            factor.factor_id for factor in factors if factor.factor_id.startswith(f"ai:h{index}:")
        ][:4]
        if len(factor_ids) < 2:
            continue
        refs = list(
            dict.fromkeys(
                ref
                for step in hypothesis.steps
                for ref in step.evidence_refs
                if ref in allowed_refs
            )
        )[:20]
        retained_bridge_variables = [step.label for step in hypothesis.steps[1:-1]][:6]
        bridge_variables = _expanded_bridge_variables(hypothesis)
        node_records: list[
            tuple[str, ResearchStepStatus, float, list[str]]
        ]
        if bridge_variables != retained_bridge_variables:
            node_records = [
                (
                    hypothesis.steps[0].label,
                    hypothesis.steps[0].status,
                    hypothesis.steps[0].confidence,
                    hypothesis.steps[0].evidence_refs,
                ),
                *[
                    (label, "evidence_missing", 0.18, [])
                    for label in bridge_variables
                ],
                (
                    hypothesis.steps[-1].label,
                    hypothesis.steps[-1].status,
                    hypothesis.steps[-1].confidence,
                    hypothesis.steps[-1].evidence_refs,
                ),
            ]
        else:
            node_records = [
                (step.label, step.status, step.confidence, step.evidence_refs)
                for step in hypothesis.steps
            ]
        linear_segments: list[ModelLinearTransmissionSegment] = []
        for sequence, (source_node, target_node) in enumerate(
            pairwise(node_records),
            start=1,
        ):
            source_label, source_status, source_confidence, source_refs = source_node
            target_label, target_status, target_confidence, target_refs = target_node
            segment_refs = list(
                dict.fromkeys(
                    ref
                    for ref in [
                        *source_refs,
                        *target_refs,
                    ]
                    if ref in allowed_refs
                )
            )[:20]
            segment_status: Literal[
                "verified",
                "partially_supported",
                "evidence_missing",
                "hypothesis",
            ]
            if "evidence_missing" in {source_status, target_status}:
                segment_status = "evidence_missing"
            elif (
                source_status in {"verified", "partially_supported"}
                and target_status in {"verified", "partially_supported"}
                and segment_refs
            ):
                segment_status = "partially_supported"
            else:
                segment_status = "hypothesis"
            segment_cap = 0.5 if segment_status == "partially_supported" else 0.2
            linear_segments.append(
                ModelLinearTransmissionSegment(
                    sequence=sequence,
                    source=source_label,
                    mechanism=(
                        f"检验 {source_label[:220]} 到 "
                        f"{target_label[:220]} 的相邻传导"
                    ),
                    target=target_label,
                    direction="conditional",
                    status=segment_status,
                    evidence_refs=segment_refs,
                    confidence=min(
                        source_confidence,
                        target_confidence,
                        segment_cap,
                    ),
                )
            )
        relationship_class: Literal[
            "exploratory_nonlinear",
            "partially_supported_nonlinear",
            "supported_nonlinear",
        ] = (
            "partially_supported_nonlinear"
            if any(
                segment.status == "partially_supported"
                for segment in linear_segments
            )
            else "exploratory_nonlinear"
        )
        links.append(
            ModelNonlinearFactorLink(
                link_id=f"ai:interaction:h{index}",
                input_factor_ids=factor_ids,
                operator="regime_switch",
                condition=("多个步骤同时成立，且宏观、市场或地缘状态没有触发反向机制。"),
                expected_output=hypothesis.outcome[:1_000],
                rationale=(
                    "线性证据链继续保留；该交互边单独检验步骤之间可能存在的阈值、"
                    "放大、抵消或状态切换效应。"
                ),
                evidence_refs=refs,
                confidence=min(hypothesis.confidence, 0.5 if refs else 0.2),
                relationship_class=relationship_class,
                bridge_variables=bridge_variables,
                linear_segments=linear_segments,
            )
        )
    return links


def _expanded_bridge_variables(
    hypothesis: ModelResearchHypothesis,
) -> list[str]:
    """Expand legacy generic mechanisms into measurable, unverified bridges."""
    retained = [step.label for step in hypothesis.steps[1:-1]][:6]
    if len(retained) != 1:
        return retained
    generic = retained[0].casefold()
    if not any(
        marker in generic
        for marker in (
            "transmission mechanism",
            "传导机制",
            "not established",
            "尚未验证",
        )
    ):
        return retained
    topic = " ".join(
        (hypothesis.title, hypothesis.premise, hypothesis.outcome)
    ).casefold()
    if any(term in topic for term in ("coal", "lignite", "coking", "煤", "焦炭")):
        return [
            "信用利差、企业融资与贸易融资成本",
            "电力和工业用煤需求、库存与采购量",
            "矿山供给、铁路港口运力与海运成本",
            "汇率、关税和煤炭进口到岸成本",
        ]
    if any(
        term in topic
        for term in (
            "commodity",
            "crude",
            "oil",
            "gas",
            "metal",
            "大宗商品",
            "原油",
            "天然气",
            "金属",
        )
    ):
        return [
            "宏观需求、信用条件或风险偏好状态",
            "生产供给、库存、采购与进口需求",
            "运费、汇率、关税与贸易流量",
        ]
    return retained


def _select_target_series(
    session: Session,
    result: ModelResearchResult,
) -> MarketSeries | None:
    rows = list(
        session.execute(
            select(MarketSeries, func.count(MarketObservation.observed_on))
            .join(MarketObservation, MarketObservation.series_id == MarketSeries.series_id)
            .where(MarketSeries.category.in_(TRADABLE_CATEGORIES))
            .group_by(MarketSeries.series_id)
            .having(func.count(MarketObservation.observed_on) >= 40)
        )
    )
    if not rows:
        return None
    scope_terms = " ".join(
        value
        for hypothesis in result.hypotheses
        for values in (
            hypothesis.scope.companies,
            hypothesis.scope.sectors,
            hypothesis.scope.products,
        )
        for value in values
    )
    text = f"{result.question} {result.summary} {scope_terms}".casefold()
    tokens = set(TOKEN_PATTERN.findall(text))
    preferred = {
        "SP500": 20,
        "TD:SPY": 19,
        "NASDAQCOM": 18,
        "TD:QQQ": 17,
        "DCOILWTICO": 4,
    }

    def score(row: tuple[MarketSeries, int]) -> tuple[float, int, str]:
        series, count = row
        name = series.name.casefold()
        identifier = series.series_id.casefold()
        name_tokens = set(TOKEN_PATTERN.findall(name)) - GENERIC_MARKET_TOKENS
        relevance = len(tokens & name_tokens) * 40
        short_identifier = identifier.removeprefix("td:").removeprefix("eq:")
        if identifier in text or short_identifier in tokens:
            relevance += 100
        if series.series_id in {"NASDAQCOM", "TD:QQQ"} and any(
            term in text for term in ("technology", "tech stocks", "科技", "科技股", "人工智能")
        ):
            relevance += 35
        if series.series_id == "DCOILWTICO" and any(
            term in text for term in ("oil", "crude", "brent", "石油", "原油", "布伦特")
        ):
            relevance += 50
        if any(term in name for term in ("index", "price", "stock", "oil", "commodity")):
            relevance += 2
        relevance += preferred.get(series.series_id, 0)
        return relevance, count, series.series_id

    return max(rows, key=score)[0]


def _mine_market_interaction(
    session: Session,
    *,
    target: MarketSeries,
    question_text: str,
    horizon: int = 5,
    transaction_cost_bps: float = 10,
) -> tuple[list[ModelFactorCandidate], list[ModelNonlinearFactorLink], ModelProfitValidation]:
    target_rows = _load_series(session, target.series_id)
    insufficient = len(target_rows) < 60
    series_rows = list(
        session.execute(
            select(MarketSeries, func.count(MarketObservation.observed_on))
            .join(MarketObservation, MarketObservation.series_id == MarketSeries.series_id)
            .where(MarketSeries.series_id != target.series_id)
            .group_by(MarketSeries.series_id)
            .having(func.count(MarketObservation.observed_on) >= 36)
        )
    )
    ranked_predictors = sorted(
        series_rows,
        key=lambda row: _predictor_relevance(row[0], question_text),
        reverse=True,
    )[:14]
    samples = _target_samples(target_rows, horizon=horizon)
    split_index = int(len(samples) * 0.7)
    split_date = samples[split_index][0] if samples and split_index < len(samples) else None
    candidates: list[dict[str, Any]] = []
    for series, _ in ranked_predictors:
        changes = _series_changes(_load_series(session, series.series_id))
        paired = _pair_feature(samples, changes)
        train = [row for row in paired if split_date is not None and row[2] < split_date]
        test = [row for row in paired if split_date is not None and row[0] >= split_date]
        correlation = _pearson([row[1] for row in train], [row[3] for row in train])
        if correlation is None or len(train) < 18:
            continue
        candidates.append(
            {
                "series": series,
                "train": train,
                "test": test,
                "correlation": correlation,
                "training_p_value": _correlation_p_value(correlation, len(train)),
                "changes": changes,
                "paired": paired,
            }
        )
    _apply_bh_qvalues(candidates)
    selected = sorted(candidates, key=lambda item: abs(item["correlation"]), reverse=True)[:2]
    factors = [
        ModelFactorCandidate(
            factor_id=f"market:{item['series'].series_id}:change5",
            name=f"{item['series'].name} 5期变化因子",
            factor_type="market",
            direction="positive" if item["correlation"] >= 0 else "negative",
            transformation="rolling_zscore",
            lag_days=1,
            hypothesis=(
                f"仅用训练期估计：{item['series'].name} 的滞后变化可能与 "
                f"{target.name} 未来{horizon}期收益相关。"
            ),
            evidence_refs=[],
            confidence=min(0.55, max(0.1, abs(float(item["correlation"])) * 0.7)),
            training_p_value=item.get("training_p_value"),
            adjusted_q_value=item.get("adjusted_q_value"),
        )
        for item in selected
    ]
    factor_ids = [factor.factor_id for factor in factors]
    if not factor_ids:
        factor_ids = [f"market:{target.series_id}:insufficient_predictors"]
        factors = [
            ModelFactorCandidate(
                factor_id=factor_ids[0],
                name=f"{target.name} 待验证因子",
                factor_type="market",
                direction="regime_dependent",
                transformation="rolling_zscore",
                lag_days=1,
                hypothesis="当前历史长度或共同时间戳不足以形成样本外因子组合。",
                evidence_refs=[],
                confidence=0.1,
            )
        ]

    links: list[ModelNonlinearFactorLink] = []
    if len(factor_ids) >= 2:
        links.append(
            ModelNonlinearFactorLink(
                link_id=f"market:interaction:{target.series_id}",
                input_factor_ids=factor_ids,
                operator="threshold",
                condition=(
                    "使用训练期均值和波动率标准化；两个滞后因子按训练期相关方向"
                    "合成，合成分数跨过零阈值时切换多空状态。"
                ),
                expected_output=f"预测 {target.name} 未来{horizon}期收益方向",
                rationale=(
                    "交互项允许两个因子在不同宏观状态下互相放大或抵消，不会替代原有线性因果链。"
                ),
                evidence_refs=[],
                confidence=min(0.55, fmean(abs(float(item["correlation"])) for item in selected)),
            )
        )

    validation = _validate_selected_factors(
        target=target,
        target_rows=target_rows,
        samples=samples,
        split_date=split_date,
        selected=selected,
        factor_ids=factor_ids,
        horizon=horizon,
        transaction_cost_bps=transaction_cost_bps,
    )
    validation.replication = _replicate_market_factor_rule(
        target=target,
        target_rows=target_rows,
        samples=samples,
        candidates=candidates,
        horizon=horizon,
        transaction_cost_bps=max(transaction_cost_bps, 25.0),
    )
    if insufficient:
        validation.status = "insufficient_data"
    return factors, links, validation


def _mine_cross_sectional_factors(
    session: Session,
    *,
    question_text: str,
    horizon: int = 5,
    transaction_cost_bps: float = 10,
) -> tuple[
    list[ModelFactorCandidate],
    list[ModelNonlinearFactorLink],
    ModelCrossSectionalValidation,
]:
    """Rank one tradable universe with factor loadings learned only in training."""
    registered_rows = list(
        session.execute(
            select(MarketSeries, func.count(MarketObservation.observed_on))
            .outerjoin(MarketObservation, MarketObservation.series_id == MarketSeries.series_id)
            .where(MarketSeries.category.in_(TRADABLE_CATEGORIES))
            .group_by(MarketSeries.series_id)
        )
    )
    provider_history_ids = {
        series_id
        for series_id in session.scalars(
            select(MarketPriceBackfillState.series_id).where(
                MarketPriceBackfillState.series_id.is_not(None)
            )
        )
        if series_id is not None
    }
    verified_history_ids = verified_provider_history_series_ids(session)
    identity_rejected = {
        series_id for series_id in provider_history_ids if series_id not in verified_history_ids
    }
    safe_rows = [row for row in registered_rows if row[0].series_id not in identity_rejected]
    universe_rows = [row for row in safe_rows if row[1] >= 60][:100]
    incomplete_assets = [row[0].series_id for row in safe_rows if row[1] < 60]
    incomplete_assets.extend(f"identity:{series_id}" for series_id in sorted(identity_rejected))
    expected_asset_count = len(registered_rows)
    fallback_id = "cross_section:insufficient_macro_factors"
    if not universe_rows:
        return (
            [],
            [],
            _empty_cross_sectional_validation(
                factor_ids=[fallback_id],
                asset_count=0,
                expected_asset_count=expected_asset_count,
                incomplete_assets=incomplete_assets,
                horizon=horizon,
                transaction_cost_bps=transaction_cost_bps,
                limitation="没有至少60期历史的股票、地区代理、股指或商品序列。",
            ),
        )

    reference, _ = max(
        universe_rows,
        key=lambda row: (
            {"SP500": 5, "TD:SPY": 4, "NASDAQCOM": 3, "TD:QQQ": 2}.get(
                row[0].series_id,
                0,
            ),
            row[1],
        ),
    )
    reference_rows = _load_series(session, reference.series_id)
    samples = _target_samples(reference_rows, horizon=horizon)
    split_index = int(len(samples) * 0.7)
    split_date = samples[split_index][0] if split_index < len(samples) else None

    predictor_rows = list(
        session.execute(
            select(MarketSeries, func.count(MarketObservation.observed_on))
            .join(MarketObservation, MarketObservation.series_id == MarketSeries.series_id)
            .where(~MarketSeries.category.in_(TRADABLE_CATEGORIES))
            .group_by(MarketSeries.series_id)
            .having(func.count(MarketObservation.observed_on) >= 36)
        )
    )
    ranked_predictors = sorted(
        predictor_rows,
        key=lambda row: _predictor_relevance(row[0], question_text),
        reverse=True,
    )[:18]
    candidates: list[dict[str, Any]] = []
    for series, _ in ranked_predictors:
        changes = _series_changes(_load_series(session, series.series_id))
        paired = _pair_feature(samples, changes)
        train = [row for row in paired if split_date is not None and row[2] < split_date]
        correlation = _pearson([row[1] for row in train], [row[3] for row in train])
        if correlation is None or len(train) < 18:
            continue
        candidates.append(
            {
                "series": series,
                "changes": changes,
                "paired": paired,
                "train": train,
                "correlation": correlation,
                "training_p_value": _correlation_p_value(correlation, len(train)),
            }
        )
    _apply_bh_qvalues(candidates)
    selected = sorted(candidates, key=lambda item: abs(item["correlation"]), reverse=True)[:3]
    robust_selected = sorted(
        [item for item in candidates if item.get("adjusted_q_value", 1.0) <= 0.1],
        key=lambda item: abs(item["correlation"]),
        reverse=True,
    )[:3]
    factors = [
        ModelFactorCandidate(
            factor_id=f"cross_section:{item['series'].series_id}:lagged_change5",
            name=f"{item['series'].name} 横截面暴露因子",
            factor_type="economic",
            direction="regime_dependent",
            transformation="rolling_zscore",
            lag_days=1,
            hypothesis=(
                f"用训练期估计各资产对 {item['series'].name} 的暴露，并在每个样本外"
                f"时点按综合暴露分数排序，检验未来{horizon}期收益差异。"
            ),
            evidence_refs=[],
            confidence=min(0.55, max(0.1, abs(float(item["correlation"])) * 0.7)),
            training_p_value=item.get("training_p_value"),
            adjusted_q_value=item.get("adjusted_q_value"),
        )
        for item in selected
    ]
    factor_ids = [factor.factor_id for factor in factors] or [fallback_id]
    links: list[ModelNonlinearFactorLink] = []
    if len(factor_ids) >= 2:
        links.append(
            ModelNonlinearFactorLink(
                link_id=f"cross_section:rank:{reference.series_id}",
                input_factor_ids=factor_ids,
                operator="interaction",
                condition=(
                    "用训练期因子暴露乘以当期滞后宏观状态；按综合分数横截面排序，"
                    "只在样本外做多最高组并做空最低组。"
                ),
                expected_output="检验股票、行业ETF、地区市场、债券、货币与商品的相对收益差",
                rationale=(
                    "相同宏观冲击对不同资产的敏感度并不相同；横截面组合检验可区分"
                    "普遍市场上涨与可交易的相对价值信号。"
                ),
                evidence_refs=[],
                confidence=min(0.55, fmean(abs(float(item["correlation"])) for item in selected)),
            )
        )
    validation = _validate_cross_sectional_factors(
        session,
        universe_rows=universe_rows,
        reference=reference,
        reference_rows=reference_rows,
        samples=samples,
        split_date=split_date,
        selected=selected,
        robust_selected=robust_selected,
        candidate_factor_tests=len(candidates),
        expected_asset_count=expected_asset_count,
        incomplete_assets=incomplete_assets,
        factor_ids=factor_ids,
        horizon=horizon,
        transaction_cost_bps=transaction_cost_bps,
    )
    return factors, links, validation


def _validate_cross_sectional_factors(
    session: Session,
    *,
    universe_rows: list[tuple[MarketSeries, int]],
    reference: MarketSeries,
    reference_rows: list[tuple[date, float]],
    samples: list[tuple[date, float, date]],
    split_date: date | None,
    selected: list[dict[str, Any]],
    robust_selected: list[dict[str, Any]],
    candidate_factor_tests: int,
    expected_asset_count: int,
    incomplete_assets: list[str],
    factor_ids: list[str],
    horizon: int,
    transaction_cost_bps: float,
) -> ModelCrossSectionalValidation:
    if split_date is None or not selected:
        return _empty_cross_sectional_validation(
            factor_ids=factor_ids,
            asset_count=len(universe_rows),
            expected_asset_count=expected_asset_count,
            incomplete_assets=incomplete_assets,
            horizon=horizon,
            transaction_cost_bps=transaction_cost_bps,
            limitation="共同训练样本或非交易型宏观因子不足。",
            reference_rows=reference_rows,
            split_date=split_date,
        )

    factor_feature_maps = [
        {observed_on: value for observed_on, value, _, _ in item["paired"]} for item in selected
    ]
    train_factor_stats: list[tuple[float, float]] = []
    for item in selected:
        values = [row[1] for row in item["train"]]
        train_factor_stats.append((fmean(values), pstdev(values) if len(values) > 1 else 0.0))

    asset_returns: dict[str, dict[date, float]] = {}
    asset_models: dict[str, dict[str, Any]] = {}
    for asset, _ in universe_rows:
        asset_rows = _load_series(session, asset.series_id)
        returns = _aligned_asset_forward_returns(
            asset_rows,
            samples,
            listed_from=asset.listed_from,
            listed_until=asset.listed_until,
            delisting_return=asset.delisting_return,
        )
        asset_returns[asset.series_id] = returns
        loadings: dict[str, float] = {}
        used_observations = 0
        for factor_id, feature_map in zip(factor_ids, factor_feature_maps, strict=True):
            pairs = [
                (feature_map[observed_on], returns[observed_on])
                for observed_on, _, outcome_on in samples
                if outcome_on < split_date and observed_on in feature_map and observed_on in returns
            ]
            correlation = _pearson(
                [pair[0] for pair in pairs],
                [pair[1] for pair in pairs],
            )
            if correlation is not None and len(pairs) >= 18:
                loadings[factor_id] = float(correlation)
                used_observations = max(used_observations, len(pairs))
        if not loadings:
            continue
        signed_sum = sum(loadings.values())
        magnitude = math.sqrt(sum(value * value for value in loadings.values()))
        asset_models[asset.series_id] = {
            "series": asset,
            "loadings": loadings,
            "train_observations": used_observations,
            "composite_exposure": math.copysign(magnitude, signed_sum or 1.0),
            "available_from": asset_rows[0][0] if asset_rows else None,
            "available_until": asset_rows[-1][0] if asset_rows else None,
            **_asset_neutralization_metadata(asset),
        }

    top_returns: list[float] = []
    bottom_returns: list[float] = []
    long_short_returns: list[float] = []
    equal_returns: list[float] = []
    asset_oos_returns: dict[str, list[float]] = {series_id: [] for series_id in asset_models}
    latest_scores: dict[str, float] = {}
    latest_long: set[str] = set()
    latest_short: set[str] = set()
    previous_long: set[str] | None = None
    previous_short: set[str] | None = None
    previous_equal: set[str] | None = None
    last_bucket_size = 0
    hits = 0
    train_rebalances = 0

    for observed_on, _, outcome_on in samples:
        raw_features = [feature_map.get(observed_on) for feature_map in factor_feature_maps]
        if any(value is None for value in raw_features):
            continue
        standardized = [
            0.0 if deviation <= 1e-12 else (float(value) - mean) / deviation
            for value, (mean, deviation) in zip(
                raw_features,
                train_factor_stats,
                strict=True,
            )
        ]
        if outcome_on < split_date:
            train_rebalances += 1
            continue
        if observed_on < split_date:
            continue

        scored: list[tuple[float, str, float]] = []
        for series_id, model in asset_models.items():
            forward_return = asset_returns[series_id].get(observed_on)
            if forward_return is None:
                continue
            score = sum(
                model["loadings"].get(factor_id, 0.0) * value
                for factor_id, value in zip(factor_ids, standardized, strict=True)
            )
            scored.append((score, series_id, forward_return))
            asset_oos_returns[series_id].append(forward_return)
        if len(scored) < 6:
            continue
        scored.sort(key=lambda row: row[0])
        bucket_size = max(1, min(12, len(scored) // 5))
        short_rows = scored[:bucket_size]
        long_rows = scored[-bucket_size:]
        long_ids = {row[1] for row in long_rows}
        short_ids = {row[1] for row in short_rows}
        equal_ids = {row[1] for row in scored}
        long_raw = fmean(row[2] for row in long_rows)
        bottom_raw = fmean(row[2] for row in short_rows)
        equal_raw = fmean(row[2] for row in scored)
        long_cost = _turnover_cost(long_ids, previous_long, transaction_cost_bps)
        short_cost = _turnover_cost(short_ids, previous_short, transaction_cost_bps)
        equal_cost = _turnover_cost(equal_ids, previous_equal, transaction_cost_bps)
        top_returns.append(long_raw - long_cost)
        bottom_returns.append(bottom_raw)
        long_short_return = long_raw - bottom_raw - long_cost - short_cost
        long_short_returns.append(long_short_return)
        equal_returns.append(equal_raw - equal_cost)
        hits += int(long_short_return > 0)
        previous_long, previous_short, previous_equal = long_ids, short_ids, equal_ids
        latest_scores = {series_id: score for score, series_id, _ in scored}
        latest_long, latest_short = long_ids, short_ids
        last_bucket_size = bucket_size

    robustness, robust_scores, robust_long, robust_short = _run_robust_cross_sectional(
        asset_models=asset_models,
        asset_returns=asset_returns,
        samples=samples,
        split_date=split_date,
        selected=robust_selected,
        candidate_factor_tests=candidate_factor_tests,
        horizon=horizon,
        transaction_cost_bps=transaction_cost_bps,
    )
    survivorship_audit = _build_survivorship_audit(
        session=session,
        asset_models=asset_models,
        asset_returns=asset_returns,
        samples=samples,
        split_date=split_date,
    )
    exposure_rows = [
        ModelCrossSectionAssetExposure(
            series_id=series_id,
            name=model["series"].name,
            category=model["series"].category,
            train_observations=model["train_observations"],
            factor_loadings=model["loadings"],
            composite_exposure=model["composite_exposure"],
            sector=model["sector"],
            region=model["region"],
            neutralization_group=model["neutralization_group"],
            latest_score=latest_scores.get(series_id),
            latest_bucket=(
                "long"
                if series_id in latest_long
                else "short"
                if series_id in latest_short
                else "neutral"
                if series_id in latest_scores
                else "unavailable"
            ),
            robust_latest_score=robust_scores.get(series_id),
            robust_latest_bucket=(
                "long"
                if series_id in robust_long
                else "short"
                if series_id in robust_short
                else "neutral"
                if series_id in robust_scores
                else "unavailable"
            ),
            oos_mean_return=(
                fmean(asset_oos_returns[series_id]) if asset_oos_returns[series_id] else None
            ),
        )
        for series_id, model in asset_models.items()
    ]
    exposure_rows.sort(
        key=lambda row: (
            {"long": 0, "short": 1, "neutral": 2, "unavailable": 3}[row.latest_bucket],
            -(row.latest_score or 0.0),
        )
    )

    count = len(long_short_returns)
    top_total = _compound(top_returns) if top_returns else None
    bottom_total = _compound(bottom_returns) if bottom_returns else None
    long_short_total = _compound(long_short_returns) if long_short_returns else None
    equal_total = _compound(equal_returns) if equal_returns else None
    top_excess = (
        top_total - equal_total if top_total is not None and equal_total is not None else None
    )
    if count < 8 or len(asset_models) < 6:
        status = "insufficient_data"
    elif (
        long_short_total is not None
        and top_excess is not None
        and long_short_total > 0
        and top_excess > 0
        and hits / count > 0.5
    ):
        status = "out_of_sample_positive"
    else:
        status = "out_of_sample_negative"

    return ModelCrossSectionalValidation(
        universe_name="股票、行业ETF、国家/地区市场、股指、债券、货币与商品共同横截面",
        asset_count=len(asset_models),
        expected_asset_count=expected_asset_count,
        asset_category_counts=dict(
            sorted(
                {
                    category: sum(
                        1 for model in asset_models.values() if model["series"].category == category
                    )
                    for category in {model["series"].category for model in asset_models.values()}
                }.items()
            )
        ),
        incomplete_assets=incomplete_assets[:100],
        factor_ids=factor_ids,
        start_date=reference_rows[0][0].isoformat() if reference_rows else None,
        end_date=reference_rows[-1][0].isoformat() if reference_rows else None,
        train_end_date=split_date.isoformat(),
        rebalance_horizon_days=horizon,
        train_rebalances=train_rebalances,
        test_rebalances=count,
        long_bucket_size=last_bucket_size,
        short_bucket_size=last_bucket_size,
        transaction_cost_bps=transaction_cost_bps,
        top_bucket_return=top_total,
        bottom_bucket_return=bottom_total,
        long_short_return=long_short_total,
        equal_weight_return=equal_total,
        top_vs_equal_excess=top_excess,
        hit_rate=hits / count if count else None,
        max_drawdown=_max_drawdown(long_short_returns) if long_short_returns else None,
        sharpe_like=_sharpe_like(long_short_returns, horizon=horizon),
        status=status,
        asset_exposures=exposure_rows[:100],
        methodology=(
            f"以 {reference.name} 的共同日期建立{horizon}期非重叠再平衡表；训练期估计每项"
            "资产对同一组滞后因子的相关暴露。验证期不重估参数，每期做多综合分数最高组、"
            "做空最低组，并与全资产等权组合比较。"
        ),
        leakage_guard=(
            "按日期70/30切分；训练收益终点必须早于验证起点；因子只允许使用再平衡日"
            "之前的最后观测，均值、波动率、因子筛选和资产暴露均冻结于训练期。"
        ),
        limitations=[
            "当前资产集合由本地现存序列构成，仍可能存在幸存者偏差和退市样本缺失。",
            "股指、ETF、股票和商品之间可能持仓重叠，横截面观测并非完全独立。",
            "国家/地区市场使用可交易代理时，汇率、跟踪误差和交易时区会影响结果。",
            "成本按换手比例作简化估计，尚未模拟做空借券、滑点和市场冲击。",
            "原始检验未校正多重比较；下方稳健性结果另行执行FDR校正。",
        ],
        robustness=robustness,
        survivorship_audit=survivorship_audit,
    )


def _run_robust_cross_sectional(
    *,
    asset_models: dict[str, dict[str, Any]],
    asset_returns: dict[str, dict[date, float]],
    samples: list[tuple[date, float, date]],
    split_date: date,
    selected: list[dict[str, Any]],
    candidate_factor_tests: int,
    horizon: int,
    transaction_cost_bps: float,
    training_window_rebalances: int = 252,
    reestimate_every_rebalances: int = 12,
) -> tuple[ModelCrossSectionRobustness, dict[str, float], set[str], set[str]]:
    factor_ids = [f"cross_section:{item['series'].series_id}:lagged_change5" for item in selected]
    groups = {
        str(model["neutralization_group"])
        for model in asset_models.values()
        if model.get("neutralization_group")
    }
    if not selected:
        return (
            ModelCrossSectionRobustness(
                training_window_rebalances=training_window_rebalances,
                reestimate_every_rebalances=reestimate_every_rebalances,
                neutralization_dimensions=["industry", "region", "asset_class"],
                neutralization_group_count=len(groups),
                candidate_factor_tests=candidate_factor_tests,
                adjusted_significant_factors=0,
                factor_ids=[],
                multiple_testing_method="Benjamini-Hochberg FDR 10%（仅使用初始训练区间）",
                test_rebalances=0,
                status="insufficient_data",
                methodology="没有因子通过训练期多重检验校正，因此不生成稳健组合。",
                limitations=[
                    "未通过FDR阈值不等于不存在经济机制，只表示现有样本不足以支持该交易因子。"
                ],
            ),
            {},
            set(),
            set(),
        )

    feature_maps = [
        {observed_on: value for observed_on, value, _, _ in item["paired"]} for item in selected
    ]
    top_returns: list[float] = []
    bottom_returns: list[float] = []
    long_short_returns: list[float] = []
    equal_returns: list[float] = []
    previous_long: set[str] | None = None
    previous_short: set[str] | None = None
    previous_equal: set[str] | None = None
    latest_scores: dict[str, float] = {}
    latest_long: set[str] = set()
    latest_short: set[str] = set()
    rolling_loadings: dict[str, dict[str, float]] = {}
    rolling_stats: list[tuple[float, float]] = []
    period_attribution: list[dict[str, dict[str, float]]] = []
    attribution_membership: dict[tuple[str, str], list[int]] = {}
    test_step = 0
    hits = 0

    for observed_on, _, _ in samples:
        if observed_on < split_date:
            continue
        raw_features = [feature_map.get(observed_on) for feature_map in feature_maps]
        if any(value is None for value in raw_features):
            continue
        if test_step % reestimate_every_rebalances == 0 or not rolling_loadings:
            available_history = [
                row
                for row in samples
                if row[2] < observed_on
                and all(row[0] in feature_map for feature_map in feature_maps)
            ][-training_window_rebalances:]
            rolling_stats = []
            for feature_map in feature_maps:
                values = [feature_map[row[0]] for row in available_history]
                rolling_stats.append((fmean(values), pstdev(values) if len(values) > 1 else 0.0))
            rolling_loadings = {}
            for series_id in asset_models:
                returns = asset_returns[series_id]
                loadings: dict[str, float] = {}
                for factor_id, feature_map in zip(factor_ids, feature_maps, strict=True):
                    pairs = [
                        (feature_map[row[0]], returns[row[0]])
                        for row in available_history
                        if row[0] in returns
                    ]
                    correlation = _pearson(
                        [pair[0] for pair in pairs],
                        [pair[1] for pair in pairs],
                    )
                    if correlation is not None and len(pairs) >= 24:
                        loadings[factor_id] = float(correlation)
                if loadings:
                    rolling_loadings[series_id] = loadings

        standardized = [
            0.0 if deviation <= 1e-12 else (float(value) - mean) / deviation
            for value, (mean, deviation) in zip(raw_features, rolling_stats, strict=True)
        ]
        raw_scores: dict[str, float] = {}
        returns_now: dict[str, float] = {}
        for series_id, loadings in rolling_loadings.items():
            forward_return = asset_returns[series_id].get(observed_on)
            if forward_return is None:
                continue
            raw_scores[series_id] = sum(
                loadings.get(factor_id, 0.0) * value
                for factor_id, value in zip(factor_ids, standardized, strict=True)
            )
            returns_now[series_id] = forward_return
        neutral_scores = _neutralize_cross_section_scores(raw_scores, asset_models)
        scored = sorted(
            (
                score,
                series_id,
                returns_now[series_id],
            )
            for series_id, score in neutral_scores.items()
            if series_id in returns_now
        )
        test_step += 1
        if len(scored) < 6:
            continue
        bucket_size = max(1, min(12, len(scored) // 5))
        short_rows = scored[:bucket_size]
        long_rows = scored[-bucket_size:]
        long_ids = {row[1] for row in long_rows}
        short_ids = {row[1] for row in short_rows}
        equal_ids = {row[1] for row in scored}
        long_raw = fmean(row[2] for row in long_rows)
        bottom_raw = fmean(row[2] for row in short_rows)
        equal_raw = fmean(row[2] for row in scored)
        long_cost = _turnover_cost(long_ids, previous_long, transaction_cost_bps)
        short_cost = _turnover_cost(short_ids, previous_short, transaction_cost_bps)
        equal_cost = _turnover_cost(equal_ids, previous_equal, transaction_cost_bps)
        top_returns.append(long_raw - long_cost)
        bottom_returns.append(bottom_raw)
        long_short_return = long_raw - bottom_raw - long_cost - short_cost
        long_short_returns.append(long_short_return)
        period_attribution.append(
            _portfolio_group_components(
                long_rows=long_rows,
                short_rows=short_rows,
                asset_models=asset_models,
                transaction_cost=long_cost + short_cost,
                membership_counts=attribution_membership,
            )
        )
        equal_returns.append(equal_raw - equal_cost)
        hits += int(long_short_return > 0)
        previous_long, previous_short, previous_equal = long_ids, short_ids, equal_ids
        latest_scores = neutral_scores
        latest_long, latest_short = long_ids, short_ids

    count = len(long_short_returns)
    top_total = _compound(top_returns) if top_returns else None
    bottom_total = _compound(bottom_returns) if bottom_returns else None
    long_short_total = _compound(long_short_returns) if long_short_returns else None
    equal_total = _compound(equal_returns) if equal_returns else None
    top_excess = (
        top_total - equal_total if top_total is not None and equal_total is not None else None
    )
    contribution_attribution, attribution_reconciled = _link_portfolio_contributions(
        period_attribution,
        long_short_returns,
        membership_counts=attribution_membership,
    )
    if count < 8:
        status = "insufficient_data"
    elif (
        long_short_total is not None
        and top_excess is not None
        and long_short_total > 0
        and top_excess > 0
        and hits / count > 0.5
    ):
        status = "out_of_sample_positive"
    else:
        status = "out_of_sample_negative"
    return (
        ModelCrossSectionRobustness(
            training_window_rebalances=training_window_rebalances,
            reestimate_every_rebalances=reestimate_every_rebalances,
            neutralization_dimensions=["industry", "region", "asset_class"],
            neutralization_group_count=len(groups),
            candidate_factor_tests=candidate_factor_tests,
            adjusted_significant_factors=len(selected),
            factor_ids=factor_ids,
            multiple_testing_method="Benjamini-Hochberg FDR 10%（仅使用初始训练区间）",
            test_rebalances=count,
            top_bucket_return=top_total,
            bottom_bucket_return=bottom_total,
            long_short_return=long_short_total,
            equal_weight_return=equal_total,
            top_vs_equal_excess=top_excess,
            hit_rate=hits / count if count else None,
            max_drawdown=_max_drawdown(long_short_returns) if long_short_returns else None,
            sharpe_like=_sharpe_like(long_short_returns, horizon=horizon),
            contribution_attribution=contribution_attribution,
            attribution_reconciled=attribution_reconciled,
            status=status,
            methodology=(
                f"先在初始训练区间对{candidate_factor_tests}项候选因子执行BH-FDR校正；"
                f"只保留q≤10%的因子。之后每{reestimate_every_rebalances}次再平衡，"
                f"用当时可获得的最近{training_window_rebalances}个已结束样本重新估计暴露，"
                "并按美国股票行业、国家代理地区和资产类别对分数去均值/标准化。"
            ),
            limitations=[
                "行业和地区分类来自受审目录，未分类资产只能按较宽资产类别中性化。",
                "相关系数显著性近似未完全消除时间序列自相关，FDR结果仍是探索性的。",
                "滚动重估会增加参数不稳定性和换手，真实借券与冲击成本可能更高。",
                "中性化降低集中暴露，但不能消除ETF持仓重叠、汇率和共同市场Beta。",
            ],
        ),
        latest_scores,
        latest_long,
        latest_short,
    )


def _portfolio_group_components(
    *,
    long_rows: list[tuple[float, str, float]],
    short_rows: list[tuple[float, str, float]],
    asset_models: dict[str, dict[str, Any]],
    transaction_cost: float,
    membership_counts: dict[tuple[str, str], list[int]],
) -> dict[str, dict[str, float]]:
    dimensions = {
        "asset_class": lambda model: model["series"].category,
        "industry": lambda model: model.get("sector") or "Unclassified",
        "region": lambda model: model.get("region") or "Unclassified",
    }
    result: dict[str, dict[str, float]] = {}
    for dimension, group_for in dimensions.items():
        components: dict[str, float] = {}
        long_groups: set[str] = set()
        short_groups: set[str] = set()
        for _, series_id, forward_return in long_rows:
            group = str(group_for(asset_models[series_id]))
            components[group] = components.get(group, 0.0) + forward_return / len(long_rows)
            long_groups.add(group)
        for _, series_id, forward_return in short_rows:
            group = str(group_for(asset_models[series_id]))
            components[group] = components.get(group, 0.0) - forward_return / len(short_rows)
            short_groups.add(group)
        components["Transaction cost"] = components.get("Transaction cost", 0.0) - transaction_cost
        for group in long_groups | short_groups:
            counts = membership_counts.setdefault((dimension, group), [0, 0])
            counts[0] += int(group in long_groups)
            counts[1] += int(group in short_groups)
        result[dimension] = components
    return result


def _link_portfolio_contributions(
    periods: list[dict[str, dict[str, float]]],
    portfolio_returns: list[float],
    *,
    membership_counts: dict[tuple[str, str], list[int]],
) -> tuple[list[ModelPortfolioContribution], bool]:
    if not periods or len(periods) != len(portfolio_returns):
        return [], False
    linked: dict[tuple[str, str], float] = {}
    wealth = 1.0
    for period, portfolio_return in zip(periods, portfolio_returns, strict=True):
        for dimension, components in period.items():
            for group, value in components.items():
                key = (dimension, group)
                linked[key] = linked.get(key, 0.0) + wealth * value
        wealth *= max(0.0, 1.0 + portfolio_return)
    total = wealth - 1.0
    dimensions = {dimension for dimension, _ in linked}
    reconciled = all(
        math.isclose(
            sum(
                value
                for (item_dimension, _), value in linked.items()
                if item_dimension == dimension
            ),
            total,
            rel_tol=1e-8,
            abs_tol=1e-8,
        )
        for dimension in dimensions
    )
    rows = [
        ModelPortfolioContribution(
            dimension=dimension,
            group=group,
            contribution=value,
            share_of_total=value / total if abs(total) > 1e-12 else None,
            long_periods=membership_counts.get((dimension, group), [0, 0])[0],
            short_periods=membership_counts.get((dimension, group), [0, 0])[1],
        )
        for (dimension, group), value in linked.items()
    ]
    rows.sort(key=lambda row: (row.dimension, -abs(row.contribution), row.group))
    return rows[:100], reconciled


def _build_survivorship_audit(
    *,
    session: Session,
    asset_models: dict[str, dict[str, Any]],
    asset_returns: dict[str, dict[date, float]],
    samples: list[tuple[date, float, date]],
    split_date: date,
) -> ModelSurvivorshipAudit:
    catalog = alpha_vantage_listing_coverage(session)
    discovered_delisted = int(catalog["delisted_assets"])
    price_covered_delisted = int(catalog["local_price_covered_delisted_assets"])
    missing_price_delisted = int(catalog["missing_price_delisted_assets"])
    historical = [
        model
        for model in asset_models.values()
        if model["series"].listing_status in {"delisted", "historical"}
    ]
    explicit_lifecycle = sum(
        1
        for model in asset_models.values()
        if model["series"].listed_from is not None or model["series"].listed_until is not None
    )
    delisting_returns_covered = sum(
        1 for model in historical if model["series"].delisting_return is not None
    )
    delisting_returns_missing = len(historical) - delisting_returns_covered
    eligible_counts = [
        sum(1 for series_id in asset_models if observed_on in asset_returns.get(series_id, {}))
        for observed_on, _, _ in samples
        if observed_on >= split_date
    ]
    ordered = sorted(eligible_counts)
    if not ordered:
        median_eligible = 0.0
    elif len(ordered) % 2:
        median_eligible = float(ordered[len(ordered) // 2])
    else:
        middle = len(ordered) // 2
        median_eligible = (ordered[middle - 1] + ordered[middle]) / 2
    if not historical:
        status = "survivor_only"
    elif (
        delisting_returns_missing
        or explicit_lifecycle < len(historical)
        or missing_price_delisted
    ):
        status = "partial_historical"
    else:
        status = "point_in_time_audited"
    gaps = ["当前受审目录仍不等于任一历史指数的完整逐日成分清单。"]
    if not historical:
        gaps.append("尚未导入可验证的退市资产价格，因此仍存在幸存者偏差。")
    if discovered_delisted and missing_price_delisted:
        gaps.append(
            f"Alpha Vantage 已发现 {discovered_delisted} 项退市生命周期，"
            f"其中 {missing_price_delisted} 项尚无本地历史价格；清单不会被当成价格使用。"
        )
    if delisting_returns_missing:
        gaps.append(
            f"{delisting_returns_missing} 项历史资产缺少退市收益，跨越退市日的持有期已排除。"
        )
    if int(catalog["unresolved_identity_assets"]):
        gaps.append(
            f"{int(catalog['unresolved_identity_assets'])} 项历史价格尚未通过 FIGI/名称/交易所"
            "交叉身份核验，已从因子资产池排除。"
        )
    if int(catalog["ambiguous_identity_assets"]) or int(
        catalog["mismatched_identity_assets"]
    ):
        gaps.append(
            "身份映射存在歧义或名称冲突的价格序列不会进入回测，直至人工或新增来源确认。"
        )
    if int(catalog["lifecycle_conflict_identity_assets"]):
        gaps.append(
            f"{int(catalog['lifecycle_conflict_identity_assets'])} 项价格序列末端晚于 SEC "
            "终止上市证据，已按代码复用风险隔离。"
        )
    return ModelSurvivorshipAudit(
        point_in_time_membership_enforced=True,
        status=status,
        active_or_unknown_assets=len(asset_models) - len(historical),
        historical_assets=len(historical),
        discovered_delisted_assets=discovered_delisted,
        local_price_covered_delisted_assets=price_covered_delisted,
        missing_price_delisted_assets=missing_price_delisted,
        price_backfill_queued_assets=int(catalog["price_backfill_queued_assets"]),
        price_backfill_pending_assets=int(catalog["price_backfill_pending_assets"]),
        price_backfill_factor_ready_assets=int(
            catalog["price_backfill_factor_ready_assets"]
        ),
        price_backfill_partial_assets=int(catalog["price_backfill_partial_assets"]),
        price_backfill_unavailable_assets=int(
            catalog["price_backfill_unavailable_assets"]
        ),
        price_backfill_ticker_reused_assets=int(
            catalog["price_backfill_ticker_reused_assets"]
        ),
        identity_verified_assets=int(catalog["verified_identity_assets"]),
        identity_unresolved_assets=int(catalog["unresolved_identity_assets"]),
        identity_ambiguous_assets=int(catalog["ambiguous_identity_assets"]),
        identity_mismatched_assets=int(catalog["mismatched_identity_assets"]),
        identity_lifecycle_conflict_assets=int(
            catalog["lifecycle_conflict_identity_assets"]
        ),
        identity_sec_cik_assets=int(catalog["sec_cik_assets"]),
        terminal_outcomes_verified=int(catalog["verified_outcomes"]),
        terminal_outcomes_requiring_evidence=int(
            catalog["outcomes_requiring_evidence"]
        ),
        terminal_outcomes_requiring_identity=int(
            catalog["outcomes_requiring_identity"]
        ),
        terminal_evidence_assets_searched=int(catalog["evidence_assets_searched"]),
        terminal_evidence_cik_resolved=int(catalog["evidence_assets_cik_resolved"]),
        terminal_evidence_metadata_candidates=int(
            catalog["evidence_metadata_candidates"]
        ),
        terminal_evidence_value_candidates=int(catalog["evidence_value_candidates"]),
        terminal_evidence_review_ready=int(catalog["evidence_review_ready"]),
        terminal_evidence_accepted=int(catalog["evidence_terminal_accepted"]),
        supporting_evidence_accepted=int(catalog["evidence_supporting_accepted"]),
        terminal_evidence_needs_more=int(catalog["evidence_needs_more"]),
        terminal_evidence_lifecycle_segmented_assets=int(
            catalog["evidence_lifecycle_segmented_assets"]
        ),
        terminal_evidence_body_contact_required=int(
            catalog["evidence_body_contact_required_assets"]
        ),
        terminal_evidence_lifecycle_conflicts=int(
            catalog["evidence_lifecycle_conflict_assets"]
        ),
        lifecycle_catalog_start=(
            catalog["point_in_time_boundary"].isoformat()
            if catalog["record_count"]
            else None
        ),
        lifecycle_catalog_end=(
            catalog["ends_at"].isoformat() if catalog["ends_at"] is not None else None
        ),
        assets_with_explicit_lifecycle=explicit_lifecycle,
        delisting_returns_covered=delisting_returns_covered,
        delisting_returns_missing=delisting_returns_missing,
        min_eligible_assets=min(eligible_counts, default=0),
        median_eligible_assets=median_eligible,
        max_eligible_assets=max(eligible_counts, default=0),
        methodology=(
            "每个再平衡日只允许当日已上市且仍可形成未来收益的资产进入排序；上市前、"
            "退市后和缺少退市收益的跨退市持有期不会被回填或向前延伸。Alpha Vantage "
            "生命周期目录只用于发现历史资产；自动回填序列还必须通过 FIGI/名称/交易所"
            "身份门；SEC 文件检索只生成候选，退市后最终价值仍只接受有来源的人工核验结果。"
        ),
        known_gaps=gaps,
    )


def _asset_neutralization_metadata(series: MarketSeries) -> dict[str, str | None]:
    series_id = series.series_id
    if series.neutralization_group:
        return {
            "sector": series.sector,
            "region": series.region,
            "neutralization_group": series.neutralization_group,
        }
    if series_id.startswith("EQ:"):
        ticker = series_id.removeprefix("EQ:")
        sector = COMPANY_SECTOR_BY_TICKER.get(ticker, "Unclassified equity")
        return {
            "sector": sector,
            "region": "north_america",
            "neutralization_group": f"industry:{sector}",
        }
    if series_id.startswith("TD:"):
        symbol = series_id.removeprefix("TD:")
        factor_definition = FACTOR_ASSET_BY_SYMBOL.get(symbol)
        if factor_definition is not None:
            return {
                "sector": factor_definition.sector,
                "region": factor_definition.region,
                "neutralization_group": factor_definition.neutralization_group,
            }
        country = COUNTRY_BY_PROXY.get(symbol)
        region = REGION_BY_COUNTRY.get(country or "", "other_region")
        return {
            "sector": None,
            "region": region,
            "neutralization_group": f"region:{region}",
        }
    if series.category in {"equity_index", "market_index"}:
        return {
            "sector": None,
            "region": "north_america" if series_id in {"SP500", "NASDAQCOM"} else None,
            "neutralization_group": "asset_class:market_index",
        }
    if series.category == "commodity_price":
        return {
            "sector": "Energy",
            "region": "global",
            "neutralization_group": "asset_class:commodity",
        }
    return {
        "sector": None,
        "region": None,
        "neutralization_group": f"asset_class:{series.category}",
    }


def _neutralize_cross_section_scores(
    scores: dict[str, float],
    asset_models: dict[str, dict[str, Any]],
) -> dict[str, float]:
    if not scores:
        return {}
    all_values = list(scores.values())
    global_mean = fmean(all_values)
    global_deviation = pstdev(all_values) if len(all_values) > 1 else 0.0
    grouped: dict[str, list[tuple[str, float]]] = {}
    for series_id, score in scores.items():
        group = str(asset_models[series_id].get("neutralization_group") or "unclassified")
        grouped.setdefault(group, []).append((series_id, score))
    neutral: dict[str, float] = {}
    for rows in grouped.values():
        values = [row[1] for row in rows]
        group_mean = fmean(values)
        group_deviation = pstdev(values) if len(values) > 1 else 0.0
        for series_id, score in rows:
            if group_deviation > 1e-12:
                neutral[series_id] = (score - group_mean) / group_deviation
            elif global_deviation > 1e-12:
                neutral[series_id] = (score - global_mean) / global_deviation
            else:
                neutral[series_id] = 0.0
    return neutral


def _empty_cross_sectional_validation(
    *,
    factor_ids: list[str],
    asset_count: int,
    expected_asset_count: int = 0,
    incomplete_assets: list[str] | None = None,
    horizon: int,
    transaction_cost_bps: float,
    limitation: str,
    reference_rows: list[tuple[date, float]] | None = None,
    split_date: date | None = None,
) -> ModelCrossSectionalValidation:
    rows = reference_rows or []
    return ModelCrossSectionalValidation(
        universe_name="股票、行业ETF、国家/地区市场、股指、债券、货币与商品共同横截面",
        asset_count=asset_count,
        expected_asset_count=expected_asset_count,
        incomplete_assets=(incomplete_assets or [])[:100],
        factor_ids=factor_ids,
        start_date=rows[0][0].isoformat() if rows else None,
        end_date=rows[-1][0].isoformat() if rows else None,
        train_end_date=split_date.isoformat() if split_date else None,
        rebalance_horizon_days=horizon,
        train_rebalances=0,
        test_rebalances=0,
        long_bucket_size=0,
        short_bucket_size=0,
        transaction_cost_bps=transaction_cost_bps,
        status="insufficient_data",
        asset_exposures=[],
        methodology="等待形成可冻结训练参数的共同时间轴和至少六项可交易资产。",
        leakage_guard="数据不足时不生成或宣称任何样本外盈利结论。",
        limitations=[limitation],
    )


def _validate_selected_factors(
    *,
    target: MarketSeries,
    target_rows: list[tuple[date, float]],
    samples: list[tuple[date, float, date]],
    split_date: date | None,
    selected: list[dict[str, Any]],
    factor_ids: list[str],
    horizon: int,
    transaction_cost_bps: float,
) -> ModelProfitValidation:
    start = target_rows[0][0].isoformat() if target_rows else None
    end = target_rows[-1][0].isoformat() if target_rows else None
    train_observations = sum(1 for row in samples if split_date is not None and row[2] < split_date)
    if split_date is None or not selected:
        return ModelProfitValidation(
            target_series_id=target.series_id,
            target_name=target.name,
            factor_ids=factor_ids,
            start_date=start,
            end_date=end,
            train_end_date=split_date.isoformat() if split_date else None,
            forecast_horizon_days=horizon,
            train_observations=train_observations,
            test_observations=0,
            transaction_cost_bps=transaction_cost_bps,
            status="insufficient_data",
            signal_rule="因子只在训练区间筛选，当前没有足够的共同样本形成验证信号。",
            leakage_guard="目标收益严格位于因子观测之后；验证期从未参与因子筛选。",
            limitations=["共同时间戳或训练样本不足。", "尚未形成可审计的样本外结果。"],
        )

    train_stats: list[tuple[float, float, float]] = []
    for item in selected:
        values = [row[1] for row in item["train"]]
        deviation = pstdev(values) if len(values) > 1 else 0.0
        train_stats.append((fmean(values), deviation, 1.0 if item["correlation"] >= 0 else -1.0))

    feature_maps = [{row[0]: row[1] for row in item["test"]} for item in selected]
    test_returns: list[float] = []
    strategy_returns: list[float] = []
    hits = 0
    last_position = 0
    for observed_on, forward_return, _ in samples:
        if observed_on < split_date:
            continue
        raw_values = [values.get(observed_on) for values in feature_maps]
        if any(value is None for value in raw_values):
            continue
        score = 0.0
        for value, (mean, deviation, direction) in zip(raw_values, train_stats, strict=True):
            if value is None or deviation <= 1e-12:
                continue
            score += direction * (value - mean) / deviation
        position = 1 if score >= 0 else -1
        cost = transaction_cost_bps / 10_000 if position != last_position else 0.0
        strategy_return = position * forward_return - cost
        test_returns.append(forward_return)
        strategy_returns.append(strategy_return)
        hits += int(position * forward_return > 0)
        last_position = position

    count = len(strategy_returns)
    if count < 8:
        status = "insufficient_data"
    else:
        strategy_total = _compound(strategy_returns)
        baseline_total = _compound(test_returns)
        status = (
            "out_of_sample_positive"
            if strategy_total > baseline_total and hits / count > 0.5
            else "out_of_sample_negative"
        )
    strategy_total = _compound(strategy_returns) if strategy_returns else None
    baseline_total = _compound(test_returns) if test_returns else None
    excess = (
        strategy_total - baseline_total
        if strategy_total is not None and baseline_total is not None
        else None
    )
    return ModelProfitValidation(
        target_series_id=target.series_id,
        target_name=target.name,
        factor_ids=factor_ids,
        start_date=start,
        end_date=end,
        train_end_date=split_date.isoformat(),
        forecast_horizon_days=horizon,
        train_observations=train_observations,
        test_observations=count,
        transaction_cost_bps=transaction_cost_bps,
        baseline_return=baseline_total,
        strategy_return=strategy_total,
        excess_return=excess,
        hit_rate=hits / count if count else None,
        max_drawdown=_max_drawdown(strategy_returns) if strategy_returns else None,
        sharpe_like=_sharpe_like(strategy_returns, horizon=horizon),
        status=status,
        signal_rule=(
            "训练期内选择绝对相关性最高的两个滞后变化因子，并只用训练期均值、"
            "波动率和方向构建阈值交互信号；验证期不重新调参。"
        ),
        leakage_guard=(
            "采用按日期70/30切分；训练样本的目标终点必须早于验证期起点；"
            "所有因子至少滞后一期，盈利指标只计算未参与选因的后30%样本。"
        ),
        limitations=[
            "该检验是探索性研究，尚未进行多重检验校正。",
            "回测使用收盘序列，未建模滑点、市场冲击、税费和真实成交约束。",
            "宏观数据发布时间与后续修订可能仍需更精细的逐期数据版本控制。",
        ],
    )


def _replicate_market_factor_rule(
    *,
    target: MarketSeries,
    target_rows: list[tuple[date, float]],
    samples: list[tuple[date, float, date]],
    candidates: list[dict[str, Any]],
    horizon: int,
    transaction_cost_bps: float,
) -> ModelFactorReplication:
    """Repeat selection on non-overlapping future blocks, then freeze one live signal."""
    ordered_samples = sorted(samples, key=lambda row: row[0])
    initial_train = max(24, int(len(ordered_samples) * 0.45))
    remaining = max(0, len(ordered_samples) - initial_train)
    trial_count = min(4, remaining // 8)
    if trial_count < 3 or not candidates or not target_rows:
        return ModelFactorReplication(
            protocol_version="factor_replication_v1_nonoverlap_fdr",
            trials=[],
            total_trials=0,
            valid_trials=0,
            passed_trials=0,
            pass_rate=None,
            stable_factor_ids=[],
            retention_status="insufficient_evidence",
            retention_reason=(
                "至少需要三个互不重叠的验证窗口、每窗八个结果及足够的训练期共同样本。"
            ),
            future_validation_status="not_registered",
            leakage_guard=(
                "每轮只使用该轮验证窗口开始前已经结束的目标收益选因；验证窗口互不重叠。"
            ),
        )

    test_samples = ordered_samples[initial_train:]
    block_size = len(test_samples) // trial_count
    trials: list[ModelFactorReplicationTrial] = []
    pooled_excess: list[float] = []
    selected_frequency: Counter[str] = Counter()
    for trial_index in range(trial_count):
        start_index = trial_index * block_size
        end_index = (
            len(test_samples)
            if trial_index == trial_count - 1
            else (trial_index + 1) * block_size
        )
        block = test_samples[start_index:end_index]
        if not block:
            continue
        cutoff = block[0][0]
        selected = _select_trial_candidates(candidates, cutoff=cutoff)
        selected_ids = [_market_factor_id(item) for item in selected]
        selected_frequency.update(selected_ids)
        trial_returns = _evaluate_trial_block(
            selected=selected,
            block=block,
            transaction_cost_bps=transaction_cost_bps,
        )
        strategy_returns = trial_returns["strategy_returns"]
        baseline_returns = trial_returns["baseline_returns"]
        excess_returns = trial_returns["excess_returns"]
        pooled_excess.extend(excess_returns)
        count = len(strategy_returns)
        strategy_total = _compound(strategy_returns) if strategy_returns else None
        baseline_total = _compound(baseline_returns) if baseline_returns else None
        excess_total = (
            strategy_total - baseline_total
            if strategy_total is not None and baseline_total is not None
            else None
        )
        hit_rate = trial_returns["hits"] / count if count else None
        if count < 8 or not selected:
            status: Literal["passed", "failed", "insufficient_data"] = "insufficient_data"
        elif (
            strategy_total is not None
            and baseline_total is not None
            and strategy_total > 0
            and strategy_total > baseline_total
            and hit_rate is not None
            and hit_rate > 0.5
        ):
            status = "passed"
        else:
            status = "failed"
        train_rows = [row for row in ordered_samples if row[2] < cutoff]
        trials.append(
            ModelFactorReplicationTrial(
                trial_id=f"walk-forward-{trial_index + 1}",
                train_end_date=train_rows[-1][2].isoformat() if train_rows else cutoff.isoformat(),
                test_start_date=block[0][0].isoformat(),
                test_end_date=block[-1][2].isoformat(),
                selected_factor_ids=selected_ids,
                train_observations=len(train_rows),
                test_observations=count,
                transaction_cost_bps=transaction_cost_bps,
                baseline_return=baseline_total,
                strategy_return=strategy_total,
                excess_return=excess_total,
                hit_rate=hit_rate,
                max_drawdown=(
                    _max_drawdown(strategy_returns) if strategy_returns else None
                ),
                sharpe_like=(
                    _sharpe_like(strategy_returns, horizon=horizon)
                    if strategy_returns
                    else None
                ),
                status=status,
            )
        )

    valid_trials = [trial for trial in trials if trial.status != "insufficient_data"]
    passed_trials = [trial for trial in valid_trials if trial.status == "passed"]
    factor_threshold = max(2, math.ceil(max(1, len(valid_trials)) / 2))
    stable_factor_ids = sorted(
        factor_id
        for factor_id, frequency in selected_frequency.items()
        if frequency >= factor_threshold
    )[:8]
    excess_totals = [
        float(trial.excess_return)
        for trial in valid_trials
        if trial.excess_return is not None
    ]
    pooled_mean, ci_low, ci_high = _mean_confidence_interval(pooled_excess)
    required_passes = math.ceil(len(valid_trials) * 0.75) if valid_trials else 0
    if len(valid_trials) < 3:
        retention_status = "insufficient_evidence"
        retention_reason = "有效独立窗口少于三个，不能把探索性因子升级为保留因子。"
    elif (
        len(passed_trials) >= required_passes
        and excess_totals
        and median(excess_totals) > 0
        and ci_low is not None
        and ci_low > 0
        and stable_factor_ids
    ):
        retention_status = "provisional_retained"
        retention_reason = (
            "至少四分之三的独立窗口通过，窗口超额收益中位数为正，"
            "且逐期超额收益90%置信区间下界为正；仅进入未来验证，不直接用于交易。"
        )
    else:
        retention_status = "rejected"
        retention_reason = (
            "重复试验未同时满足通过率、正超额收益、置信区间下界和因子稳定性门槛。"
        )

    anchor_date, prospective_ids, prospective_position = _prospective_factor_signal(
        target_rows=target_rows,
        candidates=candidates,
        stable_factor_ids=stable_factor_ids,
    )
    future_status: Literal["not_registered", "pending"] = "not_registered"
    if retention_status == "provisional_retained" and prospective_position != "unavailable":
        future_status = "pending"
    return ModelFactorReplication(
        protocol_version="factor_replication_v1_nonoverlap_fdr",
        trials=trials,
        total_trials=len(trials),
        valid_trials=len(valid_trials),
        passed_trials=len(passed_trials),
        pass_rate=(len(passed_trials) / len(valid_trials) if valid_trials else None),
        median_excess_return=(median(excess_totals) if excess_totals else None),
        pooled_mean_excess_return=pooled_mean,
        pooled_excess_ci_low=ci_low,
        pooled_excess_ci_high=ci_high,
        stable_factor_ids=stable_factor_ids,
        retention_status=retention_status,
        retention_reason=retention_reason,
        prospective_anchor_date=anchor_date.isoformat() if anchor_date else None,
        prospective_factor_ids=prospective_ids,
        prospective_position=prospective_position,
        future_validation_status=future_status,
        leakage_guard=(
            "四个测试窗口互不重叠；每轮在窗口开始前重新执行训练期相关检验和"
            "Benjamini-Hochberg FDR 10%筛选，训练收益终点必须早于测试起点；"
            "最终未来信号冻结后不得用未来结果回写参数。"
        ),
    )


def _select_trial_candidates(
    candidates: list[dict[str, Any]],
    *,
    cutoff: date,
) -> list[dict[str, Any]]:
    evaluated: list[dict[str, Any]] = []
    for candidate in candidates:
        train = [row for row in candidate.get("paired", []) if row[2] < cutoff]
        correlation = _pearson([row[1] for row in train], [row[3] for row in train])
        if correlation is None or len(train) < 18:
            continue
        evaluated.append(
            {
                **candidate,
                "trial_train": train,
                "trial_correlation": correlation,
                "training_p_value": _correlation_p_value(correlation, len(train)),
            }
        )
    _apply_bh_qvalues(evaluated)
    eligible = [item for item in evaluated if item.get("adjusted_q_value", 1.0) <= 0.10]
    return sorted(
        eligible,
        key=lambda item: abs(float(item["trial_correlation"])),
        reverse=True,
    )[:2]


def _evaluate_trial_block(
    *,
    selected: list[dict[str, Any]],
    block: list[tuple[date, float, date]],
    transaction_cost_bps: float,
) -> dict[str, Any]:
    if not selected:
        return {
            "strategy_returns": [],
            "baseline_returns": [],
            "excess_returns": [],
            "hits": 0,
        }
    stats: list[tuple[float, float, float]] = []
    feature_maps: list[dict[date, float]] = []
    for item in selected:
        train_values = [row[1] for row in item["trial_train"]]
        stats.append(
            (
                fmean(train_values),
                pstdev(train_values) if len(train_values) > 1 else 0.0,
                1.0 if item["trial_correlation"] >= 0 else -1.0,
            )
        )
        feature_maps.append({row[0]: row[1] for row in item.get("paired", [])})
    strategy_returns: list[float] = []
    baseline_returns: list[float] = []
    excess_returns: list[float] = []
    last_position = 0
    hits = 0
    for observed_on, forward_return, _ in block:
        values = [feature_map.get(observed_on) for feature_map in feature_maps]
        if any(value is None for value in values):
            continue
        score = sum(
            direction * (float(value) - mean) / deviation
            for value, (mean, deviation, direction) in zip(values, stats, strict=True)
            if value is not None and deviation > 1e-12
        )
        position = 1 if score >= 0 else -1
        cost = transaction_cost_bps / 10_000 if position != last_position else 0.0
        strategy_return = position * forward_return - cost
        strategy_returns.append(strategy_return)
        baseline_returns.append(forward_return)
        excess_returns.append(strategy_return - forward_return)
        hits += int(position * forward_return > 0)
        last_position = position
    return {
        "strategy_returns": strategy_returns,
        "baseline_returns": baseline_returns,
        "excess_returns": excess_returns,
        "hits": hits,
    }


def _market_factor_id(candidate: dict[str, Any]) -> str:
    return f"market:{candidate['series'].series_id}:change5"


def _prospective_factor_signal(
    *,
    target_rows: list[tuple[date, float]],
    candidates: list[dict[str, Any]],
    stable_factor_ids: list[str],
) -> tuple[date | None, list[str], Literal["long", "short", "unavailable"]]:
    if not target_rows or not stable_factor_ids:
        return None, [], "unavailable"
    anchor_date = target_rows[-1][0]
    selected = [
        item
        for item in _select_trial_candidates(candidates, cutoff=anchor_date)
        if _market_factor_id(item) in stable_factor_ids
    ]
    if not selected:
        return anchor_date, [], "unavailable"
    score = 0.0
    retained_ids: list[str] = []
    for item in selected:
        train_values = [row[1] for row in item["trial_train"]]
        deviation = pstdev(train_values) if len(train_values) > 1 else 0.0
        change_rows = item.get("changes", [])
        change_dates = [row[0] for row in change_rows]
        position = bisect_left(change_dates, anchor_date) - 1
        if deviation <= 1e-12 or position < 0:
            continue
        latest_value = float(change_rows[position][1])
        direction = 1.0 if item["trial_correlation"] >= 0 else -1.0
        score += direction * (latest_value - fmean(train_values)) / deviation
        retained_ids.append(_market_factor_id(item))
    if not retained_ids:
        return anchor_date, [], "unavailable"
    return anchor_date, retained_ids, "long" if score >= 0 else "short"


def _mean_confidence_interval(
    values: list[float],
) -> tuple[float | None, float | None, float | None]:
    if not values:
        return None, None, None
    average = fmean(values)
    if len(values) < 3:
        return average, None, None
    standard_error = pstdev(values) / math.sqrt(len(values))
    margin = 1.645 * standard_error
    return average, average - margin, average + margin


def _load_series(session: Session, series_id: str) -> list[tuple[date, float]]:
    rows = session.execute(
        select(MarketObservation.observed_on, MarketObservation.value)
        .where(MarketObservation.series_id == series_id)
        .order_by(MarketObservation.observed_on)
    )
    return [(observed_on, float(value)) for observed_on, value in rows]


def _target_samples(
    rows: list[tuple[date, float]],
    *,
    horizon: int,
) -> list[tuple[date, float, date]]:
    samples: list[tuple[date, float, date]] = []
    for index in range(0, max(0, len(rows) - horizon), horizon):
        observed_on, value = rows[index]
        future_on, future_value = rows[index + horizon]
        if abs(value) <= 1e-12:
            continue
        samples.append((observed_on, future_value / value - 1.0, future_on))
    return samples


def _aligned_asset_forward_returns(
    rows: list[tuple[date, float]],
    samples: list[tuple[date, float, date]],
    *,
    max_stale_days: int = 10,
    listed_from: date | None = None,
    listed_until: date | None = None,
    delisting_return: float | None = None,
) -> dict[date, float]:
    dates = [row[0] for row in rows]
    aligned: dict[date, float] = {}
    for observed_on, _, outcome_on in samples:
        if listed_from is not None and observed_on < listed_from:
            continue
        if listed_until is not None and observed_on > listed_until:
            continue
        crosses_delisting = listed_until is not None and observed_on <= listed_until < outcome_on
        if crosses_delisting and delisting_return is None:
            continue
        entry_index = bisect_right(dates, observed_on) - 1
        effective_outcome = listed_until if crosses_delisting else outcome_on
        exit_index = bisect_right(dates, effective_outcome) - 1
        if entry_index < 0 or exit_index <= entry_index:
            continue
        entry_on, entry_value = rows[entry_index]
        exit_on, exit_value = rows[exit_index]
        if (
            (observed_on - entry_on).days > max_stale_days
            or (effective_outcome - exit_on).days > max_stale_days
            or abs(entry_value) <= 1e-12
        ):
            continue
        forward_return = exit_value / entry_value - 1.0
        if crosses_delisting and delisting_return is not None:
            forward_return = (1.0 + forward_return) * (1.0 + delisting_return) - 1.0
        if math.isfinite(forward_return):
            aligned[observed_on] = forward_return
    return aligned


def _series_changes(rows: list[tuple[date, float]], lookback: int = 5) -> list[tuple[date, float]]:
    changes: list[tuple[date, float]] = []
    for index in range(lookback, len(rows)):
        observed_on, value = rows[index]
        previous = rows[index - lookback][1]
        change = value - previous if abs(previous) <= 1e-9 else value / abs(previous) - 1.0
        if math.isfinite(change):
            changes.append((observed_on, change))
    return changes


def _pair_feature(
    samples: list[tuple[date, float, date]],
    changes: list[tuple[date, float]],
) -> list[tuple[date, float, date, float]]:
    dates = [row[0] for row in changes]
    paired: list[tuple[date, float, date, float]] = []
    for observed_on, forward_return, outcome_on in samples:
        position = bisect_left(dates, observed_on) - 1
        if position < 0:
            continue
        paired.append((observed_on, changes[position][1], outcome_on, forward_return))
    return paired


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    left_mean = fmean(left)
    right_mean = fmean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right, strict=True))
    denominator = math.sqrt(
        sum((x - left_mean) ** 2 for x in left) * sum((y - right_mean) ** 2 for y in right)
    )
    return numerator / denominator if denominator > 1e-12 else None


def _correlation_p_value(correlation: float, observations: int) -> float:
    """Two-sided Fisher-z normal approximation for a training correlation."""
    if observations <= 3:
        return 1.0
    bounded = max(-0.999999, min(0.999999, correlation))
    z_score = math.atanh(bounded) * math.sqrt(observations - 3)
    return max(0.0, min(1.0, math.erfc(abs(z_score) / math.sqrt(2.0))))


def _apply_bh_qvalues(candidates: list[dict[str, Any]]) -> None:
    """Attach monotone Benjamini-Hochberg q-values to candidate dictionaries."""
    ranked = sorted(
        enumerate(candidates),
        key=lambda row: float(row[1].get("training_p_value", 1.0)),
    )
    total = len(ranked)
    running_min = 1.0
    qvalues: dict[int, float] = {}
    for reverse_index in range(total - 1, -1, -1):
        original_index, candidate = ranked[reverse_index]
        rank = reverse_index + 1
        raw = float(candidate.get("training_p_value", 1.0)) * total / rank
        running_min = min(running_min, raw)
        qvalues[original_index] = max(0.0, min(1.0, running_min))
    for index, candidate in enumerate(candidates):
        candidate["adjusted_q_value"] = qvalues.get(index, 1.0)


def _predictor_relevance(series: MarketSeries, question_text: str) -> tuple[int, str]:
    text = question_text.casefold()
    tokens = set(TOKEN_PATTERN.findall(text))
    name_tokens = set(TOKEN_PATTERN.findall(series.name.casefold()))
    structural = {
        "DGS2": 12,
        "DGS10": 11,
        "T10Y2Y": 10,
        "VIXCLS": 10,
        "NFCI": 10,
        "DTWEXBGS": 9,
        "DCOILWTICO": 9,
        "BAMLH0A0HYM2": 9,
        "INDPRO": 8,
        "CPIAUCSL": 7,
    }.get(series.series_id, 0)
    return structural + len(tokens & name_tokens) * 4, series.series_id


def _compound(returns: list[float]) -> float:
    wealth = 1.0
    for value in returns:
        wealth *= max(0.0, 1.0 + value)
    return wealth - 1.0


def _turnover_cost(
    current: set[str],
    previous: set[str] | None,
    transaction_cost_bps: float,
) -> float:
    if not current:
        return 0.0
    turnover = 1.0 if previous is None else 1.0 - len(current & previous) / len(current)
    return max(0.0, turnover) * transaction_cost_bps / 10_000


def _max_drawdown(returns: list[float]) -> float:
    wealth = 1.0
    peak = 1.0
    worst = 0.0
    for value in returns:
        wealth *= max(0.0, 1.0 + value)
        peak = max(peak, wealth)
        worst = min(worst, wealth / peak - 1.0)
    return worst


def _sharpe_like(returns: list[float], *, horizon: int) -> float | None:
    if len(returns) < 3:
        return None
    deviation = pstdev(returns)
    if deviation <= 1e-12:
        return None
    return fmean(returns) / deviation * math.sqrt(252 / horizon)


def _evidence_refs(evidence: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for value in evidence.values():
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, dict) and isinstance(item.get("evidence_id"), str):
                refs.add(item["evidence_id"])
    return refs


def _deduplicate_links(links: list[ModelNonlinearFactorLink]) -> list[ModelNonlinearFactorLink]:
    retained: list[ModelNonlinearFactorLink] = []
    seen: set[str] = set()
    for link in links:
        if link.link_id in seen:
            continue
        retained.append(link)
        seen.add(link.link_id)
    return retained


def _archive_factor_research(
    research: ModelFactorResearch,
    *,
    settings: Settings,
    inquiry_id: int,
    question: str,
) -> None:
    payload = {
        "schema_version": 1,
        "inquiry_id": inquiry_id,
        "question": question,
        "factor_research": research.model_dump(mode="json"),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    compressed = gzip.compress(encoded, compresslevel=6, mtime=0)
    digest = hashlib.sha256(encoded).hexdigest()
    relative_path = (
        f"model-outputs/factor-research/{research.generated_at:%Y/%m/%d}/"
        f"{inquiry_id}-{digest[:16]}.json.gz"
    )
    try:
        archive = ColdArchive(
            settings.cold_data_root,
            min_free_bytes=settings.cold_archive_min_free_gb * 1024**3,
            max_used_percent=settings.cold_archive_max_used_percent,
        )
        research.archive_path = archive.store_bytes(relative_path, compressed)
        research.archive_status = "stored"
    except (ArchiveCapacityError, OSError, ValueError):
        research.archive_status = "write_failed"
