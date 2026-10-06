"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type FocusEvent,
  type KeyboardEvent,
  type PointerEvent,
} from "react";
import styles from "./OraktMegaNav.module.css";
import OraktBrandIcon from "./OraktBrandIcon";
import OraktArrow from "./OraktArrow";

export type OraktMegaNavLanguage = "zh" | "en";

export type OraktMegaNavProps = {
  language: OraktMegaNavLanguage;
  enterHref: string;
  homeHref?: string;
  className?: string;
  onLanguageChange?: (language: OraktMegaNavLanguage) => void;
  onNavigate?: () => void;
};

const sectionOrder = ["company", "product", "research", "future"] as const;
type SectionId = (typeof sectionOrder)[number];
const sectionHref:Record<SectionId,string>={company:"/company",product:"/#world",research:"/research",future:"/roadmap"};

type NavItem = {
  href: string;
  number: string;
  title: string;
  description: string;
  meta: string;
};

type NavSection = {
  label: string;
  kicker: string;
  title: string;
  description: string;
  feature: NavItem;
  items: readonly NavItem[];
};

type NavCopy = {
  navigationLabel: string;
  openMenu: string;
  closeMenu: string;
  switchLanguage: string;
  enter: string;
  enterNote: string;
  explore: string;
  byline: string;
  sections: Record<SectionId, NavSection>;
};

