"use client";
import useDisplayLanguage from "./useDisplayLanguage";

import { useEffect, useMemo, useRef, useState } from "react";
import { accessHref, productPlans } from "./product-plans";
import OraktMegaNav from "./OraktMegaNav";
import OraktSignalField from "./OraktSignalField";
import OraktBrandIcon from "./OraktBrandIcon";
import OraktArrow from "./OraktArrow";
import OraktWorldScene from "./OraktWorldScene";
import OraktChainScene from "./OraktChainScene";
import styles from "./OraktLanding.module.css";
import {marketingPages,legacyMarketingPaths,type MarketingPageKey} from "./marketing-pages";
import MarketingGuide from "./MarketingGuide";
import OraktContour from "./OraktContour";
import SiteFooter from "./SiteFooter";
import usePublishedMetrics from './usePublishedMetrics';
import HeroOutlineWord from './HeroOutlineWord';
import OraktAISection from './OraktAISection';
import ProtocolSection from './ProtocolSection';

type Language = "zh" | "en";

type LandingMetrics = {
  newsRecords?: number;
  events: number;
  articles: number;
  reports: number;
  companies: number;
  generatedAt: string;
};

const copy = {
  zh: {
    nav: [
      ["world", "世界事件"],
      ["chains", "因果链"],
      ["markets", "市场情报"],
      ["lab", "因子实验室"],
      ["plans", "版本方案"],
    ],
    access: "进入 ORAKT",
    eyebrow: "GLOBAL CAUSAL INTELLIGENCE",
    heroLead: "看见事件。理解传导。验证结果。",
    heroBody:
      "ORAKT 把新闻、冲突、宏观数据、公司披露与市场价格连成可追溯的因果地图，让每个判断都能回到证据。",
    heroPrimary: "探索世界事件",
    heroSecondary: "查验研究报告",
    live: "已发布数据",
    scroll: "向下探索系统",
    proofTitle: "不是更快地下结论，\n而是更清楚地知道结论从哪里来。",
    proofBody:
      "从一条报道到市场结果，中间往往隔着政策预期、资金流、供应链与替代解释。ORAKT 保留这些中间步骤，并逐项标记证据状态。",
    steps: ["报道事实", "机制假设", "数据核验", "替代解释", "形成结论"],
    systemKicker: "ONE SYSTEM · FOUR LENSES",
    systemTitle: "从世界现场，到可验证的市场判断。",
    modules: {
      world: {
        number: "01",
        name: "ORAKT WORLD",
        title: "事件不是列表，\n而是正在变化的空间。",
        body: "在同一张地图上按时间查看冲突、灾害、经济指标与供应链设施。缩放到国家、区域与城市，保留地点精度和来源边界。",
        points: ["时间轴回放与范围过滤", "冲突、经济、运输与供应链图层", "移动端按需加载，避免一次载入全部数据"],
        link: "打开事件地图",
      },
      chains: {
        number: "02",
        name: "ORAKT CHAINS",
        title: "把“因为”拆开，\n直到每一步都能被质疑。",
        body: "本地研究引擎先提出假设，再检索全文、公告和市场序列。验证器检查时间顺序、机制证据、预期差与更强的替代解释。",
        points: ["线性与非线性传导链", "支持、反证与缺口并列", "置信度拆解与人工反馈"],
        link: "查看证据报告",
      },
      markets: {
        number: "03",
        name: "ORAKT MARKETS",
        title: "公司、行业与宏观，\n在同一个截止时间比较。",
        body: "连接财报、价格、持仓披露、供应链与宏观周期。比较时先核对数据截止日、可得时间与覆盖范围，避免用后来信息解释过去的判断。",
        points: ["A 股与美股公司报告", "多周期入场区间与风险边界", "行业基准与大盘基准双重比较"],
        link: "进入市场报告",
      },
      lab: {
        number: "04",
        name: "ORAKT LAB",
        title: "好故事不等于好因子。\n让未来数据来决定。",
        body: "因子必须经历历史回放、非重叠样本、交易成本、置信区间与未来到期验证。没有足够样本，就保持“收集中”，不自动升级。",
        points: ["样本外回测与未来验证", "数据版本、参数与审计记录", "有效因子进入候选，失败因子保留原因"],
        link: "查看验证状态",
      },
    },
    pipelineKicker: "AUDITABLE BY DESIGN",
    pipelineTitle: "一条结论的完整旅程",
    pipelineBody: "每个节点都有来源、时间、证据状态和不确定性。系统展示推导过程，而不只展示最后一句话。",
    evidenceLabels: ["事实已确认", "机制部分支持", "市场数据已验证", "替代解释待排除"],
    companyKicker: "INSOLVE TECH · COMPANY",
    companyTitle: "为复杂世界，构建可验证的研究基础设施。",
    companyBody:
      "Insolve Tech 是 ORAKT 背后的产品与研究团队。我们把新闻全文、地理事件、企业披露与市场序列放在同一个时间坐标里，让研究从观点文本升级为可复查、可回测、可持续改进的证据系统。",
    companyPillars: [
      ["ALPHA DISCOVERY", "Alpha 因子挖掘", "从跨市场与跨事件数据中提出候选因子，再用样本外数据、成本和未来到期结果淘汰伪相关。"],
      ["CAUSAL VERIFICATION", "因果证据核验", "把结论拆成事实、机制、传导和结果；并列支持、反证、时间顺序与更强替代解释。"],
      ["DECISION INFRASTRUCTURE", "研究决策基础设施", "把地图、报告、因子与审核记录连接起来，让团队可以追踪一个判断如何形成、何时失效。"],
    ],
    directionKicker: "PRODUCT DIRECTION",
    directionTitle: "从可见的事件，走向可验证的世界模型。",
    directionSteps: [
      ["NOW", "世界事件与证据报告", "让全球事件、公司与市场结果在同一时间轴上被查验。"],
      ["NEXT", "因子工厂与组合传导", "把经多轮回测和未来验证的逻辑链转化为可比较的研究因子。"],
      ["SCALE", "区域身份、团队协作与 API", "为中文与全球用户建立合规入口，并向专业研究工作流开放结构化能力。"],
    ],
    accessKicker: "IDENTITY & ACCESS",
    accessTitle: "为中文与全球用户设计的同一套入口。",
    accessBody: "使用 ChatGPT、Google、Phantom 钱包或独立 ORAKT 账号登录。免费查看地图与报告目录，全文按账号授权开放；登录不会自动扣费。",
    pilot: "当前可用",
    coming: "准备接入",
    china: "独立 ORAKT 账号",
    global: "Google 账号",
    chinaMethods: "用户名与密码 · 恢复码找回",
    globalMethods: "Google 身份验证 · 已发布内容只读",
    pilotMethods: "Phantom · Solana 钱包",
    plansKicker: "PLANS · MONTHLY",
    plansTitle: "从看见世界，到建立自己的研究系统。",
    planNote: "Signal / Research 支持 Solana USDC、USDT 按月付款，不自动续费。Team 尚未开放。",
    finalTitle: "THE WORLD MOVES\nIN CHAINS.",
    finalBody: "世界以链条运转。ORAKT 让它可见、可查、可验证。",
    finalButton: "进入 ORAKT WORLD",
    disclaimer: "研究工具 · 不是投资建议 · 已发布内容只读",
    updated: "数据发布",
  },
  en: {
    nav: [
      ["world", "World"],
      ["chains", "Chains"],
      ["markets", "Markets"],
      ["lab", "Lab"],
      ["plans", "Plans"],
    ],
    access: "Enter ORAKT",
    eyebrow: "GLOBAL CAUSAL INTELLIGENCE",
    heroLead: "See the event. Trace the transmission. Verify the outcome.",
    heroBody:
      "ORAKT connects news, conflict, macro data, company disclosures and market prices into an auditable causal map — so every judgment can return to its evidence.",
    heroPrimary: "Explore world events",
    heroSecondary: "Audit a research report",
    live: "Published data",
    scroll: "Explore the system",
    proofTitle: "Not faster conclusions.\nClearer origins.",
    proofBody:
      "Between a report and a market outcome sit expectations, capital flows, supply chains and competing explanations. ORAKT preserves those steps and marks the evidence state of each one.",
    steps: ["Reported fact", "Mechanism", "Data test", "Alternatives", "Conclusion"],
    systemKicker: "ONE SYSTEM · FOUR LENSES",
    systemTitle: "From events on the ground to market judgments you can audit.",
    modules: {
      world: {
        number: "01",
        name: "ORAKT WORLD",
        title: "Events are not a feed.\nThey are a changing space.",
        body: "Explore conflict, disasters, economic indicators and supply-chain facilities on one time-aware map, from countries down to regions and cities.",
        points: ["Timeline replay and range filters", "Conflict, economy, transport and supply layers", "Demand-loaded mobile rendering"],
        link: "Open event map",
      },
      chains: {
        number: "02",
        name: "ORAKT CHAINS",
        title: "Break apart “because”\nuntil every step can be challenged.",
        body: "The local research engine proposes a hypothesis, retrieves full text, filings and market series, then tests timing, mechanism, expectations and stronger alternatives.",
        points: ["Linear and nonlinear transmission", "Support, contradiction and gaps side by side", "Confidence decomposition and review"],
        link: "View evidence reports",
      },
      markets: {
        number: "03",
        name: "ORAKT MARKETS",
        title: "Company, sector and macro —\none shared cutoff.",
        body: "Link filings, prices, disclosed ownership, supply chains and cycles. Check data cutoffs, availability times and coverage before comparing, to keep hindsight out of earlier judgments.",
        points: ["China and U.S. company research", "Multi-horizon entry and risk ranges", "Dual sector and market benchmarks"],
        link: "Enter market reports",
      },
      lab: {
        number: "04",
        name: "ORAKT LAB",
        title: "A good story is not a good factor.\nLet future data decide.",
        body: "Factors face replay, non-overlapping samples, costs, confidence intervals and future maturity tests. Without enough evidence, they remain collecting — never silently promoted.",
        points: ["Out-of-sample and forward validation", "Versioned data, parameters and audits", "Candidate promotion with failure memory"],
        link: "Inspect validation status",
      },
    },
    pipelineKicker: "AUDITABLE BY DESIGN",
    pipelineTitle: "The full journey of a conclusion",
    pipelineBody: "Every node carries a source, timestamp, evidence state and uncertainty. The reasoning process is visible — not only its final sentence.",
    evidenceLabels: ["Fact confirmed", "Mechanism partial", "Market data verified", "Alternative unresolved"],
    companyKicker: "INSOLVE TECH · COMPANY",
    companyTitle: "Research infrastructure for a world that refuses to stay simple.",
    companyBody:
      "Insolve Tech is the product and research team behind ORAKT. We place full-text news, geospatial events, company disclosures and market series on one shared timeline — turning research from opinion prose into evidence that can be audited, tested and improved.",
    companyPillars: [
      ["ALPHA DISCOVERY", "Alpha factor discovery", "Propose cross-market and cross-event factors, then reject false relationships with out-of-sample data, costs and forward outcomes."],
      ["CAUSAL VERIFICATION", "Causal evidence verification", "Split claims into fact, mechanism, transmission and outcome while keeping support, contradiction, timing and stronger alternatives visible."],
      ["DECISION INFRASTRUCTURE", "Decision research infrastructure", "Connect maps, reports, factors and review history so a team can trace how a judgment formed — and when it stopped working."],
    ],
    directionKicker: "PRODUCT DIRECTION",
    directionTitle: "From visible events to a testable model of the world.",
    directionSteps: [
      ["NOW", "World events and evidence reports", "Audit global events, companies and market outcomes on the same time axis."],
      ["NEXT", "Factor factory and portfolio transmission", "Turn repeatedly backtested, forward-validated chains into comparable research factors."],
      ["SCALE", "Regional identity, team workflows and APIs", "Create compliant entry points for Chinese and global users, then expose structured capabilities to professional research workflows."],
    ],
    accessKicker: "IDENTITY & ACCESS",
    accessTitle: "One system, designed for Chinese and global users.",
    accessBody: "Sign in with ChatGPT, Google, Phantom or an ORAKT account. Maps and the report catalog are free; full reports require account access. Signing in never triggers a charge.",
    pilot: "Available now",
    coming: "In preparation",
    china: "Independent ORAKT account",
    global: "Google account",
    chinaMethods: "Username & password · Saved recovery key",
    globalMethods: "Google identity · Published research",
    pilotMethods: "Phantom · Solana wallet",
    plansKicker: "PLANS · MONTHLY",
    plansTitle: "From seeing the world to building a research system of your own.",
    planNote: "Signal / Research support monthly Solana USDC or USDT payments, without automatic renewal. Team is not on sale.",
    finalTitle: "THE WORLD MOVES\nIN CHAINS.",
    finalBody: "ORAKT makes those chains visible, traceable and testable.",
    finalButton: "ENTER ORAKT WORLD",
    disclaimer: "Research tool · Not investment advice · Published content is read-only",
    updated: "Data published",
  },
} as const;

