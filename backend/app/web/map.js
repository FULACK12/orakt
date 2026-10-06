"use strict";

const i18n = window.NewsI18n;
i18n.register({
  zh: {
    "map.eyebrow": "LIVE EVENT LAYER · 本地数据",
    "map.title": "全球事件地图",
    "map.description": "同时查看正式入库事件和本地 AI 提取、尚未入库的候选事件。",
    "map.canonical": "正式事件",
    "map.candidates": "AI 候选",
    "map.visible": "当前显示",
    "map.candidateNoticeTitle": "候选层不会自动入库",
    "map.candidateNoticeBody": "它来自近期多个本地 AI 聚类批次，仅用于观察和复核。",
    "map.layer": "数据层",
    "map.layerAll": "全部事件",
    "map.layerCanonical": "仅正式事件",
    "map.layerCandidate": "仅 AI 候选",
    "map.source": "新闻来源",
    "map.sourceAll": "全部来源",
    "map.type": "事件类型",
    "map.typeAll": "全部类型",
    "map.eventIndicatorsNone": "事件指标：未选择",
    "map.eventIndicatorsSelected": "已选择事件指标",
    "map.eventIndicatorsHint": "默认不显示任何事件；只有勾选的指标会在地图、列表和时间轴中展开。",
    "map.conflictIndicator": "战争与政治暴力",
    "map.earthquakeIndicator": "地震",
    "map.eventList": "事件列表",
    "map.empty": "当前筛选条件下没有地图事件。",
    "map.loading": "正在装载全球事件坐标…",
    "map.independentCandidate": "独立候选",
    "map.reviewCandidate": "待复核候选",
    "map.job": "候选任务",
    "map.canonicalLabel": "正式事件",
    "map.candidateLabel": "AI 候选",
    "map.reviewLabel": "待复核候选",
    "map.sourceLink": "打开原文 ↗",
    "map.mapUnavailable": "地图组件未能加载。事件数据仍保留在左侧列表中。",
    "map.loadFailed": "地图数据读取失败",
    "map.economyKicker": "OFFICIAL MACRO DATA · 官方年度数据",
    "map.economicIndicator": "经济指标",
    "map.economicYear": "数据年份",
    "map.economyOff": "关闭经济图层",
    "map.economyPending": "等待官方经济数据首次同步。",
    "map.economyLoading": "正在读取经济数据…",
    "map.economyCoverage": "个国家/地区",
    "map.economyLegend": "国家经济指标",
    "map.countryReference": "国家级参考点（首都坐标）",
    "map.exactLocation": "精确事件坐标",
    "map.sourceAttribution": "来源",
    "map.timeWindow": "时间范围",
    "map.timeScopeStrict": "事件、战争和灾害严格按此区间过滤",
    "map.timeScopeAll": "本地保留的全部事件时间",
    "map.timeScopeSlow": "年度经济与基础设施层保留自己的观测年份",
    "map.timeWeek": "最近一周",
    "map.timeMonth": "最近一个月",
    "map.timeQuarter": "最近三个月",
    "map.timeAll": "全部时间",
    "map.play": "回放",
    "map.pause": "暂停",
    "map.timeline": "事件时间轴",
    "map.through": "显示截至",
    "map.conflictLegend": "冲突/战争事件",
    "map.geographyLevel": "当前层级",
    "map.levelCountry": "国家",
    "map.levelAdmin1": "省州",
    "map.levelCity": "城市",
    "map.closeCountry": "关闭国家面板",
    "map.countryPanelKicker": "COUNTRY PROFILE · 国家面板",
    "map.countryLoading": "正在读取国家数据…",
    "map.countryUnavailable": "暂无该国家的结构化数据。",
    "map.subnationalNext": "放大后的下一层",
    "map.subnationalNotice": "省州和城市会使用独立统计口径；不会把国家值平均分配到下级地区。",
    "map.conflictEvent": "冲突高关注事件",
    "map.regionPopulation": "人口",
    "map.regionReference": "省州参考中心（由城市点加权派生）",
    "map.cityReference": "城市/聚居地参考点",
    "map.cityEventReference": "城市归纳点（并非事件精确坐标）",
    "map.admin1EventReference": "省州归纳点（并非事件精确坐标）",
    "map.regionLoading": "正在读取地区数据…",
    "map.regionNoMetrics": "暂未接入该地区的独立统计指标",
    "map.zoomForRegions": "继续放大地图可查看省州和城市",
    "map.chainLegend": "事件链建议（未确认因果）",
    "map.chainSuggested": "时间/响应链建议，不代表已确认因果",
    "map.chainFixed": "已人工固定的证据/逻辑链（仍不自动等同因果）",
    "map.labelLanguage": "地图地名",
    "map.labelFollowInterface": "跟随界面",
    "map.labelNative": "当地/原始",
    "map.labelEnglish": "英文",
    "map.transportKicker": "GLOBAL TRANSPORT · 航空与海运",
    "map.airports": "主要机场",
    "map.ports": "主要港口",
    "map.transportNotice": "点位等级表示地图重要性；国家运力使用官方年度旅客、货运、起降、TEU 与班轮连通度。",
    "map.hubRank": "地图重要性等级",
    "map.hubRankNotice": "此等级不是吞吐量；实际运力请查看国家面板。",
    "map.evidenceChains": "证据与逻辑链",
    "map.evidenceNotice": "机器先提出时间/响应关系；只有人工接受并固定后才进入固定链。",
    "map.fixedCount": "条已固定",
    "map.pinEvidence": "接受并固定",
    "map.fixedEvidence": "已固定",
    "map.evidenceDocuments": "证据文档",
    "map.marketKicker": "MAJOR MARKET INDICES · 主要交易指数",
    "map.marketCredential": "已加入指数定义；配置 Twelve Data API 密钥后显示行情。",
    "map.marketProviderError": "行情提供方暂时无法返回有效数据。",
    "map.marketPartial": "部分指数受套餐或交易所授权限制，已显示可用行情。",
    "map.marketDelay": "行情时效取决于套餐与交易所授权。",
    "map.noMarketIndex": "该国家暂未配置主要交易指数。",
    "map.integrationStatus": "数据访问凭证",
    "map.integrationNotice": "凭证只从本机环境变量读取，页面不会显示令牌值。",
    "map.integrationReady": "已配置",
    "map.integrationRequired": "待配置",
    "map.laneConflict": "冲突安全",
    "map.laneEconomy": "经济市场",
    "map.lanePolitics": "政治外交",
    "map.laneDisaster": "灾害气候",
    "map.laneOther": "社会其他",
    "map.earthquakeSeries": "地震序列",
    "map.waves": "波次",
    "map.strongestWave": "地图显示本序列中震级最高的一次",
    "map.logicHypotheses": "AI 多步逻辑假设",
    "map.logicNotice": "主模型生成假设后，独立验证器会核对事件、时间、机制、市场预期、替代解释和因果充分性。",
    "map.generateLogic": "生成并验证",
    "map.generatingLogic": "本地 AI 生成与验证中…",
    "map.validateLogic": "重新验证",
    "map.validatingLogic": "正在刷新证据并验证…",
    "map.trainingSignals": "条人工训练信号",
    "map.acceptLogic": "接受",
    "map.reviseAcceptLogic": "修改后接受",
    "map.deferLogic": "暂缓",
    "map.rejectLogic": "驳回",
    "map.correctionPlaceholder": "给 AI 的修正建议（将保留为训练参数）",
    "map.reportedEvent": "已报道事件",
    "map.inferredMechanism": "AI 推断机制",
    "map.possibleOutcome": "可能结果",
    "map.economicContext": "经济数据背景",
    "map.marketObservation": "市场观测",
    "map.observationOutsideWindow": "观测不在所选区间内",
    "map.counterevidence": "反证 / 其他原因",
    "map.compositeScore": "综合指标",
    "map.associationScore": "关联度",
    "map.evidenceCoverage": "证据覆盖",
    "map.relevance": "相关度",
    "map.statusSuggested": "待审核",
    "map.statusAccepted": "已接受",
    "map.statusRevisedAccepted": "修改后接受",
    "map.statusDeferred": "暂缓",
    "map.statusRejected": "已驳回",
    "map.causalValidator": "因果验证 Agent",
    "map.recalculatedConfidence": "验证后置信度",
    "map.validationWindow": "时间窗口",
    "map.hours": "小时",
    "map.missingEvidence": "仍缺少的证据",
    "map.noMissingEvidence": "六个验证门未发现结构性证据缺口",
    "map.causalTemporal": "仅时间相关",
    "map.causalPartial": "机制部分支持",
    "map.causalSupported": "机制获支持（非因果证实）",
    "map.checkPremise": "前提事件确有报道",
    "map.checkTiming": "结果与时间窗口",
    "map.checkMechanism": "中间机制证据",
    "map.checkExpectations": "市场是否提前预期",
    "map.checkAlternatives": "更强替代解释",
    "map.checkSufficiency": "因果充分性",
    "map.checkPassed": "通过",
    "map.checkPartial": "部分支持",
    "map.checkMissing": "证据缺失",
    "map.checkFailed": "未通过",
    "map.checkNA": "不适用",
    "map.validationSources": "本次验证数据源",
    "map.sourceReady": "可用",
    "map.sourcePartial": "部分可用",
    "map.sourceUnavailable": "本次无数据",
    "map.sourceNotConfigured": "未配置",
    "map.observations": "条观测",
    "map.evidenceFacts": "结构化证据明细",
    "map.actuallyCitedEvidence": "本次实际引用的数据项",
    "map.usedByChecks": "用于验证门",
    "map.contextNotCited": "仅作背景，本次评分未引用",
    "map.confidenceBreakdown": "置信度组成与上限",
    "map.originalConfidence": "主模型原始",
    "map.weightedGateScore": "验证门加权",
    "map.conclusionCap": "结论安全上限",
    "map.weight": "权重",
    "map.limitingFactor": "最终限制因素",
    "map.limitOriginal": "主模型原始置信度",
    "map.limitGates": "六项验证门加权得分",
    "map.limitConclusion": "当前结论的安全上限",
    "map.limitValidator": "独立验证 Agent 给出的上限",
    "map.causalFlow": "事件 → 机制 → 传导 → 结果",
    "map.reasoningTrace": "可审计验证记录",
    "map.validationSummary": "基于本次结果的结论",
    "map.nextDataSuggestions": "建议下一步补充的数据",
    "map.historicalCases": "历史人工审核案例 / 迭代对比",
    "map.reviewerRecommendation": "审核建议",
    "map.analysisWorkspace": "国家、排名与证据链",
    "map.analysisWorkspaceNotice": "点击国家查看世界排名；AI 假设与人工批复固定在本栏。",
    "map.openResearch": "打开 AI 研究报告",
    "map.openResearchHint": "论文式报告 · 预测走查 · 人工审核",
    "map.selectCountryHint": "点击地图上的国家进入省州层级，并查看该国指标与排名。",
    "map.rankingKicker": "GLOBAL RANKING · 全球排名",
    "map.rankingWeights": "调整综合指数权重",
    "map.applyWeights": "重新计算排名",
    "map.compositeRank": "综合指数世界排名",
    "map.coverage": "数据覆盖",
    "map.topCountries": "综合指数前列国家",
    "map.conflictPrimary": "AI 推定主战场",
    "map.conflictSecondary": "AI 推定次要战场",
    "map.conflictReported": "具体冲突报道点",
    "map.conflictUnlocated": "冲突地点待核实",
    "map.reportedShift": "报道重心变化方向",
    "map.conflictCaution": "战场等级与方向依据报道密度和时间位置推断，不等同于已确认部队态势。",
    "map.conflictActors": "报道涉及方",
    "map.conflictActorsUnknown": "来源未提供结构化交战方",
    "map.conflictReports": "条冲突记录",
    "map.conflictSources": "个来源",
    "map.fatalitiesBest": "来源最佳死亡估计",
    "map.economicIndicators": "经济指标叠加",
    "map.economicSelected": "已选指标",
    "map.economicMultiHint": "最多同时显示 4 项；外圈与内圈分别代表不同指标。",
    "map.economicMax": "最多可同时选择 4 个经济指标。",
    "map.thematicKicker": "REGIONAL COLORING · 区域分布着色",
    "map.thematicEnabled": "开启区域着色",
    "map.thematicMode": "着色依据",
    "map.thematicOff": "关闭着色",
    "map.thematicConflict": "战争与冲突紧急度",
    "map.thematicEconomy": "首个经济指标分布",
    "map.thematicAffinity": "与所选国家的政治亲密度",
    "map.thematicConflictClear": "当前时间范围内未发现冲突报道",
    "map.thematicConflictMinor": "较低关注 / 小规模摩擦",
    "map.thematicConflictElevated": "较高关注冲突",
    "map.thematicConflictSevere": "严重冲突 / 主战场",
    "map.thematicAffinityClose": "共同联盟/组织联系较强",
    "map.thematicAffinityLimited": "联系有限或证据不足",
    "map.thematicAffinityRival": "存在战略竞争或直接冲突信号",
    "map.thematicConflictCaution": "冲突颜色只覆盖有坐标证据的局部战区；未着色地区不等于绝对安全。",
    "map.thematicEconomyCaution": "颜色表示所选指标的相对分布，不自动代表好坏；首个已选指标用于国家填色。",
    "map.thematicAffinityCaution": "亲密度是基于联盟和国际组织共同成员关系的透明规则估计，不代表官方外交定性。",
    "map.thematicSelectCountry": "请先点击一个国家，再显示相对政治亲密度。",
    "map.boundarySource": "省州轮廓：geoBoundaries gbOpen（开放许可）",
    "map.newsFocusUnavailable": "该报道只有未核实的概略位置，未按精确点放大。",
  },
  en: {
    "map.eyebrow": "LIVE EVENT LAYER · LOCAL DATA",
    "map.title": "Global event map",
    "map.description": "Explore persisted events alongside local-AI candidates that have not been published.",
    "map.canonical": "Canonical",
    "map.candidates": "AI candidates",
    "map.visible": "Visible",
    "map.candidateNoticeTitle": "Candidates are never auto-published",
    "map.candidateNoticeBody": "They come from several recent local-AI clustering batches and remain for observation and review.",
    "map.layer": "Data layer",
    "map.layerAll": "All events",
    "map.layerCanonical": "Canonical only",
    "map.layerCandidate": "AI candidates only",
    "map.source": "News source",
    "map.sourceAll": "All sources",
    "map.type": "Event type",
    "map.typeAll": "All types",
    "map.eventIndicatorsNone": "Event indicators: none selected",
    "map.eventIndicatorsSelected": "Selected event indicators",
    "map.eventIndicatorsHint": "No event is shown by default. Only checked indicators expand on the map, list and timeline.",
    "map.conflictIndicator": "War and political violence",
    "map.earthquakeIndicator": "Earthquakes",
    "map.eventList": "Event list",
    "map.empty": "No mapped events match the current filters.",
    "map.loading": "Loading global event coordinates…",
    "map.independentCandidate": "Independent candidate",
    "map.reviewCandidate": "Review candidate",
    "map.job": "Candidate job",
    "map.canonicalLabel": "Canonical event",
    "map.candidateLabel": "AI candidate",
    "map.reviewLabel": "Review candidate",
    "map.sourceLink": "Open source ↗",
    "map.mapUnavailable": "The map component could not load. Event data remains available in the list.",
    "map.loadFailed": "Could not load map data",
    "map.economyKicker": "OFFICIAL MACRO DATA · ANNUAL SERIES",
    "map.economicIndicator": "Economic indicator",
    "map.economicYear": "Data year",
    "map.economyOff": "Turn economic layer off",
    "map.economyPending": "Waiting for the first official economic-data sync.",
    "map.economyLoading": "Loading economic data…",
    "map.economyCoverage": "countries/economies",
    "map.economyLegend": "Country economic indicator",
    "map.countryReference": "Country reference point (capital coordinate)",
    "map.exactLocation": "Exact event coordinate",
    "map.sourceAttribution": "Source",
    "map.timeWindow": "Time range",
    "map.timeScopeStrict": "Events, conflicts and disasters are strictly filtered to this range",
    "map.timeScopeAll": "All locally retained event time",
    "map.timeScopeSlow": "Annual economy and infrastructure layers retain their own observation periods",
    "map.timeWeek": "Last 7 days",
    "map.timeMonth": "Last month",
    "map.timeQuarter": "Last 3 months",
    "map.timeAll": "All time",
    "map.play": "Replay",
    "map.pause": "Pause",
    "map.timeline": "Event timeline",
    "map.through": "Showing through",
    "map.conflictLegend": "Conflict / war event",
    "map.geographyLevel": "Current level",
    "map.levelCountry": "Country",
    "map.levelAdmin1": "Province/state",
    "map.levelCity": "City",
    "map.closeCountry": "Close country panel",
    "map.countryPanelKicker": "COUNTRY PROFILE · OFFICIAL VALUES",
    "map.countryLoading": "Loading country data…",
    "map.countryUnavailable": "No structured data is available for this country.",
    "map.subnationalNext": "Next level when zoomed in",
    "map.subnationalNotice": "Province/state and city values use their own statistical definitions; national values are never divided across lower levels.",
    "map.conflictEvent": "High-attention conflict event",
    "map.regionPopulation": "Population",
    "map.regionReference": "Province/state reference center (derived from city points)",
    "map.cityReference": "City / populated-place reference point",
    "map.cityEventReference": "City aggregation point (not an exact event coordinate)",
    "map.admin1EventReference": "Province/state aggregation point (not an exact event coordinate)",
    "map.regionLoading": "Loading regional data…",
    "map.regionNoMetrics": "No independently sourced regional metrics are available yet",
    "map.zoomForRegions": "Zoom in to reveal provinces/states and cities",
    "map.chainLegend": "Event-chain suggestion (causality unconfirmed)",
    "map.chainSuggested": "Time/response sequence suggestion; causality is not confirmed",
    "map.chainFixed": "Human-fixed evidence/logic link (still not automatic proof of causality)",
    "map.labelLanguage": "Map labels",
    "map.labelFollowInterface": "Follow interface",
    "map.labelNative": "Local/native",
    "map.labelEnglish": "English",
    "map.transportKicker": "GLOBAL TRANSPORT · AIR AND SEA",
    "map.airports": "Major airports",
    "map.ports": "Major ports",
    "map.transportNotice": "Point rank is cartographic importance; country capacity uses official passenger, freight, departure, TEU and connectivity series.",
    "map.hubRank": "Cartographic importance rank",
    "map.hubRankNotice": "This rank is not throughput; open the country panel for capacity indicators.",
    "map.evidenceChains": "Evidence and logic chains",
    "map.evidenceNotice": "The machine proposes time/response links; only human-accepted links can be fixed.",
    "map.fixedCount": "fixed",
    "map.pinEvidence": "Accept and fix",
    "map.fixedEvidence": "Fixed",
    "map.evidenceDocuments": "Evidence documents",
    "map.marketKicker": "MAJOR MARKET INDICES",
    "map.marketCredential": "Index definitions are ready; configure a Twelve Data API key to show quotes.",
    "map.marketProviderError": "The quote provider did not return valid data.",
    "map.marketPartial": "Some indices are unavailable under the current plan or exchange licence; available quotes are shown.",
    "map.marketDelay": "Quote freshness depends on the plan and exchange licence.",
    "map.noMarketIndex": "No major index is configured for this country.",
    "map.integrationStatus": "Data access credentials",
    "map.integrationNotice": "Credentials are read only from local environment variables; token values are never shown.",
    "map.integrationReady": "Ready",
    "map.integrationRequired": "Required",
    "map.laneConflict": "Conflict",
    "map.laneEconomy": "Economy",
    "map.lanePolitics": "Politics",
    "map.laneDisaster": "Disaster",
    "map.laneOther": "Other",
    "map.earthquakeSeries": "Earthquake sequence",
    "map.waves": "waves",
    "map.strongestWave": "The map shows the strongest wave in this sequence",
    "map.logicHypotheses": "AI multi-step logic hypotheses",
    "map.logicNotice": "After generation, a separate validator checks events, timing, mechanisms, expectations, alternatives and causal sufficiency.",
    "map.generateLogic": "Generate & validate",
    "map.generatingLogic": "Local AI is generating and validating…",
    "map.validateLogic": "Revalidate",
    "map.validatingLogic": "Refreshing evidence and validating…",
    "map.trainingSignals": "human training signals",
    "map.acceptLogic": "Accept",
    "map.reviseAcceptLogic": "Revise & accept",
    "map.deferLogic": "Defer",
    "map.rejectLogic": "Reject",
    "map.correctionPlaceholder": "Correction for the AI (retained as a training parameter)",
    "map.reportedEvent": "Reported event",
    "map.inferredMechanism": "AI-inferred mechanism",
    "map.possibleOutcome": "Possible outcome",
    "map.economicContext": "Economic context",
    "map.marketObservation": "Market observation",
    "map.observationOutsideWindow": "Observation falls outside the selected range",
    "map.counterevidence": "Counterevidence / alternatives",
    "map.compositeScore": "Composite",
    "map.associationScore": "Association",
    "map.evidenceCoverage": "Evidence coverage",
    "map.relevance": "Relevance",
    "map.statusSuggested": "Suggested",
    "map.statusAccepted": "Accepted",
    "map.statusRevisedAccepted": "Revised & accepted",
    "map.statusDeferred": "Deferred",
    "map.statusRejected": "Rejected",
    "map.causalValidator": "Causal-validation agent",
    "map.recalculatedConfidence": "Validated confidence",
    "map.validationWindow": "Time window",
    "map.hours": "hours",
    "map.missingEvidence": "Evidence still missing",
    "map.noMissingEvidence": "No structural evidence gap found across the six gates",
    "map.causalTemporal": "Temporal correlation only",
    "map.causalPartial": "Mechanism partly supported",
    "map.causalSupported": "Mechanism supported (not causal proof)",
    "map.checkPremise": "Premise was reported",
    "map.checkTiming": "Outcome and time window",
    "map.checkMechanism": "Intermediate mechanism evidence",
    "map.checkExpectations": "Pre-decision market expectations",
    "map.checkAlternatives": "Stronger alternative explanations",
    "map.checkSufficiency": "Causal sufficiency",
    "map.checkPassed": "Passed",
    "map.checkPartial": "Partial",
    "map.checkMissing": "Missing evidence",
    "map.checkFailed": "Failed",
    "map.checkNA": "Not applicable",
    "map.validationSources": "Evidence sources for this validation",
    "map.sourceReady": "Ready",
    "map.sourcePartial": "Partial",
    "map.sourceUnavailable": "No data for window",
    "map.sourceNotConfigured": "Not configured",
    "map.observations": "observations",
    "map.evidenceFacts": "Structured evidence facts",
    "map.actuallyCitedEvidence": "Actually cited data items",
    "map.usedByChecks": "Used by gates",
    "map.contextNotCited": "Context only; not used in this score",
    "map.confidenceBreakdown": "Confidence composition and caps",
    "map.originalConfidence": "Main-model prior",
    "map.weightedGateScore": "Weighted gates",
    "map.conclusionCap": "Conclusion cap",
    "map.weight": "weight",
    "map.limitingFactor": "Final limiting factor",
    "map.limitOriginal": "Main-model original confidence",
    "map.limitGates": "Weighted score across six validation gates",
    "map.limitConclusion": "Safety cap for the current conclusion",
    "map.limitValidator": "Independent validator cap",
    "map.causalFlow": "Event → mechanism → transmission → outcome",
    "map.reasoningTrace": "Auditable validation trace",
    "map.validationSummary": "Conclusion based on this validation",
    "map.nextDataSuggestions": "Recommended next evidence",
    "map.historicalCases": "Comparable cases / prior review iterations",
    "map.reviewerRecommendation": "Reviewer recommendation",
    "map.analysisWorkspace": "Country, rankings and evidence",
    "map.analysisWorkspaceNotice": "Select a country for world ranks; AI hypotheses and human review stay in this pane.",
    "map.openResearch": "Open AI research reports",
    "map.openResearchHint": "Paper reports · forecast walk-forward · human review",
    "map.selectCountryHint": "Select a country to enter the province/state level and inspect its indicators and ranks.",
    "map.rankingKicker": "GLOBAL RANKING",
    "map.rankingWeights": "Adjust composite weights",
    "map.applyWeights": "Recalculate ranking",
    "map.compositeRank": "Composite world rank",
    "map.coverage": "Data coverage",
    "map.topCountries": "Leading composite countries",
    "map.conflictPrimary": "AI-estimated primary theater",
    "map.conflictSecondary": "AI-estimated secondary theater",
    "map.conflictReported": "Reported conflict site",
    "map.conflictUnlocated": "Conflict location unverified",
    "map.reportedShift": "Reported-location shift",
    "map.conflictCaution": "Theater tier and direction are inferred from report density, time and location; they are not confirmed troop positions.",
    "map.conflictActors": "Reported parties",
    "map.conflictActorsUnknown": "No structured conflict party in the source",
    "map.conflictReports": "conflict records",
    "map.conflictSources": "sources",
    "map.fatalitiesBest": "source best fatality estimate",
    "map.economicIndicators": "Economic overlays",
    "map.economicSelected": "Selected indicators",
    "map.economicMultiHint": "Show up to four series together; outer and inner rings represent different indicators.",
    "map.economicMax": "Up to four economic indicators can be selected.",
    "map.thematicKicker": "REGIONAL COLORING",
    "map.thematicEnabled": "Enable regional coloring",
    "map.thematicMode": "Color by",
    "map.thematicOff": "Coloring off",
    "map.thematicConflict": "War and conflict urgency",
    "map.thematicEconomy": "First economic indicator distribution",
    "map.thematicAffinity": "Political proximity to selected country",
    "map.thematicConflictClear": "No conflict report detected in the current time window",
    "map.thematicConflictMinor": "Lower attention / limited friction",
    "map.thematicConflictElevated": "Elevated conflict attention",
    "map.thematicConflictSevere": "Severe conflict / primary theater",
    "map.thematicAffinityClose": "Stronger shared alliance or organization links",
    "map.thematicAffinityLimited": "Limited links or insufficient evidence",
    "map.thematicAffinityRival": "Strategic competition or direct-conflict signal",
    "map.thematicConflictCaution": "Conflict colors cover only local footprints with coordinate evidence; an uncolored area is not guaranteed safe.",
    "map.thematicEconomyCaution": "Colors show relative distribution, not automatically good or bad. The first selected indicator colors countries.",
    "map.thematicAffinityCaution": "Proximity is a transparent rule-based estimate from shared alliances and international organizations, not an official diplomatic classification.",
    "map.thematicSelectCountry": "Select a country before displaying relative political proximity.",
    "map.boundarySource": "Province/state boundaries: geoBoundaries gbOpen (openly licensed)",
    "map.newsFocusUnavailable": "This report only has an unverified approximate location, so the map was not zoomed as if it were an exact site.",
  },
});

