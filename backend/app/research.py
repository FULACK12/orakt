"""Autonomous local research with deterministic audit and optional OpenAI review."""

# ruff: noqa: RUF001

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal, cast

import httpx
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import desc, extract, func, or_, select
from sqlalchemy.orm import Session

from app.conflicts.service import current_conflict_hotspots
from app.core.config import Settings, get_settings
from app.cycle_models import build_cycle_model_suite
from app.data_coverage import build_coverage_report
from app.db.models import (
    CompanyFinancialFact,
    CompanyProfile,
    CountryProfile,
    Document,
    EconomicIndicator,
    EconomicObservation,
    EnergyObservation,
    EnergySeries,
    Event,
    LogicChainHypothesis,
    MarketObservation,
    MarketSeries,
    ResearchBatchItem,
    ResearchInquiry,
    ResearchReviewSignal,
    Source,
)
from app.equity_research import (
    COMPANY_ALIASES,
    COMPANY_RESEARCH_PROFILES,
    build_equity_research_pack,
)
from app.evidence_completion import complete_research_evidence
from app.evidence_quality import (
    can_verify_claims,
    document_evidence_tier,
    headline_only_evidence_ids,
)
from app.extractors.llm import UNSUPPORTED_GRAMMAR_SCHEMA_KEYS
from app.factor_mining import build_factor_research
from app.forecast_validation import build_forecast_validation_cases
from app.logic_memory import qualified_logic_memories
from app.market_history import build_cycle_snapshot
from app.research_event_table import (
    build_research_event_table,
    select_preferred_research_period,
)
from app.research_evidence import (
    build_news_evidence_sequences,
    build_news_forecast_anchors,
    enrich_research_evidence,
    evidence_subject_key,
)
from app.schemas.research import (
    ChatGPTResearchReview,
    ModelAcademicResearchReport,
    ModelChatGPTResearchReview,
    ModelEquityDecisionFramework,
    ModelEquityResearchDimension,
    ModelForecastValidationBatch,
    ModelNewsForecast,
    ModelResearchHypothesis,
    ModelResearchResult,
    ModelResearchScope,
    ModelResearchStep,
    ResearchInquirySummaryView,
    ResearchInquiryView,
    ResearchReportChangeAlert,
    ResearchReportChangeAlertListResponse,
    ResearchReportChangeSummary,
    ResearchReportComparisonResponse,
    ResearchReportComparisonVersion,
    ResearchReportEvidenceChange,
    ResearchReviewSignalView,
)
from app.storage.archive import ColdArchive
from app.storage.document_tiering import document_body_for_research
from app.task_controls import TaskCancellationRequested

LOCAL_REPORT_AUDIT_VERSION = "local_report_audit_v12_a_share_confidence_gate"
RESEARCH_COVERAGE_CACHE_TTL = timedelta(minutes=30)
_RESEARCH_COVERAGE_CACHE: dict[str, Any] = {}
REPORT_CHANGE_ALERT_CACHE_TTL = timedelta(minutes=2)
_REPORT_CHANGE_ALERT_CACHE: dict[
    tuple[int, int],
    tuple[datetime, ResearchReportChangeAlertListResponse],
] = {}

RESEARCH_TERM_GLOSSARY: dict[str, dict[str, str]] = {
    "DGS2": {
        "name_zh": "美国2年期国债收益率",
        "name_en": "2-Year U.S. Treasury Yield",
        "plain_zh": "更敏感地反映市场对未来几年利率的预期。上升常会压低高估值资产的估值空间，但不能单独证明股价会跌。",
        "plain_en": "A rate-expectations gauge. A rise can pressure richly valued assets, but does not by itself prove that a stock will fall.",
    },
    "DGS10": {
        "name_zh": "美国10年期国债收益率",
        "name_en": "10-Year U.S. Treasury Yield",
        "plain_zh": "常被当作长期无风险利率和估值折现率的参考。它与股价同日变化只是相关性，不自动构成因果。",
        "plain_en": "A common long-term risk-free-rate and valuation discount-rate reference; same-day co-movement is not automatic causality.",
    },
    "NFCI": {
        "name_zh": "芝加哥联储全国金融状况指数",
        "name_en": "Chicago Fed National Financial Conditions Index",
        "plain_zh": "综合信用、杠杆和风险状况；高于0通常表示比历史平均更紧，低于0表示更宽松。它描述金融环境，不直接等于股票资金流。",
        "plain_en": "A composite of credit, leverage and risk. Above zero is generally tighter than average and below zero looser; it is not a direct stock-flow measure.",
    },
    "M2SL": {
        "name_zh": "美国M2货币供应量",
        "name_en": "U.S. M2 Money Stock",
        "plain_zh": "衡量现金、活期存款及部分高流动性存款的总量。增长不代表资金一定会流入某只股票。",
        "plain_en": "A broad liquid-money measure. Growth does not mean that money must flow into a particular stock.",
    },
    "DTWEXBGS": {
        "name_zh": "广义贸易加权美元指数",
        "name_en": "Broad Trade-Weighted U.S. Dollar Index",
        "plain_zh": "衡量美元相对主要贸易伙伴货币的强弱，可影响海外收入折算、商品价格和全球融资条件。",
        "plain_en": "Tracks the dollar against major trading partners and can affect translated foreign revenue, commodities and global funding conditions.",
    },
    "VIXCLS": {
        "name_zh": "VIX波动率指数",
        "name_en": "CBOE Volatility Index",
        "plain_zh": "反映期权市场对未来约30天标普500波动的定价，常被称为恐慌指数；它不是涨跌方向预测。",
        "plain_en": "Option-implied S&P 500 volatility over roughly 30 days; it is not a directional forecast.",
    },
    "13F": {
        "name_zh": "SEC 13F机构持仓申报",
        "name_en": "SEC Form 13F Institutional Holdings",
        "plain_zh": "大型机构按季度披露的历史持仓，通常有最多45天延迟，不能当作实时买卖或机构成本价。",
        "plain_en": "Quarterly institutional holdings disclosed with a delay of up to 45 days; not real-time trades or cost basis.",
    },
    "FORM4": {
        "name_zh": "SEC Form 4内部人交易",
        "name_en": "SEC Form 4 Insider Transactions",
        "plain_zh": "公司内部人申报的交易记录；要区分主动买卖、薪酬授予、期权行权和预设交易计划。",
        "plain_en": "Reported insider transactions; open-market trades, grants, exercises and preset plans must be distinguished.",
    },
    "TTM": {
        "name_zh": "过去12个月（TTM）",
        "name_en": "Trailing Twelve Months",
        "plain_zh": "把最近四个季度合并成滚动年度，便于看最新经营状态，但不等于下一年的预测。",
        "plain_en": "A rolling sum of the latest four quarters; useful for current operating context, not a next-year forecast.",
    },
    "SMA_MACD_RSI": {
        "name_zh": "SMA / MACD / RSI技术指标",
        "name_en": "SMA / MACD / RSI Technical Indicators",
        "plain_zh": "分别描述均价趋势、动量变化和近期涨跌强弱。它们来自历史价格，不识别机构身份，也不能单独给出可靠买点。",
        "plain_en": "They summarize trend, momentum and recent price strength. They use historical prices and cannot identify institutions or provide a reliable entry point alone.",
    },
}

LOCAL_RESEARCH_PROMPT = """\
You are the local research agent for a geospatial news intelligence system.
Return JSON only and match the supplied schema exactly.
If mode is autonomous, choose one consequential, falsifiable financial or
economic question grounded in the supplied evidence. Prioritize monetary-policy
transmission, inflation and growth cycles, debt/credit/liquidity, currencies,
earnings and valuation, commodities, industrial capacity, trade or supply-chain
risk. State a measurable outcome and a decision-relevant time horizon. Avoid
generic questions that cannot be tested with market or economic observations.
The supplied required_autonomous_focus is mandatory for that run.
For autonomous runs, all causal claims must stay inside the supplied
episode_window. Historical anchors and historical_context_refs are comparison
baselines only; do not describe the full retained history as one event period.
Verified_logic_memory contains prior human-approved mechanism analogies. It may
guide the shape of a chain, but it is not evidence for the current episode and
must never be cited instead of current dated evidence.
Do not repeat any supplied prior_research_questions. Before treating a market
move as consequential, compare it with a longer baseline or explicitly mark
historical significance as missing evidence; do not amplify a trivial change.
If mode is user_question, preserve the user's meaning.
If equity_research_context is present, this is a public-equity research task.
If equity_research_context.market_region is china, the retained pack is limited
to BaoStock market/factor snapshots and selected substantive news. Do not call
it SEC evidence, do not treat the snapshot date as the original filing date,
and do not claim that exchange announcements, contracts, shareholder flows or
supply-chain edges are present when required_missing_evidence lists them.
Return all five equity_dimensions exactly once: fundamentals_valuation,
technicals_positioning, macro_liquidity, supply_chain_geopolitics, and
technology_competition. Separate facts from calculations and hypotheses.
For fundamentals, examine products, competitors, contracts/filings, revenue,
earnings, margins, R&D, sales and shareholder changes when evidence exists.
Use derived_company_financial_trend to distinguish point-in-time filings from
later information and compare revenue, margins, inventory, capex and the free-
cash-flow proxy across fiscal years. Do not extrapolate a cyclical rebound.
For technicals, use the supplied SMA/RSI/MACD/KDJ context, valuation and market
capitalization, but never infer block trades, institutional cost basis, or
active/passive fund flows without volume/trade or SEC 13F evidence. For macro,
test rates, yields, FX and liquidity transmission step by step; national debt
or correlation alone cannot prove that Japanese borrowing funded the stock.
Treat derived_macro_sensitivity correlations and betas as descriptive exposure
checks only, never as proof of a funding-flow or policy transmission mechanism.
For supply chains, distinguish reviewed search targets from verified sourcing.
Company_news_document items marked can_verify_claims may support only the facts
stated in their excerpts; they do not prove an entire supply chain.
For technology, examine substitutes, process-node position and switching risk.
Any price target, including a user-supplied target, must state its implied
market capitalization and earnings/revenue/cash-flow assumptions. If inputs are
missing, mark the signal unknown and request the exact missing evidence.
The equity_decision_framework must give conditional entry and invalidation
conditions, never a guaranteed forecast or personalized buy/sell instruction.
For broad questions such as whether technology stocks may continue rising:
identify representative companies, their businesses and products, material and
physical inputs, electricity and infrastructure needs, policy dependencies,
and relevant conflict/disaster locations. Return one primary hypothesis and at
most one materially distinct alternative hypothesis.
Every hypothesis must have 3-8 ordered steps. Mark each step verified,
partially_supported, evidence_missing, or hypothesis. Cite only evidence_id
values present in the supplied evidence. A model inference is not evidence.
Evidence marked headline_only is a discovery lead: it may support a hypothesis
or a search request, but it may not be marked verified or partially_supported
without an independent substantive or structured source.
bridge_evidence_completion is produced by a deterministic resolver. Treat its
candidate_data_found status as data availability only, not proof that one node
caused the next. Reject candidates whose quality.can_verify_claims is false,
and cite only the evidence_refs returned for candidates that passed the gate.
Do not reject a financially distant pair merely because the relationship may
be nonlinear. Treat it as nonlinear_exploratory only when a threshold, regime,
interaction or common state could connect the endpoints. Name the bridge
variables, then decompose the idea into adjacent linear transmission segments
that can each be verified or falsified (for example funding cost, inventory,
procurement, freight, FX, trade volume and then commodity price). A nonlinear
label is not evidence: if bridge data are absent, mark those segments
evidence_missing and keep confidence low.
Use priority_evidence first. Cite the supplied planned_question_evidence_refs
for the premise and measured outcome when they support those exact steps. The
evidence_retrieval log shows what the local search actually checked. If a
second gap_search pass exists, reassess every earlier evidence gap against the
new records instead of repeating the draft unchanged.
For a planned autonomous episode, the summary, premise and outcome must name
the selected trigger and outcome subjects and stay inside episode_window. Do
not substitute unrelated recent companies, sectors or current events. At least
two steps must cite retained planned or derived window evidence when those
records exist; otherwise explicitly state that only the measured co-movement
is verified and the causal mechanism remains unsupported.
Every hypothesis must be materially different; do not repeat the same premise,
outcome or mechanism with superficial wording changes.
Also propose exactly four factor_candidates drawn from the retained news, market,
economic, company, supply-chain and geopolitical evidence. Each candidate must
state a transformation, lag, direction or regime dependence, falsifiable
hypothesis and exact evidence refs. These are hypotheses, not validated alpha.
Do not invent profitability metrics. The deterministic factor engine will
construct nonlinear interactions and chronological out-of-sample tests after
the local draft. Keep factor_research null; it is system-generated.
Write paper_report as a professional research paper: title, abstract,
methodology, ordered evidence chain, findings, alternative explanations,
limitations, conclusion and exact retained evidence references. The report must
explain why each link is plausible and distinguish observation from inference.
For every supplied news_forecast_anchor, write one falsifiable news_forecast.
Treat its published_at as a hard information cutoff: cite the anchor and only
evidence dated at or before it, propose a 1-365 day horizon, an ordered
mechanism chain, measurable expected outcome and explicit falsification
conditions. Do not call it a fact or a trading instruction. Initial forecast
status must be unresolved; later news and market data are evaluated by a
separate walk-forward validator.
Include counterarguments, stronger alternative explanations, and specific
evidence gaps. Never claim confirmed causality. Cap confidence at 0.75.
Use a concise output budget: one primary hypothesis is preferred, use 3-6 steps,
keep each prose field below 500 Chinese characters or 250 English words, keep
only the strongest six items in any list, and do not repeat the same narrative
across summary, equity dimensions and paper_report. Keep factor_research null.
Do not expose hidden chain-of-thought; return only concise, auditable steps.
"""

OPENAI_REVIEW_PROMPT = """\
Audit a local research model's result against its retained evidence snapshot.
Return JSON only and match the supplied schema exactly.
Check factual grounding, timing, each transmission mechanism, market
expectations, physical-resource assumptions, geospatial risks, alternative
explanations, and whether correlation was mislabeled as causation.
Explicitly check whether the direction/sign of every link is complete and
whether the cited evidence is sufficient for that exact link. A long-run
baseline is context only; judge causal timing only inside episode_window.
Use only supplied evidence_refs. Do not invent facts or sources. Recommend
accept, revise_and_accept, defer_for_evidence, or reject. Give concrete
revision text and explicitly list missing evidence. Do not expose hidden
chain-of-thought; provide concise audit findings only.
"""

LOCAL_REVISION_PROMPT = """\
You are the local revision agent in a two-model causal research workflow.
Return JSON only and match the supplied research-result schema exactly.
Rewrite the local draft after reading the OpenAI audit. Apply every finding:
repair incomplete causal direction, add supported intermediate links, remove
unsupported claims, and move unverified mechanisms or missing data into
evidence_gaps. Never invent evidence. Cite only retained evidence_id values.
Preserve or improve factor_candidates, but do not invent factor_research or
profitability figures; those are produced by the deterministic backtest.
Keep the question and bounded episode_window unchanged. Historical_context is
only a baseline or comparison and must not expand the causal time window.
Where evidence is insufficient, lower confidence and use evidence_missing or
hypothesis instead of pretending the reviewer supplied new facts. Preserve all
five equity lenses for an equity question. Do not expose hidden chain-of-
thought; return only the revised auditable result.
"""

LOCAL_FORECAST_VALIDATOR_PROMPT = """\
You are the local walk-forward forecast validator. Return JSON only and match
the supplied schema exactly. For each forecast, use only candidate_evidence
timestamped after its as_of cutoff. Decide whether the stated expected outcome
and mechanism are supported, partially supported, contradicted, still only
candidate evidence, or expired without enough evidence. Cite only supplied
candidate evidence IDs. A related headline is a lead, not verification. A
market move verifies the measured move but not the causal mechanism by itself.
Test falsification conditions and stronger alternative explanations. Do not
expose hidden chain-of-thought; return a concise audit summary.
"""

LOCAL_QUESTION_PLANNER_PROMPT = """\
You are the question-planning agent for a financial intelligence system.
Return JSON only and match the supplied schema exactly. Propose exactly one
consequential, falsifiable question in the mandatory focus area. Select one
specific episode from episode_candidates. Prefer the supplied
preferred_research_period: it is the earliest complete closed period not used
by recent research. Evidence completeness outranks recency. Never use the
current_open_period for an autonomous causal conclusion; it is monitoring-only.
The causal episode must be bounded
to 7-550 days, name a measurable outcome, cite at least one retained trigger
and one retained outcome/context observation inside that window, and report
the exact start and end dates. outcome_evidence_refs must contain a structured
market, economic, company-financial or energy observation, not only a headline.
The trigger and outcome must be financially or economically relevant; temporal
proximity alone is never enough. Historical anchors may be cited separately for
baseline comparison, but they must never expand the episode window or produce
a question such as "1854-2026". Never propose a question first and hope that
evidence can be found later. Do not assume that a small move is historically
significant. Do not repeat or paraphrase a prohibited prior question. Do not
lead with an off-focus indicator merely because it appears first.
Classify the proposed relationship as direct_linear, mediated_linear, or
nonlinear_exploratory. A distant pair is allowed as nonlinear exploration only
when bridge_hypotheses lists two to five measurable intermediate variables or
regime conditions. The full research stage will turn those bridges into linear
subchains and must not treat them as verified without evidence.
"""

AUTONOMOUS_FINANCIAL_FOCUS = (
    "monetary policy expectations, sovereign yields and asset valuation",
    "growth, inflation, labour conditions and the economic cycle",
    "credit spreads, corporate funding and investment",
    "currencies, reserves, external balances and cross-border liquidity",
    "earnings, margins, valuation and sector dispersion",
    "commodities, energy, agriculture and supply-chain transmission",
    "trade, industrial capacity, shipping and geopolitical risk",
)

FINANCIAL_EPISODE_TERMS = (
    "rate yield inflation employment unemployment growth recession credit debt "
    "liquidity currency dollar yen euro earnings revenue margin valuation stock "
    "equity bond commodity oil gas energy agriculture industrial production trade "
    "tariff export import supply chain shipping port freight semiconductor bank "
    "monetary fiscal treasury central bank market price index capacity investment "
    "利率 收益率 通胀 就业 失业 增长 衰退 信贷 债务 流动性 汇率 盈利 估值 股市 债券 "
    "大宗商品 石油 天然气 能源 农业 工业 贸易 关税 出口 进口 供应链 航运 港口 半导体"
)

CAUSAL_TRIGGER_TERMS = (
    "federal reserve fomc central bank interest rate yield inflation tariff sanction "
    "earnings revenue margin bankruptcy default credit debt currency dollar yen euro "
    "oil gas commodity crop drought flood earthquake wildfire conflict war strike "
    "supply chain shipping port freight semiconductor export control trade agreement "
    "央行 美联储 利率 收益率 通胀 关税 制裁 财报 收入 利润 破产 违约 信贷 债务 汇率 "
    "石油 天然气 大宗商品 农作物 干旱 洪水 地震 山火 冲突 战争 罢工 供应链 航运 港口 "
    "半导体 出口管制 贸易协定"
)

STRUCTURED_EPISODE_SECTIONS = {
    "market_observations",
    "economic_observations",
    "company_financials",
    "energy_observations",
}

EQUITY_RESEARCH_CORE_MARKET_SERIES = {
    "BAMLH0A0HYM2",
    "DCOILWTICO",
    "DGS2",
    "DGS10",
    "DTWEXBGS",
    "EFFR",
    "M2SL",
    "NASDAQCOM",
    "NFCI",
    "SP500",
    "T10Y2Y",
    "VIXCLS",
}

MODEL_EVIDENCE_EXCLUDED_MARKET_CATEGORIES = {
    "company_fundamental",
    "equity_factor",
    "equity_turnover",
    "equity_turnover_rate",
    "equity_volume",
    "historical_equity_price",
    "valuation",
}


class ResearchProviderError(RuntimeError):
    """Raised when an AI provider cannot return a valid bounded result."""


class PlannedResearchQuestion(BaseModel):
    """Minimal first-stage output before the full evidence-chain analysis."""

    question: str
    episode_start: date
    episode_end: date
    trigger_evidence_refs: list[str]
    outcome_evidence_refs: list[str]
    historical_context_refs: list[str]
    relationship_mode: Literal[
        "direct_linear",
        "mediated_linear",
        "nonlinear_exploratory",
    ] = "mediated_linear"
    bridge_hypotheses: list[str] = Field(default_factory=list, max_length=5)


class ResearchInquiryNotFoundError(LookupError):
    """Raised when a stored research inquiry does not exist."""


def run_research(
    session: Session,
    *,
    question: str | None,
    mode: Literal["user_question", "autonomous"],
    settings: Settings | None = None,
    transport: httpx.BaseTransport | None = None,
    progress_callback: Callable[[str, int, str], None] | None = None,
    checkpoint_callback: Callable[[str, int, str, dict[str, Any]], None] | None = None,
    resume_checkpoint: dict[str, Any] | None = None,
) -> ResearchInquiryView:
    """Build a local evidence pack and ask the configured local model."""
    usage_started = time.monotonic()
    runtime = settings or get_settings()
    resume = _usable_research_resume_checkpoint(
        resume_checkpoint,
        question=question,
        mode=mode,
    )
    if resume is not None:
        evidence = deepcopy(resume["evidence"])
        resumed_question = resume.get("model_question")
        assisted_question = (
            str(resumed_question) if isinstance(resumed_question, str) else question
        )
        _notify_research_progress(
            progress_callback,
            "checkpoint_restored",
            15,
            "已载入最近安全检查点，跳过已经完成的证据整理",
        )
    else:
        _notify_research_progress(
            progress_callback,
            "preparing_evidence",
            5,
            "正在整理本地新闻、市场、公司和经济数据",
        )
        evidence = _build_evidence_snapshot(
            session,
            question=question,
            settings=runtime,
            progress_callback=progress_callback,
        )
        assisted_question = _expand_plain_user_question(question, evidence=evidence)
    if assisted_question and question and assisted_question != question:
        evidence["question_assistance"] = {
            "applied": True,
            "original_question": question,
            "expanded_research_brief": assisted_question,
            "reason": "short_equity_question_expanded_into_auditable_dimensions",
        }
    _notify_research_progress(
        progress_callback,
        "evidence_snapshot_ready",
        15,
        "基础证据快照已冻结，准备定向检索",
    )
    if resume is None:
        _notify_research_checkpoint(
            checkpoint_callback,
            "evidence_snapshot_ready",
            15,
            "基础公司、新闻、市场和宏观证据已保存",
            _research_checkpoint_payload(
                question=question,
                model_question=assisted_question or question,
                evidence=evidence,
                result=None,
                percent=15,
            ),
        )
    if mode == "autonomous":
        previous_questions = evidence.get("prior_research_questions", [])
        focus_index = len(previous_questions) % len(AUTONOMOUS_FINANCIAL_FOCUS)
        evidence["required_autonomous_focus"] = AUTONOMOUS_FINANCIAL_FOCUS[focus_index]
    placeholder = question or "AI autonomous evidence-grounded research question"
    row = ResearchInquiry(
        question=placeholder,
        mode=mode,
        status="running",
        local_model=f"{runtime.llm_provider}:{runtime.llm_model}",
        # Keep the ORM value separate from the working dictionary so adding
        # planner evidence later is detected and persisted by SQLAlchemy.
        evidence_snapshot=dict(evidence),
    )
    session.add(row)
    session.flush()
    try:
        model_question = assisted_question or question
        model_mode = mode
        plan: PlannedResearchQuestion | None = None
        if mode == "autonomous":
            _notify_research_progress(
                progress_callback,
                "question_planning",
                20,
                "本地 AI 正在选择可验证的研究问题和时间窗口",
            )
            plan = _call_local_question_planner(
                evidence=evidence,
                settings=runtime,
                transport=transport,
            )
            model_question = plan.question
            planned_refs = list(
                dict.fromkeys(
                    [
                        *plan.trigger_evidence_refs,
                        *plan.outcome_evidence_refs,
                        *plan.historical_context_refs,
                    ]
                )
            )
            evidence["planned_question_evidence_refs"] = planned_refs
            evidence["episode_window"] = {
                "start": plan.episode_start.isoformat(),
                "end": plan.episode_end.isoformat(),
                "duration_days": (plan.episode_end - plan.episode_start).days + 1,
                "trigger_evidence_refs": plan.trigger_evidence_refs,
                "outcome_evidence_refs": plan.outcome_evidence_refs,
                "relationship_mode": plan.relationship_mode,
                "bridge_hypotheses": plan.bridge_hypotheses,
            }
            evidence["historical_context_refs"] = plan.historical_context_refs
            _prioritize_episode_evidence(evidence, plan=plan)
            evidence["research_workflow"] = {
                "status": "local_draft",
                "episode_window": evidence["episode_window"],
                "historical_context_only": True,
                "stages": [],
            }
            row.evidence_snapshot = dict(evidence)
            if _duplicates_prior_question(
                model_question,
                evidence.get("prior_research_questions", []),
            ):
                raise ResearchProviderError(
                    "local question planner repeated an existing research question"
                )
            model_mode = "user_question"
        if model_question and resume is None:
            _notify_research_progress(
                progress_callback,
                "targeted_retrieval",
                25,
                "正在按研究问题检索全文、事件和市场序列",
            )
            initial_report = enrich_research_evidence(
                session,
                evidence,
                question=model_question,
                episode_start=plan.episode_start if plan else None,
                episode_end=plan.episode_end if plan else None,
                required_refs=(list(evidence.get("planned_question_evidence_refs") or [])),
                pass_name="question_search",
            )
            evidence["question_search_summary"] = initial_report
            row.evidence_snapshot = dict(evidence)
            _notify_research_checkpoint(
                checkpoint_callback,
                "targeted_retrieval_complete",
                28,
                "定向证据检索已保存",
                _research_checkpoint_payload(
                    question=question,
                    model_question=model_question,
                    evidence=evidence,
                    result=None,
                    percent=28,
                ),
            )
        resumed_result = _resume_research_result(resume)
        if resumed_result is not None:
            result = resumed_result
            _notify_research_progress(
                progress_callback,
                "checkpoint_restored",
                55,
                "已恢复 AI 初稿，继续补证、因子检验和审计",
            )
        else:
            _notify_research_progress(
                progress_callback,
                "local_draft",
                30,
                "本地 AI 正在生成第一版报告，此阶段通常耗时最长",
            )
            result = _call_local_research_model(
                question=model_question,
                mode=model_mode,
                evidence=evidence,
                settings=runtime,
                transport=transport,
            )
            _notify_research_progress(
                progress_callback,
                "local_draft_complete",
                55,
                "第一版报告已生成，开始逐段补证",
            )
            _notify_research_checkpoint(
                checkpoint_callback,
                "local_draft_complete",
                55,
                "AI 初稿和引用证据已保存",
                _research_checkpoint_payload(
                    question=question,
                    model_question=model_question,
                    evidence=evidence,
                    result=result,
                    percent=55,
                ),
            )
    except ResearchProviderError as exc:
        row.status = "failed"
        row.error = str(exc)[:2_000]
        session.flush()
        raise
    if model_question:
        result.question = (
            question.strip() if mode == "user_question" and question else model_question.strip()
        )
    if plan and _planned_result_needs_repair(result, evidence=evidence):
        evidence["evidence_revision_instruction"] = (
            "The previous draft ignored the selected historical episode. Rebuild it "
            "using the exact trigger/outcome and derived market-window records in "
            "priority_evidence. Cite at least two of those retained IDs, state the "
            "observed changes, keep the entire answer inside episode_window, and "
            "do not introduce unrelated recent companies or events. If mechanism "
            "evidence is absent, verify only the observations and mark causality "
            "unsupported."
        )
        repair_error: str | None = None
        try:
            _notify_research_progress(
                progress_callback,
                "local_episode_repair",
                57,
                "本地 AI 正在按已选历史区间修复证据引用",
            )
            repaired = _call_local_research_model(
                question=model_question,
                mode="user_question",
                evidence=evidence,
                settings=runtime,
                transport=transport,
                max_attempts=1,
                timeout_seconds=runtime.research_llm_timeout_seconds,
            )
            repaired.question = plan.question.strip()
            repair_used_fallback = _planned_result_needs_repair(
                repaired,
                evidence=evidence,
            )
        except ResearchProviderError as exc:
            repair_error = str(exc)[:500]
            repair_used_fallback = True
            repaired = result
        result = (
            _grounded_episode_fallback(plan.question, evidence=evidence)
            if repair_used_fallback
            else repaired
        )
        evidence["research_workflow"]["stages"].append(
            {
                "stage": "local_episode_repair",
                "status": "completed",
                "model": f"{runtime.llm_provider}:{runtime.llm_model}",
                "reason": (
                    "deterministic_evidence_guard"
                    if repair_used_fallback
                    else "model_grounding_repair"
                ),
                "error": repair_error,
            }
        )
    result = _apply_numerical_evidence_quality_gate(result, evidence=evidence)
    workflow = evidence.setdefault(
        "research_workflow",
        {
            "status": "local_draft",
            "episode_window": evidence.get("episode_window"),
            "historical_context_only": True,
            "stages": [],
        },
    )
    workflow["stages"].append(
        {
            "stage": "local_draft",
            "status": "completed",
            "model": f"{runtime.llm_provider}:{runtime.llm_model}",
            "summary": result.summary,
        }
    )
    completion_end = plan.episode_end if plan else datetime.now(UTC).date()
    completion_start = plan.episode_start if plan else completion_end - timedelta(days=550)
    completion = complete_research_evidence(
        session,
        result=result,
        evidence=evidence,
        window_start=completion_start,
        window_end=completion_end,
    )
    _notify_research_progress(
        progress_callback,
        "bridge_evidence_completion",
        62,
        "正在核对因果链各环节的数据覆盖和异常值",
    )
    workflow["stages"].append(
        {
            "stage": "bridge_evidence_completion",
            "status": "completed",
            "segment_count": completion.segment_count,
            "candidate_data_segments": completion.candidate_data_segments,
            "rejected_anomaly_segments": completion.rejected_anomaly_segments,
            "missing_segments": completion.missing_segments,
        }
    )
    gap_queries = _research_gap_queries(result)
    if model_question and gap_queries:
        _notify_research_progress(
            progress_callback,
            "evidence_gap_search",
            68,
            "正在反查报告缺少的关键证据",
        )
        gap_report = enrich_research_evidence(
            session,
            evidence,
            question=model_question,
            episode_start=plan.episode_start if plan else None,
            episode_end=plan.episode_end if plan else None,
            required_refs=list(evidence.get("planned_question_evidence_refs") or []),
            extra_queries=gap_queries,
            pass_name="gap_search",
        )
        workflow["stages"].append(
            {
                "stage": "evidence_gap_search",
                "status": "completed",
                "query_count": len(gap_queries),
                "added_evidence": gap_report["added_total"],
                "available_evidence": gap_report["available_total"],
            }
        )
        needs_citation_repair = _needs_evidence_revision(result, evidence=evidence)
        if gap_report["added_total"] > 0 or needs_citation_repair:
            evidence["retrieval_iteration"] = 2
            evidence["previous_evidence_gaps"] = gap_queries
            evidence["evidence_revision_instruction"] = (
                "Rebuild the answer using the priority evidence and exact planned "
                "references; retain only gaps that remain after this search."
            )
            try:
                _notify_research_progress(
                    progress_callback,
                    "local_evidence_revision",
                    72,
                    "本地 AI 正在用补充证据重写和收敛报告",
                )
                revised_for_evidence = _call_local_research_model(
                    question=model_question,
                    mode="user_question",
                    evidence=evidence,
                    settings=runtime,
                    transport=transport,
                )
                revised_for_evidence.question = model_question.strip()
                revision_used_fallback = bool(
                    plan
                    and _planned_result_needs_repair(
                        revised_for_evidence,
                        evidence=evidence,
                    )
                )
                result = (
                    _grounded_episode_fallback(plan.question, evidence=evidence)
                    if plan and revision_used_fallback
                    else revised_for_evidence
                )
                workflow["stages"].append(
                    {
                        "stage": "local_evidence_revision",
                        "status": "completed",
                        "model": f"{runtime.llm_provider}:{runtime.llm_model}",
                        "reason": (
                            "deterministic_evidence_guard_after_gap_search"
                            if revision_used_fallback
                            else (
                                "new_evidence"
                                if gap_report["added_total"] > 0
                                else "citation_repair"
                            )
                        ),
                        "remaining_gap_count": len(_research_gap_queries(result)),
                    }
                )
                _notify_research_progress(
                    progress_callback,
                    "local_evidence_revision_complete",
                    84,
                    "证据修订完成，准备因子检验",
                )
                _notify_research_checkpoint(
                    checkpoint_callback,
                    "local_evidence_revision_complete",
                    84,
                    "补证后的报告和引用状态已保存",
                    _research_checkpoint_payload(
                        question=question,
                        model_question=model_question,
                        evidence=evidence,
                        result=result,
                        percent=84,
                    ),
                )
            except ResearchProviderError as exc:
                workflow["stages"].append(
                    {
                        "stage": "local_evidence_revision",
                        "status": "failed",
                        "error": str(exc)[:500],
                    }
                )
    stored_review: ChatGPTResearchReview | None = None
    if not runtime.openai_auto_review_enabled:
        workflow["status"] = "awaiting_local_report_audit"
        workflow["stages"].append(
            {
                "stage": "openai_review",
                "status": "skipped",
                "reason": "automatic_review_disabled",
                "manual_review_available": runtime.openai_api_key is not None,
            }
        )
    elif runtime.openai_api_key is not None:
        try:
            result, stored_review = _run_openai_revision_loop(
                local_result=result,
                evidence=evidence,
                settings=runtime,
                transport=transport,
            )
        except ResearchProviderError as exc:
            workflow["status"] = "openai_revision_failed"
            workflow["stages"].append(
                {
                    "stage": "openai_review",
                    "status": "failed",
                    "error": str(exc)[:500],
                }
            )
    else:
        workflow["status"] = "awaiting_openai_configuration"
        workflow["stages"].append(
            {
                "stage": "openai_review",
                "status": "not_configured",
            }
        )
    if plan and _planned_result_needs_repair(result, evidence=evidence):
        result = _grounded_episode_fallback(plan.question, evidence=evidence)
        workflow["stages"].append(
            {
                "stage": "final_evidence_guard",
                "status": "completed",
                "reason": "prevented_ungrounded_result_persistence",
            }
        )
    _notify_research_progress(
        progress_callback,
        "factor_mining",
        88,
        "正在运行线性/非线性因子和样本外检验",
    )
    result.factor_research = build_factor_research(
        session,
        result=result,
        evidence=evidence,
        settings=runtime,
        inquiry_id=row.id,
        persist_artifact=session.get_bind().dialect.name != "sqlite",
    )
    _notify_research_checkpoint(
        checkpoint_callback,
        "factor_mining_complete",
        94,
        "因子与样本外检验结果已保存",
        _research_checkpoint_payload(
            question=question,
            model_question=model_question,
            evidence=evidence,
            result=result,
            percent=94,
        ),
    )
    workflow["stages"].append(
        {
            "stage": "factor_mining",
            "status": "completed",
            "method": result.factor_research.method_version,
            "factor_count": len(result.factor_research.factors),
            "nonlinear_link_count": len(result.factor_research.nonlinear_links),
            "profit_validation_count": len(result.factor_research.profit_validations),
            "cross_sectional_validation_count": len(
                result.factor_research.cross_sectional_validations
            ),
            "archive_status": result.factor_research.archive_status,
        }
    )
    _notify_research_progress(
        progress_callback,
        "deterministic_audit",
        97,
        "正在审计引用、时间边界、估值算术和盈利证据",
    )
    _apply_local_report_audit(result, evidence=evidence)
    _notify_research_checkpoint(
        checkpoint_callback,
        "deterministic_audit_complete",
        99,
        "最终引用、时间边界和估值审计已保存",
        _research_checkpoint_payload(
            question=question,
            model_question=model_question,
            evidence=evidence,
            result=result,
            percent=99,
        ),
    )
    row.question = result.question
    row.result = result.model_dump(mode="json")
    evidence.setdefault('_reportUsage', {})['runWallSeconds'] = round(time.monotonic()-usage_started, 3)
    evidence['_reportUsage']['scope'] = 'This run and retained main local research calls only; planning, external review and prior resumes may be unmetered.'
    evidence['_reportUsage']['codexTokens'] = None
    row.evidence_snapshot = dict(evidence)
    if stored_review is not None:
        row.chatgpt_review = stored_review.model_dump(mode="json")
    row.status = "completed"
    row.error = None
    session.flush()
    _notify_research_progress(
        progress_callback,
        "completed",
        100,
        "报告和本地审计已完成",
    )
    return _inquiry_view(row)


