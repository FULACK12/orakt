"""Auditable CAN SLIM scorecard built from retained point-in-time evidence."""

# ruff: noqa: RUF001

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import CompanyFinancialFact, MarketObservation

CriterionStatus = Literal["pass", "partial", "fail", "missing"]

_WEIGHTS = {"C": 20, "A": 15, "N": 15, "S": 15, "L": 15, "I": 10, "M": 10}


def build_canslim_scorecard(
    session: Session,
    *,
    ticker: str,
    as_of: date,
    technical: dict[str, Any] | None,
    product_evidence: list[dict[str, Any]],
    institutional_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply the seven factors without turning historical heuristics into a forecast."""
    quarterly = _quarterly_earnings(session, ticker=ticker, as_of=as_of)
    annual = _annual_earnings(session, ticker=ticker, as_of=as_of)
    market = _market_direction(session, as_of=as_of)
    criteria = [
        _current_earnings_criterion(quarterly),
        _annual_earnings_criterion(annual),
        _new_factor_criterion(product_evidence, technical=technical),
        _supply_demand_criterion(technical),
        _leader_criterion(technical, market=market),
        _institutional_criterion(institutional_evidence),
        _market_criterion(market),
    ]
    overall = round(
        sum(float(item["score"]) * _WEIGHTS[str(item["code"])] for item in criteria)
        / 100,
        2,
    )
    covered_weight = sum(
        _WEIGHTS[str(item["code"])] for item in criteria if item["status"] != "missing"
    )
    coverage = round(covered_weight, 2)
    decision = (
        "insufficient_evidence"
        if coverage < 70
        else "criteria_supported"
        if overall >= 75 and all(item["status"] != "fail" for item in criteria)
        else "mixed_or_not_confirmed"
    )
    return {
        "evidence_id": f"derived:canslim:{ticker}:{as_of.isoformat()}",
        "category": "derived_canslim_scorecard",
        "ticker": ticker,
        "as_of": as_of.isoformat(),
        "version": "canslim_audit_v1_point_in_time",
        "overall_score": overall,
        "coverage_score": coverage,
        "decision": decision,
        "criteria": criteria,
        "discipline": _trading_discipline(technical),
        "source": "Local point-in-time SEC filings, daily OHLCV, FRED S&P 500 and SEC 13F",
        "underlying_evidence_refs": list(
            dict.fromkeys(
                ref
                for item in criteria
                for ref in item.get("evidence_refs", [])
                if ref
            )
        )[:80],
        "limitations": [
            "CAN SLIM is a historical screening framework, not a guaranteed-return model.",
            (
                "The advertised 941% competition result in the reference image is not "
                "treated as validated evidence."
            ),
            (
                "A pass describes a threshold at the stated cutoff; it does not prove "
                "a profitable entry or future return."
            ),
            (
                "For A-shares, an exchange-filing EPS/ROE feed, institution-flow "
                "provenance and a point-in-time broad-China market proxy are still "
                "required before applying the same scorecard."
            ),
        ],
        "can_verify_claims": True,
    }


def _criterion(
    code: str,
    label_zh: str,
    label_en: str,
    *,
    status: CriterionStatus,
    score: float,
    observed: str,
    threshold: str,
    evidence_refs: list[str],
    limitations: list[str],
) -> dict[str, Any]:
    return {
        "code": code,
        "label_zh": label_zh,
        "label_en": label_en,
        "weight": _WEIGHTS[code],
        "status": status,
        "score": round(max(0.0, min(score, 1.0)) * 100, 1),
        "observed": observed,
        "threshold": threshold,
        "evidence_refs": evidence_refs,
        "limitations": limitations,
    }


def _current_earnings_criterion(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if snapshot is None:
        return _criterion(
            "C",
            "当季收益",
            "Current quarterly earnings",
            status="missing",
            score=0,
            observed="缺少可比的单季度摊薄 EPS",
            threshold="单季度摊薄 EPS 同比至少增长 20%",
            evidence_refs=[],
            limitations=["累计季度值不能与单季度值混用。"],
        )
    growth = snapshot.get("eps_yoy")
    if not isinstance(growth, (int, float)):
        status: CriterionStatus = "partial"
        score = 0.35
        observed = (
            f"最新单季度 EPS {snapshot['latest_eps']:.2f}；比较期为非正值，"
            "同比增长率不具备稳定含义"
        )
    else:
        status = "pass" if growth >= 0.20 else "fail"
        score = min(max(growth / 0.20, 0), 1)
        observed = f"单季度摊薄 EPS 同比 {growth:+.1%}"
    return _criterion(
        "C",
        "当季收益",
        "Current quarterly earnings",
        status=status,
        score=score,
        observed=observed,
        threshold="单季度摊薄 EPS 同比至少增长 20%",
        evidence_refs=snapshot["evidence_refs"],
        limitations=["SEC EPS 采用公司财季，可能受一次性项目和回购影响。"],
    )


def _annual_earnings_criterion(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if snapshot is None:
        return _criterion(
            "A",
            "年度收益",
            "Annual earnings",
            status="missing",
            score=0,
            observed="缺少至少四个可比年度的摊薄 EPS 或 ROE",
            threshold="3 年 EPS 复合增长至少 25%，最新 ROE 至少 17%",
            evidence_refs=[],
            limitations=["负 EPS 基期不计算传统复合增长率。"],
        )
    cagr = snapshot.get("eps_cagr")
    roe = snapshot.get("roe")
    cagr_pass = isinstance(cagr, (int, float)) and cagr >= 0.25
    roe_pass = isinstance(roe, (int, float)) and roe >= 0.17
    status: CriterionStatus = "pass" if cagr_pass and roe_pass else "fail"
    score = (
        min(max(float(cagr or 0) / 0.25, 0), 1) * 0.65
        + min(max(float(roe or 0) / 0.17, 0), 1) * 0.35
    )
    return _criterion(
        "A",
        "年度收益",
        "Annual earnings",
        status=status,
        score=score,
        observed=(
            f"{snapshot['span_years']:.1f} 年摊薄 EPS 复合增长 "
            f"{cagr:+.1%}；最新年度 ROE {roe:.1%}"
        ),
        threshold="3 年 EPS 复合增长至少 25%，最新 ROE 至少 17%",
        evidence_refs=snapshot["evidence_refs"],
        limitations=["ROE 使用期末股东权益近似，未替代完整平均权益分析。"],
    )


def _new_factor_criterion(
    evidence: list[dict[str, Any]],
    *,
    technical: dict[str, Any] | None,
) -> dict[str, Any]:
    actual = [item for item in evidence if item.get("evidence_status") == "reported_actual"]
    plans = [
        item for item in evidence if item.get("evidence_status") == "forward_looking_plan"
    ]
    near_high = bool(
        technical
        and isinstance(technical.get("drawdown_from_52_week_high"), (int, float))
        and float(technical["drawdown_from_52_week_high"]) >= -0.15
    )
    refs = [str(item.get("evidence_id")) for item in [*actual, *plans] if item.get("evidence_id")]
    if not actual and not plans and not near_high:
        return _criterion(
            "N",
            "新因素",
            "New product, management or price high",
            status="missing",
            score=0,
            observed="没有经申报核验的新产品/经营证据，且价格不接近 52 周高点",
            threshold="经申报的新因素或接近新高；计划与已兑现结果必须分开",
            evidence_refs=[],
            limitations=["新闻中的新概念不能替代公司申报或已实现经营数据。"],
        )
    status: CriterionStatus = "pass" if actual and near_high else "partial"
    score = min(len(actual) / 4, 1) * 0.7 + int(bool(plans)) * 0.1 + int(near_high) * 0.2
    return _criterion(
        "N",
        "新因素",
        "New product, management or price high",
        status=status,
        score=score,
        observed=(
            f"{len(actual)} 条已报告产品经营证据，{len(plans)} 条前瞻计划；"
            f"价格{'接近' if near_high else '未接近'} 52 周高点"
        ),
        threshold="经申报的新因素或接近新高；计划与已兑现结果必须分开",
        evidence_refs=refs,
        limitations=["新因素的存在不等于它尚未被市场定价。"],
    )


def _supply_demand_criterion(technical: dict[str, Any] | None) -> dict[str, Any]:
    ratio = technical.get("volume_ratio_20") if technical else None
    direction = (
        (technical.get("volume_confirmation") or {}).get("latest_candle_direction")
        if technical
        else None
    )
    if not isinstance(ratio, (int, float)):
        return _criterion(
            "S",
            "供需关系",
            "Supply and demand",
            status="missing",
            score=0,
            observed="缺少完整成交量数据",
            threshold="向上交易日成交量至少为 20 日均量的 1.4 倍",
            evidence_refs=[],
            limitations=["成交量不能识别买方身份。"],
        )
    passed = ratio >= 1.4 and direction == "up"
    return _criterion(
        "S",
        "供需关系",
        "Supply and demand",
        status="pass" if passed else "fail",
        score=min(ratio / 1.4, 1) * (1 if direction == "up" else 0.55),
        observed=f"最新成交量/20 日均量 {ratio:.2f} 倍；K 线方向 {direction or '未知'}",
        threshold="向上交易日成交量至少为 20 日均量的 1.4 倍",
        evidence_refs=[str(technical.get("evidence_id"))] if technical else [],
        limitations=["单日放量不是机构吸筹或未来上涨的证明。"],
    )


def _leader_criterion(
    technical: dict[str, Any] | None,
    *,
    market: dict[str, Any] | None,
) -> dict[str, Any]:
    stock_return = technical.get("return_252d") if technical else None
    market_return = market.get("return_252d") if market else None
    drawdown = technical.get("drawdown_from_52_week_high") if technical else None
    if not all(
        isinstance(value, (int, float))
        for value in (stock_return, market_return, drawdown)
    ):
        return _criterion(
            "L",
            "领军股",
            "Leader or laggard",
            status="missing",
            score=0,
            observed="缺少股票或标普 500 的完整 252 日比较",
            threshold="252 日跑赢标普 500 且距 52 周高点不超过 15%",
            evidence_refs=[],
            limitations=["这不是 IBD 的专有 RS 排名。"],
        )
    excess = float(stock_return) - float(market_return)
    passed = excess > 0 and float(drawdown) >= -0.15
    return _criterion(
        "L",
        "领军股",
        "Leader or laggard",
        status="pass" if passed else "fail",
        score=(0.6 if excess > 0 else 0.2) + (0.4 if float(drawdown) >= -0.15 else 0),
        observed=(
            f"252 日收益 {float(stock_return):+.1%}，标普 500 {float(market_return):+.1%}，"
            f"相对超额 {excess:+.1%}；距 52 周高点 {float(drawdown):.1%}"
        ),
        threshold="252 日跑赢标普 500 且距 52 周高点不超过 15%",
        evidence_refs=[
            str(technical.get("evidence_id")),
            str(market.get("evidence_id")),
        ],
        limitations=["采用可审计的标普相对强度代理，不声称等同于专有 RS 百分位。"],
    )


def _institutional_criterion(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    comparable = [
        item for item in evidence if isinstance(item.get("reported_share_change"), (int, float))
    ]
    if not comparable:
        return _criterion(
            "I",
            "机构认同",
            "Institutional sponsorship",
            status="missing",
            score=0,
            observed="缺少可比季度的 13F 持仓变化",
            threshold="主要披露机构中增持者多于减持者",
            evidence_refs=[],
            limitations=["13F 滞后且不披露买入成本、空头和全部资产。"],
        )
    increased = sum(float(item["reported_share_change"]) > 0 for item in comparable)
    decreased = sum(float(item["reported_share_change"]) < 0 for item in comparable)
    share = increased / len(comparable)
    return _criterion(
        "I",
        "机构认同",
        "Institutional sponsorship",
        status="pass" if increased > decreased else "fail",
        score=share,
        observed=f"{len(comparable)} 家可比机构中 {increased} 家增持、{decreased} 家减持",
        threshold="主要披露机构中增持者多于减持者",
        evidence_refs=[str(item.get("evidence_id")) for item in comparable],
        limitations=["管理人汇总不等于具体主动基金决策，也不是实时资金流。"],
    )


def _market_criterion(market: dict[str, Any] | None) -> dict[str, Any]:
    if market is None:
        return _criterion(
            "M",
            "市场方向",
            "Market direction",
            status="missing",
            score=0,
            observed="缺少标普 500 趋势数据",
            threshold="标普 500 高于 50/200 日均线且 21 日收益为正",
            evidence_refs=[],
            limitations=["单一指数不能代表所有市场风格。"],
        )
    passed = bool(market["above_sma_50"] and market["above_sma_200"] and market["return_21d"] > 0)
    score = (
        int(market["above_sma_50"])
        + int(market["above_sma_200"])
        + int(market["return_21d"] > 0)
    ) / 3
    return _criterion(
        "M",
        "市场方向",
        "Market direction",
        status="pass" if passed else "fail",
        score=score,
        observed=(
            f"标普 500 处于 50 日均线{'上方' if market['above_sma_50'] else '下方'}、"
            f"200 日均线{'上方' if market['above_sma_200'] else '下方'}；"
            f"21 日收益 {market['return_21d']:+.1%}"
        ),
        threshold="标普 500 高于 50/200 日均线且 21 日收益为正",
        evidence_refs=[str(market["evidence_id"])],
        limitations=["趋势过滤器不是择时保证，快速反转仍可能发生。"],
    )


def _quarterly_earnings(
    session: Session,
    *,
    ticker: str,
    as_of: date,
) -> dict[str, Any] | None:
    facts = list(
        session.scalars(
            select(CompanyFinancialFact)
            .where(
                CompanyFinancialFact.ticker == ticker,
                CompanyFinancialFact.concept == "EarningsPerShareDiluted",
                CompanyFinancialFact.form.in_(("10-Q", "10-Q/A")),
                CompanyFinancialFact.filed_at <= as_of,
                CompanyFinancialFact.period_end <= as_of,
                CompanyFinancialFact.period_start.is_not(None),
            )
            .order_by(desc(CompanyFinancialFact.period_end), desc(CompanyFinancialFact.filed_at))
            .limit(80)
        )
    )
    by_end: dict[date, CompanyFinancialFact] = {}
    for fact in facts:
        if fact.period_start is None or not 60 <= (fact.period_end - fact.period_start).days <= 120:
            continue
        by_end.setdefault(fact.period_end, fact)
    if not by_end:
        return None
    latest = by_end[max(by_end)]
    prior_candidates = [
        fact for end, fact in by_end.items() if 340 <= (latest.period_end - end).days <= 390
    ]
    if not prior_candidates:
        return None
    prior = min(
        prior_candidates,
        key=lambda fact: abs((latest.period_end - fact.period_end).days - 365),
    )
    growth = latest.value / prior.value - 1 if prior.value > 0 else None
    return {
        "latest_eps": latest.value,
        "prior_eps": prior.value,
        "eps_yoy": growth,
        "evidence_refs": [_fact_ref(latest), _fact_ref(prior)],
    }


def _annual_earnings(
    session: Session,
    *,
    ticker: str,
    as_of: date,
) -> dict[str, Any] | None:
    concepts = {"EarningsPerShareDiluted", "NetIncomeLoss", "StockholdersEquity"}
    facts = list(
        session.scalars(
            select(CompanyFinancialFact)
            .where(
                CompanyFinancialFact.ticker == ticker,
                CompanyFinancialFact.concept.in_(concepts),
                CompanyFinancialFact.form.in_(("10-K", "10-K/A")),
                CompanyFinancialFact.filed_at <= as_of,
                CompanyFinancialFact.period_end <= as_of,
            )
            .order_by(desc(CompanyFinancialFact.period_end), desc(CompanyFinancialFact.filed_at))
            .limit(500)
        )
    )
    annual_eps: dict[date, CompanyFinancialFact] = {}
    annual_net: dict[date, CompanyFinancialFact] = {}
    equity: dict[date, CompanyFinancialFact] = {}
    for fact in facts:
        if fact.concept == "StockholdersEquity":
            equity.setdefault(fact.period_end, fact)
            continue
        if (
            fact.period_start is None
            or not 300 <= (fact.period_end - fact.period_start).days <= 400
        ):
            continue
        target = annual_eps if fact.concept == "EarningsPerShareDiluted" else annual_net
        target.setdefault(fact.period_end, fact)
    ends = sorted(annual_eps, reverse=True)
    if len(ends) < 4:
        return None
    latest = annual_eps[ends[0]]
    earliest = annual_eps[ends[3]]
    span = (latest.period_end - earliest.period_end).days / 365.25
    if latest.value <= 0 or earliest.value <= 0 or span < 2.5:
        return None
    cagr = (latest.value / earliest.value) ** (1 / span) - 1
    net = annual_net.get(latest.period_end)
    equity_fact = equity.get(latest.period_end)
    if net is None or equity_fact is None or equity_fact.value <= 0:
        return None
    return {
        "eps_cagr": cagr,
        "span_years": span,
        "roe": net.value / equity_fact.value,
        "evidence_refs": [
            _fact_ref(latest),
            _fact_ref(earliest),
            _fact_ref(net),
            _fact_ref(equity_fact),
        ],
    }


def _market_direction(session: Session, *, as_of: date) -> dict[str, Any] | None:
    rows = list(
        session.execute(
            select(MarketObservation.observed_on, MarketObservation.value)
            .where(
                MarketObservation.series_id == "SP500",
                MarketObservation.observed_on <= as_of,
            )
            .order_by(desc(MarketObservation.observed_on))
            .limit(260)
        )
    )
    rows.reverse()
    values = [float(value) for _, value in rows]
    if len(values) < 201 or values[-201] <= 0 or values[-22] <= 0:
        return None
    current = values[-1]
    return {
        "evidence_id": f"market:SP500:{rows[-1][0].isoformat()}",
        "observed_on": rows[-1][0].isoformat(),
        "value": current,
        "sma_50": sum(values[-50:]) / 50,
        "sma_200": sum(values[-200:]) / 200,
        "above_sma_50": current > sum(values[-50:]) / 50,
        "above_sma_200": current > sum(values[-200:]) / 200,
        "return_21d": current / values[-22] - 1,
        "return_252d": current / values[-253] - 1 if len(values) >= 253 else None,
    }


def _trading_discipline(technical: dict[str, Any] | None) -> dict[str, Any]:
    high = technical.get("high_52_week_close") if technical else None
    current = technical.get("adjusted_close") if technical else None
    if not isinstance(high, (int, float)) or not isinstance(current, (int, float)):
        return {
            "status": "unavailable",
            "reason": "Complete price history is required before calculating a pivot proxy.",
        }
    upper = float(high) * 1.05
    position = (
        "below_pivot"
        if current < high
        else "buy_zone_proxy"
        if current <= upper
        else "extended"
    )
    return {
        "status": "scenario_only",
        "pivot_proxy": high,
        "traditional_buy_zone_proxy": [high, upper],
        "current_price": current,
        "current_position": position,
        "stop_loss_rule": (
            "7%–8% below a user-selected entry; scenario discipline, not an instruction."
        ),
        "profit_rule": (
            "20%–25% above entry; the three-week rapid-gain exception requires a "
            "separate historical test."
        ),
        "limitations": [
            (
                "The 52-week closing high is a mechanical proxy, not a manually "
                "validated chart base or pivot."
            ),
            "No buy, stop or take-profit order is generated automatically.",
        ],
    }


def _fact_ref(fact: CompanyFinancialFact) -> str:
    return (
        f"sec:{fact.ticker}:{fact.concept}:{fact.period_end.isoformat()}:"
        f"{fact.accession_number}"
    )