i18n.register({
  zh: {
    "map.researchWorkspace": "本地 AI 研究、证据链与二次复核",
    "map.researchWorkspaceNotice": "本地模型先提出可证伪假设并检索本机证据；ChatGPT 复核是可选的第二意见。",
    "map.workspaceTabResearch": "AI 研究",
    "map.workspaceTabEvidence": "证据与逻辑链",
    "map.workspaceTabData": "数据与模型",
    "map.modelRoutingTitle": "本地 AI 与 ChatGPT 的分工",
    "map.modelRoutingNotice": "本地 AI 选择有限事件窗口、检索证据并形成初稿；配置 OpenAI 后自动复核方向与证据，本地 AI 必须按反馈修订。",
    "map.modelRoutingLocal": "默认研究",
    "map.modelRoutingLocalValue": "本地 AI",
    "map.modelRoutingReview": "二次复核",
    "map.modelRoutingReviewValue": "OpenAI Responses API",
    "map.modelRoutingPrivacy": "密钥与原始数据",
    "map.modelRoutingPrivacyValue": "仅由本机后端读取",
    "map.researchQuestion": "研究问题",
    "map.researchQuestionPlaceholder": "例如：科技股是否还会涨？哪些电力、芯片、矿产、政策或地缘风险可能改变结论？",
    "map.researchSubmit": "本地 AI 开始研究",
    "map.researchAutonomous": "让 AI 自主提出问题",
    "map.researchIdle": "等待研究问题。",
    "map.researchEmpty": "暂无研究结果。可以输入问题，或让本地 AI 从近期证据中自主提出问题。",
    "map.researchRunning": "本地 AI 正在检索证据并拆解问题…",
    "map.researchAutonomousRunning": "本地 AI 正在选择一个可证伪问题并查找证据…",
    "map.researchCompleted": "研究闭环已完成；可查看事件窗口、复核意见、本地修订和最终确认。",
    "map.researchWorkflow": "研究闭环",
    "map.episodeWindow": "因果事件窗口",
    "map.historyContextOnly": "长期历史仅作基线",
    "map.localDraftStage": "本地初稿",
    "map.openaiAuditStage": "OpenAI 方向/证据复核",
    "map.localRevisionStage": "本地按反馈修订",
    "map.openaiConfirmationStage": "OpenAI 最终确认",
    "map.researchFailed": "本地研究失败",
    "map.researchLoadFailed": "研究记录读取失败",
    "map.researchQuestionRequired": "请输入至少 6 个字符的研究问题。",
    "map.researchModeAutonomous": "AI 自主问题",
    "map.researchModeUser": "用户问题",
    "map.researchEvidenceGaps": "仍需补充的证据",
    "map.researchVerified": "已验证",
    "map.researchPartial": "部分支持",
    "map.researchMissing": "证据不足",
    "map.researchHypothesis": "待验证假设",
    "map.scopeCompanies": "公司",
    "map.scopeSectors": "行业",
    "map.scopeInputs": "资源/投入",
    "map.scopeInfrastructure": "基础设施",
    "map.scopeGeographies": "地理风险",
    "map.chatgptReview": "ChatGPT 二次复核",
    "map.chatgptReviewRunning": "ChatGPT 正在复核本地模型的证据与逻辑…",
    "map.chatgptReviewCompleted": "ChatGPT 第二意见已返回。",
    "map.chatgptReviewFailed": "ChatGPT 复核失败",
    "map.chatgptReviewed": "已完成 ChatGPT 复核",
    "map.chatgptKeyRequired": "需配置 OpenAI API Key",
    "map.chatgptSecondOpinion": "OpenAI 最终确认",
    "map.revisedSummary": "建议修订后的结论",
    "map.researchAccept": "建议接受",
    "map.researchReviseAccept": "建议修改后接受",
    "map.researchDefer": "建议暂缓等待证据",
    "map.researchReject": "建议驳回",
    "map.conflictLayerKicker": "CONFLICT INDICATOR · 战争与政治暴力",
    "map.showConflicts": "显示战争指标",
    "map.conflictLayerOff": "在下方勾选战争指标后，按所选时间范围加载省州级热点。",
    "map.conflictLayerLoading": "正在按当前视野聚合 ACLED 冲突热点…",
    "map.conflictLayerEmpty": "所选时间范围和当前视野内没有 ACLED 冲突聚合记录。",
    "map.conflictLayerFailed": "战争指标读取失败",
    "map.conflictHotspots": "个省州级热点",
    "map.conflictAggregateCaution": "颜色表示近期政治暴力记录的聚合紧急度，不代表整省控制权或已确认军队位置。",
    "map.thematicConflictClear": "当前 ACLED 聚合周期内没有已导入的省州级政治暴力记录",
    "map.thematicConflictCaution": "冲突颜色只覆盖有坐标证据的局部热点，并独立于新闻时间轴；未着色地区不等于绝对安全。",
  },
  en: {
    "map.researchWorkspace": "Local-AI research, evidence chains and second review",
    "map.researchWorkspaceNotice": "The local model proposes falsifiable hypotheses and searches local evidence first; ChatGPT is an optional second opinion.",
    "map.workspaceTabResearch": "AI Research",
    "map.workspaceTabEvidence": "Evidence & Logic",
    "map.workspaceTabData": "Data & Models",
    "map.modelRoutingTitle": "Local AI and ChatGPT responsibilities",
    "map.modelRoutingNotice": "Local AI selects a bounded episode, retrieves evidence and drafts the analysis. When OpenAI is configured it audits direction and evidence, and the local AI must revise from that feedback.",
    "map.modelRoutingLocal": "Default research",
    "map.modelRoutingLocalValue": "Local AI",
    "map.modelRoutingReview": "Second review",
    "map.modelRoutingReviewValue": "OpenAI Responses API",
    "map.modelRoutingPrivacy": "Key and raw data",
    "map.modelRoutingPrivacyValue": "Read only by the local backend",
    "map.researchQuestion": "Research question",
    "map.researchQuestionPlaceholder": "Example: Can technology stocks keep rising, and which power, chip, mineral, policy or geopolitical constraints could change the answer?",
    "map.researchSubmit": "Research with local AI",
    "map.researchAutonomous": "Let AI propose a question",
    "map.researchIdle": "Waiting for a research question.",
    "map.researchEmpty": "No research result yet. Enter a question or let the local AI propose one from recent evidence.",
    "map.researchRunning": "Local AI is retrieving evidence and decomposing the question…",
    "map.researchAutonomousRunning": "Local AI is selecting a falsifiable question and searching for evidence…",
    "map.researchCompleted": "The research loop is complete. Inspect the episode, audit, local revision and final confirmation.",
    "map.researchWorkflow": "Research loop",
    "map.episodeWindow": "Causal episode window",
    "map.historyContextOnly": "Long history is baseline context only",
    "map.localDraftStage": "Local draft",
    "map.openaiAuditStage": "OpenAI direction/evidence audit",
    "map.localRevisionStage": "Local feedback revision",
    "map.openaiConfirmationStage": "OpenAI final confirmation",
    "map.researchFailed": "Local research failed",
    "map.researchLoadFailed": "Could not load research history",
    "map.researchQuestionRequired": "Enter a research question of at least 6 characters.",
    "map.researchModeAutonomous": "AI-proposed question",
    "map.researchModeUser": "User question",
    "map.researchEvidenceGaps": "Evidence still needed",
    "map.researchVerified": "Verified",
    "map.researchPartial": "Partially supported",
    "map.researchMissing": "Evidence missing",
    "map.researchHypothesis": "Unverified hypothesis",
    "map.scopeCompanies": "Companies",
    "map.scopeSectors": "Sectors",
    "map.scopeInputs": "Resources/inputs",
    "map.scopeInfrastructure": "Infrastructure",
    "map.scopeGeographies": "Geospatial risk",
    "map.chatgptReview": "ChatGPT second review",
    "map.chatgptReviewRunning": "ChatGPT is auditing the local model's evidence and logic…",
    "map.chatgptReviewCompleted": "The ChatGPT second opinion is ready.",
    "map.chatgptReviewFailed": "ChatGPT review failed",
    "map.chatgptReviewed": "ChatGPT review complete",
    "map.chatgptKeyRequired": "OpenAI API key required",
    "map.chatgptSecondOpinion": "OpenAI final confirmation",
    "map.revisedSummary": "Suggested revised conclusion",
    "map.researchAccept": "Accept",
    "map.researchReviseAccept": "Revise and accept",
    "map.researchDefer": "Defer for evidence",
    "map.researchReject": "Reject",
    "map.conflictLayerKicker": "CONFLICT INDICATOR · POLITICAL VIOLENCE",
    "map.showConflicts": "Show conflict indicator",
    "map.conflictLayerOff": "Check the conflict indicator below to load province/state hotspots for the selected time range.",
    "map.conflictLayerLoading": "Aggregating ACLED conflict hotspots for the current view…",
    "map.conflictLayerEmpty": "No ACLED conflict aggregate is available in the selected time range and map view.",
    "map.conflictLayerFailed": "Could not load the conflict indicator",
    "map.conflictHotspots": "province/state hotspots",
    "map.conflictAggregateCaution": "Color is an aggregate of recent political-violence records, not a claim of province-wide control or confirmed troop positions.",
    "map.thematicConflictClear": "No imported province/state political-violence aggregate exists in the current ACLED period",
    "map.thematicConflictCaution": "Conflict color covers only geolocated local hotspots and remains independent from the news timeline; an uncolored area is not guaranteed safe.",
  },
});

const GEOBOUNDARIES_API_BASE =
  "https://www.geoboundaries.org/api/current/gbOpen";

const POLITICAL_AFFINITY_MODEL = {
  updatedAt: "2026-07-30",
  groups: [
    {
      id: "nato",
      weight: 0.48,
      members: [
        "AL", "BE", "BG", "CA", "HR", "CZ", "DK", "EE", "FI", "FR", "DE",
        "GR", "HU", "IS", "IT", "LV", "LT", "LU", "ME", "NL", "MK", "NO",
        "PL", "PT", "RO", "SK", "SI", "ES", "SE", "TR", "GB", "US",
      ],
    },
    {
      id: "eu",
      weight: 0.30,
      members: [
        "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE",
        "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT",
        "RO", "SK", "SI", "ES", "SE",
      ],
    },
    {
      id: "five-eyes",
      weight: 0.22,
      members: ["AU", "CA", "GB", "NZ", "US"],
    },
    {
      id: "aukus",
      weight: 0.18,
      members: ["AU", "GB", "US"],
    },
    {
      id: "quad",
      weight: 0.16,
      members: ["AU", "IN", "JP", "US"],
    },
    {
      id: "g7",
      weight: 0.12,
      members: ["CA", "FR", "DE", "IT", "JP", "GB", "US"],
    },
    {
      id: "brics",
      weight: 0.18,
      members: ["BR", "RU", "IN", "CN", "ZA", "EG", "ET", "ID", "IR", "AE"],
    },
    {
      id: "sco",
      weight: 0.20,
      members: ["BY", "CN", "IN", "IR", "KZ", "KG", "PK", "RU", "TJ", "UZ"],
    },
  ],
  rivalryPairs: [
    ["RU", "UA"],
    ["IR", "IL"],
    ["KP", "KR"],
    ["IN", "PK"],
    ["US", "RU"],
    ["US", "CN"],
  ],
};

const state = {
  data: null,
  map: null,
  baseTileLayer: null,
  layerGroup: null,
  economicLayerGroup: null,
  countryLayerGroup: null,
  countryLabelLayerGroup: null,
  administrativeBoundaryLayerGroup: null,
  administrativeLayerGroup: null,
  conflictZoneLayerGroup: null,
  conflictMovementLayerGroup: null,
  conflictRenderer: null,
  chainLayerGroup: null,
  transportLayerGroup: null,
  markerLayers: new Map(),
  countryCache: new Map(),
  marketCache: new Map(),
  countryBounds: new Map(),
  countryProperties: new Map(),
  countryFeatureLayer: null,
  admin1BoundarySources: new Map(),
  admin1BoundaryPromises: new Map(),
  admin1FeatureLayer: null,
  renderedAdmin1BoundaryCountry: null,
  areaCache: new Map(),
  administrativeCache: new Map(),
  renderedAdministrativeKey: null,
  selectedAreaDetail: null,
  visibleMarkers: [],
  eventChain: null,
  logicChain: null,
  hasInitialFit: false,
  selectedCountry: null,
  rankings: {
    cache: new Map(),
    weights: new Map(),
    year: new Date().getUTCFullYear(),
  },
  mapLabelMode: ["interface", "native", "english"].includes(
    localStorage.getItem("newsapp-map-label-mode"),
  )
    ? localStorage.getItem("newsapp-map-label-mode")
    : "interface",
  transport: {
    airports: null,
    ports: null,
    showAirports: false,
    showPorts: false,
  },
  conflicts: {
    enabled: false,
    loading: false,
    payload: null,
    controller: null,
    debounceTimer: null,
  },
  research: {
    inquiries: [],
    openaiConfigured: false,
  },
  integrations: [],
  filters: {
    window: "7d",
    layer: "all",
    source: "all",
    eventTypes: new Set(),
  },
  timeline: {
    times: [],
    index: null,
    timer: null,
  },
  economics: {
    indicators: [],
    dataByCode: new Map(),
    selectedCodes: [],
    year: null,
  },
  thematic: {
    enabled: false,
    mode: "conflict",
    conflictScores: new Map(),
    provinceConflictScores: new Map(),
  },
};

