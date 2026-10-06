"""Point-in-time product operating evidence extracted from archived SEC filings."""

# ruff: noqa: RUF001

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from html import unescape
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import CompanyFiling, CompanySupplyChainCoverage
from app.storage.archive import ColdArchive
from app.supply_chain_discovery import (
    ANNUAL_SUPPLY_CHAIN_FORMS,
    MAX_FILING_BYTES,
    _archive_path,
    _VisibleTextParser,
)

EvidenceStatus = Literal["reported_actual", "forward_looking_plan", "risk_disclosure"]
QUARTERLY_PRODUCT_FORMS = ("10-Q", "10-Q/A")
PRODUCT_EVIDENCE_FORMS = ANNUAL_SUPPLY_CHAIN_FORMS + QUARTERLY_PRODUCT_FORMS


class ProductFilingArchiveResult(BaseModel):
    """Measured archive result for annual and quarterly product evidence."""

    filings_selected: int = Field(ge=0)
    filings_downloaded: int = Field(ge=0)
    filings_already_archived: int = Field(ge=0)
    filings_failed: int = Field(ge=0)
    tickers_completed: list[str] = Field(default_factory=list)
    archived_paths: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class ProductEvidenceRule:
    """One deliberately narrow filing sentence matcher."""

    key: str
    ticker: str
    product: str
    metric_type: str
    metric_name: str
    evidence_status: EvidenceStatus
    pattern: re.Pattern[str]
    signal: Literal["positive", "negative", "mixed", "regime_dependent"]
    plain_explanation_zh: str
    forms: tuple[str, ...] = ANNUAL_SUPPLY_CHAIN_FORMS


def _rule(
    key: str,
    ticker: str,
    product: str,
    metric_type: str,
    metric_name: str,
    evidence_status: EvidenceStatus,
    pattern: str,
    signal: Literal["positive", "negative", "mixed", "regime_dependent"],
    plain_explanation_zh: str,
    forms: tuple[str, ...] = ANNUAL_SUPPLY_CHAIN_FORMS,
) -> ProductEvidenceRule:
    return ProductEvidenceRule(
        key=key,
        ticker=ticker,
        product=product,
        metric_type=metric_type,
        metric_name=metric_name,
        evidence_status=evidence_status,
        pattern=re.compile(pattern, re.IGNORECASE),
        signal=signal,
        plain_explanation_zh=plain_explanation_zh,
        forms=forms,
    )