function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className={styles.logo} aria-label="ORAKT 观因">
      <OraktBrandIcon className={styles.brandAsset} />
      {!compact && (
        <span>
          <strong>ORAKT</strong>
          <small>观因</small>
        </span>
      )}
    </span>
  );
}

function Arrow() {
  return <OraktArrow />;
}

function MotionLine({
  text,
  outline = false,
  offset = 0,
}: {
  text: string;
  outline?: boolean;
  offset?: number;
}) {
  return (
    <span
      className={`${styles.motionLine} ${outline ? styles.heroOutline : ""}`}
      aria-hidden="true"
    >
      {outline && text === "MOVES" ? <HeroOutlineWord className={styles.outlineWord} /> : Array.from(text).map((character, index) => (
        <i
          className={styles.motionGlyph}
          key={`${character}-${index}`}
          style={{ "--glyph-index": offset + index } as React.CSSProperties}
        >
          {character === " " ? "\u00a0" : character}
        </i>
      ))}
    </span>
  );
}

function WorldPreview() {
  const points = [
    ["a", "650ms"],
    ["b", "1050ms"],
    ["c", "1650ms"],
    ["d", "2200ms"],
    ["e", "2450ms"],
    ["f", "500ms"],
  ] as const;

  return (
    <div className={`${styles.moduleVisual} ${styles.worldPreview}`} aria-hidden="true">
      <div className={styles.previewTop}><span>WORLD / 90D</span><b>12:42 UTC</b></div>
      <div className={styles.mapLines} />
      <div className={styles.mapSweep} />
      {points.map(([name, delay]) => (
        <i key={name} className={styles[`mapPoint${name.toUpperCase()}` as keyof typeof styles]} style={{ "--signal-delay": delay } as React.CSSProperties} />
      ))}
      <div className={styles.mapTrack}><span /><span /><span /></div>
      <div className={styles.previewLegend}><span><i /> CONFLICT</span><span><i /> MACRO</span><span><i /> SUPPLY</span></div>
    </div>
  );
}

