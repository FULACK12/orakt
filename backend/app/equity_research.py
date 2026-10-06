"""Deterministic company context and technical/valuation calculations."""

# ruff: noqa: RUF001

from __future__ import annotations

import math
import re
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.canslim import build_canslim_scorecard
from app.competitive_evidence import build_competitor_operating_comparison
from app.core.config import get_settings
from app.db.models import (
    ChinaDisclosureSyncState,
    CompanyFiling,
    CompanyFinancialFact,
    CompanyProfile,
    Document,
    MarketDailyBar,
    MarketObservation,
    MarketSeries,
    Source,
)
from app.disclosure_evidence import (
    extract_structured_disclosure_evidence,
    structured_evidence_counts,
)
from app.evidence_quality import can_verify_claims, document_evidence_tier
from app.horizon_backtest import (
    apply_point_in_time_fundamental_gate,
    build_horizon_models,
)
from app.insider_history import build_insider_evidence
from app.institutional_history import build_institutional_evidence
from app.product_evidence import (
    build_product_operating_evidence,
    summarize_product_operating_evidence,
)
from app.supply_chain import build_supply_chain_evidence, count_verified_supply_chain_edges
from app.supply_chain_sites import build_supply_chain_site_evidence

TWELVE_HISTORY_DOCUMENTATION = (
    "https://support.twelvedata.com/en/articles/5656039-how-to-get-historical-prices"
)

COMPANY_ALIASES: dict[str, tuple[str, ...]] = {
    "MU": ("mu", "micron", "micron technology", "美光", "美光科技"),
    "LULU": ("lulu", "lululemon", "lululemon athletica", "露露乐蒙"),
    "NVDA": ("nvda", "nvidia", "英伟达", "辉达"),
    "AMD": ("amd", "advanced micro devices", "超威半导体", "超威"),
    "AAPL": ("aapl", "apple", "苹果"),
    "MSFT": ("msft", "microsoft", "微软"),
    "AMZN": ("amzn", "amazon", "亚马逊"),
    "GOOGL": ("googl", "google", "alphabet", "谷歌"),
    "META": ("meta", "facebook", "脸书"),
    "TSLA": ("tsla", "tesla", "特斯拉"),
    "T": ("at&t", "at and t", "at&t inc"),
}

COMPANY_RESEARCH_PROFILES: dict[str, dict[str, list[str]]] = {
    "LULU": {
        "products": [
            "technical athletic apparel",
            "women's apparel",
            "men's apparel",
            "footwear",
            "fitness-inspired accessories",
        ],
        "competitors_to_verify": [
            "Nike",
            "Adidas",
            "Athleta",
            "Alo Yoga",
            "Vuori",
        ],
        "supply_chain_inputs_to_verify": [
            "technically advanced fabrics",
            "garment manufacturing capacity",
            "content labels, elastics, buttons, clasps and drawcords",
            "ocean and air freight",
            "distribution-center capacity",
        ],
        "geographies_to_verify": [
            "United States",
            "Canada",
            "China Mainland",
            "Taiwan",
            "Vietnam",
            "Cambodia",
            "Sri Lanka",
            "Indonesia",
            "Bangladesh",
            "South Korea",
        ],
        "technology_questions": [
            "product innovation, fabric performance and brand differentiation",
            "women's, men's, footwear and accessories category mix",
            "international expansion and comparable-sales execution",
            "supplier concentration, freight capacity and Taiwan fabric exposure",
        ],
    },
    "AAPL": {
        "products": [
            "iPhone",
            "Mac and iPad",
            "Wearables",
            "Services and App Store",
            "Apple silicon and Apple Intelligence",
        ],
        "competitors_to_verify": [
            "Samsung Electronics",
            "Huawei",
            "Google",
            "Microsoft",
            "Xiaomi",
        ],
        "supply_chain_inputs_to_verify": [
            "leading-edge semiconductors and foundry capacity",
            "displays, cameras and memory components",
            "batteries and critical minerals",
            "contract manufacturing and final assembly",
            "electricity, ports and international logistics",
        ],
        "geographies_to_verify": [
            "United States",
            "China",
            "Taiwan",
            "India",
            "Vietnam",
            "Japan",
            "South Korea",
        ],
        "technology_questions": [
            "iPhone replacement cycle, unit demand and product mix",
            "services growth, App Store regulation and ecosystem retention",
            "on-device AI adoption and custom-silicon differentiation",
            "supplier concentration, foundry dependency and assembly diversification",
        ],
    },
    "MU": {
        "products": [
            "DRAM",
            "NAND flash",
            "HBM high-bandwidth memory",
            "data-center SSD",
            "automotive and embedded memory",
        ],
        "competitors_to_verify": [
            "Samsung Electronics",
            "SK hynix",
            "Kioxia",
            "Western Digital / Sandisk",
        ],
        "supply_chain_inputs_to_verify": [
            "silicon wafers",
            "photoresists and specialty chemicals",
            "neon, argon and other process gases",
            "advanced lithography and deposition equipment",
            "electricity and ultra-pure water",
            "advanced packaging capacity",
        ],
        "geographies_to_verify": [
            "United States",
            "Japan",
            "Taiwan",
            "Singapore",
            "Malaysia",
            "China",
        ],
        "technology_questions": [
            "HBM generation competitiveness and qualification timing",
            "DRAM and NAND process-node cost position",
            "customer concentration and long-term supply agreements",
            "emerging memory architectures and compute-near-memory substitution",
        ],
    },
    "NVDA": {
        "products": [
            "data-center GPUs and AI accelerators",
            "CUDA software platform",
            "gaming GPUs",
            "networking and interconnect",
            "automotive computing",
        ],
        "competitors_to_verify": [
            "AMD",
            "Intel",
            "Google custom accelerators",
            "Amazon custom accelerators",
            "Microsoft custom accelerators",
        ],
        "supply_chain_inputs_to_verify": [
            "leading-edge foundry capacity",
            "HBM high-bandwidth memory",
            "advanced packaging and substrates",
            "networking components",
            "data-center electricity and cooling",
        ],
        "geographies_to_verify": [
            "United States",
            "Taiwan",
            "South Korea",
            "Japan",
            "China",
        ],
        "technology_questions": [
            "accelerator performance and total cost of ownership",
            "CUDA ecosystem retention and switching costs",
            "HBM and advanced-packaging capacity constraints",
            "custom accelerator and competing GPU substitution",
        ],
    },
    "AMD": {
        "products": [
            "EPYC server CPUs",
            "Ryzen client CPUs",
            "Instinct AI accelerators",
            "Radeon GPUs",
            "adaptive and embedded computing",
        ],
        "competitors_to_verify": [
            "NVIDIA",
            "Intel",
            "Arm-based server processors",
            "Google custom accelerators",
            "Amazon custom accelerators",
        ],
        "supply_chain_inputs_to_verify": [
            "leading-edge foundry capacity",
            "advanced packaging and substrates",
            "HBM high-bandwidth memory",
            "semiconductor manufacturing equipment and chemicals",
            "data-center electricity and cooling",
        ],
        "geographies_to_verify": [
            "United States",
            "Taiwan",
            "Malaysia",
            "China",
            "Japan",
        ],
        "technology_questions": [
            "server CPU share and hyperscaler adoption",
            "AI accelerator qualification and software ecosystem",
            "foundry and advanced-packaging concentration",
            "x86, Arm and custom-accelerator substitution",
        ],
    },
    "MSFT": {
        "products": [
            "Azure cloud and AI infrastructure",
            "Microsoft 365 and Copilot",
            "Windows and devices",
            "Dynamics business applications",
            "gaming and content",
        ],
        "competitors_to_verify": [
            "Amazon Web Services",
            "Google Cloud",
            "Oracle",
            "Salesforce",
            "Apple",
        ],
        "supply_chain_inputs_to_verify": [
            "AI accelerators and server CPUs",
            "memory, networking and storage",
            "data-center construction equipment",
            "electricity, grid connections and cooling water",
            "subsea cables and cloud-region connectivity",
        ],
        "geographies_to_verify": [
            "United States",
            "Europe",
            "China",
            "India",
            "Japan",
            "Southeast Asia",
        ],
        "technology_questions": [
            "AI infrastructure utilization and return on capital",
            "Copilot adoption, pricing and retention",
            "custom silicon versus merchant accelerators",
            "power, grid and data-center construction constraints",
        ],
    },
}

AAPL_RETAIL_DOMAINS = {
    "amazon.com",
    "ebay.com",
    "walmart.com",
    "aliexpress.com",
}
AAPL_TECH_TERMS = (
    "aapl",
    "apple inc",
    "苹果公司",
    "iphone",
    "ipad",
    "mac",
    "app store",
    "apple watch",
    "apple intelligence",
    "icloud",
    "ios",
    "macos",
    "vision pro",
    "wwdc",
    "tim cook",
    "cupertino",
)
AAPL_FRUIT_TERMS = (
    "apple juice",
    "apple carrot",
    "苹果汁",
    "苹果胡萝卜",
    "鲜榨果汁",
    "蔬果汁",
)
AAPL_ACCESSORY_PATTERNS = (
    r"compatible with (?:an? )?(?:apple )?(?:iphone|ipad|watch)",
    r"designed for (?:an? )?(?:apple )?(?:iphone|ipad|watch)",
    r"for (?:apple )?(?:iphone|ipad|watch) users",
    r"专为.{0,12}(?:iphone|ipad|apple watch|苹果).{0,12}(?:打造|设计)",
    r"(?:iphone|ipad|apple watch).{0,12}(?:配件|充电器|耳机)",
    r"(?:苹果授权|mfi.{0,12}认证)",
)

REQUIRED_EQUITY_DIMENSIONS = [
    "fundamentals_valuation",
    "technicals_positioning",
    "macro_liquidity",
    "supply_chain_geopolitics",
    "technology_competition",
]

MACRO_SENSITIVITY_SERIES: dict[str, tuple[str, str]] = {
    "DGS2": ("U.S. 2-year Treasury yield", "absolute_change"),
    "DGS10": ("U.S. 10-year Treasury yield", "absolute_change"),
    "VIXCLS": ("CBOE VIX", "absolute_change"),
    "DTWEXBGS": ("Trade-weighted U.S. dollar", "log_return"),
    "SP500": ("S&P 500", "log_return"),
    "NASDAQCOM": ("Nasdaq Composite", "log_return"),
}


def detect_company_ticker(
    question: str | None,
    profiles: list[CompanyProfile],
) -> str | None:
    """Resolve explicit ticker, English name or common Chinese alias."""
    if not question:
        return None
    normalized = question.casefold()
    # Resolve explicit ticker tokens first and prefer the longest token. Database
    # row order is not semantic; without this pass, a short ticker such as ``T``
    # can win before an explicit ``LULU`` token is evaluated.
    for profile in sorted(profiles, key=lambda item: len(item.ticker), reverse=True):
        if _contains_alias(normalized, profile.ticker.casefold()):
            return profile.ticker
    for ticker, aliases in COMPANY_ALIASES.items():
        if any(_contains_alias(normalized, alias) for alias in aliases):
            return ticker
    for profile in profiles:
        company_tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", profile.name.casefold())
            if len(token) >= 3
            and token not in {"inc", "corp", "corporation", "company", "co"}
        ]
        if company_tokens and all(
            _contains_alias(normalized, token) for token in company_tokens
        ):
            return profile.ticker
    return None