PRODUCT_EVIDENCE_RULES = (
    _rule(
        "dram-revenue-history",
        "MU",
        "DRAM",
        "revenue",
        "reported DRAM revenue",
        "reported_actual",
        r"\bTotal reported DRAM revenue was\b",
        "positive",
        "DRAM 年度收入是已申报的产品收入，不等于未来订单或利润。",
    ),
    _rule(
        "nand-revenue-history",
        "MU",
        "NAND",
        "revenue",
        "reported NAND revenue",
        "reported_actual",
        r"\bTotal reported NAND revenue was\b",
        "positive",
        "NAND 年度收入是已申报结果，可用于核对产品组合与周期变化。",
    ),
    _rule(
        "dram-asp-bit-shipments",
        "MU",
        "DRAM",
        "price_and_volume_change",
        "average selling price and bit-shipment change",
        "reported_actual",
        r"\bSales of DRAM products increased\b.*\baverage selling prices\b.*\bbit shipments\b",
        "positive",
        "把收入变化拆成平均售价与出货位元量，可避免只凭总收入猜需求。",
    ),
    _rule(
        "nand-bit-shipments",
        "MU",
        "NAND",
        "volume_change",
        "bit-shipment change",
        "reported_actual",
        r"\bSales of NAND products increased\b.*\bbit shipments\b",
        "positive",
        "NAND 位元出货变化是销量代理；年报没有给出绝对出货单位。",
    ),
    _rule(
        "hbm-product-mix",
        "MU",
        "HBM3E",
        "product_mix",
        "HBM3E 12-high shipment mix",
        "reported_actual",
        r"\bHBM3E 12-high represented the majority of our HBM shipments\b",
        "positive",
        "这说明已实现的 HBM 出货结构，但没有披露客户、绝对数量或单价。",
    ),
    _rule(
        "hbm4-volume-plan",
        "MU",
        "HBM4",
        "capacity_timing",
        "planned volume-production timing",
        "forward_looking_plan",
        r"\bHBM4 technology\b.*\b(?:schedule|volume production)\b",
        "regime_dependent",
        "这是管理层的量产时间计划，不是已经实现的产量。",
    ),
    _rule(
        "hbm-packaging-capacity-plan",
        "MU",
        "HBM advanced packaging",
        "capacity_timing",
        "planned packaging-capacity expansion",
        "forward_looking_plan",
        r"\bHBM advanced packaging facility\b.*\b(?:capacity|calendar 2027)\b",
        "regime_dependent",
        "这是未来封装扩产计划，实际投产时间、良率和产能仍需后续披露验证。",
    ),
    _rule(
        "supplier-contract-limit",
        "MU",
        "manufacturing inputs",
        "contract_limitation",
        "supplier contract capacity and pricing limitation",
        "risk_disclosure",
        (
            r"\blong-term contracts with some suppliers\b.*\bdo not provide for "
            r"long-term capacity or pricing commitments\b"
        ),
        "negative",
        "部分供应合同不锁定长期产能或价格，因此不能把合同存在写成供应完全有保障。",
    ),
    _rule(
        "cloud-revenue",
        "MSFT",
        "Microsoft Cloud",
        "revenue",
        "Microsoft Cloud revenue",
        "reported_actual",
        r"\bMicrosoft Cloud revenue increased\b.*\b214\.4 billion\b",
        "positive",
        "云业务收入是已申报结果，可核对 AI 与云需求的总体兑现程度。",
    ),
    _rule(
        "commercial-rpo",
        "MSFT",
        "Commercial cloud contracts",
        "contracted_revenue",
        "commercial remaining performance obligation",
        "reported_actual",
        r"\bCommercial remaining performance obligation increased\b.*\b678 billion\b",
        "positive",
        "商业剩余履约义务是合同未确认收入指标，但不等同于不可撤销的订单积压。",
    ),
    _rule(
        "azure-revenue-growth",
        "MSFT",
        "Azure",
        "revenue_growth",
        "Azure and other cloud services revenue growth",
        "reported_actual",
        r"\bAzure and other cloud services revenue increased 41%",
        "positive",
        "Azure 增速反映已确认收入变化，并不直接给出新增算力、客户数或利润贡献。",
    ),
    _rule(
        "m365-commercial-revenue-growth",
        "MSFT",
        "Microsoft 365 Commercial",
        "revenue_growth",
        "commercial cloud revenue growth",
        "reported_actual",
        r"\bMicrosoft 365 Commercial cloud revenue (?:increased|grew) 17%",
        "positive",
        "商业云收入增速可验证产品变现，但仍需结合席位与单用户收入拆解。",
    ),
    _rule(
        "m365-commercial-seats",
        "MSFT",
        "Microsoft 365 Commercial",
        "volume_change",
        "commercial seat growth",
        "reported_actual",
        r"\bMicrosoft 365 Commercial seats grew 6%",
        "positive",
        "商业席位增速是用户量代理，可与单用户收入变化共同拆解增长来源。",
    ),
    _rule(
        "cloud-gross-margin",
        "MSFT",
        "Microsoft Cloud",
        "margin_change",
        "cloud gross-margin percentage",
        "reported_actual",
        r"\bMicrosoft Cloud gross margin percentage decreased to 66%",
        "negative",
        "云毛利率下降可用于约束 AI 基础设施增长叙事，收入增长不一定同步转化为利润率提升。",
    ),
    _rule(
        "rpo-recognition-plan",
        "MSFT",
        "Commercial cloud contracts",
        "contract_timing",
        "planned RPO recognition timing",
        "forward_looking_plan",
        r"\bexpect to recognize approximately 30%.*\bRPO revenue over the next 12 months\b",
        "regime_dependent",
        "这是管理层预计的合同收入确认节奏，不是已经确认的收入。",
    ),
    _rule(
        "multi-year-contract-volume",
        "MSFT",
        "Commercial cloud contracts",
        "contract_activity",
        "multi-year contract volume",
        "reported_actual",
        r"\b(?:revenue|bookings)\b.*\bhigher volume of multi-year contracts\b",
        "positive",
        "多年合同数量提升是经营活动线索，但年报原句未披露单笔合同或客户名单。",
    ),
    _rule(
        "rpo-estimation-risk",
        "MSFT",
        "Commercial cloud contracts",
        "contract_limitation",
        "RPO estimate limitation",
        "risk_disclosure",
        r"\bremaining performance obligations?\b.*\b(?:variable consideration|renegotiat)\b",
        "negative",
        "RPO 含估计与可变对价，不应直接视为完全不可撤销的确定订单。",
    ),
    _rule(
        "aapl-iphone-net-sales",
        "AAPL",
        "iPhone",
        "product_revenue_change",
        "iPhone net sales change",
        "reported_actual",
        r"\biPhone net sales\b.*\b(?:increased|decreased)\b",
        "regime_dependent",
        "iPhone 净销售变化是已申报的产品收入变化；它不等于设备销量或平均售价。",
        PRODUCT_EVIDENCE_FORMS,
    ),
    _rule(
        "aapl-services-net-sales",
        "AAPL",
        "Services",
        "product_revenue_change",
        "Services net sales change",
        "reported_actual",
        r"\bServices net sales\b.*\b(?:increased|decreased)\b",
        "regime_dependent",
        "服务净销售变化反映已确认收入，不代表订阅用户数、留存率或监管风险已经改善。",
        PRODUCT_EVIDENCE_FORMS,
    ),
    _rule(
        "aapl-mac-net-sales",
        "AAPL",
        "Mac",
        "product_revenue_change",
        "Mac net sales change",
        "reported_actual",
        r"\bMac net sales\b.*\b(?:increased|decreased)\b",
        "regime_dependent",
        "Mac 净销售变化是产品线收入信号，仍需销量、渠道库存和平均售价补充。",
        PRODUCT_EVIDENCE_FORMS,
    ),
    _rule(
        "aapl-ipad-net-sales",
        "AAPL",
        "iPad",
        "product_revenue_change",
        "iPad net sales change",
        "reported_actual",
        r"\biPad net sales\b.*\b(?:increased|decreased)\b",
        "regime_dependent",
        "iPad 净销售变化是产品线收入信号，不能单独识别更新周期或促销影响。",
        PRODUCT_EVIDENCE_FORMS,
    ),
    _rule(
        "aapl-wearables-net-sales",
        "AAPL",
        "Wearables, Home and Accessories",
        "product_revenue_change",
        "Wearables, Home and Accessories net sales change",
        "reported_actual",
        r"\bWearables, Home and Accessories net sales\b.*\b(?:increased|decreased)\b",
        "regime_dependent",
        "可穿戴、家居与配件收入是合并产品篮子，不能据此推断单一设备表现。",
        PRODUCT_EVIDENCE_FORMS,
    ),
    _rule(
        "aapl-product-gross-margin",
        "AAPL",
        "Products",
        "margin_change",
        "Products gross-margin percentage change",
        "reported_actual",
        r"\bProducts gross margin percentage\b.*\b(?:increased|decreased)\b",
        "regime_dependent",
        "产品毛利率变化能约束收入增长叙事，但公司没有披露每个硬件产品的独立毛利率。",
        PRODUCT_EVIDENCE_FORMS,
    ),
    _rule(
        "aapl-services-gross-margin",
        "AAPL",
        "Services",
        "margin_change",
        "Services gross-margin percentage change",
        "reported_actual",
        r"\bServices gross margin percentage\b.*\b(?:increased|decreased)\b",
        "regime_dependent",
        "服务毛利率是已申报结果，但仍是多种服务合并后的总体指标。",
        PRODUCT_EVIDENCE_FORMS,
    ),
    _rule(
        "nvda-data-center-revenue",
        "NVDA",
        "Data Center",
        "segment_revenue_change",
        "Data Center revenue change",
        "reported_actual",
        r"\bData Center revenue\b.*\b(?:increased|decreased|was)\b",
        "regime_dependent",
        "数据中心收入变化是已申报结果，不能单独证明 GPU 数量、单价或终端客户需求。",
        PRODUCT_EVIDENCE_FORMS,
    ),
    _rule(
        "nvda-gaming-revenue",
        "NVDA",
        "Gaming",
        "segment_revenue_change",
        "Gaming revenue change",
        "reported_actual",
        r"\bGaming revenue\b.*\b(?:increased|decreased|was)\b",
        "regime_dependent",
        "游戏业务收入变化是已申报结果，仍需区分渠道库存、产品组合和终端需求。",
        PRODUCT_EVIDENCE_FORMS,
    ),
    _rule(
        "nvda-compute-networking-revenue",
        "NVDA",
        "Compute and Networking",
        "segment_revenue_change",
        "Compute and Networking revenue change",
        "reported_actual",
        r"\bCompute & Networking revenue\b.*\b(?:increased|decreased|was)\b",
        "regime_dependent",
        "计算与网络收入是合并业务指标，不能直接拆成 GPU、网络设备或软件收入。",
        PRODUCT_EVIDENCE_FORMS,
    ),
    _rule(
        "nvda-gross-margin",
        "NVDA",
        "Consolidated products",
        "margin_change",
        "gross-margin change",
        "reported_actual",
        r"\bgross margin\b.*\b(?:increased|decreased|was)\b",
        "regime_dependent",
        "总体毛利率能约束增长质量，但不能直接归因于某一代 GPU 或单个客户。",
        PRODUCT_EVIDENCE_FORMS,
    ),
    _rule(
        "nvda-export-control-risk",
        "NVDA",
        "Data Center accelerators",
        "regulatory_risk",
        "export-control exposure",
        "risk_disclosure",
        r"\bexport controls?\b.*\b(?:China|PRC|data center|accelerator)\b",
        "negative",
        "出口管制是公司披露的经营风险，不能把潜在影响直接等同于已经损失的收入。",
        PRODUCT_EVIDENCE_FORMS,
    ),
    _rule(
        "amd-data-center-revenue",
        "AMD",
        "Data Center",
        "segment_revenue_change",
        "Data Center segment revenue change",
        "reported_actual",
        r"\bData Center segment revenue\b.*\b(?:increased|decreased|was)\b",
        "regime_dependent",
        "数据中心分部收入是已申报结果，但仍需拆分 EPYC、Instinct 与客户集中度。",
        PRODUCT_EVIDENCE_FORMS,
    ),
    _rule(
        "amd-client-gaming-revenue",
        "AMD",
        "Client and Gaming",
        "segment_revenue_change",
        "Client and Gaming segment revenue change",
        "reported_actual",
        r"\bClient and Gaming segment revenue\b.*\b(?:increased|decreased|was)\b",
        "regime_dependent",
        "客户端与游戏分部是合并指标，不能单独代表 Ryzen 或游戏 GPU 的表现。",
        PRODUCT_EVIDENCE_FORMS,
    ),
    _rule(
        "amd-embedded-revenue",
        "AMD",
        "Embedded",
        "segment_revenue_change",
        "Embedded segment revenue change",
        "reported_actual",
        r"\bEmbedded segment revenue\b.*\b(?:increased|decreased|was)\b",
        "regime_dependent",
        "嵌入式分部收入能反映已确认销售，但周期、渠道库存和产品组合仍需进一步拆解。",
        PRODUCT_EVIDENCE_FORMS,
    ),
    _rule(
        "amd-gross-margin",
        "AMD",
        "Consolidated products",
        "margin_change",
        "gross-margin change",
        "reported_actual",
        r"\bgross margin\b.*\b(?:increased|decreased|was)\b",
        "regime_dependent",
        "总体毛利率可用于检查增长质量，但不能直接归因于单一产品或价格变化。",
        PRODUCT_EVIDENCE_FORMS,
    ),
    _rule(
        "amd-export-control-risk",
        "AMD",
        "Data Center accelerators",
        "regulatory_risk",
        "export-control exposure",
        "risk_disclosure",
        r"\bexport controls?\b.*\b(?:China|PRC|data center|accelerator)\b",
        "negative",
        "出口管制属于披露风险；只有后续收入、库存或减值数据才能验证实际影响。",
        PRODUCT_EVIDENCE_FORMS,
    ),
    _rule(
        "lulu-category-revenue-mix",
        "LULU",
        "Women's, men's, accessories and other",
        "category_revenue_mix",
        "reported category share of net revenue",
        "reported_actual",
        r"\bwomen's, men's, and accessories and other categories represented 63%, 24%, and 13% of net revenue\b",
        "mixed",
        "女装、男装及配饰等品类收入占比是已申报的业务结构，可用于判断集中度，但不等于各品类未来增速。",
    ),
    _rule(
        "lulu-q2-net-revenue-change",
        "LULU",
        "Consolidated products",
        "revenue_change",
        "second-quarter net-revenue change",
        "reported_actual",
        r"\bNet revenue decreased 4% to \$2\.4 billion\b",
        "negative",
        "二季度净收入同比下降是已申报结果；其中关税退款、汇率和地区差异需要分开解释。",
        QUARTERLY_PRODUCT_FORMS,
    ),
    _rule(
        "lulu-q2-comparable-sales",
        "LULU",
        "Comparable stores and e-commerce",
        "comparable_sales_change",
        "second-quarter comparable-sales change",
        "reported_actual",
        r"\bComparable sales decreased 9%, or 10% on a constant dollar basis\b",
        "negative",
        "可比销售下降同时覆盖成熟门店和电商，是需求与执行的结果指标，但仍需结合客流、转化率和客单价。",
        QUARTERLY_PRODUCT_FORMS,
    ),
    _rule(
        "lulu-q2-gross-margin",
        "LULU",
        "Consolidated products",
        "gross_margin_change",
        "second-quarter gross margin",
        "reported_actual",
        r"\bGross margin increased 200 basis points to 60\.5%\b",
        "mixed",
        "二季度毛利率上升包含关税退款影响，不能直接解释为基础产品利润率持续改善。",
        QUARTERLY_PRODUCT_FORMS,
    ),
    _rule(
        "lulu-americas-demand-drivers",
        "LULU",
        "Americas",
        "demand_driver_change",
        "traffic, conversion and average-order-value change",
        "reported_actual",
        r"\breduced traffic and lower conversion rates, as well as a decrease in average order value in the Americas\b",
        "negative",
        "美洲客流、转化率和客单价同时下降，是可比销售走弱的经营拆解，不应只归因于宏观环境。",
        QUARTERLY_PRODUCT_FORMS,
    ),
    _rule(
        "lulu-manufacturing-country-concentration",
        "LULU",
        "Finished goods manufacturing",
        "manufacturing_country_mix",
        "reported manufacturing concentration by country",
        "reported_actual",
        r"\bApproximately 40% of our products were manufactured in Vietnam, 18% in Cambodia, 11% in Sri Lanka, 11% in Indonesia, and 7% in Bangladesh\b",
        "regime_dependent",
        "成衣生产国占比是已披露的供应暴露，可与当地冲突、灾害、物流和劳动力事件做点时映射。",
        PRODUCT_EVIDENCE_FORMS,
    ),
    _rule(
        "lulu-fabric-origin-concentration",
        "LULU",
        "Technical fabrics",
        "fabric_origin_mix",
        "reported fabric-origin concentration by country",
        "reported_actual",
        r"\bApproximately 34% of the fabric used in our products originated from Taiwan, 29% from China Mainland, 10% from South Korea, 10% from Vietnam\b",
        "regime_dependent",
        "面料来源集中度是已披露的上游暴露，尤其可用于审计台湾地缘风险与替代采购能力。",
        PRODUCT_EVIDENCE_FORMS,
    ),
    _rule(
        "lulu-majority-supplier-contract-limit",
        "LULU",
        "Fabrics and garments",
        "contract_limitation",
        "majority supplier and manufacturing contract limitation",
        "risk_disclosure",
        r"\bdo not, however, have any long-term contracts with the majority of our suppliers or manufacturing sources\b",
        "negative",
        "多数供应商和制造来源没有长期合同是公司披露的约束，但并不等于供应中断已经发生。",
        PRODUCT_EVIDENCE_FORMS,
    ),
)