def _notify_research_progress(
    callback: Callable[[str, int, str], None] | None,
    stage: str,
    percent: int,
    message: str,
) -> None:
    """Keep observability best-effort so a UI update can never fail research."""
    if callback is None:
        return
    try:
        callback(stage, max(0, min(100, percent)), message[:255])
    except TaskCancellationRequested:
        raise
    except Exception:
        return


def _notify_research_checkpoint(
    callback: Callable[[str, int, str, dict[str, Any]], None] | None,
    stage: str,
    percent: int,
    message: str,
    payload: dict[str, Any],
) -> None:
    if callback is None:
        return
    try:
        callback(stage, max(0, min(100, percent)), message[:255], payload)
    except TaskCancellationRequested:
        raise
    except Exception:
        return


def _research_checkpoint_payload(
    *,
    question: str | None,
    model_question: str | None,
    evidence: dict[str, Any],
    result: ModelResearchResult | None,
    percent: int,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "question": question,
        "model_question": model_question,
        "percent": percent,
        "evidence": deepcopy(evidence),
        "result": result.model_dump(mode="json") if result is not None else None,
    }


def _usable_research_resume_checkpoint(
    checkpoint: dict[str, Any] | None,
    *,
    question: str | None,
    mode: Literal["user_question", "autonomous"],
) -> dict[str, Any] | None:
    if mode != "user_question" or not isinstance(checkpoint, dict):
        return None
    if checkpoint.get("schema_version") != 1 or checkpoint.get("question") != question:
        return None
    if not isinstance(checkpoint.get("evidence"), dict):
        return None
    return checkpoint


def _resume_research_result(
    checkpoint: dict[str, Any] | None,
) -> ModelResearchResult | None:
    if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get("result"), dict):
        return None
    try:
        return ModelResearchResult.model_validate(checkpoint["result"])
    except ValidationError:
        return None


def _expand_plain_user_question(
    question: str | None,
    *,
    evidence: dict[str, Any],
) -> str | None:
    """Turn a short equity question into a professional brief without another model call."""
    if not question:
        return None
    context = evidence.get("equity_research_context")
    if not isinstance(context, dict) or len(question.strip()) >= 180:
        return question
    ticker = str(context.get("ticker") or "").upper()
    company = str(context.get("company") or ticker)
    if not ticker:
        return question
    return (
        f"用户原始问题：{question.strip()}\n"
        f"请把它扩展为对{company}（{ticker}）的可审计条件研究，而不是承诺涨跌或给出个性化投资建议。"
        "必须分别检查：产品与竞争、合同/订单、季度与TTM财务、估值、技术与持仓、"
        "宏观流动性、供应商—工厂—原料—物流、冲突/灾害空间暴露、替代技术；"
        "区分事实、相关性和因果推断，列出反证、缺失数据、失效条件及可执行的下一步补证据。"
    )[:1_000]


def audit_local_report(
    session: Session,
    *,
    inquiry_id: int,
    refresh_equity_evidence: bool = False,
    refresh_document_evidence: bool = False,
) -> ResearchInquiryView:
    """Re-audit one report; frozen evidence is the safe historical default."""
    row = session.get(ResearchInquiry, inquiry_id)
    if row is None:
        raise ResearchInquiryNotFoundError(inquiry_id)
    if row.status != "completed" or row.result is None:
        raise ResearchProviderError("only completed research can be locally audited")
    evidence = dict(row.evidence_snapshot or {})
    refreshed_documents: list[str] = []
    if refresh_equity_evidence:
        equity_context, derived_equity_evidence = build_equity_research_pack(
            session,
            question=row.question,
        )
        if equity_context is not None:
            evidence["equity_research_context"] = equity_context
            evidence["derived_equity_evidence"] = derived_equity_evidence
    else:
        equity_context = None
    if refresh_document_evidence:
        refreshed_documents = _refresh_document_evidence_snapshot(session, evidence)
    if refresh_equity_evidence or refresh_document_evidence:
        evidence["local_report_audit_refresh"] = {
            "mode": (
                "refresh_and_audit" if refresh_equity_evidence else "refresh_documents_and_audit"
            ),
            "refreshed_at": datetime.now(UTC).isoformat(),
            "new_point_in_time_cutoff": (
                equity_context.get("point_in_time_cutoff") if equity_context is not None else None
            ),
            "refreshed_document_refs": refreshed_documents,
        }
    else:
        evidence["local_report_audit_refresh"] = {
            "mode": "audit_only",
            "frozen_evidence": True,
            "audited_at": datetime.now(UTC).isoformat(),
        }
    if not isinstance(evidence.get("local_report_repairs"), list):
        evidence["local_report_repairs"] = []
    result = ModelResearchResult.model_validate(row.result)
    result = _sanitize_research_result(result, evidence=evidence)
    _apply_local_report_audit(result, evidence=evidence)
    row.result = result.model_dump(mode="json")
    row.evidence_snapshot = evidence
    session.flush()
    return _inquiry_view(row)


def _refresh_document_evidence_snapshot(
    session: Session,
    evidence: dict[str, Any],
) -> list[str]:
    """Refresh only already-captured document rows, preserving the report scope."""
    items = evidence.get("documents")
    if not isinstance(items, list):
        return []
    evidence_by_document_id: dict[int, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        match = re.fullmatch(r"document:(\d+)", str(item.get("evidence_id") or ""))
        if match:
            evidence_by_document_id[int(match.group(1))] = item
    if not evidence_by_document_id:
        return []

    rows = session.execute(
        select(Document, Source)
        .join(Source, Source.id == Document.source_id)
        .where(Document.id.in_(tuple(evidence_by_document_id)))
    ).all()
    settings = get_settings()
    archive = ColdArchive(
        settings.cold_data_root,
        min_free_bytes=settings.cold_archive_min_free_gb * 1024**3,
        max_used_percent=settings.cold_archive_max_used_percent,
    )
    changed: list[str] = []
    for document, source in rows:
        item = evidence_by_document_id[document.id]
        before = (
            item.get("evidence_tier"),
            item.get("can_verify_claims"),
            item.get("full_body_chars"),
            item.get("excerpt"),
        )
        full_body, read_tier = document_body_for_research(document, archive)
        tier = document_evidence_tier(document)
        item.update(
            {
                "title": document.title[:500],
                "published_at": (
                    document.published_at.isoformat() if document.published_at else None
                ),
                "source": source.name,
                "source_country": source.country,
                "language": document.language or source.language,
                "source_url": document.url,
                "excerpt": full_body[:700],
                "content_storage": read_tier,
                "full_body_chars": int(
                    (document.raw_metadata or {}).get("full_body_chars") or len(full_body)
                ),
                "evidence_tier": tier,
                "can_verify_claims": can_verify_claims(tier),
            }
        )
        after = (
            item.get("evidence_tier"),
            item.get("can_verify_claims"),
            item.get("full_body_chars"),
            item.get("excerpt"),
        )
        if after != before:
            changed.append(f"document:{document.id}")
    return sorted(changed)


def list_research_inquiries(
    session: Session,
    *,
    limit: int,
) -> list[ResearchInquiryView]:
    """Return recent stored inquiries newest-first."""
    rows = session.scalars(
        select(ResearchInquiry)
        .order_by(ResearchInquiry.created_at.desc(), ResearchInquiry.id.desc())
        .limit(limit)
    )
    return [_inquiry_view(row, include_full_evidence=False) for row in rows]


def list_research_inquiry_summaries(
    session: Session,
    *,
    page: int,
    page_size: int,
    search: str | None = None,
    market_region: Literal["us", "china"] | None = None,
    status: Literal["running", "completed", "failed"] | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
) -> tuple[list[ResearchInquirySummaryView], int]:
    """Return catalog metadata without selecting large result or evidence JSON."""
    batch_ticker = (
        select(ResearchBatchItem.ticker)
        .where(ResearchBatchItem.inquiry_id == ResearchInquiry.id)
        .order_by(ResearchBatchItem.id.desc())
        .limit(1)
        .correlate(ResearchInquiry)
        .scalar_subquery()
    )
    batch_company = (
        select(ResearchBatchItem.company_name)
        .where(ResearchBatchItem.inquiry_id == ResearchInquiry.id)
        .order_by(ResearchBatchItem.id.desc())
        .limit(1)
        .correlate(ResearchInquiry)
        .scalar_subquery()
    )
    batch_market = (
        select(ResearchBatchItem.market_region)
        .where(ResearchBatchItem.inquiry_id == ResearchInquiry.id)
        .order_by(ResearchBatchItem.id.desc())
        .limit(1)
        .correlate(ResearchInquiry)
        .scalar_subquery()
    )
    batch_sector = (
        select(ResearchBatchItem.sector)
        .where(ResearchBatchItem.inquiry_id == ResearchInquiry.id)
        .order_by(ResearchBatchItem.id.desc())
        .limit(1)
        .correlate(ResearchInquiry)
        .scalar_subquery()
    )
    # Single historical runs are not batch items; keep them discoverable by market.
    for_field = lambda key: func.coalesce(  # noqa: E731
        ResearchInquiry.evidence_snapshot["equity_research_context"][key].as_string(),
        ResearchInquiry.evidence_snapshot["equity_context"][key].as_string(),
    )
    batch_ticker = func.coalesce(batch_ticker, for_field("ticker"))
    batch_company = func.coalesce(batch_company, for_field("company_name"))
    batch_market = func.coalesce(batch_market, for_field("market_region"))
    batch_sector = func.coalesce(batch_sector, for_field("sector"))
    filters = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                ResearchInquiry.question.ilike(pattern),
                ResearchInquiry.local_model.ilike(pattern),
                batch_ticker.ilike(pattern),
                batch_company.ilike(pattern),
            )
        )
    if market_region:
        filters.append(batch_market == market_region)
    if status:
        filters.append(ResearchInquiry.status == status)
    if created_from:
        filters.append(
            ResearchInquiry.created_at
            >= datetime.combine(created_from, datetime.min.time(), tzinfo=UTC)
        )
    if created_to:
        filters.append(
            ResearchInquiry.created_at
            < datetime.combine(
                created_to + timedelta(days=1),
                datetime.min.time(),
                tzinfo=UTC,
            )
        )

    total = int(
        session.scalar(select(func.count(ResearchInquiry.id)).where(*filters)) or 0
    )
    rows = session.execute(
        select(
            ResearchInquiry.id,
            ResearchInquiry.question,
            ResearchInquiry.mode,
            ResearchInquiry.status,
            ResearchInquiry.local_model,
            ResearchInquiry.result.is_not(None).label("has_result"),
            batch_market.label("market_region"),
            batch_ticker.label("ticker"),
            batch_company.label("company_name"),
            batch_sector.label("sector"),
            ResearchInquiry.error,
            ResearchInquiry.created_at,
            ResearchInquiry.updated_at,
        )
        .where(*filters)
        .order_by(ResearchInquiry.created_at.desc(), ResearchInquiry.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    summaries = [
        ResearchInquirySummaryView(
            id=row.id,
            question=row.question,
            mode=cast(Literal["user_question", "autonomous"], row.mode),
            status=cast(Literal["running", "completed", "failed"], row.status),
            local_model=row.local_model,
            has_result=bool(row.has_result),
            market_region=cast(Literal["us", "china"] | None, row.market_region),
            ticker=row.ticker,
            company_name=row.company_name,
            sector=row.sector,
            error=row.error,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
    return summaries, total


def get_research_report_comparison(
    session: Session,
    inquiry_id: int,
    *,
    limit: int = 12,
) -> ResearchReportComparisonResponse:
    """Return a compact same-company report timeline without full report payloads."""
    selected = session.get(ResearchInquiry, inquiry_id)
    if selected is None:
        raise ResearchInquiryNotFoundError(inquiry_id)

    selected_item = session.scalar(
        select(ResearchBatchItem)
        .where(ResearchBatchItem.inquiry_id == inquiry_id)
        .order_by(ResearchBatchItem.id.desc())
        .limit(1)
    )
    selected_evidence = selected.evidence_snapshot or {}
    equity_context = selected_evidence.get("equity_research_context") or selected_evidence.get("equity_context")
    equity_context = equity_context if isinstance(equity_context, dict) else {}
    ticker = str(
        selected_item.ticker if selected_item is not None else equity_context.get("ticker") or ""
    ).strip().upper()
    market_region = (
        selected_item.market_region
        if selected_item is not None
        else equity_context.get("market_region")
    )
    company_name = (
        selected_item.company_name
        if selected_item is not None
        else equity_context.get("company_name")
    )
    sector = selected_item.sector if selected_item is not None else equity_context.get("sector")

    historical = bool(selected_evidence.get("historical_reconstruction"))
    if historical or not ticker or market_region not in {"us", "china"}:
        version, _, _ = _research_report_comparison_version(
            selected,
            batch_item=selected_item,
            selected_inquiry_id=inquiry_id,
        )
        return ResearchReportComparisonResponse(
            selected_inquiry_id=inquiry_id,
            comparable=False,
            reason="historical_reconstruction" if historical else "company_identity_unavailable",
            market_region=market_region if market_region in {"us", "china"} else None,
            ticker=ticker or None,
            company_name=str(company_name) if company_name else None,
            sector=str(sector) if sector else None,
            total_versions=1,
            versions=[version],
        )

    subject_filter = (
        func.upper(ResearchBatchItem.ticker) == ticker,
        ResearchBatchItem.market_region == market_region,
        ResearchInquiry.status == "completed",
        ResearchInquiry.result.is_not(None),
    )
    total_versions = int(
        session.scalar(
            select(func.count(func.distinct(ResearchInquiry.id)))
            .select_from(ResearchInquiry)
            .join(
                ResearchBatchItem,
                ResearchBatchItem.inquiry_id == ResearchInquiry.id,
            )
            .where(*subject_filter)
        )
        or 0
    )
    rows = session.execute(
        select(ResearchInquiry, ResearchBatchItem)
        .join(
            ResearchBatchItem,
            ResearchBatchItem.inquiry_id == ResearchInquiry.id,
        )
        .where(*subject_filter)
        .order_by(ResearchInquiry.created_at.desc(), ResearchInquiry.id.desc())
        .limit(limit)
    ).all()
    row_by_inquiry = {row.ResearchInquiry.id: row for row in rows}
    if inquiry_id not in row_by_inquiry:
        rows = [*rows, (selected, selected_item)]
    rows = sorted(
        rows,
        key=lambda row: (row[0].created_at, row[0].id),
        reverse=True,
    )
    if len(rows) > limit:
        removable = next(
            (index for index in range(len(rows) - 1, -1, -1) if rows[index][0].id != inquiry_id),
            None,
        )
        if removable is not None:
            rows.pop(removable)

    compact_with_refs = [
        _research_report_comparison_version(
            inquiry,
            batch_item=batch_item,
            selected_inquiry_id=inquiry_id,
        )
        for inquiry, batch_item in rows
    ]
    chronological = list(reversed(compact_with_refs))
    compared: list[
        tuple[
            ResearchReportComparisonVersion,
            set[str],
            dict[str, ResearchReportEvidenceChange],
        ]
    ] = []
    previous_refs: set[str] | None = None
    previous_catalog: dict[str, ResearchReportEvidenceChange] = {}
    previous_version: ResearchReportComparisonVersion | None = None
    for version, evidence_refs, evidence_catalog in chronological:
        if previous_refs is not None:
            new_refs = sorted(evidence_refs - previous_refs)
            retired_refs = sorted(previous_refs - evidence_refs)
            version = version.model_copy(
                update={
                    "new_evidence_count": len(new_refs),
                    "retired_evidence_count": len(retired_refs),
                    "new_evidence": [
                        evidence_catalog[ref]
                        for ref in new_refs
                        if ref in evidence_catalog
                    ][:8],
                    "retired_evidence": [
                        previous_catalog[ref]
                        for ref in retired_refs
                        if ref in previous_catalog
                    ][:8],
                    "change_summary": _comparison_change_summary(
                        current=version,
                        previous=previous_version,
                        new_refs=new_refs,
                        retired_refs=retired_refs,
                        current_catalog=evidence_catalog,
                        previous_catalog=previous_catalog,
                    ),
                }
            )
        compared.append((version, evidence_refs, evidence_catalog))
        previous_refs = evidence_refs
        previous_catalog = evidence_catalog
        previous_version = version

    return ResearchReportComparisonResponse(
        selected_inquiry_id=inquiry_id,
        comparable=len(compared) > 1,
        reason=None if len(compared) > 1 else "single_company_report",
        market_region=cast(Literal["us", "china"], market_region),
        ticker=ticker,
        company_name=str(company_name) if company_name else None,
        sector=str(sector) if sector else None,
        total_versions=max(total_versions, 1),
        versions=[version for version, _, _ in reversed(compared)],
    )


def list_research_report_change_alerts(
    session: Session,
    *,
    limit: int = 24,
) -> ResearchReportChangeAlertListResponse:
    """Rank latest-versus-prior company report changes without returning full reports."""
    now = datetime.now(UTC)
    cache_key = (id(session.get_bind()), limit)
    cached = _REPORT_CHANGE_ALERT_CACHE.get(cache_key)
    if cached is not None and now - cached[0] < REPORT_CHANGE_ALERT_CACHE_TTL:
        return cached[1]
    metadata_rows = session.execute(
        select(
            ResearchInquiry.id,
            ResearchInquiry.created_at,
            ResearchBatchItem.market_region,
            ResearchBatchItem.ticker,
            ResearchBatchItem.company_name,
            ResearchBatchItem.sector,
        )
        .join(
            ResearchBatchItem,
            ResearchBatchItem.inquiry_id == ResearchInquiry.id,
        )
        .where(
            ResearchInquiry.status == "completed",
            ResearchInquiry.result.is_not(None),
            ResearchBatchItem.market_region.in_(("us", "china")),
        )
        .order_by(ResearchInquiry.created_at.desc(), ResearchInquiry.id.desc())
    ).all()

    histories: dict[tuple[str, str], list[Any]] = {}
    seen_inquiries: set[int] = set()
    for row in metadata_rows:
        inquiry_id = int(row.id)
        if inquiry_id in seen_inquiries:
            continue
        seen_inquiries.add(inquiry_id)
        ticker = str(row.ticker or "").strip().upper()
        market_region = str(row.market_region or "")
        if not ticker or market_region not in {"us", "china"}:
            continue
        history = histories.setdefault((market_region, ticker), [])
        if len(history) < 2:
            history.append(row)

    comparable_histories = [history for history in histories.values() if len(history) == 2]
    inquiry_ids = {
        int(row.id)
        for history in comparable_histories
        for row in history
    }
    detailed_rows = session.execute(
        select(ResearchInquiry, ResearchBatchItem)
        .join(
            ResearchBatchItem,
            ResearchBatchItem.inquiry_id == ResearchInquiry.id,
        )
        .where(ResearchInquiry.id.in_(inquiry_ids))
        .order_by(ResearchBatchItem.id.desc())
    ).all() if inquiry_ids else []
    detail_by_inquiry: dict[int, tuple[ResearchInquiry, ResearchBatchItem]] = {}
    for inquiry, batch_item in detailed_rows:
        detail_by_inquiry.setdefault(inquiry.id, (inquiry, batch_item))

    alerts: list[ResearchReportChangeAlert] = []
    for history in comparable_histories:
        latest_metadata, previous_metadata = history
        latest_pair = detail_by_inquiry.get(int(latest_metadata.id))
        previous_pair = detail_by_inquiry.get(int(previous_metadata.id))
        if latest_pair is None or previous_pair is None:
            continue
        latest, latest_refs, latest_catalog = _research_report_comparison_version(
            latest_pair[0],
            batch_item=latest_pair[1],
            selected_inquiry_id=latest_pair[0].id,
        )
        previous, previous_refs, previous_catalog = _research_report_comparison_version(
            previous_pair[0],
            batch_item=previous_pair[1],
            selected_inquiry_id=latest_pair[0].id,
        )
        new_refs = sorted(latest_refs - previous_refs)
        retired_refs = sorted(previous_refs - latest_refs)
        change = _comparison_change_summary(
            current=latest,
            previous=previous,
            new_refs=new_refs,
            retired_refs=retired_refs,
            current_catalog=latest_catalog,
            previous_catalog=previous_catalog,
        )
        if change is None:
            continue
        score = _report_change_alert_score(
            current=latest,
            previous=previous,
            change=change,
            evidence_turnover=len(new_refs) + len(retired_refs),
        )
        severity: Literal["critical", "high", "medium", "low"]
        if score >= 50:
            severity = "critical"
        elif score >= 30:
            severity = "high"
        elif score >= 15:
            severity = "medium"
        else:
            severity = "low"
        alerts.append(
            ResearchReportChangeAlert(
                latest_inquiry_id=latest.inquiry_id,
                previous_inquiry_id=previous.inquiry_id,
                market_region=cast(Literal["us", "china"], latest_metadata.market_region),
                ticker=str(latest_metadata.ticker).strip().upper(),
                company_name=str(latest_metadata.company_name),
                sector=(str(latest_metadata.sector) if latest_metadata.sector else None),
                latest_created_at=latest.created_at,
                previous_created_at=previous.created_at,
                severity=severity,
                alert_score=score,
                assessment=_report_change_alert_assessment(change),
                current_confidence=latest.confidence,
                previous_confidence=previous.confidence,
                current_readiness=latest.data_readiness_score,
                previous_readiness=previous.data_readiness_score,
                change_summary=change,
            )
        )

    alerts.sort(
        key=lambda item: (
            item.alert_score,
            item.latest_created_at,
            item.latest_inquiry_id,
        ),
        reverse=True,
    )
    response = ResearchReportChangeAlertListResponse(
        generated_at=now,
        total_companies_with_history=len(comparable_histories),
        alerts=alerts[:limit],
        methodology=(
            "Monitoring priority ranks changes in chain confidence, data readiness, "
            "verified and unresolved links, cited-evidence turnover, signal, timing, "
            "price and conditional reward-risk. It is not an investment rating or "
            "proof that one observed change caused another."
        ),
    )
    _REPORT_CHANGE_ALERT_CACHE[cache_key] = (now, response)
    return response


def _report_change_alert_score(
    *,
    current: ResearchReportComparisonVersion,
    previous: ResearchReportComparisonVersion,
    change: ResearchReportChangeSummary,
    evidence_turnover: int,
) -> int:
    """Create a bounded monitoring-priority score, not a bullishness score."""
    score = 0.0
    if change.confidence_delta is not None:
        score += min(abs(change.confidence_delta) * 100.0, 25.0)
    if change.data_readiness_delta is not None:
        score += min(abs(change.data_readiness_delta) * 100.0, 20.0)
    score += min(abs(change.verified_steps_delta) * 3.0, 8.0)
    score += min(abs(change.unresolved_steps_delta) * 3.0, 8.0)
    score += min(evidence_turnover * 1.5, 10.0)
    if change.primary_signal_from != change.primary_signal_to:
        score += 18.0
    if change.timing_from != change.timing_to:
        score += 12.0
    if (
        change.current_price_delta is not None
        and previous.current_price is not None
        and abs(previous.current_price) > 0.0001
    ):
        score += min(
            abs(change.current_price_delta / previous.current_price) * 100.0,
            15.0,
        )
    if change.reward_risk_delta is not None:
        score += min(abs(change.reward_risk_delta) * 5.0, 10.0)
    if change.audit_status_from != change.audit_status_to:
        score += 6.0
    if change.model_changed:
        score += 4.0
    if change.summary_changed:
        score += 2.0
    return max(0, min(100, round(score)))


def _report_change_alert_assessment(
    change: ResearchReportChangeSummary,
) -> Literal[
    "evidence_upgrade",
    "evidence_downgrade",
    "mixed_change",
    "parameter_refresh",
]:
    """Classify evidence quality movement separately from market direction."""
    quality_movement = (
        (change.confidence_delta or 0.0) * 60.0
        + (change.data_readiness_delta or 0.0) * 40.0
        + change.verified_steps_delta * 3.0
        - change.unresolved_steps_delta * 3.0
    )
    if quality_movement >= 3.0:
        return "evidence_upgrade"
    if quality_movement <= -3.0:
        return "evidence_downgrade"
    evidence_drivers = {
        "new_cited_evidence",
        "retired_cited_evidence",
        "chain_support_increased",
        "chain_support_decreased",
        "data_readiness_improved",
        "data_readiness_weakened",
        "verified_links_increased",
        "verified_links_decreased",
        "unresolved_links_increased",
        "unresolved_links_decreased",
    }
    if not evidence_drivers.intersection(change.driver_codes):
        return "parameter_refresh"
    return "mixed_change"


def _research_report_comparison_version(
    inquiry: ResearchInquiry,
    *,
    batch_item: ResearchBatchItem | None,
    selected_inquiry_id: int,
) -> tuple[
    ResearchReportComparisonVersion,
    set[str],
    dict[str, ResearchReportEvidenceChange],
]:
    """Extract only longitudinal metrics needed by the browser comparison panel."""
    result = inquiry.result if isinstance(inquiry.result, dict) else {}
    evidence = inquiry.evidence_snapshot if isinstance(inquiry.evidence_snapshot, dict) else {}
    directional = evidence.get("directional_confidence")
    directional = directional if isinstance(directional, dict) else {}
    readiness = batch_item.data_readiness if batch_item is not None else None
    readiness = readiness if isinstance(readiness, dict) else {}
    if not readiness:
        equity_context = evidence.get("equity_research_context")
        equity_context = equity_context if isinstance(equity_context, dict) else {}
        candidate = equity_context.get("data_readiness")
        readiness = candidate if isinstance(candidate, dict) else {}
    audit = evidence.get("local_report_audit")
    audit = audit if isinstance(audit, dict) else {}
    audit_checks = audit.get("checks")
    audit_checks = audit_checks if isinstance(audit_checks, dict) else {}

    dimensions = result.get("equity_dimensions")
    dimensions = dimensions if isinstance(dimensions, list) else []
    signal_counts = {key: 0 for key in ("bullish", "bearish", "mixed", "unknown")}
    for dimension in dimensions:
        if not isinstance(dimension, dict):
            continue
        signal = str(dimension.get("signal") or "unknown")
        signal_counts[signal if signal in signal_counts else "unknown"] += 1
    primary_signal = max(signal_counts, key=signal_counts.get) if dimensions else "unknown"

    framework = result.get("equity_decision_framework")
    framework = framework if isinstance(framework, dict) else {}
    technical = next(
        (
            item
            for item in evidence.get("derived_equity_evidence", [])
            if isinstance(item, dict) and item.get("category") == "derived_market_technical"
        ),
        {},
    )
    risk_reward = technical.get("risk_reward") if isinstance(technical, dict) else {}
    risk_reward = risk_reward if isinstance(risk_reward, dict) else {}
    hypothesis = next(
        (item for item in result.get("hypotheses", []) if isinstance(item, dict)),
        {},
    )
    confidence = _comparison_float(directional.get("score"))
    if confidence is None:
        confidence = _comparison_float(hypothesis.get("confidence"))

    evidence_refs = _evidence_ids(evidence)
    evidence_catalog = _comparison_evidence_catalog(evidence)
    cited_refs = {
        str(ref)
        for hypothesis_item in result.get("hypotheses", [])
        if isinstance(hypothesis_item, dict)
        for step in hypothesis_item.get("steps", [])
        if isinstance(step, dict)
        for ref in step.get("evidence_refs", [])
        if ref
    }
    cited_refs.update(
        str(ref)
        for dimension in dimensions
        if isinstance(dimension, dict)
        for ref in dimension.get("evidence_refs", [])
        if ref
    )
    cited_refs.update(
        str(ref)
        for factor in result.get("factor_candidates", [])
        if isinstance(factor, dict)
        for ref in factor.get("evidence_refs", [])
        if ref
    )
    paper = result.get("paper_report")
    if isinstance(paper, dict):
        cited_refs.update(str(ref) for ref in paper.get("evidence_refs", []) if ref)
    comparison_refs = cited_refs & evidence_refs

    blockers = directional.get("blockers_zh") or directional.get("blockers_en") or []
    blockers = [str(item) for item in blockers if item][:8] if isinstance(blockers, list) else []
    summary = str(result.get("summary") or "").strip() or None
    if summary and len(summary) > 700:
        summary = f"{summary[:697]}…"

    data_readiness_score = _comparison_float(readiness.get("score"))
    if data_readiness_score is None:
        data_readiness_score = _comparison_float(directional.get("data_readiness_score"))
    data_readiness_status = readiness.get("status") or audit_checks.get(
        "data_readiness_status"
    )
    directional_allowed = readiness.get("directional_conclusion_allowed")
    if directional_allowed is None:
        directional_allowed = directional.get("directional_conclusion_allowed")

    return (
        ResearchReportComparisonVersion(
            inquiry_id=inquiry.id,
            question=inquiry.question,
            status=cast(Literal["running", "completed", "failed"], inquiry.status),
            local_model=inquiry.local_model,
            created_at=inquiry.created_at,
            updated_at=inquiry.updated_at,
            is_selected=inquiry.id == selected_inquiry_id,
            confidence=confidence,
            data_readiness_score=data_readiness_score,
            data_readiness_status=(str(data_readiness_status) if data_readiness_status else None),
            directional_conclusion_allowed=(
                bool(directional_allowed) if directional_allowed is not None else None
            ),
            verified_steps=int(directional.get("verified_steps") or 0),
            partially_supported_steps=int(
                directional.get("partially_supported_steps") or 0
            ),
            unresolved_steps=int(directional.get("unresolved_steps") or 0),
            evidence_count=len(evidence_refs),
            cited_reference_count=int(
                audit_checks.get("cited_reference_count") or len(cited_refs)
            ),
            missing_reference_count=int(
                audit_checks.get("missing_reference_count") or len(cited_refs - evidence_refs)
            ),
            primary_signal=cast(
                Literal["bullish", "bearish", "mixed", "unknown"],
                primary_signal,
            ),
            signal_counts=signal_counts,
            timing_assessment=(
                str(framework.get("timing_assessment"))
                if framework.get("timing_assessment")
                else None
            ),
            current_price=_comparison_float(
                technical.get("adjusted_close") if isinstance(technical, dict) else None
            ),
            entry_reference=_comparison_float(risk_reward.get("entry_reference")),
            stop_reference=_comparison_float(risk_reward.get("stop_reference")),
            target_reference=_comparison_float(risk_reward.get("target_reference")),
            reward_risk_ratio=_comparison_float(risk_reward.get("reward_risk_ratio")),
            audit_status=str(audit.get("status")) if audit.get("status") else None,
            audit_recommendation=(
                str(audit.get("recommendation")) if audit.get("recommendation") else None
            ),
            summary=summary,
            blockers=blockers,
        ),
        comparison_refs,
        evidence_catalog,
    )


def _comparison_evidence_catalog(
    evidence: dict[str, Any],
) -> dict[str, ResearchReportEvidenceChange]:
    """Index evidence identities with bounded human-readable metadata."""
    catalog: dict[str, ResearchReportEvidenceChange] = {}
    for value in evidence.values():
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict) or not isinstance(item.get("evidence_id"), str):
                continue
            evidence_id = str(item["evidence_id"])
            if evidence_id in catalog:
                continue
            title = _comparison_first_text(
                item,
                (
                    "title",
                    "label",
                    "name",
                    "series_name",
                    "metric_label",
                    "fact_name",
                    "product_name",
                    "description",
                    "statement",
                ),
            )
            if title is None:
                ticker = _comparison_first_text(item, ("ticker", "symbol"))
                form = _comparison_first_text(item, ("filing_form", "form"))
                if ticker or form:
                    title = " · ".join(part for part in (ticker, form) if part)
            catalog[evidence_id] = ResearchReportEvidenceChange(
                evidence_id=evidence_id,
                category=_comparison_first_text(item, ("category", "evidence_type")),
                title=title,
                observed_at=_comparison_first_text(
                    item,
                    (
                        "published_at",
                        "observed_on",
                        "observed_at",
                        "filed_at",
                        "filed_on",
                        "filing_date",
                        "period_end",
                        "as_of",
                        "date",
                    ),
                ),
                source=_comparison_first_text(
                    item,
                    ("source_name", "provider", "source", "feed_name", "filing_form"),
                ),
            )
    return catalog


def _comparison_first_text(
    item: dict[str, Any],
    keys: tuple[str, ...],
) -> str | None:
    for key in keys:
        value = item.get(key)
        if not isinstance(value, (str, int, float)) or isinstance(value, bool):
            continue
        text = " ".join(str(value).split())
        if text:
            return f"{text[:237]}…" if len(text) > 240 else text
    return None


def _comparison_change_summary(
    *,
    current: ResearchReportComparisonVersion,
    previous: ResearchReportComparisonVersion | None,
    new_refs: list[str],
    retired_refs: list[str],
    current_catalog: dict[str, ResearchReportEvidenceChange],
    previous_catalog: dict[str, ResearchReportEvidenceChange],
) -> ResearchReportChangeSummary | None:
    if previous is None:
        return None
    confidence_delta = _comparison_numeric_delta(current.confidence, previous.confidence)
    readiness_delta = _comparison_numeric_delta(
        current.data_readiness_score,
        previous.data_readiness_score,
    )
    price_delta = _comparison_numeric_delta(current.current_price, previous.current_price)
    reward_risk_delta = _comparison_numeric_delta(
        current.reward_risk_ratio,
        previous.reward_risk_ratio,
    )
    verified_delta = current.verified_steps - previous.verified_steps
    unresolved_delta = current.unresolved_steps - previous.unresolved_steps
    cited_delta = current.cited_reference_count - previous.cited_reference_count
    signal_changed = current.primary_signal != previous.primary_signal
    timing_changed = current.timing_assessment != previous.timing_assessment
    audit_changed = current.audit_status != previous.audit_status
    model_changed = current.local_model != previous.local_model
    summary_changed = (current.summary or "").strip() != (previous.summary or "").strip()

    driver_codes: list[str] = []
    if new_refs:
        driver_codes.append("new_cited_evidence")
    if retired_refs:
        driver_codes.append("retired_cited_evidence")
    if confidence_delta is not None and abs(confidence_delta) >= 0.005:
        driver_codes.append(
            "chain_support_increased" if confidence_delta > 0 else "chain_support_decreased"
        )
    if readiness_delta is not None and abs(readiness_delta) >= 0.005:
        driver_codes.append(
            "data_readiness_improved" if readiness_delta > 0 else "data_readiness_weakened"
        )
    if verified_delta:
        driver_codes.append(
            "verified_links_increased" if verified_delta > 0 else "verified_links_decreased"
        )
    if unresolved_delta:
        driver_codes.append(
            "unresolved_links_increased"
            if unresolved_delta > 0
            else "unresolved_links_decreased"
        )
    if signal_changed:
        driver_codes.append("signal_changed")
    if timing_changed:
        driver_codes.append("timing_changed")
    if price_delta is not None and abs(price_delta) >= 0.0001:
        driver_codes.append("market_price_updated")
    if reward_risk_delta is not None and abs(reward_risk_delta) >= 0.0001:
        driver_codes.append("risk_reward_recalculated")
    if audit_changed:
        driver_codes.append("audit_status_changed")
    if model_changed:
        driver_codes.append("model_changed")
    if summary_changed:
        driver_codes.append("conclusion_text_changed")

    return ResearchReportChangeSummary(
        confidence_delta=confidence_delta,
        data_readiness_delta=readiness_delta,
        verified_steps_delta=verified_delta,
        unresolved_steps_delta=unresolved_delta,
        cited_evidence_delta=cited_delta,
        current_price_delta=price_delta,
        reward_risk_delta=reward_risk_delta,
        primary_signal_from=previous.primary_signal,
        primary_signal_to=current.primary_signal,
        timing_from=previous.timing_assessment,
        timing_to=current.timing_assessment,
        audit_status_from=previous.audit_status,
        audit_status_to=current.audit_status,
        model_changed=model_changed,
        summary_changed=summary_changed,
        new_category_counts=_comparison_category_counts(new_refs, current_catalog),
        retired_category_counts=_comparison_category_counts(
            retired_refs,
            previous_catalog,
        ),
        driver_codes=driver_codes[:16],
    )


def _comparison_category_counts(
    refs: list[str],
    catalog: dict[str, ResearchReportEvidenceChange],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ref in refs:
        category = catalog.get(ref).category if ref in catalog else None
        key = category or "uncategorized"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:8])


def _comparison_numeric_delta(current: Any, previous: Any) -> float | None:
    current_number = _comparison_float(current)
    previous_number = _comparison_float(previous)
    if current_number is None or previous_number is None:
        return None
    return current_number - previous_number


def _comparison_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def get_research_inquiry(
    session: Session,
    inquiry_id: int,
    *,
    include_full_evidence: bool = True,
) -> ResearchInquiryView:
    """Load one inquiry or raise a typed not-found error."""
    row = session.get(ResearchInquiry, inquiry_id)
    if row is None:
        raise ResearchInquiryNotFoundError(inquiry_id)
    return _inquiry_view(row, include_full_evidence=include_full_evidence)


def refresh_factor_research(
    session: Session,
    *,
    inquiry_id: int,
    settings: Settings | None = None,
) -> ResearchInquiryView:
    """Re-mine factors from one stored report and the latest retained market data."""
    row = session.get(ResearchInquiry, inquiry_id)
    if row is None:
        raise ResearchInquiryNotFoundError(inquiry_id)
    if row.status != "completed" or row.result is None:
        raise ResearchProviderError("only completed research can be factor-mined")
    result = ModelResearchResult.model_validate(row.result)
    evidence = dict(row.evidence_snapshot or {})
    result = _apply_numerical_evidence_quality_gate(result, evidence=evidence)
    completion_start, completion_end = _evidence_completion_window(evidence)
    completion = complete_research_evidence(
        session,
        result=result,
        evidence=evidence,
        window_start=completion_start,
        window_end=completion_end,
    )
    factor_research = build_factor_research(
        session,
        result=result,
        evidence=evidence,
        settings=settings or get_settings(),
        inquiry_id=row.id,
        persist_artifact=session.get_bind().dialect.name != "sqlite",
    )
    session.refresh(row, attribute_names=["result", "evidence_snapshot"])
    result.factor_research = factor_research
    result = _sanitize_research_result(result, evidence=evidence)
    _apply_local_report_audit(result, evidence=evidence)
    # Keep the newly resolved candidates and quality reports. Refreshing the ORM
    # row restores the pre-run JSON snapshot and would otherwise silently discard
    # the evidence completer output before commit.
    workflow = evidence.setdefault("research_workflow", {"status": "completed", "stages": []})
    stages = workflow.setdefault("stages", [])
    if isinstance(stages, list):
        stages.append(
            {
                "stage": "bridge_evidence_completion_refresh",
                "status": "completed",
                "segment_count": completion.segment_count,
                "candidate_data_segments": completion.candidate_data_segments,
                "rejected_anomaly_segments": completion.rejected_anomaly_segments,
                "missing_segments": completion.missing_segments,
            }
        )
        stages.append(
            {
                "stage": "factor_mining_refresh",
                "status": "completed",
                "method": factor_research.method_version,
                "generated_at": factor_research.generated_at.isoformat(),
                "cross_sectional_validation_count": len(
                    factor_research.cross_sectional_validations
                ),
                "archive_status": factor_research.archive_status,
            }
        )
    row.result = result.model_dump(mode="json")
    row.evidence_snapshot = evidence
    session.flush()
    return _inquiry_view(row)


def _evidence_completion_window(evidence: dict[str, Any]) -> tuple[date, date]:
    episode = evidence.get("episode_window")
    if isinstance(episode, dict):
        try:
            return date.fromisoformat(str(episode["start"])[:10]), date.fromisoformat(
                str(episode["end"])[:10]
            )
        except (KeyError, ValueError):
            pass
    end = datetime.now(UTC).date()
    return end - timedelta(days=550), end


def _apply_numerical_evidence_quality_gate(
    result: ModelResearchResult,
    *,
    evidence: dict[str, Any],
) -> ModelResearchResult:
    """Prevent invalid numerical endpoints from surviving into conclusions.

    Raw provider rows remain auditable under ``quality_rejected_evidence``, but
    non-finite values and non-positive price observations are removed from the
    model-facing evidence sections and from all claimed citations.
    """
    rejected: dict[str, dict[str, Any]] = {}
    for section in ("market_observations", "energy_observations"):
        retained: list[Any] = []
        for item in evidence.get(section) or []:
            if not isinstance(item, dict):
                retained.append(item)
                continue
            reason = _numerical_evidence_rejection_reason(item)
            evidence_id = item.get("evidence_id")
            if reason and isinstance(evidence_id, str):
                rejected[evidence_id] = {**item, "quality_rejection_reason": reason}
            else:
                retained.append(item)
        evidence[section] = retained
    if not rejected:
        return result

    rejected_ids = set(rejected)
    existing_rejected = [
        item
        for item in evidence.get("quality_rejected_evidence") or []
        if isinstance(item, dict) and item.get("evidence_id") not in rejected_ids
    ]
    evidence["quality_rejected_evidence"] = [*existing_rejected, *rejected.values()]
    for key in (
        "planned_question_evidence_refs",
        "historical_context_refs",
        "forecasted_news_refs",
    ):
        values = evidence.get(key)
        if isinstance(values, list):
            evidence[key] = [value for value in values if value not in rejected_ids]
    priority = evidence.get("priority_evidence")
    if isinstance(priority, list):
        evidence["priority_evidence"] = [
            item
            for item in priority
            if not isinstance(item, dict) or item.get("evidence_id") not in rejected_ids
        ]
    episode = evidence.get("episode_window")
    if isinstance(episode, dict):
        for key in ("trigger_evidence_refs", "outcome_evidence_refs"):
            values = episode.get(key)
            if isinstance(values, list):
                episode[key] = [value for value in values if value not in rejected_ids]

    payload = result.model_dump(mode="json")
    used_rejected: set[str] = set()
    for hypothesis in payload["hypotheses"]:
        hypothesis_rejected: set[str] = set()
        for step in hypothesis["steps"]:
            step_refs = list(step.get("evidence_refs") or [])
            blocked = rejected_ids.intersection(step_refs)
            if not blocked:
                continue
            used_rejected.update(blocked)
            hypothesis_rejected.update(blocked)
            step["evidence_refs"] = [ref for ref in step_refs if ref not in rejected_ids]
            if not step["evidence_refs"]:
                step["status"] = "evidence_missing"
                step["confidence"] = min(float(step.get("confidence") or 0), 0.1)
                step["label"] = (
                    "Numerical endpoint rejected by the data-quality gate; "
                    "a valid observed value is required."
                )
        if hypothesis_rejected:
            hypothesis["confidence"] = min(float(hypothesis.get("confidence") or 0), 0.2)
            hypothesis["outcome"] = (
                "The proposed numerical endpoint failed the data-quality gate and "
                "is not currently verified."
            )
            gaps = list(hypothesis.get("evidence_gaps") or [])
            gaps.append("A finite, positive price observation for the proposed endpoint.")
            hypothesis["evidence_gaps"] = list(dict.fromkeys(gaps))[:10]

    if not used_rejected:
        evidence["research_quality_gate"] = {
            "status": "rejected_unused_rows",
            "rejected_evidence_refs": sorted(rejected_ids),
            "invalid_claim_citations": 0,
        }
        return ModelResearchResult.model_validate(payload)

    gate_summary = (
        f"The prior draft cited {len(used_rejected)} numerical endpoint(s) that "
        "failed the deterministic data-quality gate. The endpoint and causal "
        "relationship are not verified until a valid observation is available."
    )
    payload["summary"] = gate_summary
    payload["news_forecasts"] = []
    payload["factor_research"] = None
    for factor in payload.get("factor_candidates") or []:
        refs = list(factor.get("evidence_refs") or [])
        if rejected_ids.intersection(refs):
            factor["evidence_refs"] = [ref for ref in refs if ref not in rejected_ids]
            factor["confidence"] = min(float(factor.get("confidence") or 0), 0.1)
    paper = payload.get("paper_report")
    if isinstance(paper, dict):
        paper["abstract"] = gate_summary
        paper["conclusion"] = gate_summary
        paper["evidence_refs"] = [
            ref for ref in paper.get("evidence_refs") or [] if ref not in rejected_ids
        ]
        paper["evidence_chain"] = [
            step["label"] for hypothesis in payload["hypotheses"] for step in hypothesis["steps"]
        ][:12]
        paper["findings"] = [
            "No causal finding is admitted because the proposed endpoint failed "
            "the numerical data-quality gate."
        ]
        limitations = list(paper.get("limitations") or [])
        limitations.append("The originally cited endpoint was a rejected provider value.")
        paper["limitations"] = list(dict.fromkeys(limitations))[:10]
    evidence["research_quality_gate"] = {
        "status": "claims_downgraded",
        "rejected_evidence_refs": sorted(rejected_ids),
        "invalid_claim_citations": len(used_rejected),
    }
    return ModelResearchResult.model_validate(payload)


def _numerical_evidence_rejection_reason(item: dict[str, Any]) -> str | None:
    value = item.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if not math.isfinite(numeric):
        return "non_finite_value"
    identity = " ".join(
        str(item.get(key) or "") for key in ("category", "name", "indicator", "unit")
    ).casefold()
    price_like = any(
        marker in identity for marker in ("price", "close", "价格", "收盘", "$/", "usd/", "cny/")
    )
    if price_like and numeric <= 0:
        return "nonpositive_price_value"
    return None


def backfill_factor_research(
    session: Session,
    *,
    settings: Settings | None = None,
    report_limit: int = 24,
    report_offset: int = 0,
    only_missing: bool = True,
) -> dict[str, int]:
    """Add dual-track factor research to recent completed reports."""
    runtime = settings or get_settings()
    rows = list(
        session.scalars(
            select(ResearchInquiry)
            .where(
                ResearchInquiry.status == "completed",
                ResearchInquiry.result.is_not(None),
            )
            .order_by(desc(ResearchInquiry.created_at), desc(ResearchInquiry.id))
            .offset(report_offset)
            .limit(report_limit)
        )
    )
    updated = 0
    stored = 0
    for row in rows:
        result = ModelResearchResult.model_validate(row.result)
        if only_missing and result.factor_research is not None:
            continue
        factor_research = build_factor_research(
            session,
            result=result,
            evidence=dict(row.evidence_snapshot or {}),
            settings=runtime,
            inquiry_id=row.id,
            persist_artifact=session.get_bind().dialect.name != "sqlite",
        )
        session.refresh(row, attribute_names=["result"])
        result = ModelResearchResult.model_validate(row.result)
        result.factor_research = factor_research
        row.result = result.model_dump(mode="json")
        updated += 1
        stored += int(factor_research.archive_status == "stored")
    session.flush()
    return {
        "scanned_reports": len(rows),
        "factor_reports_updated": updated,
        "cold_artifacts_stored": stored,
    }


def record_research_review(
    session: Session,
    *,
    inquiry_id: int,
    decision: str,
    reviewer_note: str | None,
) -> ResearchInquiryView:
    """Append one human report decision without rewriting prior audit history."""
    row = session.get(ResearchInquiry, inquiry_id)
    if row is None:
        raise ResearchInquiryNotFoundError(inquiry_id)
    if row.status != "completed" or not row.result:
        raise ResearchProviderError("only completed research reports can be reviewed")
    row.review_signals.append(
        ResearchReviewSignal(
            decision=decision,
            reviewer_note=(reviewer_note or "").strip() or None,
        )
    )
    session.flush()
    return _inquiry_view(row)


def refresh_research_forecasts(
    session: Session,
    *,
    settings: Settings | None = None,
    transport: httpx.BaseTransport | None = None,
    report_limit: int = 12,
) -> dict[str, int]:
    """Find post-cutoff evidence and let the local validator score forecasts."""
    runtime = settings or get_settings()
    rows = list(
        session.scalars(
            select(ResearchInquiry)
            .where(
                ResearchInquiry.status == "completed",
                ResearchInquiry.result.is_not(None),
            )
            .order_by(desc(ResearchInquiry.created_at), desc(ResearchInquiry.id))
            .limit(report_limit)
        )
    )
    forecasts_checked = 0
    forecasts_updated = 0
    for row in rows:
        result = ModelResearchResult.model_validate(row.result)
        fallback_created = False
        if not result.news_forecasts:
            result.news_forecasts = _fallback_news_forecasts(
                result,
                list(row.evidence_snapshot.get("news_forecast_anchors") or []),
            )
            fallback_created = True
        pending = [
            forecast
            for forecast in result.news_forecasts
            if forecast.status in {"unresolved", "candidate_evidence_found"}
        ]
        cases = build_forecast_validation_cases(session, pending)
        if not cases:
            if fallback_created:
                session.refresh(row, attribute_names=["result"])
                latest_result = ModelResearchResult.model_validate(row.result)
                if not latest_result.news_forecasts:
                    latest_result.news_forecasts = result.news_forecasts
                    row.result = latest_result.model_dump(mode="json")
            continue
        forecasts_checked += len(cases)
        batch = _call_local_forecast_validator(
            cases=cases,
            settings=runtime,
            transport=transport,
        )
        case_by_id = {str(case["forecast"]["forecast_id"]): case for case in cases}
        forecasts_by_id = {forecast.forecast_id: forecast for forecast in result.news_forecasts}
        updated_forecast_ids: set[str] = set()
        validated_at = datetime.now(UTC)
        for decision in batch.decisions:
            forecast = forecasts_by_id.get(decision.forecast_id)
            case = case_by_id.get(decision.forecast_id)
            if forecast is None or case is None:
                continue
            candidate_by_ref = {
                str(item["evidence_id"]): item
                for item in case["candidate_evidence"]
                if isinstance(item, dict) and item.get("evidence_id")
            }
            supporting = [
                ref
                for ref in decision.supporting_evidence_refs
                if ref in candidate_by_ref and candidate_by_ref[ref].get("can_verify_claims")
            ]
            contradicting = [
                ref
                for ref in decision.contradicting_evidence_refs
                if ref in candidate_by_ref and candidate_by_ref[ref].get("can_verify_claims")
            ]
            status = decision.status
            if status in {"supported", "partially_supported"} and not supporting:
                status = "candidate_evidence_found"
            if status == "contradicted" and not contradicting:
                status = "candidate_evidence_found"
            forecast.status = status
            forecast.supporting_evidence_refs = supporting[:20]
            forecast.contradicting_evidence_refs = contradicting[:20]
            forecast.validation_summary = decision.validation_summary
            forecast.last_validated_at = validated_at
            forecast.confidence = min(decision.confidence, 0.75)
            forecasts_updated += 1
            updated_forecast_ids.add(forecast.forecast_id)
        session.refresh(row, attribute_names=["result", "evidence_snapshot"])
        latest_result = ModelResearchResult.model_validate(row.result)
        updated_by_id = {
            forecast.forecast_id: forecast
            for forecast in result.news_forecasts
            if forecast.forecast_id in updated_forecast_ids
        }
        if not latest_result.news_forecasts:
            latest_result.news_forecasts = result.news_forecasts
        else:
            latest_result.news_forecasts = [
                updated_by_id.get(forecast.forecast_id, forecast)
                for forecast in latest_result.news_forecasts
            ]
        row.result = latest_result.model_dump(mode="json")
        evidence = dict(row.evidence_snapshot)
        evidence["forecast_validation_cases"] = cases
        runs = list(evidence.get("forecast_validation_runs") or [])
        runs.append(
            {
                "validated_at": validated_at.isoformat(),
                "forecast_count": len(cases),
                "local_model": f"{runtime.llm_provider}:{runtime.llm_model}",
            }
        )
        evidence["forecast_validation_runs"] = runs[-12:]
        row.evidence_snapshot = evidence
    session.flush()
    return {
        "scanned_reports": len(rows),
        "forecasts_checked": forecasts_checked,
        "forecasts_updated": forecasts_updated,
    }


def _call_local_forecast_validator(
    *,
    cases: list[dict[str, Any]],
    settings: Settings,
    transport: httpx.BaseTransport | None,
) -> ModelForecastValidationBatch:
    if settings.llm_provider == "mock":
        raise ResearchProviderError("forecast validation requires a local model")
    schema = _compatible_json_schema(ModelForecastValidationBatch)
    messages = [
        {"role": "system", "content": LOCAL_FORECAST_VALIDATOR_PROMPT},
        {
            "role": "user",
            "content": json.dumps({"forecast_cases": cases}, ensure_ascii=False),
        },
    ]
    if settings.llm_provider == "ollama":
        endpoint = "/api/chat"
        payload: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": messages,
            "stream": False,
            "think": False,
            "format": schema,
            "options": {"temperature": 0.05},
        }
    else:
        endpoint = "/v1/chat/completions"
        payload = {
            "model": settings.llm_model,
            "messages": messages,
            "stream": False,
            "temperature": 0.05,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "news_forecast_validation",
                    "strict": True,
                    "schema": schema,
                },
            },
        }
    try:
        with httpx.Client(
            base_url=str(settings.llm_base_url).rstrip("/"),
            timeout=settings.research_llm_timeout_seconds,
            transport=transport,
        ) as client:
            response = client.post(endpoint, json=payload)
            response.raise_for_status()
        data = response.json()
        content = (
            data["message"]["content"]
            if settings.llm_provider == "ollama"
            else data["choices"][0]["message"]["content"]
        )
        return ModelForecastValidationBatch.model_validate_json(content)
    except (httpx.HTTPError, KeyError, TypeError, ValueError, ValidationError) as exc:
        raise ResearchProviderError(
            "local forecast validator could not return an auditable decision"
        ) from exc