const copy = {
  zh: {
    navigationLabel: "INSOLVE TECH 与 ORAKT 导航",
    openMenu: "打开导航",
    closeMenu: "关闭导航",
    switchLanguage: "切换至英文",
    enter: "进入 ORAKT",
    enterNote: "已发布地图与研究报告",
    explore: "查看详情",
    byline: "BY INSOLVE TECH",
    sections: {
      company: {
        label: "公司",
        kicker: "INSOLVE TECH",
        title: "为复杂决策构建可查验的研究基础设施。",
        description:
          "我们把分散的公开信息、结构化市场数据和研究方法放进同一条可追溯工作流。ORAKT 是 INSOLVE TECH 打造的因果与市场情报产品。",
        feature: {
          href: "/company",
          number: "00 / COMPANY",
          title: "证据先于结论",
          description:
            "系统保留来源、时间边界、反证与人工复核记录，让判断可以被复查，而不是只留下一个分数。",
          meta: "EVIDENCE · TIME · REVIEW",
        },
        items: [
          {
            href: "/company",
            number: "01",
            title: "研究原则",
            description: "事实、机制、验证和替代解释分层呈现。",
            meta: "AUDITABLE BY DESIGN",
          },
          {
            href: "/membership",
            number: "02",
            title: "产品边界",
            description: "研究工具，不代替投资判断；已发布内容保持只读。",
            meta: "RESEARCH, NOT ADVICE",
          },
        ],
      },
      product: {
        label: "产品",
        kicker: "ORAKT PRODUCT",
        title: "从世界事件到市场结果，一条链路完成查验。",
        description:
          "ORAKT 将新闻、宏观数据、公司披露、供应链与价格序列连接为带时间戳的因果地图，并明确标记证据强弱。",
        feature: {
          href: "/",
          number: "01 / ORAKT",
          title: "全球因果与市场情报系统",
          description:
            "先定位发生了什么，再解释影响如何传导，最后用公司与市场数据验证结果。每一步都能回到原始来源。",
          meta: "SEE · TRACE · VERIFY",
        },
        items: [
          {
            href: "/#world",
            number: "01",
            title: "ORAKT WORLD",
            description: "按地点与时间回放冲突、经济、运输和供应链事件。",
            meta: "EVENT MAP",
          },
          {
            href: "/#chains",
            number: "02",
            title: "ORAKT CHAINS",
            description: "把机制、支持证据、反证和缺口放在同一证据链中。",
            meta: "CAUSAL EVIDENCE",
          },
          {
            href: "/#markets",
            number: "03",
            title: "ORAKT MARKETS",
            description: "在统一数据截止日比较公司、行业和宏观环境。",
            meta: "MARKET INTELLIGENCE",
          },
          {
            href: "/lab",
            number: "04",
            title: "ORAKT LAB",
            description: "用样本外回测和到期数据筛选可重复的因子。",
            meta: "FACTOR VALIDATION",
          },
        ],
      },
      research: {
        label: "研究能力",
        kicker: "RESEARCH ENGINE",
        title: "不是生成一段解释，而是形成一份可复核的研究记录。",
        description:
          "研究流程锁定信息可得时间，区分事实与假设，并让失败的因子和未排除的解释继续留在记录里。",
        feature: {
          href: "/lab",
          number: "A / ALPHA",
          title: "Alpha 因子挖掘",
          description:
            "候选信号经过历史回放、非重叠样本、交易成本、置信区间与未来到期验证；样本不足时只标记为收集中。",
          meta: "OUT-OF-SAMPLE · FORWARD TEST",
        },
        items: [
          {
            href: "/#chains",
            number: "B",
            title: "因果证据链",
            description: "检查时间顺序、传导机制、预期差和更强替代解释。",
            meta: "SUPPORT · CONTRADICTION · GAP",
          },
          {
            href: "/#world",
            number: "C",
            title: "事件地图",
            description: "用地理精度、来源边界与时间轴还原事件现场。",
            meta: "PLACE · SOURCE · TIME",
          },
          {
            href: "/#markets",
            number: "D",
            title: "市场情报",
            description: "连接披露、价格、持仓、供应链与行业基准。",
            meta: "COMPANY · SECTOR · MACRO",
          },
          {
            href: "/research",
            number: "E",
            title: "研究审计",
            description: "为每个节点保留来源、时间、证据状态与不确定性。",
            meta: "PROVENANCE · VERSION · REVIEW",
          },
        ],
      },
      future: {
        label: "未来方向",
        kicker: "PRODUCT DIRECTION",
        title: "把一次研究，沉淀为持续更新的决策系统。",
        description:
          "路线图围绕数据覆盖、协作审阅和区域化服务展开；能力会在数据授权、身份与合规配置完成后分阶段开放。",
        feature: {
          href: "/roadmap",
          number: "NEXT / SYSTEM",
          title: "从已发布研究到团队研究账本",
          description:
            "让事件、公司、证据链和因子验证共享版本记录，使团队能够复盘当时看到了什么、为何形成判断。",
          meta: "SHARED CONTEXT · VERSIONED EVIDENCE",
        },
        items: [
          {
            href: "/roadmap",
            number: "01",
            title: "更完整的数据图层",
            description: "扩展区域事件、供应链节点与点时公司数据覆盖。",
            meta: "COVERAGE",
          },
          {
            href: "/plans",
            number: "02",
            title: "团队协作与审阅",
            description: "围绕假设、反证、参数和报告版本形成协作记录。",
            meta: "WORKFLOW",
          },
          {
            href: "/membership",
            number: "03",
            title: "区域化身份与服务",
            description: "在合规、支付与数据授权就绪后分区上线。",
            meta: "ACCESS",
          },
        ],
      },
    },
  },
  en: {
    navigationLabel: "INSOLVE TECH and ORAKT navigation",
    openMenu: "Open navigation",
    closeMenu: "Close navigation",
    switchLanguage: "Switch to Chinese",
    enter: "Enter ORAKT",
    enterNote: "Published maps and research reports",
    explore: "Explore",
    byline: "BY INSOLVE TECH",
    sections: {
      company: {
        label: "Company",
        kicker: "INSOLVE TECH",
        title: "Research infrastructure for decisions that need to be checked.",
        description:
          "We bring fragmented public information, structured market data and research methods into one traceable workflow. ORAKT is the causal and market intelligence product built by INSOLVE TECH.",
        feature: {
          href: "/company",
          number: "00 / COMPANY",
          title: "Evidence before conclusions",
          description:
            "Sources, point-in-time boundaries, counterevidence and human review stay attached to the work, so a judgment can be inspected rather than reduced to a score.",
          meta: "EVIDENCE · TIME · REVIEW",
        },
        items: [
          {
            href: "/company",
            number: "01",
            title: "Research principles",
            description: "Facts, mechanisms, tests and alternatives remain distinct.",
            meta: "AUDITABLE BY DESIGN",
          },
          {
            href: "/membership",
            number: "02",
            title: "Product boundary",
            description: "A research tool, not investment advice; published content is read-only.",
            meta: "RESEARCH, NOT ADVICE",
          },
        ],
      },
      product: {
        label: "Product",
        kicker: "ORAKT PRODUCT",
        title: "Trace the full path from world events to market outcomes.",
        description:
          "ORAKT links news, macro data, filings, supply chains and price series in a timestamped causal map, with the strength of evidence made explicit.",
        feature: {
          href: "/",
          number: "01 / ORAKT",
          title: "Global causal and market intelligence",
          description:
            "Locate what happened, trace how the effect travels, then test the outcome against company and market data. Every step returns to its source.",
          meta: "SEE · TRACE · VERIFY",
        },
        items: [
          {
            href: "/#world",
            number: "01",
            title: "ORAKT WORLD",
            description: "Replay conflict, economic, transport and supply-chain events by place and time.",
            meta: "EVENT MAP",
          },
          {
            href: "/#chains",
            number: "02",
            title: "ORAKT CHAINS",
            description: "Keep mechanisms, support, contradictions and gaps in one evidence chain.",
            meta: "CAUSAL EVIDENCE",
          },
          {
            href: "/#markets",
            number: "03",
            title: "ORAKT MARKETS",
            description: "Compare company, sector and macro conditions at one shared data cutoff.",
            meta: "MARKET INTELLIGENCE",
          },
          {
            href: "/lab",
            number: "04",
            title: "ORAKT LAB",
            description: "Use out-of-sample replay and matured outcomes to filter repeatable factors.",
            meta: "FACTOR VALIDATION",
          },
        ],
      },
      research: {
        label: "Research",
        kicker: "RESEARCH ENGINE",
        title: "Not a generated explanation. An inspectable research record.",
        description:
          "The workflow freezes information availability, separates facts from hypotheses, and retains failed factors and unresolved alternatives in the record.",
        feature: {
          href: "/lab",
          number: "A / ALPHA",
          title: "Alpha factor discovery",
          description:
            "Candidate signals face historical replay, non-overlapping samples, costs, confidence intervals and forward maturity tests. Thin evidence stays in collection.",
          meta: "OUT-OF-SAMPLE · FORWARD TEST",
        },
        items: [
          {
            href: "/#chains",
            number: "B",
            title: "Causal evidence chains",
            description: "Test chronology, transmission, expectation gaps and stronger alternatives.",
            meta: "SUPPORT · CONTRADICTION · GAP",
          },
          {
            href: "/#world",
            number: "C",
            title: "Event map",
            description: "Reconstruct events with geographic precision, source boundaries and a timeline.",
            meta: "PLACE · SOURCE · TIME",
          },
          {
            href: "/#markets",
            number: "D",
            title: "Market intelligence",
            description: "Connect filings, prices, ownership, supply chains and sector benchmarks.",
            meta: "COMPANY · SECTOR · MACRO",
          },
          {
            href: "/research",
            number: "E",
            title: "Research audit",
            description: "Preserve source, time, evidence state and uncertainty at every node.",
            meta: "PROVENANCE · VERSION · REVIEW",
          },
        ],
      },
      future: {
        label: "Direction",
        kicker: "PRODUCT DIRECTION",
        title: "Turn individual research into a continuously updated decision system.",
        description:
          "The roadmap centers on data coverage, collaborative review and regional service. Capabilities open in stages as licensing, identity and compliance are ready.",
        feature: {
          href: "/roadmap",
          number: "NEXT / SYSTEM",
          title: "From published research to a team research ledger",
          description:
            "Events, companies, evidence chains and factor tests share version history, so a team can reconstruct what was known and why a judgment was made.",
          meta: "SHARED CONTEXT · VERSIONED EVIDENCE",
        },
        items: [
          {
            href: "/roadmap",
            number: "01",
            title: "Deeper data layers",
            description: "Expand regional events, supply-chain nodes and point-in-time company coverage.",
            meta: "COVERAGE",
          },
          {
            href: "/plans",
            number: "02",
            title: "Collaborative review",
            description: "Create team records around hypotheses, counterevidence, parameters and versions.",
            meta: "WORKFLOW",
          },
          {
            href: "/membership",
            number: "03",
            title: "Regional identity and service",
            description: "Launch by region as compliance, payments and data licensing are completed.",
            meta: "ACCESS",
          },
        ],
      },
    },
  },
} satisfies Record<OraktMegaNavLanguage, NavCopy>;