_VALUE_PATTERN = re.compile(
    r"\$[\d,.]+\s*(?:trillion|billion|million)|"
    r"\b\d+(?:\.\d+)?%|"
    r"\b(?:low|mid|high)-(?:\d+|single|teen|twent(?:y|ies)|thirt(?:y|ies)|"
    r"fort(?:y|ies))%?(?:\s+(?:range|percentage))?",
    re.IGNORECASE,
)


async def archive_product_operating_filings(
    session: Session,
    *,
    client: httpx.AsyncClient,
    archive: ColdArchive,
    tickers: set[str],
    as_of: date,
    quarterly_periods: int = 4,
) -> ProductFilingArchiveResult:
    """Archive the latest annual filing and recent 10-Qs for each requested issuer."""
    if not 1 <= quarterly_periods <= 12:
        raise ValueError("quarterly_periods must be between one and twelve")
    normalized_tickers = sorted({item.strip().upper() for item in tickers if item.strip()})
    filings: list[CompanyFiling] = []
    for ticker in normalized_tickers:
        filings.extend(
            _selected_product_filings(
                session,
                ticker=ticker,
                as_of=as_of,
                quarterly_periods=quarterly_periods,
            )
        )
    downloaded = 0
    already_archived = 0
    failed = 0
    paths: list[str] = []
    errors: list[str] = []
    successful_tickers: set[str] = set()
    failed_tickers: set[str] = set()
    for filing in filings:
        relative_path = _archive_path(filing)
        archived_path = archive.root / relative_path
        try:
            if archived_path.is_file():
                payload = archived_path.read_bytes()
                already_archived += 1
            else:
                response = await client.get(filing.source_url)
                response.raise_for_status()
                payload = response.content
                if not payload or len(payload) > MAX_FILING_BYTES:
                    raise ValueError(
                        "filing response size is outside the allowed range: "
                        f"{len(payload)}"
                    )
                prefix = payload[:8_000].lower()
                if b"<html" not in prefix and b"<!doctype" not in prefix:
                    raise ValueError("SEC filing response is not an HTML primary document")
                archive.store_bytes(relative_path, payload)
                downloaded += 1
            if not payload or len(payload) > MAX_FILING_BYTES:
                raise ValueError(
                    f"archived filing size is outside the allowed range: {len(payload)}"
                )
            paths.append(relative_path)
            successful_tickers.add(filing.ticker)
        except (OSError, httpx.HTTPError, ValueError) as exc:
            failed += 1
            failed_tickers.add(filing.ticker)
            errors.append(
                f"{filing.ticker} {filing.accession_number}: {type(exc).__name__}: {exc}"
            )
    return ProductFilingArchiveResult(
        filings_selected=len(filings),
        filings_downloaded=downloaded,
        filings_already_archived=already_archived,
        filings_failed=failed,
        tickers_completed=sorted(successful_tickers - failed_tickers),
        archived_paths=paths,
        errors=errors,
    )