function ChainPreview() {
  return (
    <div className={`${styles.moduleVisual} ${styles.chainPreview}`} aria-hidden="true">
      <svg viewBox="0 0 720 440">
        <g className={styles.chainWires}>
          <path d="M148 112 C 250 112, 220 220, 332 220" />
          <path d="M148 328 C 250 328, 220 220, 332 220" />
          <path d="M388 220 C 500 220, 468 116, 574 116" />
          <path d="M388 220 C 500 220, 468 326, 574 326" />
        </g>
        <g className={styles.chainPulse}>
          <path d="M148 112 C 250 112, 220 220, 332 220" />
          <path d="M148 328 C 250 328, 220 220, 332 220" />
          <path d="M388 220 C 500 220, 468 116, 574 116" />
          <path d="M388 220 C 500 220, 468 326, 574 326" />
        </g>
      </svg>
      <div className={`${styles.chainNode} ${styles.chainNodeOne}`}><span>01</span><b>POLICY</b><small>verified</small></div>
      <div className={`${styles.chainNode} ${styles.chainNodeTwo}`}><span>02</span><b>SUPPLY</b><small>context</small></div>
      <div className={`${styles.chainNode} ${styles.chainNodeCore}`}><span>03</span><b>MECHANISM</b><small>72%</small></div>
      <div className={`${styles.chainNode} ${styles.chainNodeFour}`}><span>04</span><b>PRICE</b><small>verified</small></div>
      <div className={`${styles.chainNode} ${styles.chainNodeFive}`}><span>05</span><b>ALTERNATIVE</b><small>open</small></div>
    </div>
  );
}