const elements = {
  canonicalCount: document.querySelector("#canonical-count"),
  candidateCount: document.querySelector("#candidate-count"),
  visibleCount: document.querySelector("#visible-count"),
  layerFilter: document.querySelector("#layer-filter"),
  sourceFilter: document.querySelector("#source-filter"),
  eventIndicatorOptions: document.querySelector("#event-indicator-options"),
  eventIndicatorSummary: document.querySelector("#event-indicator-summary"),
  timeWindow: document.querySelector("#time-window"),
  timeScopeStatus: document.querySelector("#time-scope-status"),
  eventList: document.querySelector("#event-list"),
  listEmpty: document.querySelector("#list-empty"),
  jobLabel: document.querySelector("#job-label"),
  loading: document.querySelector("#map-loading"),
  mapError: document.querySelector("#map-error"),
  economicIndicatorOptions: document.querySelector("#economic-indicator-options"),
  economicIndicatorSummary: document.querySelector("#economic-indicator-summary"),
  economicYear: document.querySelector("#economic-year"),
  economicStatus: document.querySelector("#economic-status"),
  thematicEnabled: document.querySelector("#thematic-enabled"),
  thematicMode: document.querySelector("#thematic-mode"),
  thematicLegend: document.querySelector("#thematic-legend"),
  conflictLayerStatus: document.querySelector("#conflict-layer-status"),
  timelinePlay: document.querySelector("#timeline-play"),
  timelineSlider: document.querySelector("#timeline-slider"),
  timelineDate: document.querySelector("#timeline-date"),
  geographyLevel: document.querySelector("#geography-level"),
  countryPanel: document.querySelector("#country-panel"),
  countryPanelClose: document.querySelector("#country-panel-close"),
  countryPanelName: document.querySelector("#country-panel-name"),
  countryPanelMeta: document.querySelector("#country-panel-meta"),
  countryPanelMetrics: document.querySelector("#country-panel-metrics"),
  countryMarketIndices: document.querySelector("#country-market-indices"),
  countryMarketStatus: document.querySelector("#country-market-status"),
  countryRankingSummary: document.querySelector("#country-ranking-summary"),
  countryRankingWeights: document.querySelector("#country-ranking-weights"),
  countryRankingList: document.querySelector("#country-ranking-list"),
  countryRankingStatus: document.querySelector("#country-ranking-status"),
  applyRankingWeights: document.querySelector("#apply-ranking-weights"),
  analysisPanel: document.querySelector("#analysis-panel"),
  countryPanelEmpty: document.querySelector("#country-panel-empty"),
  evidencePanel: document.querySelector(".evidence-panel"),
  mapLanguageMode: document.querySelector("#map-language-mode"),
  showAirports: document.querySelector("#show-airports"),
  showPorts: document.querySelector("#show-ports"),
  timelineLanes: document.querySelector("#timeline-lanes"),
  fixedChainCount: document.querySelector("#fixed-chain-count"),
  evidenceList: document.querySelector("#evidence-list"),
  logicChainList: document.querySelector("#logic-chain-list"),
  logicTrainingCount: document.querySelector("#logic-training-count"),
  generateLogic: document.querySelector("#generate-logic"),
  validateLogic: document.querySelector("#validate-logic"),
  integrationList: document.querySelector("#integration-list"),
  researchWorkspace: document.querySelector("#research-workspace"),
  workspaceTabs: [...document.querySelectorAll("[data-workspace-tab]")],
  workspacePanels: [...document.querySelectorAll("[data-workspace-panel]")],
  researchQuestion: document.querySelector("#research-question"),
  researchSubmit: document.querySelector("#research-submit"),
  researchAutonomous: document.querySelector("#research-autonomous"),
  researchStatus: document.querySelector("#research-status"),
  researchResults: document.querySelector("#research-results"),
};

document.addEventListener("DOMContentLoaded", initialize);
window.addEventListener("news:languagechange", () => {
  populateFilters();
  populateEconomicIndicators();
  populateEconomicYears();
  renderEconomicLayer();
  renderThematicLegend();
  applyCountryStyles();
  refreshMapLanguage();
  renderTransportLayer();
  renderTimelineLanes();
  if (state.selectedAreaDetail && !elements.countryPanel.hidden) {
    renderAreaPanel(state.selectedAreaDetail);
  } else {
    renderCountryPanelFromCache();
  }
  state.renderedAdministrativeKey = null;
  state.renderedAdmin1BoundaryCountry = null;
  void updateAdministrativeLayer();
  updateGeographyLevel();
  updateTimelineLabel();
  updateTimeScopeStatus();
  render();
});

async function initialize() {
  mountAnalysisWorkspace();
  bindFilters();
  initializeMap();
  try {
    state.data = await api("/map-data");
    elements.canonicalCount.textContent = state.data.canonical_count;
    elements.candidateCount.textContent = state.data.candidate_count;
    elements.jobLabel.textContent = state.data.latest_cluster_job_id
      ? `${i18n.t("map.job")} #${state.data.latest_cluster_job_id}`
      : "";
    populateFilters();
    refreshTimeline();
    render();
    await initializeEconomics();
    await Promise.all([
      initializeCountryBoundaries(),
      initializeTransportHubs(),
    ]);
    renderTransportLayer();
    render();
  } catch (error) {
    showMapError(`${i18n.t("map.loadFailed")}: ${error.message}`);
  } finally {
    elements.loading.hidden = true;
  }
}

function activateWorkspaceTab(requestedTab, persist = true) {
  const availableTabs = new Set(
    elements.workspaceTabs.map((tab) => tab.dataset.workspaceTab),
  );
  const activeTab = availableTabs.has(requestedTab) ? requestedTab : "research";
  elements.workspaceTabs.forEach((tab) => {
    const selected = tab.dataset.workspaceTab === activeTab;
    tab.classList.toggle("is-active", selected);
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
  });
  elements.workspacePanels.forEach((panel) => {
    const selected = panel.dataset.workspacePanel === activeTab;
    panel.classList.toggle("is-active", selected);
    panel.hidden = !selected;
  });
  if (persist) localStorage.setItem("newsapp-workspace-tab", activeTab);
  window.setTimeout(() => state.map?.invalidateSize(), 80);
}

function mountAnalysisWorkspace() {
  if (!elements.analysisPanel) return;
  if (elements.countryPanel) {
    elements.analysisPanel.appendChild(elements.countryPanel);
  }
}

async function initializeIntegrations() {
  try {
    const payload = await api("/integrations/status");
    state.integrations = payload.integrations;
    state.research.openaiConfigured = Boolean(
      payload.integrations.find((item) => item.key === "openai_review")?.configured,
    );
    renderIntegrationStatus();
  } catch (error) {
    console.warn("integration status unavailable", error);
  }
}

function renderIntegrationStatus() {
  elements.integrationList.innerHTML = state.integrations.map((integration) => `
    <a class="integration-row" href="${escapeAttribute(integration.application_url)}"
      target="_blank" rel="noreferrer">
      <b>${escapeHtml(integration.name)}</b>
      <span class="${integration.configured ? "ready" : "required"}">
        ${escapeHtml(i18n.t(
          integration.configured
            ? "map.integrationReady"
            : "map.integrationRequired",
        ))}
      </span>
    </a>
  `).join("");
  renderResearchInquiries();
}

async function initializeResearch() {
  try {
    const payload = await api("/research/inquiries/summaries?page=1&page_size=1");
    state.research.inquiries = payload.inquiries.length
      ? [await api(`/research/inquiries/${payload.inquiries[0].id}/workspace`)]
      : [];
    renderResearchInquiries();
  } catch (error) {
    elements.researchStatus.textContent =
      `${i18n.t("map.researchLoadFailed")}: ${error.message}`;
  }
}

async function submitResearchQuestion() {
  const question = elements.researchQuestion.value.trim();
  if (question.length < 6) {
    elements.researchStatus.textContent = i18n.t("map.researchQuestionRequired");
    return;
  }
  await runResearchMutation(
    "/research/inquiries",
    { question },
    i18n.t("map.researchRunning"),
  );
}

async function runAutonomousResearch() {
  await runResearchMutation(
    "/research/autonomous",
    null,
    i18n.t("map.researchAutonomousRunning"),
  );
}

async function runResearchMutation(endpoint, body, pendingLabel) {
  elements.researchSubmit.disabled = true;
  elements.researchAutonomous.disabled = true;
  elements.researchStatus.textContent = pendingLabel;
  try {
    const inquiry = await apiMutation(endpoint, {
      method: "POST",
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    state.research.inquiries = [
      inquiry,
      ...state.research.inquiries.filter((item) => item.id !== inquiry.id),
    ].slice(0, 8);
    elements.researchStatus.textContent = i18n.t("map.researchCompleted");
    renderResearchInquiries();
  } catch (error) {
    elements.researchStatus.textContent =
      `${i18n.t("map.researchFailed")}: ${error.message}`;
  } finally {
    elements.researchSubmit.disabled = false;
    elements.researchAutonomous.disabled = false;
  }
}

async function requestChatGPTReview(inquiryId) {
  const button = elements.researchResults.querySelector(
    `[data-chatgpt-review="${inquiryId}"]`,
  );
  if (button) {
    button.disabled = true;
    button.textContent = i18n.t("map.chatgptReviewRunning");
  }
  elements.researchStatus.textContent = i18n.t("map.chatgptReviewRunning");
  try {
    const inquiry = await apiMutation(
      `/research/inquiries/${inquiryId}/chatgpt-review`,
      { method: "POST" },
    );
    state.research.inquiries = state.research.inquiries.map(
      (item) => item.id === inquiry.id ? inquiry : item,
    );
    elements.researchStatus.textContent = i18n.t("map.chatgptReviewCompleted");
    renderResearchInquiries();
  } catch (error) {
    elements.researchStatus.textContent =
      `${i18n.t("map.chatgptReviewFailed")}: ${error.message}`;
    if (button) button.disabled = false;
  }
}

function renderResearchInquiries() {
  if (!elements.researchResults) return;
  if (!state.research.inquiries.length) {
    elements.researchResults.innerHTML = `
      <div class="research-empty">${escapeHtml(i18n.t("map.researchEmpty"))}</div>
    `;
    return;
  }
  elements.researchResults.innerHTML = state.research.inquiries.map((inquiry) => {
    const result = inquiry.result;
    if (!result) {
      return `
        <article class="research-card is-${escapeHtml(inquiry.status)}">
          <h3>${escapeHtml(inquiry.question)}</h3>
          <p>${escapeHtml(inquiry.error || inquiry.status)}</p>
        </article>
      `;
    }
    return `
      <article class="research-card">
        <header>
          <div>
            <span>${escapeHtml(
              inquiry.mode === "autonomous"
                ? i18n.t("map.researchModeAutonomous")
                : i18n.t("map.researchModeUser"),
            )}</span>
            <h3>${escapeHtml(result.question)}</h3>
          </div>
          <small>${escapeHtml(inquiry.local_model)}</small>
        </header>
        ${renderMapResearchWorkflow(inquiry.evidence_snapshot?.research_workflow)}
        <p class="research-summary">${escapeHtml(result.summary)}</p>
        <div class="research-hypotheses">
          ${result.hypotheses.map((hypothesis) => `
            <section class="research-hypothesis">
              <div class="research-hypothesis-heading">
                <h4>${escapeHtml(hypothesis.title)}</h4>
                <strong>${Math.round(hypothesis.confidence * 100)}%</strong>
              </div>
              <div class="research-scope">
                ${renderResearchScope(hypothesis.scope)}
              </div>
              <ol>
                ${hypothesis.steps.map((step) => `
                  <li class="is-${escapeHtml(step.status)}">
                    <i>${step.sequence}</i>
                    <span>
                      <b>${escapeHtml(step.label)}</b>
                      <small>${escapeHtml(researchStepStatusLabel(step.status))}
                        · ${Math.round(step.confidence * 100)}%${
                          step.evidence_refs.length
                            ? ` · ${escapeHtml(step.evidence_refs.join(" · "))}`
                            : ""
                        }</small>
                    </span>
                  </li>
                `).join("")}
              </ol>
              ${hypothesis.evidence_gaps.length ? `
                <details>
                  <summary>${escapeHtml(i18n.t("map.researchEvidenceGaps"))}</summary>
                  <ul>${hypothesis.evidence_gaps.map(
                    (gap) => `<li>${escapeHtml(gap)}</li>`,
                  ).join("")}</ul>
                </details>
              ` : ""}
            </section>
          `).join("")}
        </div>
        ${renderChatGPTResearchReview(inquiry.chatgpt_review)}
        <footer>
          <span>${formatDate(inquiry.created_at)}</span>
          <button type="button" data-chatgpt-review="${inquiry.id}"
            ${!state.research.openaiConfigured || inquiry.chatgpt_review
              ? "disabled"
              : ""}>
            ${escapeHtml(
              inquiry.chatgpt_review
                ? i18n.t("map.chatgptReviewed")
                : state.research.openaiConfigured
                  ? i18n.t("map.chatgptReview")
                  : i18n.t("map.chatgptKeyRequired"),
            )}
          </button>
        </footer>
      </article>
    `;
  }).join("");
}

function renderMapResearchWorkflow(workflow) {
  if (!workflow) return "";
  const episode = workflow.episode_window;
  const labels = {
    local_draft: "map.localDraftStage",
    openai_review: "map.openaiAuditStage",
    local_revision: "map.localRevisionStage",
    openai_confirmation: "map.openaiConfirmationStage",
  };
  return `
    <section class="research-workflow is-${escapeHtml(workflow.status || "unknown")}">
      <header><b>${escapeHtml(i18n.t("map.researchWorkflow"))}</b>
        <span>${escapeHtml(workflow.status || "—")}</span></header>
      ${episode ? `<p><strong>${escapeHtml(i18n.t("map.episodeWindow"))}</strong>
        ${escapeHtml(episode.start)} → ${escapeHtml(episode.end)}
        · ${Number(episode.duration_days) || "—"} days</p>
        <small>${escapeHtml(i18n.t("map.historyContextOnly"))}</small>` : ""}
      <ol>${(workflow.stages || []).map((stage) => `
        <li class="is-${escapeHtml(stage.status || "unknown")}">
          <i></i><span><b>${escapeHtml(i18n.t(labels[stage.stage] || stage.stage))}</b>
          <small>${escapeHtml([
            stage.status,
            stage.recommendation,
            stage.error,
            stage.finding_count !== undefined ? `${stage.finding_count} findings` : null,
            stage.remaining_findings !== undefined
              ? `${stage.remaining_findings} remaining` : null,
          ].filter(Boolean).join(" · "))}</small></span>
        </li>
      `).join("")}</ol>
    </section>
  `;
}

function renderResearchScope(scope) {
  const groups = [
    ["map.scopeCompanies", scope.companies],
    ["map.scopeSectors", scope.sectors],
    ["map.scopeInputs", scope.supply_chain_inputs],
    ["map.scopeInfrastructure", scope.infrastructure],
    ["map.scopeGeographies", scope.geographies],
  ].filter(([, values]) => values?.length);
  return groups.map(([label, values]) => `
    <span><b>${escapeHtml(i18n.t(label))}</b>${escapeHtml(values.slice(0, 6).join(" · "))}</span>
  `).join("");
}

function renderChatGPTResearchReview(review) {
  if (!review) return "";
  return `
    <section class="chatgpt-review">
      <header>
        <b>${escapeHtml(i18n.t("map.chatgptSecondOpinion"))}</b>
        <span>${escapeHtml(review.model)} · ${
          escapeHtml(researchRecommendationLabel(review.recommendation))
        }</span>
      </header>
      <p>${escapeHtml(review.overall_assessment)}</p>
      <strong>${escapeHtml(i18n.t("map.revisedSummary"))}</strong>
      <p>${escapeHtml(review.revised_summary)}</p>
      <ul>${review.findings.map((finding) => `
        <li class="is-${escapeHtml(finding.severity)}">
          ${escapeHtml(finding.finding)}
          <small>${escapeHtml(finding.suggested_revision)}</small>
        </li>
      `).join("")}</ul>
    </section>
  `;
}

function researchStepStatusLabel(status) {
  const labels = {
    verified: "map.researchVerified",
    partially_supported: "map.researchPartial",
    evidence_missing: "map.researchMissing",
    hypothesis: "map.researchHypothesis",
  };
  return i18n.t(labels[status] || status);
}

function researchRecommendationLabel(recommendation) {
  const labels = {
    accept: "map.researchAccept",
    revise_and_accept: "map.researchReviseAccept",
    defer_for_evidence: "map.researchDefer",
    reject: "map.researchReject",
  };
  return i18n.t(labels[recommendation] || recommendation);
}

function initializeMap() {
  if (!window.L) {
    showMapError(i18n.t("map.mapUnavailable"));
    return;
  }
  state.map = L.map("map", {
    zoomControl: true,
    minZoom: 2.25,
    maxZoom: 12,
    zoomSnap: 0.25,
    zoomDelta: 0.5,
    worldCopyJump: false,
    maxBounds: [[-85, -180], [85, 180]],
    maxBoundsViscosity: 1,
  }).setView([25, 5], 2.25);
  setBaseTileLayer();
  [
    ["country-shapes", 320],
    ["administrative-shapes", 340],
    ["conflict-zones", 355],
    ["economic-overlays", 365],
    ["conflict-movements", 378],
    ["event-chains", 385],
    ["administrative-points", 410],
    ["event-points", 440],
    ["transport-markers", 610],
    ["country-labels", 630],
  ].forEach(([name, zIndex]) => {
    const pane = state.map.createPane(name);
    pane.style.zIndex = String(zIndex);
  });
  state.countryLayerGroup = L.layerGroup().addTo(state.map);
  state.countryLabelLayerGroup = L.layerGroup().addTo(state.map);
  state.economicLayerGroup = L.layerGroup().addTo(state.map);
  state.administrativeBoundaryLayerGroup = L.layerGroup().addTo(state.map);
  state.administrativeLayerGroup = L.layerGroup().addTo(state.map);
  state.conflictZoneLayerGroup = L.layerGroup().addTo(state.map);
  state.conflictMovementLayerGroup = L.layerGroup().addTo(state.map);
  state.conflictRenderer = L.canvas({ padding: 0.35 });
  state.chainLayerGroup = L.layerGroup().addTo(state.map);
  state.transportLayerGroup = L.layerGroup().addTo(state.map);
  state.layerGroup = L.layerGroup().addTo(state.map);
  state.map.on("zoomend", () => {
    updateGeographyLevel();
    void updateAdministrativeLayer();
    renderCountryLabels();
    renderTransportLayer();
    scheduleConflictIndicatorLoad();
  });
  state.map.on("moveend", scheduleConflictIndicatorLoad);
}

function bindFilters() {
  [
    ["window", elements.timeWindow],
    ["layer", elements.layerFilter],
    ["source", elements.sourceFilter],
  ].forEach(([key, element]) => {
    element.addEventListener("change", () => {
      state.filters[key] = element.value;
      stopPlayback();
      if (key === "window") populateFilters();
      refreshTimeline();
      render();
      if (key === "window") {
        const markets = state.marketCache.get(state.selectedCountry);
        if (markets) renderMarketIndices(markets);
      }
      if (key === "window" && state.conflicts.enabled) {
        void loadConflictIndicator();
      }
    });
  });

  elements.eventIndicatorOptions.addEventListener("change", () => {
    state.filters.eventTypes = new Set(
      [...elements.eventIndicatorOptions.querySelectorAll(
        "[data-event-type]:checked",
      )].map((input) => input.value),
    );
    const conflictsEnabled = state.filters.eventTypes.has("conflict");
    state.conflicts.enabled = conflictsEnabled;
    updateEventIndicatorSummary();
    stopPlayback();
    refreshTimeline();
    if (!conflictsEnabled) {
      state.conflicts.controller?.abort();
      state.conflicts.payload = null;
      state.conflictZoneLayerGroup?.clearLayers();
      state.conflictMovementLayerGroup?.clearLayers();
      elements.conflictLayerStatus.textContent = i18n.t("map.conflictLayerOff");
    }
    render();
    if (conflictsEnabled) {
      elements.conflictLayerStatus.textContent = i18n.t("map.conflictLayerLoading");
      void loadConflictIndicator();
    }
  });

  elements.eventList.addEventListener("click", (event) => {
    const card = event.target.closest("[data-marker-id]");
    if (!card || !state.map) return;
    focusNewsMarker(card.dataset.markerId);
  });

  elements.economicIndicatorOptions.addEventListener("change", async (event) => {
    const input = event.target.closest("[data-economic-code]");
    if (!input) return;
    const selected = [...elements.economicIndicatorOptions.querySelectorAll(
      "[data-economic-code]:checked",
    )].map((option) => option.value);
    if (selected.length > 4) {
      input.checked = false;
      elements.economicStatus.textContent = i18n.t("map.economicMax");
      return;
    }
    state.economics.selectedCodes = selected;
    state.economics.year = null;
    updateEconomicIndicatorSummary();
    await loadEconomicLayer();
  });
  elements.economicYear.addEventListener("change", async () => {
    state.economics.year = elements.economicYear.value || null;
    await loadEconomicLayer();
  });
  elements.timelineSlider.addEventListener("input", () => {
    state.timeline.index = Number(elements.timelineSlider.value);
    updateTimelineLabel();
    render();
  });
  elements.timelinePlay.addEventListener("click", togglePlayback);
  elements.countryPanelClose.addEventListener("click", () => {
    elements.countryPanel.hidden = true;
    elements.countryPanelEmpty.hidden = false;
  });
  elements.applyRankingWeights.addEventListener("click", () => {
    void loadCountryRankings(state.selectedCountry, true);
  });
  elements.mapLanguageMode.value = state.mapLabelMode;
  elements.mapLanguageMode.addEventListener("change", () => {
    state.mapLabelMode = elements.mapLanguageMode.value;
    localStorage.setItem("newsapp-map-label-mode", state.mapLabelMode);
    refreshMapLanguage();
    renderTransportLayer();
    state.renderedAdministrativeKey = null;
    state.renderedAdmin1BoundaryCountry = null;
    void updateAdministrativeLayer();
  });
  elements.showAirports.addEventListener("change", () => {
    state.transport.showAirports = elements.showAirports.checked;
    renderTransportLayer();
  });
  elements.showPorts.addEventListener("change", () => {
    state.transport.showPorts = elements.showPorts.checked;
    renderTransportLayer();
  });
  elements.thematicEnabled.addEventListener("change", () => {
    state.thematic.enabled = elements.thematicEnabled.checked;
    elements.thematicMode.disabled = !state.thematic.enabled;
    renderThematicLegend();
    applyCountryStyles();
    applyAdministrativeBoundaryStyles();
  });
  elements.thematicMode.addEventListener("change", () => {
    state.thematic.mode = elements.thematicMode.value;
    renderThematicLegend();
    applyCountryStyles();
    applyAdministrativeBoundaryStyles();
  });
}

function focusNewsMarker(markerId) {
  const marker = state.data?.markers.find((item) => item.id === markerId);
  if (!marker || !state.map) return;
  const preciseLocation = !(
    marker.is_conflict
    && marker.conflict_zone_role === "location_unconfirmed"
  );
  if (!preciseLocation) {
    elements.mapError.textContent = i18n.t("map.newsFocusUnavailable");
    elements.mapError.hidden = false;
    window.setTimeout(() => {
      elements.mapError.hidden = true;
    }, 3600);
    return;
  }
  const targetZoom = marker.geolocation_precision === "point"
    ? 9
    : marker.geolocation_precision === "city"
      ? 8
      : marker.geolocation_precision === "admin1"
        ? 7
        : 5.5;
  const layer = state.markerLayers.get(markerId);
  state.map.flyTo(
    [marker.latitude, marker.longitude],
    Math.max(state.map.getZoom(), targetZoom),
    { animate: true, duration: 0.85 },
  );
  const reveal = () => {
    if (!layer) return;
    layer.openPopup();
    if (layer._path) {
      layer._path.classList.add("focused-news-marker");
      window.setTimeout(() => {
        layer._path?.classList.remove("focused-news-marker");
      }, 2200);
    }
  };
  state.map.once("moveend", reveal);
  window.setTimeout(reveal, 1100);
}

async function initializeEconomics() {
  try {
    const payload = await api("/economics/indicators");
    state.economics.indicators = payload.indicators;
    const defaultCode = payload.indicators.some(
      (indicator) => indicator.code === "FP.CPI.TOTL.ZG",
    )
      ? "FP.CPI.TOTL.ZG"
      : payload.indicators[0]?.code;
    state.economics.selectedCodes = defaultCode ? [defaultCode] : [];
    populateEconomicIndicators();
    await loadEconomicLayer();
  } catch (error) {
    elements.economicStatus.textContent =
      `${i18n.t("map.loadFailed")}: ${error.message}`;
  }
}

async function initializeCountryBoundaries() {
  if (!state.map || !state.countryLayerGroup) return;
  try {
    const countries = await api("/review-assets/data/countries.geojson");
    const layer = L.geoJSON(countries, {
      pane: "country-shapes",
      style: countryBoundaryStyle,
      onEachFeature: (feature, featureLayer) => {
        const iso2 = countryIso2(feature.properties || {});
        if (!iso2) return;
        state.countryProperties.set(iso2, feature.properties || {});
        state.countryBounds.set(iso2, featureLayer.getBounds());
        featureLayer.on("add", () => {
          const path = featureLayer.getElement?.();
          if (!path) return;
          path.setAttribute(
            "aria-label",
            `${localizedFeatureName(feature.properties || {})} `
            + `${i18n.language === "zh" ? "区域" : "area"}`,
          );
        });
        featureLayer.on({
          click: () => {
            void openCountryPanel(iso2);
          },
          mouseover: () => {
            const base = countryBoundaryStyle(feature);
            featureLayer.setStyle({
              color: "#f7d37a",
              fillColor: base.fillColor,
              fillOpacity: Math.max(base.fillOpacity || 0, 0.2),
              opacity: 1,
              weight: 2.5,
            });
            featureLayer.bringToFront();
          },
          mouseout: () => {
            featureLayer.setStyle(countryBoundaryStyle(feature));
          },
        });
      },
    });
    state.countryFeatureLayer = layer;
    layer.addTo(state.countryLayerGroup);
    renderCountryLabels();
  } catch (error) {
    console.warn("country boundaries unavailable", error);
  }
}

async function initializeEventChains() {
  if (!state.data?.latest_cluster_job_id) return;
  try {
    state.eventChain = await api(
      `/event-chains/${state.data.latest_cluster_job_id}`,
    );
    renderEvidenceList();
  } catch (error) {
    console.warn("event-chain layer unavailable", error);
  }
}

async function initializeLogicChains() {
  const logicJobId = state.data?.latest_logic_job_id
    || state.data?.latest_cluster_job_id;
  if (!logicJobId) return;
  try {
    state.logicChain = await api(
      `/logic-chains/${logicJobId}`,
    );
    renderLogicChains();
  } catch (error) {
    console.warn("logic-chain layer unavailable", error);
  }
}

async function initializeTransportHubs() {
  try {
    const [airports, ports] = await Promise.all([
      api("/review-assets/data/airports.geojson"),
      api("/review-assets/data/ports.geojson"),
    ]);
    state.transport.airports = airports;
    state.transport.ports = ports;
  } catch (error) {
    console.warn("transport hub layers unavailable", error);
  }
}

function setBaseTileLayer() {
  if (!state.map) return;
  if (state.baseTileLayer) state.map.removeLayer(state.baseTileLayer);
  const nativeLabels = state.mapLabelMode === "native";
  state.baseTileLayer = nativeLabels
    ? L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 12,
      noWrap: true,
      bounds: [[-85, -180], [85, 180]],
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    })
    : L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png",
      {
        maxZoom: 12,
        noWrap: true,
        bounds: [[-85, -180], [85, 180]],
        subdomains: "abcd",
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> '
          + '&copy; <a href="https://carto.com/attributions">CARTO</a>',
      },
    );
  state.baseTileLayer.addTo(state.map);
}

