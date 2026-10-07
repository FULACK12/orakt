"use client";
import {Activity,ExternalLink,ShieldCheck} from "lucide-react";
import {finiteNumber} from './metric-format.mjs';
type SemiconductorCompany = {
  ticker: string;
  name: string;
  industry: string;
  dataCoverageScore: number;
  dataStatus: string;
  missing: string[];
  market: {
    historyStart: string;
    historyEnd: string;
    barCount: number;
    completeOhlcv: boolean;
    latestClose: number | null;
    return21d: number | null;
    return63d: number | null;
    return252d: number | null;
    annualizedVolatility63d: number | null;
    maximumDrawdown252d: number | null;
    sma20: number | null;
    sma50: number | null;
    sma200: number | null;
    volumeRatio20: number | null;
  };
  fundamentals: {
    periodEnd: string | null;
    revenue: number | null;
    netIncome: number | null;
    researchAndDevelopment: number | null;
    netMargin: number | null;
    researchIntensity: number | null;
    marketCapitalizationProxy: number | null;
    priceToSalesProxy: number | null;
    priceToEarningsProxy: number | null;
    debtToEquity: number | null;
    sourceUrl: string;
  };
  evidence: {
    filingCount: number;
    institutionalObservationCount: number;
    insiderTransactionCount: number;
    verifiedSupplyChainEdges: number;
    unnamedVerifiedSupplyChainEdges: number;
    candidateSupplyChainEdges: number;
  };
};
function formatCount(value: number | undefined){return typeof value==='number'?value.toLocaleString('en-US'):'—'}
type SemiconductorComparison = {
  version: string;
  generatedAt: string;
  marketDataCutoff: string;
  titleZh: string;
  titleEn: string;
  verdictZh: string;
  verdictEn: string;
  openaiUsed: boolean;
  companies: SemiconductorCompany[];
  findings: Array<{
    key: string;
    ticker: string | null;
    labelZh: string;
    labelEn: string;
    value: number | null;
    caveatZh: string;
    caveatEn: string;
  }>;
  methodologyZh: string;
  methodologyEn: string;
};
function formatPrice(value: number | null) {
  return !finiteNumber(value) ? "—" : `$${value!.toFixed(2)}`;
}
function formatMove(value: number | null | undefined) {
  return !finiteNumber(value)
    ? "—"
    : `${value! >= 0 ? "+" : ""}${(value! * 100).toFixed(1)}%`;
}
function formatRatio(value: number | null) {
  return value == null ? "—" : `${value.toFixed(1)}×`;
}
function formatLargeMoney(value: number | null) {
  if (value == null) return "—";
  const absolute = Math.abs(value);
  return absolute >= 1e12
    ? `$${(value / 1e12).toFixed(2)}T`
    : absolute >= 1e9
      ? `$${(value / 1e9).toFixed(1)}B`
      : `$${(value / 1e6).toFixed(1)}M`;
}
export default function SemiconductorComparisonPanel({
  comparison,
  language,
}: {
  comparison: SemiconductorComparison;
  language: 'zh'|'en';
}) {
  return (
    <section className="semiconductor-comparison">
      <header>
        <div>
          <span className="eyebrow">
            <Activity size={14} />
            {comparison.version} · OPENAI {comparison.openaiUsed ? "ON" : "OFF"}
          </span>
          <h1>{language === "zh" ? comparison.titleZh : comparison.titleEn}</h1>
          <p>
            {language === "zh" ? comparison.verdictZh : comparison.verdictEn}
          </p>
        </div>
        <b>
          {comparison.marketDataCutoff}
          <small>
            {language === "zh" ? "统一行情截止日" : "common market cutoff"}
          </small>
        </b>
      </header>
      <div className="comparison-findings">
        {comparison.findings.map((item) => (
          <article key={item.key}>
            <span>{language === "zh" ? item.labelZh : item.labelEn}</span>
            <strong>
              {item.ticker ?? "—"} · {formatMove(item.value)}
            </strong>
            <p>{language === "zh" ? item.caveatZh : item.caveatEn}</p>
          </article>
        ))}
      </div>
      <div className="comparison-company-grid">
        {comparison.companies.map((company) => (
          <article key={company.ticker}>
            <header>
              <div>
                <span>{company.ticker}</span>
                <h2>{company.name}</h2>
                <small>{company.industry}</small>
              </div>
              <b>
                {company.dataCoverageScore}%
                <small>{language === "zh" ? "数据覆盖" : "coverage"}</small>
              </b>
            </header>
            <div className="comparison-price">
              <strong>{formatPrice(company.market.latestClose)}</strong>
              <span>
                21D {formatMove(company.market.return21d)} · 63D{" "}
                {formatMove(company.market.return63d)}
              </span>
              <small>
                {company.market.historyStart} — {company.market.historyEnd} ·{" "}
                {formatCount(company.market.barCount)} OHLCV
              </small>
            </div>
            <dl>
              <div>
                <dt>{language === "zh" ? "年度收入" : "Annual revenue"}</dt>
                <dd>{formatLargeMoney(company.fundamentals.revenue)}</dd>
              </div>
              <div>
                <dt>
                  {language === "zh" ? "年度净利润" : "Annual net income"}
                </dt>
                <dd>{formatLargeMoney(company.fundamentals.netIncome)}</dd>
              </div>
              <div>
                <dt>{language === "zh" ? "净利率" : "Net margin"}</dt>
                <dd>{formatMove(company.fundamentals.netMargin)}</dd>
              </div>
              <div>
                <dt>{language === "zh" ? "研发强度" : "R&D intensity"}</dt>
                <dd>{formatMove(company.fundamentals.researchIntensity)}</dd>
              </div>
              <div>
                <dt>P/S {language === "zh" ? "代理" : "proxy"}</dt>
                <dd>{formatRatio(company.fundamentals.priceToSalesProxy)}</dd>
              </div>
              <div>
                <dt>P/E {language === "zh" ? "代理" : "proxy"}</dt>
                <dd>
                  {formatRatio(company.fundamentals.priceToEarningsProxy)}
                </dd>
              </div>
              <div>
                <dt>
                  {language === "zh" ? "63日年化波动" : "63D ann. volatility"}
                </dt>
                <dd>{formatMove(company.market.annualizedVolatility63d)}</dd>
              </div>
              <div>
                <dt>
                  {language === "zh" ? "252日最大回撤" : "252D max drawdown"}
                </dt>
                <dd>{formatMove(company.market.maximumDrawdown252d)}</dd>
              </div>
            </dl>
            <footer>
              <span>
                {language === "zh" ? "财年截止" : "Fiscal end"}{" "}
                {company.fundamentals.periodEnd ?? "—"}
              </span>
              <span>
                {language === "zh" ? "已核验供应链" : "Verified supply-chain"}{" "}
                {company.evidence.verifiedSupplyChainEdges} ·{" "}
                {language === "zh" ? "未具名" : "unnamed"}{" "}
                {company.evidence.unnamedVerifiedSupplyChainEdges}
              </span>
              <a
                href={company.fundamentals.sourceUrl}
                target="_blank"
                rel="noreferrer"
              >
                SEC
                <ExternalLink size={11} />
              </a>
            </footer>
          </article>
        ))}
      </div>
      <footer>
        <ShieldCheck size={16} />
        <p>
          {language === "zh"
            ? comparison.methodologyZh
            : comparison.methodologyEn}
        </p>
      </footer>
    </section>
  );
}