function MarketPreview() {
  const bars = [32, 46, 38, 62, 54, 78, 68, 92, 73, 85, 98, 88, 110, 103, 125, 118, 142, 132, 154, 148, 169, 157, 182, 176];
  return (
    <div className={`${styles.moduleVisual} ${styles.marketPreview}`} aria-hidden="true">
      <div className={styles.previewTop}><span>ORAKT / MARKET FIELD</span><b>1W · 1M · 1Y</b></div>
      <div className={styles.marketAxis}><span>+18%</span><span>0%</span><span>−12%</span></div>
      <div className={styles.marketBars}>
        {bars.map((height, index) => <i key={index} style={{ "--height": `${height}px`, "--bar-delay": `${450 + index * 32}ms` } as React.CSSProperties} />)}
      </div>
      <svg viewBox="0 0 720 260" preserveAspectRatio="none">
        <path className={styles.marketArea} d="M0 220 C75 214 86 180 146 187 S245 120 304 143 397 80 455 101 555 38 720 42 V260 H0Z" />
        <path className={styles.marketLine} d="M0 220 C75 214 86 180 146 187 S245 120 304 143 397 80 455 101 555 38 720 42" />
        <path className={styles.marketBenchmark} d="M0 236 C95 224 130 206 212 213 S350 173 442 181 570 137 720 145" />
      </svg>
      <div className={styles.marketBadge}><span>DUAL BENCHMARK</span><b>+4.8% EXCESS</b></div>
    </div>
  );
}