function refreshMapLanguage() {
  setBaseTileLayer();
  renderCountryLabels();
  if (state.selectedCountry) renderCountryPanelFromCache();
}

function localizedFeatureName(properties) {
  if (state.mapLabelMode === "native") {
    return properties.NAME || properties.name || properties.ADMIN || "";
  }
  if (state.mapLabelMode === "english") {
    return properties.NAME_EN || properties.name_en
      || properties.NAME || properties.name || properties.ADMIN || "";
  }
  if (i18n.language === "zh") {
    return properties.NAME_ZH || properties.name_zh || properties.NAME_ZHT
      || properties.name_zht || properties.NAME || properties.name
      || properties.ADMIN || "";
  }
  return properties.NAME_EN || properties.name_en
    || properties.NAME || properties.name || properties.ADMIN || "";
}

function renderCountryLabels() {
  if (!state.map || !state.countryLabelLayerGroup || !state.countryFeatureLayer) return;
  state.countryLabelLayerGroup.clearLayers();
  if (state.mapLabelMode === "native") return;
  const zoom = state.map.getZoom();
  if (zoom > 8.5) return;
  const maximumRank = zoom < 2.75
    ? 3
    : zoom < 3.75
      ? 5
      : zoom <= 5.5
        ? 9
        : 99;
  const visibleBounds = state.map.getBounds().pad(0.08);
  state.countryFeatureLayer.eachLayer((layer) => {
    const properties = layer.feature?.properties || {};
    const iso2 = countryIso2(properties);
    const rank = Number(properties.LABELRANK ?? 99);
    const minimumLabelZoom = Number(
      properties.MIN_LABEL ?? properties.MIN_ZOOM ?? 99,
    );
    if (
      (
        zoom <= 5.5
        && (rank > maximumRank || minimumLabelZoom > zoom + 0.35)
      )
      || (zoom > 5.5 && iso2 !== state.selectedCountry)
      || typeof layer.getBounds !== "function"
      || !visibleBounds.intersects(layer.getBounds())
    ) return;
    const name = localizedFeatureName(properties);
    if (!name) return;
    const labelMarker = L.marker(featureLabelLatLng(properties, layer), {
      pane: "country-labels",
      interactive: true,
      keyboard: true,
      title: name,
      alt: name,
      icon: L.divIcon({
        className: `place-label country${zoom > 4 ? " zoomed" : ""}`,
        html: `<button type="button" class="country-label-button" `
          + `aria-label="${escapeHtml(name)}">${escapeHtml(name)}</button>`,
        iconSize: null,
      }),
    });
    labelMarker.on("click", (event) => {
      if (event.originalEvent) L.DomEvent.stopPropagation(event.originalEvent);
      void openCountryPanel(iso2);
    });
    labelMarker.addTo(state.countryLabelLayerGroup);
  });
}

function featureLabelLatLng(properties, layer) {
  const latitude = Number(
    properties.LABEL_Y ?? properties.label_y ?? properties.LABEL_LAT,
  );
  const longitude = Number(
    properties.LABEL_X ?? properties.label_x ?? properties.LABEL_LON,
  );
  if (
    Number.isFinite(latitude)
    && Number.isFinite(longitude)
    && latitude >= -90
    && latitude <= 90
    && longitude >= -180
    && longitude <= 180
  ) {
    return [latitude, longitude];
  }
  return layer.getBounds().getCenter();
}

function countryBoundaryStyle(feature = null) {
  const zoom = state.map?.getZoom() || 2;
  const iso2 = countryIso2(feature?.properties || {});
  const thematic = thematicCountryStyle(iso2);
  const selected = Boolean(iso2 && iso2 === state.selectedCountry);
  const selectedDetail = selected && zoom > 4;
  let fillOpacity = thematic.fillOpacity;
  if (
    selectedDetail
    && state.thematic.enabled
    && state.thematic.mode === "conflict"
  ) {
    fillOpacity = 0;
  } else if (selectedDetail) {
    fillOpacity = Math.min(fillOpacity, 0.2);
  } else if (zoom > 4 && state.selectedCountry) {
    fillOpacity *= 0.72;
  }
  return {
    color: selected ? "#f3d58a" : "rgba(197, 217, 222, 0.46)",
    fillColor: thematic.fillColor,
    fillOpacity,
    opacity: selected ? 0.95 : zoom <= 7 ? 0.72 : 0.32,
    weight: selected ? 1.8 : zoom <= 4 ? 0.9 : 0.6,
  };
}

function countryIso2(properties) {
  const candidates = [properties.ISO_A2_EH, properties.ISO_A2];
  return candidates.find((value) => /^[A-Z]{2}$/.test(String(value || ""))) || null;
}

async function openCountryPanel(iso2) {
  state.selectedCountry = iso2;
  state.selectedAreaDetail = null;
  state.renderedAdministrativeKey = null;
  state.renderedAdmin1BoundaryCountry = null;
  renderCountryLabels();
  renderThematicLegend();
  applyCountryStyles();
  const bounds = state.countryBounds.get(iso2);
  if (bounds && state.map) {
    const properties = state.countryProperties.get(iso2) || {};
    const fittedZoom = state.map.getBoundsZoom(bounds, false, [42, 42]);
    const focus = featureLabelLatLng(properties, {
      getBounds: () => bounds,
    });
    state.map.setView(
      focus,
      Math.max(4.75, Math.min(6, fittedZoom)),
      { animate: true },
    );
  }
  elements.countryPanel.hidden = false;
  elements.countryPanelEmpty.hidden = true;
  elements.countryPanelName.textContent = iso2;
  elements.countryPanelMeta.textContent = i18n.t("map.countryLoading");
  elements.countryPanelMetrics.innerHTML = "";
  elements.countryMarketIndices.innerHTML = "";
  elements.countryMarketStatus.textContent = "";
  void updateAdministrativeLayer();
  try {
    let country = state.countryCache.get(iso2);
    let markets = state.marketCache.get(iso2);
    if (!country || !markets) {
      const [countryPayload, marketPayload] = await Promise.all([
        country || api(`/economics/countries/${encodeURIComponent(iso2)}`),
        markets || api(`/markets/indices?country_iso2=${encodeURIComponent(iso2)}`),
      ]);
      country = countryPayload;
      markets = marketPayload;
      state.countryCache.set(iso2, country);
      state.marketCache.set(iso2, markets);
    }
    if (state.selectedCountry === iso2) {
      renderCountryPanel(country);
      renderMarketIndices(markets);
      void loadCountryRankings(iso2);
    }
  } catch (error) {
    elements.countryPanelMeta.textContent =
      error.message.includes("404") || error.message.includes("not found")
        ? i18n.t("map.countryUnavailable")
        : `${i18n.t("map.loadFailed")}: ${error.message}`;
  }
}

function renderCountryPanelFromCache() {
  if (!state.selectedCountry || elements.countryPanel.hidden) return;
  const country = state.countryCache.get(state.selectedCountry);
  if (country) renderCountryPanel(country);
  const markets = state.marketCache.get(state.selectedCountry);
  if (markets) renderMarketIndices(markets);
  const rankings = state.rankings.cache.get(state.selectedCountry);
  if (rankings) renderCountryRankings(rankings, state.selectedCountry);
}

async function loadCountryRankings(iso2, force = false) {
  if (!iso2) return;
  const params = new URLSearchParams({
    country_iso2: iso2,
    year: String(state.rankings.year),
    top_limit: "10",
  });
  if (force) {
    elements.countryRankingWeights
      .querySelectorAll("[data-ranking-weight]")
      .forEach((input) => {
        state.rankings.weights.set(
          input.dataset.rankingWeight,
          Number(input.value),
        );
      });
  }
  state.rankings.weights.forEach((value, code) => {
    params.append("weight", `${code}:${value}`);
  });
  elements.countryRankingStatus.textContent =
    i18n.language === "zh" ? "正在计算世界排名…" : "Calculating world ranks…";
  try {
    const payload = await api(`/economics/rankings?${params.toString()}`);
    state.rankings.cache.set(iso2, payload);
    if (!state.rankings.weights.size) {
      payload.weights.forEach((row) => {
        state.rankings.weights.set(row.indicator_code, row.weight);
      });
    }
    if (state.selectedCountry === iso2) {
      renderCountryRankings(payload, iso2);
    }
  } catch (error) {
    elements.countryRankingStatus.textContent =
      `${i18n.t("map.loadFailed")}: ${error.message}`;
  }
}

function renderCountryRankings(payload, iso2) {
  const selected = payload.countries.find(
    (country) => country.iso2 === iso2,
  );
  elements.countryRankingSummary.innerHTML = selected
    ? `
      <strong>#${selected.rank}</strong>
      <span>${escapeHtml(i18n.t("map.compositeRank"))}</span>
      <b>${selected.composite_score.toFixed(1)} / 100</b>
      <small>${escapeHtml(i18n.t("map.coverage"))} · ${
        Math.round(selected.data_coverage * 100)
      }% · ${payload.year}</small>
    `
    : `<span>${payload.year} · ${
      i18n.language === "zh" ? "官方数据不足，暂不排名" : "Insufficient official data"
    }</span>`;
  const names = new Map(
    payload.weights.map((row) => [
      row.indicator_code,
      i18n.language === "zh" ? row.name_zh : row.name_en,
    ]),
  );
  elements.countryRankingWeights.innerHTML = payload.weights.map((row) => `
    <label class="ranking-weight">
      <span>${escapeHtml(names.get(row.indicator_code))}</span>
      <input type="range" min="0" max="40" step="1"
        value="${state.rankings.weights.get(row.indicator_code) ?? row.weight}"
        data-ranking-weight="${escapeHtml(row.indicator_code)}">
      <b>${state.rankings.weights.get(row.indicator_code) ?? row.weight}</b>
    </label>
  `).join("");
  elements.countryRankingWeights
    .querySelectorAll("[data-ranking-weight]")
    .forEach((input) => {
      input.addEventListener("input", () => {
        input.nextElementSibling.textContent = input.value;
      });
    });
  const metricRanks = selected?.metric_ranks || [];
  const metricHtml = metricRanks
    .sort((left, right) => left.rank - right.rank)
    .slice(0, 9)
    .map((metric) => `
      <li>
        <span>${escapeHtml(names.get(metric.indicator_code) || metric.indicator_code)}</span>
        <b>#${metric.rank}<small> / ${metric.ranked_country_count}</small></b>
      </li>
    `).join("");
  const leaders = payload.countries
    .filter((country) => country.rank <= 10)
    .sort((left, right) => left.rank - right.rank)
    .map((country) => `
      <li class="${country.iso2 === iso2 ? "selected" : ""}">
        <b>#${country.rank}</b>
        <span>${escapeHtml(country.country_name)}</span>
        <strong>${country.composite_score.toFixed(1)}</strong>
      </li>
    `).join("");
  elements.countryRankingList.innerHTML = `
    ${metricHtml ? `<ul class="metric-rank-list">${metricHtml}</ul>` : ""}
    <h4>${escapeHtml(i18n.t("map.topCountries"))}</h4>
    <ol>${leaders}</ol>
  `;
  elements.countryRankingStatus.textContent = i18n.language === "zh"
    ? "采用同年度百分位与可调权重；低值更优指标及2%通胀目标会先反向处理，数据缺口会降低综合分。"
    : payload.methodology;
}

function renderCountryPanel(country) {
  const countryProperties = state.countryProperties.get(country.iso2);
  elements.countryPanelName.textContent =
    localizedFeatureName(countryProperties || {}) || country.country_name;
  elements.countryPanelMeta.textContent = [
    country.iso2,
    country.region,
    country.income_level,
    country.capital_city,
  ].filter(Boolean).join(" · ");
  elements.countryPanelMetrics.innerHTML = country.metrics.map((metric) => {
    const name = i18n.language === "zh"
      ? metric.indicator.name_zh
      : metric.indicator.name_en;
    return `
      <article class="country-metric">
        <span>${escapeHtml(name)}</span>
        <strong title="${escapeHtml(String(metric.value))}">
          ${escapeHtml(formatEconomicValue(metric.value, metric.indicator.unit))}
        </strong>
        <small>${metric.year}</small>
      </article>
    `;
  }).join("");
}

function renderMarketIndices(payload) {
  if (!payload) return;
  if (!payload.indices.length) {
    elements.countryMarketIndices.innerHTML = "";
    elements.countryMarketStatus.textContent = i18n.t("map.noMarketIndex");
    return;
  }
  elements.countryMarketIndices.innerHTML = payload.indices.map((index) => {
    const name = i18n.language === "zh" ? index.name_zh : index.name_en;
    const value = index.close === null
      ? "—"
      : new Intl.NumberFormat(i18n.language === "zh" ? "zh-CN" : "en-CA", {
        maximumFractionDigits: 2,
      }).format(index.close);
    const change = index.change_percent === null
      ? ""
      : `${index.change_percent >= 0 ? "+" : ""}${index.change_percent.toFixed(2)}%`;
    const windowStart = timeWindowStart(state.filters.window);
    const observedAt = index.observed_on
      ? new Date(`${index.observed_on}T23:59:59Z`).getTime()
      : null;
    const outsideWindow = windowStart !== null
      && observedAt !== null
      && observedAt < windowStart;
    return `
      <a class="market-index ${outsideWindow ? "is-outside-window" : ""}"
        href="${escapeAttribute(index.official_url)}"
        target="_blank" rel="noreferrer">
        <span>${escapeHtml(name)}</span>
        <strong>${escapeHtml(value)}</strong>
        <small>${escapeHtml(index.exchange)} · ${escapeHtml(index.currency)}
          ${change ? ` · ${escapeHtml(change)}` : ""}
          ${index.observed_on ? ` · ${escapeHtml(index.observed_on)}` : ""}
          ${outsideWindow ? `<br>${escapeHtml(
            i18n.t("map.observationOutsideWindow"),
          )}` : ""}
          ${index.quote_proxy_en ? `<br>${escapeHtml(
            i18n.language === "zh"
              ? index.quote_proxy_zh
              : index.quote_proxy_en,
          )}` : ""}</small>
      </a>
    `;
  }).join("");
  const statusKey = payload.quote_status === "credential_required"
    ? "map.marketCredential"
    : payload.quote_status === "provider_error"
      ? "map.marketProviderError"
      : payload.quote_status === "partial"
        ? "map.marketPartial"
      : "map.marketDelay";
  elements.countryMarketStatus.textContent =
    `${i18n.t(statusKey)} · ${payload.provider}`;
}

