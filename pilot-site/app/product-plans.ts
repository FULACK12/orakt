export type ProductPlanKey = "explorer" | "signal" | "research" | "team";

export type ProductPlan = {
  key: ProductPlanKey;
  name: string;
  price: string;
  accent: "lime" | "cyan" | "violet" | "white";
  returnTo: string;
  featuresZh: readonly string[];
  featuresEn: readonly string[];
};

export const productPlans: readonly ProductPlan[] = [
  {
    key: "explorer",
    name: "EXPLORER",
    price: "0",
    accent: "lime",
    returnTo: "/platform",
    featuresZh: ["全球事件地图", "公开数据图层", "报告目录预览"],
    featuresEn: ["Global event map", "Public data layers", "Report catalog preview"],
  },
  {
    key: "signal",
    name: "SIGNAL",
    price: "19",
    accent: "cyan",
    returnTo: "/platform/research",
    featuresZh: ["完整报告库", "公司与时间筛选", "证据链与来源核验"],
    featuresEn: ["Full report library", "Company and time filters", "Evidence-chain audit"],
  },
  {
    key: "research",
    name: "RESEARCH",
    price: "79",
    accent: "violet",
    returnTo: "/platform/data",
    featuresZh: ["已发布因子与回测状态", "供应链与竞争比较", "已发布研究查验 · 只读"],
    featuresEn: ["Published factor and backtest status", "Supply-chain comparisons", "Read-only published research"],
  },
  {
    key: "team",
    name: "TEAM",
    price: "299",
    accent: "white",
    returnTo: "/platform/research",
    featuresZh: ["团队研究空间 · 规划", "协作审核流程 · 规划", "定制数据接入 · 规划"],
    featuresEn: ["Team research spaces · Planned", "Collaborative review · Planned", "Custom data connections · Planned"],
  },
] as const;

export function accessHref(returnTo: string, plan: ProductPlanKey = "explorer") {
  return `/access?plan=${plan}&return_to=${encodeURIComponent(returnTo)}`;
}