function LabPreview() {
  const cells = Array.from({ length: 48 }, (_, index) => (index * 17 + 11) % 9);
  return (
    <div className={`${styles.moduleVisual} ${styles.labPreview}`} aria-hidden="true">
      <div className={styles.previewTop}><span>FACTOR / OOS MATRIX</span><b>LOCKED CUTOFF</b></div>
      <div className={styles.labMatrix}>
        <span className={styles.labSweep} />
        {cells.map((value, index) => (
          <i
            key={index}
            data-level={value}
            style={{ "--cell-delay": `${250 + (index % 8) * 90 + Math.floor(index / 8) * 24}ms` } as React.CSSProperties}
          />
        ))}
      </div>
      <div className={styles.labScore}>
        <span>FORWARD VALIDATION</span>
        <strong>0.74</strong>
        <small>95% CI · [0.61, 0.82]</small>
      </div>
      <div className={styles.labFoot}><span>NON-OVERLAP</span><span>COST ADJUSTED</span><span>NO AUTO-PROMOTION</span></div>
    </div>
  );
}

function ProductModule({
  id,
  copy: moduleCopy,
  href,
  visual,
}: {
  id: string;
  copy: (typeof copy.zh.modules)[keyof typeof copy.zh.modules] | (typeof copy.en.modules)[keyof typeof copy.en.modules];
  href: string;
  visual: React.ReactNode;
}) {
  return (
    <article id={id} className={styles.module} data-orakt-reveal>
      <div className={styles.moduleCopy}>
        <div className={styles.moduleIndex}><span>{moduleCopy.number}</span><i /></div>
        <p className={styles.moduleName}>{moduleCopy.name}</p>
        <h3>{moduleCopy.title.split("\n").map((line) => <span key={line}>{line}</span>)}</h3>
        <p className={styles.moduleBody}>{moduleCopy.body}</p>
        <ul>{moduleCopy.points.map((point) => <li key={point}>{point}</li>)}</ul>
        <a className={styles.textLink} href={href}>{moduleCopy.link}<Arrow /></a>
      </div>
      {visual}
    </article>
  );
}