function populateEconomicIndicators() {
  elements.economicIndicatorOptions.innerHTML =
    state.economics.indicators.map((indicator) => {
      const name = i18n.language === "zh" ? indicator.name_zh : indicator.name_en;
      const checked = state.economics.selectedCodes.includes(indicator.code);
      return `
        <label>
          <input type="checkbox" value="${escapeHtml(indicator.code)}"
            data-economic-code ${checked ? "checked" : ""}>
          <span>${escapeHtml(name)}</span>
        </label>
      `;
    }).join("");
  updateEconomicIndicatorSummary();
}

function updateEconomicIndicatorSummary() {
  const selected = state.economics.selectedCodes.map((code) => {
    const indicator = state.economics.indicators.find((item) => item.code === code);
    return indicator
      ? i18n.language === "zh" ? indicator.name_zh : indicator.name_en
      : code;
  });
  elements.economicIndicatorSummary.textContent = selected.length
    ? `${i18n.t("map.economicSelected")} · ${selected.length}: ${selected.join(" + ")}`
    : i18n.t("map.economyOff");
}

function populateEconomicYears() {
  const data = state.economics.dataByCode.get(
    state.economics.selectedCodes[0],
  );
  const years = data?.available_years || [];
  elements.economicYear.innerHTML = years.map(
    (year) => `<option value="${year}">${year}</option>`,
  ).join("");
  elements.economicYear.disabled = years.length === 0;
  if (data?.selected_year) {
    elements.economicYear.value = String(data.selected_year);
  }
}

async function loadEconomicLayer() {
  const codes = state.economics.selectedCodes;
  if (!codes.length) {
    state.economics.dataByCode.clear();
    populateEconomicYears();
    elements.economicStatus.textContent = i18n.t("map.economyOff");
    renderEconomicLayer();
    renderThematicLegend();
    return;
  }
  elements.economicStatus.textContent = i18n.t("map.economyLoading");
  try {
    const yearQuery = state.economics.year
      ? `&year=${encodeURIComponent(state.economics.year)}`
      : "";
    const payloads = await Promise.all(codes.map((code) => api(
      `/economics/map?indicator_code=${encodeURIComponent(code)}${yearQuery}`,
    )));
    state.economics.dataByCode = new Map(
      payloads.map((payload) => [payload.indicator.code, payload]),
    );
    const primaryData = payloads[0];
    state.economics.year = primaryData.selected_year
      ? String(primaryData.selected_year)
      : null;
    state.rankings.year = Number(
      primaryData.selected_year
        || state.economics.year
        || new Date().getUTCFullYear(),
    );
    state.rankings.cache.clear();
    if (state.selectedCountry) {
      void loadCountryRankings(state.selectedCountry);
    }
    populateEconomicYears();
    renderEconomicLayer();
    renderThematicLegend();
  } catch (error) {
    elements.economicStatus.textContent =
      `${i18n.t("map.loadFailed")}: ${error.message}`;
  }
}

function renderEconomicLayer() {
  if (!state.economicLayerGroup) return;
  state.economicLayerGroup.clearLayers();
  const datasets = state.economics.selectedCodes
    .map((code) => state.economics.dataByCode.get(code))
    .filter(Boolean);
  if (!datasets.length || !datasets.some((data) => data.points.length)) {
    if (state.economics.selectedCodes.length) {
      elements.economicStatus.textContent = i18n.t("map.economyPending");
    }
    applyCountryStyles();
    return;
  }
  [...datasets].reverse().forEach((data, reverseIndex) => {
    const indicatorIndex = datasets.length - reverseIndex - 1;
    const values = data.points.map((point) => point.value);
    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    data.points.forEach((point) => {
      const color = economicColor(point.value, minimum, maximum);
      const economicMarker = L.circleMarker([point.latitude, point.longitude], {
        pane: "economic-overlays",
        radius: 8 + indicatorIndex * 3.5,
        color,
        fillColor: color,
        fillOpacity: datasets.length === 1 ? 0.28 : 0.08,
        opacity: 0.9,
        weight: 2.2,
        dashArray: indicatorIndex % 2 ? "4 3" : null,
      });
      economicMarker.bindPopup(renderEconomicPopup(point, data.indicator));
      economicMarker.on("click", () => openCountryPanel(point.iso2));
      economicMarker.addTo(state.economicLayerGroup);
    });
  });
  const statuses = datasets.map((data) => {
    const indicatorName = i18n.language === "zh"
      ? data.indicator.name_zh
      : data.indicator.name_en;
    return `${indicatorName} · ${data.selected_year} · ${data.country_count}`;
  });
  elements.economicStatus.textContent = `${statuses.join(" / ")} `
    + `${i18n.t("map.economyCoverage")}`;
  applyCountryStyles();
}

function economicColor(value, minimum, maximum) {
  if (maximum === minimum) return "#75b9df";
  const ratio = (value - minimum) / (maximum - minimum);
  if (ratio < 0.25) return "#4d8eb7";
  if (ratio < 0.5) return "#65b8c7";
  if (ratio < 0.75) return "#c2be72";
  return "#e2a357";
}

function applyCountryStyles() {
  if (!state.countryFeatureLayer) return;
  state.countryFeatureLayer.eachLayer((layer) => {
    if (typeof layer.setStyle === "function") {
      layer.setStyle(countryBoundaryStyle(layer.feature));
    }
  });
}

function thematicCountryStyle(iso2) {
  const defaultStyle = {
    fillColor: "#3a6065",
    fillOpacity: state.map?.getZoom() <= 4 ? 0.08 : 0.035,
  };
  if (!state.thematic.enabled || !iso2) return defaultStyle;
  if (state.thematic.mode === "conflict") {
    // Conflict is rendered as evidence-backed local footprints, never as a
    // whole-country safety or war judgment.
    return { fillColor: "#263f43", fillOpacity: 0.025 };
  }
  if (state.thematic.mode === "economy") {
    const data = state.economics.dataByCode.get(
      state.economics.selectedCodes[0],
    );
    const point = data?.points.find((item) => item.iso2 === iso2);
    if (!point || !data?.points.length) {
      return { fillColor: "#435458", fillOpacity: 0.12 };
    }
    const values = data.points.map((item) => item.value);
    return {
      fillColor: economicColor(
        point.value,
        Math.min(...values),
        Math.max(...values),
      ),
      fillOpacity: 0.48,
    };
  }
  if (state.thematic.mode === "affinity") {
    if (!state.selectedCountry) return defaultStyle;
    const score = politicalAffinityScore(state.selectedCountry, iso2);
    if (score >= 0.66) return { fillColor: "#3cab76", fillOpacity: 0.45 };
    if (score >= 0.34) return { fillColor: "#d4b34f", fillOpacity: 0.4 };
    return { fillColor: "#d9574f", fillOpacity: 0.48 };
  }
  return defaultStyle;
}

function rebuildConflictScores(markers) {
  const scores = new Map();
  const points = state.conflicts.enabled
    ? (state.conflicts.payload?.points || [])
    : [];
  points.forEach((point) => {
    const iso2 = countryIso2FromName(point.country);
    if (!iso2) return;
    const score = Number(point.urgency_score || 0);
    scores.set(iso2, Math.max(scores.get(iso2) || 0, score));
  });
  state.thematic.conflictScores = scores;
}

function countryIso2FromName(countryName) {
  const target = normalizePlaceName(countryName);
  for (const [iso2, properties] of state.countryProperties.entries()) {
    const names = [
      properties.ADMIN,
      properties.NAME,
      properties.NAME_EN,
      properties.BRK_NAME,
      properties.SOVEREIGNT,
    ].map(normalizePlaceName);
    if (names.includes(target)) return iso2;
  }
  return null;
}

function markerCountryIso2(marker) {
  const raw = String(marker.country_code || "").toUpperCase();
  if (/^[A-Z]{2}$/.test(raw)) return raw;
  if (!/^[A-Z]{3}$/.test(raw)) return null;
  for (const [iso2, properties] of state.countryProperties.entries()) {
    if ([
      properties.ISO_A3,
      properties.ISO_A3_EH,
      properties.ADM0_A3,
      properties.SOV_A3,
    ].some((value) => String(value || "").toUpperCase() === raw)) {
      return iso2;
    }
  }
  return null;
}

function politicalAffinityScore(selectedIso2, targetIso2) {
  if (selectedIso2 === targetIso2) return 1;
  const directRivalry = POLITICAL_AFFINITY_MODEL.rivalryPairs.some(
    ([left, right]) => (
      left === selectedIso2 && right === targetIso2
    ) || (
      right === selectedIso2 && left === targetIso2
    ),
  );
  if (directRivalry) return 0.08;
  let score = 0.34;
  POLITICAL_AFFINITY_MODEL.groups.forEach((group) => {
    if (
      group.members.includes(selectedIso2)
      && group.members.includes(targetIso2)
    ) {
      score += group.weight;
    }
  });
  const selectedProperties = state.countryProperties.get(selectedIso2) || {};
  const targetProperties = state.countryProperties.get(targetIso2) || {};
  const selectedSubregion = selectedProperties.SUBREGION
    || selectedProperties.subregion;
  const targetSubregion = targetProperties.SUBREGION
    || targetProperties.subregion;
  if (
    selectedSubregion
    && targetSubregion
    && selectedSubregion === targetSubregion
  ) {
    score += 0.08;
  }
  return Math.min(0.96, score);
}

function renderThematicLegend() {
  if (!elements.thematicLegend) return;
  if (!state.thematic.enabled) {
    elements.thematicLegend.innerHTML = "";
    return;
  }
  if (state.thematic.mode === "conflict") {
    elements.thematicLegend.innerHTML = thematicLegendRows([
      ["#d6bd4d", "map.thematicConflictMinor"],
      ["#e48343", "map.thematicConflictElevated"],
      ["#df4c46", "map.thematicConflictSevere"],
    ]) + `<p>${escapeHtml(i18n.t("map.thematicConflictCaution"))}</p>`;
    return;
  }
  if (state.thematic.mode === "economy") {
    const primaryCode = state.economics.selectedCodes[0];
    const indicator = state.economics.indicators.find(
      (item) => item.code === primaryCode,
    );
    const name = indicator
      ? i18n.language === "zh" ? indicator.name_zh : indicator.name_en
      : i18n.t("map.economyOff");
    elements.thematicLegend.innerHTML = thematicLegendRows([
      ["#4d8eb7", i18n.language === "zh" ? "较低区间" : "Lower range"],
      ["#65b8c7", i18n.language === "zh" ? "中低区间" : "Lower-middle"],
      ["#c2be72", i18n.language === "zh" ? "中高区间" : "Upper-middle"],
      ["#e2a357", i18n.language === "zh" ? "较高区间" : "Higher range"],
    ], false) + `<strong>${escapeHtml(name)}</strong>`
      + `<p>${escapeHtml(i18n.t("map.thematicEconomyCaution"))}</p>`;
    return;
  }
  const selectionNotice = state.selectedCountry
    ? ""
    : `<strong>${escapeHtml(i18n.t("map.thematicSelectCountry"))}</strong>`;
  elements.thematicLegend.innerHTML = thematicLegendRows([
    ["#3cab76", "map.thematicAffinityClose"],
    ["#d4b34f", "map.thematicAffinityLimited"],
    ["#d9574f", "map.thematicAffinityRival"],
  ]) + selectionNotice
    + `<p>${escapeHtml(i18n.t("map.thematicAffinityCaution"))}</p>`
    + `<small>${POLITICAL_AFFINITY_MODEL.updatedAt} · `
    + `<a href="https://www.nato.int/cps/en/natohq/topics_52044.htm" `
    + `target="_blank" rel="noreferrer">NATO</a> · `
    + `<a href="https://brics.br/en/about-the-brics" target="_blank" `
    + `rel="noreferrer">BRICS</a> · `
    + `<a href="https://eng.sectsco.org/" target="_blank" `
    + `rel="noreferrer">SCO</a></small>`;
}

function thematicLegendRows(rows, translate = true) {
  return `<div class="thematic-scale">${rows.map(([color, label]) => `
    <span><i style="background:${color}"></i>${
      escapeHtml(translate ? i18n.t(label) : label)
    }</span>
  `).join("")}</div>`;
}

function renderEconomicPopup(point, indicator) {
  const name = i18n.language === "zh" ? indicator.name_zh : indicator.name_en;
  return `
    <p class="popup-kind">${escapeHtml(name)} · ${point.year}</p>
    <h3 class="popup-title">${escapeHtml(point.country_name)}</h3>
    <div class="economic-value">
      ${escapeHtml(formatEconomicValue(point.value, indicator.unit))}
    </div>
    <div class="popup-meta">
      ${escapeHtml(point.capital_city || "")}<br>
      ${escapeHtml(i18n.t("map.countryReference"))}<br>
      ${escapeHtml(i18n.t("map.sourceAttribution"))}: ${escapeHtml(indicator.source_name)}
    </div>
    <a class="popup-link" href="${escapeAttribute(indicator.source_url)}" target="_blank" rel="noreferrer">
      ${escapeHtml(i18n.t("map.sourceLink"))}
    </a>
  `;
}

function renderTransportLayer() {
  if (!state.map || !state.transportLayerGroup) return;
  state.transportLayerGroup.clearLayers();
  const zoom = state.map.getZoom();
  const maximumRank = zoom <= 2 ? 2 : zoom === 3 ? 4 : zoom === 4 ? 6 : 9;
  if (state.transport.showAirports && state.transport.airports) {
    renderHubFeatures(
      state.transport.airports.features,
      "airport",
      maximumRank,
    );
  }
  if (state.transport.showPorts && state.transport.ports) {
    renderHubFeatures(
      state.transport.ports.features,
      "port",
      maximumRank,
    );
  }
}

function renderHubFeatures(features, kind, maximumRank) {
  const effectiveMaximumRank = kind === "port"
    ? Math.max(3, maximumRank)
    : maximumRank;
  features
    .filter(
      (feature) =>
        Number(feature.properties?.scalerank ?? 99) <= effectiveMaximumRank,
    )
    .slice(0, 450)
    .forEach((feature) => {
      const coordinates = feature.geometry?.coordinates;
      if (!Array.isArray(coordinates) || coordinates.length < 2) return;
      const properties = feature.properties || {};
      const name = localizedFeatureName(properties);
      const marker = L.marker([coordinates[1], coordinates[0]], {
        pane: "transport-markers",
        icon: L.divIcon({
          className: `hub-marker ${kind}`,
          html: `<span>${kind === "airport" ? "✈" : "⚓"}</span>`,
          iconSize: [18, 18],
          iconAnchor: [9, 9],
        }),
        title: name,
      });
      marker.bindTooltip(name, { direction: "top" });
      marker.bindPopup(renderHubPopup(properties, kind));
      marker.addTo(state.transportLayerGroup);
    });
}

function renderHubPopup(properties, kind) {
  const name = localizedFeatureName(properties);
  const code = kind === "airport"
    ? properties.iata_code || properties.gps_code || properties.abbrev || ""
    : "";
  const rank = properties.scalerank ?? "—";
  const link = properties.wikipedia || properties.website || "";
  const normalizedLink = /^https?:\/\//i.test(link)
    ? link
    : link ? `https://${link}` : "";
  return `
    <p class="popup-kind">${escapeHtml(
      i18n.t(kind === "airport" ? "map.airports" : "map.ports"),
    )}${code ? ` · ${escapeHtml(code)}` : ""}</p>
    <h3 class="popup-title">${escapeHtml(name)}</h3>
    <div class="popup-meta">
      ${escapeHtml(i18n.t("map.hubRank"))}: ${escapeHtml(rank)}<br>
      ${escapeHtml(i18n.t("map.hubRankNotice"))}<br>
      ${escapeHtml(i18n.t("map.sourceAttribution"))}: Natural Earth
    </div>
    ${normalizedLink
      ? `<a class="popup-link" href="${escapeAttribute(normalizedLink)}"
          target="_blank" rel="noreferrer">${escapeHtml(i18n.t("map.sourceLink"))}</a>`
      : ""}
  `;
}

function formatEconomicValue(value, unit) {
  const formatted = new Intl.NumberFormat(
    i18n.language === "zh" ? "zh-CN" : "en-CA",
    {
      maximumFractionDigits: Math.abs(value) >= 1000 ? 0 : 2,
      notation: Math.abs(value) >= 1_000_000 ? "compact" : "standard",
    },
  ).format(value);
  return `${formatted} ${localizedEconomicUnit(unit)}`;
}

function localizedEconomicUnit(unit) {
  if (i18n.language !== "zh") return unit;
  const units = {
    "% annual": "%（年率）",
    "% of GDP": "%（占 GDP）",
    "% of labor force": "%（占劳动力）",
    "% of total value added": "%（占增加值）",
    "constant 2014-2016 = 100": "2014–2016 年 = 100",
    "current US$": "现价美元",
    "LCU per US$": "本币/美元",
    "million ton-km": "百万吨公里",
    passengers: "人次",
    people: "人",
  };
  return units[unit] || unit;
}

function populateFilters() {
  if (!state.data) return;
  const selectedSource = state.filters.source;
  const sources = [...new Set(
    state.data.markers.map((marker) => marker.source_name),
  )].sort();
  const typeCounts = new Map();
  const visibleTypeCounts = new Map();
  state.data.markers.forEach((marker) => {
    const type = marker.is_conflict ? "conflict" : marker.event_type;
    typeCounts.set(type, (typeCounts.get(type) || 0) + 1);
    if (markerMatchesTimeWindow(marker)) {
      visibleTypeCounts.set(type, (visibleTypeCounts.get(type) || 0) + 1);
    }
  });
  const types = [...typeCounts].sort(
    (left, right) => right[1] - left[1] || left[0].localeCompare(right[0]),
  );
  elements.sourceFilter.innerHTML = [
    `<option value="all">${escapeHtml(i18n.t("map.sourceAll"))}</option>`,
    ...sources.map(
      (source) => `<option value="${escapeHtml(source)}">${escapeHtml(source)}</option>`,
    ),
  ].join("");
  elements.eventIndicatorOptions.innerHTML = types.map(([type, count]) => `
    <label>
      <input type="checkbox" value="${escapeHtml(type)}"
        data-event-type="${escapeHtml(type)}"
        ${state.filters.eventTypes.has(type) ? "checked" : ""}>
      <span>${escapeHtml(eventIndicatorLabel(type))}</span>
      <b>${visibleTypeCounts.get(type) || 0} / ${count}</b>
    </label>
  `).join("");
  if (sources.includes(selectedSource)) {
    elements.sourceFilter.value = selectedSource;
  } else {
    state.filters.source = "all";
  }
  state.filters.eventTypes = new Set(
    [...state.filters.eventTypes].filter((type) => typeCounts.has(type)),
  );
  updateEventIndicatorSummary();
}

function eventIndicatorLabel(type) {
  if (type === "conflict") return i18n.t("map.conflictIndicator");
  if (type === "earthquake") return i18n.t("map.earthquakeIndicator");
  return humanize(type);
}

function updateEventIndicatorSummary() {
  const selected = [...state.filters.eventTypes];
  elements.eventIndicatorSummary.textContent = selected.length
    ? `${i18n.t("map.eventIndicatorsSelected")}: ${selected.map(
        eventIndicatorLabel,
      ).join("、")}`
    : i18n.t("map.eventIndicatorsNone");
}

function refreshTimeline() {
  if (!state.data) return;
  const markers = filteredMarkersWithoutPlayback().filter(
    (marker) => !marker.is_conflict,
  );
  state.timeline.times = markers
    .map(
      (marker) =>
        new Date(marker.series_end_at || marker.occurred_at).getTime(),
    )
    .filter((value) => Number.isFinite(value))
    .sort((left, right) => left - right);
  state.timeline.index = null;
  elements.timelineSlider.min = "0";
  elements.timelineSlider.max = String(
    Math.max(0, state.timeline.times.length - 1),
  );
  elements.timelineSlider.value = String(
    Math.max(0, state.timeline.times.length - 1),
  );
  elements.timelineSlider.disabled = state.timeline.times.length < 2;
  elements.timelinePlay.disabled = state.timeline.times.length < 2;
  updateTimelineLabel();
  renderTimelineLanes();
}

function filteredMarkersWithoutPlayback() {
  if (!state.data) return [];
  return state.data.markers.filter((marker) => {
    if (!state.filters.eventTypes.size) return false;
    const layerMatches = state.filters.layer === "all"
      || marker.kind === state.filters.layer;
    const sourceMatches = state.filters.source === "all"
      || marker.source_name === state.filters.source;
    const typeMatches = marker.is_conflict
      ? state.filters.eventTypes.has("conflict")
      : state.filters.eventTypes.has(marker.event_type);
    return layerMatches && sourceMatches && typeMatches
      && markerMatchesTimeWindow(marker);
  });
}

function markerMatchesTimeWindow(marker) {
  const windowStart = timeWindowStart(state.filters.window);
  if (windowStart === null) return true;
  const occurredAt = new Date(
    marker.series_end_at || marker.occurred_at,
  ).getTime();
  return Number.isFinite(occurredAt) && occurredAt >= windowStart;
}

