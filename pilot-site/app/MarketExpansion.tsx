import { Layers3, ShieldCheck, Coins } from "lucide-react";
import CryptoMarkets from './CryptoMarkets';

export default function MarketExpansion({ kind, language }: { kind: "portfolio" | "crypto"; language: "zh" | "en" }) {
  if(kind==='crypto')return <CryptoMarkets language={language}/>;
  const zh = language === "zh";
  const portfolio = kind === "portfolio";
  const items = portfolio
    ? (zh ? [["01", "资产篮子", "预留股票、基金及加密资产分类，证券与代币化价格敞口分开标记。"], ["02", "目标权重", "预留权重合计校验、集中度和基准币设置。"], ["03", "再平衡与验证", "预留定时或偏离阈值规则；后续以含费用的历史回测验证。"]] : [["01", "Asset basket", "Separate equities, funds, crypto and tokenized price exposure."], ["02", "Target weights", "Weight validation, concentration and base-currency settings are planned."], ["03", "Rebalance & validate", "Scheduled or deviation-based rules, followed by cost-aware backtesting."]])
    : (zh ? [["BTC / ETH / SOL", "现货市场", "预留行情、成交额和价格历史；当前尚未接入行情。"], ["FUNDING / OI", "衍生品风险", "预留资金费率、未平仓量及清算风险，与现货区分。"], ["NEWS / MACRO", "证据与传导", "预留监管、流动性、链上与宏观证据；本轮不生成加密报告。"]] : [["BTC / ETH / SOL", "Spot markets", "Prices, volume and history are reserved; no live feed is connected."], ["FUNDING / OI", "Derivatives risk", "Funding, open interest and liquidation risk, distinct from spot."], ["NEWS / MACRO", "Evidence & transmission", "Regulation, liquidity, on-chain and macro evidence. Crypto reports are not generated yet."]]);
  return <section className="market-expansion" data-module={kind}>
    <header><div><span className="eyebrow">{portfolio ? <Layers3 size={16}/> : <Coins size={16}/>} {portfolio ? "ORAKT BASKETS" : "ORAKT DIGITAL ASSETS"}</span><h1>{portfolio ? (zh ? "组合实验室 · 自建资产篮子" : "Portfolio lab · Custom baskets") : (zh ? "加密市场分析" : "Crypto market analysis")}</h1><p>{portfolio ? (zh ? "先为你的组合留出研究空间：资产、权重、再平衡与风险。" : "A research space for assets, weights, rebalancing and risk.") : (zh ? "独立市场入口已预留。行情、证据与报告按阶段接入，不以演示价格代替真实数据。" : "A dedicated market area. Feeds, evidence and reports will be connected in stages; no simulated quotes are presented as live.")}</p></div><b className="module-status">{zh ? "功能预留 · 未接数据" : "Reserved · No feed"}</b></header>
    <div className="expansion-grid">{items.map(([id,title,description])=><article key={id}><small>{id}</small><h2>{title}</h2><p>{description}</p><span>{zh ? "待接入" : "Not connected"}</span></article>)}</div>
    <footer><ShieldCheck size={18}/><p>{portfolio ? (zh ? "这是研究与模拟组合模块，不是受监管 ETF，不持有客户资产，不自动交易。当前仅预留入口，不会创建投资账户。" : "A reserved research/simulation module, not a regulated ETF. No custody, automatic trading or investment account creation.") : (zh ? "加密资产波动与流动性风险较高。未连接钱包、交易所账户或下单接口；报告数量为 0。" : "Crypto carries volatility and liquidity risks. No wallets, exchange accounts or execution interfaces are connected; 0 reports.")}</p></footer>
    {portfolio && <a className="module-source" href="https://www.okx.com/zh-hans/help/viii-smart-portfolio" target="_blank" rel="noreferrer">{zh ? "参考：OKX 智能组合官方说明 ↗" : "Reference: OKX Smart Portfolio documentation ↗"}</a>}
  </section>;
}