function BrandMark() {
  return <OraktBrandIcon className={styles.brandAsset} />;
}

function DirectionArrow() {
  return <OraktArrow />;
}

function trapFocus(root: HTMLElement | null, event: globalThis.KeyboardEvent) {
  const focusableElements = [...(root?.querySelectorAll<HTMLElement>(
    'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
  ) ?? [])].filter((element) => element.getClientRects().length > 0);
  const firstElement = focusableElements[0];
  const lastElement = focusableElements[focusableElements.length - 1];
  if (!firstElement || !lastElement) return;

  if (event.shiftKey && document.activeElement === firstElement) {
    event.preventDefault();
    lastElement.focus();
  } else if (!event.shiftKey && document.activeElement === lastElement) {
    event.preventDefault();
    firstElement.focus();
  }
}

export default function OraktMegaNav({
  language,
  enterHref,
  homeHref = "/",
  className,
  onLanguageChange,
  onNavigate,
}: OraktMegaNavProps) {
  const [activeSection, setActiveSection] = useState<SectionId | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mobileSection, setMobileSection] = useState<SectionId | null>("product");
  const [scrolled, setScrolled] = useState(false);
  const rootRef = useRef<HTMLElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const mobileButtonRef = useRef<HTMLButtonElement | null>(null);
  const triggerRefs = useRef<Record<SectionId, HTMLButtonElement | null>>({
    company: null,
    product: null,
    research: null,
    future: null,
  });
  const instanceId = useId().replace(/:/g, "");
  const t = copy[language];

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 16);
    const frame = window.requestAnimationFrame(onScroll);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("scroll", onScroll);
    };
  }, []);

  useEffect(() => {
    if (!activeSection && !mobileOpen) return;

    const onPointerDown = (event: globalThis.PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setActiveSection(null);
        setMobileOpen(false);
      }
    };

    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Tab" && mobileOpen) {
        trapFocus(rootRef.current, event);
        return;
      }
      if (event.key !== "Escape") return;
      event.preventDefault();
      const sectionToFocus = activeSection;
      setActiveSection(null);
      setMobileOpen(false);
      if (sectionToFocus) triggerRefs.current[sectionToFocus]?.focus();
      else mobileButtonRef.current?.focus();
    };

    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [activeSection, mobileOpen]);

  useEffect(() => {
    if (!mobileOpen) return;

    const documentElement = document.documentElement;
    const previousOverflow = documentElement.style.overflow;
    const mobileQuery = window.matchMedia("(max-width: 1040px)");
    const syncScrollLock = () => {
      documentElement.style.overflow = mobileQuery.matches ? "hidden" : previousOverflow;
    };

    syncScrollLock();
    mobileQuery.addEventListener("change", syncScrollLock);
    return () => {
      mobileQuery.removeEventListener("change", syncScrollLock);
      documentElement.style.overflow = previousOverflow;
    };
  }, [mobileOpen]);

  function closeNavigation() {
    setActiveSection(null);
    setMobileOpen(false);
    onNavigate?.();
  }

  function focusPanel(section: SectionId) {
    setActiveSection(section);
    window.requestAnimationFrame(() => {
      panelRef.current?.querySelector<HTMLAnchorElement>("a[href]")?.focus();
    });
  }

  function handleTriggerKeyDown(event: KeyboardEvent<HTMLButtonElement>, section: SectionId) {
    const index = sectionOrder.indexOf(section);

    if (event.key === "ArrowDown") {
      event.preventDefault();
      focusPanel(section);
      return;
    }

    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      event.preventDefault();
      const direction = event.key === "ArrowRight" ? 1 : -1;
      const nextSection = sectionOrder[(index + direction + sectionOrder.length) % sectionOrder.length];
      setActiveSection(nextSection);
      triggerRefs.current[nextSection]?.focus();
      return;
    }

    if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      const nextSection = event.key === "Home" ? sectionOrder[0] : sectionOrder[sectionOrder.length - 1];
      setActiveSection(nextSection);
      triggerRefs.current[nextSection]?.focus();
    }
  }

  function handleBlur(event: FocusEvent<HTMLElement>) {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
      setActiveSection(null);
    }
  }

  function handlePointerLeave(event: PointerEvent<HTMLElement>) {
    if (
      event.pointerType === "mouse" &&
      !rootRef.current?.contains(document.activeElement)
    ) {
      setActiveSection(null);
    }
  }

  const desktopPanelId = `${instanceId}-mega-panel`;
  const headerClassName = [
    styles.root,
    scrolled || activeSection || mobileOpen ? styles.rootActive : "",
    className ?? "",
  ].filter(Boolean).join(" ");

  return (
    <header
      ref={rootRef}
      className={headerClassName}
      onBlur={handleBlur}
      onPointerLeave={handlePointerLeave}
    >
      <div className={styles.headerBar}>
        <a className={styles.brand} href={homeHref} onClick={closeNavigation}>
          <BrandMark />
          <span className={styles.wordmark}>
            <strong>ORAKT</strong>
            <small>{t.byline}</small>
          </span>
        </a>

        <nav className={styles.desktopNav} aria-label={t.navigationLabel}>
          {sectionOrder.map((section) => {
            const triggerId = `${instanceId}-${section}-trigger`;
            const isActive = activeSection === section;
            return (
              <div key={section} className={styles.navEntry}>
              <a className={styles.sectionLink} href={sectionHref[section]} onClick={closeNavigation}>{t.sections[section].label}</a>
              <button
                ref={(node) => { triggerRefs.current[section] = node; }}
                id={triggerId}
                aria-label={language==="zh"?`展开${t.sections[section].label}导航`:`Open ${t.sections[section].label} menu`}
                type="button"
                className={isActive ? styles.navTriggerActive : undefined}
                aria-expanded={isActive}
                aria-controls={desktopPanelId}
                onClick={() => setActiveSection(isActive ? null : section)}
                onKeyDown={(event) => handleTriggerKeyDown(event, section)}
              >
                <i aria-hidden="true" />
              </button>
              </div>
            );
          })}
        </nav>

        <div className={styles.actions}>
          <a className={styles.accountLink} href="/account" onClick={closeNavigation}>{language === "zh" ? "账号" : "Account"}</a>
          {onLanguageChange && (
            <button
              type="button"
              className={styles.languageButton}
              aria-label={t.switchLanguage}
              onClick={() => onLanguageChange(language === "zh" ? "en" : "zh")}
            >
              <span>{language === "zh" ? "中" : "EN"}</span>
              <i aria-hidden="true" />
              {language === "zh" ? "EN" : "中"}
            </button>
          )}
          <a className={styles.enterButton} href={enterHref} onClick={closeNavigation}>
            <span>{t.enter}</span>
            <DirectionArrow />
          </a>
          <button
            ref={mobileButtonRef}
            type="button"
            className={`${styles.mobileToggle} ${mobileOpen ? styles.mobileToggleOpen : ""}`}
            aria-label={mobileOpen ? t.closeMenu : t.openMenu}
            aria-expanded={mobileOpen}
            aria-controls={`${instanceId}-mobile-navigation`}
            onClick={() => {
              setActiveSection(null);
              setMobileOpen((open) => !open);
            }}
          >
            <i aria-hidden="true" />
            <i aria-hidden="true" />
          </button>
        </div>
      </div>

      {activeSection && (
        <div
          ref={panelRef}
          id={desktopPanelId}
          className={styles.megaPanel}
          role="region"
          aria-labelledby={`${instanceId}-${activeSection}-trigger`}
        >
          <div className={styles.panelGrid}>
            <div className={styles.panelIntro}>
              <span className={styles.kicker}>{t.sections[activeSection].kicker}</span>
              <h2>{t.sections[activeSection].title}</h2>
              <p>{t.sections[activeSection].description}</p>
              <div className={styles.panelCoordinates} aria-hidden="true">
                <span>SOURCE / TIME</span>
                <i />
                <span>EVIDENCE / REVIEW</span>
              </div>
            </div>

            <a
              className={styles.featureCard}
              href={t.sections[activeSection].feature.href}
              onClick={closeNavigation}
            >
              <div className={styles.featureSignal} aria-hidden="true">
                <i /><i /><i /><i />
              </div>
              <span className={styles.cardNumber}>{t.sections[activeSection].feature.number}</span>
              <div>
                <h3>{t.sections[activeSection].feature.title}</h3>
                <p>{t.sections[activeSection].feature.description}</p>
              </div>
              <footer>
                <small>{t.sections[activeSection].feature.meta}</small>
                <DirectionArrow />
              </footer>
            </a>

            <div className={styles.panelLinks}>
              {t.sections[activeSection].items.map((item) => (
                <a key={`${activeSection}-${item.number}`} href={item.href} onClick={closeNavigation}>
                  <span className={styles.cardNumber}>{item.number}</span>
                  <div>
                    <h3>{item.title}</h3>
                    <p>{item.description}</p>
                    <small>{item.meta}</small>
                  </div>
                  <DirectionArrow />
                </a>
              ))}
            </div>
          </div>
        </div>
      )}

      {mobileOpen && (
        <nav
          id={`${instanceId}-mobile-navigation`}
          className={styles.mobileDrawer}
          aria-label={t.navigationLabel}
        >
          <div className={styles.mobileScroll}>
            <div className={styles.mobileLead}>
              <span>INSOLVE TECH / ORAKT</span>
              <p>{language === "zh" ? "全球因果与市场情报系统" : "Global causal and market intelligence"}</p>
            </div>

            <div className={styles.mobileSections}>
              {sectionOrder.map((section) => {
                const isExpanded = mobileSection === section;
                const triggerId = `${instanceId}-${section}-mobile-trigger`;
                const regionId = `${instanceId}-${section}-mobile-region`;
                return (
                  <section key={section} className={styles.mobileSection}>
                    <h2>
                      <a href={sectionHref[section]} onClick={closeNavigation}>{t.sections[section].label}</a>
                      <button
                        id={triggerId}
                aria-label={language==="zh"?`展开${t.sections[section].label}导航`:`Open ${t.sections[section].label} menu`}
                        type="button"
                        aria-expanded={isExpanded}
                        aria-controls={regionId}
                        onClick={() => setMobileSection(isExpanded ? null : section)}
                      >
                        <i aria-hidden="true" />
                      </button>
                    </h2>
                    {isExpanded && (
                      <div id={regionId} className={styles.mobileRegion} role="region" aria-labelledby={triggerId}>
                        <p>{t.sections[section].description}</p>
                        <a
                          className={styles.mobileFeature}
                          href={t.sections[section].feature.href}
                          onClick={closeNavigation}
                        >
                          <small>{t.sections[section].feature.number}</small>
                          <strong>{t.sections[section].feature.title}</strong>
                          <span>{t.explore}<DirectionArrow /></span>
                        </a>
                        <div className={styles.mobileLinks}>
                          {t.sections[section].items.map((item) => (
                            <a key={`${section}-mobile-${item.number}`} href={item.href} onClick={closeNavigation}>
                              <small>{item.number}</small>
                              <span>
                                <strong>{item.title}</strong>
                                <em>{item.meta}</em>
                              </span>
                              <DirectionArrow />
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                  </section>
                );
              })}
            </div>

            <a className={styles.mobileEnter} href={enterHref} onClick={closeNavigation}>
              <span>
                <strong>{t.enter}</strong>
                <small>{t.enterNote}</small>
              </span>
              <DirectionArrow />
            </a>
          </div>
        </nav>
      )}
    </header>
  );
}