function updateTimeScopeStatus() {
  if (!elements.timeScopeStatus) return;
  const start = timeWindowStart(state.filters.window);
  const range = start === null
    ? i18n.t("map.timeScopeAll")
    : `${formatDate(new Date(start).toISOString())} → ${formatDate(
      new Date().toISOString(),
    )}`;
  const count = state.data ? filteredMarkersWithoutPlayback().length : 0;
  elements.timeScopeStatus.textContent = `${range} · ${count} · ${
    i18n.t("map.timeScopeStrict")
  }. ${i18n.t("map.timeScopeSlow")}.`;
}

function timeWindowStart(windowValue) {
  const dayCount = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
  }[windowValue];
  return dayCount ? Date.now() - dayCount * 24 * 60 * 60 * 1000 : null;
}

function togglePlayback() {
  if (state.timeline.timer) {
    stopPlayback();
    return;
  }
  if (state.timeline.times.length < 2) return;
  const lastIndex = state.timeline.times.length - 1;
  state.timeline.index = (
    state.timeline.index === null || state.timeline.index >= lastIndex
  ) ? 0 : state.timeline.index;
  elements.timelineSlider.value = String(state.timeline.index);
  setPlaybackButton(true);
  updateTimelineLabel();
  render();
  state.timeline.timer = window.setInterval(() => {
    if (
      state.timeline.index === null
      || state.timeline.index >= lastIndex
    ) {
      stopPlayback();
      return;
    }
    state.timeline.index += 1;
    elements.timelineSlider.value = String(state.timeline.index);
    updateTimelineLabel();
    render();
  }, 650);
}

function stopPlayback() {
  if (state.timeline.timer) {
    window.clearInterval(state.timeline.timer);
    state.timeline.timer = null;
  }
  setPlaybackButton(false);
}

function setPlaybackButton(playing) {
  const icon = elements.timelinePlay.querySelector("span");
  const label = elements.timelinePlay.querySelector("b");
  icon.textContent = playing ? "Ⅱ" : "▶";
  label.textContent = i18n.t(playing ? "map.pause" : "map.play");
}

function updateTimelineLabel() {
  const times = state.timeline.times;
  if (!times.length) {
    elements.timelineDate.textContent = "—";
    return;
  }
  const index = state.timeline.index ?? times.length - 1;
  elements.timelineDate.textContent =
    `${i18n.t("map.through")} ${formatDate(times[index])}`;
}

function renderTimelineLanes() {
  const markers = filteredMarkersWithoutPlayback().filter(
    (marker) => !marker.is_conflict,
  );
  const laneDefinitions = [
    ["conflict", "map.laneConflict"],
    ["economy", "map.laneEconomy"],
    ["politics", "map.lanePolitics"],
    ["disaster", "map.laneDisaster"],
    ["other", "map.laneOther"],
  ];
  if (!markers.length) {
    elements.timelineLanes.innerHTML = "";
    return;
  }
  const times = markers
    .map((marker) => new Date(marker.occurred_at).getTime())
    .filter(Number.isFinite);
  const minimum = Math.min(...times);
  const maximum = Math.max(...times);
  elements.timelineLanes.innerHTML = laneDefinitions.map(([key, labelKey]) => {
    const laneMarkers = markers.filter(
      (marker) => timelineCategory(marker) === key,
    );
    const sampleEvery = Math.max(1, Math.ceil(laneMarkers.length / 80));
    const ticks = laneMarkers
      .filter((_, index) => index % sampleEvery === 0)
      .map((marker) => {
        const time = new Date(
          marker.series_end_at || marker.occurred_at,
        ).getTime();
        const position = maximum === minimum
          ? 50
          : ((time - minimum) / (maximum - minimum)) * 100;
        return `<i class="timeline-tick" style="left:${position.toFixed(2)}%"></i>`;
      })
      .join("");
    return `
      <div class="timeline-lane ${key}">
        <span>${escapeHtml(i18n.t(labelKey))}</span>
        <div class="timeline-track">${ticks}</div>
        <b>${laneMarkers.length}</b>
      </div>
    `;
  }).join("");
}

function timelineCategory(marker) {
  if (marker.is_conflict) return "conflict";
  const type = String(marker.event_type || "").toLowerCase();
  if (/(econom|market|trade|financ|business|industry|agricultur)/.test(type)) {
    return "economy";
  }
  if (/(politic|diplom|policy|election|government|sanction)/.test(type)) {
    return "politics";
  }
  if (/(disaster|weather|climate|earthquake|flood|fire|storm)/.test(type)) {
    return "disaster";
  }
  return "other";
}

function updateGeographyLevel() {
  const zoom = state.map?.getZoom() || 2;
  const key = zoom <= 4
    ? "map.levelCountry"
    : zoom <= 7
      ? "map.levelAdmin1"
      : "map.levelCity";
  elements.geographyLevel.textContent = i18n.t(key);
  // The outer LayerGroup contains one GeoJSON container without a feature.
  // Styling that container applies the same anonymous style to every child
  // and erases the selected-country/thematic state after zooming.
  applyCountryStyles();
}

async function updateAdministrativeLayer() {
  if (!state.map || !state.administrativeLayerGroup) return;
  const zoom = state.map.getZoom();
  if (!state.selectedCountry || zoom <= 4) {
    state.administrativeLayerGroup.clearLayers();
    state.administrativeBoundaryLayerGroup?.clearLayers();
    state.admin1FeatureLayer = null;
    state.renderedAdministrativeKey = null;
    state.renderedAdmin1BoundaryCountry = null;
    return;
  }
  void renderAdministrativeBoundaries(state.selectedCountry);
  const level = zoom <= 7 ? "admin1" : "city";
  const key = `${state.selectedCountry}:${level}`;
  if (state.renderedAdministrativeKey === key) return;
  state.renderedAdministrativeKey = key;
  try {
    let payload = state.administrativeCache.get(key);
    if (!payload) {
      const minimum = level === "city" ? "&minimum_population=15000" : "";
      payload = await api(
        `/geography/areas?country_iso2=${encodeURIComponent(state.selectedCountry)}`
        + `&level=${level}&limit=${level === "city" ? 1000 : 500}${minimum}`,
      );
      state.administrativeCache.set(key, payload);
    }
    if (state.renderedAdministrativeKey !== key) return;
    renderAdministrativeLayer(payload.areas);
  } catch (error) {
    console.warn("administrative layer unavailable", error);
    state.renderedAdministrativeKey = null;
  }
}

async function renderAdministrativeBoundaries(iso2) {
  if (
    !state.administrativeBoundaryLayerGroup
    || state.renderedAdmin1BoundaryCountry === iso2
  ) return;
  state.renderedAdmin1BoundaryCountry = iso2;
  try {
    const source = await loadAdmin1BoundarySource(iso2);
    if (state.selectedCountry !== iso2 || (state.map?.getZoom() || 0) <= 4) return;
    const features = Array.isArray(source.features) ? source.features : [];
    state.administrativeBoundaryLayerGroup.clearLayers();
    const layer = L.geoJSON(
      { type: "FeatureCollection", features },
      {
        pane: "administrative-shapes",
        style: admin1BoundaryStyle,
        onEachFeature: (feature, featureLayer) => {
          const name = localizedAdmin1Name(feature.properties || {});
          featureLayer.on("add", () => {
            window.requestAnimationFrame(() => {
              decorateBoundaryAccessibility(featureLayer, name);
            });
          });
          if (name) {
            featureLayer.bindTooltip(name, {
              sticky: true,
              direction: "top",
              opacity: 0.92,
              className: "administrative-boundary-label",
            });
          }
          featureLayer.on({
            mouseover: () => {
              const base = admin1BoundaryStyle(feature);
              featureLayer.setStyle({
                color: "#f8d77d",
                fillColor: base.fillColor,
                fillOpacity: Math.max(base.fillOpacity || 0, 0.24),
                opacity: 1,
                weight: 2.4,
              });
              featureLayer.bringToFront();
            },
            mouseout: () => {
              featureLayer.setStyle(admin1BoundaryStyle(feature));
            },
            click: () => {
              if (!state.map || typeof featureLayer.getBounds !== "function") return;
              state.map.fitBounds(featureLayer.getBounds(), {
                animate: true,
                padding: [54, 54],
                maxZoom: 8.25,
              });
              const areas = state.administrativeCache.get(`${iso2}:admin1`)?.areas || [];
              const match = areas.find(
                (area) => normalizePlaceName(localizedAreaName(area))
                  === normalizePlaceName(name),
              );
              if (match) void openAreaPanel(match);
            },
          });
        },
      },
    );
    state.admin1FeatureLayer = layer;
    layer.addTo(state.administrativeBoundaryLayerGroup);
    layer.eachLayer((featureLayer) => {
      const name = localizedAdmin1Name(featureLayer.feature?.properties || {});
      decorateBoundaryAccessibility(featureLayer, name);
    });
    applyAdministrativeBoundaryStyles();
  } catch (error) {
    console.warn("administrative boundaries unavailable", error);
    state.renderedAdmin1BoundaryCountry = null;
  }
}

function decorateBoundaryAccessibility(featureLayer, name) {
  if (!name) return;
  const path = featureLayer.getElement?.();
  if (path) {
    path.setAttribute("role", "button");
    path.setAttribute("tabindex", "0");
    path.setAttribute(
      "aria-label",
      `${name} ${i18n.language === "zh" ? "省州轮廓" : "boundary"}`,
    );
  }
  if (typeof featureLayer.eachLayer === "function") {
    featureLayer.eachLayer((childLayer) => {
      decorateBoundaryAccessibility(childLayer, name);
    });
  }
}

async function loadAdmin1BoundarySource(iso2) {
  const cached = state.admin1BoundarySources.get(iso2);
  if (cached) return cached;
  let pending = state.admin1BoundaryPromises.get(iso2);
  if (!pending) {
    pending = (async () => {
      const properties = state.countryProperties.get(iso2) || {};
      const iso3 = [
        properties.ISO_A3_EH,
        properties.ISO_A3,
        properties.ADM0_A3,
        properties.SOV_A3,
      ].map((value) => String(value || "").toUpperCase())
        .find((value) => /^[A-Z]{3}$/.test(value) && value !== "-99");
      if (!iso3) {
        throw new Error(`no ISO3 code available for ${iso2}`);
      }
      const metadataResponse = await fetch(
        `${GEOBOUNDARIES_API_BASE}/${encodeURIComponent(iso3)}/ADM1/`,
      );
      if (!metadataResponse.ok) {
        throw new Error(`admin1 metadata request failed: ${metadataResponse.status}`);
      }
      const metadata = await metadataResponse.json();
      const metadataGeometryUrl =
        metadata.simplifiedGeometryGeoJSON || metadata.gjDownloadURL;
      if (!metadataGeometryUrl) {
        throw new Error(`admin1 geometry URL missing for ${iso3}`);
      }
      const geometryUrl = normalizeGithubRawUrl(metadataGeometryUrl);
      const geometryResponse = await fetch(geometryUrl);
      if (!geometryResponse.ok) {
        throw new Error(`admin1 geometry request failed: ${geometryResponse.status}`);
      }
      const source = await geometryResponse.json();
      state.admin1BoundarySources.set(iso2, source);
      return source;
    })().catch((error) => {
      state.admin1BoundaryPromises.delete(iso2);
      throw error;
    });
    state.admin1BoundaryPromises.set(iso2, pending);
  }
  return pending;
}

function normalizeGithubRawUrl(url) {
  return String(url).replace(
    /^https:\/\/github\.com\/([^/]+\/[^/]+)\/raw\/([^/]+)\/(.*)$/i,
    "https://media.githubusercontent.com/media/$1/$2/$3",
  );
}

function localizedAdmin1Name(properties) {
  if (state.mapLabelMode === "native") {
    return properties.name_local || properties.shapeName
      || properties.name || properties.NAME || "";
  }
  if (state.mapLabelMode === "english" || i18n.language === "en") {
    return properties.name_en || properties.shapeName
      || properties.name || properties.NAME || "";
  }
  return properties.name_zh || properties.name_zht
    || properties.shapeName || properties.name || properties.NAME || "";
}

function admin1BoundaryStyle(feature) {
  const conflictScore = provinceConflictScore(feature);
  if (
    state.thematic.enabled
    && state.thematic.mode === "conflict"
  ) {
    if (conflictScore === null) {
      return admin1StyleWithFill("#365156", 0.025);
    }
    if (conflictScore < 0.38) {
      return admin1StyleWithFill("#d6bd4d", 0.28);
    }
    if (conflictScore < 0.7) {
      return admin1StyleWithFill("#e48343", 0.34);
    }
    return admin1StyleWithFill("#df4c46", 0.42);
  }
  return admin1StyleWithFill("#6ea8b4", 0.035);
}

function admin1StyleWithFill(fillColor, fillOpacity) {
  return {
    color: "rgba(176, 207, 216, 0.55)",
    fillColor,
    fillOpacity,
    opacity: 0.82,
    weight: 0.85,
  };
}

function applyAdministrativeBoundaryStyles() {
  if (!state.admin1FeatureLayer) return;
  state.admin1FeatureLayer.eachLayer((layer) => {
    if (typeof layer.setStyle === "function") {
      layer.setStyle(admin1BoundaryStyle(layer.feature));
    }
  });
}

function provinceConflictScore(feature) {
  let score = null;
  if (!state.conflicts.enabled) return score;
  (state.conflicts.payload?.points || []).forEach((point) => {
      if (!pointInGeoJsonFeature(point.longitude, point.latitude, feature)) return;
      score = Math.max(score || 0, Number(point.urgency_score || 0));
    });
  return score;
}

function pointInGeoJsonFeature(longitude, latitude, feature) {
  const geometry = feature?.geometry;
  if (!geometry) return false;
  const polygons = geometry.type === "Polygon"
    ? [geometry.coordinates]
    : geometry.type === "MultiPolygon"
      ? geometry.coordinates
      : [];
  return polygons.some((polygon) => {
    if (!polygon.length || !pointInRing(longitude, latitude, polygon[0])) {
      return false;
    }
    return !polygon.slice(1).some(
      (hole) => pointInRing(longitude, latitude, hole),
    );
  });
}

function pointInRing(longitude, latitude, ring) {
  let inside = false;
  for (let index = 0, previous = ring.length - 1; index < ring.length; previous = index++) {
    const [x1, y1] = ring[index];
    const [x2, y2] = ring[previous];
    const intersects = (
      (y1 > latitude) !== (y2 > latitude)
      && longitude < ((x2 - x1) * (latitude - y1)) / ((y2 - y1) || 1e-12) + x1
    );
    if (intersects) inside = !inside;
  }
  return inside;
}

function normalizePlaceName(value) {
  return String(value || "").normalize("NFKD").replace(/\p{Diacritic}/gu, "")
    .toLowerCase().replace(/[^a-z0-9\u3400-\u9fff]+/g, "");
}

function renderAdministrativeLayer(areas) {
  state.administrativeLayerGroup.clearLayers();
  areas.forEach((area) => {
    if (area.latitude === null || area.longitude === null) return;
    const isCity = area.level === "city";
    const marker = L.circleMarker([area.latitude, area.longitude], {
      pane: "administrative-points",
      className: `administrative-marker ${area.level}-marker`,
      radius: isCity
        ? Math.min(8, 3 + Math.log10(Math.max(area.population || 1, 1)) / 2)
        : 7,
      color: isCity ? "#b7d8f3" : "#e7b95b",
      fillColor: isCity ? "#83aedd" : "#d4a95b",
      fillOpacity: isCity ? 0.62 : 0.5,
      opacity: 0.9,
      weight: 1.3,
      dashArray: isCity ? null : "4 3",
    });
    const areaName = localizedAreaName(area);
    marker.bindTooltip(areaName, {
      direction: "top",
      permanent: !isCity || (area.population || 0) >= 1_000_000,
      opacity: isCity ? 0.72 : 0.82,
      className: "administrative-label",
    });
    marker.bindPopup(renderAdministrativePopup(area));
    marker.on("click", () => void openAreaPanel(area));
    marker.addTo(state.administrativeLayerGroup);
  });
}

function renderAdministrativePopup(area) {
  const precision = area.level === "city"
    ? i18n.t("map.cityReference")
    : i18n.t("map.regionReference");
  const population = area.population
    ? `<strong>${escapeHtml(i18n.t("map.regionPopulation"))}: `
      + `${escapeHtml(new Intl.NumberFormat().format(area.population))}</strong><br>`
    : "";
  return `
    <p class="popup-kind">${escapeHtml(humanize(area.level))}</p>
    <h3 class="popup-title">${escapeHtml(localizedAreaName(area))}</h3>
    <div class="popup-meta">
      ${population}
      ${escapeHtml(precision)}<br>
      ${escapeHtml(i18n.t("map.sourceAttribution"))}: ${escapeHtml(area.source_name)}
    </div>
  `;
}

async function openAreaPanel(area) {
  elements.countryPanel.hidden = false;
  elements.countryPanelName.textContent = localizedAreaName(area);
  elements.countryPanelMeta.textContent = i18n.t("map.regionLoading");
  elements.countryPanelMetrics.innerHTML = "";
  void loadCountryMarkets(area.country_iso2);
  try {
    let detail = state.areaCache.get(area.id);
    if (!detail) {
      detail = await api(`/geography/areas/${area.id}`);
      state.areaCache.set(area.id, detail);
    }
    state.selectedAreaDetail = detail;
    renderAreaPanel(detail);
  } catch (error) {
    elements.countryPanelMeta.textContent =
      `${i18n.t("map.loadFailed")}: ${error.message}`;
  }
}

function renderAreaPanel(detail) {
  const area = detail.area;
  const precision = area.level === "city"
    ? i18n.t("map.cityReference")
    : i18n.t("map.regionReference");
  elements.countryPanelName.textContent = localizedAreaName(area);
  elements.countryPanelMeta.textContent = [
    area.country_iso2,
    humanize(area.level),
    precision,
  ].join(" · ");
  const metrics = detail.metrics.map((metric) => {
    const name = i18n.language === "zh" ? metric.name_zh : metric.name_en;
    return `
      <article class="country-metric">
        <span>${escapeHtml(name)}</span>
        <strong>${escapeHtml(formatEconomicValue(metric.value, metric.unit))}</strong>
        <small>${escapeHtml(metric.period)} · ${escapeHtml(metric.source_name)}</small>
      </article>
    `;
  });
  if (!metrics.length) {
    metrics.push(
      `<p class="country-panel-meta">${escapeHtml(i18n.t("map.regionNoMetrics"))}</p>`,
    );
  }
  elements.countryPanelMetrics.innerHTML = metrics.join("");
}

function localizedAreaName(area) {
  if (state.mapLabelMode === "english") return area.ascii_name || area.name;
  if (state.mapLabelMode === "native") return area.name;
  return i18n.language === "en" ? area.ascii_name || area.name : area.name;
}

async function loadCountryMarkets(iso2) {
  try {
    let payload = state.marketCache.get(iso2);
    if (!payload) {
      payload = await api(`/markets/indices?country_iso2=${encodeURIComponent(iso2)}`);
      state.marketCache.set(iso2, payload);
    }
    renderMarketIndices(payload);
  } catch (error) {
    elements.countryMarketStatus.textContent =
      `${i18n.t("map.loadFailed")}: ${error.message}`;
  }
}

function render() {
  if (!state.data) return;
  let markers = filteredMarkersWithoutPlayback();
  if (state.timeline.index !== null && state.timeline.times.length) {
    const cutoff = state.timeline.times[state.timeline.index];
    markers = markers.filter(
      (marker) => marker.is_conflict
        || new Date(marker.occurred_at).getTime() <= cutoff,
    );
  }
  state.visibleMarkers = markers;
  rebuildConflictScores(markers);
  elements.visibleCount.textContent = markers.length;
  renderMapMarkers(
    markers,
    state.timeline.index === null && !state.hasInitialFit,
  );
  renderList(markers);
  applyCountryStyles();
  applyAdministrativeBoundaryStyles();
  renderThematicLegend();
  updateTimeScopeStatus();
}