def build_equity_research_pack(
    session: Session,
    *,
    question: str | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Build question-specific inputs; calculations remain auditable evidence."""
    profiles = list(session.scalars(select(CompanyProfile)))
    ticker = detect_company_ticker(question, profiles)
    if ticker is None:
        return _build_china_equity_research_pack(session, question=question)
    profile = next((item for item in profiles if item.ticker == ticker), None)
    if profile is None:
        return None, []

    price_rows = list(
        session.execute(
            select(MarketObservation.observed_on, MarketObservation.value)
            .where(MarketObservation.series_id == f"EQ:{ticker}")
            .order_by(desc(MarketObservation.observed_on))
            .limit(1_500)
        )
    )
    price_rows.reverse()
    price_values = [(observed_on, float(value)) for observed_on, value in price_rows]
    daily_bars = list(
        session.scalars(
            select(MarketDailyBar)
            .where(MarketDailyBar.series_id == f"EQ:{ticker}")
            .order_by(desc(MarketDailyBar.observed_on))
            .limit(1_500)
        )
    )
    daily_bars.reverse()
    price_as_of = price_values[-1][0] if price_values else date.today()
    supply_chain_as_of = max(price_as_of, date.today())
    technical = _technical_snapshot(ticker, price_values, daily_bars=daily_bars)
    insider_evidence = build_insider_evidence(
        session,
        ticker=ticker,
        as_of=price_as_of,
    )
    institutional_evidence = build_institutional_evidence(
        session,
        ticker=ticker,
    )
    institutional_positioning = _institutional_positioning_snapshot(
        ticker,
        institutional_evidence,
    )
    annual_facts = _latest_annual_facts(
        session,
        ticker=ticker,
        as_of=price_as_of,
    )
    valuation_basis = _latest_valuation_basis(
        session,
        ticker=ticker,
        as_of=price_as_of,
        annual_facts=annual_facts,
    )
    latest_shares = _latest_instant_fact(
        session,
        ticker=ticker,
        concept="CommonStockSharesOutstanding",
        as_of=price_as_of,
    )
    valuation = _valuation_snapshot(
        ticker,
        price_values,
        annual_facts,
        question=question or "",
        valuation_basis=valuation_basis,
        latest_shares=latest_shares,
    )
    financial_trend = _financial_trend_snapshot(
        session,
        ticker=ticker,
        as_of=price_as_of,
    )
    if technical is not None:
        apply_point_in_time_fundamental_gate(
            technical.get("horizon_models"),
            available=financial_trend is not None,
        )
    macro_sensitivity = _macro_sensitivity_snapshot(
        session,
        ticker=ticker,
        price_rows=price_values,
    )
    company_documents = _company_document_evidence(
        session,
        ticker=ticker,
        company_name=profile.name,
        as_of=price_as_of,
    )
    product_operating_evidence = build_product_operating_evidence(
        session,
        ticker=ticker,
        as_of=price_as_of,
        cold_data_root=get_settings().cold_data_root,
    )
    product_operating_coverage = summarize_product_operating_evidence(product_operating_evidence)
    competitor_operating_comparison = build_competitor_operating_comparison(
        session,
        ticker=ticker,
        as_of=price_as_of,
        cold_data_root=get_settings().cold_data_root,
    )
    canslim_scorecard = build_canslim_scorecard(
        session,
        ticker=ticker,
        as_of=price_as_of,
        technical=technical,
        product_evidence=product_operating_evidence,
        institutional_evidence=institutional_evidence,
    )
    supply_chain_edges, supplier_factors = build_supply_chain_evidence(
        session,
        ticker=ticker,
        as_of=price_as_of,
    )
    supply_chain_sites = build_supply_chain_site_evidence(
        session,
        ticker=ticker,
        as_of=supply_chain_as_of,
    )
    verified_supply_chain_edge_total = count_verified_supply_chain_edges(
        session,
        ticker=ticker,
        as_of=price_as_of,
    )
    filings = list(
        session.scalars(
            select(CompanyFiling)
            .where(CompanyFiling.ticker == ticker)
            .order_by(desc(CompanyFiling.filed_at))
            .limit(12)
        )
    )

    evidence: list[dict[str, Any]] = []
    if technical is not None:
        evidence.append(technical)
    if valuation is not None:
        evidence.append(valuation)
    if financial_trend is not None:
        evidence.append(financial_trend)
    if macro_sensitivity is not None:
        evidence.append(macro_sensitivity)
    if competitor_operating_comparison is not None:
        evidence.append(competitor_operating_comparison)
    evidence.append(canslim_scorecard)
    evidence.extend(product_operating_evidence)
    evidence.extend(company_documents)
    evidence.extend(supply_chain_edges)
    evidence.extend(supplier_factors)
    evidence.extend(supply_chain_sites)
    evidence.extend(insider_evidence)
    evidence.extend(institutional_evidence)
    if institutional_positioning is not None:
        evidence.append(institutional_positioning)
    for filing in filings:
        evidence.append(
            {
                "evidence_id": f"sec-filing:{ticker}:{filing.accession_number}",
                "category": "company_filing",
                "ticker": ticker,
                "form": filing.form,
                "filed_at": filing.filed_at.isoformat(),
                "report_date": (filing.report_date.isoformat() if filing.report_date else None),
                "source": "SEC EDGAR submission",
                "source_url": filing.source_url,
                "can_verify_filing_exists": True,
                "can_verify_filing_contents": False,
            }
        )

    reviewed_profile = COMPANY_RESEARCH_PROFILES.get(ticker, {})
    data_readiness = _equity_data_readiness(
        technical=technical,
        financial_trend=financial_trend,
        filing_count=len(filings),
        company_document_count=len(company_documents),
        product_operating_evidence_count=len(product_operating_evidence),
        product_operating_actual_count=int(product_operating_coverage["reported_actual_count"]),
        institutional_evidence_count=len(institutional_evidence),
        insider_evidence_count=len(insider_evidence),
        macro_sensitivity=macro_sensitivity,
        verified_supply_chain_edge_total=verified_supply_chain_edge_total,
        supplier_market_factor_count=len(supplier_factors),
        supply_chain_site_count=len(supply_chain_sites),
    )
    context = {
        "research_type": "public_equity",
        "market_region": "us",
        "ticker": ticker,
        "sec_ticker": ticker,
        "price_series_id": f"EQ:{ticker}",
        "company": profile.name,
        "sector": profile.sector,
        "industry": profile.industry,
        "point_in_time_cutoff": price_as_of.isoformat(),
        "supply_chain_point_in_time_cutoff": supply_chain_as_of.isoformat(),
        "required_dimensions": REQUIRED_EQUITY_DIMENSIONS,
        "reviewed_search_plan_not_evidence": reviewed_profile,
        "technical_data_status": (
            (
                "calculated_from_split_adjusted_daily_ohlcv"
                if technical and technical.get("bar_data_status") == "complete_ohlcv"
                else "calculated_from_adjusted_daily_closes"
            )
            if technical
            else "missing"
        ),
        "financial_trend_status": (
            "point_in_time_annual_trend_available" if financial_trend else "missing"
        ),
        "macro_sensitivity_status": (
            "descriptive_aligned_changes_available" if macro_sensitivity else "missing"
        ),
        "data_readiness": data_readiness,
        "company_full_text_documents": len(company_documents),
        "product_operating_evidence": product_operating_coverage,
        "competitor_operating_comparison": (
            {
                "status": "available",
                "peer_group": competitor_operating_comparison["peer_group"],
                "company_count": len(competitor_operating_comparison["rows"]),
                "comparable_product_metric_types": competitor_operating_comparison[
                    "comparable_product_metric_types"
                ],
            }
            if competitor_operating_comparison is not None
            else {"status": "missing", "peer_group": [], "company_count": 0}
        ),
        "canslim_scorecard": {
            "version": canslim_scorecard["version"],
            "overall_score": canslim_scorecard["overall_score"],
            "coverage_score": canslim_scorecard["coverage_score"],
            "decision": canslim_scorecard["decision"],
        },
        "verified_supply_chain_edges": len(supply_chain_edges),
        "verified_supply_chain_edge_total": verified_supply_chain_edge_total,
        "verified_supply_chain_edge_payload_limit": 80,
        "supplier_market_factors": len(supplier_factors),
        "supply_chain_site_exposures": len(supply_chain_sites),
        "supply_chain_exact_facilities": sum(
            item.get("coordinate_precision") == "exact_facility" for item in supply_chain_sites
        ),
        "supply_chain_geocoded_regions": sum(
            item.get("latitude") is not None and item.get("longitude") is not None
            for item in supply_chain_sites
        ),
        "supply_chain_status": (
            "source-reviewed company facilities or supplier locations available"
            if supply_chain_sites
            else "source-reviewed supplier edges and exploratory market factors available"
            if supply_chain_edges
            else "pending: no source-reviewed supplier edge is currently allowed into the report"
        ),
        "institutional_positioning_status": (
            "SEC Form 13F quarter comparisons available; they remain delayed and do "
            "not disclose cost basis or exact fund mandate"
            if institutional_evidence
            else "backfill_pending: do not infer block trades, active/passive fund "
            "flows or institutional cost basis from price alone; SEC Form 13F and "
            "trade/volume evidence are required"
        ),
        "insider_activity_status": (
            "SEC Form 4 transaction date, code, shares, price and post-transaction "
            "ownership are parsed; disclosures do not establish insider motive"
            if insider_evidence
            else "backfill_pending: filing references may exist, but transaction "
            "details require Form 4 XML parsing"
        ),
        "price_target_rule": (
            "Any target price must show the implied market capitalization and the "
            "earnings/revenue multiple or cash-flow assumptions used."
        ),
        "macro_causality_rule": (
            "Claims about Japanese-funded liquidity require direct evidence for funding "
            "flows, FX hedging, Treasury holdings/yields and timing; national debt and "
            "USD/JPY correlation alone are insufficient."
        ),
    }
    return context, evidence


def _equity_data_readiness(
    *,
    technical: dict[str, Any] | None,
    financial_trend: dict[str, Any] | None,
    filing_count: int,
    company_document_count: int,
    product_operating_evidence_count: int,
    product_operating_actual_count: int,
    institutional_evidence_count: int,
    insider_evidence_count: int,
    macro_sensitivity: dict[str, Any] | None,
    verified_supply_chain_edge_total: int,
    supplier_market_factor_count: int,
    supply_chain_site_count: int,
) -> dict[str, Any]:
    """Score retained issuer evidence and enforce a transparent conclusion gate."""
    observations = int(technical.get("observations") or 0) if technical else 0
    complete_ohlcv = bool(
        technical and technical.get("bar_data_status") == "complete_ohlcv" and observations >= 252
    )
    close_history = observations >= 252
    ownership_sources = int(bool(institutional_evidence_count)) + int(bool(insider_evidence_count))
    supply_score = min(
        1.0,
        (min(verified_supply_chain_edge_total, 3) / 3) * 0.6
        + (0.2 if supplier_market_factor_count else 0.0)
        + (0.2 if supply_chain_site_count else 0.0),
    )
    components = [
        {
            "key": "daily_ohlcv",
            "label_zh": "完整日线 OHLCV",
            "label_en": "Complete daily OHLCV",
            "weight": 20,
            "score": 1.0 if complete_ohlcv else 0.55 if close_history else 0.0,
            "status": "complete" if complete_ohlcv else "partial" if close_history else "missing",
            "detail_zh": (
                f"已保留 {observations} 个完整交易日。"
                if complete_ohlcv
                else f"仅保留 {observations} 个收盘价交易日；成交量、ATR 与真实 KDJ 不完整。"
                if close_history
                else "不足 252 个交易日，不能形成稳定技术统计。"
            ),
            "detail_en": (
                f"{observations} complete trading days are retained."
                if complete_ohlcv
                else (
                    f"{observations} close-only days are retained; volume, ATR and "
                    "true KDJ are incomplete."
                )
                if close_history
                else "Fewer than 252 trading days are retained."
            ),
        },
        {
            "key": "fundamentals",
            "label_zh": "点时财务趋势",
            "label_en": "Point-in-time fundamentals",
            "weight": 20,
            "score": 1.0 if financial_trend else 0.0,
            "status": "complete" if financial_trend else "missing",
            "detail_zh": "已形成可得时间约束的年度财务趋势。"
            if financial_trend
            else "缺少可得时间约束的多期财务趋势。",
            "detail_en": "Availability-bounded financial trends are retained."
            if financial_trend
            else "Availability-bounded multi-period fundamentals are missing.",
        },
        {
            "key": "primary_filings",
            "label_zh": "SEC 原始申报",
            "label_en": "Primary SEC filings",
            "weight": 10,
            "score": 1.0 if filing_count else 0.0,
            "status": "complete" if filing_count else "missing",
            "detail_zh": f"报告包内含 {filing_count} 个最新申报引用。"
            if filing_count
            else "没有可引用的 SEC 申报。",
            "detail_en": f"{filing_count} recent filing references are available."
            if filing_count
            else "No SEC filing reference is available.",
        },
        {
            "key": "company_documents",
            "label_zh": "公司新闻正文",
            "label_en": "Substantive company news",
            "weight": 5,
            "score": min(company_document_count / 4, 1.0),
            "status": "complete"
            if company_document_count >= 4
            else "partial"
            if company_document_count
            else "missing",
            "detail_zh": f"已纳入 {company_document_count} 条含正文或实质摘要的公司材料。",
            "detail_en": f"{company_document_count} substantive company documents are included.",
        },
        {
            "key": "product_operating_evidence",
            "label_zh": "产品经营与合同证据",
            "label_en": "Product operating and contract evidence",
            "weight": 10,
            "score": min(product_operating_actual_count / 4, 1.0),
            "status": "complete"
            if product_operating_actual_count >= 4
            else "partial"
            if product_operating_evidence_count
            else "missing",
            "detail_zh": (
                f"已从年报与季报原文提取 {product_operating_evidence_count} 条证据，其中"
                f" {product_operating_actual_count} 条为已报告经营结果；前瞻计划不计入完成度。"
            ),
            "detail_en": (
                f"{product_operating_evidence_count} annual/quarterly filing excerpts "
                "are retained, including "
                f"{product_operating_actual_count} reported actuals; forward-looking plans do not "
                "count toward completion."
            ),
        },
        {
            "key": "ownership",
            "label_zh": "机构与内部人披露",
            "label_en": "Institutional and insider filings",
            "weight": 15,
            "score": ownership_sources / 2,
            "status": "complete"
            if ownership_sources == 2
            else "partial"
            if ownership_sources
            else "missing",
            "detail_zh": f"13F 与 Form 4 两类披露中已有 {ownership_sources} 类可用。",
            "detail_en": f"{ownership_sources} of two 13F/Form 4 evidence classes are available.",
        },
        {
            "key": "supply_chain",
            "label_zh": "供应链与设施映射",
            "label_en": "Supply-chain and facility mapping",
            "weight": 10,
            "score": round(supply_score, 4),
            "status": "complete"
            if supply_score >= 0.99
            else "partial"
            if supply_score
            else "missing",
            "detail_zh": (
                f"已核验 {verified_supply_chain_edge_total} 条关系、"
                f"{supplier_market_factor_count} 个供应商/行业篮子市场代理因子、"
                f"{supply_chain_site_count} 个设施/区域暴露。"
            ),
            "detail_en": (
                f"{verified_supply_chain_edge_total} relationships, "
                f"{supplier_market_factor_count} supplier/category-basket market proxies "
                f"and {supply_chain_site_count} facility/region exposures are retained."
            ),
        },
        {
            "key": "macro_alignment",
            "label_zh": "宏观序列对齐",
            "label_en": "Macro-series alignment",
            "weight": 10,
            "score": 1.0 if macro_sensitivity else 0.0,
            "status": "complete" if macro_sensitivity else "missing",
            "detail_zh": "已计算宏观变量的同期与滞后描述性敏感度。"
            if macro_sensitivity
            else "缺少可对齐的宏观市场序列。",
            "detail_en": "Contemporaneous and lagged descriptive macro sensitivities are available."
            if macro_sensitivity
            else "Aligned macro-market series are missing.",
        },
    ]
    weighted_score = round(
        sum(float(item["score"]) * int(item["weight"]) for item in components) / 100,
        4,
    )
    hard_gates = {
        "daily_ohlcv": complete_ohlcv,
        "fundamentals": financial_trend is not None,
        "primary_filings": filing_count > 0,
        "company_documents": company_document_count >= 2,
        "ownership": ownership_sources > 0,
        "supply_chain": verified_supply_chain_edge_total > 0,
        "macro_alignment": macro_sensitivity is not None,
    }
    directional_allowed = weighted_score >= 0.75 and all(hard_gates.values())
    status = (
        "full_research_ready"
        if directional_allowed
        else "evidence_gap_report_only"
        if weighted_score >= 0.45
        else "insufficient_for_company_report"
    )
    return {
        "version": "equity_data_readiness_v2_product_operating",
        "score": weighted_score,
        "status": status,
        "directional_conclusion_allowed": directional_allowed,
        "confidence_cap": 0.75
        if directional_allowed
        else round(min(0.55, 0.2 + weighted_score * 0.45), 2),
        "hard_gates": hard_gates,
        "missing_required": [key for key, passed in hard_gates.items() if not passed],
        "components": components,
        "policy_zh": (
            "数据门控通过，可生成有条件研究结论；交易方向仍须通过样本外检验。"
            if directional_allowed
            else "仅生成证据缺口报告，不允许输出确定方向、买点或盈利结论。"
        ),
        "policy_en": (
            "The data gate passed for a conditional research conclusion; trading "
            "direction still requires out-of-sample validation."
            if directional_allowed
            else (
                "Evidence-gap report only; no definitive direction, entry point or "
                "profit conclusion is allowed."
            )
        ),
    }


def _china_equity_data_readiness(
    *,
    technical: dict[str, Any] | None,
    snapshot_count: int,
    company_document_count: int,
    periodic_report_count: int,
    structured_financial_metric_count: int,
    shareholder_document_count: int,
    shareholder_excerpt_count: int,
    operating_document_count: int,
    operating_excerpt_count: int,
    supply_chain_document_count: int,
    supply_chain_excerpt_count: int,
    macro_sensitivity: dict[str, Any] | None,
) -> dict[str, Any]:
    """Score A-share evidence without treating snapshots as filing facts."""
    observations = int(technical.get("observations") or 0) if technical else 0
    complete_ohlcv = bool(
        technical and technical.get("bar_data_status") == "complete_ohlcv" and observations >= 252
    )
    close_history = observations >= 252
    snapshot_score = min(max(snapshot_count, 0) / 8, 1.0) * 0.55
    filing_score = min(max(periodic_report_count, 0) / 4, 1.0)
    structured_financial_score = min(max(structured_financial_metric_count, 0) / 8, 1.0)
    ownership_score = min(
        1.0,
        (0.35 if shareholder_document_count else 0.0)
        + 0.65 * min(max(shareholder_excerpt_count, 0) / 4, 1.0),
    )
    operating_score = min(
        1.0,
        (0.35 if operating_document_count else 0.0)
        + 0.65 * min(max(operating_excerpt_count, 0) / 4, 1.0),
    )
    supply_chain_score = min(
        1.0,
        (0.3 if supply_chain_document_count else 0.0)
        + 0.7 * min(max(supply_chain_excerpt_count, 0) / 4, 1.0),
    )
    components = [
        {
            "key": "daily_price_history",
            "label_zh": "A股日线历史",
            "label_en": "A-share daily price history",
            "weight": 20,
            "score": (
                1.0
                if complete_ohlcv
                else 0.65
                if close_history
                else 0.3
                if observations >= 60
                else 0.0
            ),
            "status": (
                "complete"
                if complete_ohlcv
                else "partial"
                if observations >= 60
                else "missing"
            ),
            "detail_zh": (
                f"已保留 {observations} 个完整 OHLCV 交易日。"
                if complete_ohlcv
                else f"已保留 {observations} 个前复权收盘价交易日；成交量、ATR 与真实 KDJ 尚不完整。"
                if observations
                else "没有足够的可用交易日。"
            ),
            "detail_en": (
                f"{observations} complete OHLCV sessions are retained."
                if complete_ohlcv
                else (
                    f"{observations} forward-adjusted close sessions are retained; "
                    "volume, ATR and true KDJ remain incomplete."
                )
                if observations
                else "No sufficient trading history is retained."
            ),
        },
        {
            "key": "latest_fundamental_snapshot",
            "label_zh": "最新基本面快照",
            "label_en": "Latest fundamental snapshot",
            "weight": 10,
            "score": round(snapshot_score, 4),
            "status": "partial" if snapshot_count else "missing",
            "detail_zh": f"已取得 {snapshot_count}/8 个 BaoStock 快照字段；快照不是点时财报，因此最高只计 55%。",
            "detail_en": (
                f"{snapshot_count}/8 BaoStock snapshot fields are retained; snapshots "
                "are not point-in-time filings and are capped at 55% credit."
            ),
        },
        {
            "key": "primary_exchange_filings",
            "label_zh": "交易所原始公告",
            "label_en": "Primary exchange filings",
            "weight": 15,
            "score": round(filing_score, 4),
            "status": (
                "complete"
                if periodic_report_count >= 4
                else "partial"
                if periodic_report_count
                else "missing"
            ),
            "detail_zh": f"已归档 {periodic_report_count} 份定期报告原文及发布时间。",
            "detail_en": (
                f"{periodic_report_count} periodic filings with source text and "
                "publication times are archived."
            ),
        },
        {
            "key": "structured_financials",
            "label_zh": "结构化季度财务",
            "label_en": "Structured quarterly financials",
            "weight": 15,
            "score": round(structured_financial_score, 4),
            "status": (
                "complete"
                if structured_financial_metric_count >= 8
                else "partial"
                if structured_financial_metric_count
                else "missing"
            ),
            "detail_zh": f"已提取 {structured_financial_metric_count} 个财务指标候选；仍需核对 PDF 表格列与单位。",
            "detail_en": (
                f"{structured_financial_metric_count} financial metric candidates are "
                "extracted; PDF table columns and units still require reconciliation."
            ),
        },
        {
            "key": "company_documents",
            "label_zh": "公司公告与新闻正文",
            "label_en": "Substantive company documents",
            "weight": 5,
            "score": min(max(company_document_count, 0) / 4, 1.0),
            "status": (
                "complete"
                if company_document_count >= 4
                else "partial"
                if company_document_count
                else "missing"
            ),
            "detail_zh": f"本次报告纳入 {company_document_count} 份含正文的公司材料。",
            "detail_en": f"{company_document_count} substantive company documents are included.",
        },
        {
            "key": "operating_evidence",
            "label_zh": "产销、合同与经营证据",
            "label_en": "Operating and contract evidence",
            "weight": 10,
            "score": round(operating_score, 4),
            "status": (
                "complete"
                if operating_excerpt_count >= 4
                else "partial"
                if operating_document_count or operating_excerpt_count
                else "missing"
            ),
            "detail_zh": f"经营类公告 {operating_document_count} 份，结构化经营摘录 {operating_excerpt_count} 条。",
            "detail_en": (
                f"{operating_document_count} operating documents and "
                f"{operating_excerpt_count} structured operating excerpts are retained."
            ),
        },
        {
            "key": "ownership_evidence",
            "label_zh": "股东与资金披露",
            "label_en": "Shareholder and ownership evidence",
            "weight": 10,
            "score": round(ownership_score, 4),
            "status": (
                "complete"
                if shareholder_excerpt_count >= 4
                else "partial"
                if shareholder_document_count or shareholder_excerpt_count
                else "missing"
            ),
            "detail_zh": (
                f"股东类公告 {shareholder_document_count} 份，结构化股东摘录 "
                f"{shareholder_excerpt_count} 条；不等同于实时北向资金。"
            ),
            "detail_en": (
                f"{shareholder_document_count} shareholder documents and "
                f"{shareholder_excerpt_count} structured excerpts are retained; "
                "these are not live northbound-flow data."
            ),
        },
        {
            "key": "supply_chain_evidence",
            "label_zh": "供应链公告证据",
            "label_en": "Supply-chain filing evidence",
            "weight": 5,
            "score": round(supply_chain_score, 4),
            "status": (
                "complete"
                if supply_chain_excerpt_count >= 4
                else "partial"
                if supply_chain_document_count or supply_chain_excerpt_count
                else "missing"
            ),
            "detail_zh": (
                f"供应链类公告 {supply_chain_document_count} 份，结构化供应链摘录 "
                f"{supply_chain_excerpt_count} 条；尚不代表已核验工厂坐标与产能。"
            ),
            "detail_en": (
                f"{supply_chain_document_count} supply-chain documents and "
                f"{supply_chain_excerpt_count} structured excerpts are retained; "
                "verified facility coordinates and capacity are separate requirements."
            ),
        },
        {
            "key": "macro_alignment",
            "label_zh": "宏观序列对齐",
            "label_en": "Macro-series alignment",
            "weight": 10,
            "score": 1.0 if macro_sensitivity else 0.0,
            "status": "complete" if macro_sensitivity else "missing",
            "detail_zh": "已计算宏观变量的同期与滞后描述性敏感度。" if macro_sensitivity else "缺少可对齐的宏观市场序列。",
            "detail_en": (
                "Contemporaneous and lagged descriptive macro sensitivities are available."
                if macro_sensitivity
                else "Aligned macro-market series are missing."
            ),
        },
    ]
    weighted_score = round(
        sum(float(item["score"]) * int(item["weight"]) for item in components) / 100,
        4,
    )
    hard_gates = {
        "daily_price_history": close_history,
        "primary_exchange_filings": periodic_report_count > 0,
        "structured_financials": structured_financial_metric_count > 0,
        "operating_evidence": operating_document_count > 0 or operating_excerpt_count > 0,
        "ownership_evidence": shareholder_document_count > 0 or shareholder_excerpt_count > 0,
        "supply_chain_evidence": supply_chain_document_count > 0 or supply_chain_excerpt_count > 0,
        "macro_alignment": macro_sensitivity is not None,
    }
    directional_allowed = weighted_score >= 0.72 and all(hard_gates.values())
    status = (
        "full_research_ready"
        if directional_allowed
        else "evidence_gap_report_only"
        if weighted_score >= 0.45
        else "insufficient_for_company_report"
    )
    return {
        "version": "a_share_data_readiness_v1",
        "score": weighted_score,
        "status": status,
        "directional_conclusion_allowed": directional_allowed,
        "confidence_cap": 0.75
        if directional_allowed
        else round(min(0.55, 0.2 + weighted_score * 0.45), 2),
        "hard_gates": hard_gates,
        "missing_required": [key for key, passed in hard_gates.items() if not passed],
        "components": components,
        "policy_zh": (
            "A股数据门控通过，可生成有条件研究结论；方向仍须通过严格样本外检验。"
            if directional_allowed
            else "仅生成证据缺口报告，不允许把快照或未核对摘录解释为确定方向、买点或盈利概率。"
        ),
        "policy_en": (
            "The A-share data gate passed for a conditional research conclusion; "
            "direction still requires strict out-of-sample validation."
            if directional_allowed
            else (
                "Evidence-gap report only; snapshots or unreconciled excerpts cannot "
                "support a definitive direction, entry point or profit probability."
            )
        ),
    }


def _build_china_equity_research_pack(
    session: Session,
    *,
    question: str | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Build a bounded A-share market/factor pack without claiming filing coverage."""
    if not question:
        return None, []
    price_series = list(
        session.scalars(
            select(MarketSeries)
            .where(
                MarketSeries.category == "equity_price",
                MarketSeries.region == "china",
                MarketSeries.series_id.like("CN:%"),
            )
            .order_by(MarketSeries.series_id)
        )
    )
    normalized = question.casefold()
    explicit_codes = set(re.findall(r"(?<!\d)\d{6}(?!\d)", question))
    selected: MarketSeries | None = None
    for series in price_series:
        ticker = series.series_id.split(":", 1)[1]
        company_name = _china_company_name(series.name, ticker=ticker)
        if ticker in explicit_codes or company_name.casefold() in normalized:
            selected = series
            break
    if selected is None:
        return None, []

    ticker = selected.series_id.split(":", 1)[1]
    company_name = _china_company_name(selected.name, ticker=ticker)
    price_rows = list(
        session.execute(
            select(MarketObservation.observed_on, MarketObservation.value)
            .where(MarketObservation.series_id == selected.series_id)
            .order_by(desc(MarketObservation.observed_on))
            .limit(1_500)
        )
    )
    price_rows.reverse()
    prices = [(observed_on, float(value)) for observed_on, value in price_rows]
    if not prices:
        return None, []
    as_of = prices[-1][0]
    technical = _technical_snapshot(ticker, prices)
    if technical is not None:
        technical.update(
            {
                "source": "Local calculation from BaoStock forward-adjusted closes",
                "source_url": selected.source_url,
                "market_region": "china",
            }
        )
    snapshots = _china_snapshot_values(session, ticker=ticker, as_of=as_of)
    snapshot_refs = [
        f"market:{series_id}:{item['observed_on']}" for series_id, item in snapshots.items()
    ]
    price = prices[-1][1]
    market_cap = _snapshot_number(snapshots, f"CNMCAP:{ticker}")
    revenue = _snapshot_number(snapshots, f"CNREV:{ticker}")
    net_profit = _snapshot_number(snapshots, f"CNNP:{ticker}")
    pe_ttm = _snapshot_number(snapshots, f"CNPE:{ticker}")
    valuation = {
        "evidence_id": f"derived:valuation:{ticker}:{as_of.isoformat()}",
        "category": "derived_company_valuation",
        "ticker": ticker,
        "market_region": "china",
        "price": price,
        "price_observed_on": as_of.isoformat(),
        "market_cap": market_cap,
        "basis_revenue": revenue,
        "basis_net_income": net_profit,
        "trailing_price_to_sales": (
            market_cap / revenue
            if market_cap is not None and revenue is not None and revenue > 0
            else None
        ),
        "trailing_price_to_earnings": pe_ttm,
        "price_to_book": _snapshot_number(snapshots, f"CNPB:{ticker}"),
        "valuation_basis": "BaoStock latest ranking snapshot; not filing-audited",
        "valuation_basis_period_end": None,
        "underlying_evidence_refs": snapshot_refs,
        "source": "BaoStock CSI 800 proxy sector-leader snapshot",
        "source_url": selected.source_url,
        "method_limitations": [
            "Snapshot observation time is not the original financial filing availability time.",
            "A-share exchange filing bodies and audited statement excerpts are not retained yet.",
            "PE/PB and market capitalization are descriptive and do not establish fair value.",
        ],
    }
    financial = {
        "evidence_id": f"derived:financial-trend:{ticker}:{as_of.isoformat()}",
        "category": "derived_company_financial_trend",
        "ticker": ticker,
        "market_region": "china",
        "as_of": as_of.isoformat(),
        "periods": [
            {
                "snapshot_observed_on": as_of.isoformat(),
                "revenue": revenue,
                "net_income": net_profit,
                "roe": _snapshot_number(snapshots, f"CNROE:{ticker}"),
                "net_income_yoy": _snapshot_number(snapshots, f"CNYOYNI:{ticker}"),
                "sector_leader_score": _snapshot_number(
                    snapshots,
                    f"CNSCORE:{ticker}",
                ),
                "underlying_evidence_refs": snapshot_refs,
            }
        ],
        "underlying_evidence_refs": snapshot_refs,
        "source": "BaoStock latest fundamental and sector-ranking snapshot",
        "source_url": selected.source_url,
        "method_limitations": [
            "Only a latest snapshot is retained, so this is not a point-in-time filing trend.",
            "Revenue, profit and ROE require exchange-announcement provenance before causal use.",
            (
                "The sector score is a current cross-sectional rank, not a historical "
                "constituent rank."
            ),
        ],
    }
    macro = _macro_sensitivity_snapshot(session, ticker=ticker, price_rows=prices)
    if macro is not None:
        macro.update(
            {
                "source": "Local alignment of BaoStock A-share closes and retained macro series",
                "market_region": "china",
            }
        )
    company_documents = _china_company_document_evidence(
        session,
        ticker=ticker,
        company_name=company_name,
        as_of=as_of,
        limit=14,
    )
    disclosure_state = session.get(ChinaDisclosureSyncState, ticker)
    document_kinds = {
        str(kind) for document in company_documents for kind in document.get("evidence_kinds", [])
    }
    structured_counts = {
        "financial_metrics": 0,
        "shareholder_excerpts": 0,
        "operating_excerpts": 0,
        "supply_chain_excerpts": 0,
    }
    for document in company_documents:
        counts = structured_evidence_counts(document.get("structured_evidence"))
        for key, count in counts.items():
            structured_counts[key] += count
    periodic_available = "periodic_report" in document_kinds
    shareholder_available = "shareholder" in document_kinds
    operating_available = "operating" in document_kinds
    supply_chain_available = "supply_chain" in document_kinds
    evidence = [item for item in (technical, valuation, financial, macro) if item is not None]
    evidence.extend(company_documents)
    missing_structured_evidence: list[str] = []
    if not periodic_available:
        missing_structured_evidence.append(
            "exchange filing full text with original publication timestamps"
        )
    if not structured_counts["financial_metrics"]:
        missing_structured_evidence.append(
            "structured point-in-time quarterly cash-flow and balance-sheet line items"
        )
    if not operating_available:
        missing_structured_evidence.append("product ASP, volume, order and contract records")
    if not shareholder_available:
        missing_structured_evidence.append("shareholder and institution disclosure provenance")
    missing_structured_evidence.append("northbound daily capital-flow provenance")
    if not supply_chain_available:
        missing_structured_evidence.append(
            "facility coordinates, capacity and supplier dependency edges"
        )
    periodic_report_count = (
        disclosure_state.periodic_reports if disclosure_state is not None else int(periodic_available)
    )
    shareholder_document_count = (
        disclosure_state.shareholder_documents
        if disclosure_state is not None
        else int(shareholder_available)
    )
    operating_document_count = (
        disclosure_state.operating_documents
        if disclosure_state is not None
        else int(operating_available)
    )
    supply_chain_document_count = (
        disclosure_state.supply_chain_documents
        if disclosure_state is not None
        else int(supply_chain_available)
    )
    data_readiness = _china_equity_data_readiness(
        technical=technical,
        snapshot_count=len(snapshots),
        company_document_count=len(company_documents),
        periodic_report_count=periodic_report_count,
        structured_financial_metric_count=structured_counts["financial_metrics"],
        shareholder_document_count=shareholder_document_count,
        shareholder_excerpt_count=structured_counts["shareholder_excerpts"],
        operating_document_count=operating_document_count,
        operating_excerpt_count=structured_counts["operating_excerpts"],
        supply_chain_document_count=supply_chain_document_count,
        supply_chain_excerpt_count=structured_counts["supply_chain_excerpts"],
        macro_sensitivity=macro,
    )
    context = {
        "research_type": "public_equity",
        "market_region": "china",
        "research_scope": "market_factor_evidence",
        "ticker": ticker,
        "sec_ticker": None,
        "price_series_id": selected.series_id,
        "company": company_name,
        "sector": selected.sector,
        "point_in_time_cutoff": as_of.isoformat(),
        "required_dimensions": REQUIRED_EQUITY_DIMENSIONS,
        "reviewed_search_plan_not_evidence": {
            "missing_structured_evidence": missing_structured_evidence,
        },
        "technical_data_status": "calculated_from_baostock_forward_adjusted_closes",
        "financial_trend_status": (
            "official_periodic_filing_text_available_but_not_structured"
            if periodic_available
            else "latest_snapshot_only_not_filing_point_in_time"
        ),
        "macro_sensitivity_status": (
            "descriptive_aligned_changes_available" if macro else "missing"
        ),
        "data_readiness": data_readiness,
        "company_full_text_documents": len(company_documents),
        "official_disclosure_coverage": {
            "status": disclosure_state.status if disclosure_state is not None else "pending",
            "period_start": (
                disclosure_state.period_start.isoformat()
                if disclosure_state is not None and disclosure_state.period_start
                else None
            ),
            "period_end": (
                disclosure_state.period_end.isoformat()
                if disclosure_state is not None and disclosure_state.period_end
                else None
            ),
            "evidence_kinds": sorted(document_kinds),
            "periodic_reports": (
                disclosure_state.periodic_reports if disclosure_state is not None else 0
            ),
            "shareholder_documents": (
                disclosure_state.shareholder_documents if disclosure_state is not None else 0
            ),
            "operating_documents": (
                disclosure_state.operating_documents if disclosure_state is not None else 0
            ),
            "supply_chain_documents": (
                disclosure_state.supply_chain_documents if disclosure_state is not None else 0
            ),
        },
        "structured_disclosure_coverage": {
            **structured_counts,
            "status": (
                "official_excerpt_candidates_available_requires_table_reconciliation"
                if any(structured_counts.values())
                else "not_available"
            ),
        },
        "institutional_positioning_status": (
            "official_shareholder_disclosures_available_not_live_fund_flow"
            if shareholder_available
            else "missing_structured_a_share_flow_evidence"
        ),
        "insider_activity_status": (
            "official_shareholder_disclosures_available_not_transaction_normalized"
            if shareholder_available
            else "official_shareholder_disclosure_not_available"
        ),
        "evidence_scope_warning": (
            "Official CNINFO PDF/full-text evidence and exact structured excerpts are included "
            "when archived. Nearby numeric values remain extraction candidates until PDF table "
            "columns are reconciled; therefore the pack is not equivalent to a filing audit."
        ),
        "required_missing_evidence": missing_structured_evidence,
        "price_target_rule": (
            "Do not issue a target price or buy point from snapshot PE/PB and close-only "
            "technicals. Exchange filings and explicit operating assumptions are required."
        ),
    }
    return context, evidence


def _china_company_name(series_name: str, *, ticker: str) -> str:
    marker = f" ({ticker})"
    return series_name.split(marker, 1)[0].strip() if marker in series_name else series_name


def _china_snapshot_values(
    session: Session,
    *,
    ticker: str,
    as_of: date,
) -> dict[str, dict[str, Any]]:
    prefixes = ("CNSCORE", "CNMCAP", "CNREV", "CNNP", "CNROE", "CNYOYNI", "CNPE", "CNPB")
    result: dict[str, dict[str, Any]] = {}
    for prefix in prefixes:
        series_id = f"{prefix}:{ticker}"
        row = session.execute(
            select(MarketObservation.observed_on, MarketObservation.value)
            .where(
                MarketObservation.series_id == series_id,
                MarketObservation.observed_on <= as_of,
            )
            .order_by(desc(MarketObservation.observed_on))
            .limit(1)
        ).first()
        if row is not None:
            result[series_id] = {
                "observed_on": row.observed_on.isoformat(),
                "value": float(row.value),
            }
    return result


def _snapshot_number(
    snapshots: dict[str, dict[str, Any]],
    series_id: str,
) -> float | None:
    item = snapshots.get(series_id)
    value = item.get("value") if item else None
    return float(value) if isinstance(value, (int, float)) else None


def _china_company_document_evidence(
    session: Session,
    *,
    ticker: str,
    company_name: str,
    as_of: date,
    limit: int = 8,
) -> list[dict[str, Any]]:
    predicates = (
        Document.title.ilike(f"%{company_name}%"),
        Document.body.ilike(f"%{company_name}%"),
        Document.title.ilike(f"%{ticker}%"),
    )
    rows = list(
        session.execute(
            select(Document, Source)
            .join(Source, Source.id == Document.source_id)
            .where(
                Document.published_at.is_not(None),
                Document.published_at < as_of + timedelta(days=1),
                or_(*predicates),
            )
            .order_by(desc(Document.published_at), desc(Document.id))
            .limit(200)
        )
    )
    evidence: list[dict[str, Any]] = []
    for document, source in rows:
        tier = document_evidence_tier(document)
        if not can_verify_claims(tier):
            continue
        metadata = document.raw_metadata if isinstance(document.raw_metadata, dict) else {}
        structured_evidence = metadata.get("structured_evidence")
        if not isinstance(structured_evidence, dict):
            structured_evidence = extract_structured_disclosure_evidence(
                document.body or "",
                title=document.title,
                published_at=document.published_at,
            )
        evidence.append(
            {
                "evidence_id": f"document:{document.id}",
                "category": (
                    "official_company_disclosure"
                    if metadata.get("content_collector") == "cninfo_disclosure"
                    else "company_news_document"
                ),
                "ticker": ticker,
                "market_region": "china",
                "title": document.title[:500],
                "published_at": document.published_at.isoformat(),
                "source": source.name,
                "source_url": document.url,
                "excerpt": (document.body or "")[:1_000],
                "evidence_tier": tier,
                "can_verify_claims": True,
                "evidence_kinds": list(metadata.get("evidence_kinds") or []),
                "full_text_characters": metadata.get("full_text_characters"),
                "full_text_archive_path": document.raw_object_path,
                "structured_evidence": structured_evidence,
            }
        )
    evidence.sort(key=lambda item: item["category"] != "official_company_disclosure")
    return evidence[:limit]


def _technical_snapshot(
    ticker: str,
    rows: list[tuple[date, float]],
    *,
    daily_bars: list[MarketDailyBar] | None = None,
) -> dict[str, Any] | None:
    complete_bars = sorted(
        (daily_bars or []),
        key=lambda item: item.observed_on,
    )
    use_ohlcv = len(complete_bars) >= 35
    if use_ohlcv:
        dates = [item.observed_on for item in complete_bars]
        opens = [float(item.open_price) for item in complete_bars]
        highs = [float(item.high_price) for item in complete_bars]
        lows = [float(item.low_price) for item in complete_bars]
        closes = [float(item.close_price) for item in complete_bars]
        volumes = [
            float(item.volume) if item.volume is not None else None for item in complete_bars
        ]
    else:
        dates = [item[0] for item in rows]
        closes = [item[1] for item in rows]
        opens = highs = lows = volumes = None
    if len(closes) < 35:
        return None
    current = closes[-1]
    macd_line = _ema(closes, 12)[-1] - _ema(closes, 26)[-1]
    macd_series = [
        fast - slow for fast, slow in zip(_ema(closes, 12), _ema(closes, 26), strict=True)
    ]
    macd_signal = _ema(macd_series, 9)[-1]
    rsv_values = (
        _rolling_bar_stochastic(highs, lows, closes, 9)
        if highs is not None and lows is not None
        else _rolling_close_stochastic(closes, 9)
    )
    k_value, d_value = 50.0, 50.0
    for rsv in rsv_values:
        k_value = (2 / 3) * k_value + (1 / 3) * rsv
        d_value = (2 / 3) * d_value + (1 / 3) * k_value
    year_values = closes[-252:]
    sma_20 = _mean(closes[-20:])
    sma_50 = _mean(closes[-50:]) if len(closes) >= 50 else None
    sma_200 = _mean(closes[-200:]) if len(closes) >= 200 else None
    annualized_volatility = _annualized_volatility(closes[-64:])
    atr_14 = _average_true_range(highs, lows, closes, 14) if use_ohlcv else None
    valid_recent_volumes = [value for value in (volumes or [])[-20:] if value is not None]
    average_volume_20 = _mean(valid_recent_volumes) if valid_recent_volumes else None
    latest_volume = volumes[-1] if volumes else None
    volume_ratio_20 = (
        latest_volume / average_volume_20
        if latest_volume is not None and average_volume_20 not in {None, 0}
        else None
    )
    chart_points = _technical_chart_points(
        dates,
        closes,
        limit=90,
        opens=opens,
        highs=highs,
        lows=lows,
        volumes=volumes,
    )
    structure = (
        _ohlcv_structure(
            current=current,
            dates=dates,
            highs=highs,
            lows=lows,
            closes=closes,
            sma_20=sma_20,
            sma_50=sma_50,
            sma_200=sma_200,
            atr_14=atr_14,
            annualized_volatility=annualized_volatility,
        )
        if highs is not None and lows is not None
        else _close_only_structure(
            current=current,
            closes=closes,
            sma_20=sma_20,
            sma_50=sma_50,
            sma_200=sma_200,
            annualized_volatility=annualized_volatility,
        )
    )
    volume_status = None
    if volume_ratio_20 is not None:
        volume_status = (
            "high_volume"
            if volume_ratio_20 >= 1.2
            else "low_volume"
            if volume_ratio_20 <= 0.8
            else "normal_volume"
        )
    return {
        "evidence_id": f"derived:technical:{ticker}:{dates[-1].isoformat()}",
        "category": "derived_market_technical",
        "ticker": ticker,
        "observed_on": dates[-1].isoformat(),
        "history_start": dates[0].isoformat(),
        "history_end": dates[-1].isoformat(),
        "observations": len(closes),
        "bar_data_status": "complete_ohlcv" if use_ohlcv else "close_only_fallback",
        "adjusted_close": current,
        "sma_20": sma_20,
        "sma_50": sma_50,
        "sma_200": sma_200,
        "rsi_14": _rsi(closes, 14),
        "macd_12_26": macd_line,
        "macd_signal_9": macd_signal,
        "macd_histogram": macd_line - macd_signal,
        "kdj_k": k_value if use_ohlcv else None,
        "kdj_d": d_value if use_ohlcv else None,
        "kdj_j": 3 * k_value - 2 * d_value if use_ohlcv else None,
        "kdj_close_proxy_k": k_value if not use_ohlcv else None,
        "kdj_close_proxy_d": d_value if not use_ohlcv else None,
        "kdj_close_proxy_j": 3 * k_value - 2 * d_value if not use_ohlcv else None,
        "high_52_week_close": max(year_values),
        "low_52_week_close": min(year_values),
        "drawdown_from_52_week_high": current / max(year_values) - 1,
        "return_21d": _period_return(closes, 21),
        "return_63d": _period_return(closes, 63),
        "return_126d": _period_return(closes, 126),
        "return_252d": _period_return(closes, 252),
        "annualized_volatility_63d": annualized_volatility,
        "atr_14": atr_14,
        "atr_14_fraction": atr_14 / current if atr_14 is not None and current else None,
        "latest_volume": latest_volume,
        "average_volume_20": average_volume_20,
        "volume_ratio_20": volume_ratio_20,
        "volume_confirmation": {
            "status": volume_status,
            "latest_candle_direction": (
                "up"
                if opens is not None and current > opens[-1]
                else "down"
                if opens is not None and current < opens[-1]
                else "flat"
                if opens is not None
                else None
            ),
            "interpretation": (
                "Volume describes participation in the latest daily bar; it does not "
                "identify institutions or prove accumulation/distribution."
                if use_ohlcv
                else "Unavailable because complete daily volume is not retained."
            ),
        },
        "chart_points": chart_points,
        "price_structure": structure,
        "close_only_structure": structure,
        "risk_reward": structure["risk_reward"],
        "horizon_models": build_horizon_models(
            dates,
            closes,
            volumes=volumes,
        ),
        "source": (
            "Local calculation from Twelve Data split-adjusted daily OHLCV"
            if use_ohlcv
            else "Local calculation from Twelve Data split-adjusted daily closes"
        ),
        "source_url": TWELVE_HISTORY_DOCUMENTATION,
        "method_limitations": [
            (
                "OHLC prices are split-adjusted; volume is provider-reported and is not "
                "used to infer holder identity."
                if use_ohlcv
                else (
                    "KDJ is a close-only proxy because high/low bars are not retained "
                    "for this series."
                )
            ),
            "Daily closes cannot identify block trades or institutional cost basis.",
            "Technical indicators describe past prices and do not prove future direction.",
            (
                "Support, resistance, stop and target references use swing highs/lows, "
                "ATR, moving averages and historical volatility; they are scenario "
                "boundaries, not trading instructions."
                if use_ohlcv
                else (
                    "Support, resistance, stop and target references use closes, moving "
                    "averages and historical volatility; they are scenario boundaries, "
                    "not trading instructions."
                )
            ),
        ],
    }


def _technical_chart_points(
    dates: list[date],
    closes: list[float],
    *,
    limit: int,
    opens: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[float | None] | None = None,
) -> list[dict[str, Any]]:
    """Return a compact chart series without losing each average's lookback."""
    start = max(0, len(closes) - limit)
    points: list[dict[str, Any]] = []
    for index in range(start, len(closes)):
        points.append(
            {
                "date": dates[index].isoformat(),
                "open": opens[index] if opens is not None else None,
                "high": highs[index] if highs is not None else None,
                "low": lows[index] if lows is not None else None,
                "close": closes[index],
                "volume": volumes[index] if volumes is not None else None,
                "sma_20": (_mean(closes[index - 19 : index + 1]) if index >= 19 else None),
                "sma_50": (_mean(closes[index - 49 : index + 1]) if index >= 49 else None),
            }
        )
    return points


def _ohlcv_structure(
    *,
    current: float,
    dates: list[date],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    sma_20: float,
    sma_50: float | None,
    sma_200: float | None,
    atr_14: float | None,
    annualized_volatility: float | None,
) -> dict[str, Any]:
    """Build scenario levels from actual bars, pivots and ATR volatility."""
    candidates: list[tuple[str, float]] = [("SMA20", sma_20)]
    if sma_50 is not None:
        candidates.append(("SMA50", sma_50))
    if sma_200 is not None:
        candidates.append(("SMA200", sma_200))
    start = max(0, len(closes) - 126)
    for index in range(max(start, 2), len(closes) - 2):
        local_lows = lows[index - 2 : index + 3]
        local_highs = highs[index - 2 : index + 3]
        if lows[index] == min(local_lows):
            candidates.append((f"{dates[index].isoformat()} 波段低点", lows[index]))
        if highs[index] == max(local_highs):
            candidates.append((f"{dates[index].isoformat()} 波段高点", highs[index]))
    for window in (20, 50, 63):
        bounded = min(window, len(closes))
        candidates.extend(
            (
                (f"{bounded}日最低价", min(lows[-bounded:])),
                (f"{bounded}日最高价", max(highs[-bounded:])),
            )
        )
    meaningful_gap = max(0.25 * (atr_14 or 0), current * 0.0025)
    supports = sorted(
        (
            (_structure_role_label(label, role="support"), value)
            for label, value in candidates
            if value <= current - meaningful_gap
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    resistances = sorted(
        (
            (_structure_role_label(label, role="resistance"), value)
            for label, value in candidates
            if value >= current + meaningful_gap
        ),
        key=lambda item: item[1],
    )
    support = supports[0] if supports else None
    resistance = resistances[0] if resistances else None
    daily_volatility = (
        annualized_volatility / math.sqrt(252) if annualized_volatility is not None else None
    )
    expected_5d = daily_volatility * math.sqrt(5) if daily_volatility else None
    expected_10d = daily_volatility * math.sqrt(10) if daily_volatility else None
    one_week_low = current * (1 - expected_5d) if expected_5d else None
    one_week_high = current * (1 + expected_5d) if expected_5d else None
    two_week_low = current * (1 - expected_10d) if expected_10d else None
    two_week_high = current * (1 + expected_10d) if expected_10d else None
    if support is not None:
        stop_reference = support[1] - 0.5 * (atr_14 or 0)
        stop_basis = f"{support[0]}下方留出0.5倍ATR14缓冲"
    else:
        stop_reference = current - 1.5 * atr_14 if atr_14 is not None else one_week_low
        stop_basis = "缺少下方波段位，使用1.5倍ATR14或一周历史波动下沿"
    if resistance is not None:
        target_reference = resistance[1]
        target_basis = resistance[0]
    else:
        target_reference = current + 2 * atr_14 if atr_14 is not None else two_week_high
        target_basis = "缺少上方波段位，使用2倍ATR14或两周历史波动上沿"
    downside = (
        (current - stop_reference) / current
        if stop_reference is not None and stop_reference < current
        else None
    )
    upside = (
        (target_reference - current) / current
        if target_reference is not None and target_reference > current
        else None
    )
    reward_risk = upside / downside if upside is not None and downside not in {None, 0} else None
    return {
        "method": "split_adjusted_ohlcv_swing_structure_plus_atr14",
        "minimum_level_gap": meaningful_gap,
        "nearest_support": {"label": support[0], "value": support[1]} if support else None,
        "nearest_resistance": (
            {"label": resistance[0], "value": resistance[1]} if resistance else None
        ),
        "one_week_volatility_band": {
            "lower": one_week_low,
            "upper": one_week_high,
            "expected_move": expected_5d,
        },
        "two_week_volatility_band": {
            "lower": two_week_low,
            "upper": two_week_high,
            "expected_move": expected_10d,
        },
        "risk_reward": {
            "entry_reference": current,
            "stop_reference": stop_reference,
            "stop_basis": stop_basis,
            "target_reference": target_reference,
            "target_basis": target_basis,
            "downside_fraction": downside,
            "upside_fraction": upside,
            "reward_risk_ratio": reward_risk,
            "interpretation": (
                "Research scenario from point-in-time split-adjusted OHLCV; not a "
                "recommendation, order instruction or guarantee of execution."
            ),
        },
    }


def _structure_role_label(label: str, *, role: str) -> str:
    """Explain when a crossed pivot is reused as a scenario support/resistance."""
    if role == "support" and "波段高点" in label:
        return f"已突破 {label}（回踩参考）"
    if role == "resistance" and "波段低点" in label:
        return f"已跌破 {label}（反抽参考）"
    return label


def _close_only_structure(
    *,
    current: float,
    closes: list[float],
    sma_20: float,
    sma_50: float | None,
    sma_200: float | None,
    annualized_volatility: float | None,
) -> dict[str, Any]:
    """Create auditable close-only levels and a non-prescriptive R/R scenario."""
    candidates: list[tuple[str, float]] = [("SMA20", sma_20)]
    if sma_50 is not None:
        candidates.append(("SMA50", sma_50))
    if sma_200 is not None:
        candidates.append(("SMA200", sma_200))
    for window in (20, 50, 63, 252):
        values = closes[-min(window, len(closes)) :]
        candidates.extend(
            (
                (f"{min(window, len(closes))}日收盘低点", min(values)),
                (f"{min(window, len(closes))}日收盘高点", max(values)),
            )
        )
    supports = sorted(
        ((label, value) for label, value in candidates if value < current),
        key=lambda item: item[1],
        reverse=True,
    )
    resistances = sorted(
        ((label, value) for label, value in candidates if value > current),
        key=lambda item: item[1],
    )
    support = supports[0] if supports else None
    resistance = resistances[0] if resistances else None
    daily_volatility = (
        annualized_volatility / math.sqrt(252) if annualized_volatility is not None else None
    )
    expected_5d = daily_volatility * math.sqrt(5) if daily_volatility else None
    expected_10d = daily_volatility * math.sqrt(10) if daily_volatility else None
    one_week_low = current * (1 - expected_5d) if expected_5d else None
    one_week_high = current * (1 + expected_5d) if expected_5d else None
    two_week_low = current * (1 - expected_10d) if expected_10d else None
    two_week_high = current * (1 + expected_10d) if expected_10d else None

    if support is not None:
        stop_reference = support[1] * (1 - 0.25 * (expected_5d or 0))
        stop_basis = f"{support[0]}下方留出0.25倍一周历史波动缓冲"
    else:
        stop_reference = one_week_low
        stop_basis = "缺少更近收盘结构位，使用一周一倍历史波动下沿"
    if resistance is not None:
        target_reference = resistance[1]
        target_basis = resistance[0]
    else:
        target_reference = two_week_high
        target_basis = "缺少更近收盘阻力位，使用两周一倍历史波动上沿"
    downside = (
        (current - stop_reference) / current
        if stop_reference is not None and stop_reference < current
        else None
    )
    upside = (
        (target_reference - current) / current
        if target_reference is not None and target_reference > current
        else None
    )
    reward_risk = upside / downside if upside is not None and downside not in {None, 0} else None
    return {
        "method": "close_only_structure_plus_63d_historical_volatility",
        "nearest_support": ({"label": support[0], "value": support[1]} if support else None),
        "nearest_resistance": (
            {"label": resistance[0], "value": resistance[1]} if resistance else None
        ),
        "one_week_volatility_band": {
            "lower": one_week_low,
            "upper": one_week_high,
            "expected_move": expected_5d,
        },
        "two_week_volatility_band": {
            "lower": two_week_low,
            "upper": two_week_high,
            "expected_move": expected_10d,
        },
        "risk_reward": {
            "entry_reference": current,
            "stop_reference": stop_reference,
            "stop_basis": stop_basis,
            "target_reference": target_reference,
            "target_basis": target_basis,
            "downside_fraction": downside,
            "upside_fraction": upside,
            "reward_risk_ratio": reward_risk,
            "interpretation": (
                "Research scenario from point-in-time closes; not a recommendation, "
                "order instruction or guarantee of execution."
            ),
        },
    }


def _institutional_positioning_snapshot(
    ticker: str,
    holdings: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Expose a 13F valuation proxy while explicitly refusing a fake cost basis."""
    if not holdings:
        return None
    usable = [
        item
        for item in holdings
        if float(item.get("reported_shares") or 0) > 0
        and float(item.get("reported_value_usd") or 0) > 0
    ]
    total_shares = sum(float(item["reported_shares"]) for item in usable)
    total_value = sum(float(item["reported_value_usd"]) for item in usable)
    report_period = str(holdings[0].get("report_period") or "")
    return {
        "evidence_id": f"derived:institutional-positioning:{ticker}:{report_period}",
        "category": "derived_institutional_positioning",
        "ticker": ticker,
        "report_period": report_period,
        "manager_rows_returned": len(holdings),
        "actual_average_cost": None,
        "actual_average_cost_status": "unavailable_from_form_13f",
        "quarter_end_value_per_share_proxy": (
            total_value / total_shares if total_shares > 0 else None
        ),
        "proxy_scope": "weighted across the returned top manager rows only",
        "top_manager_proxies": [
            {
                "manager_name": item.get("manager_name"),
                "reported_shares": item.get("reported_shares"),
                "reported_share_change": item.get("reported_share_change"),
                "quarter_end_value_per_share_proxy": (
                    float(item["reported_value_usd"]) / float(item["reported_shares"])
                    if float(item.get("reported_shares") or 0) > 0
                    else None
                ),
            }
            for item in usable[:5]
        ],
        "source": "Derived from SEC Form 13F structured quarter-end values",
        "method_limitations": [
            (
                "The proxy is reported quarter-end value divided by shares, not purchase "
                "price or cost basis."
            ),
            (
                "13F is delayed, can be amended, excludes many assets and does not reveal "
                "intraday trades."
            ),
            "The returned manager rows are not the full shareholder register.",
        ],
    }


def _latest_annual_facts(
    session: Session,
    *,
    ticker: str,
    as_of: date,
) -> dict[str, CompanyFinancialFact]:
    concepts = {
        "CommonStockSharesOutstanding",
        "EarningsPerShareDiluted",
        "GrossProfit",
        "NetIncomeLoss",
        "OperatingIncomeLoss",
        "ResearchAndDevelopmentExpense",
        "InventoryNet",
        "NetCashProvidedByUsedInOperatingActivities",
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    }
    rows = session.scalars(
        select(CompanyFinancialFact)
        .where(
            CompanyFinancialFact.ticker == ticker,
            CompanyFinancialFact.concept.in_(concepts),
            CompanyFinancialFact.form.in_(("10-K", "10-K/A")),
            CompanyFinancialFact.filed_at <= as_of,
        )
        .order_by(
            desc(CompanyFinancialFact.period_end),
            desc(CompanyFinancialFact.filed_at),
        )
        .limit(300)
    )
    result: dict[str, CompanyFinancialFact] = {}
    for fact in rows:
        result.setdefault(fact.concept, fact)
    return result


def _latest_instant_fact(
    session: Session,
    *,
    ticker: str,
    concept: str,
    as_of: date,
) -> CompanyFinancialFact | None:
    return session.scalar(
        select(CompanyFinancialFact)
        .where(
            CompanyFinancialFact.ticker == ticker,
            CompanyFinancialFact.concept == concept,
            CompanyFinancialFact.filed_at <= as_of,
            CompanyFinancialFact.period_end <= as_of,
        )
        .order_by(
            desc(CompanyFinancialFact.period_end),
            desc(CompanyFinancialFact.filed_at),
        )
        .limit(1)
    )


def _latest_valuation_basis(
    session: Session,
    *,
    ticker: str,
    as_of: date,
    annual_facts: dict[str, CompanyFinancialFact],
) -> dict[str, Any]:
    """Build a point-in-time TTM proxy from annual and comparable quarter facts."""
    revenue_fact = _preferred_revenue_fact(annual_facts)
    if revenue_fact is None:
        return {"basis": "latest_fiscal_year", "values": {}, "facts": []}
    annual_end = revenue_fact.period_end
    concepts = {
        "EarningsPerShareDiluted",
        "GrossProfit",
        "NetIncomeLoss",
        "OperatingIncomeLoss",
        "ResearchAndDevelopmentExpense",
        revenue_fact.concept,
    }
    quarter_rows = list(
        session.scalars(
            select(CompanyFinancialFact)
            .where(
                CompanyFinancialFact.ticker == ticker,
                CompanyFinancialFact.concept.in_(concepts),
                CompanyFinancialFact.form.in_(("10-Q", "10-Q/A")),
                CompanyFinancialFact.filed_at <= as_of,
                CompanyFinancialFact.period_end <= as_of,
                CompanyFinancialFact.period_start.is_not(None),
            )
            .order_by(
                desc(CompanyFinancialFact.filed_at),
                desc(CompanyFinancialFact.period_end),
            )
            .limit(1_500)
        )
    )
    quarterly: dict[tuple[str, date], CompanyFinancialFact] = {}
    for fact in quarter_rows:
        if fact.period_start is None:
            continue
        duration = (fact.period_end - fact.period_start).days
        if not 60 <= duration <= 120:
            continue
        quarterly.setdefault((fact.concept, fact.period_end), fact)
    revenue_ends = sorted(
        period_end
        for concept, period_end in quarterly
        if concept == revenue_fact.concept and period_end > annual_end
    )
    current_ends = revenue_ends[-3:]
    if len(current_ends) != 3:
        return _annual_valuation_basis(annual_facts)

    prior_revenue_ends = sorted(
        period_end
        for concept, period_end in quarterly
        if concept == revenue_fact.concept and period_end <= annual_end
    )
    prior_ends: list[date] = []
    for current_end in current_ends:
        candidates = [
            period_end
            for period_end in prior_revenue_ends
            if 340 <= (current_end - period_end).days <= 390
        ]
        if not candidates:
            return _annual_valuation_basis(annual_facts)
        prior_ends.append(min(candidates, key=lambda value: abs((current_end - value).days - 365)))
    if len(set(prior_ends)) != 3:
        return _annual_valuation_basis(annual_facts)

    values: dict[str, float] = {}
    used_facts: list[CompanyFinancialFact] = []
    for concept in concepts:
        annual_fact = annual_facts.get(concept)
        current_facts = [quarterly.get((concept, period_end)) for period_end in current_ends]
        prior_facts = [quarterly.get((concept, period_end)) for period_end in prior_ends]
        if annual_fact is None or any(fact is None for fact in [*current_facts, *prior_facts]):
            return _annual_valuation_basis(annual_facts)
        current_values = [fact.value for fact in current_facts if fact is not None]
        prior_values = [fact.value for fact in prior_facts if fact is not None]
        values[concept] = annual_fact.value + sum(current_values) - sum(prior_values)
        used_facts.extend(
            [
                annual_fact,
                *[fact for fact in current_facts if fact],
                *[fact for fact in prior_facts if fact],
            ]
        )
    unique_facts: dict[tuple[str, date, str], CompanyFinancialFact] = {}
    for fact in used_facts:
        unique_facts[(fact.concept, fact.period_end, fact.accession_number)] = fact
    return {
        "basis": "ttm_proxy",
        "period_end": current_ends[-1].isoformat(),
        "annual_period_end": annual_end.isoformat(),
        "current_quarter_ends": [value.isoformat() for value in current_ends],
        "prior_comparable_quarter_ends": [value.isoformat() for value in prior_ends],
        "values": values,
        "facts": list(unique_facts.values()),
    }


def _annual_valuation_basis(
    annual_facts: dict[str, CompanyFinancialFact],
) -> dict[str, Any]:
    period_end = max(
        (fact.period_end for fact in annual_facts.values()),
        default=None,
    )
    return {
        "basis": "latest_fiscal_year",
        "period_end": period_end.isoformat() if period_end else None,
        "values": {concept: fact.value for concept, fact in annual_facts.items()},
        "facts": list(annual_facts.values()),
    }


def _financial_trend_snapshot(
    session: Session,
    *,
    ticker: str,
    as_of: date,
) -> dict[str, Any] | None:
    """Build a filing-date-bounded annual operating and cash-flow trend."""
    concepts = {
        "GrossProfit",
        "InventoryNet",
        "NetCashProvidedByUsedInOperatingActivities",
        "NetIncomeLoss",
        "OperatingIncomeLoss",
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "ResearchAndDevelopmentExpense",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    }
    facts = list(
        session.scalars(
            select(CompanyFinancialFact)
            .where(
                CompanyFinancialFact.ticker == ticker,
                CompanyFinancialFact.concept.in_(concepts),
                CompanyFinancialFact.form.in_(("10-K", "10-K/A")),
                CompanyFinancialFact.filed_at <= as_of,
            )
            .order_by(
                desc(CompanyFinancialFact.filed_at),
                desc(CompanyFinancialFact.period_end),
            )
            .limit(1_000)
        )
    )
    by_year: dict[int, dict[str, CompanyFinancialFact]] = {}
    for fact in facts:
        is_instant = fact.concept == "InventoryNet"
        if not is_instant:
            if fact.period_start is None:
                continue
            duration_days = (fact.period_end - fact.period_start).days
            if not 300 <= duration_days <= 400:
                continue
        # SEC Company Facts can label comparative rows with the filing's FY.
        # The actual period end is the stable year key for annual trend math.
        fiscal_year = fact.period_end.year
        if fiscal_year > as_of.year:
            continue
        by_year.setdefault(fiscal_year, {}).setdefault(fact.concept, fact)
    retained_years = sorted(by_year)[-6:]
    if not retained_years:
        return None

    periods: list[dict[str, Any]] = []
    previous_revenue: float | None = None
    previous_net_income: float | None = None
    evidence_refs: list[str] = []
    for fiscal_year in retained_years:
        values = by_year[fiscal_year]
        revenue = _preferred_revenue_fact(values)
        net_income = values.get("NetIncomeLoss")
        gross_profit = values.get("GrossProfit")
        operating_income = values.get("OperatingIncomeLoss")
        operating_cash_flow = values.get("NetCashProvidedByUsedInOperatingActivities")
        capital_expenditure = values.get("PaymentsToAcquirePropertyPlantAndEquipment")
        research_and_development = values.get("ResearchAndDevelopmentExpense")
        inventory = values.get("InventoryNet")
        revenue_value = revenue.value if revenue else None
        net_income_value = net_income.value if net_income else None
        capex_value = capital_expenditure.value if capital_expenditure else None
        operating_cash_flow_value = operating_cash_flow.value if operating_cash_flow else None
        period_facts = [
            revenue,
            net_income,
            gross_profit,
            operating_income,
            operating_cash_flow,
            capital_expenditure,
            research_and_development,
            inventory,
        ]
        period_refs = [_financial_fact_ref(fact) for fact in period_facts if fact]
        evidence_refs.extend(period_refs)
        periods.append(
            {
                "fiscal_year": fiscal_year,
                "period_end": _max_fact_date(period_facts, "period_end"),
                "filed_at": _max_fact_date(period_facts, "filed_at"),
                "revenue": revenue_value,
                "revenue_yoy": _growth_rate(revenue_value, previous_revenue),
                "gross_profit": gross_profit.value if gross_profit else None,
                "gross_margin": _safe_ratio(
                    gross_profit.value if gross_profit else None,
                    revenue_value,
                ),
                "operating_income": (operating_income.value if operating_income else None),
                "operating_margin": _safe_ratio(
                    operating_income.value if operating_income else None,
                    revenue_value,
                ),
                "net_income": net_income_value,
                "net_income_yoy": _growth_rate(
                    net_income_value,
                    previous_net_income,
                ),
                "operating_cash_flow": operating_cash_flow_value,
                "capital_expenditure": capex_value,
                "free_cash_flow_proxy": (
                    operating_cash_flow_value - capex_value
                    if operating_cash_flow_value is not None and capex_value is not None
                    else None
                ),
                "research_and_development": (
                    research_and_development.value if research_and_development else None
                ),
                "inventory": inventory.value if inventory else None,
                "underlying_evidence_refs": period_refs,
            }
        )
        previous_revenue = revenue_value
        previous_net_income = net_income_value

    return {
        "evidence_id": f"derived:financial-trend:{ticker}:{as_of.isoformat()}",
        "category": "derived_company_financial_trend",
        "ticker": ticker,
        "as_of": as_of.isoformat(),
        "periods": periods[-5:],
        "underlying_evidence_refs": list(dict.fromkeys(evidence_refs))[-40:],
        "source": "Local point-in-time calculation from SEC EDGAR Company Facts",
        "method_limitations": [
            "Only filings available on or before the market-data cutoff are used.",
            "Annual standardized facts can contain restatements and taxonomy changes.",
            "Free cash flow is a simple operating-cash-flow minus capex proxy.",
            "Earnings can be cyclical; historical growth is not a forecast.",
        ],
    }


def _macro_sensitivity_snapshot(
    session: Session,
    *,
    ticker: str,
    price_rows: list[tuple[date, float]],
) -> dict[str, Any] | None:
    """Align daily changes and expose correlations without claiming causality."""
    if len(price_rows) < 80:
        return None
    as_of = price_rows[-1][0]
    equity_changes = _series_changes(price_rows, transformation="log_return")
    sensitivities: list[dict[str, Any]] = []
    for series_id, (name, transformation) in MACRO_SENSITIVITY_SERIES.items():
        rows = list(
            session.execute(
                select(MarketObservation.observed_on, MarketObservation.value)
                .where(
                    MarketObservation.series_id == series_id,
                    MarketObservation.observed_on <= as_of,
                )
                .order_by(desc(MarketObservation.observed_on))
                .limit(520)
            )
        )
        rows.reverse()
        factor_changes = _series_changes(
            [(observed_on, float(value)) for observed_on, value in rows],
            transformation=transformation,
        )
        common_dates = sorted(set(equity_changes) & set(factor_changes))[-252:]
        if len(common_dates) < 60:
            continue
        equity_values = [equity_changes[item] for item in common_dates]
        factor_values = [factor_changes[item] for item in common_dates]
        sensitivities.append(
            {
                "series_id": series_id,
                "name": name,
                "transformation": transformation,
                "window_start": common_dates[0].isoformat(),
                "window_end": common_dates[-1].isoformat(),
                "sample_size": len(common_dates),
                "contemporaneous_correlation": _pearson(
                    factor_values,
                    equity_values,
                ),
                "univariate_beta": _beta(factor_values, equity_values),
                "latest_factor_value": float(rows[-1][1]) if rows else None,
                "latest_factor_date": rows[-1][0].isoformat() if rows else None,
            }
        )
    if not sensitivities:
        return None
    return {
        "evidence_id": f"derived:macro-sensitivity:{ticker}:{as_of.isoformat()}",
        "category": "derived_macro_sensitivity",
        "ticker": ticker,
        "as_of": as_of.isoformat(),
        "equity_return": "daily_log_return",
        "sensitivities": sensitivities,
        "source": "Local alignment of Twelve Data equity prices and FRED series",
        "method_limitations": [
            "Correlation and univariate beta are descriptive, not causal evidence.",
            "Contemporaneous daily changes do not identify funding-flow mechanisms.",
            "Overlapping macro factors and regime changes require multivariate tests.",
            "Japanese carry-trade claims still require FX basis, hedging and flow data.",
        ],
    }


def _company_document_evidence(
    session: Session,
    *,
    ticker: str,
    company_name: str | None = None,
    as_of: date,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Put substantive company-specific local documents ahead of generic news."""
    aliases = _company_search_aliases(ticker=ticker, company_name=company_name)
    if not aliases:
        return []
    predicates = []
    for alias in aliases:
        predicates.append(Document.title.ilike(f"%{alias}%"))
        # Three-letter ticker searches in full article bodies create too many
        # incidental substring matches. Keep the exact ticker useful in titles,
        # while searching substantive body text only with long or non-ASCII names.
        if len(alias) >= 4 or not alias.isascii():
            predicates.append(Document.body.ilike(f"%{alias}%"))
    rows = list(
        session.execute(
            select(Document, Source)
            .join(Source, Source.id == Document.source_id)
            .where(
                Document.published_at.is_not(None),
                Document.published_at < as_of + timedelta(days=1),
                or_(*predicates),
            )
            .order_by(desc(Document.published_at), desc(Document.id))
            .limit(300)
        )
    )
    ranked: list[tuple[int, Document, Source]] = []
    product_terms = COMPANY_RESEARCH_PROFILES.get(ticker, {}).get("products", [])
    for document, source in rows:
        title = document.title or ""
        body = document.body or ""
        if not _contains_company_alias(f"{title} {body}", aliases):
            continue
        tier = document_evidence_tier(document)
        if not can_verify_claims(tier):
            continue
        score = _company_document_subject_score(
            ticker=ticker,
            document=document,
            aliases=aliases,
        )
        if score is None:
            continue
        score += sum(term.casefold() in f"{title} {body}".casefold() for term in product_terms)
        ranked.append((score, document, source))
    ranked.sort(
        key=lambda item: (
            item[0],
            item[1].published_at or item[1].fetched_at,
            item[1].id,
        ),
        reverse=True,
    )
    return [
        {
            "evidence_id": f"document:{document.id}",
            "category": "company_news_document",
            "ticker": ticker,
            "title": document.title[:500],
            "published_at": (document.published_at.isoformat() if document.published_at else None),
            "source": source.name,
            "source_url": document.url,
            "excerpt": (document.body or "")[:1_000],
            "evidence_tier": document_evidence_tier(document),
            "can_verify_claims": True,
        }
        for _, document, source in ranked[:limit]
    ]


def _company_search_aliases(*, ticker: str, company_name: str | None) -> list[str]:
    """Use reviewed aliases plus the SEC catalog name for every covered issuer."""
    candidates = list(COMPANY_ALIASES.get(ticker, ()))
    if company_name:
        official = re.sub(r"\s+", " ", company_name).strip()
        candidates.append(official)
        without_suffix = re.sub(
            r"(?:[,.]?\s+)(?:incorporated|inc|corporation|corp|company|co|plc|ltd)\.?$",
            "",
            official,
            flags=re.IGNORECASE,
        ).strip()
        if without_suffix:
            candidates.append(without_suffix)
    elif not candidates:
        candidates.append(ticker.casefold())
    return list(dict.fromkeys(item.casefold() for item in candidates if item.strip()))


def _preferred_revenue_fact(
    values: dict[str, CompanyFinancialFact],
) -> CompanyFinancialFact | None:
    concept_priority = {
        concept: priority
        for priority, concept in enumerate(
            (
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues",
                "SalesRevenueNet",
            )
        )
    }
    candidates = [fact for concept, fact in values.items() if concept in concept_priority]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda fact: (
            fact.period_end,
            fact.filed_at,
            -concept_priority[fact.concept],
        ),
    )


def _financial_fact_ref(fact: CompanyFinancialFact) -> str:
    return f"sec:{fact.ticker}:{fact.concept}:{fact.period_end.isoformat()}:{fact.accession_number}"


def _max_fact_date(
    facts: list[CompanyFinancialFact | None],
    attribute: str,
) -> str | None:
    values = [getattr(fact, attribute) for fact in facts if fact is not None]
    return max(values).isoformat() if values else None


def _growth_rate(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous <= 1e-12:
        return None
    return current / previous - 1


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or abs(denominator) <= 1e-12:
        return None
    return numerator / denominator


def _series_changes(
    rows: list[tuple[date, float]],
    *,
    transformation: str,
) -> dict[date, float]:
    result: dict[date, float] = {}
    for index in range(1, len(rows)):
        observed_on, current = rows[index]
        previous = rows[index - 1][1]
        if transformation == "log_return":
            if current <= 0 or previous <= 0:
                continue
            result[observed_on] = math.log(current / previous)
        else:
            result[observed_on] = current - previous
    return result


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    left_mean = _mean(left)
    right_mean = _mean(right)
    numerator = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left, right, strict=True)
    )
    left_sum = sum((value - left_mean) ** 2 for value in left)
    right_sum = sum((value - right_mean) ** 2 for value in right)
    denominator = math.sqrt(left_sum * right_sum)
    return numerator / denominator if denominator > 1e-18 else None


def _beta(factor: list[float], equity: list[float]) -> float | None:
    if len(factor) != len(equity) or len(factor) < 3:
        return None
    factor_mean = _mean(factor)
    equity_mean = _mean(equity)
    variance = sum((value - factor_mean) ** 2 for value in factor)
    if variance <= 1e-18:
        return None
    covariance = sum(
        (factor_value - factor_mean) * (equity_value - equity_mean)
        for factor_value, equity_value in zip(factor, equity, strict=True)
    )
    return covariance / variance


def _contains_company_alias(text: str, aliases: list[str]) -> bool:
    normalized = text.casefold()
    return any(_contains_alias(normalized, alias.casefold()) for alias in aliases)


def _company_document_subject_score(
    *,
    ticker: str,
    document: Document,
    aliases: list[str],
) -> int | None:
    """Reject incidental name matches before company news reaches the model."""
    title = (document.title or "").casefold()
    body = (document.body or "").casefold()
    # Long aggregations and ranking pages often mention a large issuer several
    # times in an unrelated sidebar or comparison table.  A company document
    # must therefore identify the issuer in the headline or in the opening
    # 1,500 characters, where the article's actual subject is established.
    lead = body[:1_500]
    title_hit = _contains_company_alias(title, aliases)
    lead_hit = _contains_company_alias(lead, aliases)
    body_hits = sum(body.count(alias.casefold()) for alias in aliases)
    if not title_hit and (not lead_hit or body_hits < 2):
        return None

    if ticker == "AAPL":
        hostname = (urlsplit(document.url).hostname or "").casefold().removeprefix("www.")
        if hostname in AAPL_RETAIL_DOMAINS:
            return None
        combined = f"{title} {body}"
        has_technology_context = any(term in combined for term in AAPL_TECH_TERMS)
        if any(term in combined for term in AAPL_FRUIT_TERMS) and not has_technology_context:
            return None
        if any(re.search(pattern, title) for pattern in AAPL_ACCESSORY_PATTERNS):
            has_corporate_identity = any(
                marker in combined for marker in ("aapl", "apple inc", "苹果公司")
            )
            if not has_corporate_identity:
                return None

    return 3 * int(title_hit) + 2 * int(lead_hit) + min(body_hits, 2)


def _valuation_snapshot(
    ticker: str,
    rows: list[tuple[date, float]],
    facts: dict[str, CompanyFinancialFact],
    *,
    question: str,
    valuation_basis: dict[str, Any],
    latest_shares: CompanyFinancialFact | None,
) -> dict[str, Any] | None:
    if not rows:
        return None
    price = rows[-1][1]
    shares = latest_shares or facts.get("CommonStockSharesOutstanding")
    revenue = _preferred_revenue_fact(facts)
    net_income = facts.get("NetIncomeLoss")
    eps = facts.get("EarningsPerShareDiluted")
    gross_profit = facts.get("GrossProfit")
    operating_income = facts.get("OperatingIncomeLoss")
    research_and_development = facts.get("ResearchAndDevelopmentExpense")
    basis_values = valuation_basis.get("values")
    basis_values = basis_values if isinstance(basis_values, dict) else {}
    basis_revenue = basis_values.get(revenue.concept) if revenue else None
    basis_net_income = basis_values.get("NetIncomeLoss")
    basis_eps = basis_values.get("EarningsPerShareDiluted")
    basis_gross_profit = basis_values.get("GrossProfit")
    basis_operating_income = basis_values.get("OperatingIncomeLoss")
    basis_research_and_development = basis_values.get("ResearchAndDevelopmentExpense")
    shares_value = shares.value if shares and shares.value > 0 else None
    market_cap = price * shares_value if shares_value else None
    target_prices = _question_target_prices(question)
    scenarios = []
    for target in target_prices:
        implied_cap = target * shares_value if shares_value else None
        scenarios.append(
            {
                "target_price": target,
                "implied_market_cap": implied_cap,
                "implied_price_to_sales": (
                    implied_cap / basis_revenue
                    if implied_cap is not None
                    and isinstance(basis_revenue, (int, float))
                    and basis_revenue > 0
                    else None
                ),
                "implied_price_to_earnings": (
                    target / basis_eps
                    if isinstance(basis_eps, (int, float)) and basis_eps > 0
                    else None
                ),
            }
        )
    basis_facts = [
        fact for fact in valuation_basis.get("facts", []) if isinstance(fact, CompanyFinancialFact)
    ]
    fact_refs = list(
        dict.fromkeys(
            [
                f"sec:{fact.ticker}:{fact.concept}:{fact.period_end.isoformat()}:"
                f"{fact.accession_number}"
                for fact in [
                    shares,
                    revenue,
                    gross_profit,
                    operating_income,
                    net_income,
                    eps,
                    research_and_development,
                    *basis_facts,
                ]
                if fact is not None
            ]
        )
    )
    return {
        "evidence_id": f"derived:valuation:{ticker}:{rows[-1][0].isoformat()}",
        "category": "derived_company_valuation",
        "ticker": ticker,
        "price": price,
        "price_observed_on": rows[-1][0].isoformat(),
        "shares_outstanding": shares_value,
        "market_cap": market_cap,
        "annual_revenue": revenue.value if revenue else None,
        "annual_gross_profit": gross_profit.value if gross_profit else None,
        "annual_operating_income": (operating_income.value if operating_income else None),
        "annual_net_income": net_income.value if net_income else None,
        "annual_diluted_eps": eps.value if eps else None,
        "annual_research_and_development": (
            research_and_development.value if research_and_development else None
        ),
        "valuation_basis": valuation_basis.get("basis", "latest_fiscal_year"),
        "valuation_basis_period_end": valuation_basis.get("period_end"),
        "basis_revenue": basis_revenue,
        "basis_gross_profit": basis_gross_profit,
        "basis_operating_income": basis_operating_income,
        "basis_net_income": basis_net_income,
        "basis_diluted_eps_proxy": basis_eps,
        "basis_research_and_development": basis_research_and_development,
        "gross_margin": (
            basis_gross_profit / basis_revenue
            if isinstance(basis_gross_profit, (int, float))
            and isinstance(basis_revenue, (int, float))
            and basis_revenue > 0
            else None
        ),
        "operating_margin": (
            basis_operating_income / basis_revenue
            if isinstance(basis_operating_income, (int, float))
            and isinstance(basis_revenue, (int, float))
            and basis_revenue > 0
            else None
        ),
        "research_and_development_to_revenue": (
            basis_research_and_development / basis_revenue
            if isinstance(basis_research_and_development, (int, float))
            and isinstance(basis_revenue, (int, float))
            and basis_revenue > 0
            else None
        ),
        "trailing_price_to_sales": (
            market_cap / basis_revenue
            if market_cap is not None
            and isinstance(basis_revenue, (int, float))
            and basis_revenue > 0
            else None
        ),
        "trailing_price_to_earnings": (
            price / basis_eps if isinstance(basis_eps, (int, float)) and basis_eps > 0 else None
        ),
        "question_price_scenarios": scenarios,
        "underlying_evidence_refs": fact_refs,
        "method_limitations": [
            "TTM proxy uses latest annual facts plus current comparable quarters minus "
            "prior-year comparable quarters; diluted EPS addition is approximate.",
            "Simple trailing multiples are not a discounted cash-flow valuation.",
            "Fiscal periods, cyclicality, dilution and one-time items require review.",
            "A target price is unsupported unless its operating and multiple "
            "assumptions are explicit.",
        ],
    }


def _contains_alias(text: str, alias: str) -> bool:
    if re.fullmatch(r"[a-z0-9.]+", alias):
        return re.search(rf"(?<![a-z0-9.]){re.escape(alias)}(?![a-z0-9.])", text) is not None
    return alias in text


def _question_target_prices(question: str) -> list[float]:
    """Extract stated price scenarios without treating dates or 2Y/10Y as prices."""
    without_dates = re.sub(r"\b\d{4}-\d{1,2}-\d{1,2}\b", " ", question)
    currency_patterns = (
        r"(?:US\$|USD|\$)\s*(\d{1,4}(?:\.\d+)?)",
        r"(\d{1,4}(?:\.\d+)?)\s*(?:美元|美金|USD)",
        r"(?:目标价|股价|价格|价位|入场点|买点|均价|成本价)"
        r"[^\d]{0,8}(\d{1,4}(?:\.\d+)?)",
        r"(\d{1,4}(?:\.\d+)?)\s*(?:美元|美金|元)?\s*(?:的)?\s*"
        r"(?:目标价|股价|价格|价位|入场点|买点|均价|成本价)",
        r"(?:target\s+price|price\s+target|entry\s+price|buy\s+price)"
        r"[^\d]{0,8}\$?(\d{1,4}(?:\.\d+)?)",
    )
    matches = [
        item
        for pattern in currency_patterns
        for item in re.findall(pattern, without_dates, flags=re.IGNORECASE)
    ]
    result: list[float] = []
    for item in matches:
        value = float(item)
        if not 0 < value < 10_000 or 1900 <= value <= 2100 or value in result:
            continue
        result.append(value)
    return result[:3]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _ema(values: list[float], period: int) -> list[float]:
    alpha = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (1 - alpha) * result[-1])
    return result


def _rsi(values: list[float], period: int) -> float | None:
    if len(values) <= period:
        return None
    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    recent = changes[-period:]
    gains = sum(max(change, 0) for change in recent) / period
    losses = sum(max(-change, 0) for change in recent) / period
    if losses == 0:
        return 100.0
    relative_strength = gains / losses
    return 100 - 100 / (1 + relative_strength)


def _rolling_close_stochastic(values: list[float], period: int) -> list[float]:
    result: list[float] = []
    for index, value in enumerate(values):
        window = values[max(0, index - period + 1) : index + 1]
        low, high = min(window), max(window)
        result.append(50.0 if high == low else 100 * (value - low) / (high - low))
    return result


def _rolling_bar_stochastic(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int,
) -> list[float]:
    result: list[float] = []
    for index, close in enumerate(closes):
        start = max(0, index - period + 1)
        high = max(highs[start : index + 1])
        low = min(lows[start : index + 1])
        result.append(50.0 if high == low else 100 * (close - low) / (high - low))
    return result


def _average_true_range(
    highs: list[float] | None,
    lows: list[float] | None,
    closes: list[float],
    period: int,
) -> float | None:
    if highs is None or lows is None or len(closes) <= period:
        return None
    true_ranges = [highs[0] - lows[0]]
    for index in range(1, len(closes)):
        previous_close = closes[index - 1]
        true_ranges.append(
            max(
                highs[index] - lows[index],
                abs(highs[index] - previous_close),
                abs(lows[index] - previous_close),
            )
        )
    atr = _mean(true_ranges[1 : period + 1])
    for value in true_ranges[period + 1 :]:
        atr = ((period - 1) * atr + value) / period
    return atr


def _period_return(values: list[float], periods: int) -> float | None:
    if len(values) <= periods or values[-periods - 1] == 0:
        return None
    return values[-1] / values[-periods - 1] - 1


def _annualized_volatility(values: list[float]) -> float | None:
    if len(values) < 3:
        return None
    returns = [
        math.log(values[index] / values[index - 1])
        for index in range(1, len(values))
        if values[index] > 0 and values[index - 1] > 0
    ]
    if len(returns) < 2:
        return None
    average = _mean(returns)
    variance = sum((value - average) ** 2 for value in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(252)