def review_with_openai(
    session: Session,
    *,
    inquiry_id: int,
    settings: Settings | None = None,
    transport: httpx.BaseTransport | None = None,
) -> ResearchInquiryView:
    """Send a completed local result to the optional OpenAI Responses API."""
    runtime = settings or get_settings()
    if runtime.openai_api_key is None:
        raise ResearchProviderError("OpenAI review is not configured; set NEWSAPP_OPENAI_API_KEY")
    row = session.get(ResearchInquiry, inquiry_id)
    if row is None:
        raise ResearchInquiryNotFoundError(inquiry_id)
    if row.status != "completed" or not row.result:
        raise ResearchProviderError("only completed local research can be reviewed")
    evidence = dict(row.evidence_snapshot)
    result, stored = _run_openai_revision_loop(
        local_result=ModelResearchResult.model_validate(row.result),
        evidence=evidence,
        settings=runtime,
        transport=transport,
    )
    row.result = result.model_dump(mode="json")
    row.evidence_snapshot = evidence
    row.chatgpt_review = stored.model_dump(mode="json")
    session.flush()
    return _inquiry_view(row)


def review_logic_chain_with_openai(
    session: Session,
    *,
    hypothesis_id: int,
    settings: Settings | None = None,
    transport: httpx.BaseTransport | None = None,
) -> ChatGPTResearchReview:
    """Audit any stored local logic-chain hypothesis through OpenAI."""
    runtime = settings or get_settings()
    if runtime.openai_api_key is None:
        raise ResearchProviderError("OpenAI review is not configured; set NEWSAPP_OPENAI_API_KEY")
    row = session.get(LogicChainHypothesis, hypothesis_id)
    if row is None:
        raise ResearchInquiryNotFoundError(hypothesis_id)
    analysis = json.loads(row.steps)
    document_ids = json.loads(row.evidence_document_ids)
    document_evidence = [
        {
            "evidence_id": f"document:{document.id}",
            "title": document.title,
            "published_at": (document.published_at.isoformat() if document.published_at else None),
            "source": source.name,
            "source_url": document.url,
        }
        for document, source in session.execute(
            select(Document, Source)
            .join(Source, Source.id == Document.source_id)
            .where(Document.id.in_(document_ids))
        )
    ]
    local_result = {
        "title": row.title,
        "confidence": float(row.confidence),
        "rationale": row.rationale,
        "steps": analysis.get("steps", []),
        "association_score": analysis.get("association_score"),
        "evidence_coverage_score": analysis.get("evidence_coverage_score"),
        "counterevidence": analysis.get("counterevidence", []),
        "causal_validation": analysis.get("causal_validation"),
    }
    review = _call_openai_audit(
        local_result=local_result,
        evidence_snapshot={"documents": document_evidence},
        settings=runtime,
        transport=transport,
    )
    stored = ChatGPTResearchReview(
        **review.model_dump(),
        model=runtime.openai_review_model,
        reviewed_at=datetime.now(UTC),
    )
    analysis["chatgpt_review"] = stored.model_dump(mode="json")
    row.steps = json.dumps(analysis, ensure_ascii=False)
    session.flush()
    return stored


def _call_openai_audit(
    *,
    local_result: dict[str, Any],
    evidence_snapshot: dict[str, Any],
    settings: Settings,
    transport: httpx.BaseTransport | None,
) -> ModelChatGPTResearchReview:
    if settings.openai_api_key is None:
        raise ResearchProviderError("OpenAI review is not configured; set NEWSAPP_OPENAI_API_KEY")
    schema = _compatible_json_schema(ModelChatGPTResearchReview)
    audit_evidence = _compact_evidence(evidence_snapshot, max_chars=75_000)
    payload = {
        "model": settings.openai_review_model,
        "reasoning": {"effort": "medium"},
        "store": False,
        "safety_identifier": hashlib.sha256(
            settings.cluster_review_secret.encode("utf-8")
        ).hexdigest()[:32],
        "input": [
            {"role": "developer", "content": OPENAI_REVIEW_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "local_result": local_result,
                        "evidence_snapshot": audit_evidence,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "news_map_research_review",
                "strict": True,
                "schema": schema,
            }
        },
    }
    response: httpx.Response | None = None
    try:
        with httpx.Client(
            base_url=str(settings.openai_review_base_url).rstrip("/"),
            timeout=settings.openai_review_timeout_seconds,
            transport=transport,
        ) as client:
            response = client.post(
                "/responses",
                headers={
                    "Authorization": (f"Bearer {settings.openai_api_key.get_secret_value()}"),
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
        return ModelChatGPTResearchReview.model_validate_json(
            _responses_output_text(response.json())
        )
    except httpx.HTTPStatusError as exc:
        provider_detail = _safe_provider_error(response)
        raise ResearchProviderError(
            f"OpenAI Responses API rejected the review request: {provider_detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise ResearchProviderError(
            f"OpenAI Responses API transport failed: {type(exc).__name__}"
        ) from exc
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise ResearchProviderError(
            "OpenAI Responses API returned an invalid structured review: "
            f"{type(exc).__name__}: {str(exc)[:500]}"
        ) from exc


def _safe_provider_error(response: httpx.Response | None) -> str:
    """Extract a provider error code/message without returning request secrets."""
    if response is None:
        return "no HTTP response"
    try:
        payload = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return f"HTTP {response.status_code}"
    code = str(error.get("code") or error.get("type") or "provider_error")
    message = str(error.get("message") or "request rejected")
    return f"HTTP {response.status_code} {code}: {message[:500]}"


def _run_openai_revision_loop(
    *,
    local_result: ModelResearchResult,
    evidence: dict[str, Any],
    settings: Settings,
    transport: httpx.BaseTransport | None,
) -> tuple[ModelResearchResult, ChatGPTResearchReview]:
    """Audit, revise locally, then ask OpenAI to confirm the revised result."""
    workflow = evidence.setdefault(
        "research_workflow",
        {
            "status": "local_draft",
            "episode_window": evidence.get("episode_window"),
            "historical_context_only": True,
            "stages": [],
        },
    )
    stages = workflow.setdefault("stages", [])
    initial_review = _call_openai_audit(
        local_result=local_result.model_dump(mode="json"),
        evidence_snapshot=evidence,
        settings=settings,
        transport=transport,
    )
    workflow["initial_openai_review"] = initial_review.model_dump(mode="json")
    stages.append(
        {
            "stage": "openai_review",
            "status": "completed",
            "model": settings.openai_review_model,
            "recommendation": initial_review.recommendation,
            "finding_count": len(initial_review.findings),
            "missing_evidence_count": len(initial_review.missing_evidence),
        }
    )
    revised = _call_local_revision_model(
        local_result=local_result,
        review=initial_review,
        evidence=evidence,
        settings=settings,
        transport=transport,
    )
    stages.append(
        {
            "stage": "local_revision",
            "status": "completed",
            "model": f"{settings.llm_provider}:{settings.llm_model}",
            "before_summary": local_result.summary,
            "after_summary": revised.summary,
            "feedback_items_received": len(initial_review.findings),
        }
    )
    final_review: ModelChatGPTResearchReview
    try:
        final_review = _call_openai_audit(
            local_result=revised.model_dump(mode="json"),
            evidence_snapshot=evidence,
            settings=settings,
            transport=transport,
        )
        stages.append(
            {
                "stage": "openai_confirmation",
                "status": "completed",
                "model": settings.openai_review_model,
                "recommendation": final_review.recommendation,
                "remaining_findings": len(final_review.findings),
                "remaining_missing_evidence": len(final_review.missing_evidence),
            }
        )
        workflow["status"] = (
            "completed" if final_review.recommendation == "accept" else "needs_human_review"
        )
    except ResearchProviderError as exc:
        final_review = initial_review
        workflow["status"] = "confirmation_failed"
        stages.append(
            {
                "stage": "openai_confirmation",
                "status": "failed",
                "error": str(exc)[:500],
            }
        )
    workflow["final_recommendation"] = final_review.recommendation
    stored = ChatGPTResearchReview(
        **final_review.model_dump(),
        model=settings.openai_review_model,
        reviewed_at=datetime.now(UTC),
    )
    return revised, stored


def _call_local_revision_model(
    *,
    local_result: ModelResearchResult,
    review: ModelChatGPTResearchReview,
    evidence: dict[str, Any],
    settings: Settings,
    transport: httpx.BaseTransport | None,
) -> ModelResearchResult:
    """Require the local model to apply the external audit without new facts."""
    compact_evidence = _compact_evidence(
        evidence,
        max_chars=max(4_000, settings.llm_max_input_chars - 3_500),
    )
    messages = [
        {"role": "system", "content": LOCAL_REVISION_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "episode_window": evidence.get("episode_window"),
                    "local_draft": local_result.model_dump(mode="json"),
                    "openai_audit": review.model_dump(mode="json"),
                    "retained_evidence": compact_evidence,
                },
                ensure_ascii=False,
            ),
        },
    ]
    schema = _compatible_json_schema(ModelResearchResult)
    if settings.llm_provider == "ollama":
        endpoint = "/api/chat"
        payload: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": messages,
            "stream": False,
            "think": False,
            "format": schema,
            "options": {"temperature": 0.05},
        }
    else:
        endpoint = "/v1/chat/completions"
        payload = {
            "model": settings.llm_model,
            "messages": messages,
            "stream": False,
            "temperature": 0.05,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "news_map_research_revision",
                    "strict": True,
                    "schema": schema,
                },
            },
        }
    try:
        with httpx.Client(
            base_url=str(settings.llm_base_url).rstrip("/"),
            timeout=settings.research_llm_timeout_seconds,
            transport=transport,
        ) as client:
            response = client.post(endpoint, json=payload)
            response.raise_for_status()
        data = response.json()
        content = (
            data["message"]["content"]
            if settings.llm_provider == "ollama"
            else data["choices"][0]["message"]["content"]
        )
        revised = _validated_research_content(content)
        revised.question = local_result.question
        return _sanitize_research_result(revised, evidence=evidence)
    except (
        httpx.HTTPError,
        KeyError,
        TypeError,
        ValueError,
        ValidationError,
    ) as exc:
        raise ResearchProviderError(
            "local model could not apply the OpenAI research review"
        ) from exc


def _build_evidence_snapshot(
    session: Session,
    *,
    question: str | None,
    settings: Settings,
    progress_callback: Callable[[str, int, str], None] | None = None,
) -> dict[str, Any]:
    research_terms = question or (
        "inflation interest rates monetary policy treasury yield credit spread "
        "liquidity debt currency earnings valuation stocks commodities oil gas "
        "industrial production employment recession growth supply chain trade "
        "通胀 利率 货币政策 国债 流动性 债务 汇率 盈利 估值 股市 大宗商品 "
        "工业 失业 衰退 增长 供应链 贸易"
    )
    _notify_research_progress(
        progress_callback,
        "evidence_company",
        5,
        "正在整理公司财报、估值、股东资金和供应链证据",
    )
    equity_context, derived_equity_evidence = build_equity_research_pack(
        session,
        question=question,
    )
    equity_ticker = str(equity_context.get("ticker")) if equity_context is not None else None
    equity_sec_ticker = (
        str(equity_context.get("sec_ticker"))
        if equity_context is not None and equity_context.get("sec_ticker")
        else None
    )
    equity_price_series_id = (
        str(equity_context.get("price_series_id"))
        if equity_context is not None and equity_context.get("price_series_id")
        else (f"EQ:{equity_ticker}" if equity_ticker else None)
    )
    _notify_research_progress(
        progress_callback,
        "evidence_history",
        6,
        "公司证据已整理，正在读取历史报告和可靠研究时间窗",
    )
    now = datetime.now(UTC)
    prior_research_questions = list(
        session.scalars(
            select(ResearchInquiry.question)
            .where(ResearchInquiry.status == "completed")
            .order_by(ResearchInquiry.created_at.desc())
            .limit(12)
        )
    )
    prior_research_results = list(
        session.scalars(
            select(ResearchInquiry.result)
            .where(
                ResearchInquiry.status == "completed",
                ResearchInquiry.result.is_not(None),
            )
            .order_by(ResearchInquiry.created_at.desc())
            .limit(100)
        )
    )
    forecasted_news_refs = list(
        dict.fromkeys(
            str(forecast.get("anchor_evidence_ref"))
            for result in prior_research_results
            if isinstance(result, dict)
            for forecast in result.get("news_forecasts") or []
            if isinstance(forecast, dict) and forecast.get("anchor_evidence_ref")
        )
    )
    research_event_table = build_research_event_table(session, now=now)
    preferred_research_period = select_preferred_research_period(
        research_event_table,
        prior_questions=prior_research_questions,
    )
    _notify_research_progress(
        progress_callback,
        "evidence_news",
        7,
        "历史研究表已准备，正在筛选新闻全文与官方文件",
    )
    document_bands = (
        (now - timedelta(days=365), None, 2_000),
        (now - timedelta(days=365 * 3), now - timedelta(days=365), 800),
        (now - timedelta(days=365 * 7), now - timedelta(days=365 * 3), 800),
        (now - timedelta(days=365 * 15), now - timedelta(days=365 * 7), 800),
        (None, now - timedelta(days=365 * 15), 500),
    )
    documents: list[tuple[Document, Source]] = []
    for band_start, band_end, band_limit in document_bands:
        document_statement = (
            select(Document, Source)
            .join(Source, Source.id == Document.source_id)
            .where(Document.published_at.is_not(None))
        )
        if band_start is not None:
            document_statement = document_statement.where(Document.published_at >= band_start)
        if band_end is not None:
            document_statement = document_statement.where(Document.published_at < band_end)
        band_rows = [
            (document, source)
            for document, source in session.execute(
                document_statement.order_by(desc(Document.published_at), desc(Document.id)).limit(
                    band_limit
                )
            )
        ]
        documents.extend(
            sorted(
                band_rows,
                key=lambda item: (
                    _text_relevance(
                        f"{item[0].title} {item[0].body or ''}",
                        research_terms,
                    ),
                    item[0].published_at or item[0].fetched_at,
                ),
                reverse=True,
            )[:18]
        )
    documents.extend(
        (document, source)
        for document, source in session.execute(
            select(Document, Source)
            .join(Source, Source.id == Document.source_id)
            .where(Document.published_at.is_(None))
            .order_by(desc(Document.fetched_at), desc(Document.id))
            .limit(30)
        )
    )
    relevant_documents = sorted(
        documents,
        key=lambda item: (
            _text_relevance(
                f"{item[0].title} {item[0].body or ''}",
                research_terms,
            ),
            item[0].published_at or item[0].fetched_at,
        ),
        reverse=True,
    )[:80]
    ranked_documents = _unique_document_rows(
        [*documents[:20], *relevant_documents],
        limit=80,
    )
    cold_archive = ColdArchive(
        settings.cold_data_root,
        min_free_bytes=settings.cold_archive_min_free_gb * 1024**3,
        max_used_percent=settings.cold_archive_max_used_percent,
    )
    document_evidence: list[dict[str, Any]] = []
    for position, (document, source) in enumerate(ranked_documents, start=1):
        full_body, read_tier = document_body_for_research(document, cold_archive)
        document_evidence.append(
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
                "excerpt": full_body[:700],
                "content_storage": read_tier,
                "full_body_chars": int(
                    (document.raw_metadata or {}).get("full_body_chars") or len(full_body)
                ),
                "evidence_tier": document_evidence_tier(document),
                "can_verify_claims": can_verify_claims(document_evidence_tier(document)),
            }
        )
        if position % 10 == 0 or position == len(ranked_documents):
            _notify_research_progress(
                progress_callback,
                "evidence_news",
                8,
                f"正在读取新闻全文与官方文件 {position}/{len(ranked_documents)}",
            )
    _notify_research_progress(
        progress_callback,
        "evidence_events",
        9,
        "新闻证据已整理，正在匹配历史事件与地理位置",
    )
    event_rows: list[Event] = []
    for band_start, band_end, _ in document_bands:
        event_statement = select(Event)
        if band_start is not None:
            event_statement = event_statement.where(Event.start_at >= band_start)
        if band_end is not None:
            event_statement = event_statement.where(Event.start_at < band_end)
        band_events = list(
            session.scalars(event_statement.order_by(Event.start_at.desc()).limit(400))
        )
        event_rows.extend(
            sorted(
                band_events,
                key=lambda event: (
                    _text_relevance(
                        f"{event.title} {event.summary or ''} {event.event_type}",
                        research_terms,
                    ),
                    event.start_at,
                ),
                reverse=True,
            )[:14]
        )
    event_evidence = [
        {
            "evidence_id": f"event:{event.id}",
            "category": "canonical_event",
            "title": event.title,
            "event_type": event.event_type,
            "occurred_at": event.start_at.isoformat(),
            "country_code": event.country_code,
            "latitude": float(event.latitude) if event.latitude is not None else None,
            "longitude": float(event.longitude) if event.longitude is not None else None,
            "confidence": float(event.confidence),
        }
        for event in _unique_events(event_rows, limit=70)
    ]
    retained_event_ids = {item["evidence_id"] for item in event_evidence}
    for period in research_event_table.get("periods", []):
        for event in period.get("representative_events", []):
            if event["evidence_id"] in retained_event_ids:
                continue
            event_evidence.append(event)
            retained_event_ids.add(event["evidence_id"])
    _notify_research_progress(
        progress_callback,
        "evidence_macro",
        10,
        "事件证据已整理，正在加载宏观经济与能源序列",
    )
    finance_indicator_codes = {
        "NY.GDP.MKTP.CD",
        "NY.GDP.MKTP.KD.ZG",
        "FP.CPI.TOTL.ZG",
        "SL.UEM.TOTL.ZS",
        "GC.DOD.TOTL.GD.ZS",
        "BN.CAB.XOKA.GD.ZS",
        "FI.RES.TOTL.CD",
        "NV.IND.MANF.CD",
        "NV.AGR.TOTL.CD",
        "NE.EXP.GNFS.CD",
        "NE.IMP.GNFS.CD",
    }
    economic_rows = [
        (observation, indicator, country)
        for observation, indicator, country in session.execute(
            select(EconomicObservation, EconomicIndicator, CountryProfile)
            .join(
                EconomicIndicator,
                EconomicIndicator.code == EconomicObservation.indicator_code,
            )
            .join(
                CountryProfile,
                CountryProfile.iso3 == EconomicObservation.country_iso3,
            )
            .order_by(EconomicObservation.year.desc())
            .limit(1_200)
        )
    ]
    historical_economic_rows = [
        (observation, indicator, country)
        for observation, indicator, country in session.execute(
            select(EconomicObservation, EconomicIndicator, CountryProfile)
            .join(
                EconomicIndicator,
                EconomicIndicator.code == EconomicObservation.indicator_code,
            )
            .join(
                CountryProfile,
                CountryProfile.iso3 == EconomicObservation.country_iso3,
            )
            .where(EconomicObservation.indicator_code.in_(finance_indicator_codes))
            .order_by(EconomicObservation.year.asc())
            .limit(1_200)
        )
    ]
    ranked_recent_economic_rows = sorted(
        economic_rows,
        key=lambda item: (
            2 if item[1].code in finance_indicator_codes else 0,
            _text_relevance(
                f"{item[1].name_en} {item[1].name_zh} {item[2].name}",
                research_terms,
            ),
            item[0].year,
        ),
        reverse=True,
    )[:80]
    ranked_historical_economic_rows = sorted(
        historical_economic_rows,
        key=lambda item: (
            _text_relevance(
                f"{item[1].name_en} {item[1].name_zh} {item[2].name}",
                research_terms,
            ),
            -item[0].year,
        ),
        reverse=True,
    )[:40]
    ranked_economic_rows = _unique_economic_rows(
        [*ranked_recent_economic_rows, *ranked_historical_economic_rows],
        limit=120,
    )
    economic_evidence = [
        {
            "evidence_id": (f"economic:{country.iso3}:{indicator.code}:{observation.year}"),
            "category": "economic",
            "country": country.name,
            "indicator": indicator.name_en,
            "indicator_code": indicator.code,
            "year": observation.year,
            "value": observation.value,
            "unit": indicator.unit,
            "source": indicator.source_name,
            "source_url": indicator.source_url,
        }
        for observation, indicator, country in ranked_economic_rows
    ]
    energy_evidence: list[dict[str, Any]] = []
    for series in session.scalars(
        select(EnergySeries)
        .where(EnergySeries.materialized.is_(True))
        .order_by(EnergySeries.updated_at.desc())
        .limit(40)
    ):
        observations = [
            session.scalar(
                select(EnergyObservation)
                .where(EnergyObservation.series_id == series.series_id)
                .order_by(ordering)
                .limit(1)
            )
            for ordering in (
                EnergyObservation.period.desc(),
                EnergyObservation.period.asc(),
            )
        ]
        for observation in {
            item.period: item for item in observations if item is not None
        }.values():
            energy_evidence.append(
                {
                    "evidence_id": f"energy:{series.series_id}:{observation.period}",
                    "category": "energy_or_commodity",
                    "series_id": series.series_id,
                    "name": series.name,
                    "period": observation.period,
                    "value": observation.value,
                    "unit": series.units,
                    "source": "U.S. EIA bulk data",
                    "source_url": series.source_url,
                }
            )
    _notify_research_progress(
        progress_callback,
        "evidence_market",
        11,
        "宏观与能源证据已整理，正在加载行情、利率和流动性序列",
    )
    market_evidence: list[dict[str, Any]] = []
    reliable_start = date.fromisoformat(
        str(research_event_table.get("reliable_start") or "2007-01-01")
    )
    reliable_end = date.fromisoformat(
        str(
            research_event_table.get("reliable_end")
            or f"{max(now.year - 1, reliable_start.year):04d}-12-31"
        )
    )
    market_series_statement = select(MarketSeries).where(
        ~MarketSeries.category.in_(MODEL_EVIDENCE_EXCLUDED_MARKET_CATEGORIES)
    )
    if equity_ticker:
        equity_series_ids = {
            *EQUITY_RESEARCH_CORE_MARKET_SERIES,
            *([equity_price_series_id] if equity_price_series_id else []),
        }
        equity_context_categories = {
            "bond_proxy",
            "commodity_price",
            "commodity_proxy",
            "credit_spread",
            "currency_index",
            "currency_proxy",
            "financial_conditions",
            "global_market_proxy",
            "liquidity",
            "market_index",
            "market_volatility",
            "policy_rate",
            "sector_etf",
            "treasury_yield",
        }
        market_series_statement = market_series_statement.where(
            or_(
                MarketSeries.series_id.in_(equity_series_ids),
                MarketSeries.category.in_(equity_context_categories),
            )
        )
    retained_market_series = list(
        session.scalars(market_series_statement.order_by(MarketSeries.series_id))
    )
    for position, market_series in enumerate(retained_market_series, start=1):
        market_observation_by_date: dict[str, MarketObservation] = {}
        observation_year = extract("year", MarketObservation.observed_on)
        annual_bounds = list(
            session.execute(
                select(
                    observation_year,
                    func.min(MarketObservation.observed_on),
                    func.max(MarketObservation.observed_on),
                )
                .where(
                    MarketObservation.series_id == market_series.series_id,
                    MarketObservation.observed_on >= reliable_start,
                    MarketObservation.observed_on <= reliable_end,
                )
                .group_by(observation_year)
                .order_by(observation_year)
            )
        )
        annual_dates = {
            observed_on
            for _, first_date, last_date in annual_bounds
            for observed_on in (first_date, last_date)
            if observed_on is not None
        }
        if annual_dates:
            for annual_observation in session.scalars(
                select(MarketObservation).where(
                    MarketObservation.series_id == market_series.series_id,
                    MarketObservation.observed_on.in_(annual_dates),
                )
            ):
                market_observation_by_date[annual_observation.observed_on.isoformat()] = (
                    annual_observation
                )
        latest_observation = session.scalar(
            select(MarketObservation)
            .where(MarketObservation.series_id == market_series.series_id)
            .order_by(MarketObservation.observed_on.desc())
            .limit(1)
        )
        if latest_observation is not None:
            market_observation_by_date[latest_observation.observed_on.isoformat()] = (
                latest_observation
            )
        earliest_observation = session.scalar(
            select(MarketObservation)
            .where(MarketObservation.series_id == market_series.series_id)
            .order_by(MarketObservation.observed_on.asc())
            .limit(1)
        )
        if earliest_observation is not None:
            market_observation_by_date[earliest_observation.observed_on.isoformat()] = (
                earliest_observation
            )
        market_observations = sorted(
            market_observation_by_date.values(),
            key=lambda item: item.observed_on,
            reverse=True,
        )
        for market_observation in market_observations:
            market_evidence.append(
                {
                    "evidence_id": (
                        f"market:{market_series.series_id}:"
                        f"{market_observation.observed_on.isoformat()}"
                    ),
                    "category": market_series.category,
                    "series_id": market_series.series_id,
                    "name": market_series.name,
                    "observed_on": market_observation.observed_on.isoformat(),
                    "value": market_observation.value,
                    "unit": market_series.unit,
                    "source": market_series.source_name,
                    "source_url": market_series.source_url,
                }
            )
        if position % 5 == 0 or position == len(retained_market_series):
            _notify_research_progress(
                progress_callback,
                "evidence_market",
                12,
                f"正在加载行情与流动性序列 {position}/{len(retained_market_series)}",
            )
    _notify_research_progress(
        progress_callback,
        "evidence_financials",
        13,
        "市场序列已整理，正在核对公司季度财报与可比公司数据",
    )
    company_fact_statement = select(
        CompanyFinancialFact,
        CompanyProfile,
    ).join(
        CompanyProfile,
        CompanyProfile.ticker == CompanyFinancialFact.ticker,
    )
    if equity_sec_ticker:
        company_fact_statement = company_fact_statement.where(
            CompanyFinancialFact.ticker == equity_sec_ticker
        )
    elif equity_context is not None:
        company_fact_statement = company_fact_statement.where(
            CompanyFinancialFact.ticker == "__NO_SEC_TICKER__"
        )
    company_fact_rows = list(
        session.execute(
            company_fact_statement.order_by(
                CompanyFinancialFact.period_end.desc(),
                CompanyFinancialFact.filed_at.desc(),
            ).limit(160 if equity_sec_ticker else 80)
        )
    )
    if equity_sec_ticker:
        company_fact_rows.extend(
            session.execute(
                select(CompanyFinancialFact, CompanyProfile)
                .join(
                    CompanyProfile,
                    CompanyProfile.ticker == CompanyFinancialFact.ticker,
                )
                .where(CompanyFinancialFact.ticker != equity_sec_ticker)
                .order_by(
                    CompanyFinancialFact.period_end.desc(),
                    CompanyFinancialFact.filed_at.desc(),
                )
                .limit(40)
            )
        )
    company_fact_evidence = [
        {
            "evidence_id": (
                f"sec:{fact.ticker}:{fact.concept}:{fact.period_end.isoformat()}:"
                f"{fact.accession_number}"
            ),
            "category": "company_financial",
            "ticker": fact.ticker,
            "company": company.name,
            "sector": company.sector,
            "concept": fact.concept,
            "label": fact.label,
            "period_end": fact.period_end.isoformat(),
            "filed_at": fact.filed_at.isoformat(),
            "form": fact.form,
            "value": fact.value,
            "unit": fact.unit,
            "source": "SEC EDGAR Company Facts",
            "source_url": fact.source_url,
        }
        for fact, company in company_fact_rows
    ][:160]
    _notify_research_progress(
        progress_callback,
        "evidence_context",
        14,
        "公司财报已整理，正在计算数据覆盖率、经济周期和历史案例",
    )
    coverage_rows = _research_data_coverage_snapshot(session, settings=settings)
    _notify_research_progress(
        progress_callback,
        "evidence_context",
        14,
        "数据覆盖率已完成，正在计算经济周期模型",
    )
    economic_cycle = build_cycle_snapshot(session)
    economic_cycle_models = build_cycle_model_suite(session).model_dump(mode="json")
    _notify_research_progress(
        progress_callback,
        "evidence_context",
        14,
        "经济周期已完成，正在核对冲突暴露与已验证逻辑记忆",
    )
    conflict_hotspots = current_conflict_hotspots(session)
    verified_logic_memory = [
        memory.model_dump(mode="json")
        for memory in qualified_logic_memories(
            session,
            focus=research_terms,
            limit=6,
        )
    ]
    evidence_snapshot = {
        "generated_at": datetime.now(UTC).isoformat(),
        "question": question,
        "documents": document_evidence,
        "news_evidence_sequences": build_news_evidence_sequences(
            document_evidence,
            focus=research_terms,
        ),
        "forecasted_news_refs": forecasted_news_refs,
        "news_forecast_anchors": build_news_forecast_anchors(
            document_evidence,
            exclude_refs=set(forecasted_news_refs),
        ),
        "events": event_evidence,
        "economic_observations": economic_evidence,
        "market_observations": market_evidence,
        "company_financials": company_fact_evidence,
        "equity_research_context": equity_context,
        "derived_equity_evidence": derived_equity_evidence,
        "economic_cycle": economic_cycle,
        "economic_cycle_models": economic_cycle_models,
        "energy_observations": energy_evidence,
        "conflict_hotspots": conflict_hotspots,
        "data_coverage": coverage_rows,
        "prior_research_questions": prior_research_questions,
        "verified_logic_memory": verified_logic_memory,
        "research_event_table": research_event_table,
        "reliable_research_window": {
            "start": research_event_table.get("reliable_start"),
            "end": research_event_table.get("reliable_end"),
            "current_year_monitoring_only": True,
        },
        "preferred_research_period": preferred_research_period,
        "evidence_policy": (
            "Only listed evidence_id values may be cited; inference is not evidence."
        ),
    }
    evidence_snapshot["historical_anchors"] = _build_historical_anchors(
        evidence_snapshot,
        focus=research_terms,
        limit=48,
    )
    evidence_snapshot["episode_candidates"] = _build_episode_candidates(
        evidence_snapshot,
        focus=research_terms,
        limit=24,
    )
    _notify_research_progress(
        progress_callback,
        "evidence_snapshot_ready",
        15,
        "公司、新闻、市场、宏观和历史案例证据快照已完成",
    )
    return evidence_snapshot