function renderMapMarkers(markers, fitMarkers = true) {
  if (!state.map || !state.layerGroup) return;
  state.layerGroup.clearLayers();
  state.markerLayers.clear();
  const bounds = [];
  markers.forEach((marker) => {
    // Conflict reports are rendered by the bounded ACLED indicator layer.
    // Keeping raw historical conflict circles out of this loop prevents
    // timeline and zoom changes from rebuilding thousands of SVG paths.
    if (marker.is_conflict) return;
    if (
      marker.is_conflict
      && marker.conflict_zone_role === "location_unconfirmed"
    ) {
      return;
    }
    const color = markerColor(marker);
    const approximate = marker.geolocation_precision !== "point";
    const conflictRadius = marker.conflict_zone_role === "primary_theater"
      ? 12
      : marker.conflict_zone_role === "secondary_theater"
        ? 10
        : 8;
    const layer = L.circleMarker(
      [marker.latitude, marker.longitude],
      {
        pane: "event-points",
        radius: marker.is_conflict
          ? conflictRadius
          : marker.series_count > 1
          ? Math.min(14, 8 + Math.log2(marker.series_count))
          : marker.geolocation_precision === "country"
          ? 10
          : marker.geolocation_precision === "admin1"
            ? 8
            : marker.geolocation_precision === "city"
              ? 7
              : marker.kind === "canonical" ? 8 : 6,
        color,
        fillColor: color,
        fillOpacity: approximate
          ? 0.25
          : marker.kind === "canonical" ? 0.86 : 0.64,
        weight: 1.5,
        dashArray: approximate ? "3 3" : null,
      },
    );
    layer.bindPopup(renderPopup(marker));
    layer.addTo(state.layerGroup);
    if (marker.is_conflict && layer._path) {
      layer._path.classList.add("conflict-marker");
      layer._path.classList.add(
        String(marker.conflict_zone_role || "reported_site")
          .replaceAll("_", "-"),
      );
    }
    state.markerLayers.set(marker.id, layer);
    bounds.push([marker.latitude, marker.longitude]);
  });
  renderConflictIndicatorLayer();
  renderReportedConflictMovements(markers);
  renderEventChainLines(markers);
  if (bounds.length && fitMarkers) {
    state.map.fitBounds(bounds, { padding: [45, 45], maxZoom: 7 });
    state.hasInitialFit = true;
  }
}

function renderEventChainLines(markers) {
  if (!state.chainLayerGroup) return;
  state.chainLayerGroup.clearLayers();
  const visibleById = new Map(
    markers
      .filter(
        (marker) => !(
          marker.is_conflict
          && marker.conflict_zone_role === "location_unconfirmed"
        ),
      )
      .map((marker) => [marker.id, marker]),
  );
  if (state.eventChain) {
    state.eventChain.relations
      .filter((relation) => relation.status !== "rejected")
      .forEach((relation) => {
        const source = visibleById.get(`candidate:${relation.source_candidate_id}`);
        const target = visibleById.get(`candidate:${relation.target_candidate_id}`);
        if (!source || !target) return;
        const accepted = relation.status === "accepted";
        const fixed = relation.pinned;
        const line = L.polyline(
          [
            [source.latitude, source.longitude],
            [target.latitude, target.longitude],
          ],
          {
            pane: "event-chains",
            color: fixed ? "#f4f1e8" : accepted ? "#79c7b6" : "#d4a95b",
            opacity: fixed ? 0.92 : accepted ? 0.68 : 0.5,
            weight: fixed ? 3.4 : accepted ? 2.4 : 1.6,
            dashArray: accepted ? null : "6 7",
          },
        );
        line.bindTooltip(
          `${i18n.t(fixed ? "map.chainFixed" : "map.chainSuggested")} · `
          + `${Math.round(relation.confidence * 100)}%`,
          { sticky: true },
        );
        line.addTo(state.chainLayerGroup);
      });
  }
  if (state.logicChain) {
    state.logicChain.hypotheses
      .filter((hypothesis) => hypothesis.status !== "rejected")
      .forEach((hypothesis) => {
        const source = visibleById.get(
          `candidate:${hypothesis.premise_candidate_id}`,
        );
        const target = visibleById.get(
          `candidate:${hypothesis.outcome_candidate_id}`,
        );
        if (!source || !target) return;
        const accepted = ["accepted", "revised_accepted"].includes(
          hypothesis.status,
        );
        const line = L.polyline(
          [
            [source.latitude, source.longitude],
            [target.latitude, target.longitude],
          ],
          {
            pane: "event-chains",
            color: accepted ? "#c7a8f4" : "#9d7bd2",
            opacity: accepted ? 0.8 : 0.5,
            weight: accepted ? 3 : 2,
            dashArray: accepted ? null : "2 7",
          },
        );
        line.bindTooltip(
          `${escapeHtml(hypothesis.title)} · `
          + `${Math.round(hypothesis.confidence * 100)}%`,
          { sticky: true },
        );
        line.addTo(state.chainLayerGroup);
      });
  }
}

function scheduleConflictIndicatorLoad() {
  if (!state.conflicts.enabled || !state.map) return;
  if (state.conflicts.debounceTimer) {
    window.clearTimeout(state.conflicts.debounceTimer);
  }
  state.conflicts.debounceTimer = window.setTimeout(() => {
    void loadConflictIndicator();
  }, 220);
}

