export const marketingPages = {
  lab: {path:"/lab", kicker:"ORAKT LAB", zh:"因子挖掘与验证", en:"Factor discovery & validation", description:"理解 ORAKT 如何通过样本外回测、成本与未来验证研究候选因子。"},
  company: {path:"/company", kicker:"INSOLVE TECH", zh:"关于我们", en:"About us", description:"了解 INSOLVE TECH 与 ORAKT 的研究原则：来源、时间、证据与复核。"},
  research: {path:"/research", kicker:"RESEARCH ENGINE", zh:"研究方法", en:"Research methodology", description:"从原始来源到证据链，了解 ORAKT 的研究流程与报告查验方式。"},
  roadmap: {path:"/roadmap", kicker:"PRODUCT DIRECTION", zh:"未来方向", en:"Our direction", description:"了解 ORAKT 在数据覆盖、协作研究和区域化服务上的未来方向。"},
  membership: {path:"/membership", kicker:"IDENTITY & ACCESS", zh:"账号与访问", en:"Identity & access", description:"通过 ChatGPT、Google、Phantom 或 ORAKT 账号访问地图与授权研究报告。"},
  plans: {path:"/plans", kicker:"ORAKT PLANS", zh:"套餐方案", en:"Plans", description:"查看 ORAKT 套餐与功能范围。Signal / Research 支持 Solana USDC、USDT 按月付款，不自动续费。"},
} as const;
export type MarketingPageKey = keyof typeof marketingPages;
export const legacyMarketingPaths:Record<string,string> = {"#lab":"/lab","#company":"/company","#direction":"/roadmap","#plans":"/plans","#access":"/membership"};