def build_product_operating_evidence(
    session: Session,
    *,
    ticker: str,
    as_of: date,
    cold_data_root: Path,
    limit: int = 32,
    quarterly_periods: int = 4,
) -> list[dict[str, Any]]:
    """Extract audited excerpts from archived annual filings and recent 10-Qs."""
    normalized_ticker = ticker.strip().upper()
    rules = [rule for rule in PRODUCT_EVIDENCE_RULES if rule.ticker == normalized_ticker]
    if not rules or limit <= 0:
        return []
    filings = _selected_product_filings(
        session,
        ticker=normalized_ticker,
        as_of=as_of,
        quarterly_periods=quarterly_periods,
    )
    coverage = session.get(CompanySupplyChainCoverage, normalized_ticker)
    root = cold_data_root.resolve()
    results: list[dict[str, Any]] = []
    for filing in filings:
        relative_path = _archive_path(filing)
        if (
            coverage is not None
            and coverage.latest_filing_accession == filing.accession_number
            and coverage.latest_raw_archive_path
        ):
            relative_path = coverage.latest_raw_archive_path
        archived_path = (root / relative_path).resolve()
        if not archived_path.is_relative_to(root) or not archived_path.is_file():
            continue
        try:
            payload = archived_path.read_bytes()
        except OSError:
            continue
        if not payload or len(payload) > MAX_FILING_BYTES:
            continue
        sentences = _sentences(_visible_text(payload))
        for rule in rules:
            if filing.form not in rule.forms:
                continue
            sentence = next((item for item in sentences if rule.pattern.search(item)), None)
            if sentence is None:
                continue
            limitations = _limitations(rule, filing_form=filing.form)
            results.append(
                {
                    "evidence_id": (
                        f"product-operating:{normalized_ticker}:"
                        f"{filing.accession_number}:{rule.key}"
                    ),
                    "category": "product_operating_evidence",
                    "ticker": normalized_ticker,
                    "product": rule.product,
                    "metric_type": rule.metric_type,
                    "metric_name": rule.metric_name,
                    "evidence_status": rule.evidence_status,
                    "signal": rule.signal,
                    "reported_values": list(dict.fromkeys(_VALUE_PATTERN.findall(sentence))),
                    "filing_form": filing.form,
                    "fiscal_year": filing.fiscal_year,
                    "fiscal_period": filing.fiscal_period,
                    "source_periodicity": (
                        "quarterly" if filing.form in QUARTERLY_PRODUCT_FORMS else "annual"
                    ),
                    "period_end": filing.report_date.isoformat() if filing.report_date else None,
                    "available_at": filing.filed_at.isoformat(),
                    "source": (
                        f"SEC {filing.form} quarterly report"
                        if filing.form in QUARTERLY_PRODUCT_FORMS
                        else f"SEC {filing.form} annual report"
                    ),
                    "source_url": filing.source_url,
                    "source_archive_path": relative_path,
                    "source_excerpt": sentence[:1_500],
                    "plain_explanation_zh": rule.plain_explanation_zh,
                    "limitations": limitations,
                    "can_verify_claims": True,
                    "can_verify_filing_contents": True,
                }
            )
            if len(results) >= limit:
                return results
    return results


