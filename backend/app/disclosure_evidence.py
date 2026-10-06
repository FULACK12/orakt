"""Conservative structured candidates extracted from Chinese statutory disclosures."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

STRUCTURED_DISCLOSURE_EVIDENCE_VERSION = "cninfo_structured_evidence_v1"

_SPACE_PATTERN = re.compile(r"[\t\r\f\v ]+")
_NUMBER_PATTERN = re.compile(
    r"(?<![\d.])-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:%|亿元|万元|元|股|万股|亿股)?"
)

_FINANCIAL_LABELS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("operating_revenue", ("营业收入",)),
    (
        "net_profit_attributable",
        ("归属于上市公司股东的净利润", "归属于母公司股东的净利润"),
    ),
    ("net_operating_cash_flow", ("经营活动产生的现金流量净额",)),
    ("total_assets", ("总资产",)),
    (
        "net_assets_attributable",
        ("归属于上市公司股东的所有者权益", "归属于母公司所有者权益"),
    ),
    ("basic_earnings_per_share", ("基本每股收益",)),
    ("weighted_return_on_equity", ("加权平均净资产收益率",)),
)

_SHAREHOLDER_TERMS = (
    "前十名股东",
    "十大股东",
    "股东持股",
    "持股数量",
    "增持",
    "减持",
    "股份回购",
    "股权质押",
)
_OPERATING_TERMS = (
    "重大合同",
    "中标",
    "订单",
    "销售量",
    "生产量",
    "库存量",
    "产能",
    "业绩预告",
)
_SUPPLY_CHAIN_TERMS = (
    "主要供应商",
    "前五名供应商",
    "主要客户",
    "前五名客户",
    "原材料",
    "采购额",
    "生产基地",
    "供应链",
    "物流",
    "电力",
)


def extract_structured_disclosure_evidence(
    text: str,
    *,
    title: str = "",
    published_at: datetime | None = None,
) -> dict[str, Any]:
    """Return exact-source candidates without promoting table text to audited facts.

    PDF table extraction can lose columns. Values are deliberately retained as
    candidates beside their exact excerpt so the report and reviewer can inspect
    provenance instead of treating a guessed column as a normalized filing fact.
    """
    normalized = _normalize_text(text)
    period_type = _period_type(title)
    financial_metrics: list[dict[str, Any]] = []
    seen_metrics: set[tuple[str, str]] = set()
    for metric, labels in _FINANCIAL_LABELS:
        for label in labels:
            for excerpt in _term_excerpts(normalized, (label,), limit=3):
                candidates = _NUMBER_PATTERN.findall(excerpt)
                signature = (metric, excerpt)
                if signature in seen_metrics:
                    continue
                seen_metrics.add(signature)
                financial_metrics.append(
                    {
                        "metric": metric,
                        "label": label,
                        "value_candidates": candidates[:8],
                        "source_excerpt": excerpt,
                        "period_type": period_type,
                        "extraction_status": "candidate_requires_table_reconciliation",
                    }
                )

    return {
        "version": STRUCTURED_DISCLOSURE_EVIDENCE_VERSION,
        "published_at": published_at.isoformat() if published_at else None,
        "period_type": period_type,
        "financial_metrics": financial_metrics[:24],
        "shareholder_excerpts": _term_excerpts(
            normalized,
            _SHAREHOLDER_TERMS,
            limit=8,
        ),
        "operating_excerpts": _term_excerpts(
            normalized,
            _OPERATING_TERMS,
            limit=8,
        ),
        "supply_chain_excerpts": _term_excerpts(
            normalized,
            _SUPPLY_CHAIN_TERMS,
            limit=8,
        ),
        "provenance_note": (
            "Exact excerpts and nearby value candidates from an official PDF; "
            "table columns must be reconciled before the candidates are used as audited facts."
        ),
    }


def structured_evidence_counts(evidence: dict[str, Any] | None) -> dict[str, int]:
    """Summarize only list-shaped evidence fields from a persisted extraction."""
    payload = evidence if isinstance(evidence, dict) else {}
    return {
        key: len(payload.get(key) or []) if isinstance(payload.get(key), list) else 0
        for key in (
            "financial_metrics",
            "shareholder_excerpts",
            "operating_excerpts",
            "supply_chain_excerpts",
        )
    }


def _normalize_text(text: str) -> str:
    cleaned = (
        text.replace("\x00", "")
        .replace("\u3000", " ")
        .replace("\N{FULLWIDTH PERCENT SIGN}", "%")
    )
    cleaned = _SPACE_PATTERN.sub(" ", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _term_excerpts(
    text: str,
    terms: tuple[str, ...],
    *,
    limit: int,
) -> list[str]:
    excerpts: list[str] = []
    seen: set[str] = set()
    for term in terms:
        for match in re.finditer(re.escape(term), text):
            start = max(0, match.start() - 80)
            end = min(len(text), match.end() + 260)
            excerpt = re.sub(r"\s+", " ", text[start:end]).strip()
            if excerpt and excerpt not in seen:
                seen.add(excerpt)
                excerpts.append(excerpt)
            if len(excerpts) >= limit:
                return excerpts
    return excerpts


def _period_type(title: str) -> str:
    if "第一季度" in title or "一季度" in title:
        return "quarter_1"
    if "半年度" in title or "中期报告" in title:
        return "half_year"
    if "第三季度" in title or "三季度" in title:
        return "quarter_3"
    if "年度报告" in title:
        return "annual"
    return "announcement"