async function loadConflictIndicator() {
  if (!state.conflicts.enabled || !state.map) return;
  state.conflicts.controller?.abort();
  const controller = new AbortController();
  state.conflicts.controller = controller;
  state.conflicts.loading = true;
  state.conflicts.payload = null;
  state.conflictZoneLayerGroup?.clearLayers();
  elements.conflictLayerStatus.textContent = i18n.t("map.conflictLayerLoading");
  const bounds = state.map.getBounds();
  const query = new URLSearchParams({
    weeks: String(conflictWeeksForWindow(state.filters.window)),
    west: String(bounds.getWest()),
    south: String(bounds.getSouth()),
    east: String(bounds.getEast()),
    north: String(bounds.getNorth()),
    zoom: String(state.map.getZoom()),
    limit: "1200",
  });
  try {
    const response = await fetch(`/conflicts/indicator?${query}`, {
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.conflicts.payload = await response.json();
    elements.conflictLayerStatus.textContent = state.conflicts.payload.latest_week
      ? `${state.conflicts.payload.point_count} ${i18n.t("map.conflictHotspots")} · `
        + `${i18n.t("map.through")} ${formatDate(
          state.conflicts.payload.latest_week,
        )}`
      : i18n.t("map.conflictLayerEmpty");
    rebuildConflictScores(state.visibleMarkers);
    renderConflictIndicatorLayer();
    applyCountryStyles();
    applyAdministrativeBoundaryStyles();
  } catch (error) {
    if (error.name !== "AbortError") {
      elements.conflictLayerStatus.textContent =
        `${i18n.t("map.conflictLayerFailed")}: ${error.message}`;
    }
  } finally {
    if (state.conflicts.controller === controller) {
      state.conflicts.loading = false;
    }
  }
}

function conflictWeeksForWindow(windowValue) {
  return {
    "7d": 1,
    "30d": 5,
    "90d": 13,
    "all": 2000,
  }[windowValue] || 1;
}

function renderConflictIndicatorLayer() {
  if (!state.conflictZoneLayerGroup) return;
  state.conflictZoneLayerGroup.clearLayers();
  if (!state.conflicts.enabled || !state.conflicts.payload) return;
  const zoom = state.map?.getZoom() || 2;
  state.conflicts.payload.points.forEach((point) => {
    const color = conflictZoneColor(point);
    const radius = 4.5 + Number(point.urgency_score) * (zoom < 4 ? 7 : 10);
    const layer = L.circleMarker([point.latitude, point.longitude], {
      pane: "conflict-zones",
      renderer: state.conflictRenderer,
      radius,
      color,
      fillColor: color,
      fillOpacity: 0.25 + Number(point.urgency_score) * 0.45,
      opacity: 0.84,
      weight: point.role === "primary_theater" ? 2.3 : 1.3,
      interactive: true,
    });
    layer.bindTooltip(
      `${escapeHtml(point.admin1)}, ${escapeHtml(point.country)} · `
      + `${point.events} ${escapeHtml(i18n.t("map.conflictReports"))}`,
      { sticky: true },
    );
    layer.bindPopup(renderConflictIndicatorPopup(point));
    layer.addTo(state.conflictZoneLayerGroup);
  });
}

function renderConflictIndicatorPopup(point) {
  return `
    <article class="conflict-zone-popup">
      <small>${escapeHtml(conflictZoneRoleLabel(point.role))}</small>
      <h3>${escapeHtml(point.admin1)} · ${escapeHtml(point.country)}</h3>
      <p>${point.events} ${escapeHtml(i18n.t("map.conflictReports"))} ·
        ${escapeHtml(i18n.t("map.fatalitiesBest"))} ${point.fatalities}</p>
      <p>${escapeHtml(formatDate(point.period_start))} → ${
        escapeHtml(formatDate(point.period_end))
      } · ${Math.round(point.urgency_score * 100)}%</p>
      <strong>${escapeHtml(i18n.t("map.conflictAggregateCaution"))}</strong>
    </article>
  `;
}

function renderReportedConflictMovements(markers) {
  if (!state.conflictMovementLayerGroup) return;
  state.conflictMovementLayerGroup.clearLayers();
  if (!state.conflicts.enabled || (state.map?.getZoom() || 0) < 5) return;
  const visibleIds = new Set(markers.map((marker) => marker.id));
  const enhanced = state.thematic.enabled && state.thematic.mode === "conflict";
  (state.data.conflict_movements || [])
    .filter(
      (movement) => movement.marker_ids.filter((id) => visibleIds.has(id)).length >= 2,
    )
    .slice(0, 40)
    .forEach((movement) => {
      const line = L.polyline(
        [
          [movement.from_latitude, movement.from_longitude],
          [movement.to_latitude, movement.to_longitude],
        ],
        {
          pane: "conflict-movements",
          className: "conflict-report-shift",
          color: "#ffab54",
          opacity: enhanced ? 0.9 : 0.64,
          weight: enhanced ? 3 : 2.2,
          dashArray: "8 7",
        },
      );
      const tooltip = `${escapeHtml(i18n.t("map.reportedShift"))}: `
        + `${escapeHtml(movement.direction)} · `
        + `${Math.round(movement.confidence * 100)}%`
        + `<br>${escapeHtml(i18n.t("map.conflictCaution"))}`;
      line.bindTooltip(tooltip, { sticky: true });
      line.addTo(state.conflictMovementLayerGroup);
      const angle = conflictDirectionAngle(movement.direction);
      const endpoint = L.marker(
        [movement.to_latitude, movement.to_longitude],
        {
          pane: "conflict-movements",
          interactive: true,
          icon: L.divIcon({
            className: "conflict-shift-arrow",
            html: `<span style="transform:rotate(${angle}deg)">➤</span>`,
            iconSize: [22, 22],
            iconAnchor: [11, 11],
          }),
        },
      );
      endpoint.bindTooltip(tooltip, { sticky: true });
      endpoint.addTo(state.conflictMovementLayerGroup);
    });
}

function conflictZoneColor(zone) {
  if (zone.role === "primary_theater" || Number(zone.urgency_score) >= 0.72) {
    return "#ee514a";
  }
  if (zone.role === "secondary_theater" || Number(zone.urgency_score) >= 0.42) {
    return "#ec8b43";
  }
  return "#d7bd50";
}

function conflictDirectionAngle(direction) {
  return {
    N: -90,
    NE: -45,
    E: 0,
    SE: 45,
    S: 90,
    SW: 135,
    W: 180,
    NW: -135,
  }[direction] || 0;
}

function conflictZoneRoleLabel(role) {
  if (role === "primary_theater") return i18n.t("map.conflictPrimary");
  if (role === "secondary_theater") return i18n.t("map.conflictSecondary");
  return i18n.t("map.conflictReported");
}

function renderConflictZonePopup(zone) {
  const actors = zone.actors?.length
    ? zone.actors.join(" ↔ ")
    : i18n.t("map.conflictActorsUnknown");
  return `
    <article class="conflict-zone-popup">
      <small>${escapeHtml(conflictZoneRoleLabel(zone.role))}</small>
      <h3>${escapeHtml(zone.country_code)} · ${Math.round(
        zone.urgency_score * 100,
      )}</h3>
      <p>${escapeHtml(i18n.t("map.conflictActors"))}: ${escapeHtml(actors)}</p>
      <p>${zone.event_count} ${escapeHtml(i18n.t("map.conflictReports"))} ·
        ${zone.source_count} ${escapeHtml(i18n.t("map.conflictSources"))}${
          zone.fatalities_best === null
            ? ""
            : ` · ${escapeHtml(i18n.t("map.fatalitiesBest"))} ${zone.fatalities_best}`
        }</p>
      <p>${escapeHtml(formatDate(zone.start_at))} → ${
        escapeHtml(formatDate(zone.end_at))
      } · ${Math.round(zone.confidence * 100)}%</p>
      <strong>${escapeHtml(i18n.t("map.conflictCaution"))}</strong>
    </article>
  `;
}

function renderEvidenceList() {
  const chain = state.eventChain;
  if (!chain) {
    elements.fixedChainCount.textContent = "—";
    elements.evidenceList.innerHTML = "";
    return;
  }
  const fixedCount = chain.relations.filter((relation) => relation.pinned).length;
  chain.fixed_relation_count = fixedCount;
  elements.fixedChainCount.textContent =
    `${fixedCount} ${i18n.t("map.fixedCount")}`;
  const relations = [...chain.relations]
    .filter((relation) => relation.status !== "rejected")
    .sort((left, right) => Number(right.pinned) - Number(left.pinned)
      || right.confidence - left.confidence)
    .slice(0, 6);
  elements.evidenceList.innerHTML = relations.map((relation) => `
    <article class="evidence-card ${relation.pinned ? "is-fixed" : ""}">
      <p>${escapeHtml(relation.source_title)}</p>
      <span class="evidence-arrow">↓ ${escapeHtml(
        relation.relation_type === "reported_follow_up"
          ? (i18n.language === "zh" ? "报道中存在响应线索" : "reported response cue")
          : (i18n.language === "zh" ? "时间顺序建议" : "temporal suggestion"),
      )}</span>
      <p>${escapeHtml(relation.target_title)}</p>
      <div class="evidence-meta">
        <span>${Math.round(relation.confidence * 100)}%</span>
        <span>${escapeHtml(i18n.t("map.evidenceDocuments"))}: ${
          relation.evidence_document_ids.length
        }</span>
        <button type="button" data-pin-relation="${relation.id}"
          ${relation.pinned ? "disabled" : ""}>
          ${escapeHtml(i18n.t(relation.pinned ? "map.fixedEvidence" : "map.pinEvidence"))}
        </button>
      </div>
    </article>
  `).join("");
}

async function pinEvidenceRelation(relationId) {
  const relation = state.eventChain?.relations.find((row) => row.id === relationId);
  if (!relation || relation.pinned) return;
  try {
    await apiMutation(`/event-chains/relations/${relationId}`, {
      method: "PATCH",
      body: JSON.stringify({
        status: "accepted",
        pinned: true,
        review_note: i18n.language === "zh"
          ? "由地图复核界面人工接受并固定"
          : "Human accepted and fixed from the map review interface",
      }),
    });
    relation.status = "accepted";
    relation.pinned = true;
    relation.decided_at = new Date().toISOString();
    renderEvidenceList();
    render();
  } catch (error) {
    console.warn("could not fix evidence relation", error);
  }
}

function renderLogicChains() {
  const chain = state.logicChain;
  if (!chain) {
    elements.logicTrainingCount.textContent = "—";
    elements.logicChainList.innerHTML = "";
    return;
  }
  elements.logicTrainingCount.textContent =
    `${chain.training_signal_count} ${i18n.t("map.trainingSignals")}`;
  elements.logicChainList.innerHTML = [...chain.hypotheses]
    .sort((left, right) => {
      const rank = {
        suggested: 0,
        deferred: 1,
        revised_accepted: 2,
        accepted: 3,
        rejected: 4,
      };
      return rank[left.status] - rank[right.status]
        || right.confidence - left.confidence;
    })
    .slice(0, 8)
    .map((hypothesis) => `
      <article class="logic-card is-${escapeHtml(hypothesis.status)}">
        <header>
          <h4>${escapeHtml(hypothesis.title)}</h4>
          <span>${Math.round(hypothesis.composite_score * 100)}%</span>
        </header>
        <div class="logic-scores">
          <span>${escapeHtml(i18n.t("map.compositeScore"))}<b>${
            Math.round(hypothesis.composite_score * 100)
          }</b></span>
          <span>${escapeHtml(i18n.t("map.associationScore"))}<b>${
            Math.round(hypothesis.association_score * 100)
          }</b></span>
          <span>${escapeHtml(i18n.t("map.evidenceCoverage"))}<b>${
            Math.round(hypothesis.evidence_coverage_score * 100)
          }</b></span>
        </div>
        <ol>
          ${hypothesis.steps.map((step) => `
            <li class="logic-step ${escapeHtml(step.step_type)}">
              <b>${escapeHtml(logicStepLabel(step.step_type))}</b>
              <span>${escapeHtml(step.text)}</span>
              <small>${Math.round(step.confidence * 100)}% · ${
                Math.round(step.relevance * 100)
              }% ${escapeHtml(i18n.t("map.relevance"))}${
                step.evidence_refs?.length
                  ? ` · ${escapeHtml(step.evidence_refs.join(" · "))}`
                  : ""
              }</small>
            </li>
          `).join("")}
        </ol>
        ${hypothesis.counterevidence?.length ? `
          <div class="logic-counterevidence">
            <b>${escapeHtml(i18n.t("map.counterevidence"))}</b>
            <ul>${hypothesis.counterevidence.map(
              (item) => `<li>${escapeHtml(item)}</li>`,
            ).join("")}</ul>
          </div>
        ` : ""}
        ${renderCausalValidation(
          hypothesis.causal_validation,
          hypothesis.steps,
          hypothesis.historical_cases,
        )}
        ${renderChatGPTResearchReview(hypothesis.chatgpt_review)}
        <p class="logic-rationale">${escapeHtml(hypothesis.rationale)}</p>
        <textarea data-logic-correction="${hypothesis.id}"
          placeholder="${escapeHtml(i18n.t("map.correctionPlaceholder"))}">${
            escapeHtml(hypothesis.suggested_correction || "")
          }</textarea>
        <footer>
          <span>${escapeHtml(logicStatusLabel(hypothesis.status))}</span>
          <button type="button" data-logic-chatgpt="${hypothesis.id}"
            ${!state.research.openaiConfigured || hypothesis.chatgpt_review
              ? "disabled"
              : ""}>${escapeHtml(
                hypothesis.chatgpt_review
                  ? i18n.t("map.chatgptReviewed")
                  : state.research.openaiConfigured
                    ? i18n.t("map.chatgptReview")
                    : i18n.t("map.chatgptKeyRequired"),
              )}</button>
          <button type="button" data-hypothesis-id="${hypothesis.id}"
            data-logic-decision="rejected">${escapeHtml(i18n.t("map.rejectLogic"))}</button>
          <button type="button" data-hypothesis-id="${hypothesis.id}"
            data-logic-decision="deferred">${escapeHtml(i18n.t("map.deferLogic"))}</button>
          <button type="button" data-hypothesis-id="${hypothesis.id}"
            data-logic-decision="revised_accepted">${escapeHtml(i18n.t("map.reviseAcceptLogic"))}</button>
          <button type="button" data-hypothesis-id="${hypothesis.id}"
            data-logic-decision="accepted">${escapeHtml(i18n.t("map.acceptLogic"))}</button>
        </footer>
      </article>
    `).join("");
}

async function requestLogicChatGPTReview(hypothesisId) {
  const button = elements.logicChainList.querySelector(
    `[data-logic-chatgpt="${hypothesisId}"]`,
  );
  if (button) {
    button.disabled = true;
    button.textContent = i18n.t("map.chatgptReviewRunning");
  }
  try {
    const review = await apiMutation(
      `/logic-chains/hypotheses/${hypothesisId}/chatgpt-review`,
      { method: "POST" },
    );
    const hypothesis = state.logicChain?.hypotheses.find(
      (item) => item.id === hypothesisId,
    );
    if (hypothesis) hypothesis.chatgpt_review = review;
    renderLogicChains();
  } catch (error) {
    elements.researchStatus.textContent =
      `${i18n.t("map.chatgptReviewFailed")}: ${error.message}`;
    if (button) button.disabled = false;
  }
}

function renderCausalValidation(validation, hypothesisSteps = [], historicalCases = []) {
  if (!validation) return "";
  const language = i18n.language;
  const summary = language === "zh"
    ? validation.summary_zh
    : validation.summary_en;
  const citedFacts = (validation.evidence_facts || []).filter(
    (fact) => fact.used_by_checks?.length,
  );
  const recommendation = language === "zh"
    ? validation.recommendation_zh
    : validation.recommendation_en;
  return `
    <section class="causal-validation is-${escapeHtml(validation.conclusion)}">
      <header>
        <div>
          <b>${escapeHtml(i18n.t("map.causalValidator"))}</b>
          <span class="causal-conclusion">${escapeHtml(
            causalConclusionLabel(validation.conclusion),
          )}</span>
        </div>
        <strong>${Math.round(validation.recalculated_confidence * 100)}%</strong>
      </header>
      <div class="causal-meta">
        <span>${escapeHtml(i18n.t("map.recalculatedConfidence"))}</span>
        <span>${escapeHtml(i18n.t("map.validationWindow"))}: ${
          validation.time_window_hours
        } ${escapeHtml(i18n.t("map.hours"))}</span>
      </div>
      ${renderConfidenceBreakdown(validation.confidence_breakdown)}
      ${renderCausalFlow(hypothesisSteps, validation.checks)}
      ${validation.evidence_sources?.length ? `
        <div class="causal-sources">
          <b>${escapeHtml(i18n.t("map.validationSources"))}</b>
          <div>${validation.evidence_sources.map((source) => `
            <a href="${escapeAttribute(source.source_url)}" target="_blank"
              rel="noreferrer" class="is-${escapeHtml(source.status)}"
              title="${escapeHtml(
                language === "zh" ? source.message_zh : source.message_en,
              )}">
              <span>${escapeHtml(source.name)}</span>
              <small>${escapeHtml(causalSourceStatusLabel(source.status))} · ${
                source.observation_count
              } ${escapeHtml(i18n.t("map.observations"))}</small>
              ${citedFacts.filter(
                (fact) => fact.source === source.name,
              ).slice(0, 2).map(
                (fact) => `<em>↳ ${escapeHtml(fact.label)} · ${
                  escapeHtml(fact.value_text)
                }</em>`,
              ).join("")}
            </a>
          `).join("")}</div>
        </div>
      ` : ""}
      ${validation.evidence_facts?.length ? `
        <details class="causal-facts" open>
          <summary>${escapeHtml(i18n.t("map.actuallyCitedEvidence"))} · ${
            citedFacts.length
          } / ${validation.evidence_facts.length
          }</summary>
          <ul>${validation.evidence_facts.map((fact) => `
            <li class="${fact.used_by_checks?.length ? "is-cited" : "is-context"}">
              <a href="${escapeAttribute(fact.source_url)}" target="_blank"
                rel="noreferrer">${escapeHtml(fact.label)}</a>
              <span>${escapeHtml(fact.value_text)}</span>
              <small>${escapeHtml(
                [fact.observed_at, fact.source].filter(Boolean).join(" · "),
              )}</small>
              <em>${escapeHtml(
                fact.used_by_checks?.length
                  ? `${i18n.t("map.usedByChecks")}: ${fact.used_by_checks.map(
                    causalCheckLabel,
                  ).join(" · ")}`
                  : i18n.t("map.contextNotCited"),
              )}</em>
            </li>
          `).join("")}</ul>
        </details>
      ` : ""}
      <div class="causal-section-title">${escapeHtml(
        i18n.t("map.reasoningTrace"),
      )}</div>
      <ol class="causal-checks causal-trace">
        ${(validation.reasoning_trace?.length
          ? validation.reasoning_trace
          : validation.checks).map((check, index) => `
          <li class="is-${escapeHtml(check.status)}">
            <i>${check.sequence || index + 1}</i>
            <div>
              <b>${escapeHtml(causalCheckLabel(check.check_key))}</b>
              <span>${escapeHtml(causalCheckStatusLabel(check.status))} · ${
                Math.round(check.score * 100)
              }%</span>
            </div>
            <p>${escapeHtml(
              language === "zh" ? check.explanation_zh : check.explanation_en,
            )}</p>
            ${check.evidence_refs?.length ? `
              <small>${escapeHtml(check.evidence_refs.join(" · "))}</small>
            ` : ""}
          </li>
        `).join("")}
      </ol>
      <div class="causal-summary">
        <b>${escapeHtml(i18n.t("map.validationSummary"))}</b>
        <p>${escapeHtml(summary)}</p>
      </div>
      <details class="causal-missing" ${
        validation.missing_evidence?.length ? "open" : ""
      }>
        <summary>${escapeHtml(i18n.t("map.missingEvidence"))} · ${
          validation.missing_evidence?.length || 0
        }</summary>
        ${validation.missing_evidence?.length ? `
          <ul>${validation.missing_evidence.map(
            (item) => `<li>${escapeHtml(item)}</li>`,
          ).join("")}</ul>
        ` : `<p>${escapeHtml(i18n.t("map.noMissingEvidence"))}</p>`}
      </details>
      ${validation.next_data_suggestions?.length ? `
        <div class="causal-next-data">
          <b>${escapeHtml(i18n.t("map.nextDataSuggestions"))}</b>
          <ul>${validation.next_data_suggestions.map((item) => {
            const label = language === "zh" ? item.label_zh : item.label_en;
            const reason = language === "zh" ? item.reason_zh : item.reason_en;
            const content = `
              <span>${escapeHtml(label)}</span>
              <small>${escapeHtml(reason)}</small>
            `;
            return `<li class="is-${escapeHtml(item.priority)}">${
              item.source_url
                ? `<a href="${escapeAttribute(item.source_url)}" target="_blank"
                    rel="noreferrer">${content}</a>`
                : content
            }</li>`;
          }).join("")}</ul>
        </div>
      ` : ""}
      ${historicalCases?.length ? `
        <details class="causal-history">
          <summary>${escapeHtml(i18n.t("map.historicalCases"))} · ${
            historicalCases.length
          }</summary>
          <ul>${historicalCases.map((item) => `
            <li>
              <div><b>${escapeHtml(item.title)}</b><span>${
                Math.round(item.similarity_score * 100)
              }%</span></div>
              <small>${escapeHtml(logicStatusLabel(item.decision))} · ${
                escapeHtml(formatDate(item.reviewed_at))
              } · ${Math.round(
                (item.validated_confidence ?? item.original_confidence) * 100,
              )}%</small>
              <p>${escapeHtml(language === "zh" ? item.summary_zh : item.summary_en)}</p>
            </li>
          `).join("")}</ul>
        </details>
      ` : ""}
      <div class="causal-recommendation is-${escapeHtml(
        validation.reviewer_recommendation,
      )}">
        <b>${escapeHtml(i18n.t("map.reviewerRecommendation"))}</b>
        <span>${escapeHtml(logicStatusLabel(validation.reviewer_recommendation))}</span>
        <p>${escapeHtml(recommendation)}</p>
      </div>
      <small class="causal-model">${escapeHtml(validation.validator_model)} · ${
        escapeHtml(validation.validator_version)
      }</small>
    </section>
  `;
}

function renderConfidenceBreakdown(breakdown) {
  if (!breakdown) return "";
  return `
    <details class="causal-score-breakdown" open>
      <summary>${escapeHtml(i18n.t("map.confidenceBreakdown"))}</summary>
      <div class="causal-score-limits">
        <span>${escapeHtml(i18n.t("map.originalConfidence"))}<b>${
          Math.round(breakdown.original_confidence * 100)
        }%</b></span>
        <span>${escapeHtml(i18n.t("map.weightedGateScore"))}<b>${
          Math.round(breakdown.weighted_gate_score * 100)
        }%</b></span>
        <span>${escapeHtml(i18n.t("map.conclusionCap"))}<b>${
          Math.round(breakdown.conclusion_cap * 100)
        }%</b></span>
      </div>
      <div class="causal-score-components">
        ${breakdown.components.map((component) => `
          <div class="is-${escapeHtml(component.status)}">
            <span>${escapeHtml(causalCheckLabel(component.check_key))}</span>
            <div><i style="width:${Math.round(component.score * 100)}%"></i></div>
            <small>${Math.round(component.weight * 100)}% ${
              escapeHtml(i18n.t("map.weight"))
            } · +${Math.round(component.contribution * 100)}%</small>
          </div>
        `).join("")}
      </div>
      <p>${escapeHtml(i18n.t("map.limitingFactor"))}: ${
        escapeHtml(confidenceLimitLabel(breakdown.limiting_factor))
      }</p>
    </details>
  `;
}

function renderCausalFlow(steps, checks) {
  if (!steps?.length) return "";
  const checkByKey = new Map(checks.map((check) => [check.check_key, check]));
  return `
    <div class="causal-flow-wrap">
      <b>${escapeHtml(i18n.t("map.causalFlow"))}</b>
      <ol class="causal-flow">${steps.map((step, index) => {
        const checkKey = causalStepCheckKey(step, index, steps.length);
        const check = checkByKey.get(checkKey);
        return `
          <li class="is-${escapeHtml(check?.status || "missing_evidence")}">
            <small>${escapeHtml(logicStepLabel(step.step_type))}</small>
            <span>${escapeHtml(step.text)}</span>
            <b>${escapeHtml(causalCheckStatusLabel(
              check?.status || "missing_evidence",
            ))}</b>
          </li>
        `;
      }).join("")}</ol>
    </div>
  `;
}

function causalStepCheckKey(step, index, length) {
  if (index === 0 || step.step_type === "reported_event") return "premise_reported";
  if (index === length - 1 || step.step_type === "possible_outcome") {
    return "outcome_time_window";
  }
  if (step.step_type === "market_observation") return "market_expectations";
  if (step.step_type === "counterevidence") return "alternative_explanations";
  return "mechanism_evidence";
}

function confidenceLimitLabel(value) {
  const labels = {
    original_model_confidence: "map.limitOriginal",
    weighted_validation_gates: "map.limitGates",
    conclusion_safety_cap: "map.limitConclusion",
    independent_validator_cap: "map.limitValidator",
  };
  return i18n.t(labels[value] || value);
}

function causalConclusionLabel(conclusion) {
  if (conclusion === "mechanism_supported_not_causal") {
    return i18n.t("map.causalSupported");
  }
  if (conclusion === "mechanism_partially_supported") {
    return i18n.t("map.causalPartial");
  }
  return i18n.t("map.causalTemporal");
}

function causalCheckLabel(checkKey) {
  const labels = {
    premise_reported: "map.checkPremise",
    outcome_time_window: "map.checkTiming",
    mechanism_evidence: "map.checkMechanism",
    market_expectations: "map.checkExpectations",
    alternative_explanations: "map.checkAlternatives",
    causal_sufficiency: "map.checkSufficiency",
  };
  return i18n.t(labels[checkKey] || checkKey);
}

function causalCheckStatusLabel(status) {
  const labels = {
    passed: "map.checkPassed",
    partially_supported: "map.checkPartial",
    missing_evidence: "map.checkMissing",
    failed: "map.checkFailed",
    not_applicable: "map.checkNA",
  };
  return i18n.t(labels[status] || status);
}

function causalSourceStatusLabel(status) {
  const labels = {
    ready: "map.sourceReady",
    partial: "map.sourcePartial",
    unavailable: "map.sourceUnavailable",
    not_configured: "map.sourceNotConfigured",
  };
  return i18n.t(labels[status] || status);
}

function logicStepLabel(stepType) {
  if (stepType === "reported_event") return i18n.t("map.reportedEvent");
  if (stepType === "economic_context") return i18n.t("map.economicContext");
  if (stepType === "market_observation") return i18n.t("map.marketObservation");
  if (stepType === "counterevidence") return i18n.t("map.counterevidence");
  if (stepType === "inferred_mechanism") return i18n.t("map.inferredMechanism");
  return i18n.t("map.possibleOutcome");
}

function logicStatusLabel(status) {
  if (status === "accepted") return i18n.t("map.statusAccepted");
  if (status === "revised_accepted") {
    return i18n.t("map.statusRevisedAccepted");
  }
  if (status === "deferred") return i18n.t("map.statusDeferred");
  if (status === "rejected") return i18n.t("map.statusRejected");
  return i18n.t("map.statusSuggested");
}

async function generateLogicChains() {
  if (!state.data?.latest_cluster_job_id) return;
  elements.generateLogic.disabled = true;
  elements.generateLogic.textContent = i18n.t("map.generatingLogic");
  try {
    state.logicChain = await apiMutation(
      `/logic-chains/${state.data.latest_cluster_job_id}/generate`,
      { method: "POST" },
    );
    renderLogicChains();
    render();
  } catch (error) {
    console.warn("local AI logic generation failed", error);
  } finally {
    elements.generateLogic.disabled = false;
    elements.generateLogic.textContent = i18n.t("map.generateLogic");
  }
}

async function validateLogicChains() {
  if (!state.data?.latest_cluster_job_id) return;
  elements.validateLogic.disabled = true;
  elements.validateLogic.textContent = i18n.t("map.validatingLogic");
  try {
    state.logicChain = await apiMutation(
      `/logic-chains/${state.data.latest_cluster_job_id}/validate`,
      { method: "POST" },
    );
    renderLogicChains();
    render();
  } catch (error) {
    console.warn("causal validation failed", error);
  } finally {
    elements.validateLogic.disabled = false;
    elements.validateLogic.textContent = i18n.t("map.validateLogic");
  }
}

async function reviewLogicHypothesis(hypothesisId, decision) {
  const correction = elements.logicChainList.querySelector(
    `[data-logic-correction="${hypothesisId}"]`,
  )?.value || null;
  try {
    await apiMutation(`/logic-chains/hypotheses/${hypothesisId}`, {
      method: "PATCH",
      body: JSON.stringify({
        status: decision,
        reviewer_note: i18n.language === "zh"
          ? "通过地图人工审核界面作出判断"
          : "Reviewed from the map interface",
        suggested_correction: correction,
      }),
    });
    state.logicChain = await api(`/logic-chains/${state.logicChain.cluster_job_id}`);
    renderLogicChains();
    render();
  } catch (error) {
    console.warn("logic hypothesis review failed", error);
  }
}

function renderList(markers) {
  const sorted = [...markers].sort(
    (left, right) => new Date(right.occurred_at) - new Date(left.occurred_at),
  );
  elements.eventList.innerHTML = sorted.slice(0, 200).map((marker) => {
    const style = markerStyle(marker);
    return `
      <button class="event-card" type="button" data-marker-id="${escapeHtml(marker.id)}">
        <span class="event-card-head">
          <i class="kind-dot ${style}"></i>
          <span class="event-kind">${escapeHtml(markerLabel(marker))}</span>
          <span class="event-score">${Math.round(marker.confidence * 100)}%</span>
        </span>
        <h3>${escapeHtml(marker.title)}</h3>
        ${marker.series_count > 1
          ? `<span class="series-badge">${marker.series_count} ${escapeHtml(i18n.t("map.waves"))}</span>`
          : ""}
        ${marker.is_conflict
          ? `<span class="conflict-role-badge">${
            escapeHtml(conflictRoleLabel(marker.conflict_zone_role))
          }</span>`
          : ""}
        <span class="event-meta">
          <span>${escapeHtml(marker.source_name)}</span>
          <span>${formatDate(marker.occurred_at)}</span>
        </span>
      </button>
    `;
  }).join("");
  elements.listEmpty.hidden = sorted.length > 0;
}

function renderPopup(marker) {
  return `
    <p class="popup-kind">${escapeHtml(markerLabel(marker))} · ${escapeHtml(humanize(marker.event_type))}</p>
    <h3 class="popup-title">${escapeHtml(marker.title)}</h3>
    <div class="popup-meta">
      ${escapeHtml(marker.source_name)}<br>
      ${escapeHtml(formatDate(marker.occurred_at))}<br>
      ${marker.country_code ? escapeHtml(marker.country_code) : ""}
      <br>${escapeHtml(markerPrecisionLabel(marker.geolocation_precision))}
    </div>
    ${renderImpact(marker.impact)}
    ${renderConflictAssessment(marker)}
    ${renderEarthquakeSeries(marker)}
    <a class="popup-link" href="${escapeAttribute(marker.source_url)}" target="_blank" rel="noreferrer">
      ${escapeHtml(i18n.t("map.sourceLink"))}
    </a>
  `;
}

function renderConflictAssessment(marker) {
  if (!marker.is_conflict) return "";
  const confidence = marker.theater_confidence === null
    || marker.theater_confidence === undefined
    ? ""
    : ` · ${Math.round(marker.theater_confidence * 100)}%`;
  const direction = marker.advance_direction
    ? `<br>${escapeHtml(i18n.t("map.reportedShift"))}: ${
      escapeHtml(marker.advance_direction)
    }`
    : "";
  return `
    <div class="conflict-assessment">
      <strong>${escapeHtml(conflictRoleLabel(marker.conflict_zone_role))}${
        confidence
      }</strong>
      ${direction}
      <br><small>${escapeHtml(i18n.t("map.conflictCaution"))}</small>
    </div>
  `;
}

function conflictRoleLabel(role) {
  if (role === "primary_theater") return i18n.t("map.conflictPrimary");
  if (role === "secondary_theater") return i18n.t("map.conflictSecondary");
  if (role === "reported_site") return i18n.t("map.conflictReported");
  return i18n.t("map.conflictUnlocated");
}

function renderEarthquakeSeries(marker) {
  if (!marker.series_events || marker.series_count <= 1) return "";
  const waves = [...marker.series_events].sort(
    (left, right) => new Date(left.occurred_at) - new Date(right.occurred_at),
  );
  return `
    <div class="earthquake-series">
      <strong>${escapeHtml(i18n.t("map.earthquakeSeries"))} · ${
        marker.series_count
      } ${escapeHtml(i18n.t("map.waves"))}</strong>
      <small>${escapeHtml(i18n.t("map.strongestWave"))}</small>
      <ol>
        ${waves.map((wave) => `
          <li>
            <time>${escapeHtml(formatDate(wave.occurred_at))}</time>
            <b>${wave.magnitude === null ? "M ?" : `M ${wave.magnitude.toFixed(1)}`}</b>
            <span>${escapeHtml(wave.title.replace(/^M\s*\d+(?:\.\d+)?\s*-\s*/i, ""))}</span>
          </li>
        `).join("")}
      </ol>
    </div>
  `;
}

function markerPrecisionLabel(precision) {
  if (precision === "country") return i18n.t("map.countryReference");
  if (precision === "admin1") return i18n.t("map.admin1EventReference");
  if (precision === "city") return i18n.t("map.cityEventReference");
  return i18n.t("map.exactLocation");
}

function renderImpact(impact) {
  if (!impact) return "";
  const rows = [];
  if (impact.fatalities_best !== null) {
    rows.push(
      `${i18n.language === "zh" ? "死亡" : "Fatalities"}: ${impact.fatalities_best}`,
    );
  } else if (
    impact.fatalities_low !== null
    || impact.fatalities_high !== null
  ) {
    rows.push(
      `${i18n.language === "zh" ? "死亡区间" : "Fatality range"}: `
      + `${impact.fatalities_low ?? "?"}–${impact.fatalities_high ?? "?"}`,
    );
  }
  if (impact.injured_low !== null || impact.injured_high !== null) {
    rows.push(
      `${i18n.language === "zh" ? "受伤区间" : "Injury range"}: `
      + `${impact.injured_low ?? "?"}–${impact.injured_high ?? "?"}`,
    );
  }
  if (
    impact.economic_loss_low !== null
    || impact.economic_loss_high !== null
  ) {
    rows.push(
      `${i18n.language === "zh" ? "经济损失" : "Economic loss"}: `
      + `${impact.economic_loss_low ?? "?"}–${impact.economic_loss_high ?? "?"} `
      + `${impact.economic_loss_currency}`,
    );
  }
  return rows.length
    ? `<div class="popup-impact">${rows.map(escapeHtml).join("<br>")}</div>`
    : "";
}

function markerStyle(marker) {
  if (marker.is_conflict) return "conflict";
  if (marker.kind === "canonical") return "canonical";
  return marker.review_category === "review" ? "review" : "candidate";
}

function markerColor(marker) {
  if (marker.conflict_zone_role === "primary_theater") return "#ff3b33";
  if (marker.conflict_zone_role === "secondary_theater") return "#ff8f3d";
  if (marker.is_conflict) return "#ef6f66";
  if (marker.kind === "canonical") return "#79c7b6";
  return marker.review_category === "review" ? "#e7b95b" : "#83aedd";
}

function markerLabel(marker) {
  if (marker.series_count > 1) return i18n.t("map.earthquakeSeries");
  if (marker.is_conflict) {
    return conflictRoleLabel(marker.conflict_zone_role);
  }
  if (marker.kind === "canonical") return i18n.t("map.canonicalLabel");
  return marker.review_category === "review"
    ? i18n.t("map.reviewLabel")
    : i18n.t("map.candidateLabel");
}

function humanize(value) {
  return String(value).replaceAll("_", " ");
}

function formatDate(value) {
  return new Intl.DateTimeFormat(
    i18n.language === "zh" ? "zh-CN" : "en-CA",
    {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    },
  ).format(new Date(value));
}

function showMapError(message) {
  elements.mapError.textContent = message;
  elements.mapError.hidden = false;
}

async function api(path) {
  const response = await fetch(path);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

async function apiMutation(path, options) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }
  if (response.status === 204) return null;
  return response.json().catch(() => null);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  const text = String(value ?? "");
  if (!/^https?:\/\//i.test(text)) return "#";
  return escapeHtml(text);
}