def _research_data_coverage_snapshot(
    session: Session,
    *,
    settings: Settings,
) -> list[dict[str, Any]]:
    """Reuse slow global coverage counts inside one bounded report batch."""
    now = datetime.now(UTC)
    dialect = session.get_bind().dialect.name
    cached_at = _RESEARCH_COVERAGE_CACHE.get("generated_at")
    cached_rows = _RESEARCH_COVERAGE_CACHE.get("rows")
    if (
        dialect != "sqlite"
        and isinstance(cached_at, datetime)
        and now - cached_at <= RESEARCH_COVERAGE_CACHE_TTL
        and isinstance(cached_rows, list)
    ):
        return deepcopy(cached_rows)
    coverage = build_coverage_report(
        session,
        settings=settings,
        now=now,
        include_sources=False,
    )
    rows = [
        {
            "key": item.key,
            "provider": item.provider,
            "starts_at": item.starts_at,
            "ends_at": item.ends_at,
            "record_count": item.record_count,
            "completeness_ratio": item.completeness_ratio,
            "timestamp_ratio": item.timestamp_ratio,
            "content_ratio": item.content_ratio,
            "headline_only_count": item.headline_only_count,
            "status": item.status,
        }
        for item in coverage.datasets
    ]
    if dialect != "sqlite":
        _RESEARCH_COVERAGE_CACHE["generated_at"] = now
        _RESEARCH_COVERAGE_CACHE["rows"] = deepcopy(rows)
    return rows


def _prioritize_episode_evidence(
    evidence: dict[str, Any],
    *,
    plan: PlannedResearchQuestion,
) -> None:
    """Put exact-window evidence first while retaining long history as context."""
    required_refs = set([*plan.trigger_evidence_refs, *plan.outcome_evidence_refs])
    for section in (
        "documents",
        "events",
        "market_observations",
        "company_financials",
        "economic_observations",
        "energy_observations",
    ):
        values = evidence.get(section)
        if not isinstance(values, list):
            continue

        def episode_rank(item: Any) -> tuple[int, int, str]:
            if not isinstance(item, dict):
                return (0, 0, "")
            evidence_id = item.get("evidence_id")
            observed = _evidence_date(item)
            in_window = bool(observed and plan.episode_start <= observed <= plan.episode_end)
            return (
                2 if evidence_id in required_refs else 1 if in_window else 0,
                _text_relevance(
                    json.dumps(item, ensure_ascii=False),
                    plan.question,
                ),
                observed.isoformat() if observed else "",
            )

        values.sort(key=episode_rank, reverse=True)


def _call_local_research_model(
    *,
    question: str | None,
    mode: str,
    evidence: dict[str, Any],
    settings: Settings,
    transport: httpx.BaseTransport | None,
    max_attempts: int | None = None,
    timeout_seconds: float | None = None,
) -> ModelResearchResult:
    if settings.llm_provider == "mock":
        raise ResearchProviderError("local research requires a configured local model")
    compact_evidence = _compact_evidence(
        evidence,
        max_chars=max(4_000, settings.llm_max_input_chars - 1_500),
    )
    messages = [
        {"role": "system", "content": LOCAL_RESEARCH_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "mode": mode,
                    "question": question,
                    "required_autonomous_focus": evidence.get("required_autonomous_focus"),
                    "prohibited_prior_questions": evidence.get(
                        "prior_research_questions",
                        [],
                    ),
                    "retry_instruction": evidence.get("autonomous_retry_instruction"),
                    "evidence": compact_evidence,
                },
                ensure_ascii=False,
            ),
        },
    ]
    schema = _compatible_json_schema(ModelResearchResult)
    if settings.llm_provider == "ollama":
        endpoint = "/api/chat"
        payload = {
            "model": settings.llm_model,
            "messages": messages,
            "stream": False,
            "think": False,
            "format": schema,
            # The nine-dimension equity template plus citations can legitimately
            # exceed 8K tokens. Keep a finite ceiling, but leave enough room for the
            # model to close the strict JSON object instead of persisting a truncated
            # report. The one-hour HTTP deadline remains the outer workload bound.
            "options": {"temperature": 0.15, "num_predict": 12_288},
        }
    else:
        endpoint = "/v1/chat/completions"
        payload = {
            "model": settings.llm_model,
            "messages": messages,
            "stream": False,
            "temperature": 0.15,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "news_map_research",
                    "strict": True,
                    "schema": schema,
                },
            },
        }
    last_error: Exception | None = None
    for _ in range(max_attempts or settings.llm_max_attempts):
        attempt_started = time.monotonic()
        usage_raw = None
        usage_outcome = 'failed'
        try:
            with httpx.Client(
                base_url=str(settings.llm_base_url).rstrip("/"),
                timeout=timeout_seconds or settings.research_llm_timeout_seconds,
                transport=transport,
            ) as client:
                response = client.post(endpoint, json=payload)
                response.raise_for_status()
            data = response.json()
            usage_raw = data
            content = (
                data["message"]["content"]
                if settings.llm_provider == "ollama"
                else data["choices"][0]["message"]["content"]
            )
            result = _validated_research_content(content)
            sanitized = _sanitize_research_result(result, evidence=evidence)
            usage_outcome = 'validated_local_draft'
            return sanitized
        except httpx.TimeoutException as exc:
            # A timed-out generation can keep consuming the local runner briefly.
            # Reissuing the same large report immediately doubles compute without
            # adding a corrective instruction, so only validation failures retry.
            last_error = exc
            break
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
            ValidationError,
        ) as exc:
            last_error = exc
            payload["messages"] = [
                *messages,
                {
                    "role": "user",
                    "content": (
                        "The previous response failed strict validation. Return a "
                        "complete replacement JSON object matching the schema; do not "
                        "omit required arrays or the five equity dimensions. Validation "
                        f"error: {type(exc).__name__}: {str(exc)[:1_200]}"
                    ),
                },
            ]
        finally:
            raw_counts = usage_raw or {}
            evidence.setdefault('_reportUsage', {}).setdefault('localCalls', []).append({
                'model':settings.llm_model, 'outcome':usage_outcome,
                'at':datetime.now(UTC).isoformat(),
                'inputTokens':raw_counts.get('prompt_eval_count'),
                'outputTokens':raw_counts.get('eval_count'),
                'wallSeconds':round(time.monotonic()-attempt_started,3),
                'modelSeconds':raw_counts['total_duration']/1e9 if isinstance(raw_counts.get('total_duration'),int) else None,
                'unknownCountersAreNotZero':True,
            })
    detail = (
        f"{type(last_error).__name__}: {str(last_error)[:1_200]}"
        if last_error is not None
        else "unknown validation error"
    )
    raise ResearchProviderError(
        f"local model failed to return valid autonomous research: {detail}"
    ) from last_error