export default function OraktLanding({ metrics:initialMetrics, page="home" }: { metrics: LandingMetrics; page?:"home"|MarketingPageKey }) {
  const {metrics,stale}=usePublishedMetrics(initialMetrics);
  const [language, setLanguage] = useDisplayLanguage();
  const rootRef = useRef<HTMLElement | null>(null);
  const t = copy[language];
  const pageInfo=page==="home"?null:marketingPages[page];
  useEffect(()=>{if(page!=="home")return;const visit=()=>{const target=legacyMarketingPaths[location.hash];if(target)location.replace(target);};visit();addEventListener("hashchange",visit);return()=>removeEventListener("hashchange",visit);},[page]);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const nodes = [...root.querySelectorAll<HTMLElement>("[data-orakt-reveal]")];
    if (!("IntersectionObserver" in window)) {
      nodes.forEach((node) => node.dataset.visible = "true");
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((entry) => {
        if (entry.isIntersecting) {
          (entry.target as HTMLElement).dataset.visible = "true";
          observer.unobserve(entry.target);
        }
      }),
      { rootMargin: "0px 0px -12%", threshold: 0.12 },
    );
    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, [page]);

  const formatter = useMemo(
    () => new Intl.NumberFormat(language === "zh" ? "zh-CN" : "en-US"),
    [language],
  );

  const stats = [
    ...(Number.isSafeInteger(metrics.newsRecords)?[{value:metrics.newsRecords!,zh:'已收录新闻索引',en:'Indexed news records'}]:[]),
    { value: metrics.events, zh: "本地地理事件", en: "Geolocated events" },
    { value: metrics.articles, zh: "可分析正文", en: "Content-ready articles" },
    { value: metrics.reports, zh: "可查验研究报告", en: "Auditable reports" },
    { value: metrics.companies, zh: "市场龙头覆盖", en: "Market leaders covered" },
  ];

  function moveGlow(event: React.PointerEvent<HTMLElement>) {
    if (event.pointerType === "touch") return;
    const rect = event.currentTarget.getBoundingClientRect();
    event.currentTarget.style.setProperty("--pointer-x", `${event.clientX - rect.left}px`);
    event.currentTarget.style.setProperty("--pointer-y", `${event.clientY - rect.top}px`);
  }

  return (
    <main ref={rootRef} className={`${styles.site} ${page==="home"?"":styles.interior}`} data-marketing-page={page} onPointerMove={moveGlow}>
      <a className={styles.skipLink} href="#main-content">Skip to content</a>
      <div className={styles.cursorGlow} />
      <div className={styles.noise} />

      <OraktMegaNav
        language={language}
        enterHref={accessHref("/platform")}
        onLanguageChange={setLanguage}
        homeHref="/"
      />
      {pageInfo&&<header id="main-content" className={styles.interiorHeading}><a href="/">{language==="zh"?"返回首页":"Back to home"}</a><p>{pageInfo.kicker}</p><h1>{language==="zh"?pageInfo.zh:pageInfo.en}</h1></header>}

      {page==="home" && <>
      <section id="top" className={styles.hero}>
        <OraktSignalField className={styles.heroSignalField} intensity={1.05} speed={0.9} />
        <div id="main-content" className={styles.heroCopy}>
          <p className={styles.eyebrow}><i />{t.eyebrow}<span>ORAKT / 2026</span></p>
          <h1 aria-label="See what moves the world">
            <MotionLine text="SEE WHAT" />
            <MotionLine text="MOVES" outline offset={8} />
            <MotionLine text="THE WORLD." offset={13} />
          </h1>
          <div className={styles.heroText}>
            <h2>{t.heroLead}</h2>
            <p>{t.heroBody}</p>
            <div className={styles.heroActions}>
              <a className={styles.primaryButton} href={accessHref("/platform")}><span>{t.heroPrimary}</span><Arrow /></a>
              <a className={styles.secondaryButton} href={accessHref("/platform/research", "signal")}>{t.heroSecondary}<span>→</span></a>
            </div>
          </div>
        </div>
        <a className={styles.scrollCue} href="#proof"><i /><span>{t.scroll}</span></a>
      </section>

      <section className={styles.statRail} aria-label="Published data coverage">
        <div className={styles.marquee}>
          {[0, 1].map((group) => <div className={styles.marqueeGroup} key={group} aria-hidden={group === 1 ? true : undefined}>
            {stats.map((stat) => <div className={styles.statItem} key={stat.en} title={`${language==='zh'?'已发布库截至':'Published library as of'} ${metrics.generatedAt.slice(0,10)}${stale?' · Offline / 上次数据':''}`}><strong>{formatter.format(stat.value)}</strong><span>{language === "zh" ? stat.zh : stat.en}</span><i /></div>)}
          </div>)}
        </div>
      </section>

      <OraktAISection language={language}/>
      <section id="proof" className={styles.proof}>
        <div className={styles.sectionRule} data-orakt-reveal><span>WHY ORAKT</span><i /></div>
        <div className={styles.proofGrid} data-orakt-reveal>
          <h2>{t.proofTitle.split("\n").map((line) => <span key={line}>{line}</span>)}</h2>
          <div><p>{t.proofBody}</p><small>FACT ≠ MECHANISM ≠ OUTCOME</small></div>
        </div>
        <div className={styles.methodRail} data-orakt-reveal>
          {t.steps.map((step, index) => (
            <div key={step} style={{'--step':index} as React.CSSProperties}><span>0{index + 1}</span><b>{step}</b>{index < t.steps.length - 1 && <i />}</div>
          ))}
        </div>
      </section>

      <section className={styles.systemIntro}>
        <p>{t.systemKicker}</p>
        <h2>{t.systemTitle}</h2>
      </section>
      <section className={styles.cryptoBridge}>
        <span className={styles.eyebrow}>ORAKT × SOLANA</span>
        <h2>{language==='zh'?'让信息有出处，让资产有上下文。':'Provenance for information. Context for assets.'}</h2>
        <p>{language==='zh'?'从原始新闻、可核验的主张到事件与资产暴露，把研究连接至 Solana 与代币化资产生态。内容哈希与审核历史可以被查验；链上记录不替代事实核查。':'Connect original news, verifiable claims and events to asset exposure across Solana and tokenized-asset ecosystems. Content hashes and review histories are inspectable; an on-chain record does not replace fact checking.'}</p>
        <div><span>SOURCE</span><i>→</i><span>CLAIM</span><i>→</i><span>EVENT</span><i>→</i><span>ASSET</span></div>
        <a href={accessHref('/platform/assets')}>{language==='zh'?'探索新闻与链上资产':'Explore news & on-chain assets'} ↗</a>
        <small>{language==='zh'?'已有 Devnet 存证；管理员可通过 Phantom 手动签名发布主网 Memo。自定义协议已部署 Devnet 并提供验收交易，主网合约付款未启用。具体记录以网络与签名为准；不提供自动资产交易。':'Devnet provenance exists; administrators can manually sign mainnet Memo publications with Phantom. The custom protocol is deployed on Devnet with acceptance transactions; mainnet contract checkout is disabled. Verify each network and signature. No automatic asset trading.'}</small>
      </section>
      <ProtocolSection language={language}/>

      <section className={styles.modules}>
        <ProductModule id="world" copy={t.modules.world} href={accessHref("/platform")} visual={<OraktWorldScene language={language} />} />
        <ProductModule id="chains" copy={t.modules.chains} href={accessHref("/platform/research", "signal")} visual={<OraktChainScene language={language} />} />
        <ProductModule id="markets" copy={t.modules.markets} href={accessHref("/platform/research", "signal")} visual={<div><MarketPreview/><p className={styles.demoNote}>{language==="zh"?"界面概念示意 · 图中价格、曲线与超额收益不代表实际业绩":"Interface illustration · Prices, charts and excess returns are not actual performance"}</p></div>} />
      </section>

      </>}

      {page==="lab"&&<section className={styles.modules}>
        <ProductModule id="lab" copy={t.modules.lab} href={accessHref("/platform/data", "research")} visual={<div><LabPreview/><p className={styles.demoNote}>{language==="zh"?"验证界面示意 · 数值与区间为演示，不是已验证收益或获利概率":"Validation interface illustration · Values and intervals are demonstrations, not verified returns or profit probabilities"}</p></div>} />
      </section>}
      {page==="roadmap"&&<section className={styles.company}>
        <div id="direction" className={styles.direction} data-orakt-reveal>
          <header>
            <p>{t.directionKicker}</p>
            <h2>{t.directionTitle}</h2>
          </header>
          <div>
            {t.directionSteps.map(([phase, title, body], index) => (
              <article key={phase} style={{ "--direction-index": index } as React.CSSProperties}>
                <span>{phase}</span>
                <h3>{title}</h3>
                <p>{body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>}

      {page==="company" && <>
      <section id="company" className={styles.company}>
        <div className={styles.companyLead} data-orakt-reveal>
          <p>{t.companyKicker}</p>
          <h2>{t.companyTitle}</h2>
          <span>{t.companyBody}</span>
        </div>
        <div className={styles.companyPillars} data-orakt-reveal>
          {t.companyPillars.map(([code, title, body], index) => (
            <article key={code}>
              <header><span>0{index + 1}</span><b>{code}</b></header>
              <h3>{title}</h3>
              <p>{body}</p>
              <i aria-hidden="true" />
            </article>
          ))}
        </div>
      </section>

      </>}

      {page==="research" && <>
      <section className={styles.pipeline}>
        <div className={styles.pipelineHeading} data-orakt-reveal>
          <p>{t.pipelineKicker}</p>
          <h2>{t.pipelineTitle}</h2>
          <span>{t.pipelineBody}</span>
        </div>
        <div className={styles.pipelineStage} data-orakt-reveal>
          <div className={styles.pipelineTrace}>
            <span className={styles.traceOne} /><span className={styles.traceTwo} /><span className={styles.traceThree} />
          </div>
          {t.evidenceLabels.map((label, index) => (
            <article key={label} style={{ "--index": index } as React.CSSProperties}>
              <header><span>0{index + 1}</span><i className={index === 3 ? styles.statusOpen : ""} /></header>
              <h3>{label}</h3>
              <p>{index === 0 ? "SOURCE / T+00" : index === 1 ? "LINK / T+04" : index === 2 ? "SERIES / T+18" : "COUNTER / OPEN"}</p>
              <div><i /><i /><i /></div>
            </article>
          ))}
        </div>
        <p className={styles.demoNote}>{language==="zh"?"以下为教学报告示意 · 分数、日期与核验数量不是实际报告结果":"Illustrative teaching report · Score, dates and verification counts are not actual report results"}</p>
        <div className={styles.reportWindow} data-orakt-reveal>
          <aside>
            <Logo compact />
            <span>RESEARCH / 0417</span>
            <i />
            <small>LOCKED CUTOFF<br />2026-09-19</small>
          </aside>
          <div className={styles.reportBody}>
            <header><span>CAUSAL AUDIT</span><b>72 / 100</b></header>
            <h3>{language === "zh" ? "政策预期如何穿过收益率、估值与供应链" : "How policy expectations travel through yields, valuation and supply chains"}</h3>
            <div className={styles.reportChain}><span>POLICY</span><i /><span>EXPECTATION</span><i /><span>YIELD</span><i /><span>VALUATION</span></div>
            <footer><span>07 VERIFIED</span><span>02 PARTIAL</span><span>01 OPEN</span></footer>
          </div>
        </div>
      </section>

      </>}

      {page==="membership" && <>
      <section id="access" className={styles.access}>
        <div className={styles.accessCopy} data-orakt-reveal>
          <p>{t.accessKicker}</p><h2>{t.accessTitle}</h2><span>{t.accessBody}</span>
        </div>
        <div className={styles.identityGrid} data-orakt-reveal>
          <article className={styles.identityActive}>
            <header><span>ORAKT WALLET</span><b>{t.pilot}</b></header>
            <div className={styles.identityGlyph}><Logo compact /><i /><i /></div>
            <h3>{t.pilotMethods}</h3>
            <a href={accessHref("/platform")}>{t.access}<Arrow /></a>
          </article>
          <article>
            <header><span>ORAKT ACCOUNT</span><b>{t.pilot}</b></header>
            <div className={styles.identityGlyph}><strong>O</strong><i /><i /></div>
            <h3>{t.china}</h3><p>{t.chinaMethods}</p>
          </article>
          <article>
            <header><span>GOOGLE IDENTITY</span><b>{t.pilot}</b></header>
            <div className={styles.identityGlyph}><strong>G</strong><i /><i /></div>
            <h3>{t.global}</h3><p>{t.globalMethods}</p>
          </article>
        </div>
      </section>

      </>}

      {page==="plans" && <>
      <section id="plans" className={styles.plans}>
        <div className={styles.plansHeading} data-orakt-reveal><p>{t.plansKicker}</p><h2>{t.plansTitle}</h2><span>{t.planNote}</span></div>
        <div className={styles.planGrid} data-orakt-reveal>
          {productPlans.map((plan, index) => (
            <article key={plan.name} data-accent={plan.accent}>
              <header><span>0{index + 1}</span><b>{plan.key==="team"?"PLANNED":plan.key==="explorer"?"FREE":"MONTHLY"}</b></header>
              <h3>{plan.name}</h3>
              <div className={styles.price}><small>US$</small><strong>{plan.price}</strong><span>/ MO</span></div>
              <ul>{(language === "zh" ? plan.featuresZh : plan.featuresEn).map((item) => <li key={item}><i />{item}</li>)}</ul>
              <a href={plan.key==="team"?"/roadmap#next":index===0?accessHref(plan.returnTo,plan.key):"/account/billing"}>{plan.key==="team"?(language==="zh"?"了解规划":"Explore the roadmap"):index===0?t.access:language==="zh"?"按月开通":"Monthly checkout"}<Arrow /></a>
            </article>
          ))}
        </div>
      </section>

      </>}

      {page==="home"?<OraktContour language={language}/>:<MarketingGuide page={page} language={language}/>}

      {page!=="home" && <>
      <section className={styles.finalCta}>
        <div className={styles.finalOrbit} aria-hidden="true"><i /><i /><i /></div>
        <p>ORAKT · 观因</p>
        <h2>{t.finalTitle.split("\n").map((line) => <span key={line}>{line}</span>)}</h2>
        <h3>{t.finalBody}</h3>
        <a href={accessHref("/platform")}><span>{t.finalButton}</span><Arrow /></a>
      </section>

      </>}

      <SiteFooter language={language} snapshotAt={metrics.generatedAt} page={page}/>
    </main>
  );
}