def _selected_product_filings(
    session: Session,
    *,
    ticker: str,
    as_of: date,
    quarterly_periods: int,
) -> list[CompanyFiling]:
    filings = list(
        session.scalars(
            select(CompanyFiling)
            .where(
                CompanyFiling.ticker == ticker,
                CompanyFiling.form.in_(PRODUCT_EVIDENCE_FORMS),
                CompanyFiling.filed_at <= as_of,
            )
            .order_by(desc(CompanyFiling.filed_at), desc(CompanyFiling.accession_number))
        )
    )
    annual = next((item for item in filings if item.form in ANNUAL_SUPPLY_CHAIN_FORMS), None)
    quarters: list[CompanyFiling] = []
    seen_periods: set[date] = set()
    for filing in filings:
        if filing.form not in QUARTERLY_PRODUCT_FORMS:
            continue
        period_key = filing.report_date or filing.filed_at
        if period_key in seen_periods:
            continue
        quarters.append(filing)
        seen_periods.add(period_key)
        if len(quarters) >= quarterly_periods:
            break
    selected = quarters + ([annual] if annual is not None else [])
    return sorted(
        selected,
        key=lambda item: (item.filed_at, item.accession_number),
        reverse=True,
    )


def summarize_product_operating_evidence(
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Expose coverage and residual gaps without overstating completeness."""
    actual = [item for item in evidence if item.get("evidence_status") == "reported_actual"]
    plans = [
        item for item in evidence if item.get("evidence_status") == "forward_looking_plan"
    ]
    risks = [item for item in evidence if item.get("evidence_status") == "risk_disclosure"]
    metric_types = sorted(
        {str(item.get("metric_type")) for item in evidence if item.get("metric_type")}
    )
    products = sorted({str(item.get("product")) for item in evidence if item.get("product")})
    annual = [item for item in evidence if item.get("source_periodicity") == "annual"]
    quarterly = [item for item in evidence if item.get("source_periodicity") == "quarterly"]
    periods = sorted(
        {str(item.get("period_end")) for item in evidence if item.get("period_end")},
        reverse=True,
    )
    status = "complete" if len(actual) >= 4 else "partial" if evidence else "missing"
    return {
        "status": status,
        "total_evidence": len(evidence),
        "reported_actual_count": len(actual),
        "forward_looking_plan_count": len(plans),
        "risk_disclosure_count": len(risks),
        "metric_types": metric_types,
        "products": products,
        "annual_evidence_count": len(annual),
        "quarterly_evidence_count": len(quarterly),
        "covered_period_ends": periods,
        "latest_period_end": periods[0] if periods else None,
        "remaining_gaps": [
            (
                "absolute product unit volume and realized unit ASP where the filing "
                "gives only changes"
            ),
            "customer-level orders, contract price, cancellation rights and delivery schedule",
            "product-level gross margin, inventory and capacity-utilization history",
        ],
        "policy": (
            "Only filed actuals can support observed operating claims. Forward-looking plans "
            "and risk disclosures remain separately labelled and cannot be treated as realized."
        ),
    }


def _visible_text(payload: bytes) -> str:
    parser = _VisibleTextParser()
    parser.feed(payload.decode("utf-8", errors="replace"))
    return re.sub(r"\s+", " ", unescape("".join(parser.parts))).strip()


def _sentences(text: str) -> list[str]:
    values = re.split(r"(?<=[.!?])\s+|(?<=;)\s+(?=[A-Z])", text)
    return [item.strip(" .") for item in values if 25 <= len(item.strip(" .")) <= 2_000]


def _limitations(rule: ProductEvidenceRule, *, filing_form: str) -> list[str]:
    limitations = [
        (
            f"Company-reported {filing_form} filing evidence; it does not independently "
            "establish future performance."
        ),
    ]
    if filing_form in QUARTERLY_PRODUCT_FORMS:
        limitations.append(
            "Quarterly filing figures can be quarter-only or year-to-date; the exact "
            "source wording and report period are preserved and must not be mixed."
        )
    if rule.metric_type in {"price_and_volume_change", "volume_change"}:
        limitations.append(
            "Relative ASP or shipment changes are preserved as reported and are not "
            "converted into absolute prices or units."
        )
    if rule.evidence_status == "forward_looking_plan":
        limitations.append(
            "Forward-looking schedule or expectation; it is not counted as realized "
            "production, revenue or capacity."
        )
    if rule.ticker == "MSFT" and "rpo" in rule.key:
        limitations.append(
            "Remaining performance obligation is not treated as an irrevocable order "
            "backlog and can include estimates or variable consideration."
        )
    if rule.metric_type == "contract_activity":
        limitations.append(
            "The excerpt does not identify customers, contract value, cancellation "
            "rights or delivery timing."
        )
    return limitations