def _sanitize_research_result(
    result: ModelResearchResult,
    *,
    evidence: dict[str, Any],
) -> ModelResearchResult:
    """Enforce evidence and confidence rules after any local-model stage."""
    _remove_off_subject_company_documents(evidence)
    allowed_refs = _evidence_ids(evidence)
    allowed_refs -= {
        str(ref)
        for ref in evidence.get("rejected_company_document_refs", [])
        if isinstance(ref, str) and ref
    }
    episode_refs = _allowed_episode_evidence_refs(evidence)
    if episode_refs is not None:
        allowed_refs &= episode_refs
    headline_only_refs = headline_only_evidence_ids(evidence)
    for hypothesis in result.hypotheses:
        hypothesis.confidence = min(hypothesis.confidence, 0.75)
        for step in hypothesis.steps:
            step.confidence = min(step.confidence, 0.75)
            step.evidence_refs = [ref for ref in step.evidence_refs if ref in allowed_refs]
            if step.status in {"verified", "partially_supported"} and (
                not step.evidence_refs or set(step.evidence_refs).issubset(headline_only_refs)
            ):
                step.status = "evidence_missing"
                step.confidence = min(step.confidence, 0.25)
        unsupported_steps = sum(
            step.status in {"evidence_missing", "hypothesis"} for step in hypothesis.steps
        )
        if unsupported_steps:
            support_ratio = 1 - unsupported_steps / len(hypothesis.steps)
            hypothesis.confidence = min(
                hypothesis.confidence,
                max(0.25, 0.25 + support_ratio * 0.4),
            )
    for dimension in result.equity_dimensions:
        dimension.confidence = min(dimension.confidence, 0.75)
        dimension.evidence_refs = [ref for ref in dimension.evidence_refs if ref in allowed_refs]
        if not dimension.evidence_refs:
            dimension.signal = "unknown"
            dimension.confidence = min(dimension.confidence, 0.2)
    original_factor_count = len(result.factor_candidates)
    original_factor_ids = {factor.factor_id for factor in result.factor_candidates}
    for factor in result.factor_candidates:
        factor.evidence_refs = [
            ref
            for ref in factor.evidence_refs
            if ref in allowed_refs and ref not in headline_only_refs
        ]
        if not factor.evidence_refs:
            factor.confidence = min(factor.confidence, 0.1)
    result.factor_candidates = _retain_equity_subject_factors(
        result.factor_candidates,
        evidence=evidence,
    )
    removed_factor_count = original_factor_count - len(result.factor_candidates)
    if removed_factor_count:
        removed_factor_ids = original_factor_ids - {
            factor.factor_id for factor in result.factor_candidates
        }
        _record_report_repair(
            evidence,
            section="factor_candidates",
            reason="off_subject_equity_factors_removed",
            removed_count=removed_factor_count,
        )
        if result.factor_research is not None:
            factor_research = result.factor_research
            factor_research.factors = [
                factor
                for factor in factor_research.factors
                if factor.factor_id not in removed_factor_ids
            ]
            factor_research.nonlinear_links = [
                link
                for link in factor_research.nonlinear_links
                if not removed_factor_ids.intersection(link.input_factor_ids)
            ]
            factor_research.profit_validations = [
                validation
                for validation in factor_research.profit_validations
                if not removed_factor_ids.intersection(validation.factor_ids)
            ]
            factor_research.cross_sectional_validations = [
                validation
                for validation in factor_research.cross_sectional_validations
                if not removed_factor_ids.intersection(validation.factor_ids)
            ]
            _record_report_repair(
                evidence,
                section="factor_research",
                reason="off_subject_factor_research_entries_removed",
                removed_count=removed_factor_count,
            )
    if result.paper_report is not None:
        original_paper_refs = list(result.paper_report.evidence_refs)
        result.paper_report.evidence_refs = [
            ref
            for ref in original_paper_refs
            if ref in allowed_refs and ref not in headline_only_refs
        ]
        if set(original_paper_refs).intersection(headline_only_refs):
            result.paper_report.limitations = list(
                dict.fromkeys(
                    [
                        *result.paper_report.limitations,
                        (
                            "Headline-only discovery leads were excluded from the "
                            "paper's validating evidence."
                        ),
                    ]
                )
            )[:10]
    anchor_index = {
        str(item.get("evidence_id")): item
        for item in evidence.get("news_forecast_anchors") or []
        if isinstance(item, dict) and item.get("evidence_id")
    }
    retained_forecasts = []
    original_forecast_count = len(result.news_forecasts)
    for forecast in result.news_forecasts:
        anchor = anchor_index.get(forecast.anchor_evidence_ref)
        if anchor is None or anchor.get("evidence_tier") == "headline_only":
            continue
        if not _equity_forecast_is_subject_relevant(
            forecast,
            anchor=anchor,
            evidence=evidence,
        ):
            continue
        try:
            anchor_time = datetime.fromisoformat(str(anchor["published_at"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        forecast.as_of = anchor_time
        forecast.anchor_title = str(anchor.get("title") or forecast.anchor_title)[:500]
        forecast.confidence = min(forecast.confidence, 0.75)
        forecast.evaluation_mode = (
            "live_prospective"
            if anchor_time >= datetime.now(UTC) - timedelta(days=2)
            else "historical_walk_forward"
        )
        forecast.status = "unresolved"
        forecast.supporting_evidence_refs = []
        forecast.contradicting_evidence_refs = []
        forecast.validation_summary = None
        forecast.last_validated_at = None
        retained_forecasts.append(forecast)
    result.news_forecasts = retained_forecasts[:12]
    removed_forecast_count = original_forecast_count - len(result.news_forecasts)
    if removed_forecast_count:
        _record_report_repair(
            evidence,
            section="news_forecasts",
            reason="off_subject_or_unanchored_equity_forecasts_removed",
            removed_count=removed_forecast_count,
        )
    if not result.news_forecasts:
        result.news_forecasts = _fallback_news_forecasts(
            result,
            [
                item
                for item in anchor_index.values()
                if item.get("evidence_tier") != "headline_only"
            ],
        )
    if result.paper_report is None:
        result.paper_report = _fallback_academic_report(result)
    result.paper_report.evidence_refs = [
        ref
        for ref in result.paper_report.evidence_refs
        if ref in allowed_refs and ref not in headline_only_refs
    ]
    if evidence.get("equity_research_context"):
        result.equity_dimensions = _complete_equity_dimensions(
            result.equity_dimensions,
            evidence=evidence,
            allowed_refs=allowed_refs,
        )
        rebuilt_framework = _fallback_equity_framework(evidence)
        if result.equity_decision_framework != rebuilt_framework:
            repair_log = evidence.setdefault("local_report_repairs", [])
            repair = {
                "section": "equity_decision_framework",
                "reason": "valuation_and_timing_recomputed_from_point_in_time_evidence",
            }
            if isinstance(repair_log, list) and repair not in repair_log:
                repair_log.append(repair)
        result.equity_decision_framework = rebuilt_framework
        result.equity_decision_framework.not_personalized_advice = True
        _ensure_equity_subject_grounding(result, evidence=evidence)
    result.hypotheses = _deduplicate_research_hypotheses(result.hypotheses)
    return result


def _allowed_episode_evidence_refs(
    evidence: dict[str, Any],
) -> set[str] | None:
    episode = evidence.get("episode_window")
    if not isinstance(episode, dict):
        return None
    try:
        start = date.fromisoformat(str(episode["start"]))
        end = date.fromisoformat(str(episode["end"]))
    except (KeyError, ValueError):
        return None
    allowed = set(evidence.get("planned_question_evidence_refs") or [])
    allowed.update(evidence.get("historical_context_refs") or [])
    for values in evidence.values():
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict) or not isinstance(item.get("evidence_id"), str):
                continue
            observed = _evidence_date(item)
            if observed is not None and start <= observed <= end:
                allowed.add(item["evidence_id"])
                continue
            window_start = item.get("window_start")
            window_end = item.get("window_end")
            if isinstance(window_start, str) and isinstance(window_end, str):
                try:
                    item_start = date.fromisoformat(window_start[:10])
                    item_end = date.fromisoformat(window_end[:10])
                except ValueError:
                    continue
                if item_start <= end and item_end >= start:
                    allowed.add(item["evidence_id"])
    return allowed


def _validated_research_content(content: str) -> ModelResearchResult:
    """Normalize bounded formatting mistakes before strict semantic validation."""
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise TypeError("research response must be a JSON object")
    normalized = dict(payload)
    normalized["question"] = str(normalized.get("question") or "")[:1_000]
    normalized["summary"] = str(normalized.get("summary") or "")[:3_000]
    normalized["suggested_next_questions"] = _bounded_string_list(
        normalized.get("suggested_next_questions"),
        limit=8,
    )
    hypotheses = normalized.get("hypotheses")
    if isinstance(hypotheses, list):
        normalized["hypotheses"] = [
            _normalize_hypothesis(item) for item in hypotheses[:5] if isinstance(item, dict)
        ]
    dimensions = normalized.get("equity_dimensions")
    normalized["equity_dimensions"] = (
        [_normalize_equity_dimension(item) for item in dimensions[:5] if isinstance(item, dict)]
        if isinstance(dimensions, list)
        else []
    )
    factors = normalized.get("factor_candidates")
    normalized["factor_candidates"] = (
        [_normalize_factor_candidate(item) for item in factors[:16] if isinstance(item, dict)]
        if isinstance(factors, list)
        else []
    )
    # The model may propose factor hypotheses, but backtest results are produced
    # later by the deterministic factor engine. Never validate or retain model-
    # invented statistics in this system-owned section.
    normalized["factor_research"] = None
    framework = normalized.get("equity_decision_framework")
    if isinstance(framework, dict):
        bounded_framework = dict(framework)
        for key, limit in (
            ("valuation_scenarios", 8),
            ("entry_conditions", 8),
            ("invalidation_conditions", 8),
            ("monitoring_indicators", 12),
        ):
            bounded_framework[key] = _bounded_string_list(
                bounded_framework.get(key),
                limit=limit,
            )
        bounded_framework["not_personalized_advice"] = True
        normalized["equity_decision_framework"] = bounded_framework
    elif framework is not None:
        normalized["equity_decision_framework"] = None
    paper_report = normalized.get("paper_report")
    if isinstance(paper_report, dict):
        normalized["paper_report"] = _normalize_paper_report(paper_report)
    elif paper_report is not None:
        normalized["paper_report"] = None
    forecasts = normalized.get("news_forecasts")
    normalized["news_forecasts"] = (
        [_normalize_news_forecast(item) for item in forecasts[:12] if isinstance(item, dict)]
        if isinstance(forecasts, list)
        else []
    )
    return ModelResearchResult.model_validate(normalized)


def _normalize_paper_report(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    for key, limit in (
        ("title", 500),
        ("abstract", 3_000),
        ("methodology", 3_000),
        ("conclusion", 3_000),
    ):
        result[key] = str(result.get(key) or "Evidence insufficient")[:limit]
    for key, limit in (
        ("evidence_chain", 12),
        ("findings", 12),
        ("alternative_explanations", 10),
        ("limitations", 10),
        ("evidence_refs", 30),
    ):
        result[key] = _bounded_string_list(result.get(key), limit=limit)
    return result


def _normalize_news_forecast(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    anchor_ref = str(result.get("anchor_evidence_ref") or "")[:160]
    result["anchor_evidence_ref"] = anchor_ref
    result["forecast_id"] = str(result.get("forecast_id") or f"forecast:{anchor_ref or 'unknown'}")[
        :160
    ]
    result["anchor_title"] = str(result.get("anchor_title") or "Unknown news anchor")[:500]
    result["hypothesis"] = str(result.get("hypothesis") or "Evidence insufficient")[:1_500]
    result["expected_outcome"] = str(
        result.get("expected_outcome") or "A measurable outcome is required"
    )[:1_500]
    mechanisms = _bounded_string_list(result.get("mechanism_chain"), limit=8)
    while len(mechanisms) < 2:
        mechanisms.append("Intermediate mechanism requires validation")
    result["mechanism_chain"] = mechanisms
    falsifiers = _bounded_string_list(result.get("falsification_conditions"), limit=8)
    result["falsification_conditions"] = falsifiers or [
        "The expected outcome does not occur inside the stated horizon"
    ]
    result["confidence"] = _bounded_confidence(result.get("confidence"))
    try:
        result["horizon_days"] = min(max(int(result.get("horizon_days") or 30), 1), 365)
    except (TypeError, ValueError):
        result["horizon_days"] = 30
    result["status"] = "unresolved"
    result["supporting_evidence_refs"] = []
    result["contradicting_evidence_refs"] = []
    result["validation_summary"] = None
    result["last_validated_at"] = None
    return result


def _fallback_academic_report(
    result: ModelResearchResult,
) -> ModelAcademicResearchReport:
    evidence_refs = list(
        dict.fromkeys(
            ref
            for hypothesis in result.hypotheses
            for step in hypothesis.steps
            for ref in step.evidence_refs
        )
    )
    return ModelAcademicResearchReport(
        title=result.question[:500],
        abstract=result.summary,
        methodology=(
            "Local evidence retrieval, chronological news linking, explicit causal "
            "step decomposition and alternative-explanation review."
        ),
        evidence_chain=[
            step.label for hypothesis in result.hypotheses for step in hypothesis.steps
        ][:12],
        findings=[hypothesis.outcome for hypothesis in result.hypotheses][:12],
        alternative_explanations=[
            item for hypothesis in result.hypotheses for item in hypothesis.counterarguments
        ][:10],
        limitations=[item for hypothesis in result.hypotheses for item in hypothesis.evidence_gaps][
            :10
        ],
        conclusion=result.summary,
        evidence_refs=evidence_refs[:30],
    )


def _fallback_news_forecasts(
    result: ModelResearchResult,
    anchors: list[dict[str, Any]],
) -> list[ModelNewsForecast]:
    """Guarantee auditable low-confidence forecasts when the model omits them."""
    if not anchors or not result.hypotheses:
        return []
    hypothesis = result.hypotheses[0]
    mechanisms = [step.label for step in hypothesis.steps[1:-1]][:6]
    if len(mechanisms) < 2:
        mechanisms = [
            hypothesis.premise,
            "The proposed intermediate mechanism requires later evidence",
        ]
    forecasts: list[ModelNewsForecast] = []
    relevant_anchors = [
        anchor
        for anchor in anchors
        if _fallback_anchor_matches_result_subject(anchor, result=result)
    ]
    for index, anchor in enumerate(relevant_anchors[:4], start=1):
        try:
            as_of = datetime.fromisoformat(str(anchor["published_at"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        anchor_ref = str(anchor.get("evidence_id") or "")
        if not anchor_ref:
            continue
        forecasts.append(
            ModelNewsForecast(
                forecast_id=f"forecast:{anchor_ref}:{index}",
                anchor_evidence_ref=anchor_ref,
                anchor_title=str(anchor.get("title") or "News evidence")[:500],
                as_of=as_of,
                hypothesis=(
                    f"After this report, the proposed mechanism in “{hypothesis.title}” "
                    "may become observable; this is a low-confidence fallback hypothesis."
                ),
                mechanism_chain=mechanisms,
                expected_outcome=hypothesis.outcome,
                horizon_days=90,
                falsification_conditions=[
                    "The stated outcome does not occur within 90 days.",
                    "A stronger alternative explanation accounts for the observed move.",
                    "The proposed intermediate mechanism remains unobserved.",
                ],
                confidence=min(hypothesis.confidence, 0.3),
                evaluation_mode=(
                    "live_prospective"
                    if as_of >= datetime.now(UTC) - timedelta(days=2)
                    else "historical_walk_forward"
                ),
            )
        )
    return forecasts


def _normalize_hypothesis(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["title"] = str(result.get("title") or "")[:500]
    result["premise"] = str(result.get("premise") or "")[:1_000]
    result["outcome"] = str(result.get("outcome") or "")[:1_000]
    result["confidence"] = _bounded_confidence(result.get("confidence"))
    result["counterarguments"] = _bounded_string_list(result.get("counterarguments"), limit=8)
    result["evidence_gaps"] = _bounded_string_list(result.get("evidence_gaps"), limit=10)
    scope = result.get("scope")
    bounded_scope = dict(scope) if isinstance(scope, dict) else {}
    for key in (
        "companies",
        "sectors",
        "products",
        "supply_chain_inputs",
        "infrastructure",
        "policies",
        "geographies",
    ):
        bounded_scope[key] = _bounded_string_list(bounded_scope.get(key), limit=20)
    result["scope"] = bounded_scope
    steps = result.get("steps")
    normalized_steps: list[dict[str, Any]] = []
    if isinstance(steps, list):
        for sequence, step in enumerate(steps[:8], start=1):
            if not isinstance(step, dict):
                continue
            normalized_step = dict(step)
            normalized_step["sequence"] = sequence
            normalized_step["label"] = str(normalized_step.get("label") or "")[:600]
            if normalized_step.get("status") not in {
                "verified",
                "partially_supported",
                "evidence_missing",
                "hypothesis",
            }:
                normalized_step["status"] = "evidence_missing"
            normalized_step["confidence"] = _bounded_confidence(normalized_step.get("confidence"))
            normalized_step["evidence_refs"] = _bounded_string_list(
                normalized_step.get("evidence_refs"), limit=10
            )
            normalized_steps.append(normalized_step)
    result["steps"] = normalized_steps
    return result


def _normalize_equity_dimension(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["assessment"] = str(result.get("assessment") or "")[:1_500]
    result["confidence"] = _bounded_confidence(result.get("confidence"))
    result["evidence_refs"] = _bounded_string_list(result.get("evidence_refs"), limit=12)
    result["evidence_gaps"] = _bounded_string_list(result.get("evidence_gaps"), limit=10)
    if result.get("signal") not in {"bullish", "bearish", "mixed", "unknown"}:
        result["signal"] = "unknown"
    return result


def _normalize_factor_candidate(value: dict[str, Any]) -> dict[str, Any]:
    """Bound harmless model formatting drift without weakening factor limits."""
    result = dict(value)
    for key, limit in (("factor_id", 160), ("name", 300), ("hypothesis", 1_500)):
        result[key] = str(result.get(key) or "")[:limit]
    result["evidence_refs"] = _bounded_string_list(result.get("evidence_refs"), limit=20)
    result["confidence"] = _bounded_confidence(result.get("confidence"))
    try:
        result["lag_days"] = min(max(int(result.get("lag_days") or 0), 0), 365)
    except (TypeError, ValueError):
        result["lag_days"] = 0
    for key in ("training_p_value", "adjusted_q_value"):
        value = result.get(key)
        if value is None:
            continue
        try:
            result[key] = min(max(float(value), 0.0), 1.0)
        except (TypeError, ValueError):
            result[key] = None
    return result


def _bounded_string_list(value: object, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item)[:1_500] for item in value[:limit] if str(item).strip()]


def _bounded_confidence(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return 0.0
    try:
        return min(max(float(value), 0.0), 0.75)
    except (TypeError, ValueError):
        return 0.0


def _research_gap_queries(result: ModelResearchResult) -> list[str]:
    """Collect model-declared missing evidence for a bounded second search."""
    values = [
        gap.strip()
        for hypothesis in result.hypotheses
        for gap in hypothesis.evidence_gaps
        if gap.strip()
    ]
    values.extend(
        gap.strip()
        for dimension in result.equity_dimensions
        for gap in dimension.evidence_gaps
        if gap.strip()
    )
    return list(dict.fromkeys(values))[:20]


def _needs_evidence_revision(
    result: ModelResearchResult,
    *,
    evidence: dict[str, Any],
) -> bool:
    """Detect when available priority evidence was not actually mobilized."""
    cited_refs = {
        ref
        for hypothesis in result.hypotheses
        for step in hypothesis.steps
        for ref in step.evidence_refs
    }
    cited_refs.update(
        ref for dimension in result.equity_dimensions for ref in dimension.evidence_refs
    )
    planned_refs = set(evidence.get("planned_question_evidence_refs") or [])
    priority_refs = {
        item["evidence_id"]
        for item in evidence.get("priority_evidence") or []
        if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
    }
    if planned_refs and not (cited_refs & planned_refs):
        return True
    return not cited_refs and bool(priority_refs)


def _planned_result_needs_repair(
    result: ModelResearchResult,
    *,
    evidence: dict[str, Any],
) -> bool:
    """Reject an autonomous draft that ignores its selected retained episode."""
    planned_refs = set(evidence.get("planned_question_evidence_refs") or [])
    derived_refs = {
        item["evidence_id"]
        for item in evidence.get("market_window_statistics") or []
        if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
    }
    cited_refs = {
        ref
        for hypothesis in result.hypotheses
        for step in hypothesis.steps
        for ref in step.evidence_refs
    }
    relevant_citations = cited_refs & (planned_refs | derived_refs)
    narrative_or_mechanism_refs = {
        ref for ref in cited_refs if not ref.startswith(("market:", "derived:"))
    }
    claims_verified_intermediate_mechanism = any(
        len(hypothesis.steps) >= 3
        and any(
            step.status in {"verified", "partially_supported"} for step in hypothesis.steps[1:-1]
        )
        for hypothesis in result.hypotheses
    )
    question_terms = _question_subject_terms(result.question)
    answer_text = " ".join(
        [
            result.summary,
            *(hypothesis.title for hypothesis in result.hypotheses),
            *(hypothesis.premise for hypothesis in result.hypotheses),
            *(hypothesis.outcome for hypothesis in result.hypotheses),
        ]
    ).casefold()
    subject_hits = sum(term in answer_text for term in question_terms)
    required_subject_hits = min(2, len(question_terms))
    return (
        len(relevant_citations) < min(2, len(planned_refs | derived_refs))
        or (bool(derived_refs) and not (cited_refs & derived_refs))
        or (claims_verified_intermediate_mechanism and not narrative_or_mechanism_refs)
        or (required_subject_hits > 0 and subject_hits < required_subject_hits)
        or _planned_evidence_subject_mismatch(result, evidence=evidence)
    )


def _planned_evidence_subject_mismatch(
    result: ModelResearchResult,
    *,
    evidence: dict[str, Any],
) -> bool:
    """Require the draft to name both selected sides, not a prior episode."""
    episode = evidence.get("episode_window") or {}
    reference_groups = (
        list(episode.get("trigger_evidence_refs") or []),
        list(episode.get("outcome_evidence_refs") or []),
    )
    if not all(reference_groups):
        return False
    evidence_index = {
        str(item["evidence_id"]): item
        for values in evidence.values()
        if isinstance(values, list)
        for item in values
        if isinstance(item, dict) and item.get("evidence_id")
    }
    paper = result.paper_report
    narrative = " ".join(
        [
            result.summary,
            *(hypothesis.title for hypothesis in result.hypotheses),
            *(hypothesis.premise for hypothesis in result.hypotheses),
            *(hypothesis.outcome for hypothesis in result.hypotheses),
            *([paper.title, paper.abstract, paper.conclusion] if paper is not None else []),
        ]
    ).casefold()
    for references in reference_groups:
        labels = " ".join(
            _evidence_display_name(evidence_index[reference], fallback="")
            for reference in references
            if reference in evidence_index
        )
        terms = _evidence_subject_terms(labels)
        if terms and not any(term in narrative for term in terms):
            return True
    return False


def _evidence_subject_terms(value: str) -> list[str]:
    stopwords = {
        "price",
        "index",
        "monthly",
        "quarterly",
        "annual",
        "world",
        "total",
        "value",
        "series",
        "global",
        "united",
        "states",
        "价格",
        "指数",
        "月度",
        "季度",
        "年度",
        "全球",
    }
    values = re.findall(
        r"[a-z][a-z0-9.-]{3,}|[\u4e00-\u9fff]{2,8}",
        value.casefold(),
    )
    return list(dict.fromkeys(term for term in values if term not in stopwords))[:12]


def _grounded_episode_fallback(
    question: str,
    *,
    evidence: dict[str, Any],
) -> ModelResearchResult:
    """Return an auditable correlation-only result when the model drifts."""
    episode = evidence.get("episode_window") or {}
    trigger_refs = list(episode.get("trigger_evidence_refs") or [])
    outcome_refs = list(episode.get("outcome_evidence_refs") or [])
    evidence_index = {
        item["evidence_id"]: item
        for values in evidence.values()
        if isinstance(values, list)
        for item in values
        if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
    }
    trigger = evidence_index.get(trigger_refs[0], {}) if trigger_refs else {}
    outcome = evidence_index.get(outcome_refs[0], {}) if outcome_refs else {}
    trigger_window = _matching_window_evidence(trigger, evidence=evidence)
    outcome_window = _matching_window_evidence(outcome, evidence=evidence)
    trigger_label = _evidence_display_name(trigger, fallback="premise observation")
    outcome_label = _evidence_display_name(outcome, fallback="outcome observation")
    trigger_text = _measured_evidence_text(trigger, trigger_window)
    outcome_text = _measured_evidence_text(outcome, outcome_window)
    trigger_citations = list(
        dict.fromkeys(
            [
                *trigger_refs[:1],
                *([str(trigger_window["evidence_id"])] if trigger_window is not None else []),
            ]
        )
    )
    outcome_citations = list(
        dict.fromkeys(
            [
                *outcome_refs[:1],
                *([str(outcome_window["evidence_id"])] if outcome_window is not None else []),
            ]
        )
    )
    start = str(episode.get("start") or "the selected start")
    end = str(episode.get("end") or "the selected end")
    relationship_mode = str(episode.get("relationship_mode") or "mediated_linear")
    bridge_hypotheses = list(
        dict.fromkeys(
            str(value).strip()
            for value in episode.get("bridge_hypotheses") or []
            if str(value).strip()
        )
    )[:5]
    if relationship_mode == "nonlinear_exploratory" and not bridge_hypotheses:
        bridge_hypotheses = [
            "共同宏观状态、信用条件或风险偏好是否跨过传导阈值",
            "采购融资、库存或进口需求是否发生可测变化",
            "汇率、运费或贸易流量是否把变化传至最终价格",
        ]
    mechanism_labels = bridge_hypotheses or [
        (
            f"A transmission mechanism from {trigger_label} to {outcome_label} "
            "is proposed but is not established by the retained episode observations alone."
        )
    ]
    mechanism_steps = [
        {
            "sequence": index + 2,
            "label": label,
            "status": "evidence_missing",
            "confidence": 0.18,
            "evidence_refs": [],
        }
        for index, label in enumerate(mechanism_labels)
    ]
    outcome_sequence = len(mechanism_steps) + 2
    relationship_summary = (
        "The endpoint pairing is retained as a nonlinear exploratory hypothesis, "
        "while each named bridge is treated as a separate linear segment requiring evidence."
        if relationship_mode == "nonlinear_exploratory"
        else "The proposed linear transmission mechanism still requires intermediate evidence."
    )
    payload = {
        "question": question,
        "summary": (
            f"Within {start} to {end}, retained local data verify {trigger_text} "
            f"and {outcome_text}. These observations establish timing and measured "
            "co-movement only; they do not by themselves verify that the first "
            f"caused the second. {relationship_summary}"
        ),
        "hypotheses": [
            {
                "title": (
                    f"{trigger_label} and {outcome_label}: measured episode, "
                    "causal mechanism not yet verified"
                ),
                "premise": trigger_text,
                "outcome": outcome_text,
                "scope": {
                    "companies": [],
                    "sectors": list(
                        dict.fromkeys(
                            str(item.get("category"))
                            for item in (trigger, outcome)
                            if item.get("category")
                        )
                    ),
                    "products": [],
                    "supply_chain_inputs": [],
                    "infrastructure": [],
                    "policies": [],
                    "geographies": [],
                },
                "steps": [
                    {
                        "sequence": 1,
                        "label": trigger_text,
                        "status": "verified",
                        "confidence": 0.72,
                        "evidence_refs": trigger_citations,
                    },
                    *mechanism_steps,
                    {
                        "sequence": outcome_sequence,
                        "label": outcome_text,
                        "status": "verified",
                        "confidence": 0.72,
                        "evidence_refs": outcome_citations,
                    },
                ],
                "counterarguments": [
                    "Common macroeconomic conditions may move both measured series.",
                    "Reverse causality, expectations and omitted variables may explain the timing.",
                ],
                "evidence_gaps": [
                    "A dated external trigger or policy shock tied to the premise.",
                    (
                        "Intermediate transmission data and tests against stronger "
                        "alternative explanations."
                    ),
                ],
                "confidence": 0.32,
            }
        ],
        "suggested_next_questions": [
            f"Which dated shocks in {start} to {end} can identify the proposed mechanism?",
            (
                "Do comparable historical episodes show the same direction after "
                "controlling for alternatives?"
            ),
        ],
        "equity_dimensions": [],
        "equity_decision_framework": None,
    }
    return _sanitize_research_result(
        ModelResearchResult.model_validate(payload),
        evidence=evidence,
    )


def _matching_window_evidence(
    item: dict[str, Any],
    *,
    evidence: dict[str, Any],
) -> dict[str, Any] | None:
    series_id = item.get("series_id")
    if not series_id:
        return None
    return next(
        (
            candidate
            for candidate in evidence.get("market_window_statistics") or []
            if isinstance(candidate, dict) and candidate.get("series_id") == series_id
        ),
        None,
    )


def _evidence_display_name(item: dict[str, Any], *, fallback: str) -> str:
    name = str(
        item.get("name")
        or item.get("title")
        or item.get("indicator")
        or item.get("series_id")
        or fallback
    )
    country = str(item.get("country") or "").strip()
    if country and country.casefold() not in name.casefold():
        name = f"{country} — {name}"
    return name[:160]


def _measured_evidence_text(
    item: dict[str, Any],
    window: dict[str, Any] | None,
) -> str:
    name = _evidence_display_name(item, fallback="the retained observation")
    if window is not None:
        return (
            f"{name} moved from {window.get('first_value')} to "
            f"{window.get('last_value')} {window.get('unit') or ''} between "
            f"{window.get('window_start')} and {window.get('window_end')} "
            f"across {window.get('observation_count')} retained observations"
        ).strip()
    observed = (
        item.get("observed_on")
        or item.get("occurred_at")
        or item.get("period_end")
        or item.get("year")
        or "the selected period"
    )
    value = item.get("value")
    if value is not None:
        return f"{name} was {value} {item.get('unit') or ''} on {observed}".strip()
    return f"{name} was retained for {observed}"


def _question_subject_terms(question: str) -> list[str]:
    stopwords = {
        "whether",
        "through",
        "within",
        "during",
        "intermediate",
        "mechanism",
        "alternative",
        "explanation",
        "specific",
        "event",
        "window",
        "price",
        "是否",
        "通过",
        "可验证",
        "中间机制",
        "影响",
        "还是",
        "替代解释",
        "更强",
        "特定事件",
        "窗口",
    }
    values = re.findall(
        r"[a-z][a-z0-9.-]{3,}|[\u4e00-\u9fff]{2,8}",
        question.casefold(),
    )
    return list(dict.fromkeys(value for value in values if value not in stopwords))[:8]


def _complete_equity_dimensions(
    dimensions: list[ModelEquityResearchDimension],
    *,
    evidence: dict[str, Any],
    allowed_refs: set[str],
) -> list[ModelEquityResearchDimension]:
    """Keep grounded model work and deterministically rebuild numerical lenses."""
    order = (
        "fundamentals_valuation",
        "technicals_positioning",
        "macro_liquidity",
        "supply_chain_geopolitics",
        "technology_competition",
    )
    retained: dict[str, ModelEquityResearchDimension] = {}
    for item in dimensions:
        previous = retained.get(item.dimension)
        if previous is None or len(item.evidence_refs) > len(previous.evidence_refs):
            retained[item.dimension] = item
    references = {
        "fundamentals_valuation": _section_evidence_refs(
            evidence,
            categories={
                "derived_company_valuation",
                "derived_company_financial_trend",
                "product_operating_evidence",
            },
            sections=(),
            allowed_refs=allowed_refs,
        ),
        "technicals_positioning": _section_evidence_refs(
            evidence,
            categories={
                "derived_market_technical",
                "derived_institutional_positioning",
                "insider_transaction",
                "institutional_holding",
            },
            sections=(),
            allowed_refs=allowed_refs,
            limit=12,
        ),
        "macro_liquidity": _section_evidence_refs(
            evidence,
            categories={"derived_macro_sensitivity"},
            sections=("market_observations", "economic_observations"),
            allowed_refs=allowed_refs,
            preferred_market_series=("DGS2", "DGS10", "NFCI", "M2SL", "DTWEXBGS"),
            limit=6,
        ),
        "supply_chain_geopolitics": _section_evidence_refs(
            evidence,
            categories={
                "company_news_document",
                "verified_supply_chain_edge",
                "derived_supplier_factor",
                "supply_chain_site_exposure",
            },
            sections=(),
            allowed_refs=allowed_refs,
        ),
        "technology_competition": _section_evidence_refs(
            evidence,
            categories={"company_news_document", "product_operating_evidence"},
            sections=(),
            allowed_refs=allowed_refs,
        ),
    }
    site_refs = _section_evidence_refs(
        evidence,
        categories={"supply_chain_site_exposure"},
        sections=(),
        allowed_refs=allowed_refs,
        limit=6,
    )
    references["supply_chain_geopolitics"] = list(
        dict.fromkeys([*site_refs, *references["supply_chain_geopolitics"]])
    )[:10]
    completed: list[ModelEquityResearchDimension] = []
    repair_log = evidence.setdefault("local_report_repairs", [])
    if not isinstance(repair_log, list):
        repair_log = []
        evidence["local_report_repairs"] = repair_log
    for dimension_key in order:
        original = retained.get(dimension_key)
        derived_dimension = _evidence_derived_dimension(
            dimension_key,
            evidence=evidence,
            evidence_refs=references[dimension_key],
        )
        must_recompute = dimension_key in {
            "fundamentals_valuation",
            "technicals_positioning",
            "macro_liquidity",
            "supply_chain_geopolitics",
        } and bool(references[dimension_key])
        needs_grounding = original is None or _equity_dimension_needs_repair(
            original,
            evidence=evidence,
        )
        selected = derived_dimension if must_recompute or needs_grounding else original
        if selected is None:
            selected = derived_dimension
        completed.append(selected)
        reason: str | None
        if original is None:
            reason = "missing_dimension_reconstructed"
        elif must_recompute:
            reason = (
                "numerical_dimension_recomputed_from_point_in_time_evidence"
                if original.assessment != derived_dimension.assessment
                else None
            )
        elif needs_grounding:
            reason = "generic_or_unreferenced_dimension_replaced"
        else:
            reason = None
        if reason:
            repair = {"section": dimension_key, "reason": reason}
            if repair not in repair_log:
                repair_log.append(repair)
    return completed


def _equity_dimension_needs_repair(
    dimension: ModelEquityResearchDimension,
    *,
    evidence: dict[str, Any],
) -> bool:
    """Reject generic study templates and answers that drift away from the company."""
    context = evidence.get("equity_research_context")
    context = context if isinstance(context, dict) else {}
    ticker = str(context.get("ticker") or "").upper()
    company = str(context.get("company") or ticker)
    generic_markers = (
        "the intervention",
        "sample size",
        "control group",
        "study participants",
        "self-reported data",
        "socioeconomic status",
        "single location",
    )
    combined = " ".join([dimension.assessment, *dimension.evidence_gaps]).casefold()
    if any(marker in combined for marker in generic_markers):
        return True
    allowed_counterparties = (
        _allowed_equity_counterparty_tickers(evidence, ticker=ticker)
        if dimension.dimension == "supply_chain_geopolitics"
        else set()
    )
    if _foreign_equity_subjects(
        combined,
        ticker=ticker,
        allowed_tickers=allowed_counterparties,
    ):
        return True
    if _equity_industry_template_contamination(combined, ticker=ticker):
        return True
    if not dimension.evidence_refs:
        return True
    if dimension.dimension == "supply_chain_geopolitics":
        verified_supply_refs = {
            evidence_id
            for item in evidence.get("derived_equity_evidence", [])
            if isinstance(item, dict)
            and item.get("category")
            in {
                "verified_supply_chain_edge",
                "derived_supplier_factor",
                "supply_chain_site_exposure",
            }
            and isinstance((evidence_id := item.get("evidence_id")), str)
        }
        if verified_supply_refs and not verified_supply_refs.intersection(dimension.evidence_refs):
            return True
    return not _mentions_equity_subject(
        dimension.assessment,
        ticker=ticker,
        company=company,
    )


def _ensure_equity_subject_grounding(
    result: ModelResearchResult,
    *,
    evidence: dict[str, Any],
) -> None:
    """Replace generic model drift with an auditable company-specific fallback."""
    context = evidence.get("equity_research_context")
    if not isinstance(context, dict):
        return
    if context.get("market_region") == "china":
        _ensure_china_equity_subject_grounding(result, evidence=evidence)
        return
    ticker = str(context.get("ticker") or "").upper()
    company = str(context.get("company") or ticker)
    forecast_horizon = _equity_horizon_text(result.question)
    profile_value = context.get("reviewed_search_plan_not_evidence")
    profile = profile_value if isinstance(profile_value, dict) else {}
    if not profile:
        profile = COMPANY_RESEARCH_PROFILES.get(ticker, {})
    products = [str(item) for item in profile.get("products") or []]
    product_focus = "、".join(products[:4]) if products else "主要产品线和业务分部"
    sector_focus = str(context.get("industry") or context.get("sector") or "public equity")
    derived = [
        item for item in evidence.get("derived_equity_evidence", []) if isinstance(item, dict)
    ]
    by_category: dict[str, list[dict[str, Any]]] = {}
    for item in derived:
        by_category.setdefault(str(item.get("category") or ""), []).append(item)
    valuation_candidate = next(iter(by_category.get("derived_company_valuation", [])), None)
    valuation = (
        valuation_candidate
        if valuation_candidate is not None and not _valuation_anomalies(valuation_candidate)
        else None
    )
    technical = next(iter(by_category.get("derived_market_technical", [])), None)
    trend = next(iter(by_category.get("derived_company_financial_trend", [])), None)
    macro = next(iter(by_category.get("derived_macro_sensitivity", [])), None)
    company_documents = by_category.get("company_news_document", [])
    product_operating = by_category.get("product_operating_evidence", [])
    product_actuals = [
        item for item in product_operating if item.get("evidence_status") == "reported_actual"
    ]
    supply_chain_edges = by_category.get("verified_supply_chain_edge", [])
    supplier_factors = by_category.get("derived_supplier_factor", [])
    supply_chain_sites = by_category.get("supply_chain_site_exposure", [])
    supply_chain_total = int(
        context.get("verified_supply_chain_edge_total") or len(supply_chain_edges)
    )
    insider_transactions = by_category.get("insider_transaction", [])
    institutional_holdings = by_category.get("institutional_holding", [])

    valuation_ref = _item_evidence_ref(valuation)
    technical_ref = _item_evidence_ref(technical)
    trend_ref = _item_evidence_ref(trend)
    macro_ref = _item_evidence_ref(macro)
    company_refs = [
        ref for item in company_documents[:4] if (ref := _item_evidence_ref(item)) is not None
    ]
    product_refs = [
        ref for item in product_operating[:8] if (ref := _item_evidence_ref(item)) is not None
    ]
    supplier_refs = [
        ref
        for item in [
            *supply_chain_sites[:4],
            *supply_chain_edges[:4],
            *supplier_factors[:2],
        ]
        if (ref := _item_evidence_ref(item)) is not None
    ][:10]
    insider_refs = [
        ref for item in insider_transactions[:3] if (ref := _item_evidence_ref(item)) is not None
    ]
    institutional_refs = [
        ref for item in institutional_holdings[:2] if (ref := _item_evidence_ref(item)) is not None
    ]
    current_price = (
        valuation.get("price")
        if valuation
        else (technical.get("adjusted_close") if technical else None)
    )
    price_date = (
        valuation.get("price_observed_on")
        if valuation
        else (technical.get("observed_on") if technical else None)
    )
    scenario = (
        next(
            (
                item
                for item in (valuation.get("question_price_scenarios") or [])
                if isinstance(item, dict)
            ),
            None,
        )
        if valuation
        else None
    )
    target_price = scenario.get("target_price") if scenario else None
    target_context = ""
    if (
        isinstance(scenario, dict)
        and isinstance(target_price, (int, float))
        and isinstance(current_price, (int, float))
    ):
        multiple_label = (
            "TTM代理"
            if valuation and valuation.get("valuation_basis") == "ttm_proxy"
            else "最近财年静态"
        )
        relationship = (
            "低于当前价格的回撤观察情景" if target_price < current_price else "上涨估值情景"
        )
        target_context = (
            f" 用户提出的{_fmt_number(target_price)}美元是{relationship}，对应隐含市值"
            f"{_fmt_money(scenario.get('implied_market_cap'))}、{multiple_label}市销率"
            f"{_fmt_number(scenario.get('implied_price_to_sales'))}倍和{multiple_label}市盈率"
            f"{_fmt_number(scenario.get('implied_price_to_earnings'))}倍。"
        )
    grounded_summary = (
        f"截至{price_date or context.get('point_in_time_cutoff')}，{company}（{ticker}）"
        f"拆股调整收盘价为{_fmt_number(current_price)}美元。点时SEC财务、估值、技术面、"
        "机构持仓、内部人交易、宏观敏感度和公司全文只能支持条件化研究，不能保证继续上涨或给出"
        f"确定买点。{target_context}相关性测算不等于利率、汇率、市场资金或供应链因素已经"
        "造成股价变化；"
        + (
            f"已从年报原文纳入{len(product_operating)}条产品经营证据，其中"
            f"{len(product_actuals)}条是已报告结果；绝对单位ASP/销量、客户级合同与"
            "产品毛利仍需补证。"
            if product_operating
            else "合同与产品ASP/销量仍需补证。"
        )
        + (
            f" 当前数据库共有{supply_chain_total}条经来源审核的供应链关系；"
            f"本报告为控制上下文最多注入{len(supply_chain_edges)}条，"
            "这仍不能证明单项组件、数量、依赖程度或当前持续状态。"
            if supply_chain_edges
            else " 具体供应商与工厂风险仍需补证。"
        )
    )
    result.summary = grounded_summary
    suggestion_text = " ".join(result.suggested_next_questions)
    if (
        not _mentions_equity_subject(
            suggestion_text,
            ticker=ticker,
            company=company,
        )
        or _foreign_equity_subjects(
            suggestion_text,
            ticker=ticker,
        )
        or _equity_industry_template_contamination(
            suggestion_text.casefold(),
            ticker=ticker,
        )
    ):
        result.suggested_next_questions = [
            f"{company}（{ticker}）下一份财报的收入、毛利、自由现金流和指引是否足以消化当前静态估值？",
            f"{ticker}的{product_focus}在销量、价格、毛利、份额及需求结构上发生了什么可验证变化？",
            f"{ticker}价格重新站稳SMA50时，成交量、期权持仓和盈利预期是否同步改善？",
            f"利率、信用、美元与资金流的精确时序能否验证宏观环境对{ticker}估值的传导？",
            (
                "哪些已披露的Apple关键供应商、晶圆代工、组件、代工装配、港口与电力"
                "节点暴露于冲突或灾害？"
                if ticker == "AAPL"
                else f"哪些已披露的{company}工厂、供应商、能源和封装节点暴露于冲突或灾害？"
            ),
        ]

    hypothesis_text = " ".join(
        " ".join(
            [
                item.title,
                item.premise,
                item.outcome,
                *[step.label for step in item.steps],
                *item.counterarguments,
                *item.evidence_gaps,
            ]
        )
        for item in result.hypotheses
    )
    refresh_metadata = evidence.get("local_report_audit_refresh")
    point_in_time_chain_refresh = (
        isinstance(refresh_metadata, dict) and refresh_metadata.get("mode") == "refresh_and_audit"
    )
    product_chain_missing = bool(product_refs) and not any(
        set(product_refs).intersection(step.evidence_refs)
        for hypothesis in result.hypotheses
        for step in hypothesis.steps
    )
    hypotheses_invalid = (
        not _mentions_equity_subject(
            hypothesis_text,
            ticker=ticker,
            company=company,
        )
        or _equity_hypotheses_need_repair(
            result.hypotheses,
            target_price=target_price,
            current_price=current_price,
        )
        or bool(
            _foreign_equity_subjects(
                hypothesis_text,
                ticker=ticker,
                allowed_tickers=_allowed_equity_counterparty_tickers(
                    evidence,
                    ticker=ticker,
                ),
            )
        )
        or _equity_industry_template_contamination(
            hypothesis_text.casefold(),
            ticker=ticker,
        )
        or product_chain_missing
    )
    hypotheses_repaired = hypotheses_invalid or point_in_time_chain_refresh
    if hypotheses_repaired:
        repair_log = evidence.setdefault("local_report_repairs", [])
        hypothesis_repair = {
            "section": "hypotheses",
            "reason": (
                "product_operating_evidence_missing_from_main_chain"
                if product_chain_missing
                else "foreign_subject_or_generic_chain_replaced"
                if hypotheses_invalid
                else "point_in_time_chain_refs_refreshed"
            ),
        }
        if isinstance(repair_log, list) and hypothesis_repair not in repair_log:
            repair_log.append(hypothesis_repair)
        steps = [
            {
                "sequence": 1,
                "label": (
                    f"点时SEC数据与{price_date or '最新价格日'}估值共同界定{ticker}"
                    "当前基本面和静态倍数。"
                ),
                "status": "verified" if valuation_ref else "evidence_missing",
                "confidence": 0.68 if valuation_ref else 0.2,
                "evidence_refs": [ref for ref in (valuation_ref, trend_ref) if ref],
            },
            {
                "sequence": 2,
                "label": (
                    "SMA、RSI、MACD、KDJ、13F与Form 4描述已有价格和披露状态，"
                    "但不能单独预测下一阶段方向。"
                ),
                "status": "verified" if technical_ref else "evidence_missing",
                "confidence": 0.62 if technical_ref else 0.2,
                "evidence_refs": [
                    ref
                    for ref in (
                        technical_ref,
                        *insider_refs,
                        *institutional_refs,
                    )
                    if ref
                ],
            },
            {
                "sequence": 3,
                "label": (
                    f"2Y/10Y收益率、美元、VIX与指数对齐结果只测量{ticker}的历史敏感度，"
                    "尚未识别资金来源或政策因果。"
                ),
                "status": "partially_supported" if macro_ref else "evidence_missing",
                "confidence": 0.42 if macro_ref else 0.18,
                "evidence_refs": [macro_ref] if macro_ref else [],
            },
            {
                "sequence": 4,
                "label": (
                    (
                        f"年报原文已为{product_focus}提供{len(product_actuals)}条已报告的"
                        "收入、价格/销量、产品组合或合同经营事实；前瞻计划与风险披露已"
                        "分开标记，尚不能证明未来兑现。"
                    )
                    if product_operating
                    else (
                        f"{product_focus}的竞争、价格、需求与产品组合可能改变销量、毛利与"
                        "现金流，但必须由产品和合同证据逐项验证。"
                    )
                ),
                "status": "verified"
                if len(product_actuals) >= 4
                else "partially_supported"
                if product_refs or company_refs
                else "evidence_missing",
                "confidence": 0.64
                if len(product_actuals) >= 4
                else 0.45
                if product_refs
                else 0.38
                if company_refs
                else 0.18,
                "evidence_refs": list(dict.fromkeys([*product_refs, *company_refs]))[:8],
            },
            {
                "sequence": 5,
                "label": (
                    (
                        "半导体、显示、相机和电池组件、代工装配、港口、电力、冲突与灾害"
                        "只有映射到具体供应商和设施后，才能估算对产品发布、交付和利润率的影响。"
                    )
                    if ticker == "AAPL"
                    else (
                        "材料、设备、电力、水、封装、冲突与灾害只有映射到具体工厂和产能"
                        "后，才能估算供应中断对交付和利润率的影响。"
                    )
                ),
                "status": "partially_supported" if supply_chain_edges else "hypothesis",
                "confidence": (
                    0.5
                    if supply_chain_edges and supplier_factors
                    else 0.38
                    if supply_chain_edges
                    else 0.2
                ),
                "evidence_refs": supplier_refs,
            },
            {
                "sequence": 6,
                "label": (
                    f"{ticker}{forecast_horizon}价格取决于上述盈利、估值、技术、流动性与供应链条件"
                    "的联合状态；当前证据不足以给出保证性方向。"
                ),
                "status": "hypothesis",
                "confidence": 0.25,
                "evidence_refs": [],
            },
        ]
        result.hypotheses = [
            ModelResearchHypothesis.model_validate(
                {
                    "title": f"{company}（{ticker}）多因子条件链",
                    "premise": (
                        f"{ticker}的已观测价格、点时财务与宏观敏感度可以界定当前状态，"
                        "但不直接证明未来上涨。"
                    ),
                    "outcome": (
                        "只有盈利兑现、估值消化、技术状态改善且供应链与流动性反证未"
                        "触发时，继续上涨假设才得到增强。"
                    ),
                    "scope": {
                        "companies": [company],
                        "sectors": [sector_focus],
                        "products": list(profile.get("products") or [])[:20],
                        "supply_chain_inputs": list(
                            profile.get("supply_chain_inputs_to_verify") or []
                        )[:20],
                        "infrastructure": [
                            "major production facilities",
                            "critical suppliers",
                            "electricity",
                            "transport and logistics",
                        ],
                        "policies": [
                            "trade and export controls",
                            "industry policy",
                            "monetary policy",
                        ],
                        "geographies": list(profile.get("geographies_to_verify") or [])[:20],
                    },
                    "steps": steps,
                    "counterarguments": [
                        f"{product_focus}的需求可能强于历史周期并支持更高的远期盈利。",
                        "估值压缩可能由盈利上修抵消，而非只由利率决定。",
                        "竞争者供给纪律、库存周期或客户需求可能改变价格传导。",
                        "大盘、财报预期和地缘事件可能比单一宏观因子更强。",
                    ],
                    "evidence_gaps": [
                        (
                            f"{product_focus}仍缺绝对单位销量/ASP、产品毛利、份额和客户级"
                            "订单；年报中的相对变化不能替代这些数据。"
                            if product_operating
                            else f"{product_focus}的产品级销量、价格、份额、产能与毛利。"
                        ),
                        "客户合同、需求节奏、竞争者投入与关键组件供给约束。",
                        "具体供应商—工厂—产能—港口—电力—灾害空间映射。",
                        "利率、汇率、融资成本、市场预期和实际资金流的时间对齐。",
                    ],
                    "confidence": 0.42,
                }
            )
        ]
        # Remove only model-derived subject drift. Independent market and
        # cross-sectional backtests remain valid because their dated inputs and
        # factor definitions do not change when prose in the causal chain is repaired.
        result.factor_candidates = [
            factor
            for factor in result.factor_candidates
            if not _foreign_equity_subjects(
                f"{factor.name} {factor.hypothesis}",
                ticker=ticker,
                allowed_tickers=_allowed_equity_counterparty_tickers(
                    evidence,
                    ticker=ticker,
                ),
            )
        ]
        if result.factor_research is not None:
            factor_research = result.factor_research
            removed_ids = {
                factor.factor_id
                for factor in factor_research.factors
                if factor.factor_id.startswith("ai:")
                or _equity_industry_template_contamination(
                    f"{factor.name} {factor.hypothesis}".casefold(),
                    ticker=ticker,
                )
            }
            if removed_ids:
                factor_research.factors = [
                    factor
                    for factor in factor_research.factors
                    if factor.factor_id not in removed_ids
                ]
                factor_research.nonlinear_links = [
                    link
                    for link in factor_research.nonlinear_links
                    if not removed_ids.intersection(link.input_factor_ids)
                ]
                factor_research.profit_validations = [
                    validation
                    for validation in factor_research.profit_validations
                    if not removed_ids.intersection(validation.factor_ids)
                ]
                factor_research.cross_sectional_validations = [
                    validation
                    for validation in factor_research.cross_sectional_validations
                    if not removed_ids.intersection(validation.factor_ids)
                ]
                _record_report_repair(
                    evidence,
                    section="factor_research",
                    reason="model_derived_factors_removed_after_subject_chain_repair",
                    removed_count=len(removed_ids),
                )

    paper = result.paper_report
    paper_grounded = bool(
        paper
        and _mentions_equity_subject(
            f"{paper.title} {paper.abstract}",
            ticker=ticker,
            company=company,
        )
    )
    if not paper_grounded or hypotheses_repaired or bool(evidence.get("local_report_repairs")):
        hypothesis = result.hypotheses[0]
        limitations = list(
            dict.fromkeys(
                gap for dimension in result.equity_dimensions for gap in dimension.evidence_gaps
            )
        )[:10]
        paper_refs = list(
            dict.fromkeys(
                ref for dimension in result.equity_dimensions for ref in dimension.evidence_refs
            )
        )[:30]
        result.paper_report = ModelAcademicResearchReport(
            title=f"{company}（{ticker}）五维点时证据研究",
            abstract=result.summary,
            methodology=(
                "以价格截止日为信息边界，联合SEC申报、拆股调整价格、13F、Form 4 XML、FRED宏观"
                "序列和本地全文；区分事实、派生计算、描述性相关与尚未验证的因果链。"
            ),
            evidence_chain=[step.label for step in hypothesis.steps],
            findings=[
                f"{dimension.dimension}: {dimension.signal} — {dimension.assessment[:700]}"
                for dimension in result.equity_dimensions
            ],
            alternative_explanations=hypothesis.counterarguments,
            limitations=limitations,
            conclusion=result.summary,
            evidence_refs=paper_refs,
        )


def _ensure_china_equity_subject_grounding(
    result: ModelResearchResult,
    *,
    evidence: dict[str, Any],
) -> None:
    """Keep A-share output inside the retained market/factor evidence boundary."""
    context = evidence["equity_research_context"]
    ticker = str(context.get("ticker") or "")
    company = str(context.get("company") or ticker)
    forecast_horizon = _equity_horizon_text(result.question)
    derived = [
        item for item in evidence.get("derived_equity_evidence", []) if isinstance(item, dict)
    ]
    by_category = {
        category: [item for item in derived if item.get("category") == category]
        for category in {
            "derived_company_valuation",
            "derived_market_technical",
            "derived_macro_sensitivity",
            "company_news_document",
        }
    }
    valuation = next(iter(by_category["derived_company_valuation"]), None)
    technical = next(iter(by_category["derived_market_technical"]), None)
    macro = next(iter(by_category["derived_macro_sensitivity"]), None)
    valuation_ref = _item_evidence_ref(valuation)
    technical_ref = _item_evidence_ref(technical)
    macro_ref = _item_evidence_ref(macro)
    news_refs = [
        ref
        for item in by_category["company_news_document"][:4]
        if (ref := _item_evidence_ref(item)) is not None
    ]
    cutoff = context.get("point_in_time_cutoff")
    result.summary = (
        f"截至{cutoff}，{company}（{ticker}）的本地证据支持行情、估值快照、技术面"
        "和描述性宏观敏感度审计，但尚不支持完整公司基本面或供应链因果结论。"
        f"最新前复权收盘价为{_fmt_number(valuation.get('price') if valuation else None)}元，"
        "快照PE为"
        f"{_fmt_number(valuation.get('trailing_price_to_earnings') if valuation else None)}倍、"
        f"PB为{_fmt_number(valuation.get('price_to_book') if valuation else None)}倍。"
        "由于交易所公告全文、原始财报可得时间、合同/产销、股东资金和工厂供应链"
        "尚未结构化接入，系统不得据此给出确定目标价、买点或盈利承诺。"
    )
    steps = [
        ModelResearchStep(
            sequence=1,
            label=f"BaoStock快照和价格序列界定{company}（{ticker}）当前市场状态。",
            status="verified" if valuation_ref else "evidence_missing",
            confidence=0.62 if valuation_ref else 0.18,
            evidence_refs=[valuation_ref] if valuation_ref else [],
        ),
        ModelResearchStep(
            sequence=2,
            label="均线、RSI、MACD与KDJ仅描述历史价格形态，不能单独预测未来方向。",
            status="verified" if technical_ref else "evidence_missing",
            confidence=0.58 if technical_ref else 0.18,
            evidence_refs=[technical_ref] if technical_ref else [],
        ),
        ModelResearchStep(
            sequence=3,
            label="宏观序列对齐只能测量同期相关，不能证明流动性变化造成个股涨跌。",
            status="partially_supported" if macro_ref else "evidence_missing",
            confidence=0.35 if macro_ref else 0.15,
            evidence_refs=[macro_ref] if macro_ref else [],
        ),
        ModelResearchStep(
            sequence=4,
            label="新闻正文可提供公司事件线索，但合同、财务或产能主张仍需交易所公告原文验证。",
            status="partially_supported" if news_refs else "evidence_missing",
            confidence=0.32 if news_refs else 0.15,
            evidence_refs=news_refs,
        ),
        ModelResearchStep(
            sequence=5,
            label=f"公告全文、资金流和设施供应链补齐后，才能重新检验{forecast_horizon}方向。",
            status="hypothesis",
            confidence=0.18,
            evidence_refs=[],
        ),
    ]
    missing = list(context.get("required_missing_evidence") or [])[:10]
    result.hypotheses = [
        ModelResearchHypothesis(
            title=f"{company}（{ticker}）A股市场因子与证据缺口链",
            premise="本地已保存价格、估值快照和部分公司新闻。",
            outcome="当前只形成可审计的条件框架，不形成确定交易结论。",
            scope=ModelResearchScope(
                companies=[company],
                sectors=[str(context.get("sector") or "A-share")],
                products=[],
                supply_chain_inputs=[],
                infrastructure=[],
                policies=["exchange disclosure", "monetary policy"],
                geographies=["China"],
            ),
            steps=steps,
            counterarguments=[
                "快照估值可能因盈利周期和会计口径快速变化。",
                "公司公告、行业政策或资金流可能比历史技术指标更强。",
                "当前行业龙头分是截面排名，不代表历史稳定领先。",
            ],
            evidence_gaps=missing,
            confidence=0.35,
        )
    ]
    result.suggested_next_questions = [
        f"{company}（{ticker}）最近四期交易所财报的收入、利润、现金流和可得时间是什么？",
        f"{company}有哪些经公告验证的订单、合同、产销量和价格变化？",
        f"{ticker}的股东、机构和北向资金变化是否有原始披露或可审计序列？",
        f"{company}的工厂、关键原料、港口、电力与灾害风险如何映射？",
    ]
    hypothesis = result.hypotheses[0]
    paper_refs = list(
        dict.fromkeys(
            ref for dimension in result.equity_dimensions for ref in dimension.evidence_refs
        )
    )[:30]
    result.paper_report = ModelAcademicResearchReport(
        title=f"{company}（{ticker}）A股市场因子与证据缺口审计",
        abstract=result.summary,
        methodology=(
            "以本地价格截止日为边界，使用BaoStock前复权收盘价、截面财务/估值快照、"
            "宏观对齐和保留的新闻正文；明确区分市场观测、派生计算与尚未接入的公告证据。"
        ),
        evidence_chain=[step.label for step in hypothesis.steps],
        findings=[
            f"{dimension.dimension}: {dimension.signal} — {dimension.assessment[:700]}"
            for dimension in result.equity_dimensions
        ],
        alternative_explanations=hypothesis.counterarguments,
        limitations=missing,
        conclusion=result.summary,
        evidence_refs=paper_refs,
    )


def _item_evidence_ref(item: dict[str, Any] | None) -> str | None:
    if not isinstance(item, dict):
        return None
    value = item.get("evidence_id")
    return str(value) if isinstance(value, str) else None


def _mentions_equity_subject(text: str, *, ticker: str, company: str) -> bool:
    normalized = text.casefold()
    ticker_pattern = rf"(?<![a-z0-9]){re.escape(ticker.casefold())}(?![a-z0-9])"
    company_token = next(
        (token for token in re.findall(r"[a-z0-9]+", company.casefold()) if len(token) >= 4),
        "",
    )
    alias_hit = any(
        _equity_alias_mentioned(text, alias) for alias in COMPANY_ALIASES.get(ticker, ())
    )
    return (
        bool(re.search(ticker_pattern, normalized))
        or bool(company_token and company_token in normalized)
        or alias_hit
    )


def _equity_alias_mentioned(text: str, alias: str) -> bool:
    normalized = text.casefold()
    token = alias.casefold().strip()
    if not token:
        return False
    if re.fullmatch(r"[a-z0-9.]+", token):
        return bool(re.search(rf"(?<![a-z0-9.]){re.escape(token)}(?![a-z0-9.])", normalized))
    return token in normalized


def _remove_off_subject_company_documents(evidence: dict[str, Any]) -> None:
    """Remove incidental company-name matches before they can support a report."""
    context = evidence.get("equity_research_context")
    if not isinstance(context, dict):
        return
    ticker = str(context.get("ticker") or "").upper()
    company = str(context.get("company") or ticker)
    derived = evidence.get("derived_equity_evidence")
    if not ticker or not isinstance(derived, list):
        return
    retained: list[Any] = []
    rejected_refs: list[str] = []
    for item in derived:
        if not isinstance(item, dict) or item.get("category") != "company_news_document":
            retained.append(item)
            continue
        subject_text = f"{item.get('title') or ''} {(item.get('excerpt') or '')[:1_500]}"
        if _mentions_equity_subject(subject_text, ticker=ticker, company=company):
            retained.append(item)
            continue
        if ref := _item_evidence_ref(item):
            rejected_refs.append(ref)
    if not rejected_refs:
        return
    evidence["derived_equity_evidence"] = retained
    existing = evidence.get("rejected_company_document_refs")
    existing = existing if isinstance(existing, list) else []
    evidence["rejected_company_document_refs"] = list(dict.fromkeys([*existing, *rejected_refs]))
    _record_report_repair(
        evidence,
        section="company_news_documents",
        reason="off_subject_company_documents_removed",
        removed_count=len(rejected_refs),
    )


def _allowed_equity_counterparty_tickers(
    evidence: dict[str, Any],
    *,
    ticker: str,
) -> set[str]:
    """Allow issuer-disclosed counterparties without masking unrelated drift."""
    allowed: set[str] = set()
    for item in evidence.get("derived_equity_evidence", []):
        if not isinstance(item, dict):
            continue
        category = item.get("category")
        if category == "verified_supply_chain_edge":
            candidate = item.get("related_ticker")
        elif category == "derived_supplier_factor":
            series_id = str(item.get("supplier_series_id") or "")
            candidate = series_id.removeprefix("EQ:") if series_id.startswith("EQ:") else None
            for component in item.get("basket_components") or []:
                if not isinstance(component, dict):
                    continue
                component_id = str(component.get("series_id") or "")
                if component_id.startswith("EQ:"):
                    component_ticker = component_id.removeprefix("EQ:").upper()
                    if component_ticker and component_ticker != ticker.upper():
                        allowed.add(component_ticker)
        else:
            continue
        normalized = str(candidate or "").upper()
        if normalized and normalized != ticker.upper():
            allowed.add(normalized)
    return allowed


def _foreign_equity_subjects(
    text: str,
    *,
    ticker: str,
    allowed_tickers: set[str] | None = None,
) -> list[str]:
    """Return explicit aliases for another covered issuer found in company output."""
    normalized = text.casefold()
    allowed = {item.upper() for item in (allowed_tickers or set())}
    found: list[str] = []
    for other_ticker, aliases in COMPANY_ALIASES.items():
        if other_ticker == ticker or other_ticker in allowed:
            continue
        for alias in aliases:
            token = alias.casefold()
            if re.fullmatch(r"[a-z0-9.]+", token):
                matched = bool(
                    re.search(
                        rf"(?<![a-z0-9.]){re.escape(token)}(?![a-z0-9.])",
                        normalized,
                    )
                )
            else:
                matched = token in normalized
            if matched:
                found.append(other_ticker)
                break
    return list(dict.fromkeys(found))


def _record_report_repair(
    evidence: dict[str, Any],
    *,
    section: str,
    reason: str,
    removed_count: int | None = None,
) -> None:
    repairs = evidence.setdefault("local_report_repairs", [])
    if not isinstance(repairs, list):
        repairs = []
        evidence["local_report_repairs"] = repairs
    repair: dict[str, Any] = {"section": section, "reason": reason}
    if removed_count is not None:
        repair["removed_count"] = removed_count
    if repair not in repairs:
        repairs.append(repair)


def _equity_context(evidence: dict[str, Any] | None) -> tuple[str, str]:
    context = evidence.get("equity_research_context") if isinstance(evidence, dict) else None
    context = context if isinstance(context, dict) else {}
    ticker = str(context.get("ticker") or "").upper()
    return ticker, str(context.get("company") or ticker)


def _evidence_ref_matches_equity_subject(
    evidence_ref: str,
    *,
    evidence: dict[str, Any],
    ticker: str,
    company: str,
) -> bool:
    if ticker and re.search(
        rf"(?<![a-z0-9]){re.escape(ticker.casefold())}(?![a-z0-9])",
        evidence_ref.casefold(),
    ):
        return True
    for value in evidence.values():
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict) or item.get("evidence_id") != evidence_ref:
                continue
            text = " ".join(
                str(item.get(key) or "")
                for key in ("ticker", "series_id", "company", "name", "title", "excerpt")
            )
            return _mentions_equity_subject(text, ticker=ticker, company=company)
    return False


def _retain_equity_subject_factors(
    factors: list[Any],
    *,
    evidence: dict[str, Any],
) -> list[Any]:
    ticker, company = _equity_context(evidence)
    if not ticker:
        return factors
    retained = []
    for factor in factors:
        text = f"{factor.name} {factor.hypothesis}"
        direct_match = _mentions_equity_subject(text, ticker=ticker, company=company)
        cited_match = any(
            _evidence_ref_matches_equity_subject(
                ref,
                evidence=evidence,
                ticker=ticker,
                company=company,
            )
            for ref in factor.evidence_refs
        )
        if (direct_match or cited_match) and not _equity_industry_template_contamination(
            text.casefold(),
            ticker=ticker,
        ):
            retained.append(factor)
    return retained


def _anchor_mentions_equity_subject(
    anchor: dict[str, Any],
    *,
    ticker: str,
    company: str,
) -> bool:
    text = " ".join(str(anchor.get(key) or "") for key in ("title", "excerpt", "summary", "body"))
    return _mentions_equity_subject(text, ticker=ticker, company=company)


def _fallback_anchor_matches_result_subject(
    anchor: dict[str, Any],
    *,
    result: ModelResearchResult,
) -> bool:
    combined = " ".join((result.question, result.summary))
    for ticker, aliases in COMPANY_ALIASES.items():
        company = max(aliases, key=len)
        if _mentions_equity_subject(combined, ticker=ticker, company=company):
            return _anchor_mentions_equity_subject(
                anchor,
                ticker=ticker,
                company=company,
            )
    return True


def _equity_forecast_is_subject_relevant(
    forecast: ModelNewsForecast,
    *,
    anchor: dict[str, Any],
    evidence: dict[str, Any],
) -> bool:
    ticker, company = _equity_context(evidence)
    if not ticker:
        return True
    forecast_text = " ".join(
        [
            forecast.anchor_title,
            forecast.hypothesis,
            forecast.expected_outcome,
            *forecast.mechanism_chain,
            *forecast.falsification_conditions,
        ]
    )
    return (
        _anchor_mentions_equity_subject(anchor, ticker=ticker, company=company)
        and _mentions_equity_subject(forecast_text, ticker=ticker, company=company)
        and not _equity_industry_template_contamination(forecast_text.casefold(), ticker=ticker)
    )


def _equity_industry_template_contamination(text: str, *, ticker: str) -> bool:
    if ticker != "AAPL":
        return False
    markers = (
        "ev manufacturer",
        "electric vehicle manufacturer",
        "中国电动车",
        "中国新能源汽车",
        "铜价上涨降低",
        "客户认证",
        "apple inc.工厂、供应商、能源和封装节点",
        "晶圆产出",
        "新型存储和系统架构",
        "良率、成本、客户认证、专利、先进封装",
    )
    return any(marker in text for marker in markers)


def _equity_hypotheses_need_repair(
    hypotheses: list[ModelResearchHypothesis],
    *,
    target_price: Any,
    current_price: Any,
) -> bool:
    generic_labels = {
        "财务数据",
        "市场指标",
        "行业竞争",
        "供应链风险",
        "宏观经济环境",
    }
    if any(
        step.label.strip() in generic_labels or len(step.label.strip()) < 8
        for hypothesis in hypotheses
        for step in hypothesis.steps
    ):
        return True
    combined = " ".join(
        f"{item.title} {item.premise} {item.outcome}" for item in hypotheses
    ).casefold()
    return bool(
        isinstance(target_price, (int, float))
        and isinstance(current_price, (int, float))
        and target_price < current_price
        and _fmt_number(target_price).replace(",", "") in combined.replace(",", "")
        and any(term in combined for term in ("估值目标", "上涨目标", "upside target"))
    )


def _equity_framework_is_substantive(
    framework: ModelEquityDecisionFramework,
) -> bool:
    text_values = [
        framework.current_price_context,
        *framework.valuation_scenarios,
        *framework.entry_conditions,
        *framework.invalidation_conditions,
    ]
    placeholder_values = {
        "current_price",
        "market_stability",
        "industry_growth",
        "company_profitability",
        "market_volatility",
        "industry_competition",
        "supply_chain_disruption",
        "macroeconomic_environment",
        "target_price",
        "retracement_level",
        "unsupported_number",
    }
    return (
        len(framework.current_price_context) >= 80
        and bool(framework.entry_conditions)
        and bool(framework.invalidation_conditions)
        and not any(value.strip().casefold() in placeholder_values for value in text_values)
    )


def _section_evidence_refs(
    evidence: dict[str, Any],
    *,
    categories: set[str],
    sections: tuple[str, ...],
    allowed_refs: set[str],
    limit: int = 5,
    preferred_market_series: tuple[str, ...] = (),
) -> list[str]:
    refs: list[str] = []
    for item in evidence.get("derived_equity_evidence", []):
        if not isinstance(item, dict) or item.get("category") not in categories:
            continue
        evidence_id = item.get("evidence_id")
        if isinstance(evidence_id, str) and evidence_id in allowed_refs:
            refs.append(evidence_id)
    for section in sections:
        section_items = evidence.get(section, [])
        if section == "market_observations" and preferred_market_series:
            latest_by_series: dict[str, dict[str, Any]] = {}
            for item in section_items:
                if not isinstance(item, dict):
                    continue
                series_id = str(item.get("series_id") or "")
                if series_id not in preferred_market_series:
                    continue
                previous = latest_by_series.get(series_id)
                if previous is None or str(item.get("observed_on") or "") > str(
                    previous.get("observed_on") or ""
                ):
                    latest_by_series[series_id] = item
            section_items = [
                latest_by_series[series_id]
                for series_id in preferred_market_series
                if series_id in latest_by_series
            ]
        for item in section_items:
            if not isinstance(item, dict):
                continue
            if (
                section == "market_observations"
                and preferred_market_series
                and item.get("series_id") not in preferred_market_series
            ):
                continue
            evidence_id = item.get("evidence_id")
            if isinstance(evidence_id, str) and evidence_id in allowed_refs:
                refs.append(evidence_id)
            if len(dict.fromkeys(refs)) >= limit:
                break
    return list(dict.fromkeys(refs))[:limit]


def _evidence_derived_dimension(
    dimension_key: str,
    *,
    evidence: dict[str, Any],
    evidence_refs: list[str],
) -> ModelEquityResearchDimension:
    """Turn retained calculations into a conservative fallback, never a forecast."""
    context = evidence.get("equity_research_context")
    if isinstance(context, dict) and context.get("market_region") == "china":
        return _china_evidence_derived_dimension(
            dimension_key,
            evidence=evidence,
            evidence_refs=evidence_refs,
        )
    context = context if isinstance(context, dict) else {}
    ticker = str(context.get("ticker") or "").upper()
    company = str(context.get("company") or ticker or "该公司")
    profile_value = context.get("reviewed_search_plan_not_evidence")
    profile = profile_value if isinstance(profile_value, dict) else {}
    products = [str(item) for item in profile.get("products") or []]
    competitors = [str(item) for item in profile.get("competitors_to_verify") or []]
    supply_inputs = [str(item) for item in profile.get("supply_chain_inputs_to_verify") or []]
    geographies = [str(item) for item in profile.get("geographies_to_verify") or []]
    product_focus = "、".join(products[:4]) if products else "主要产品线和业务分部"
    competitor_focus = "、".join(competitors[:4]) if competitors else "主要竞争者"
    input_focus = "、".join(supply_inputs[:4]) if supply_inputs else "关键材料、设备、能源与物流"
    geography_focus = "、".join(geographies[:5]) if geographies else "已披露生产和供应地区"
    derived = [
        item for item in evidence.get("derived_equity_evidence", []) if isinstance(item, dict)
    ]
    technical = next(
        (item for item in derived if item.get("category") == "derived_market_technical"),
        None,
    )
    valuation = next(
        (item for item in derived if item.get("category") == "derived_company_valuation"),
        None,
    )
    financial_trend = next(
        (item for item in derived if item.get("category") == "derived_company_financial_trend"),
        None,
    )
    macro_sensitivity = next(
        (item for item in derived if item.get("category") == "derived_macro_sensitivity"),
        None,
    )
    holdings = [item for item in derived if item.get("category") == "institutional_holding"]
    institutional_positioning = next(
        (item for item in derived if item.get("category") == "derived_institutional_positioning"),
        None,
    )
    insider_transactions = [
        item for item in derived if item.get("category") == "insider_transaction"
    ]
    verified_supply_edges = [
        item for item in derived if item.get("category") == "verified_supply_chain_edge"
    ]
    supplier_factors = [
        item for item in derived if item.get("category") == "derived_supplier_factor"
    ]
    named_supplier_factors = [
        item
        for item in supplier_factors
        if item.get("proxy_type") != "category_basket"
    ]
    category_proxy_factors = [
        item
        for item in supplier_factors
        if item.get("proxy_type") == "category_basket"
    ]
    supply_chain_sites = [
        item for item in derived if item.get("category") == "supply_chain_site_exposure"
    ]
    product_operating = [
        item for item in derived if item.get("category") == "product_operating_evidence"
    ]
    product_actuals = [
        item for item in product_operating if item.get("evidence_status") == "reported_actual"
    ]
    product_plans = [
        item
        for item in product_operating
        if item.get("evidence_status") == "forward_looking_plan"
    ]
    product_risks = [
        item for item in product_operating if item.get("evidence_status") == "risk_disclosure"
    ]

    if dimension_key == "fundamentals_valuation" and valuation:
        valuation_anomalies = _valuation_anomalies(valuation)
        if valuation_anomalies:
            return ModelEquityResearchDimension(
                dimension="fundamentals_valuation",
                assessment=(
                    f"{company}（{ticker}）的估值派生证据未通过算术一致性检查："
                    f"{'、'.join(valuation_anomalies)}。在重新选取同一报告期的收入、"
                    "利润、每股数据和股本之前，不展示市盈率、市销率或利润率结论。"
                ),
                signal="unknown",
                confidence=0.1,
                evidence_refs=evidence_refs,
                evidence_gaps=[
                    "需重新对齐同一财年/同一申报的收入、毛利、营业利润和净利润。",
                    "需验证拆股调整后每股数据与股本口径。",
                ],
            )
        multiple_label = (
            "TTM代理" if valuation.get("valuation_basis") == "ttm_proxy" else "最近财年静态"
        )
        revenue_value = valuation.get("basis_revenue")
        if not isinstance(revenue_value, (int, float)):
            revenue_value = valuation.get("annual_revenue")
        net_income_value = valuation.get("basis_net_income")
        if not isinstance(net_income_value, (int, float)):
            net_income_value = valuation.get("annual_net_income")
        eps_value = valuation.get("basis_diluted_eps_proxy")
        if not isinstance(eps_value, (int, float)):
            eps_value = valuation.get("annual_diluted_eps")
        research_value = valuation.get("basis_research_and_development")
        if not isinstance(research_value, (int, float)):
            research_value = valuation.get("annual_research_and_development")
        scenario_text = ""
        scenarios = valuation.get("question_price_scenarios") or []
        if scenarios and isinstance(scenarios[0], dict):
            scenario = scenarios[0]
            scenario_text = (
                f" 用户价格 {_fmt_number(scenario.get('target_price'))} 美元对应约"
                f" {_fmt_money(scenario.get('implied_market_cap'))} 市值、"
                f"{_fmt_number(scenario.get('implied_price_to_sales'))} 倍"
                f"{multiple_label}市销率和"
                f"{_fmt_number(scenario.get('implied_price_to_earnings'))} 倍"
                f"{multiple_label}市盈率。"
            )
        trend_text = ""
        trend_periods = (
            financial_trend.get("periods") if isinstance(financial_trend, dict) else None
        )
        if isinstance(trend_periods, list) and trend_periods:
            latest_trend = trend_periods[-1]
            if isinstance(latest_trend, dict):
                net_income_trend = _net_income_trend_text(trend_periods)
                trend_text = (
                    f" 点时序列显示最近财年收入同比"
                    f" {_fmt_percent(latest_trend.get('revenue_yoy'))}、{net_income_trend}、"
                    "自由现金流代理"
                    f" {_fmt_money(latest_trend.get('free_cash_flow_proxy'))}；仅使用价格"
                    "截止日前已经提交的SEC申报。净利润变化可能受低基数、周期或一次性项目"
                    "放大，不应线性外推。"
                )
        product_details = []
        for item in product_actuals[:5]:
            values = "、".join(str(value) for value in item.get("reported_values") or [])
            product_details.append(
                f"{item.get('product')}的{item.get('metric_name')}"
                + (f"（原文值：{values}）" if values else "")
            )
        product_text = (
            f" 年报原文另提供{len(product_actuals)}条已报告产品经营事实："
            f"{'；'.join(product_details)}。另有{len(product_plans)}条前瞻计划和"
            f"{len(product_risks)}条风险披露，均未当作已实现业绩。"
            if product_actuals
            else ""
        )
        assessment = (
            f"截至 {valuation.get('price_observed_on')}，拆股调整收盘价为"
            f" {_fmt_number(valuation.get('price'))} 美元；按 SEC 点时{multiple_label}口径，"
            f"收入约 {_fmt_money(revenue_value)}、净利润约"
            f" {_fmt_money(net_income_value)}、摊薄 EPS代理"
            f" {_fmt_number(eps_value)} 美元、毛利率"
            f" {_fmt_percent(valuation.get('gross_margin'))}、营业利润率"
            f" {_fmt_percent(valuation.get('operating_margin'))}；研发投入约"
            f" {_fmt_money(research_value)}，占收入"
            f" {_fmt_percent(valuation.get('research_and_development_to_revenue'))}。"
            "静态估算市值约"
            f" {_fmt_money(valuation.get('market_cap'))}，市销率"
            f" {_fmt_number(valuation.get('trailing_price_to_sales'))} 倍、市盈率"
            f" {_fmt_number(valuation.get('trailing_price_to_earnings'))} 倍。{trend_text}"
            f"{scenario_text}{product_text}这些是历史口径的机械估值，不等于未来合理价值；"
            + (
                "绝对单位产品销量/ASP、客户级合同、产品毛利和后续指引兑现仍需补证。"
                if product_actuals
                else "合同、产品销量、毛利趋势和管理层指引仍需从原文补证。"
            )
        )
        return ModelEquityResearchDimension(
            dimension="fundamentals_valuation",
            assessment=assessment,
            signal="mixed",
            confidence=0.64 if len(product_actuals) >= 4 else 0.55,
            evidence_refs=evidence_refs,
            evidence_gaps=[
                (
                    f"已取得部分{product_focus}年报经营事实，仍缺绝对单位销量/ASP、"
                    "产品毛利、份额与客户级订单/合同。"
                    if product_actuals
                    else f"缺少按{product_focus}拆分的销量、价格、毛利和订单/合同证据。"
                ),
                "缺少基于未来自由现金流、周期中枢和稀释假设的估值区间。",
                (
                    "Form 4 已解析交易方向、数量和价格，但申报本身不能证明交易动机。"
                    if insider_transactions
                    else "Form 4 目前仅确认申报存在，尚未解析交易方向、数量和价格。"
                ),
            ],
        )

    if dimension_key == "technicals_positioning" and technical:
        close = technical.get("adjusted_close")
        risk_reward = technical.get("risk_reward")
        risk_reward = risk_reward if isinstance(risk_reward, dict) else {}
        scenario_text = (
            " 当前价情景的失效/止损参考为"
            f"{_fmt_number(risk_reward.get('stop_reference'))}美元、目标/止盈参考为"
            f"{_fmt_number(risk_reward.get('target_reference'))}美元，潜在收益/风险约"
            f"{_fmt_number(risk_reward.get('reward_risk_ratio'))}倍；这些价位来自"
            + (
                "真实日线波段、ATR14与历史波动，只是审计边界而非下单建议。"
                if technical.get("bar_data_status") == "complete_ohlcv"
                else "收盘结构与历史波动，只是审计边界而非下单建议。"
            )
            if risk_reward
            else ""
        )
        institution_text = (
            " 13F真实平均成本不可得；返回管理人期末申报价值/股数加权代理为"
            f"{_fmt_number(institutional_positioning.get('quarter_end_value_per_share_proxy'))}"
            f"美元（{institutional_positioning.get('report_period')}），不得当作买入均价。"
            if isinstance(institutional_positioning, dict)
            else " 13F真实平均成本不可得，当前也没有可显示的期末价值代理。"
        )
        sma20_relation = _price_average_relation(close, technical.get("sma_20"))
        sma50_relation = _price_average_relation(close, technical.get("sma_50"))
        sma200_relation = _price_average_relation(close, technical.get("sma_200"))
        insider_codes = [
            str(item.get("transaction_classification") or "unclassified")
            for item in insider_transactions
        ]
        insider_summary = (
            f"；点时 Form 4 证据包含 {len(insider_transactions)} 条交易：公开市场买入"
            f" {insider_codes.count('open_market_purchase')} 条、公开市场卖出"
            f" {insider_codes.count('open_market_sale')} 条，其余为授予、行权、税务代扣、"
            "赠与或其他类别。交易披露不等于动机，也不能单独预测股价"
            if insider_transactions
            else "；Form 4 交易明细仍在回填，不能从申报目录推断内部人方向"
        )
        assessment = (
            f"截至 {technical.get('observed_on')}，收盘价"
            f" {_fmt_number(close)} 美元，{sma20_relation} SMA20"
            f" {_fmt_number(technical.get('sma_20'))}、{sma50_relation} SMA50"
            f" {_fmt_number(technical.get('sma_50'))}、{sma200_relation} SMA200"
            f" {_fmt_number(technical.get('sma_200'))}；RSI14 为"
            f" {_fmt_number(technical.get('rsi_14'))}，MACD 柱为"
            f" {_fmt_number(technical.get('macd_histogram'))}，21 日收益"
            f" {_fmt_percent(technical.get('return_21d'))}，距 52 周收盘高点"
            f" {_fmt_percent(technical.get('drawdown_from_52_week_high'))}，ATR14 为"
            f" {_fmt_number(technical.get('atr_14'))} 美元，最新成交量/20日均量为"
            f" {_fmt_number(technical.get('volume_ratio_20'))} 倍。均线关系、动量"
            "与回撤必须联合解释，不能把单一指标写成买卖结论。最新 13F 证据覆盖"
            f" {len(holdings)} 家主要申报管理人；可比较季度末股数变化，但不能推出"
            "任何机构成本、盘中大单，也不能仅凭管理人名称判断主动或被动基金"
            f"{insider_summary}。{scenario_text}{institution_text}"
        )
        return ModelEquityResearchDimension(
            dimension="technicals_positioning",
            assessment=assessment,
            signal="mixed",
            confidence=0.6,
            evidence_refs=evidence_refs,
            evidence_gaps=[
                (
                    "已有日线成交量，但仍缺逐笔成交、期权持仓和真实机构成本数据。"
                    if technical.get("bar_data_status") == "complete_ohlcv"
                    else "缺少成交量、逐笔成交、期权持仓和真实机构成本数据。"
                ),
                (
                    "KDJ 已使用日线最高、最低与收盘价；仍不能代替盘中结构验证。"
                    if technical.get("bar_data_status") == "complete_ohlcv"
                    else "当前 KDJ 是仅用收盘价计算的代理值，尚缺日内最高/最低价。"
                ),
                "13F 有申报延迟、修订和持仓范围限制，不能作为实时资金流。",
                "Form 4 交易可能来自既定10b5-1计划、薪酬归属或税务安排。",
            ],
        )

    if dimension_key == "macro_liquidity":
        latest_market = _latest_market_items(evidence)
        observed = []
        for series_id in ("DGS2", "DGS10", "NFCI", "M2SL", "DTWEXBGS"):
            item = latest_market.get(series_id)
            if item:
                observed.append(
                    f"{series_id}={_fmt_number(item.get('value'))}（{item.get('observed_on')}）"
                )
        sensitivity_text = ""
        if isinstance(macro_sensitivity, dict):
            values = macro_sensitivity.get("sensitivities")
            if isinstance(values, list):
                rendered = [
                    f"{item.get('series_id')}相关系数="
                    f"{_fmt_number(item.get('contemporaneous_correlation'))}"
                    for item in values[:6]
                    if isinstance(item, dict)
                ]
                if rendered:
                    sensitivity_text = (
                        f" 与{ticker}日收益对齐后的描述性结果为：{'; '.join(rendered)}。"
                        "该测算不识别因果。"
                    )
        assessment = (
            "本地证据可监测美国利率、信用、美元和流动性环境"
            + (f"：{'; '.join(observed)}。" if observed else "，但本次缺少可引用观测。")
            + sensitivity_text
            + f"这些数据只能检验{ticker}估值与宏观环境的历史共变，"
            "不能证明特定资金来源、政策或汇率变化已经造成个股波动。"
            "建立因果链还需市场预期、利率/汇率、资金流与公司事件的精确时间对齐。"
        )
        return ModelEquityResearchDimension(
            dimension="macro_liquidity",
            assessment=assessment,
            signal="unknown",
            confidence=0.35 if observed else 0.15,
            evidence_refs=evidence_refs,
            evidence_gaps=[
                "缺少利率、信用、汇率、资金流和市场预期的统一事件时钟。",
                f"缺少宏观变量与{ticker}公司公告、行业因子和资金流的替代解释检验。",
                "宏观相关性尚不能证明对单只股票的因果贡献。",
            ],
        )

    if dimension_key == "supply_chain_geopolitics":
        disruption_impact = (
            "组件可得性、代工装配、产品发布与交付、收入和毛利率"
            if ticker == "AAPL"
            else "产出、交付周期和毛利率"
        )
        verified_names = list(
            dict.fromkeys(
                str(item.get("related_company_name"))
                for item in verified_supply_edges
                if item.get("related_company_name")
            )
        )
        geocoded_sites = [
            item
            for item in supply_chain_sites
            if item.get("latitude") is not None and item.get("longitude") is not None
        ]
        exact_sites = [
            item
            for item in supply_chain_sites
            if item.get("coordinate_precision") == "exact_facility"
        ]
        company_facilities = [
            item for item in exact_sites if item.get("facility_role") == "company_facility"
        ]
        supplier_locations = [
            item
            for item in supply_chain_sites
            if item.get("facility_role") == "upstream_supplier_location"
        ]
        conflict_sites = [
            item for item in supply_chain_sites if int(item.get("conflict_events") or 0) > 0
        ]
        disaster_sites = [
            item for item in supply_chain_sites if int(item.get("disaster_event_count") or 0) > 0
        ]
        if verified_supply_edges or supply_chain_sites:
            verified_supply_total = int(
                context.get("verified_supply_chain_edge_total") or len(verified_supply_edges)
            )
            exact_names = list(
                dict.fromkeys(
                    str(item.get("site_name")) for item in exact_sites if item.get("site_name")
                )
            )
            location_text = (
                f"本次还纳入{len(supply_chain_sites)}条制造地点暴露证据，其中"
                f"{len(geocoded_sites)}条已定位到省州或城市参考点、"
                f"{len(exact_sites)}条达到精确工厂级；近12周有"
                f"{len(conflict_sites)}条出现邻近冲突记录、"
                f"{len(disaster_sites)}条出现邻近灾害记录。"
                + (
                    f"其中{len(company_facilities)}条标记为公司自有设施，"
                    f"{len(supplier_locations)}条标记为上游供应商地点；"
                    f"已核验设施包括{'、'.join(exact_names[:8])}。"
                    if exact_sites
                    else ""
                )
                + "省州/城市中心点不等同于工厂坐标，最近港口也不代表已确认运输路线。"
                if supply_chain_sites
                else "制造地点尚未完成结构化空间连接。"
            )
            relationship_text = (
                f"数据库共有{verified_supply_total}条经来源审核的{company}供应链关系；"
                f"本次证据包纳入{len(verified_supply_edges)}条带原文和有效期的关系，涉及"
                f"{'、'.join(verified_names[:6]) or '已披露关联方'}。"
                if verified_supply_edges
                else f"数据库尚无可用于本报告的{company}上游供应商关系；"
                "公司自有设施不能被误写成上游供应商或客户专用产线。"
            )
            factor_alignment_parts: list[str] = []
            if named_supplier_factors:
                factor_alignment_parts.append(
                    f"{len(named_supplier_factors)}条具名已核验关系可与供应商市场序列对齐"
                )
            if category_proxy_factors:
                factor_alignment_parts.append(
                    f"{len(category_proxy_factors)}个未披露具体供应商的依赖类别使用行业篮子代理；"
                    "篮子成分不得解释为关联公司或真实供应商"
                )
            factor_alignment_text = (
                "；".join(factor_alignment_parts)
                if factor_alignment_parts
                else "当前没有可用的具名供应商或行业篮子市场代理"
            )
            assessment = (
                f"截至供应链证据截止日，{relationship_text}"
                f"{factor_alignment_text}；这些收益相关和"
                "滞后相关只用于探索风险传导，不能替代产品价格、交付量、产能、库存或合同证据。"
                f"{location_text}未披露关系仍视为缺口。"
            )
            confidence = (
                0.52
                if geocoded_sites and supplier_factors
                else 0.46
                if exact_sites
                else 0.5
                if named_supplier_factors
                else 0.38
            )
            signal = (
                "mixed"
                if verified_supply_edges or supplier_factors or conflict_sites or disaster_sites
                else "unknown"
            )
        else:
            assessment = (
                f"当前检索计划中的{input_focus}与{geography_focus}只是待验证对象，"
                f"并不是已验证的{company}供应商—工厂—产能映射。"
                "国家级冲突或灾害着色也不足以证明具体工厂"
                "暴露，因此暂不据此给出看多或看空信号。"
            )
            confidence = 0.2
            signal = "unknown"
        return ModelEquityResearchDimension(
            dimension="supply_chain_geopolitics",
            assessment=assessment,
            signal=signal,
            confidence=confidence,
            evidence_refs=evidence_refs,
            evidence_gaps=[
                (
                    "已取得精确设施坐标，但仍缺具体产线、产能、单点依赖、库存缓冲和替代供应能力。"
                    if exact_sites
                    else "仍缺少精确工厂坐标、具体产线、单点依赖、库存缓冲和替代供应能力。"
                ),
                "当前港口是最近地理参考而非确认路线；仍缺电网、容量、停电和运力数据。",
                f"缺少供应中断对{disruption_impact}的情景敏感度。",
            ],
        )

    if product_operating:
        observed_products = "、".join(
            list(
                dict.fromkeys(
                    str(item.get("product"))
                    for item in product_operating
                    if item.get("product")
                )
            )[:6]
        )
        technology_assessment = (
            f"{company}年报原文已提供{len(product_actuals)}条已报告经营事实，覆盖"
            f"{observed_products or product_focus}；另有{len(product_plans)}条前瞻计划与"
            f"{len(product_risks)}条风险披露。它们能验证收入、相对价格/销量、席位、产品"
            "组合或合同义务中的部分环节，但没有形成与竞争者同口径的性能、成本、份额和"
            f"客户采用对照，因此仍不能仅据此断言{company}护城河增强或削弱。"
        )
        technology_gaps = [
            f"缺少{product_focus}与{competitor_focus}同口径的性能、成本、份额和采用率。",
            "相对ASP/出货变化没有转换成绝对单价或单位量；客户级合同仍未披露。",
            "前瞻量产、产能或收入确认计划需要未来申报逐期验证是否兑现。",
        ]
    elif ticker == "AAPL":
        technology_assessment = (
            f"本地检索计划只把{product_focus}与{competitor_focus}列为待验证对象，"
            "但尚没有同口径的产品销量与组合、平均售价、市场份额、生态留存、服务收入、"
            "端侧AI采用、芯片性能及监管影响的一手对照证据。因此不能把产品发布或竞争者"
            f"名单本身当作护城河，也不能断言替代平台已经削弱或加强{company}的定价能力。"
        )
        technology_gaps = [
            f"缺少{product_focus}的销量、平均售价、市场份额、毛利和用户留存基准。",
            "缺少App Store监管、服务业务、端侧AI采用与自研芯片差异化的量化证据。",
            "缺少智能手机、PC、可穿戴与AI平台竞争变化的可比数据和采用路径。",
        ]
    else:
        technology_assessment = (
            f"本地检索计划只把{product_focus}与{competitor_focus}列为待验证对象，"
            "但尚没有同口径产品性能、成本、份额、客户采用、专利和替代技术的一手对照证据。"
            "因此不能把竞争者名单本身当作护城河，也不能断言替代技术已削弱或加强"
            f"{company}的定价能力。"
        )
        technology_gaps = [
            f"缺少{product_focus}的市场份额、价格、产能、成本和性能基准。",
            "缺少客户合同、采用周期、关键产能瓶颈与竞争者投入对照。",
            "缺少替代技术的可量化采用路径。",
        ]
    return ModelEquityResearchDimension(
        dimension="technology_competition",
        assessment=technology_assessment,
        signal="unknown",
        confidence=0.45 if product_operating else 0.2,
        evidence_refs=evidence_refs,
        evidence_gaps=technology_gaps,
    )


def _china_evidence_derived_dimension(
    dimension_key: str,
    *,
    evidence: dict[str, Any],
    evidence_refs: list[str],
) -> ModelEquityResearchDimension:
    """Build conservative A-share dimensions from market snapshots only."""
    context = evidence.get("equity_research_context") or {}
    company = str(context.get("company") or context.get("ticker") or "该公司")
    ticker = str(context.get("ticker") or "")
    derived = [
        item for item in evidence.get("derived_equity_evidence", []) if isinstance(item, dict)
    ]
    technical = next(
        (item for item in derived if item.get("category") == "derived_market_technical"),
        None,
    )
    valuation = next(
        (item for item in derived if item.get("category") == "derived_company_valuation"),
        None,
    )
    macro = next(
        (item for item in derived if item.get("category") == "derived_macro_sensitivity"),
        None,
    )
    missing = list(context.get("required_missing_evidence") or [])
    if dimension_key == "fundamentals_valuation" and valuation:
        return ModelEquityResearchDimension(
            dimension="fundamentals_valuation",
            assessment=(
                f"截至{valuation.get('price_observed_on')}，{company}（{ticker}）前复权收盘价"
                f"为{_fmt_number(valuation.get('price'))}元，BaoStock最新截面PE为"
                f"{_fmt_number(valuation.get('trailing_price_to_earnings'))}倍、PB为"
                f"{_fmt_number(valuation.get('price_to_book'))}倍，市值约"
                f"{_fmt_cny(valuation.get('market_cap'))}。收入、净利润和ROE当前仅是"
                "排名日快照，未保存原公告发布日期和审计原文，不能视为可回测的点时财报，"
                "也不能据此给出合理价值或买点。"
            ),
            signal="unknown",
            confidence=0.38,
            evidence_refs=evidence_refs,
            evidence_gaps=missing[:3],
        )
    if dimension_key == "technicals_positioning" and technical:
        close = technical.get("adjusted_close")
        return ModelEquityResearchDimension(
            dimension="technicals_positioning",
            assessment=(
                f"截至{technical.get('observed_on')}，{company}收盘价"
                f"{_fmt_number(close)}元，{_price_average_relation(close, technical.get('sma_20'))}"
                f"SMA20 {_fmt_number(technical.get('sma_20'))}、"
                f"{_price_average_relation(close, technical.get('sma_50'))}SMA50 "
                f"{_fmt_number(technical.get('sma_50'))}；RSI14为"
                f"{_fmt_number(technical.get('rsi_14'))}，MACD柱为"
                f"{_fmt_number(technical.get('macd_histogram'))}。这些是收盘价历史形态，"
                "缺少高低价、成交明细和可审计机构资金，不构成交易信号。"
            ),
            signal="mixed",
            confidence=0.55,
            evidence_refs=evidence_refs,
            evidence_gaps=[
                "缺少日内最高/最低价、逐笔成交、期权和真实机构成本。",
                "北向与机构资金序列尚未以原始来源和可得时间入库。",
            ],
        )
    if dimension_key == "macro_liquidity":
        sensitivity_count = len(macro.get("sensitivities") or []) if macro else 0
        return ModelEquityResearchDimension(
            dimension="macro_liquidity",
            assessment=(
                f"本地共形成{sensitivity_count}组{company}收益与宏观序列的同期相关/"
                "单变量敏感度。它们只能描述历史共同变化，未控制行业、政策、汇率与"
                "公司事件，不能证明宏观流动性造成该股涨跌。"
            ),
            signal="unknown",
            confidence=0.3 if macro else 0.12,
            evidence_refs=evidence_refs,
            evidence_gaps=[
                "缺少A股行业基准、人民币利率/信用、北向与基金流量的统一点时模型。",
                "缺少对公司公告、行业政策和宏观变量的多因素替代解释检验。",
            ],
        )
    if dimension_key == "supply_chain_geopolitics":
        return ModelEquityResearchDimension(
            dimension="supply_chain_geopolitics",
            assessment=(
                f"当前没有经公告验证的{company}供应商、客户、工厂、产能、原料、港口"
                "与电力依赖图谱。国家或省级冲突/灾害着色不能直接推断公司交付和利润"
                "影响，因此该维度只登记证据缺口。"
            ),
            signal="unknown",
            confidence=0.12,
            evidence_refs=evidence_refs,
            evidence_gaps=missing[-2:] or ["缺少设施和供应链结构化证据。"],
        )
    return ModelEquityResearchDimension(
        dimension="technology_competition",
        assessment=(
            f"当前没有{company}产品族、ASP、销量、市场份额、订单合同、研发路线和"
            "替代技术的结构化公告证据。新闻线索不能代替交易所原文，因此暂不判断"
            "技术护城河强弱。"
        ),
        signal="unknown",
        confidence=0.12,
        evidence_refs=evidence_refs,
        evidence_gaps=[
            "缺少产品、产销量、价格、份额和订单的公告原文及精确时间戳。",
            "缺少竞争者和替代技术的同口径对照。",
        ],
    )


def _latest_market_items(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in evidence.get("market_observations", []):
        if not isinstance(item, dict):
            continue
        series_id = item.get("series_id")
        if not isinstance(series_id, str):
            continue
        previous = result.get(series_id)
        if previous is None or str(item.get("observed_on") or "") > str(
            previous.get("observed_on") or ""
        ):
            result[series_id] = item
    return result


def _valuation_anomalies(valuation: dict[str, Any]) -> list[str]:
    """Flag internally inconsistent derived valuation inputs before they reach prose."""
    anomalies: list[str] = []
    revenue = valuation.get("basis_revenue")
    net_income = valuation.get("basis_net_income")
    gross_margin = valuation.get("gross_margin")
    operating_margin = valuation.get("operating_margin")
    research_ratio = valuation.get("research_and_development_to_revenue")
    if not isinstance(revenue, (int, float)) or not math.isfinite(float(revenue)):
        anomalies.append("收入口径缺失或非有限数")
    elif revenue <= 0:
        anomalies.append("收入不为正数")
    if (
        isinstance(revenue, (int, float))
        and revenue > 0
        and isinstance(net_income, (int, float))
        and net_income > revenue * 1.2
    ):
        anomalies.append("净利润明显高于同口径收入")
    for label, value, lower, upper in (
        ("毛利率", gross_margin, -0.5, 1.2),
        ("营业利润率", operating_margin, -3.0, 1.2),
        ("研发/收入比", research_ratio, 0.0, 2.0),
    ):
        if isinstance(value, (int, float)) and (
            not math.isfinite(float(value)) or not lower <= float(value) <= upper
        ):
            anomalies.append(f"{label}超出算术安全范围")
    return anomalies


def _fmt_number(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "缺失"
    absolute = abs(float(value))
    digits = 0 if absolute >= 100 else 2
    return f"{float(value):,.{digits}f}"


def _price_average_relation(price: Any, average: Any) -> str:
    """Return the numerically correct Chinese relation for a price and average."""
    try:
        price_value = float(price)
        average_value = float(average)
    except (TypeError, ValueError):
        return "无法比较于"
    if not math.isfinite(price_value) or not math.isfinite(average_value):
        return "无法比较于"
    if math.isclose(price_value, average_value, rel_tol=1e-9, abs_tol=1e-9):
        return "约等于"
    return "高于" if price_value > average_value else "低于"


def _equity_horizon_text(question: str | None) -> str:
    """Keep repaired equity chains aligned with the requested forecast horizon."""
    normalized = str(question or "").casefold().replace("－", "-").replace("—", "-")
    if re.search(
        r"(?:未来|接下来|next\s*)?(?:1\s*(?:-|至|到)\s*2|一\s*(?:至|到)\s*两)\s*(?:周|weeks?)",
        normalized,
    ):
        return "未来1至2周"
    if re.search(r"(?:未来|接下来|next\s*)?(?:1|一)\s*(?:周|week)", normalized):
        return "未来1周"
    if re.search(r"(?:未来|接下来|next\s*)?(?:2|两)\s*(?:周|weeks?)", normalized):
        return "未来2周"
    if re.search(r"(?:未来|接下来|next\s*)?(?:1|一)\s*(?:月|month)", normalized):
        return "未来1个月"
    return "未来6至12个月"


def _fmt_money(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "缺失"
    number = float(value)
    if abs(number) >= 1_000_000_000:
        return f"{number / 1_000_000_000:,.2f} 十亿美元"
    if abs(number) >= 1_000_000:
        return f"{number / 1_000_000:,.2f} 百万美元"
    return f"{number:,.0f} 美元"


def _fmt_cny(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "缺失"
    number = float(value)
    if abs(number) >= 100_000_000:
        return f"{number / 100_000_000:,.2f}亿元"
    if abs(number) >= 10_000:
        return f"{number / 10_000:,.2f}万元"
    return f"{number:,.0f}元"


def _fmt_percent(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "缺失"
    return f"{float(value) * 100:.1f}%"


def _net_income_trend_text(periods: list[Any]) -> str:
    """Describe profit/loss transitions without misleading negative-base growth."""
    latest = periods[-1] if periods else None
    previous = periods[-2] if len(periods) >= 2 else None
    if not isinstance(latest, dict):
        return "净利润同比 缺失"
    current_value = latest.get("net_income")
    previous_value = previous.get("net_income") if isinstance(previous, dict) else None
    if isinstance(current_value, (int, float)) and isinstance(previous_value, (int, float)):
        current = float(current_value)
        prior = float(previous_value)
        if prior < 0 and current < 0:
            direction = "收窄" if abs(current) < abs(prior) else "扩大"
            return f"净亏损由 {_fmt_money(abs(prior))}{direction}至 {_fmt_money(abs(current))}"
        if prior >= 0 > current:
            return f"净利润由 {_fmt_money(prior)}转为净亏损 {_fmt_money(abs(current))}"
        if prior < 0 <= current:
            return f"净亏损由 {_fmt_money(abs(prior))}转为净利润 {_fmt_money(current)}"
    return f"净利润同比 {_fmt_percent(latest.get('net_income_yoy'))}"


def _fallback_equity_framework(
    evidence: dict[str, Any],
) -> ModelEquityDecisionFramework:
    context = evidence.get("equity_research_context")
    if isinstance(context, dict) and context.get("market_region") == "china":
        company = str(context.get("company") or context.get("ticker") or "该公司")
        return ModelEquityDecisionFramework(
            timing_assessment="insufficient_evidence",
            current_price_context=(
                f"{company}当前只具备BaoStock行情、估值/财务截面快照和描述性宏观"
                "敏感度。财报原文可得时间、合同、资金流和供应链尚未结构化接入，"
                "因此不能给出确定买点或目标价。"
            ),
            valuation_scenarios=[],
            entry_conditions=[
                "交易所原始财报和公告验证收入、利润、现金流与业务驱动。",
                "估值与技术状态改善得到成交和资金流原始数据交叉确认。",
                "产品、合同、设施与供应链风险完成点时证据映射。",
            ],
            invalidation_conditions=[
                "公告口径盈利、现金流或订单弱于当前快照隐含假设。",
                "技术状态恶化且行业或公司事件提供独立反证。",
                "关键设施、原料、政策或地缘风险出现可量化损失。",
            ],
            monitoring_indicators=[
                "上交所/深交所/巨潮公告全文与原始披露时间",
                "收入、利润、现金流、ROE、PE、PB和行业基准",
                "成交量、股东、机构与北向资金的可审计序列",
                "产品、合同、产销量、设施和供应链风险",
            ],
            not_personalized_advice=True,
        )
    company = (
        str(context.get("company") or context.get("ticker") or "该公司")
        if isinstance(context, dict)
        else "该公司"
    )
    profile_value = (
        context.get("reviewed_search_plan_not_evidence") if isinstance(context, dict) else None
    )
    profile = profile_value if isinstance(profile_value, dict) else {}
    products = [str(item) for item in profile.get("products") or []]
    product_focus = "、".join(products[:4]) if products else "主要产品线和业务分部"
    scenarios: list[str] = []
    technical: dict[str, Any] | None = None
    valuation: dict[str, Any] | None = None
    valuation_quality_issues: list[str] = []
    for item in evidence.get("derived_equity_evidence", []):
        if not isinstance(item, dict):
            continue
        if item.get("category") == "derived_market_technical":
            technical = item
            continue
        if item.get("category") != "derived_company_valuation":
            continue
        item_quality_issues = _valuation_anomalies(item)
        if item_quality_issues:
            valuation_quality_issues.extend(item_quality_issues)
            continue
        valuation = item
        multiple_label = "TTM代理" if item.get("valuation_basis") == "ttm_proxy" else "最近财年静态"
        for scenario in item.get("question_price_scenarios", []):
            if not isinstance(scenario, dict):
                continue
            scenarios.append(
                f"价格 {_fmt_number(scenario.get('target_price'))} 美元对应隐含市值"
                f" {_fmt_money(scenario.get('implied_market_cap'))}、"
                f"{multiple_label}市销率"
                f" {_fmt_number(scenario.get('implied_price_to_sales'))} 倍、"
                f"{multiple_label}市盈率"
                f" {_fmt_number(scenario.get('implied_price_to_earnings'))} 倍；须用未来"
                "收入、利润、自由现金流与周期中枢验证。"
            )
    timing_assessment: Literal["attractive", "neutral", "extended", "insufficient_evidence"] = (
        "insufficient_evidence"
    )
    if valuation and technical:
        price_to_sales = valuation.get("trailing_price_to_sales")
        price_to_earnings = valuation.get("trailing_price_to_earnings")
        if (isinstance(price_to_sales, (int, float)) and price_to_sales > 15) or (
            isinstance(price_to_earnings, (int, float)) and price_to_earnings > 60
        ):
            timing_assessment = "extended"
    return ModelEquityDecisionFramework(
        timing_assessment=timing_assessment,
        current_price_context=(
            "当前只能形成条件化观察框架，不能给出确定买点。估值使用点时TTM代理或"
            "最近财年口径，"
            "技术指标来自拆股调整日收盘价；二者都需要未来财报、成交量、竞争与宏观"
            "证据交叉确认。若用户价格低于当前价，它是回撤情景，不应被误写成上涨目标。"
            + (
                "当前财务口径存在跨期或算术异常，相关估值及价格情景已从决策框架移除，"
                "等待同周期财务数据修复。"
                if valuation_quality_issues
                else ""
            )
        ),
        valuation_scenarios=scenarios[:8],
        entry_conditions=[
            "财报和管理层指引验证收入、毛利、EPS 与现金流增长足以压低远期估值倍数。",
            "价格止跌并重新站稳关键短中期均线，且 MACD/成交量出现相互印证的改善。",
            "供应链、竞争和宏观流动性没有出现足以推翻盈利假设的新反证。",
        ],
        invalidation_conditions=[
            "收入、毛利、EPS 或自由现金流兑现不足，不能支撑当前条件化估值。",
            "价格趋势继续转弱，同时盈利预期、订单或竞争地位被下修。",
            "关键工厂、材料、能源或地缘风险造成可量化的产能和交付损失。",
        ],
        monitoring_indicators=[
            "SEC 财报、Form 4 与管理层指引",
            "SMA、RSI、MACD、KDJ 与成交量",
            "13F 季度持仓变化（不推断成本）",
            "2Y/10Y 收益率、美元、金融条件和流动性",
            f"{company}的{product_focus}价格、销量、产能、份额和供给",
            f"{company}关键材料、设施、能源、物流、冲突和自然灾害",
        ],
        not_personalized_advice=True,
    )


def _call_local_question_planner(
    *,
    evidence: dict[str, Any],
    settings: Settings,
    transport: httpx.BaseTransport | None,
) -> PlannedResearchQuestion:
    """Use a small strict stage for autonomous question selection."""
    if settings.llm_provider == "mock":
        raise ResearchProviderError("question planning requires a configured local model")
    schema = _compatible_json_schema(PlannedResearchQuestion)
    focus = str(evidence.get("required_autonomous_focus") or "")
    planner_context = {
        "required_autonomous_focus": focus,
        "prohibited_prior_questions": evidence.get("prior_research_questions", []),
        "reliable_research_window": evidence.get("reliable_research_window"),
        "preferred_research_period": evidence.get("preferred_research_period"),
        "research_event_table": evidence.get("research_event_table"),
        "economic_cycle": evidence.get("economic_cycle"),
        "economic_cycle_models": evidence.get("economic_cycle_models"),
        "data_coverage": evidence.get("data_coverage"),
        # The builder already ranks this list while keeping oldest/latest
        # pairs adjacent. Preserve that pairing for the planner and fallback.
        "historical_anchors": list(evidence.get("historical_anchors") or [])[:36],
        "episode_candidates": list(evidence.get("episode_candidates") or [])[:24],
        "market_observations": _rank_evidence_for_focus(
            evidence.get("market_observations"),
            focus=focus,
            limit=18,
        ),
        "company_financials": _rank_evidence_for_focus(
            evidence.get("company_financials"),
            focus=focus,
            limit=18,
        ),
        "economic_observations": _rank_evidence_for_focus(
            evidence.get("economic_observations"),
            focus=focus,
            limit=12,
        ),
        "energy_observations": _rank_evidence_for_focus(
            evidence.get("energy_observations"),
            focus=focus,
            limit=12,
        ),
        "recent_documents": _rank_evidence_for_focus(
            evidence.get("documents"),
            focus=focus,
            limit=10,
        ),
    }
    messages = [
        {"role": "system", "content": LOCAL_QUESTION_PLANNER_PROMPT},
        {
            "role": "user",
            "content": json.dumps(planner_context, ensure_ascii=False),
        },
    ]
    if settings.llm_provider == "ollama":
        endpoint = "/api/chat"
        payload = {
            "model": settings.llm_model,
            "messages": messages,
            "stream": False,
            "think": False,
            "format": schema,
            "options": {"temperature": 0.35},
        }
    else:
        endpoint = "/v1/chat/completions"
        payload = {
            "model": settings.llm_model,
            "messages": messages,
            "stream": False,
            "temperature": 0.35,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "news_map_question_planner",
                    "strict": True,
                    "schema": schema,
                },
            },
        }
    last_error: Exception | None = None
    for _ in range(settings.llm_max_attempts):
        try:
            with httpx.Client(
                base_url=str(settings.llm_base_url).rstrip("/"),
                timeout=settings.research_llm_timeout_seconds,
                transport=transport,
            ) as client:
                response = client.post(endpoint, json=payload)
                response.raise_for_status()
            data = response.json()
            content = (
                data["message"]["content"]
                if settings.llm_provider == "ollama"
                else data["choices"][0]["message"]["content"]
            )
            planned = PlannedResearchQuestion.model_validate_json(content)
            if not 12 <= len(planned.question.strip()) <= 1_000:
                raise ValueError("planned question length is invalid")
            if _duplicates_prior_question(
                planned.question,
                planner_context["prohibited_prior_questions"],
            ):
                payload["messages"] = [
                    *messages,
                    {
                        "role": "user",
                        "content": (
                            "That question duplicates the prohibited list. "
                            "Return a materially different question in the required focus."
                        ),
                    },
                ]
                raise ValueError("planned question duplicates prior research")
            _validate_planned_question_evidence(
                planned,
                episode_candidates=planner_context["episode_candidates"],
                historical_anchors=planner_context["historical_anchors"],
                research_event_table=planner_context["research_event_table"],
                preferred_research_period=planner_context["preferred_research_period"],
            )
            planned.question = planned.question.strip()
            return planned
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
            ValidationError,
        ) as exc:
            last_error = exc
            if isinstance(exc, (ValueError, ValidationError)):
                payload["messages"] = [
                    *messages,
                    {
                        "role": "user",
                        "content": (
                            "The previous plan was invalid. Select a 7-550 day window "
                            "from episode_candidates, prioritize the supplied earliest "
                            "complete preferred_research_period, and cite exact trigger "
                            "and outcome evidence IDs inside it. Historical references "
                            "belong only in historical_context_refs. Return every "
                            "schema field and do not invent evidence IDs."
                        ),
                    },
                ]
    try:
        return _fallback_episode_question_plan(
            episode_candidates=planner_context["episode_candidates"],
            historical_anchors=planner_context["historical_anchors"],
            focus=focus,
            prohibited_questions=planner_context["prohibited_prior_questions"],
            preferred_research_period=planner_context["preferred_research_period"],
        )
    except ValueError as exc:
        raise ResearchProviderError(
            "local question planner could not find a bounded evidence episode"
        ) from (last_error or exc)


def _inquiry_view(
    row: ResearchInquiry,
    *,
    include_full_evidence: bool = True,
) -> ResearchInquiryView:
    result = ModelResearchResult.model_validate(row.result) if row.result else None
    review = (
        ChatGPTResearchReview.model_validate(row.chatgpt_review) if row.chatgpt_review else None
    )
    evidence_snapshot = row.evidence_snapshot
    if not include_full_evidence:
        evidence_snapshot = {
            key: row.evidence_snapshot[key]
            for key in (
                "generated_at",
                "episode_window",
                "historical_context_refs",
                "planned_question_evidence_refs",
                "evidence_retrieval",
                "bridge_evidence_completion",
                "market_data_quality",
                "question_search_summary",
                "research_workflow",
                "research_event_table",
                "reliable_research_window",
                "preferred_research_period",
                "news_evidence_sequences",
                "news_forecast_anchors",
                "forecast_validation_cases",
                "forecast_validation_runs",
                "question_assistance",
                "plain_language_report",
                "directional_confidence",
                "derived_equity_evidence",
                "report_audit",
            )
            if key in row.evidence_snapshot
        }
    return ResearchInquiryView(
        id=row.id,
        question=row.question,
        mode=cast(Literal["user_question", "autonomous"], row.mode),
        status=cast(Literal["running", "completed", "failed"], row.status),
        local_model=row.local_model,
        result=result,
        evidence_snapshot=evidence_snapshot,
        chatgpt_review=review,
        review_signals=[
            ResearchReviewSignalView.model_validate(signal) for signal in row.review_signals
        ],
        error=row.error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _apply_local_report_audit(
    result: ModelResearchResult,
    *,
    evidence: dict[str, Any],
) -> None:
    """Audit citations, time boundaries and factor claims after local generation."""
    factor_research = result.factor_research
    profit_validations = factor_research.profit_validations if factor_research else []
    cross_validations = factor_research.cross_sectional_validations if factor_research else []
    profit_negative = sum(item.status == "out_of_sample_negative" for item in profit_validations)
    profit_positive = sum(item.status == "out_of_sample_positive" for item in profit_validations)
    cross_negative = sum(item.status == "out_of_sample_negative" for item in cross_validations)
    robust_positive = sum(
        item.robustness is not None and item.robustness.status == "out_of_sample_positive"
        for item in cross_validations
    )
    validated_alpha = bool(profit_positive and robust_positive)
    equity_context = evidence.get("equity_research_context")
    equity_context = equity_context if isinstance(equity_context, dict) else {}
    data_readiness = equity_context.get("data_readiness")
    data_readiness = data_readiness if isinstance(data_readiness, dict) else None
    directional_confidence = _directional_confidence_explanation(
        result,
        validated_alpha=validated_alpha,
        data_readiness=data_readiness,
    )
    repaired_forecasts = _repair_zero_confidence_fallback_forecasts(
        result,
        evidence=evidence,
        directional_confidence=directional_confidence,
    )
    if repaired_forecasts:
        _record_report_repair(
            evidence,
            section="news_forecasts",
            reason="fallback_confidence_derived_from_audited_chain_support",
        )
    evidence["directional_confidence"] = directional_confidence
    factor_statement = (
        f"因子样本外审计：单资产检验{profit_negative}/{len(profit_validations)}为"
        f"样本外负向，横截面检验{cross_negative}/{len(cross_validations)}为样本外负向，"
        f"稳健性检验{robust_positive}/{len(cross_validations)}支持正向结果；"
        + (
            "存在待复核的正向统计信号，但仍不能视为未来收益保证。"
            if validated_alpha
            else "当前结果不支持可盈利择时、买点或交易结论。"
        )
    )
    summary_base = result.summary.split(" 因子样本外审计：", 1)[0].strip()
    result.summary = f"{summary_base} {factor_statement}"[:3_000]

    cited_refs = {
        ref
        for hypothesis in result.hypotheses
        for step in hypothesis.steps
        for ref in step.evidence_refs
    }
    cited_refs.update(
        ref for dimension in result.equity_dimensions for ref in dimension.evidence_refs
    )
    cited_refs.update(ref for factor in result.factor_candidates for ref in factor.evidence_refs)
    if result.paper_report is not None:
        cited_refs.update(result.paper_report.evidence_refs)
    allowed_refs = _evidence_ids(evidence)
    missing_refs = sorted(cited_refs - allowed_refs)
    headline_refs = sorted(cited_refs & headline_only_evidence_ids(evidence))

    evidence_index = {
        str(item["evidence_id"]): item
        for values in evidence.values()
        if isinstance(values, list)
        for item in values
        if isinstance(item, dict) and item.get("evidence_id")
    }
    context = evidence.get("equity_research_context")
    context = context if isinstance(context, dict) else {}
    ticker = str(context.get("ticker") or "").upper()
    rejected_company_refs = sorted(
        {
            str(ref)
            for ref in evidence.get("rejected_company_document_refs", [])
            if isinstance(ref, str) and ref
        }
    )
    report_text_parts = [
        result.summary,
        *result.suggested_next_questions,
        *[
            " ".join([item.assessment, *item.evidence_gaps])
            for item in result.equity_dimensions
            if item.dimension != "technology_competition"
        ],
        *[
            " ".join(
                [
                    item.title,
                    item.premise,
                    item.outcome,
                    *[step.label for step in item.steps],
                    *item.counterarguments,
                    *item.evidence_gaps,
                ]
            )
            for item in result.hypotheses
        ],
    ]
    if result.paper_report is not None:
        report_text_parts.extend(
            [
                result.paper_report.title,
                result.paper_report.abstract,
                result.paper_report.conclusion,
            ]
        )
    foreign_subjects = (
        _foreign_equity_subjects(
            " ".join(report_text_parts),
            ticker=ticker,
            allowed_tickers=_allowed_equity_counterparty_tickers(
                evidence,
                ticker=ticker,
            ),
        )
        if ticker
        else []
    )
    valuation_quality_issues = [
        {
            "evidence_id": item.get("evidence_id"),
            "issues": issues,
        }
        for item in evidence.get("derived_equity_evidence", [])
        if isinstance(item, dict)
        and item.get("category") == "derived_company_valuation"
        and (issues := _valuation_anomalies(item))
    ]
    cutoff_value = context.get("point_in_time_cutoff")
    supply_cutoff_value = context.get("supply_chain_point_in_time_cutoff")
    try:
        cutoff = date.fromisoformat(str(cutoff_value)[:10]) if cutoff_value else None
    except ValueError:
        cutoff = None
    try:
        supply_cutoff = (
            date.fromisoformat(str(supply_cutoff_value)[:10]) if supply_cutoff_value else cutoff
        )
    except ValueError:
        supply_cutoff = cutoff
    future_refs = sorted(
        ref
        for ref in cited_refs
        if ref in evidence_index
        and (
            reference_cutoff := (
                supply_cutoff
                if evidence_index[ref].get("category") == "supply_chain_site_exposure"
                else cutoff
            )
        )
        is not None
        and (observed := _evidence_date(evidence_index[ref])) is not None
        and observed > reference_cutoff
    )

    paper = result.paper_report
    if paper is not None:
        paper.abstract = result.summary
        paper.findings = [
            item for item in paper.findings if not item.startswith("因子样本外审计：")
        ][:11]
        paper.findings.append(factor_statement)
        factor_limitation = (
            "所有当前交易因子均未形成经稳健性检验支持的正向样本外证据，"
            "不得据此给出确定买点或盈利承诺。"
        )
        paper.limitations = list(
            dict.fromkeys(
                [
                    factor_limitation,
                    *[item for item in paper.limitations if "所有当前交易因子" not in item],
                ]
            )
        )[:10]
        paper.conclusion = result.summary

    repairs = evidence.get("local_report_repairs")
    repairs = repairs if isinstance(repairs, list) else []
    material_issues = []
    if missing_refs:
        material_issues.append("cited_evidence_id_not_found")
    if headline_refs:
        material_issues.append("headline_only_evidence_used_for_validation")
    if future_refs:
        material_issues.append("citation_after_point_in_time_cutoff")
    if foreign_subjects:
        material_issues.append("foreign_company_subject_contamination")
    if valuation_quality_issues:
        material_issues.append("derived_valuation_arithmetic_anomaly")
    if rejected_company_refs:
        material_issues.append("off_subject_company_documents_removed")
    if not validated_alpha:
        material_issues.append("no_robust_out_of_sample_alpha_support")
    if data_readiness and not data_readiness.get("directional_conclusion_allowed"):
        material_issues.append("equity_data_readiness_gate_not_met")
    workflow_before_audit = evidence.get("research_workflow")
    workflow_before_audit = workflow_before_audit if isinstance(workflow_before_audit, dict) else {}
    openai_used = any(
        isinstance(item, dict)
        and item.get("stage") in {"openai_review", "openai_confirmation"}
        and item.get("status") == "completed"
        for item in workflow_before_audit.get("stages", [])
    )
    evidence["local_report_audit"] = {
        "audit_version": LOCAL_REPORT_AUDIT_VERSION,
        "audited_at": datetime.now(UTC).isoformat(),
        "status": (
            "data_quality_blocked"
            if missing_refs
            or headline_refs
            or future_refs
            or foreign_subjects
            or valuation_quality_issues
            else ("repaired_and_bounded" if repairs else "bounded")
        ),
        "openai_used": openai_used,
        "checks": {
            "cited_reference_count": len(cited_refs),
            "missing_reference_count": len(missing_refs),
            "headline_only_reference_count": len(headline_refs),
            "future_dated_reference_count": len(future_refs),
            "foreign_subject_count": len(foreign_subjects),
            "valuation_quality_issue_count": len(valuation_quality_issues),
            "off_subject_company_document_count": len(rejected_company_refs),
            "profit_validation_count": len(profit_validations),
            "profit_positive_count": profit_positive,
            "profit_negative_count": profit_negative,
            "cross_sectional_validation_count": len(cross_validations),
            "cross_sectional_negative_count": cross_negative,
            "robust_positive_count": robust_positive,
            "validated_alpha_supported": validated_alpha,
            "data_readiness_score": (data_readiness.get("score") if data_readiness else None),
            "data_readiness_status": (data_readiness.get("status") if data_readiness else None),
            "directional_conclusion_allowed": (
                data_readiness.get("directional_conclusion_allowed") if data_readiness else None
            ),
        },
        "missing_evidence_refs": missing_refs,
        "headline_only_evidence_refs": headline_refs,
        "future_dated_evidence_refs": future_refs,
        "foreign_subjects": foreign_subjects,
        "valuation_quality_issues": valuation_quality_issues,
        "off_subject_company_document_refs": rejected_company_refs,
        "repairs_applied": repairs,
        "material_findings": material_issues,
        "recommendation": (
            "defer_pending_data_repair"
            if missing_refs
            or headline_refs
            or future_refs
            or foreign_subjects
            or valuation_quality_issues
            else (
                "revised_accepted_for_research_defer_for_trade_decision"
                if repairs
                or not validated_alpha
                or (data_readiness and not data_readiness.get("directional_conclusion_allowed"))
                else "accepted_for_research_not_investment_advice"
            )
        ),
    }
    evidence["plain_language_report"] = _build_plain_language_report(
        result,
        evidence=evidence,
        directional_confidence=directional_confidence,
        validated_alpha=validated_alpha,
    )
    workflow = evidence.setdefault(
        "research_workflow",
        {"status": "local_report_audited", "stages": []},
    )
    stages = workflow.setdefault("stages", [])
    if isinstance(stages, list):
        stages[:] = [
            item
            for item in stages
            if not isinstance(item, dict) or item.get("stage") != "local_report_audit"
        ]
        stages.append(
            {
                "stage": "local_report_audit",
                "status": "completed",
                "auditor": LOCAL_REPORT_AUDIT_VERSION,
                "repair_count": len(repairs),
                "missing_reference_count": len(missing_refs),
                "future_dated_reference_count": len(future_refs),
                "foreign_subject_count": len(foreign_subjects),
                "valuation_quality_issue_count": len(valuation_quality_issues),
                "off_subject_company_document_count": len(rejected_company_refs),
                "validated_alpha_supported": validated_alpha,
            }
        )
    workflow["status"] = "local_report_audited"


def _directional_confidence_explanation(
    result: ModelResearchResult,
    *,
    validated_alpha: bool,
    data_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Explain conclusion support without presenting it as a price probability."""
    if not result.hypotheses:
        return {
            "score": None,
            "score_kind": "directional_chain_support_not_price_probability",
            "components": [],
            "blockers_zh": ["当前报告没有可拆解的方向链。"],
            "blockers_en": ["The report has no directional chain to decompose."],
        }
    hypothesis = result.hypotheses[0]
    components = [
        {
            "sequence": step.sequence,
            "label": step.label,
            "status": step.status,
            "score": round(float(step.confidence), 4),
            "weight": round(1 / len(hypothesis.steps), 4),
            "evidence_count": len(step.evidence_refs),
        }
        for step in hypothesis.steps
    ]
    raw_score = round(
        sum(item["score"] for item in components) / len(components),
        2,
    )
    readiness_cap = (
        float(data_readiness.get("confidence_cap"))
        if data_readiness and data_readiness.get("confidence_cap") is not None
        else 0.75
    )
    score = round(min(raw_score, readiness_cap), 2)
    hypothesis.confidence = score
    unresolved = sum(item["status"] in {"hypothesis", "evidence_missing"} for item in components)
    partial = sum(item["status"] == "partially_supported" for item in components)
    blockers_zh: list[str] = []
    blockers_en: list[str] = []
    if unresolved:
        blockers_zh.append(f"{unresolved}个环节仍是待验证假设或缺少证据。")
        blockers_en.append(f"{unresolved} links remain hypothetical or evidence-missing.")
    if partial:
        blockers_zh.append(f"{partial}个环节只有部分支持，尚未验证完整传导。")
        blockers_en.append(f"{partial} links have only partial support.")
    if not validated_alpha:
        blockers_zh.append("样本外与稳健性检验没有支持可盈利方向信号。")
        blockers_en.append(
            "Out-of-sample robustness does not support a profitable direction signal."
        )
    if data_readiness and not data_readiness.get("directional_conclusion_allowed"):
        missing = ", ".join(str(item) for item in data_readiness.get("missing_required", []))
        blockers_zh.append(f"公司数据完整度门控未通过：{missing or '关键证据仍不完整'}。")
        blockers_en.append(
            "The issuer data-readiness gate did not pass: "
            f"{missing or 'required evidence remains incomplete'}."
        )
    readiness_components = (
        data_readiness.get("components", []) if isinstance(data_readiness, dict) else []
    )
    product_component = next(
        (
            item
            for item in readiness_components
            if isinstance(item, dict) and item.get("key") == "product_operating_evidence"
        ),
        None,
    )
    product_evidence_available = bool(
        isinstance(product_component, dict) and float(product_component.get("score") or 0) > 0
    )
    return {
        "score": score,
        "raw_chain_score": raw_score,
        "data_readiness_cap": readiness_cap,
        "data_readiness_score": (data_readiness.get("score") if data_readiness else None),
        "directional_conclusion_allowed": (
            data_readiness.get("directional_conclusion_allowed") if data_readiness else None
        ),
        "score_kind": "directional_chain_support_not_price_probability",
        "formula": "equal_weight_mean_of_step_support_scores",
        "components": components,
        "verified_steps": sum(item["status"] == "verified" for item in components),
        "partially_supported_steps": partial,
        "unresolved_steps": unresolved,
        "validated_alpha_supported": validated_alpha,
        "blockers_zh": blockers_zh,
        "blockers_en": blockers_en,
        "improvement_actions_zh": [
            (
                "继续补齐绝对单位产品销量/ASP、份额、客户级合同与产品盈利贡献。"
                if product_evidence_available
                else "补齐产品级销量、价格、份额、合同与盈利贡献。"
            ),
            "补齐经来源审核的供应商—工厂—产能—物流—灾害关系。",
            "用严格时间切分的样本外数据重新检验方向因子。",
        ],
        "improvement_actions_en": [
            (
                "Extend the filing evidence with absolute product units/ASP, share, "
                "customer-level contracts and product profit contribution."
                if product_evidence_available
                else "Add product-level volume, pricing, share, contract and profit evidence."
            ),
            "Add source-reviewed supplier, facility, capacity, logistics and hazard links.",
            "Retest directional factors with strict chronological out-of-sample data.",
        ],
    }


def _repair_zero_confidence_fallback_forecasts(
    result: ModelResearchResult,
    *,
    evidence: dict[str, Any],
    directional_confidence: dict[str, Any],
) -> int:
    """Fill only system fallback forecasts from the final audited chain score."""
    score = directional_confidence.get("score")
    if not isinstance(score, (int, float)) or score <= 0:
        return 0
    allowed_refs = _evidence_ids(evidence)
    repaired = 0
    for forecast in result.news_forecasts:
        if forecast.confidence > 0:
            continue
        if "low-confidence fallback hypothesis" not in forecast.hypothesis:
            continue
        if forecast.anchor_evidence_ref not in allowed_refs:
            continue
        forecast.confidence = min(float(score), 0.3)
        repaired += 1
    return repaired


def _build_plain_language_report(
    result: ModelResearchResult,
    *,
    evidence: dict[str, Any],
    directional_confidence: dict[str, Any],
    validated_alpha: bool,
) -> dict[str, Any]:
    context = evidence.get("equity_research_context")
    context = context if isinstance(context, dict) else {}
    ticker = str(context.get("ticker") or "")
    company = str(context.get("company") or ticker or "本次研究对象")
    score = directional_confidence.get("score")
    score_label = f"{round(float(score) * 100)}%" if isinstance(score, (int, float)) else "—"
    observed_series = {
        str(item.get("series_id"))
        for item in evidence.get("market_observations", [])
        if isinstance(item, dict) and item.get("series_id")
    }
    for item in evidence.get("derived_equity_evidence", []):
        if not isinstance(item, dict) or item.get("category") != "derived_macro_sensitivity":
            continue
        observed_series.update(
            str(sensitivity.get("series_id"))
            for sensitivity in item.get("sensitivities", [])
            if isinstance(sensitivity, dict) and sensitivity.get("series_id")
        )
    glossary_ids = [
        key
        for key in RESEARCH_TERM_GLOSSARY
        if key in observed_series or key in {"13F", "FORM4", "TTM", "SMA_MACD_RSI"}
    ]
    terms = [{"term": term, **RESEARCH_TERM_GLOSSARY[term]} for term in glossary_ids]
    audit = evidence.get("local_report_audit")
    audit = audit if isinstance(audit, dict) else {}
    checks = audit.get("checks") if isinstance(audit.get("checks"), dict) else {}
    citation_clean = not any(
        int(checks.get(key) or 0)
        for key in (
            "missing_reference_count",
            "headline_only_reference_count",
            "future_dated_reference_count",
            "foreign_subject_count",
            "valuation_quality_issue_count",
        )
    )
    product_evidence = [
        item
        for item in evidence.get("derived_equity_evidence", [])
        if isinstance(item, dict) and item.get("category") == "product_operating_evidence"
    ]
    product_actuals = [
        item for item in product_evidence if item.get("evidence_status") == "reported_actual"
    ]
    return {
        "title_zh": "通俗版结论与术语说明",
        "title_en": "Plain-Language Conclusion and Term Guide",
        "summary_zh": (
            f"这份报告已经把{company}{f'（{ticker}）' if ticker else ''}的已知财务、价格、"
            "持仓和宏观数据对齐"
            + (
                f"，并从年报原文加入{len(product_actuals)}条已报告产品经营事实"
                if product_actuals
                else ""
            )
            + "，但仍不能据此断言未来一定上涨或给出确定买点。"
        ),
        "summary_en": (
            f"The report aligns the known financial, price, positioning and macro data for "
            f"{company}{f' ({ticker})' if ticker else ''}"
            + (
                f" and includes {len(product_actuals)} reported product-operating facts "
                "from the annual filing"
                if product_actuals
                else ""
            )
            + ", but it still cannot establish a certain "
            "future rise or a definitive entry point."
        ),
        "product_evidence_note_zh": (
            f"产品经营证据共{len(product_evidence)}条：{len(product_actuals)}条已报告结果，"
            f"{sum(item.get('evidence_status') == 'forward_looking_plan' for item in product_evidence)}"
            "条"
            "前瞻计划；计划不会被当作已经实现。"
            if product_evidence
            else "尚未从年报原文提取到产品经营证据。"
        ),
        "product_evidence_note_en": (
            f"The report retains {len(product_evidence)} product-operating excerpts, including "
            f"{len(product_actuals)} reported actuals; forward-looking plans are not "
            "treated as realized."
            if product_evidence
            else "No product-operating evidence has yet been extracted from an annual filing."
        ),
        "confidence_note_zh": (
            f"页面上的{score_label}表示“方向证据链支持度”，不是股价上涨概率。"
            "分数由各环节证据强度等权计算；缺失的供应链数据和未通过的样本外检验会拉低它。"
        ),
        "confidence_note_en": (
            f"The displayed {score_label} is directional-chain support, not the probability of a "
            "price rise. It averages link-level evidence strength and is reduced by missing supply-chain "
            "data and unsupported out-of-sample tests."
        ),
        "data_quality_zh": (
            "当前引用与时间边界检查通过。"
            if citation_clean
            else "当前仍有引用或数据质量问题需要修复。"
        ),
        "data_quality_en": (
            "Citation and time-boundary checks currently pass."
            if citation_clean
            else "Citation or data-quality issues still require repair."
        ),
        "trade_signal_zh": (
            "存在经稳健性复核的探索性正向信号，但不构成收益保证。"
            if validated_alpha
            else "当前没有经稳健性复核支持的盈利或买点信号。"
        ),
        "trade_signal_en": (
            "A positive exploratory signal survived robustness review, but it is not a return guarantee."
            if validated_alpha
            else "No profitable or entry-timing signal is currently supported by robustness review."
        ),
        "terms": terms,
    }


def _evidence_ids(evidence: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for value in evidence.values():
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, dict) and isinstance(item.get("evidence_id"), str):
                result.add(item["evidence_id"])
    return result


def _compact_evidence(
    evidence: dict[str, Any],
    *,
    max_chars: int,
) -> dict[str, Any]:
    """Keep a balanced provider sample instead of truncating later categories."""
    list_limits = {
        "priority_evidence": 36,
        "documents": 14,
        "news_evidence_sequences": 6,
        "news_forecast_anchors": 8,
        "forecast_validation_cases": 8,
        "forecast_validation_runs": 6,
        "events": 16,
        "historical_anchors": 32,
        "episode_candidates": 16,
        "economic_observations": 16,
        "market_observations": 24,
        "market_window_statistics": 18,
        "market_data_quality": 18,
        "company_financials": 20,
        "derived_equity_evidence": 16,
        "energy_observations": 16,
        "conflict_hotspots": 20,
        "data_coverage": 16,
        "prior_research_questions": 12,
        "planned_question_evidence_refs": 8,
        "historical_context_refs": 6,
        "evidence_retrieval": 4,
        "verified_logic_memory": 6,
    }
    compact: dict[str, Any] = {
        key: value
        for key, value in evidence.items()
        if not isinstance(value, list) and key != "bridge_evidence_completion"
    }
    completion = evidence.get("bridge_evidence_completion")
    if isinstance(completion, dict):
        compact["bridge_evidence_completion"] = {
            key: completion.get(key)
            for key in (
                "generated_at",
                "window_start",
                "window_end",
                "segment_count",
                "candidate_data_segments",
                "rejected_anomaly_segments",
                "missing_segments",
                "added_evidence_refs",
            )
        }
        compact["bridge_evidence_completion"]["segments"] = [
            {
                **{
                    key: segment.get(key)
                    for key in (
                        "hypothesis_index",
                        "sequence",
                        "source",
                        "target",
                        "status",
                        "missing_data",
                    )
                },
                "candidates": [
                    {
                        "series_id": candidate.get("series_id"),
                        "name": candidate.get("name"),
                        "evidence_refs": candidate.get("evidence_refs", []),
                        "quality": {
                            key: (candidate.get("quality") or {}).get(key)
                            for key in (
                                "quality_score",
                                "can_verify_claims",
                                "flags",
                                "observation_count",
                                "first_observed_on",
                                "last_observed_on",
                            )
                        },
                    }
                    for candidate in segment.get("candidates", [])[:4]
                    if isinstance(candidate, dict)
                ],
            }
            for segment in completion.get("segments", [])[:16]
            if isinstance(segment, dict)
        ]
    event_table = evidence.get("research_event_table")
    if isinstance(event_table, dict):
        compact["research_event_table"] = {
            key: event_table.get(key)
            for key in (
                "reliable_start",
                "reliable_end",
                "structured_start",
                "cross_domain_start",
                "media_rich_start",
                "current_open_period",
                "methodology",
            )
        }
    for key, limit in list_limits.items():
        values = evidence.get(key)
        compact[key] = (
            [dict(item) if isinstance(item, dict) else item for item in values[:limit]]
            if isinstance(values, list)
            else []
        )
    for item in compact["documents"]:
        if isinstance(item, dict) and isinstance(item.get("excerpt"), str):
            item["excerpt"] = item["excerpt"][:260]
    categories = list(list_limits)
    while len(json.dumps(compact, ensure_ascii=False)) > max_chars:
        changed = False
        for key in categories:
            values = compact[key]
            if len(values) > 3:
                values.pop()
                changed = True
        if not changed:
            break
    return compact


def _text_relevance(text: str, question: str) -> int:
    if not question:
        return 0
    haystack = text.casefold()
    latin_haystack = set(re.findall(r"[a-z0-9][a-z0-9._/-]{1,}", haystack))
    tokens = set(re.findall(r"[a-z0-9][a-z0-9._/-]{2,}|[\u4e00-\u9fff]{2,8}", question.casefold()))
    return sum(
        1 for token in tokens if (token in latin_haystack if token.isascii() else token in haystack)
    )


def _unique_document_rows(
    rows: list[tuple[Document, Source]],
    *,
    limit: int,
) -> list[tuple[Document, Source]]:
    result: list[tuple[Document, Source]] = []
    seen: set[int] = set()
    for row in rows:
        if row[0].id in seen:
            continue
        seen.add(row[0].id)
        result.append(row)
        if len(result) >= limit:
            break
    return result


def _unique_events(rows: list[Event], *, limit: int) -> list[Event]:
    result: list[Event] = []
    seen: set[int] = set()
    for row in rows:
        if row.id in seen:
            continue
        seen.add(row.id)
        result.append(row)
        if len(result) >= limit:
            break
    return result


def _unique_economic_rows(
    rows: list[tuple[EconomicObservation, EconomicIndicator, CountryProfile]],
    *,
    limit: int,
) -> list[tuple[EconomicObservation, EconomicIndicator, CountryProfile]]:
    result: list[tuple[EconomicObservation, EconomicIndicator, CountryProfile]] = []
    seen: set[tuple[str, str, int]] = set()
    for row in rows:
        key = (row[0].country_iso3, row[0].indicator_code, row[0].year)
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
        if len(result) >= limit:
            break
    return result


def _build_historical_anchors(
    evidence: dict[str, Any],
    *,
    focus: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Select real evidence across years before the model is allowed to ask."""
    by_year: dict[int, list[dict[str, Any]]] = {}
    by_series: dict[str, list[dict[str, Any]]] = {}
    for values in evidence.values():
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict) or not isinstance(item.get("evidence_id"), str):
                continue
            year = _evidence_year(item)
            if year is None:
                continue
            by_year.setdefault(year, []).append(item)
            identity = _historical_series_identity(item)
            if identity:
                by_series.setdefault(identity, []).append(item)
    for values in by_year.values():
        values.sort(
            key=lambda item: _text_relevance(
                json.dumps(item, ensure_ascii=False),
                focus,
            ),
            reverse=True,
        )
    anchors: list[dict[str, Any]] = []
    seen: set[str] = set()

    def append_anchor(item: dict[str, Any]) -> None:
        evidence_id = item["evidence_id"]
        if evidence_id in seen or len(anchors) >= limit:
            return
        anchor = dict(item)
        anchor["observation_year"] = _evidence_year(item)
        anchors.append(anchor)
        seen.add(evidence_id)

    longitudinal_groups = [
        rows
        for rows in by_series.values()
        if len(rows) >= 2
        and max(_evidence_year(item) or 0 for item in rows)
        - min(_evidence_year(item) or 0 for item in rows)
        >= 3
    ]
    longitudinal_groups.sort(
        key=lambda rows: (
            _text_relevance(json.dumps(rows, ensure_ascii=False), focus),
            max(_evidence_year(item) or 0 for item in rows)
            - min(_evidence_year(item) or 0 for item in rows),
        ),
        reverse=True,
    )
    # Reserve half the prompt budget for auditable oldest/latest comparisons
    # from the same retained series. This makes evidence-first planning robust.
    for rows in longitudinal_groups[: max(1, limit // 4)]:
        append_anchor(min(rows, key=lambda item: _evidence_year(item) or 9999))
        append_anchor(max(rows, key=lambda item: _evidence_year(item) or 0))
        if len(anchors) >= limit // 2:
            break

    for year in sorted(by_year, reverse=True):
        append_anchor(by_year[year][0])
        if len(anchors) >= limit:
            return anchors
    remaining = sorted(
        (item for values in by_year.values() for item in values[1:]),
        key=lambda item: _text_relevance(
            json.dumps(item, ensure_ascii=False),
            focus,
        ),
        reverse=True,
    )
    for item in remaining:
        append_anchor(item)
        if len(anchors) >= limit:
            break
    return anchors


def _historical_series_identity(item: dict[str, Any]) -> str:
    category = str(item.get("category") or "")
    if item.get("series_id"):
        return f"{category}:series:{item['series_id']}"
    if item.get("indicator_code"):
        country = item.get("country") or item.get("country_iso3") or "global"
        return f"{category}:indicator:{country}:{item['indicator_code']}"
    if item.get("ticker") and item.get("concept"):
        return f"{category}:company:{item['ticker']}:{item['concept']}"
    return ""


def _evidence_year(item: dict[str, Any]) -> int | None:
    year = item.get("year") or item.get("observation_year")
    if isinstance(year, int) and 1800 <= year <= 2200:
        return year
    for key in (
        "published_at",
        "occurred_at",
        "observed_on",
        "period_end",
        "period_start",
        "period",
    ):
        value = item.get(key)
        if not isinstance(value, str):
            continue
        match = re.search(r"(?:18|19|20|21)\d{2}", value)
        if match:
            return int(match.group(0))
    return None


def _evidence_date(item: dict[str, Any]) -> date | None:
    """Return the best retained observation date without inventing precision."""
    for key in (
        "published_at",
        "occurred_at",
        "observed_on",
        "period_end",
        "period_start",
        "period",
    ):
        value = item.get(key)
        if not isinstance(value, str):
            continue
        match = re.match(r"((?:18|19|20|21)\d{2})-(\d{2})-(\d{2})", value)
        if match:
            try:
                return date(*(int(part) for part in match.groups()))
            except ValueError:
                continue
        year_match = re.search(r"(?:18|19|20|21)\d{2}", value)
        if year_match:
            return date(int(year_match.group(0)), 1, 1)
    year = item.get("year") or item.get("observation_year")
    if isinstance(year, int) and 1800 <= year <= 2200:
        return date(year, 1, 1)
    return None


def _evidence_geography_key(item: dict[str, Any]) -> str:
    """Return a conservative geography key for autonomous pair validation."""
    for key in ("country_iso3", "country_code", "country"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            normalized = value.strip().casefold()
            if normalized in {"us", "usa", "united states", "united states of america"}:
                return "usa"
            return normalized
    text = " ".join(
        str(item.get(key) or "") for key in ("name", "title", "indicator", "source")
    ).casefold()
    if re.search(r"(?:\bu\.s\.|\bunited states\b|\bfederal reserve\b)", text):
        return "usa"
    return ""


def _compatible_evidence_geography(
    premise: dict[str, Any],
    outcome: dict[str, Any],
) -> bool:
    premise_key = _evidence_geography_key(premise)
    outcome_key = _evidence_geography_key(outcome)
    return not premise_key or not outcome_key or premise_key == outcome_key


def _build_episode_candidates(
    evidence: dict[str, Any],
    *,
    focus: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Build bounded event-study windows across old and recent retained data."""
    event_table = evidence.get("research_event_table")
    eligible_years = {
        int(year)
        for year in (event_table.get("eligible_years", []) if isinstance(event_table, dict) else [])
    }
    preferred_period = evidence.get("preferred_research_period")
    preferred_year = (
        int(preferred_period["year"])
        if isinstance(preferred_period, dict) and isinstance(preferred_period.get("year"), int)
        else None
    )
    period_by_year = {
        int(item["year"]): item
        for item in (event_table.get("periods", []) if isinstance(event_table, dict) else [])
        if isinstance(item, dict) and isinstance(item.get("year"), int)
    }
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for section in (
        "documents",
        "events",
        "market_observations",
        "company_financials",
        "economic_observations",
        "energy_observations",
    ):
        for item in evidence.get(section, []):
            if not isinstance(item, dict):
                continue
            evidence_id = item.get("evidence_id")
            if (
                not isinstance(evidence_id, str)
                or evidence_id in seen
                or _evidence_date(item) is None
            ):
                continue
            observed = _evidence_date(item)
            if observed is None or (eligible_years and observed.year not in eligible_years):
                continue
            candidate_item = dict(item)
            candidate_item["episode_section"] = section
            if not _financial_episode_relevance(candidate_item):
                continue
            items.append(candidate_item)
            seen.add(evidence_id)
    if len(items) < 2:
        return []
    items.sort(
        key=lambda item: _text_relevance(json.dumps(item, ensure_ascii=False), focus),
        reverse=True,
    )
    seeds: list[dict[str, Any]] = []
    available_years = sorted(
        {observed.year for item in items if (observed := _evidence_date(item)) is not None}
    )
    if preferred_year in available_years:
        available_years.remove(preferred_year)
        available_years.insert(0, preferred_year)
    for year in available_years:
        yearly_items = [item for item in items if (_evidence_date(item) or date.min).year == year]
        if yearly_items:
            seeds.append(yearly_items[0])
    seeds.extend(item for item in items if item not in seeds)

    candidates: list[dict[str, Any]] = []
    signatures: set[tuple[str, ...]] = set()
    for seed in seeds:
        seed_date = _evidence_date(seed)
        if seed_date is None:
            continue
        lower = seed_date - timedelta(days=45)
        upper = seed_date + timedelta(days=365)
        neighbours = [
            item for item in items if lower <= (_evidence_date(item) or date.min) <= upper
        ]
        neighbours.sort(
            key=lambda item: (
                item["evidence_id"] == seed["evidence_id"],
                item.get("episode_section") != seed.get("episode_section"),
                _text_relevance(json.dumps(item, ensure_ascii=False), focus),
            ),
            reverse=True,
        )
        retained = [seed]
        retained_sections = {str(seed.get("episode_section") or "")}
        for item in neighbours:
            section = str(item.get("episode_section") or "")
            if item["evidence_id"] == seed["evidence_id"] or section in retained_sections:
                continue
            retained.append(item)
            retained_sections.add(section)
            if len(retained) >= 8:
                break
        for item in neighbours:
            if item in retained:
                continue
            retained.append(item)
            if len(retained) >= 8:
                break
        if len(retained) < 2:
            nearest = sorted(
                (item for item in items if item is not seed),
                key=lambda item: abs(((_evidence_date(item) or date.min) - seed_date).days),
            )
            if nearest and abs(((_evidence_date(nearest[0]) or date.min) - seed_date).days) <= 549:
                retained.append(nearest[0])
        if len(retained) < 2:
            continue
        if not any(item.get("episode_section") in STRUCTURED_EPISODE_SECTIONS for item in retained):
            continue
        retained_dates = [
            observed for item in retained if (observed := _evidence_date(item)) is not None
        ]
        start = min(retained_dates)
        end = max(retained_dates)
        if (end - start).days > 549:
            retained = [
                item
                for item in retained
                if abs(((_evidence_date(item) or seed_date) - seed_date).days) <= 274
            ]
            retained_dates = [
                observed for item in retained if (observed := _evidence_date(item)) is not None
            ]
            start = min(retained_dates)
            end = max(retained_dates)
        if (end - start).days < 6:
            end = start + timedelta(days=6)
        signature = tuple(sorted(str(item["evidence_id"]) for item in retained))
        if signature in signatures:
            continue
        signatures.add(signature)
        covered_years = sorted(set(range(start.year, end.year + 1)))
        period_rows = [period_by_year[year] for year in covered_years if year in period_by_year]
        coverage_score = (
            min(float(item.get("coverage_score") or 0) for item in period_rows)
            if period_rows
            else 0.0
        )
        evidence_domains = (
            min(int(item.get("evidence_domains") or 0) for item in period_rows)
            if period_rows
            else 0
        )
        evidence_sections = sorted(
            {str(item.get("episode_section")) for item in retained if item.get("episode_section")}
        )
        narrative_evidence_count = sum(
            item.get("episode_section") not in STRUCTURED_EPISODE_SECTIONS for item in retained
        )
        substantive_document_count = sum(
            item.get("episode_section") == "documents"
            and len(str(item.get("excerpt") or "").strip()) >= 120
            for item in retained
        )
        candidates.append(
            {
                "episode_start": start.isoformat(),
                "episode_end": end.isoformat(),
                "duration_days": (end - start).days + 1,
                "coverage_score": round(coverage_score, 3),
                "evidence_domains": evidence_domains,
                "evidence_sections": evidence_sections,
                "evidence_section_count": len(evidence_sections),
                "narrative_evidence_count": narrative_evidence_count,
                "substantive_document_count": substantive_document_count,
                "closed_complete_period": bool(
                    not eligible_years or all(year in eligible_years for year in covered_years)
                ),
                "preferred_period_overlap": preferred_year in covered_years,
                "evidence_refs": list(signature),
                "items": retained,
            }
        )
        if len(candidates) >= max(limit, len(available_years) + 6):
            break
    candidates.sort(
        key=lambda candidate: (
            bool(candidate.get("preferred_period_overlap")),
            int(candidate.get("substantive_document_count") or 0) > 0,
            int(candidate.get("narrative_evidence_count") or 0),
            int(candidate.get("evidence_section_count") or 0),
            float(candidate.get("coverage_score") or 0),
            int(candidate.get("evidence_domains") or 0),
            _text_relevance(json.dumps(candidate, ensure_ascii=False), focus),
        ),
        reverse=True,
    )
    return candidates[:limit]


def _financial_episode_relevance(item: dict[str, Any]) -> int:
    """Reject records that are only temporally close to a financial episode."""
    return _text_relevance(
        json.dumps(item, ensure_ascii=False),
        FINANCIAL_EPISODE_TERMS,
    )


def _valid_episode_trigger(item: dict[str, Any]) -> bool:
    """Require a plausible policy, market, commodity or physical-supply shock."""
    if item.get("episode_section") in STRUCTURED_EPISODE_SECTIONS:
        return _financial_episode_relevance(item) > 0
    return (
        _text_relevance(
            json.dumps(item, ensure_ascii=False),
            CAUSAL_TRIGGER_TERMS,
        )
        > 0
    )


def _validate_planned_question_evidence(
    planned: PlannedResearchQuestion,
    *,
    episode_candidates: Any,
    historical_anchors: Any,
    research_event_table: Any = None,
    preferred_research_period: Any = None,
) -> None:
    if not isinstance(episode_candidates, list):
        raise ValueError("episode candidates are unavailable")
    episode_items = {
        item["evidence_id"]: item
        for candidate in episode_candidates
        if isinstance(candidate, dict)
        for item in candidate.get("items", [])
        if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
    }
    trigger_refs = list(dict.fromkeys(planned.trigger_evidence_refs))
    outcome_refs = list(dict.fromkeys(planned.outcome_evidence_refs))
    all_episode_refs = list(dict.fromkeys([*trigger_refs, *outcome_refs]))
    if (
        not trigger_refs
        or not outcome_refs
        or len(all_episode_refs) < 2
        or any(ref not in episode_items for ref in all_episode_refs)
    ):
        raise ValueError("episode needs retained trigger and outcome evidence")
    duration_days = (planned.episode_end - planned.episode_start).days + 1
    if not 7 <= duration_days <= 550:
        raise ValueError("episode window must be between 7 and 550 days")
    if isinstance(research_event_table, dict):
        reliable_start_value = research_event_table.get("reliable_start")
        reliable_end_value = research_event_table.get("reliable_end")
        if reliable_start_value and planned.episode_start < date.fromisoformat(
            str(reliable_start_value)
        ):
            raise ValueError("episode starts before the reliable research window")
        if reliable_end_value and planned.episode_end > date.fromisoformat(str(reliable_end_value)):
            raise ValueError("open or incomplete periods are monitoring-only")
        eligible_years = {int(year) for year in research_event_table.get("eligible_years", [])}
        selected_years = set(range(planned.episode_start.year, planned.episode_end.year + 1))
        if eligible_years and not selected_years.issubset(eligible_years):
            raise ValueError("episode crosses a period below the coverage threshold")
    if isinstance(preferred_research_period, dict) and isinstance(
        preferred_research_period.get("year"), int
    ):
        preferred_year = int(preferred_research_period["year"])
        has_preferred_candidate = any(
            isinstance(candidate, dict) and candidate.get("preferred_period_overlap")
            for candidate in episode_candidates
        )
        if has_preferred_candidate and not (
            planned.episode_start.year <= preferred_year <= planned.episode_end.year
        ):
            raise ValueError("episode does not use the preferred complete period")
    for ref in all_episode_refs:
        observed = _evidence_date(episode_items[ref])
        if observed is None or observed < planned.episode_start or observed > planned.episode_end:
            raise ValueError("episode evidence falls outside the selected window")
    if not any(
        episode_items[ref].get("episode_section") in STRUCTURED_EPISODE_SECTIONS
        for ref in outcome_refs
    ):
        raise ValueError("outcome must cite a structured financial observation")
    if any(not _valid_episode_trigger(episode_items[ref]) for ref in trigger_refs):
        raise ValueError("trigger is not a causal policy, market or supply shock")
    trigger_subjects = {evidence_subject_key(episode_items[ref]) for ref in trigger_refs}
    outcome_subjects = {evidence_subject_key(episode_items[ref]) for ref in outcome_refs}
    if trigger_subjects & outcome_subjects:
        raise ValueError("the same measured series cannot be both cause and outcome")
    trigger_geographies = {
        key for ref in trigger_refs if (key := _evidence_geography_key(episode_items[ref]))
    }
    outcome_geographies = {
        key for ref in outcome_refs if (key := _evidence_geography_key(episode_items[ref]))
    }
    if (
        trigger_geographies
        and outcome_geographies
        and trigger_geographies.isdisjoint(outcome_geographies)
    ):
        raise ValueError("episode pairs observations from unrelated geographies")
    if any(_financial_episode_relevance(episode_items[ref]) == 0 for ref in all_episode_refs):
        raise ValueError("episode evidence is only temporally, not financially, related")
    bridge_hypotheses = list(
        dict.fromkeys(value.strip() for value in planned.bridge_hypotheses if value.strip())
    )[:5]
    if planned.relationship_mode == "nonlinear_exploratory" and len(bridge_hypotheses) < 2:
        raise ValueError("nonlinear exploration requires at least two measurable bridge hypotheses")
    historical_ids = (
        {
            item["evidence_id"]
            for item in historical_anchors
            if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
        }
        if isinstance(historical_anchors, list)
        else set()
    )
    historical_refs = list(dict.fromkeys(planned.historical_context_refs))[:6]
    if any(ref not in historical_ids for ref in historical_refs):
        raise ValueError("historical context reference was not retained")
    question_years = [int(value) for value in re.findall(r"(?:18|19|20|21)\d{2}", planned.question)]
    if question_years and max(question_years) - min(question_years) > 2:
        raise ValueError("question improperly expands the bounded episode")
    planned.trigger_evidence_refs = trigger_refs
    planned.outcome_evidence_refs = outcome_refs
    planned.historical_context_refs = historical_refs
    planned.bridge_hypotheses = bridge_hypotheses


def _fallback_episode_question_plan(
    *,
    episode_candidates: Any,
    historical_anchors: Any,
    focus: str,
    prohibited_questions: Any = None,
    preferred_research_period: Any = None,
) -> PlannedResearchQuestion:
    """Recover with one bounded retained episode, never an all-history range."""
    if not isinstance(episode_candidates, list):
        raise ValueError("episode candidates are unavailable")
    retained_historical_refs = (
        [
            item["evidence_id"]
            for item in historical_anchors
            if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
        ][:4]
        if isinstance(historical_anchors, list)
        else []
    )
    preferred_year = (
        int(preferred_research_period["year"])
        if isinstance(preferred_research_period, dict)
        and isinstance(preferred_research_period.get("year"), int)
        else None
    )

    def preferred_overlap(candidate: dict[str, Any]) -> bool:
        if candidate.get("preferred_period_overlap"):
            return True
        if preferred_year is None:
            return False
        try:
            return (
                date.fromisoformat(str(candidate["episode_start"])).year
                <= preferred_year
                <= date.fromisoformat(str(candidate["episode_end"])).year
            )
        except (KeyError, ValueError):
            return False

    ranked = sorted(
        (item for item in episode_candidates if isinstance(item, dict)),
        key=lambda candidate: (
            preferred_overlap(candidate),
            int(candidate.get("substantive_document_count") or 0) > 0,
            int(candidate.get("narrative_evidence_count") or 0),
            int(candidate.get("evidence_section_count") or 0),
            float(candidate.get("coverage_score") or 0),
            int(candidate.get("evidence_domains") or 0),
            _text_relevance(
                json.dumps(candidate, ensure_ascii=False),
                focus,
            ),
        ),
        reverse=True,
    )
    for candidate in ranked:
        items = [item for item in candidate.get("items", []) if isinstance(item, dict)]
        if len(items) < 2:
            continue
        items.sort(key=lambda item: _evidence_date(item) or date.min)
        pairs = [
            (trigger, outcome)
            for trigger in items
            for outcome in items
            if trigger["evidence_id"] != outcome["evidence_id"]
            and _valid_episode_trigger(trigger)
            and outcome.get("episode_section") in STRUCTURED_EPISODE_SECTIONS
            and evidence_subject_key(trigger) != evidence_subject_key(outcome)
            and _compatible_evidence_geography(trigger, outcome)
            and (_evidence_date(outcome) or date.min) >= (_evidence_date(trigger) or date.min)
        ]
        if not pairs:
            continue
        trigger, outcome = max(
            pairs,
            key=lambda pair: (
                pair[0].get("episode_section") not in STRUCTURED_EPISODE_SECTIONS,
                len(str(pair[0].get("excerpt") or "").strip()) >= 120,
                _text_relevance(json.dumps(pair[0], ensure_ascii=False), focus),
                _text_relevance(json.dumps(pair[1], ensure_ascii=False), focus),
                _evidence_date(pair[1]) or date.min,
            ),
        )
        start = date.fromisoformat(str(candidate["episode_start"]))
        end = date.fromisoformat(str(candidate["episode_end"]))
        trigger_label = str(
            trigger.get("title")
            or trigger.get("name")
            or trigger.get("indicator")
            or trigger.get("series_id")
            or "the trigger event"
        )[:160]
        outcome_label = str(
            outcome.get("title")
            or outcome.get("name")
            or outcome.get("indicator")
            or outcome.get("series_id")
            or "the measured outcome"
        )[:160]
        question = (
            f"在 {start.isoformat()} 至 {end.isoformat()} 的特定事件窗口内，"
            f"{trigger_label} 是否通过可验证的中间机制影响了 {outcome_label}，"
            "还是替代解释更强？"
        )
        if _duplicates_prior_question(question, prohibited_questions):
            continue
        return PlannedResearchQuestion(
            question=question,
            episode_start=start,
            episode_end=end,
            trigger_evidence_refs=[str(trigger["evidence_id"])],
            outcome_evidence_refs=[str(outcome["evidence_id"])],
            historical_context_refs=retained_historical_refs,
            relationship_mode="nonlinear_exploratory",
            bridge_hypotheses=[
                "共同宏观状态、信用条件或风险偏好是否跨过传导阈值",
                "采购融资、库存或进口需求是否发生可测变化",
                "汇率、运费或贸易流量是否把变化传至最终价格",
            ],
        )
    raise ValueError("every retained bounded episode duplicates prior research")


def _fallback_historical_question_plan(
    *,
    historical_anchors: Any,
    focus: str,
    prohibited_questions: Any = None,
) -> PlannedResearchQuestion:
    """Recover from malformed model output without inventing an evidence base."""
    if not isinstance(historical_anchors, list):
        raise ValueError("historical anchors are unavailable")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in historical_anchors:
        if not isinstance(item, dict) or _evidence_year(item) is None:
            continue
        identity = _historical_series_identity(item)
        if not identity:
            continue
        grouped.setdefault(identity, []).append(item)
    eligible = [
        rows
        for rows in grouped.values()
        if len(rows) >= 2
        and max(_evidence_year(item) or 0 for item in rows)
        - min(_evidence_year(item) or 0 for item in rows)
        >= 3
    ]
    if not eligible:
        raise ValueError("no retained series spans at least three years")
    eligible.sort(
        key=lambda items: (
            _text_relevance(
                json.dumps(items, ensure_ascii=False),
                focus,
            ),
            max(_evidence_year(item) or 0 for item in items)
            - min(_evidence_year(item) or 0 for item in items),
        ),
        reverse=True,
    )
    for rows in eligible:
        oldest = min(rows, key=lambda item: _evidence_year(item) or 9999)
        newest = max(rows, key=lambda item: _evidence_year(item) or 0)
        start_year = _evidence_year(oldest)
        end_year = _evidence_year(newest)
        if start_year is None or end_year is None:
            continue
        label = str(
            newest.get("name")
            or newest.get("indicator")
            or newest.get("series_id")
            or newest.get("ticker")
        )
        question = (
            f"从{start_year}—{end_year}年的{label}历史样本看，当前变化相对长期区间"
            "是否显著，并可能如何影响未来六个月的金融条件与资产估值？"
        )
        if _duplicates_prior_question(question, prohibited_questions):
            continue
        return PlannedResearchQuestion(
            question=question,
            episode_start=date(end_year, 1, 1) - timedelta(days=549),
            episode_end=date(end_year, 1, 1),
            trigger_evidence_refs=[newest["evidence_id"]],
            outcome_evidence_refs=[newest["evidence_id"]],
            historical_context_refs=[oldest["evidence_id"]],
            relationship_mode="direct_linear",
        )
    raise ValueError("every retained longitudinal series duplicates prior research")


def _duplicates_prior_question(question: str, prior_questions: Any) -> bool:
    if not isinstance(prior_questions, list):
        return False
    candidate = _question_tokens(question)
    if not candidate:
        return False
    candidate_years = {int(value) for value in re.findall(r"(?:18|19|20|21)\d{2}", question)}
    for prior in prior_questions:
        if not isinstance(prior, str):
            continue
        existing = _question_tokens(prior)
        if not existing:
            continue
        existing_years = {int(value) for value in re.findall(r"(?:18|19|20|21)\d{2}", prior)}
        # Re-testing the same mechanism in a disjoint historical episode is
        # replication, not a duplicate question.
        if candidate_years and existing_years and candidate_years.isdisjoint(existing_years):
            continue
        overlap = len(candidate & existing) / max(len(candidate | existing), 1)
        if overlap >= 0.72:
            return True
    return False


def _deduplicate_research_hypotheses(
    hypotheses: list[ModelResearchHypothesis],
) -> list[ModelResearchHypothesis]:
    """Remove repeated scenarios while preserving the model's original order."""
    retained: list[ModelResearchHypothesis] = []
    token_sets: list[set[str]] = []
    for hypothesis in hypotheses:
        tokens = _question_tokens(
            " ".join(
                [
                    hypothesis.title,
                    hypothesis.premise,
                    hypothesis.outcome,
                ]
            )
        )
        if any(
            len(tokens & existing) / max(len(tokens | existing), 1) >= 0.82
            for existing in token_sets
        ):
            continue
        retained.append(hypothesis)
        token_sets.append(tokens)
    return retained or hypotheses[:1]


def _question_tokens(value: str) -> set[str]:
    return set(
        re.findall(
            r"[a-z0-9][a-z0-9._/-]{2,}|[\u4e00-\u9fff]{2,8}",
            value.casefold(),
        )
    )


def _rank_evidence_for_focus(
    values: Any,
    *,
    focus: str,
    limit: int,
) -> list[Any]:
    if not isinstance(values, list):
        return []
    return sorted(
        values,
        key=lambda item: _text_relevance(
            json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else str(item),
            focus,
        ),
        reverse=True,
    )[:limit]


def _compatible_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    def compatible(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: compatible(item)
                for key, item in value.items()
                if key not in UNSUPPORTED_GRAMMAR_SCHEMA_KEYS
            }
        if isinstance(value, list):
            return [compatible(item) for item in value]
        return value

    schema = compatible(model.model_json_schema())
    if not isinstance(schema, dict):
        raise TypeError("model JSON schema must be an object")
    return schema


def _responses_output_text(payload: dict[str, Any]) -> str:
    for item in payload.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str):
                    return text
    raise ValueError("Responses API payload has no output_text")
