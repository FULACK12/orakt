"use strict";

const i18n = window.NewsI18n;

i18n.register({
  zh: {
    "audit.aiStateTitle": "AI 数据链与升级状态",
    "audit.aiStateNotice": "分开显示新增链、增强数据核验、版本变化与真实再训练；审核信号不等于模型已经训练。",
    "audit.newChains": "过去 24 小时新增逻辑链",
    "audit.chainInventory": "正式逻辑链总量",
    "audit.pendingReview": "待审核或待补证据",
    "audit.enhancedValidation": "增强数据核验",
    "audit.enhancedValidationDetail": "保存了来源或实际数据项的验证链",
    "audit.modelUpgrade": "模型与推理链版本",
    "audit.modelCurrent": "当前版本已投入生成",
    "audit.modelUpgradeDetected": "检测到版本升级记录",
    "audit.modelChangePending": "配置已变化，等待新链验证",
    "audit.modelNoHistory": "尚无链条版本记录",
    "audit.runtimeModel": "当前运行模型",
    "audit.lastChainModel": "最近链使用模型",
    "audit.promptVersion": "逻辑提示版本",
    "audit.appVersion": "应用版本",
    "audit.trainingState": "增强数据再训练",
    "audit.trainingConfirmed": "已确认再训练",
    "audit.trainingSignalsReady": "已积累信号，尚未再训练",
    "audit.trainingNoSignals": "尚无训练信号",
    "audit.trainingManifestInvalid": "训练产物记录无效",
    "audit.reviewSignals": "人工审核信号",
    "audit.signalsUsed": "已用于训练",
    "audit.signalsPending": "待用于训练",
    "audit.verifiedMemory": "可直接检索的验证记忆",
    "audit.externalPending": "外部数据待审核",
    "audit.externalApproved": "外部数据已批准",
    "audit.datasetReady": "训练集可用样本",
    "audit.trainingRun": "训练批次",
    "audit.trainedAt": "训练时间",
    "audit.latestActivity": "最近活动",
    "audit.latestChain": "逻辑链生成",
    "audit.latestValidation": "因果核验",
    "audit.latestEvidence": "研究证据快照",
    "audit.latestClusterJob": "最新完成聚类任务",
    "audit.latestLogicJob": "最新有输出的逻辑链任务",
    "audit.logicRefreshPending": "待补跑逻辑链任务",
    "audit.logicRefreshState": "全文分析同步状态",
    "audit.logicRefreshCurrent": "已同步",
    "audit.logicRefreshWaiting": "等待本地模型",
    "audit.logicRefreshRetrying": "失败后重试中",
    "audit.researchRuns": "已完成研究",
    "audit.chainsSinceTraining": "上次训练后新增",
    "audit.statusSnapshot": "状态快照",
    "audit.noTimestamp": "尚无记录",
    "audit.trainingBoundary": "这里的“已再训练”只由可审计模型产物确认；重新验证只更新证据和置信度，不会自动修改模型权重。",
    "audit.title": "AI 因子研究与核验工作台",
    "audit.description": "本地模型分析新闻全文、保留线性证据链并挖掘非线性交互因子；时序回测和本地审计检验盈利证据，人工负责最终复核。",
    "audit.workspaceReport": "查验报告",
    "audit.workspaceFactor": "因子挖掘",
    "audit.workspaceEvidence": "证据核验",
    "audit.workspaceNews": "新闻分析",
    "audit.contextTitle": "当前查验对象",
    "audit.contextNotice": "四个工作区始终使用同一份报告；默认只渲染最新报告以降低页面内存占用。",
    "audit.contextSelect": "选择报告",
    "audit.contextAll": "加载最近 4 份完整报告（较高内存）",
    "audit.contextEmpty": "暂无可选择的报告",
    "audit.contextLoading": "正在按需读取报告全文…",
    "audit.contextLocal": "本地模型",
    "audit.contextCreated": "生成时间",
    "audit.catalogSearch": "公司、代码或关键词",
    "audit.catalogSearchPlaceholder": "例如：LULU、美光、流动性",
    "audit.catalogMarket": "市场",
    "audit.catalogAllMarkets": "全部市场",
    "audit.catalogUS": "美股",
    "audit.catalogChina": "A股",
    "audit.catalogStatus": "状态",
    "audit.catalogAllStatuses": "全部状态",
    "audit.catalogFrom": "起始日期",
    "audit.catalogTo": "结束日期",
    "audit.catalogReset": "重置",
    "audit.catalogApply": "确定",
    "audit.catalogShare": "复制当前视图链接",
    "audit.catalogCopied": "当前筛选、报告和分区链接已复制",
    "audit.catalogCopyFailed": "无法自动复制，请从浏览器地址栏复制当前网址",
    "audit.catalogPage": "页",
    "audit.catalogReports": "份报告",
    "audit.alertTitle": "公司证据升级与降级提醒",
    "audit.alertNotice": "比较每家公司最近两期轻量快照；监控优先级不是股票评级，也不证明变化之间存在因果。",
    "audit.alertLoading": "正在计算跨期重大变化…",
    "audit.alertFailed": "重大变化提醒读取失败",
    "audit.alertEmpty": "当前筛选下没有公司变化提醒。",
    "audit.alertCompanies": "家公司有至少两期报告",
    "audit.alertShown": "条提醒",
    "audit.alertAll": "全部变化",
    "audit.alertUpgrades": "证据升级",
    "audit.alertDowngrades": "证据降级",
    "audit.alertUpgrade": "证据质量升级",
    "audit.alertDowngrade": "证据质量降级",
    "audit.alertMixed": "证据混合变化",
    "audit.alertRefresh": "参数与行情刷新",
    "audit.alertPriority": "监控优先级",
    "audit.alertCritical": "极高变化",
    "audit.alertHigh": "高变化",
    "audit.alertMedium": "中等变化",
    "audit.alertLow": "低变化",
    "audit.alertLatest": "最新",
    "audit.alertPrevious": "上一期",
    "audit.alertOpen": "查验最新完整报告",
    "audit.alertEvidenceBoundary": "升级/降级描述的是证据质量，不代表买入或卖出评级。",
    "audit.comparisonTitle": "同公司多期报告对比",
    "audit.comparisonNotice": "只读取轻量快照，对比结论、置信度、证据与条件价位变化；点选某一期后才加载完整报告。",
    "audit.comparisonLoading": "正在读取同公司历史快照…",
    "audit.comparisonUnavailable": "当前报告没有可识别的公司代码，无法建立同公司时间序列。",
    "audit.comparisonSingle": "这是该公司当前唯一可用报告；后续版本生成后会自动加入对比。",
    "audit.comparisonVersions": "历史版本",
    "audit.comparisonSelected": "当前报告",
    "audit.comparisonOpen": "加载完整报告",
    "audit.comparisonConfidence": "链条置信度",
    "audit.comparisonReadiness": "数据完整度",
    "audit.comparisonEvidence": "可审计证据",
    "audit.comparisonCitations": "实际引用",
    "audit.comparisonVerified": "已验证环节",
    "audit.comparisonUnresolved": "未解决环节",
    "audit.comparisonSignal": "综合信号",
    "audit.comparisonTiming": "时点判断",
    "audit.comparisonRiskReward": "条件盈亏比",
    "audit.comparisonEntry": "入场参考",
    "audit.comparisonStop": "止损参考",
    "audit.comparisonTarget": "目标参考",
    "audit.comparisonNewEvidence": "新增引用证据",
    "audit.comparisonRetiredEvidence": "退出引用证据",
    "audit.comparisonEvidenceDetails": "展开实际引用证据变化",
    "audit.comparisonAdded": "本期新增引用",
    "audit.comparisonRemoved": "本期退出引用",
    "audit.comparisonShowing": "为控制流量，最多显示前 8 条",
    "audit.comparisonNoEvidenceChanges": "与上一期相比没有可识别的证据身份变化。",
    "audit.changeSummaryTitle": "本期为什么发生变化",
    "audit.changeSummaryNotice": "以下仅解释两期数据与引用差异，不证明这些变化之间存在因果关系。",
    "audit.changeAddedMix": "新增引用构成",
    "audit.changeRetiredMix": "退出引用构成",
    "audit.changeSignal": "综合信号变化",
    "audit.changeTiming": "时点判断变化",
    "audit.changeCurrentPrice": "观察价格变化",
    "audit.changeRiskReward": "条件盈亏比变化",
    "audit.changeVerified": "已验证环节变化",
    "audit.changeUnresolved": "未解决环节变化",
    "audit.changeModel": "本期使用了不同的本地模型版本",
    "audit.changeAudit": "本地审计状态发生变化",
    "audit.changeConclusion": "结论文字已根据本期证据重新生成",
    "audit.changeNoMaterial": "未检测到可解释的结构性变化。",
    "audit.comparisonNoValue": "未形成",
    "audit.comparisonFailed": "历史对比读取失败",
    "audit.signalBullish": "偏多",
    "audit.signalBearish": "偏空",
    "audit.signalMixed": "混合",
    "audit.signalUnknown": "未知",
    "audit.reportWorkspaceTitle": "查验报告",
    "audit.reportWorkspaceNotice": "提问、生成、阅读并审核完整报告；因子、证据和新闻推演已归入各自工作区。",
    "audit.factorWorkspaceTitle": "因子挖掘",
    "audit.factorWorkspaceNotice": "集中查看候选因子、非线性交互、样本外回测、行业与大盘基准，以及防未来数据泄漏检查。",
    "audit.factorExperimentTitle": "真实因子实验区",
    "audit.factorExperimentNotice": "只有通过互不重叠重复回测、FDR 校正、交易成本和置信区间门槛的因子，才会冻结并等待未来数据验证。",
    "audit.factorExperimentSettle": "结算已成熟未来样本",
    "audit.factorExperimentLoading": "正在读取冻结实验与未来结果…",
    "audit.factorExperimentEmpty": "尚无因子通过严格重复试验；未通过的候选不会进入未来验证池。",
    "audit.factorExperimentTotal": "冻结实验",
    "audit.factorExperimentPending": "等待未来数据",
    "audit.factorExperimentPassed": "未来验证通过",
    "audit.factorExperimentFailed": "未来验证失败",
    "audit.factorExperimentGroups": "同规格未来样本组",
    "audit.factorExperimentMatured": "成熟样本",
    "audit.factorExperimentHit": "未来命中率",
    "audit.factorExperimentMean": "平均策略收益",
    "audit.factorExperimentAwaiting": "等待未来样本",
    "audit.factorExperimentInsufficient": "未来样本不足",
    "audit.factorExperimentRetained": "未来复现通过",
    "audit.factorExperimentRejected": "未来复现失败",
    "audit.factorExperimentPosition": "冻结方向",
    "audit.factorExperimentAnchor": "冻结日期",
    "audit.factorExperimentSettled": "成熟未来样本已结算",
    "audit.replicationTitle": "独立重复试验",
    "audit.replicationNotice": "每轮重新选因，测试窗口互不重叠；结果不允许倒改原参数。",
    "audit.replicationTrials": "有效试验",
    "audit.replicationPasses": "通过试验",
    "audit.replicationMedian": "超额收益中位数",
    "audit.replicationCI": "逐期超额收益 90% 区间",
    "audit.replicationStable": "稳定因子",
    "audit.replicationRetained": "初步保留，等待未来验证",
    "audit.replicationRejected": "淘汰",
    "audit.replicationInsufficient": "证据不足",
    "audit.newsWorkspaceTitle": "新闻分析",
    "audit.newsWorkspaceNotice": "按事件和时间串联全文新闻，区分事实、推断和后续验证，并走查每条新闻发生后的可能结果。",
    "audit.subState": "AI 状态",
    "audit.subSecEvidence": "SEC 证据",
    "audit.subCausal": "因果链",
    "audit.subData": "数据与来源",
    "audit.noFactorResults": "当前报告尚无可展示的因子研究结果。",
    "audit.noEvidenceResults": "当前报告尚无可展示的逐报告证据核验结果。",
    "audit.noNewsResults": "当前报告尚无可展示的新闻序列或预测结果。",
    "audit.localModel": "本地研究模型",
    "audit.openaiReview": "OpenAI 手动第二意见",
    "audit.fixedRelations": "人工固定证据",
    "audit.trainingSignals": "审核训练信号",
    "audit.ready": "已就绪",
    "audit.notConfigured": "未配置",
    "audit.researchTitle": "AI 因子挖掘、研究与复核闭环",
    "audit.researchNotice": "本地 AI 先选择有限事件窗口、补全证据并完成报告审计；OpenAI 自动复核当前关闭，需要时可手动请求第二意见。",
    "audit.batchTitle": "批量研究与报告审计",
    "audit.batchNotice": "单模型串行生成；美股使用 SEC 数值证据，A 股当前只生成行情/因子与证据缺口报告。",
    "audit.createBatch": "创建美股+A股小批次",
    "audit.queueAudits": "审计历史报告",
    "audit.batchEmpty": "尚无批量研究任务。",
    "audit.auditQueueEmpty": "历史报告审计队列为空。",
    "audit.batchCreated": "研究批次已入队",
    "audit.auditsQueued": "历史报告已按冻结证据入队审计",
    "audit.retryBatch": "重试失败标的",
    "audit.scopeUS": "SEC数值+证据缺口",
    "audit.scopeChina": "A股行情/因子审计",
    "audit.queueQueued": "排队",
    "audit.queueRunning": "运行中",
    "audit.queueCompleted": "完成",
    "audit.queueFailed": "失败",
    "audit.queuePartial": "部分失败",
    "audit.queueSuperseded": "源报告已变化",
    "audit.frozenAudit": "冻结证据审计",
    "audit.question": "研究问题",
    "audit.questionAssistantNotice": "只需用日常语言提问。系统会自动补成财务、估值、宏观、供应链、灾害与反证等可审计维度。",
    "audit.exampleEquity": "示例：苹果还能涨吗？",
    "audit.exampleEvent": "示例：油价为什么涨？",
    "audit.exampleRisk": "示例：公司有哪些风险？",
    "audit.questionExpanded": "普通问题已自动补全",
    "audit.originalQuestion": "你的原始问题",
    "audit.expandedBrief": "系统实际核验范围",
    "audit.plainReport": "通俗版报告",
    "audit.directionalSupport": "方向证据链支持度",
    "audit.notProbability": "这不是上涨概率，也不是买入建议。",
    "audit.professionalTerms": "专业数据集通俗解释",
    "audit.scoreBlockers": "主要扣分项",
    "audit.howImprove": "提高可信度需要",
    "audit.questionPlaceholder": "例如：科技股是否还会涨？哪些电力、芯片、矿产、政策、冲突或灾害因素可能改变结论？",
    "audit.startResearch": "本地 AI 开始研究",
    "audit.autonomousResearch": "让 AI 自主提出问题",
    "audit.researchIdle": "等待研究问题。",
    "audit.researchRequired": "请输入至少 6 个字符的研究问题。",
    "audit.researchRunning": "本地 AI 正在检索证据并拆解问题…",
    "audit.autonomousRunning": "本地 AI 正在提出可证伪问题并查找证据…",
    "audit.researchCompleted": "研究闭环已完成；请查看事件窗口、OpenAI 复核、本地修订和最终确认。",
    "audit.researchFailed": "研究失败",
    "audit.noResearch": "暂无研究记录。输入问题，或让本地 AI 从近期证据中自主提出问题。",
    "audit.modelBoundary": "模型边界",
    "audit.modelBoundaryNotice": "本地 AI 负责选取事件窗口、初稿、证据补全和报告审计；OpenAI 仅在手动请求时提供第二意见；人工最终决定是否固定为知识链。",
    "audit.workflow": "研究闭环",
    "audit.episodeWindow": "因果事件窗口",
    "audit.historyContext": "长期历史仅作基线，不扩展事件窗口",
    "audit.localDraft": "本地初稿",
    "audit.openaiAudit": "OpenAI 方向/证据复核",
    "audit.localRevision": "本地按反馈修订",
    "audit.localEpisodeRepair": "历史事件证据护栏修订",
    "audit.finalEvidenceGuard": "最终证据落盘护栏",
    "audit.evidenceGapSearch": "按证据缺口再次检索",
    "audit.localEvidenceRevision": "本地按新增证据重写",
    "audit.openaiConfirmation": "OpenAI 最终确认",
    "audit.bridgeEvidenceCompletion": "桥接证据补全",
    "audit.factorMiningStage": "样本外因子挖掘",
    "audit.localReportAudit": "本地报告审计",
    "audit.retrievalTitle": "问题定向证据检索",
    "audit.retrievalPasses": "检索轮次",
    "audit.retrievalAdded": "新增证据",
    "audit.retrievalAvailable": "可用证据",
    "audit.retrievalRefs": "指定证据命中",
    "audit.retrievalSeries": "相关市场序列",
    "audit.newsSequences": "连续新闻证据链",
    "audit.newsSequencesNotice": "按主题与时间串联同一事件的连续报道；时间先后不是因果结论，仍需因果验证。",
    "audit.initialReport": "首条报道",
    "audit.followUpReport": "后续证据",
    "audit.latestReport": "最新进展",
    "audit.sourceText": "有来源正文",
    "audit.leadOnly": "仅检索线索",
    "audit.citedInChain": "已被报告逻辑链引用",
    "audit.coldEvidence": "完整正文从 F 盘读取",
    "audit.paperReport": "论文式研究报告",
    "audit.paperAbstract": "摘要",
    "audit.paperMethod": "方法",
    "audit.paperEvidenceChain": "证据链",
    "audit.paperFindings": "研究结果",
    "audit.paperAlternatives": "替代解释",
    "audit.paperLimitations": "局限",
    "audit.paperConclusion": "结论",
    "audit.newsForecasts": "逐新闻可能性与走查验证",
    "audit.forecastNotice": "预测以新闻时间为信息截止点；后续新闻和市场数据由独立本地验证器回填，历史事件明确标为走查测试。",
    "audit.forecastMechanism": "推演链",
    "audit.forecastOutcome": "预期结果",
    "audit.forecastFalsifiers": "证伪条件",
    "audit.forecastHorizon": "预测窗口",
    "audit.forecastLive": "实时前瞻",
    "audit.forecastBacktest": "历史走查",
    "audit.forecastUnresolved": "等待后续数据",
    "audit.forecastCandidate": "找到候选证据",
    "audit.forecastSupported": "后续证据支持",
    "audit.forecastPartial": "部分支持",
    "audit.forecastContradicted": "后续证据反驳",
    "audit.forecastExpired": "到期但证据不足",
    "audit.supportingEvidence": "加强证据",
    "audit.contradictingEvidence": "反驳证据",
    "audit.refreshForecasts": "用后续数据走查预测",
    "audit.forecastRefreshing": "本地 AI 正在检索后续新闻和市场数据并走查预测…",
    "audit.forecastRefreshed": "预测走查完成",
    "audit.factorResearch": "AI 因子挖掘",
    "audit.factorNotice": "双轨研究：原线性证据链继续保留，另行挖掘阈值、交互与状态切换关系。",
    "audit.factorCandidates": "候选因子",
    "audit.nonlinearLinks": "非线性因子图",
    "audit.bridgeVariables": "桥接变量",
    "audit.linearSubchains": "可核验线性子链",
    "audit.relationshipClass": "关系级别",
    "audit.profitValidation": "样本外盈利验证",
    "audit.factorRemine": "用最新数据重新挖掘",
    "audit.factorMining": "正在用本地数据重新挖掘因子并执行时序回测…",
    "audit.factorMined": "因子挖掘与样本外验证已更新",
    "audit.factorDirection": "方向",
    "audit.factorLag": "滞后",
    "audit.factorHorizon": "验证周期",
    "audit.factorOperator": "组合方式",
    "audit.factorTarget": "验证目标",
    "audit.factorTrain": "训练样本",
    "audit.factorTest": "样本外样本",
    "audit.factorStrategyReturn": "策略收益",
    "audit.factorBaselineReturn": "基准收益",
    "audit.factorExcessReturn": "超额收益",
    "audit.factorHitRate": "方向命中率",
    "audit.factorDrawdown": "最大回撤",
    "audit.factorCost": "交易成本",
    "audit.factorLeakageGuard": "防未来数据泄漏",
    "audit.factorArchive": "机械盘研究产物",
    "audit.factorInsufficient": "数据不足",
    "audit.factorExploratory": "探索性",
    "audit.factorPositive": "样本外为正",
    "audit.factorNegative": "样本外未通过",
    "audit.crossSectionValidation": "多资产横截面检验",
    "audit.crossUniverse": "共同资产池",
    "audit.crossAssets": "有效资产",
    "audit.crossTrainRebalances": "训练期再平衡",
    "audit.crossTestRebalances": "样本外再平衡",
    "audit.crossTopReturn": "最高分组收益",
    "audit.crossBottomReturn": "最低分组收益",
    "audit.crossLongShort": "多空组合收益",
    "audit.crossEqualReturn": "等权基准收益",
    "audit.crossTopExcess": "最高组超额",
    "audit.crossSharpe": "多空 Sharpe-like",
    "audit.crossExposures": "资产暴露与最新分组",
    "audit.crossScore": "最新分数",
    "audit.crossLoading": "训练期载荷",
    "audit.bucketLong": "做多组",
    "audit.bucketShort": "做空组",
    "audit.bucketNeutral": "中间组",
    "audit.bucketUnavailable": "当前不可用",
    "audit.factorPValue": "训练 p 值",
    "audit.factorQValue": "FDR q 值",
    "audit.robustValidation": "滚动中性化稳健检验",
    "audit.robustNotice": "只保留通过多重检验校正的因子，并用可获得的历史滚动重估。",
    "audit.robustWindow": "滚动训练窗口",
    "audit.robustReestimate": "重估间隔",
    "audit.robustCandidateTests": "候选检验数",
    "audit.robustPassed": "FDR 通过因子",
    "audit.robustGroups": "中性化分组",
    "audit.robustLongShort": "稳健多空收益",
    "audit.robustRawLongShort": "原始多空收益",
    "audit.robustBucket": "稳健分组",
    "audit.neutralizationGroup": "中性化组",
    "audit.assetCoverage": "资产池覆盖",
    "audit.assetCategoryMix": "资产类别构成",
    "audit.pendingAssets": "待同步资产",
    "audit.survivorshipTitle": "历史资产池与幸存者偏差审计",
    "audit.survivorshipSurvivorOnly": "仅现存资产，仍有偏差",
    "audit.survivorshipPartial": "已纳入部分历史资产",
    "audit.survivorshipAudited": "逐时点生命周期已核验",
    "audit.pointInTimeRule": "逐时点准入",
    "audit.historicalAssets": "历史/退市资产",
    "audit.discoveredDelisted": "目录发现退市资产",
    "audit.localDelistedPrices": "已有本地历史价格",
    "audit.missingDelistedPrices": "仍缺历史价格",
    "audit.priceBackfillQueue": "价格补齐队列",
    "audit.priceBackfillPending": "待抓取",
    "audit.priceFactorReady": "因子检验可用",
    "audit.pricePartial": "价格不足60期",
    "audit.priceUnavailable": "来源无数据",
    "audit.priceTickerReuse": "代码复用已拦截",
    "audit.identityVerified": "跨源身份已核验",
    "audit.identityPending": "身份待确认",
    "audit.identityMismatch": "身份冲突已隔离",
    "audit.identityLifecycleConflict": "SEC 生命周期冲突已隔离",
    "audit.identityCik": "已关联 SEC CIK",
    "audit.terminalVerified": "退市终值已核验",
    "audit.terminalPending": "退市终值待证据",
    "audit.terminalEvidenceSearched": "SEC 终值证据已检索",
    "audit.terminalEvidenceCik": "SEC 公司身份已定位",
    "audit.terminalEvidenceMetadata": "候选申报文件",
    "audit.terminalEvidenceValues": "已提取数值候选",
    "audit.terminalEvidenceReview": "数值候选待审核",
    "audit.terminalEvidenceContact": "正文等待项目联系邮箱",
    "audit.terminalEvidenceLifecycle": "终止文件早于价格末端",
    "audit.mobileSecReview": "SEC 审核",
    "audit.mobileResearch": "AI 研究",
    "audit.mobileCausal": "因果链",
    "audit.mobileData": "数据状态",
    "audit.secEvidenceTitle": "SEC 退市与并购证据审核",
    "audit.secEvidenceNotice": "审核最终现金对价、历史报价和换股价值；只有身份与价格序列通过安全门后，接受的终值才能写入因子资产池。",
    "audit.secEvidenceLoading": "正在读取 SEC 证据候选…",
    "audit.secEvidenceLoaded": "SEC 证据队列已更新",
    "audit.secEvidenceFailed": "SEC 证据读取失败",
    "audit.lifecycleEmpty": "尚无人工确认的生命周期纠错",
    "audit.providerRecord": "供应商记录",
    "audit.authoritativeRecord": "权威核验",
    "audit.providerConflictActive": "供应商误报 · 仍在交易",
    "audit.adrProgramTerminated": "ADR 项目终止",
    "audit.bankruptcyPending": "破产回收待最终确认",
    "audit.liquidationPending": "分期清算尚未结束",
    "audit.verifiedDelisted": "退市已确认",
    "audit.bankruptcyFinal": "破产回收已终结",
    "audit.liquidationFinal": "清算分配已终结",
    "audit.secFilterPending": "待审核",
    "audit.secFilterAll": "全部",
    "audit.secFilterAccepted": "已接受",
    "audit.secFilterDeferred": "待补证据",
    "audit.secAssets": "涉及资产",
    "audit.secFilings": "候选申报",
    "audit.secValues": "数值证据",
    "audit.secPending": "待人工审核",
    "audit.secTerminalAccepted": "终局证据",
    "audit.secSupportingAccepted": "支持证据",
    "audit.secLifecycleSegmented": "SEC 锚定行情段",
    "audit.secBodyAccess": "正文访问",
    "audit.secReady": "已就绪",
    "audit.secBlocked": "未就绪",
    "audit.secNoCandidates": "当前筛选条件下没有数值证据候选。",
    "audit.secIdentity": "身份门",
    "audit.secOutcome": "终值状态",
    "audit.secFactorGate": "因子池资格",
    "audit.secFactorReady": "可写入因子池",
    "audit.secFactorBlocked": "暂不可写入",
    "audit.secIdentityBlocked": "跨源身份尚未核验或存在生命周期冲突，证据可审核但不得进入因子池。",
    "audit.secPriceBlocked": "历史价格序列尚未就绪，暂不能计算退市收益。",
    "audit.secAlreadyVerified": "该资产终值已经核验并进入因子资产池。",
    "audit.secTerminalEvidenceBlocked": "尚未接受可直接定价的终局证据，历史报价和拟议对价只能作为支持证据。",
    "audit.secReviewNote": "填写接受、驳回或需要补充证据的理由（至少 10 个字符）…",
    "audit.secAcceptTerminal": "接受为终局证据",
    "audit.secAcceptSupporting": "接受为支持证据",
    "audit.secNeedEvidence": "需要更多证据",
    "audit.secReject": "驳回",
    "audit.secReviewSaved": "审核结果已保存",
    "audit.secReviewFailed": "证据审核失败",
    "audit.secSource": "打开 SEC 原文",
    "audit.secConfidence": "提取置信度",
    "audit.secFinalCash": "最终现金对价",
    "audit.secHistoricalOffer": "历史/谈判报价",
    "audit.secImpliedStock": "换股隐含每股价值",
    "audit.secExchangeRatio": "换股比例",
    "audit.secAcquirerPrice": "收购方完成日价格",
    "audit.secZeroRecovery": "普通股零回收声明",
    "audit.secLiquidationDistribution": "清算分配/股",
    "audit.secAdrDistribution": "ADR 终止分配/股",
    "audit.secEvidenceDate": "事实日期",
    "audit.secSubject": "证据主体",
    "audit.secPossibleWorthless": "可能归零",
    "audit.secStatusCandidate": "待审核",
    "audit.secStatusAccepted": "已接受",
    "audit.secStatusRejected": "已驳回",
    "audit.secStatusDeferred": "待补证据",
    "audit.secRoleTerminal": "终局证据",
    "audit.secRoleSupporting": "支持证据",
    "audit.secPaymentDate": "付款/交割日期",
    "audit.secOutcomeType": "交易类型",
    "audit.secCashAcquisition": "现金收购",
    "audit.secStockAcquisition": "换股收购",
    "audit.secAddFactor": "确认终值并加入因子池",
    "audit.secFactorAdded": "终值已核验，退市收益已写入因子资产池",
    "audit.secFactorFailed": "终值写入失败",
    "audit.secAuditAcceptedTerminal": "已接受终局证据",
    "audit.secAuditAcceptedSupporting": "已接受支持证据",
    "audit.lifecycleCatalogRange": "生命周期目录范围",
    "audit.explicitLifecycle": "明确生命周期",
    "audit.delistingReturnCoverage": "退市收益覆盖",
    "audit.eligibleRange": "样本外可用资产范围",
    "audit.knownGaps": "已知偏差与缺口",
    "audit.attributionTitle": "稳健多空收益贡献归因",
    "audit.attributionNotice": "按每次真实持仓链接到复合收益；资产类别、行业和地区分别与组合总收益核对。",
    "audit.attributionReconciled": "归因已对账",
    "audit.attributionUnreconciled": "归因未对账",
    "audit.contribution": "贡献",
    "audit.longPeriods": "进入做多期数",
    "audit.shortPeriods": "进入做空期数",
    "audit.reportReview": "人工审核报告",
    "audit.reportReviewNote": "填写修改意见、遗漏证据或审核理由…",
    "audit.reportReviewRecorded": "报告审核已记录",
    "audit.eventTableTitle": "自主研究事件表",
    "audit.eventTableNotice": "先按年度核对五类证据与媒体覆盖，再从最早且尚未使用的全面年份选题；较早年份只作对照，本年度只监测。",
    "audit.reliableStart": "全面数据研究起点",
    "audit.structuredStart": "结构化历史比较起点",
    "audit.crossDomainStart": "五类数据交叉对照起点",
    "audit.reliableEnd": "最近完整结论期",
    "audit.mediaRichStart": "媒体广覆盖起点",
    "audit.newsSources": "新闻来源",
    "audit.crossDomainOnly": "五类对照",
    "audit.structuredOnly": "结构化对照",
    "audit.preferredPeriod": "本轮优先事件期",
    "audit.coverageScore": "覆盖分",
    "audit.evidenceDomains": "证据域",
    "audit.fullDocuments": "正文",
    "audit.marketSeries": "市场序列",
    "audit.companyTickers": "公司",
    "audit.researchReady": "可研究",
    "audit.monitorOnly": "仅监测",
    "audit.viewEventTable": "展开年度覆盖表",
    "audit.workflowCompleted": "闭环完成",
    "audit.workflowLocalAudited": "本地审计已完成 · OpenAI 自动复核已关闭",
    "audit.workflowNeedsReview": "仍需人工复核",
    "audit.workflowFailed": "复核阶段未完成",
    "audit.stageCompleted": "已完成",
    "audit.stageSkipped": "按设置跳过",
    "audit.stagePending": "等待中",
    "audit.stageFailed": "失败",
    "audit.autoReviewDisabled": "自动复核已关闭，可手动请求",
    "audit.userQuestion": "用户问题",
    "audit.aiQuestion": "AI 自主问题",
    "audit.evidenceGaps": "仍需补充的证据",
    "audit.verified": "已验证",
    "audit.partial": "部分支持",
    "audit.missing": "证据不足",
    "audit.hypothesis": "待验证假设",
    "audit.scopeCompanies": "公司",
    "audit.scopeSectors": "行业",
    "audit.scopeInputs": "资源/投入",
    "audit.scopeInfrastructure": "基础设施",
    "audit.scopeGeographies": "地理风险",
    "audit.chatgptReview": "请求 ChatGPT 二次复核",
    "audit.chatgptRunning": "ChatGPT 正在核对证据和推导…",
    "audit.chatgptComplete": "OpenAI 第二意见已返回。",
    "audit.chatgptReviewed": "已完成第二意见",
    "audit.chatgptUnavailable": "OpenAI 未配置",
    "audit.secondOpinion": "OpenAI 最终确认",
    "audit.revisedSummary": "建议修订后的结论",
    "audit.evidenceTitle": "证据链、逻辑链与因果验证",
    "audit.validateLogic": "重新验证现有逻辑",
    "audit.generateLogic": "生成并验证新逻辑",
    "audit.eventRelations": "事件证据关系",
    "audit.humanOnly": "仅人工接受后固定",
    "audit.logicHypotheses": "AI 多步逻辑与验证记录",
    "audit.logicAuditHint": "逐步核验，不把时间相关性冒充因果",
    "audit.noRelations": "当前聚类任务没有待固定的事件关系。",
    "audit.noLogic": "当前尚无逻辑链。可以点击“生成并验证新逻辑”。",
    "audit.fixedCount": "条已固定",
    "audit.trainingCount": "条审核信号",
    "audit.evidenceDocuments": "证据文档",
    "audit.pinEvidence": "人工接受并固定",
    "audit.fixedEvidence": "已固定",
    "audit.temporalSuggestion": "时间顺序建议",
    "audit.responseCue": "报道中存在响应线索",
    "audit.generating": "本地 AI 正在生成并验证逻辑…",
    "audit.validating": "因果验证 Agent 正在重新检索证据…",
    "audit.logicUpdated": "逻辑链和因果验证已更新。",
    "audit.compositeScore": "综合",
    "audit.associationScore": "关联",
    "audit.evidenceCoverage": "证据覆盖",
    "audit.relevance": "关联度",
    "audit.counterevidence": "反证与替代解释",
    "audit.correctionPlaceholder": "填写修改意见或应补充的证据…",
    "audit.accept": "接受",
    "audit.reviseAccept": "修改后接受",
    "audit.defer": "暂缓",
    "audit.reject": "驳回",
    "audit.statusSuggested": "待审核",
    "audit.statusAccepted": "已接受",
    "audit.statusRevised": "修改后接受",
    "audit.statusDeferred": "等待证据",
    "audit.statusRejected": "已驳回",
    "audit.reportedEvent": "已报道事件",
    "audit.economicContext": "经济背景",
    "audit.marketObservation": "市场观测",
    "audit.inferredMechanism": "推断机制",
    "audit.possibleOutcome": "可能结果",
    "audit.causalValidator": "因果验证 Agent",
    "audit.recalculatedConfidence": "验证后置信度",
    "audit.validationWindow": "核验时间窗",
    "audit.hours": "小时",
    "audit.confidenceBreakdown": "置信度组成",
    "audit.originalConfidence": "原始置信度",
    "audit.weightedGateScore": "验证门加权分",
    "audit.conclusionCap": "结论安全上限",
    "audit.weight": "权重",
    "audit.causalFlow": "因果链可视化",
    "audit.validationSources": "实际核验数据源",
    "audit.observations": "项观测",
    "audit.citedEvidence": "实际引用的数据项",
    "audit.usedBy": "用于检查",
    "audit.contextOnly": "仅作背景，未用于本次结论",
    "audit.reasoningTrace": "推理与核验日志",
    "audit.validationSummary": "本次核验总结",
    "audit.missingEvidence": "具体缺失证据",
    "audit.noMissing": "没有发现结构性证据缺口。",
    "audit.nextEvidence": "建议下一步补充的数据",
    "audit.historicalCases": "历史相似案例",
    "audit.reviewerRecommendation": "审核建议",
    "audit.checkPremise": "前提事件",
    "audit.checkTiming": "结果与时间窗",
    "audit.checkMechanism": "中间传导机制",
    "audit.checkExpectations": "市场预期",
    "audit.checkAlternatives": "替代解释",
    "audit.checkSufficiency": "因果充分性",
    "audit.checkPassed": "已验证",
    "audit.checkPartial": "部分支持",
    "audit.checkMissing": "证据不足",
    "audit.checkFailed": "未通过",
    "audit.checkNA": "不适用",
    "audit.causalTemporal": "仅确认时间相关",
    "audit.causalPartial": "传导机制部分支持",
    "audit.causalSupported": "机制得到支持，但不足以证明因果",
    "audit.dataTitle": "数据源、模型与 API 核对",
    "audit.openApiDocs": "打开完整 API 文档",
    "audit.credentials": "数据访问状态",
    "audit.credentialsNotice": "只显示是否已配置，不显示任何令牌值。",
    "audit.routing": "核验职责分工",
    "audit.routingLocal": "提出假设与初稿",
    "audit.routingLocalValue": "本地 AI",
    "audit.routingValidator": "因果步骤核验",
    "audit.routingValidatorValue": "本地因果验证 Agent",
    "audit.routingOpenAI": "方向、证据与最终确认",
    "audit.routingOpenAIValue": "OpenAI Responses API",
    "audit.routingHuman": "最终固定与训练信号",
    "audit.routingHumanValue": "人工审核记录",
    "audit.configured": "已配置",
    "audit.required": "需要凭证",
    "audit.loadFailed": "AI 核验数据读取失败",
    "audit.requestFailed": "请求失败",
    "audit.coverageTitle": "数据时间覆盖与完整度",
    "audit.coverageNotice": "区分“已配置接口”和“已在本地保存的数据”，明确显示起止时间、时间戳完整度及缺口。",
    "audit.sourceCoverage": "查看各新闻源覆盖区间",
    "audit.coverageComplete": "完整",
    "audit.coveragePartial": "部分",
    "audit.coverageStale": "已过期",
    "audit.coverageMissing": "缺失",
    "audit.coverageRecords": "条记录",
    "audit.coverageTimestamp": "时间戳",
    "audit.coverageContent": "正文/摘要",
    "audit.coverageHeadlineOnly": "仅标题",
    "audit.dataAuditTitle": "数据质量与证券覆盖报告",
    "audit.dataAuditNotice": "核对实际入库数据，不以已配置接口代替数据可用性。",
    "audit.archiveDataAudit": "生成并存档报告",
    "audit.archivingDataAudit": "正在生成完整报告…",
    "audit.dataAuditArchived": "完整数据报告已生成",
    "audit.dataAuditAbnormal": "查看异常或不可验证序列",
    "audit.auditSeries": "数值序列",
    "audit.auditObservations": "观测值",
    "audit.auditChinaLeaders": "A股行业龙头",
    "audit.auditUsEquities": "美股公司",
    "audit.auditSuspicious": "异常序列",
    "audit.auditUnusable": "禁止验证",
    "audit.auditCompanyPriceCoverage": "美股价格覆盖",
    "audit.auditHeadlineBacklog": "仅标题积压",
    "audit.auditNeverAttempted": "尚未回填",
    "audit.auditRetryableNow": "当前可重试",
    "audit.auditPermanentBlocked": "来源永久阻止",
    "audit.auditEvidenceCompletion": "最近证据补全",
    "audit.auditCandidateSegments": "有候选数据",
    "audit.auditRejectedSegments": "异常被拒绝",
    "audit.auditMissingSegments": "仍缺数据",
    "audit.auditNoCompletion": "最近研究尚未运行新版证据补全",
    "audit.evidenceCompleter": "证据补全器",
    "audit.evidenceCompleterNotice": "逐段匹配本地数值序列；候选数据存在不等于因果成立。",
    "audit.evidenceCandidateFound": "已找到候选数据",
    "audit.evidencePartial": "部分可用",
    "audit.evidenceMissing": "缺少数据",
    "audit.evidenceRejected": "异常数据已拒绝",
    "audit.evidenceCanVerify": "可参与验证",
    "audit.evidenceBlocked": "质量门控拒绝",
    "audit.chinaSectorLeaders": "A股行业十大综合龙头",
    "audit.usSectorUniverse": "美股板块覆盖",
    "audit.cycleModels": "经济周期模型",
    "audit.modelConfidence": "模型数据完整度",
    "audit.modelExpansion": "扩张信号",
    "audit.modelTransition": "过渡/分歧",
    "audit.modelContraction": "收缩信号",
    "audit.coverageUnknown": "未形成区间",
    "audit.cycleTitle": "美国经济周期模型",
    "audit.cycleExpansion": "扩张",
    "audit.cycleLate": "后周期",
    "audit.cycleSlowdown": "放缓",
    "audit.cycleContraction": "收缩/衰退",
    "audit.cycleRecovery": "复苏",
    "audit.cycleInsufficient": "数据不足",
    "audit.cycleAsOf": "截至",
    "audit.companyUniverse": "美国大型公司财报与股价",
    "audit.companySource": "SEC 原始申报 · Twelve Data 日线",
    "audit.companyPrice": "最新股价",
    "audit.companyFiling": "最新申报",
    "audit.companyFact": "最新财务指标",
    "audit.companyPending": "等待首次同步",
    "audit.equityDimensions": "股票五维研究",
    "audit.fundamentals_valuation": "基本面与估值",
    "audit.technicals_positioning": "技术形态与资金定位",
    "audit.macro_liquidity": "宏观与流动性",
    "audit.supply_chain_geopolitics": "供应链与地缘风险",
    "audit.technology_competition": "技术与竞争护城河",
    "audit.signalBullish": "偏多",
    "audit.signalBearish": "偏空",
    "audit.signalMixed": "混合",
    "audit.signalUnknown": "证据不足",
    "audit.decisionFramework": "条件式入场与失效框架",
    "audit.entryConditions": "进入观察区的条件",
    "audit.invalidationConditions": "结论失效条件",
    "audit.monitoringIndicators": "持续监测指标",
    "audit.valuationScenarios": "估值情景",
    "audit.researchDisclaimer": "研究辅助，不构成个性化投资建议",
  },
  en: {
    "audit.aiStateTitle": "AI chain and upgrade status",
    "audit.aiStateNotice": "Separates new chains, enhanced-data validation, version changes, and actual retraining. Review signals do not mean the model has been trained.",
    "audit.newChains": "New logic chains in 24 hours",
    "audit.chainInventory": "Formal logic chains",
    "audit.pendingReview": "Awaiting review or evidence",
    "audit.enhancedValidation": "Enhanced-data validation",
    "audit.enhancedValidationDetail": "Validated chains retaining sources or cited data facts",
    "audit.modelUpgrade": "Model and reasoning-chain version",
    "audit.modelCurrent": "Current version is in use",
    "audit.modelUpgradeDetected": "Version upgrade history detected",
    "audit.modelChangePending": "Configuration changed; awaiting a new chain",
    "audit.modelNoHistory": "No chain version history yet",
    "audit.runtimeModel": "Runtime model",
    "audit.lastChainModel": "Latest chain model",
    "audit.promptVersion": "Logic prompt version",
    "audit.appVersion": "Application version",
    "audit.trainingState": "Enhanced-data retraining",
    "audit.trainingConfirmed": "Retraining confirmed",
    "audit.trainingSignalsReady": "Signals collected; not retrained",
    "audit.trainingNoSignals": "No training signals yet",
    "audit.trainingManifestInvalid": "Training artifact record is invalid",
    "audit.reviewSignals": "Human review signals",
    "audit.signalsUsed": "Used in training",
    "audit.signalsPending": "Pending training",
    "audit.verifiedMemory": "Retrievable verified memory",
    "audit.externalPending": "External data pending",
    "audit.externalApproved": "External data approved",
    "audit.datasetReady": "Training-ready examples",
    "audit.trainingRun": "Training run",
    "audit.trainedAt": "Trained at",
    "audit.latestActivity": "Latest activity",
    "audit.latestChain": "Logic chain generated",
    "audit.latestValidation": "Causal validation",
    "audit.latestEvidence": "Research evidence snapshot",
    "audit.latestClusterJob": "Latest completed cluster job",
    "audit.latestLogicJob": "Latest job with retained chains",
    "audit.logicRefreshPending": "Logic refresh jobs pending",
    "audit.logicRefreshState": "Full-text analysis sync",
    "audit.logicRefreshCurrent": "Current",
    "audit.logicRefreshWaiting": "Waiting for local model",
    "audit.logicRefreshRetrying": "Retrying after failure",
    "audit.researchRuns": "Completed research runs",
    "audit.chainsSinceTraining": "New since last training",
    "audit.statusSnapshot": "Status snapshot",
    "audit.noTimestamp": "No record yet",
    "audit.trainingBoundary": "Retrained is confirmed only by an auditable model artifact. Revalidation updates evidence and confidence; it does not automatically change model weights.",
    "audit.title": "AI Factor Research and Audit Workspace",
    "audit.description": "The local model reads retained full-text news, preserves linear evidence chains and mines nonlinear factor interactions. Chronological tests and local audit evaluate profitability evidence before human review.",
    "audit.workspaceReport": "Report review",
    "audit.workspaceFactor": "Factor mining",
    "audit.workspaceEvidence": "Evidence validation",
    "audit.workspaceNews": "News analysis",
    "audit.contextTitle": "Current research target",
    "audit.contextNotice": "All four workspaces stay synchronized to the same report. Only the newest report is rendered by default to reduce browser memory use.",
    "audit.contextSelect": "Select report",
    "audit.contextAll": "Load the latest 4 full reports (higher memory)",
    "audit.contextEmpty": "No reports available",
    "audit.contextLoading": "Loading the selected full report on demand…",
    "audit.contextLocal": "Local model",
    "audit.contextCreated": "Created",
    "audit.catalogSearch": "Company, ticker or keyword",
    "audit.catalogSearchPlaceholder": "e.g. LULU, Micron, liquidity",
    "audit.catalogMarket": "Market",
    "audit.catalogAllMarkets": "All markets",
    "audit.catalogUS": "U.S.",
    "audit.catalogChina": "China A-shares",
    "audit.catalogStatus": "Status",
    "audit.catalogAllStatuses": "All statuses",
    "audit.catalogFrom": "From",
    "audit.catalogTo": "To",
    "audit.catalogReset": "Reset",
    "audit.catalogApply": "Apply",
    "audit.catalogShare": "Copy current view link",
    "audit.catalogCopied": "The current filters, report and workspace link were copied",
    "audit.catalogCopyFailed": "Automatic copy failed. Copy the current URL from the browser address bar.",
    "audit.catalogPage": "Page",
    "audit.catalogReports": "reports",
    "audit.alertTitle": "Company evidence upgrade and downgrade alerts",
    "audit.alertNotice": "Compares each company's two latest compact snapshots. Monitoring priority is not a stock rating and does not prove causality among changes.",
    "audit.alertLoading": "Calculating material cross-version changes…",
    "audit.alertFailed": "Report-change alerts failed to load",
    "audit.alertEmpty": "No company-change alerts match this filter.",
    "audit.alertCompanies": "companies have at least two reports",
    "audit.alertShown": "alerts shown",
    "audit.alertAll": "All changes",
    "audit.alertUpgrades": "Evidence upgrades",
    "audit.alertDowngrades": "Evidence downgrades",
    "audit.alertUpgrade": "Evidence quality upgraded",
    "audit.alertDowngrade": "Evidence quality downgraded",
    "audit.alertMixed": "Mixed evidence change",
    "audit.alertRefresh": "Parameter and market refresh",
    "audit.alertPriority": "Monitoring priority",
    "audit.alertCritical": "Critical change",
    "audit.alertHigh": "High change",
    "audit.alertMedium": "Medium change",
    "audit.alertLow": "Low change",
    "audit.alertLatest": "Latest",
    "audit.alertPrevious": "Previous",
    "audit.alertOpen": "Review latest full report",
    "audit.alertEvidenceBoundary": "Upgrade or downgrade refers to evidence quality, not a buy or sell rating.",
    "audit.comparisonTitle": "Same-company report history",
    "audit.comparisonNotice": "Loads compact snapshots only to compare conclusions, confidence, evidence and conditional price references. A full report is fetched only after selection.",
    "audit.comparisonLoading": "Loading same-company report snapshots…",
    "audit.comparisonUnavailable": "This report has no identifiable company ticker, so a same-company timeline cannot be built.",
    "audit.comparisonSingle": "This is the only available report for the company. Later versions will appear here automatically.",
    "audit.comparisonVersions": "versions",
    "audit.comparisonSelected": "Selected report",
    "audit.comparisonOpen": "Load full report",
    "audit.comparisonConfidence": "Chain confidence",
    "audit.comparisonReadiness": "Data readiness",
    "audit.comparisonEvidence": "Auditable evidence",
    "audit.comparisonCitations": "Citations used",
    "audit.comparisonVerified": "Verified links",
    "audit.comparisonUnresolved": "Unresolved links",
    "audit.comparisonSignal": "Overall signal",
    "audit.comparisonTiming": "Timing assessment",
    "audit.comparisonRiskReward": "Conditional R/R",
    "audit.comparisonEntry": "Entry reference",
    "audit.comparisonStop": "Stop reference",
    "audit.comparisonTarget": "Target reference",
    "audit.comparisonNewEvidence": "New cited evidence",
    "audit.comparisonRetiredEvidence": "Retired cited evidence",
    "audit.comparisonEvidenceDetails": "Expand cited-evidence changes",
    "audit.comparisonAdded": "Newly cited this version",
    "audit.comparisonRemoved": "No longer cited",
    "audit.comparisonShowing": "Up to the first 8 items are shown to limit transfer size",
    "audit.comparisonNoEvidenceChanges": "No identifiable evidence-identity changes versus the prior version.",
    "audit.changeSummaryTitle": "Why this version changed",
    "audit.changeSummaryNotice": "These items explain data and citation differences between versions; they do not prove causal relationships among the changes.",
    "audit.changeAddedMix": "New citation mix",
    "audit.changeRetiredMix": "Retired citation mix",
    "audit.changeSignal": "Overall signal change",
    "audit.changeTiming": "Timing assessment change",
    "audit.changeCurrentPrice": "Observed price change",
    "audit.changeRiskReward": "Conditional R/R change",
    "audit.changeVerified": "Verified-link change",
    "audit.changeUnresolved": "Unresolved-link change",
    "audit.changeModel": "A different local model version was used",
    "audit.changeAudit": "The local audit status changed",
    "audit.changeConclusion": "The conclusion text was regenerated from this version's evidence",
    "audit.changeNoMaterial": "No explainable structural change was detected.",
    "audit.comparisonNoValue": "Unavailable",
    "audit.comparisonFailed": "Report history failed to load",
    "audit.signalBullish": "Bullish",
    "audit.signalBearish": "Bearish",
    "audit.signalMixed": "Mixed",
    "audit.signalUnknown": "Unknown",
    "audit.reportWorkspaceTitle": "Report review",
    "audit.reportWorkspaceNotice": "Ask, generate, read and review complete reports. Factors, evidence and news projections now live in their own workspaces.",
    "audit.factorWorkspaceTitle": "Factor mining",
    "audit.factorWorkspaceNotice": "Review candidate factors, nonlinear interactions, out-of-sample tests, market and sector benchmarks, and look-ahead leakage controls in one place.",
    "audit.factorExperimentTitle": "Real factor experiment lab",
    "audit.factorExperimentNotice": "A factor is frozen for future validation only after non-overlapping replications, FDR control, trading costs and a confidence-interval gate.",
    "audit.factorExperimentSettle": "Settle matured future samples",
    "audit.factorExperimentLoading": "Loading frozen experiments and future outcomes…",
    "audit.factorExperimentEmpty": "No factor has passed strict replication yet. Failed candidates do not enter the future-validation pool.",
    "audit.factorExperimentTotal": "Frozen experiments",
    "audit.factorExperimentPending": "Awaiting future data",
    "audit.factorExperimentPassed": "Future validations passed",
    "audit.factorExperimentFailed": "Future validations failed",
    "audit.factorExperimentGroups": "Identical prospective cohorts",
    "audit.factorExperimentMatured": "Matured samples",
    "audit.factorExperimentHit": "Prospective hit rate",
    "audit.factorExperimentMean": "Mean strategy return",
    "audit.factorExperimentAwaiting": "Awaiting future samples",
    "audit.factorExperimentInsufficient": "Insufficient future samples",
    "audit.factorExperimentRetained": "Prospectively retained",
    "audit.factorExperimentRejected": "Prospectively rejected",
    "audit.factorExperimentPosition": "Frozen direction",
    "audit.factorExperimentAnchor": "Frozen date",
    "audit.factorExperimentSettled": "Matured future samples settled",
    "audit.replicationTitle": "Independent replications",
    "audit.replicationNotice": "Factors are reselected in every trial, test windows do not overlap, and outcomes cannot rewrite original parameters.",
    "audit.replicationTrials": "Valid trials",
    "audit.replicationPasses": "Passed trials",
    "audit.replicationMedian": "Median excess return",
    "audit.replicationCI": "90% period-excess interval",
    "audit.replicationStable": "Stable factors",
    "audit.replicationRetained": "Provisionally retained; awaiting future validation",
    "audit.replicationRejected": "Rejected",
    "audit.replicationInsufficient": "Insufficient evidence",
    "audit.newsWorkspaceTitle": "News analysis",
    "audit.newsWorkspaceNotice": "Connect full-text reports by event and time, separate fact from inference, and walk each forecast forward against later evidence.",
    "audit.subState": "AI state",
    "audit.subSecEvidence": "SEC evidence",
    "audit.subCausal": "Causal chains",
    "audit.subData": "Data and sources",
    "audit.noFactorResults": "The current reports do not contain factor research results yet.",
    "audit.noEvidenceResults": "The current reports do not contain report-level evidence validation yet.",
    "audit.noNewsResults": "The current reports do not contain news sequences or forecasts yet.",
    "audit.localModel": "Local research model",
    "audit.openaiReview": "Manual OpenAI second opinion",
    "audit.fixedRelations": "Human-fixed evidence",
    "audit.trainingSignals": "Review training signals",
    "audit.ready": "Ready",
    "audit.notConfigured": "Not configured",
    "audit.researchTitle": "AI factor mining, research and review loop",
    "audit.researchNotice": "Local AI selects a bounded episode, completes evidence and audits the report. Automatic OpenAI review is off; a second opinion remains available on request.",
    "audit.batchTitle": "Batch research and report audit",
    "audit.batchNotice": "One local model runs serially. US reports use SEC numeric evidence; China reports currently cover market/factor evidence and explicit gaps only.",
    "audit.createBatch": "Create small US + China batch",
    "audit.queueAudits": "Audit historical reports",
    "audit.batchEmpty": "No batch research task yet.",
    "audit.auditQueueEmpty": "The historical report audit queue is empty.",
    "audit.batchCreated": "Research batch queued",
    "audit.auditsQueued": "Historical reports queued with frozen evidence",
    "audit.retryBatch": "Retry failed targets",
    "audit.scopeUS": "SEC numeric + evidence gaps",
    "audit.scopeChina": "China market/factor audit",
    "audit.queueQueued": "Queued",
    "audit.queueRunning": "Running",
    "audit.queueCompleted": "Completed",
    "audit.queueFailed": "Failed",
    "audit.queuePartial": "Partially failed",
    "audit.queueSuperseded": "Source report changed",
    "audit.frozenAudit": "Frozen-evidence audit",
    "audit.question": "Research question",
    "audit.questionAssistantNotice": "Ask in everyday language. The system automatically expands it into auditable financial, valuation, macro, supply-chain, hazard and counter-evidence checks.",
    "audit.exampleEquity": "Example: Can Apple keep rising?",
    "audit.exampleEvent": "Example: Why did oil rise?",
    "audit.exampleRisk": "Example: What are the risks?",
    "audit.questionExpanded": "Plain question automatically expanded",
    "audit.originalQuestion": "Your original question",
    "audit.expandedBrief": "Scope actually checked",
    "audit.plainReport": "Plain-language report",
    "audit.directionalSupport": "Directional-chain support",
    "audit.notProbability": "This is not an upside probability or a buy recommendation.",
    "audit.professionalTerms": "Professional datasets in plain language",
    "audit.scoreBlockers": "Main score constraints",
    "audit.howImprove": "Evidence needed to improve confidence",
    "audit.questionPlaceholder": "Example: Can technology stocks keep rising, and which power, chip, mineral, policy, conflict or disaster constraints could change the answer?",
    "audit.startResearch": "Research with local AI",
    "audit.autonomousResearch": "Let AI propose a question",
    "audit.researchIdle": "Waiting for a research question.",
    "audit.researchRequired": "Enter a research question of at least six characters.",
    "audit.researchRunning": "Local AI is retrieving evidence and decomposing the question…",
    "audit.autonomousRunning": "Local AI is proposing a falsifiable question and finding evidence…",
    "audit.researchCompleted": "The research loop is complete. Inspect the episode, OpenAI audit, local revision and final confirmation.",
    "audit.researchFailed": "Research failed",
    "audit.noResearch": "No research record yet. Enter a question or let local AI propose one from recent evidence.",
    "audit.modelBoundary": "Model boundary",
    "audit.modelBoundaryNotice": "Local AI selects the episode, drafts, completes evidence and audits the report. OpenAI provides a second opinion only when requested. A human decides whether to fix the result as knowledge.",
    "audit.workflow": "Research loop",
    "audit.episodeWindow": "Causal episode window",
    "audit.historyContext": "Long history is baseline context only",
    "audit.localDraft": "Local draft",
    "audit.openaiAudit": "OpenAI direction/evidence audit",
    "audit.localRevision": "Local feedback revision",
    "audit.localEpisodeRepair": "Historical episode grounding repair",
    "audit.finalEvidenceGuard": "Final evidence persistence guard",
    "audit.evidenceGapSearch": "Search declared evidence gaps",
    "audit.localEvidenceRevision": "Local rewrite with new evidence",
    "audit.openaiConfirmation": "OpenAI final confirmation",
    "audit.bridgeEvidenceCompletion": "Bridge evidence completion",
    "audit.factorMiningStage": "Out-of-sample factor mining",
    "audit.localReportAudit": "Local report audit",
    "audit.retrievalTitle": "Question-directed evidence retrieval",
    "audit.retrievalPasses": "Search passes",
    "audit.retrievalAdded": "New evidence",
    "audit.retrievalAvailable": "Available evidence",
    "audit.retrievalRefs": "Required references found",
    "audit.retrievalSeries": "Relevant market series",
    "audit.newsSequences": "Connected news evidence chains",
    "audit.newsSequencesNotice": "Reports about the same episode are linked by topic and time. Chronology is not a causal conclusion and still requires validation.",
    "audit.initialReport": "Initial report",
    "audit.followUpReport": "Follow-up evidence",
    "audit.latestReport": "Latest development",
    "audit.sourceText": "Source text retained",
    "audit.leadOnly": "Discovery lead only",
    "audit.citedInChain": "Cited by the report chain",
    "audit.coldEvidence": "Full text read from F drive",
    "audit.paperReport": "Paper-style research report",
    "audit.paperAbstract": "Abstract",
    "audit.paperMethod": "Methodology",
    "audit.paperEvidenceChain": "Evidence chain",
    "audit.paperFindings": "Findings",
    "audit.paperAlternatives": "Alternative explanations",
    "audit.paperLimitations": "Limitations",
    "audit.paperConclusion": "Conclusion",
    "audit.newsForecasts": "Per-news possibilities and walk-forward validation",
    "audit.forecastNotice": "Each news timestamp is an information cutoff. A separate local validator later adds news and market evidence; historical episodes are clearly marked as walk-forward tests.",
    "audit.forecastMechanism": "Mechanism path",
    "audit.forecastOutcome": "Expected outcome",
    "audit.forecastFalsifiers": "Falsification conditions",
    "audit.forecastHorizon": "Forecast horizon",
    "audit.forecastLive": "Live prospective",
    "audit.forecastBacktest": "Historical walk-forward",
    "audit.forecastUnresolved": "Awaiting later data",
    "audit.forecastCandidate": "Candidate evidence found",
    "audit.forecastSupported": "Supported by later evidence",
    "audit.forecastPartial": "Partially supported",
    "audit.forecastContradicted": "Contradicted by later evidence",
    "audit.forecastExpired": "Expired; insufficient evidence",
    "audit.supportingEvidence": "Supporting evidence",
    "audit.contradictingEvidence": "Contradicting evidence",
    "audit.refreshForecasts": "Validate forecasts with later data",
    "audit.forecastRefreshing": "Local AI is retrieving later news and market data…",
    "audit.forecastRefreshed": "Forecast walk-forward completed",
    "audit.factorResearch": "AI factor mining",
    "audit.factorNotice": "Dual-track research keeps the original linear evidence chain while mining thresholds, interactions and regime switches separately.",
    "audit.factorCandidates": "Candidate factors",
    "audit.nonlinearLinks": "Nonlinear factor graph",
    "audit.bridgeVariables": "Bridge variables",
    "audit.linearSubchains": "Falsifiable linear subchains",
    "audit.relationshipClass": "Relationship class",
    "audit.profitValidation": "Out-of-sample profit validation",
    "audit.factorRemine": "Re-mine with latest data",
    "audit.factorMining": "The local system is re-mining factors and running chronological tests…",
    "audit.factorMined": "Factor mining and out-of-sample validation updated",
    "audit.factorDirection": "Direction",
    "audit.factorLag": "Lag",
    "audit.factorHorizon": "Horizon",
    "audit.factorOperator": "Operator",
    "audit.factorTarget": "Validation target",
    "audit.factorTrain": "Training samples",
    "audit.factorTest": "Out-of-sample samples",
    "audit.factorStrategyReturn": "Strategy return",
    "audit.factorBaselineReturn": "Baseline return",
    "audit.factorExcessReturn": "Excess return",
    "audit.factorHitRate": "Directional hit rate",
    "audit.factorDrawdown": "Maximum drawdown",
    "audit.factorCost": "Transaction cost",
    "audit.factorLeakageGuard": "Look-ahead leakage guard",
    "audit.factorArchive": "Mechanical-drive artifact",
    "audit.factorInsufficient": "Insufficient data",
    "audit.factorExploratory": "Exploratory",
    "audit.factorPositive": "Positive out of sample",
    "audit.factorNegative": "Failed out of sample",
    "audit.crossSectionValidation": "Cross-sectional multi-asset test",
    "audit.crossUniverse": "Shared asset universe",
    "audit.crossAssets": "Eligible assets",
    "audit.crossTrainRebalances": "Training rebalances",
    "audit.crossTestRebalances": "Out-of-sample rebalances",
    "audit.crossTopReturn": "Top-bucket return",
    "audit.crossBottomReturn": "Bottom-bucket return",
    "audit.crossLongShort": "Long-short return",
    "audit.crossEqualReturn": "Equal-weight benchmark",
    "audit.crossTopExcess": "Top-bucket excess",
    "audit.crossSharpe": "Long-short Sharpe-like",
    "audit.crossExposures": "Asset exposures and latest buckets",
    "audit.crossScore": "Latest score",
    "audit.crossLoading": "Training loadings",
    "audit.bucketLong": "Long bucket",
    "audit.bucketShort": "Short bucket",
    "audit.bucketNeutral": "Middle bucket",
    "audit.bucketUnavailable": "Currently unavailable",
    "audit.factorPValue": "Training p-value",
    "audit.factorQValue": "FDR q-value",
    "audit.robustValidation": "Rolling neutralized robustness test",
    "audit.robustNotice": "Keeps only multiple-testing-adjusted factors and re-estimates from available rolling history.",
    "audit.robustWindow": "Rolling training window",
    "audit.robustReestimate": "Re-estimation interval",
    "audit.robustCandidateTests": "Candidate tests",
    "audit.robustPassed": "FDR-passing factors",
    "audit.robustGroups": "Neutralization groups",
    "audit.robustLongShort": "Robust long-short return",
    "audit.robustRawLongShort": "Raw long-short return",
    "audit.robustBucket": "Robust bucket",
    "audit.neutralizationGroup": "Neutralization group",
    "audit.assetCoverage": "Asset-universe coverage",
    "audit.assetCategoryMix": "Asset category mix",
    "audit.pendingAssets": "Assets pending history",
    "audit.survivorshipTitle": "Historical universe and survivorship audit",
    "audit.survivorshipSurvivorOnly": "Survivors only; bias remains",
    "audit.survivorshipPartial": "Partial historical assets included",
    "audit.survivorshipAudited": "Point-in-time lifecycles audited",
    "audit.pointInTimeRule": "Point-in-time eligibility",
    "audit.historicalAssets": "Historical/delisted assets",
    "audit.discoveredDelisted": "Discovered delisted assets",
    "audit.localDelistedPrices": "Local historical prices",
    "audit.missingDelistedPrices": "Missing historical prices",
    "audit.priceBackfillQueue": "Price backfill queue",
    "audit.priceBackfillPending": "Pending retrieval",
    "audit.priceFactorReady": "Factor-ready",
    "audit.pricePartial": "Under 60 periods",
    "audit.priceUnavailable": "Provider unavailable",
    "audit.priceTickerReuse": "Ticker reuse blocked",
    "audit.identityVerified": "Cross-source identity verified",
    "audit.identityPending": "Identity pending",
    "audit.identityMismatch": "Identity conflict quarantined",
    "audit.identityLifecycleConflict": "SEC lifecycle conflict quarantined",
    "audit.identityCik": "SEC CIK linked",
    "audit.terminalVerified": "Terminal value verified",
    "audit.terminalPending": "Terminal evidence pending",
    "audit.terminalEvidenceSearched": "SEC terminal evidence searched",
    "audit.terminalEvidenceCik": "SEC company identity resolved",
    "audit.terminalEvidenceMetadata": "Candidate SEC filings",
    "audit.terminalEvidenceValues": "Extracted value candidates",
    "audit.terminalEvidenceReview": "Value candidates awaiting review",
    "audit.terminalEvidenceContact": "Full text awaits project contact email",
    "audit.terminalEvidenceLifecycle": "Terminal filing predates price-series end",
    "audit.mobileSecReview": "SEC review",
    "audit.mobileResearch": "AI research",
    "audit.mobileCausal": "Causal chains",
    "audit.mobileData": "Data status",
    "audit.secEvidenceTitle": "SEC delisting and transaction evidence review",
    "audit.secEvidenceNotice": "Review final cash terms, historical offers and stock consideration. Accepted terminal values enter the factor universe only after identity and price-series safety gates pass.",
    "audit.secEvidenceLoading": "Loading SEC evidence candidates…",
    "audit.secEvidenceLoaded": "SEC evidence queue updated",
    "audit.secEvidenceFailed": "Could not load SEC evidence",
    "audit.lifecycleEmpty": "No reviewed lifecycle corrections yet",
    "audit.providerRecord": "Provider record",
    "audit.authoritativeRecord": "Authoritative review",
    "audit.providerConflictActive": "Provider conflict · still listed",
    "audit.adrProgramTerminated": "ADR program terminated",
    "audit.bankruptcyPending": "Bankruptcy recovery pending final confirmation",
    "audit.liquidationPending": "Staged liquidation remains open",
    "audit.verifiedDelisted": "Delisting verified",
    "audit.bankruptcyFinal": "Bankruptcy recovery finalized",
    "audit.liquidationFinal": "Liquidation distributions finalized",
    "audit.secFilterPending": "Pending",
    "audit.secFilterAll": "All",
    "audit.secFilterAccepted": "Accepted",
    "audit.secFilterDeferred": "Needs evidence",
    "audit.secAssets": "Assets searched",
    "audit.secFilings": "Candidate filings",
    "audit.secValues": "Value evidence",
    "audit.secPending": "Awaiting review",
    "audit.secTerminalAccepted": "Terminal evidence",
    "audit.secSupportingAccepted": "Supporting evidence",
    "audit.secLifecycleSegmented": "SEC-anchored price segments",
    "audit.secBodyAccess": "Full-text access",
    "audit.secReady": "Ready",
    "audit.secBlocked": "Not ready",
    "audit.secNoCandidates": "No value candidates match this filter.",
    "audit.secIdentity": "Identity gate",
    "audit.secOutcome": "Terminal status",
    "audit.secFactorGate": "Factor eligibility",
    "audit.secFactorReady": "Eligible for factor pool",
    "audit.secFactorBlocked": "Not yet eligible",
    "audit.secIdentityBlocked": "Cross-source identity is unresolved or has a lifecycle conflict. Evidence can be reviewed but cannot enter the factor pool.",
    "audit.secPriceBlocked": "The historical price series is not ready, so a delisting return cannot yet be calculated.",
    "audit.secAlreadyVerified": "The terminal value is already verified and included in the factor universe.",
    "audit.secTerminalEvidenceBlocked": "No directly valued terminal evidence has been accepted. Historical offers and proposed consideration remain supporting evidence only.",
    "audit.secReviewNote": "Explain why this evidence should be accepted, rejected or supplemented (at least 10 characters)…",
    "audit.secAcceptTerminal": "Accept as terminal",
    "audit.secAcceptSupporting": "Accept as supporting",
    "audit.secNeedEvidence": "Need more evidence",
    "audit.secReject": "Reject",
    "audit.secReviewSaved": "Evidence review saved",
    "audit.secReviewFailed": "Evidence review failed",
    "audit.secSource": "Open SEC filing",
    "audit.secConfidence": "Extraction confidence",
    "audit.secFinalCash": "Final cash consideration",
    "audit.secHistoricalOffer": "Historical / negotiated offer",
    "audit.secImpliedStock": "Implied stock consideration per share",
    "audit.secExchangeRatio": "Share exchange ratio",
    "audit.secAcquirerPrice": "Acquirer closing-date price",
    "audit.secZeroRecovery": "Zero common-equity recovery statement",
    "audit.secLiquidationDistribution": "Liquidation distribution/share",
    "audit.secAdrDistribution": "ADR termination distribution/share",
    "audit.secEvidenceDate": "Fact date",
    "audit.secSubject": "Evidence subject",
    "audit.secPossibleWorthless": "Possible worthlessness",
    "audit.secStatusCandidate": "Pending",
    "audit.secStatusAccepted": "Accepted",
    "audit.secStatusRejected": "Rejected",
    "audit.secStatusDeferred": "Needs evidence",
    "audit.secRoleTerminal": "Terminal evidence",
    "audit.secRoleSupporting": "Supporting evidence",
    "audit.secPaymentDate": "Payment / closing date",
    "audit.secOutcomeType": "Transaction type",
    "audit.secCashAcquisition": "Cash acquisition",
    "audit.secStockAcquisition": "Stock acquisition",
    "audit.secAddFactor": "Verify terminal value and add to factor pool",
    "audit.secFactorAdded": "Terminal value verified; delisting return added to the factor universe",
    "audit.secFactorFailed": "Could not write the terminal value",
    "audit.secAuditAcceptedTerminal": "Accepted terminal evidence",
    "audit.secAuditAcceptedSupporting": "Accepted supporting evidence",
    "audit.lifecycleCatalogRange": "Lifecycle catalog range",
    "audit.explicitLifecycle": "Explicit lifecycles",
    "audit.delistingReturnCoverage": "Delisting-return coverage",
    "audit.eligibleRange": "Eligible OOS asset range",
    "audit.knownGaps": "Known bias and gaps",
    "audit.attributionTitle": "Robust long-short contribution attribution",
    "audit.attributionNotice": "Links actual holdings each period to compounded return; asset class, industry and region reconcile separately.",
    "audit.attributionReconciled": "Attribution reconciled",
    "audit.attributionUnreconciled": "Attribution not reconciled",
    "audit.contribution": "Contribution",
    "audit.longPeriods": "Long periods",
    "audit.shortPeriods": "Short periods",
    "audit.reportReview": "Human report review",
    "audit.reportReviewNote": "Add corrections, missing evidence or review rationale…",
    "audit.reportReviewRecorded": "Report review recorded",
    "audit.eventTableTitle": "Autonomous research event table",
    "audit.eventTableNotice": "Five evidence domains and media breadth are checked by year first. Questions start with the earliest comprehensive unused period; earlier years are comparison-only and the open year is monitoring-only.",
    "audit.reliableStart": "Comprehensive research start",
    "audit.structuredStart": "Structured comparison start",
    "audit.crossDomainStart": "Five-domain comparison start",
    "audit.reliableEnd": "Latest complete conclusion period",
    "audit.mediaRichStart": "Broad media coverage start",
    "audit.newsSources": "News sources",
    "audit.crossDomainOnly": "Five-domain comparison",
    "audit.structuredOnly": "Structured comparison",
    "audit.preferredPeriod": "Preferred period for this run",
    "audit.coverageScore": "Coverage",
    "audit.evidenceDomains": "Evidence domains",
    "audit.fullDocuments": "Full text",
    "audit.marketSeries": "Market series",
    "audit.companyTickers": "Companies",
    "audit.researchReady": "Research-ready",
    "audit.monitorOnly": "Monitor only",
    "audit.viewEventTable": "Open yearly coverage table",
    "audit.workflowCompleted": "Loop complete",
    "audit.workflowLocalAudited": "Local audit complete · automatic OpenAI review is off",
    "audit.workflowNeedsReview": "Human review still required",
    "audit.workflowFailed": "Audit stage incomplete",
    "audit.stageCompleted": "Completed",
    "audit.stageSkipped": "Skipped by configuration",
    "audit.stagePending": "Pending",
    "audit.stageFailed": "Failed",
    "audit.autoReviewDisabled": "Automatic review is off; manual review remains available",
    "audit.userQuestion": "User question",
    "audit.aiQuestion": "AI-proposed question",
    "audit.evidenceGaps": "Evidence still needed",
    "audit.verified": "Verified",
    "audit.partial": "Partially supported",
    "audit.missing": "Evidence missing",
    "audit.hypothesis": "Unverified hypothesis",
    "audit.scopeCompanies": "Companies",
    "audit.scopeSectors": "Sectors",
    "audit.scopeInputs": "Resources/inputs",
    "audit.scopeInfrastructure": "Infrastructure",
    "audit.scopeGeographies": "Geospatial risk",
    "audit.chatgptReview": "Request ChatGPT second review",
    "audit.chatgptRunning": "ChatGPT is auditing evidence and reasoning…",
    "audit.chatgptComplete": "The OpenAI second opinion is ready.",
    "audit.chatgptReviewed": "Second review complete",
    "audit.chatgptUnavailable": "OpenAI not configured",
    "audit.secondOpinion": "OpenAI final confirmation",
    "audit.revisedSummary": "Suggested revised conclusion",
    "audit.evidenceTitle": "Evidence chains, logic chains and causal validation",
    "audit.validateLogic": "Revalidate existing logic",
    "audit.generateLogic": "Generate and validate new logic",
    "audit.eventRelations": "Event evidence relations",
    "audit.humanOnly": "Fixed only after human acceptance",
    "audit.logicHypotheses": "AI multi-step logic and validation records",
    "audit.logicAuditHint": "Validate every step; never present temporal association as causality",
    "audit.noRelations": "The current cluster job has no event relation awaiting review.",
    "audit.noLogic": "No logic chain is available. Select Generate and validate new logic.",
    "audit.fixedCount": "fixed",
    "audit.trainingCount": "review signals",
    "audit.evidenceDocuments": "Evidence documents",
    "audit.pinEvidence": "Accept and fix",
    "audit.fixedEvidence": "Fixed",
    "audit.temporalSuggestion": "Temporal suggestion",
    "audit.responseCue": "Reported response cue",
    "audit.generating": "Local AI is generating and validating logic…",
    "audit.validating": "The causal validator is refreshing evidence…",
    "audit.logicUpdated": "Logic chains and causal validation are updated.",
    "audit.compositeScore": "Composite",
    "audit.associationScore": "Association",
    "audit.evidenceCoverage": "Evidence coverage",
    "audit.relevance": "relevance",
    "audit.counterevidence": "Counterevidence and alternatives",
    "audit.correctionPlaceholder": "Enter a correction or evidence that should be added…",
    "audit.accept": "Accept",
    "audit.reviseAccept": "Revise & accept",
    "audit.defer": "Defer",
    "audit.reject": "Reject",
    "audit.statusSuggested": "Suggested",
    "audit.statusAccepted": "Accepted",
    "audit.statusRevised": "Revised and accepted",
    "audit.statusDeferred": "Waiting for evidence",
    "audit.statusRejected": "Rejected",
    "audit.reportedEvent": "Reported event",
    "audit.economicContext": "Economic context",
    "audit.marketObservation": "Market observation",
    "audit.inferredMechanism": "Inferred mechanism",
    "audit.possibleOutcome": "Possible outcome",
    "audit.causalValidator": "Causal validation agent",
    "audit.recalculatedConfidence": "Validated confidence",
    "audit.validationWindow": "Validation window",
    "audit.hours": "hours",
    "audit.confidenceBreakdown": "Confidence composition",
    "audit.originalConfidence": "Original confidence",
    "audit.weightedGateScore": "Weighted gate score",
    "audit.conclusionCap": "Conclusion safety cap",
    "audit.weight": "weight",
    "audit.causalFlow": "Causal-chain visualization",
    "audit.validationSources": "Sources actually checked",
    "audit.observations": "observations",
    "audit.citedEvidence": "Data items actually cited",
    "audit.usedBy": "Used by checks",
    "audit.contextOnly": "Context only; not cited by this conclusion",
    "audit.reasoningTrace": "Reasoning and validation trace",
    "audit.validationSummary": "Validation summary",
    "audit.missingEvidence": "Specific missing evidence",
    "audit.noMissing": "No structural evidence gap was found.",
    "audit.nextEvidence": "Recommended next evidence",
    "audit.historicalCases": "Comparable historical cases",
    "audit.reviewerRecommendation": "Reviewer recommendation",
    "audit.checkPremise": "Premise event",
    "audit.checkTiming": "Outcome and time window",
    "audit.checkMechanism": "Intermediate mechanism",
    "audit.checkExpectations": "Market expectations",
    "audit.checkAlternatives": "Alternative explanations",
    "audit.checkSufficiency": "Causal sufficiency",
    "audit.checkPassed": "Verified",
    "audit.checkPartial": "Partially supported",
    "audit.checkMissing": "Evidence missing",
    "audit.checkFailed": "Failed",
    "audit.checkNA": "Not applicable",
    "audit.causalTemporal": "Temporal association only",
    "audit.causalPartial": "Mechanism partially supported",
    "audit.causalSupported": "Mechanism supported, but causality not proven",
    "audit.dataTitle": "Data, model and API verification",
    "audit.openApiDocs": "Open full API documentation",
    "audit.credentials": "Data access status",
    "audit.credentialsNotice": "Only configuration state is shown; token values are never exposed.",
    "audit.routing": "Audit responsibilities",
    "audit.routingLocal": "Hypotheses and initial draft",
    "audit.routingLocalValue": "Local AI",
    "audit.routingValidator": "Causal-step validation",
    "audit.routingValidatorValue": "Local causal validation agent",
    "audit.routingOpenAI": "Direction, evidence and confirmation",
    "audit.routingOpenAIValue": "OpenAI Responses API",
    "audit.routingHuman": "Final fixing and training signals",
    "audit.routingHumanValue": "Human review record",
    "audit.configured": "Configured",
    "audit.required": "Credential required",
    "audit.loadFailed": "Could not load AI audit data",
    "audit.requestFailed": "Request failed",
    "audit.coverageTitle": "Data time coverage and completeness",
    "audit.coverageNotice": "Separates configured access from locally retained data and exposes time ranges, timestamp quality and known gaps.",
    "audit.sourceCoverage": "Inspect coverage for every news source",
    "audit.coverageComplete": "Complete",
    "audit.coveragePartial": "Partial",
    "audit.coverageStale": "Stale",
    "audit.coverageMissing": "Missing",
    "audit.coverageRecords": "records",
    "audit.coverageTimestamp": "timestamps",
    "audit.coverageContent": "content/snippet",
    "audit.coverageHeadlineOnly": "headline only",
    "audit.dataAuditTitle": "Data quality and equity coverage report",
    "audit.dataAuditNotice": "Audits retained rows; configured access is not treated as usable data.",
    "audit.archiveDataAudit": "Generate and archive report",
    "audit.archivingDataAudit": "Generating the full report…",
    "audit.dataAuditArchived": "Full data report generated",
    "audit.dataAuditAbnormal": "Inspect abnormal or unusable series",
    "audit.auditSeries": "Numeric series",
    "audit.auditObservations": "Observations",
    "audit.auditChinaLeaders": "A-share sector leaders",
    "audit.auditUsEquities": "US equities",
    "audit.auditSuspicious": "Flagged series",
    "audit.auditUnusable": "Blocked from validation",
    "audit.auditCompanyPriceCoverage": "US price coverage",
    "audit.auditHeadlineBacklog": "Headline backlog",
    "audit.auditNeverAttempted": "Not attempted",
    "audit.auditRetryableNow": "Retryable now",
    "audit.auditPermanentBlocked": "Permanently blocked",
    "audit.auditEvidenceCompletion": "Latest evidence completion",
    "audit.auditCandidateSegments": "Candidate data",
    "audit.auditRejectedSegments": "Anomalies rejected",
    "audit.auditMissingSegments": "Still missing",
    "audit.auditNoCompletion": "The latest research has not run the new evidence completer",
    "audit.evidenceCompleter": "Evidence completer",
    "audit.evidenceCompleterNotice": "Matches local numeric series per segment; available candidate data does not establish causality.",
    "audit.evidenceCandidateFound": "Candidate data found",
    "audit.evidencePartial": "Partially usable",
    "audit.evidenceMissing": "Data missing",
    "audit.evidenceRejected": "Anomalous data rejected",
    "audit.evidenceCanVerify": "Eligible for validation",
    "audit.evidenceBlocked": "Rejected by quality gate",
    "audit.chinaSectorLeaders": "Top-ten composite A-share sector leaders",
    "audit.usSectorUniverse": "US sector coverage",
    "audit.cycleModels": "Economic-cycle models",
    "audit.modelConfidence": "model data coverage",
    "audit.modelExpansion": "Expansion signal",
    "audit.modelTransition": "Transition / mixed",
    "audit.modelContraction": "Contraction signal",
    "audit.coverageUnknown": "No retained range",
    "audit.cycleTitle": "US economic-cycle model",
    "audit.cycleExpansion": "Expansion",
    "audit.cycleLate": "Late cycle",
    "audit.cycleSlowdown": "Slowdown",
    "audit.cycleContraction": "Contraction",
    "audit.cycleRecovery": "Recovery",
    "audit.cycleInsufficient": "Insufficient data",
    "audit.cycleAsOf": "As of",
    "audit.companyUniverse": "US large-company filings and prices",
    "audit.companySource": "SEC primary filings · Twelve Data daily prices",
    "audit.companyPrice": "Latest price",
    "audit.companyFiling": "Latest filing",
    "audit.companyFact": "Latest financial fact",
    "audit.companyPending": "Waiting for first sync",
    "audit.equityDimensions": "Five-lens equity research",
    "audit.fundamentals_valuation": "Fundamentals and valuation",
    "audit.technicals_positioning": "Technicals and positioning",
    "audit.macro_liquidity": "Macro and liquidity",
    "audit.supply_chain_geopolitics": "Supply chain and geopolitical risk",
    "audit.technology_competition": "Technology and competitive moat",
    "audit.signalBullish": "Bullish",
    "audit.signalBearish": "Bearish",
    "audit.signalMixed": "Mixed",
    "audit.signalUnknown": "Insufficient evidence",
    "audit.decisionFramework": "Conditional entry and invalidation framework",
    "audit.entryConditions": "Entry-watch conditions",
    "audit.invalidationConditions": "Invalidation conditions",
    "audit.monitoringIndicators": "Monitoring indicators",
    "audit.valuationScenarios": "Valuation scenarios",
    "audit.researchDisclaimer": "Research support; not personalized investment advice",
  },
});

const state = {
  mapData: null,
  integrations: [],
  openaiConfigured: false,
  inquiries: [],
  inquirySummaries: [],
  inquiryCache: new Map(),
  researchLoading: false,
  reportComparison: null,
  reportComparisonLoading: false,
  reportComparisonRequest: 0,
  reportChangeAlerts: null,
  reportChangeAlertsLoading: true,
  reportChangeAlertFilter: "all",
  factorExperiments: null,
  factorExperimentsLoading: true,
  eventChain: null,
  logicChain: null,
  coverage: null,
  dataAudit: null,
  cycle: null,
  cycleModels: null,
  companies: [],
  aiStatus: null,
  secEvidence: null,
  lifecycleResolutions: [],
  researchBatches: [],
  reportAuditQueue: null,
  secFilter: "candidate",
  secBusyKey: null,
  activePanel: "report-review",
  selectedInquiryId: null,
  showAllInquiries: false,
  catalog: {
    query: "",
    marketRegion: "",
    status: "",
    createdFrom: "",
    createdTo: "",
    page: 1,
    pageSize: 50,
    total: 0,
    pages: 0,
  },
};

const elements = {
  notice: document.querySelector("#audit-notice"),
  localModelStatus: document.querySelector("#local-model-status"),
  openaiStatus: document.querySelector("#openai-status"),
  fixedChainCount: document.querySelector("#fixed-chain-count"),
  logicTrainingCount: document.querySelector("#logic-training-count"),
  researchQuestion: document.querySelector("#research-question"),
  researchSubmit: document.querySelector("#research-submit"),
  researchAutonomous: document.querySelector("#research-autonomous"),
  questionExamples: [...document.querySelectorAll("[data-question-example]")],
  researchStatus: document.querySelector("#research-status"),
  researchResults: document.querySelector("#research-results"),
  factorResults: document.querySelector("#factor-results"),
  factorExperimentStatus: document.querySelector("#factor-experiment-status"),
  settleFactorExperiments: document.querySelector("#settle-factor-experiments"),
  inquiryEvidenceResults: document.querySelector("#inquiry-evidence-results"),
  newsResults: document.querySelector("#news-results"),
  researchInquirySelect: document.querySelector("#research-inquiry-select"),
  researchContextMeta: document.querySelector("#research-context-meta"),
  reportComparisonSummary: document.querySelector("#report-comparison-summary"),
  reportComparisonList: document.querySelector("#report-comparison-list"),
  reportChangeAlertSummary: document.querySelector("#report-change-alert-summary"),
  reportChangeAlertList: document.querySelector("#report-change-alert-list"),
  reportChangeAlertFilters: [...document.querySelectorAll("[data-change-alert-filter]")],
  catalogFilters: document.querySelector("#research-catalog-filters"),
  catalogQuery: document.querySelector("#catalog-query"),
  catalogMarket: document.querySelector("#catalog-market"),
  catalogStatus: document.querySelector("#catalog-status"),
  catalogFrom: document.querySelector("#catalog-from"),
  catalogTo: document.querySelector("#catalog-to"),
  catalogShare: document.querySelector("#catalog-share"),
  catalogReset: document.querySelector("#catalog-reset"),
  catalogStats: document.querySelector("#catalog-stats"),
  catalogPrev: document.querySelector("#catalog-prev"),
  catalogNext: document.querySelector("#catalog-next"),
  researchPanelButtons: [...document.querySelectorAll("[data-research-panel]")],
  researchPanelSections: [...document.querySelectorAll("[data-research-panel-section]")],
  refreshForecasts: document.querySelector("#refresh-forecasts"),
  createEquityBatch: document.querySelector("#create-equity-batch"),
  queueReportAudits: document.querySelector("#queue-report-audits"),
  researchBatchList: document.querySelector("#research-batch-list"),
  reportAuditQueue: document.querySelector("#report-audit-queue"),
  evidenceList: document.querySelector("#evidence-list"),
  logicStatus: document.querySelector("#logic-status"),
  logicChainList: document.querySelector("#logic-chain-list"),
  generateLogic: document.querySelector("#generate-logic"),
  validateLogic: document.querySelector("#validate-logic"),
  integrationList: document.querySelector("#integration-list"),
  coverageWindow: document.querySelector("#coverage-window"),
  coverageList: document.querySelector("#coverage-list"),
  dataAuditMetrics: document.querySelector("#data-audit-metrics"),
  dataAuditEvidence: document.querySelector("#data-audit-evidence"),
  dataAuditFindings: document.querySelector("#data-audit-findings"),
  dataAuditEquities: document.querySelector("#data-audit-equities"),
  dataAuditAbnormalList: document.querySelector("#data-audit-abnormal-list"),
  archiveDataAudit: document.querySelector("#archive-data-audit"),
  sourceCoverageList: document.querySelector("#source-coverage-list"),
  cycleSummary: document.querySelector("#cycle-summary"),
  cycleModelList: document.querySelector("#cycle-model-list"),
  companyList: document.querySelector("#company-list"),
  aiStatePanel: document.querySelector("#ai-state-panel"),
  secEvidenceSummary: document.querySelector("#sec-evidence-summary"),
  secEvidenceStatus: document.querySelector("#sec-evidence-status"),
  secEvidenceList: document.querySelector("#sec-evidence-list"),
  lifecycleResolutionList: document.querySelector("#lifecycle-resolution-list"),
  secEvidenceFilters: [...document.querySelectorAll("[data-sec-filter]")],
};

document.addEventListener("DOMContentLoaded", initialize);
window.addEventListener("news:languagechange", renderAll);

async function initialize() {
  initializeCatalogFromUrl();
  bindActions();
  initializeResearchPanels();
  try {
    // The full map payload becomes very large after historical backfills.
    // This page only needs two job IDs, so keep startup independent of it.
    state.mapData = await api("/research/context");
    await Promise.all([
      loadIntegrations(),
      loadResearch(),
      loadResearchBatches(),
      loadReportAuditQueue(),
      loadEventChain(),
      loadLogicChain(),
      loadCycle(),
      loadCycleModels(),
      loadCompanies(),
      loadAIStatus(),
      loadLifecycleResolutions(),
      loadSecEvidence().catch((error) => {
        elements.secEvidenceStatus.textContent = `${i18n.t("audit.secEvidenceFailed")}: ${error.message}`;
      }),
    ]);
    renderAll();
    void loadCoverage()
      .then(() => renderCoverage())
      .catch((error) => {
        console.warn("coverage status unavailable", error);
      });
    void loadDataAudit()
      .then(() => renderDataAudit())
      .catch((error) => {
        console.warn("data audit unavailable", error);
      });
    void loadReportChangeAlerts()
      .then(() => renderReportChangeAlerts())
      .catch((error) => {
        state.reportChangeAlerts = { error: error.message };
        state.reportChangeAlertsLoading = false;
        renderReportChangeAlerts();
      });
    void loadFactorExperiments()
      .then(() => renderFactorExperiments())
      .catch((error) => {
        state.factorExperiments = { error: error.message };
        state.factorExperimentsLoading = false;
        renderFactorExperiments();
      });
    window.setInterval(refreshResearchQueues, 15_000);
  } catch (error) {
    showNotice(`${i18n.t("audit.loadFailed")}: ${error.message}`, true);
  }
}

function bindActions() {
  elements.archiveDataAudit?.addEventListener("click", archiveDataAudit);
  elements.researchSubmit.addEventListener("click", submitResearchQuestion);
  elements.researchAutonomous.addEventListener("click", runAutonomousResearch);
  elements.questionExamples.forEach((button) => {
    button.addEventListener("click", () => fillQuestionExample(button.dataset.questionExample));
  });
  elements.refreshForecasts.addEventListener("click", refreshForecasts);
  elements.createEquityBatch?.addEventListener("click", createEquityBatch);
  elements.queueReportAudits?.addEventListener("click", queueHistoricalReportAudits);
  elements.settleFactorExperiments?.addEventListener("click", settleMatureFactorExperiments);
  elements.researchBatchList?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-retry-batch]");
    if (button) retryResearchBatch(Number(button.dataset.retryBatch));
  });
  elements.researchPanelButtons.forEach((button) => {
    button.addEventListener("click", () => activateResearchPanel(
      button.dataset.researchPanel,
      { updateHash: true },
    ));
  });
  elements.researchInquirySelect?.addEventListener("change", async () => {
    await selectResearchReport(elements.researchInquirySelect.value);
  });
  elements.reportComparisonList?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-comparison-report]");
    if (!button) return;
    const inquiryId = Number(button.dataset.comparisonReport);
    const version = state.reportComparison?.versions?.find(
      (item) => Number(item.inquiry_id) === inquiryId,
    );
    if (!Number.isInteger(inquiryId) || inquiryId <= 0 || !version) return;
    ensureComparisonSummary(version);
    await selectResearchReport(String(inquiryId));
    document.querySelector("#research-lab")?.scrollIntoView({ behavior: "smooth" });
  });
  elements.reportChangeAlertFilters.forEach((button) => {
    button.addEventListener("click", () => {
      state.reportChangeAlertFilter = button.dataset.changeAlertFilter || "all";
      elements.reportChangeAlertFilters.forEach((item) => {
        item.classList.toggle("is-active", item === button);
      });
      renderReportChangeAlerts();
    });
  });
  elements.reportChangeAlertList?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-change-alert-report]");
    if (!button) return;
    const inquiryId = Number(button.dataset.changeAlertReport);
    const alert = state.reportChangeAlerts?.alerts?.find(
      (item) => Number(item.latest_inquiry_id) === inquiryId,
    );
    if (!Number.isInteger(inquiryId) || inquiryId <= 0 || !alert) return;
    ensureChangeAlertSummary(alert);
    await selectResearchReport(String(inquiryId));
    document.querySelector("#research-lab")?.scrollIntoView({ behavior: "smooth" });
  });
  elements.catalogFilters?.addEventListener("submit", async (event) => {
    event.preventDefault();
    state.catalog.query = elements.catalogQuery.value.trim();
    state.catalog.marketRegion = elements.catalogMarket.value;
    state.catalog.status = elements.catalogStatus.value;
    state.catalog.createdFrom = elements.catalogFrom.value;
    state.catalog.createdTo = elements.catalogTo.value;
    state.catalog.page = 1;
    await reloadResearchCatalog();
  });
  elements.catalogReset?.addEventListener("click", async () => {
    elements.catalogFilters.reset();
    Object.assign(state.catalog, {
      query: "",
      marketRegion: "",
      status: "",
      createdFrom: "",
      createdTo: "",
      page: 1,
    });
    await reloadResearchCatalog();
  });
  elements.catalogPrev?.addEventListener("click", async () => {
    if (state.catalog.page <= 1) return;
    state.catalog.page -= 1;
    await reloadResearchCatalog();
  });
  elements.catalogNext?.addEventListener("click", async () => {
    if (state.catalog.page >= state.catalog.pages) return;
    state.catalog.page += 1;
    await reloadResearchCatalog();
  });
  elements.catalogShare?.addEventListener("click", copyCurrentViewLink);
  window.addEventListener("hashchange", () => initializeResearchPanels());
  const handleResearchAction = (event) => {
    const chatgptButton = event.target.closest("[data-chatgpt-review]");
    if (chatgptButton) {
      requestResearchReview(Number(chatgptButton.dataset.chatgptReview));
      return;
    }
    const decisionButton = event.target.closest("[data-report-decision]");
    if (decisionButton) {
      reviewResearchReport(
        Number(decisionButton.dataset.inquiryId),
        decisionButton.dataset.reportDecision,
      );
      return;
    }
    const factorButton = event.target.closest("[data-factor-mine]");
    if (factorButton) {
      remineFactors(Number(factorButton.dataset.factorMine));
    }
  };
  [elements.researchResults, elements.factorResults].filter(Boolean).forEach((container) => {
    container.addEventListener("click", handleResearchAction);
  });
  elements.evidenceList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-pin-relation]");
    if (button) pinEvidenceRelation(Number(button.dataset.pinRelation));
  });
  elements.generateLogic.addEventListener("click", generateLogicChains);
  elements.validateLogic.addEventListener("click", validateLogicChains);
  elements.logicChainList.addEventListener("click", (event) => {
    const chatgptButton = event.target.closest("[data-logic-chatgpt]");
    if (chatgptButton) {
      requestLogicReview(Number(chatgptButton.dataset.logicChatgpt));
      return;
    }
    const decisionButton = event.target.closest("[data-logic-decision]");
    if (decisionButton) {
      reviewLogicHypothesis(
        Number(decisionButton.dataset.hypothesisId),
        decisionButton.dataset.logicDecision,
      );
    }
  });
  elements.secEvidenceFilters.forEach((button) => {
    button.addEventListener("click", () => {
      state.secFilter = button.dataset.secFilter;
      elements.secEvidenceFilters.forEach((item) => {
        item.classList.toggle("is-active", item === button);
      });
      renderSecEvidence();
    });
  });
  elements.secEvidenceList.addEventListener("click", (event) => {
    const reviewButton = event.target.closest("[data-sec-decision]");
    if (reviewButton) {
      reviewSecEvidence(
        reviewButton.dataset.evidenceKey,
        reviewButton.dataset.secDecision,
        reviewButton.dataset.secRole || null,
      );
      return;
    }
    const factorButton = event.target.closest("[data-sec-factor]");
    if (factorButton) {
      materializeSecEvidence(
        factorButton.dataset.assetKey,
        factorButton.dataset.evidenceKey,
      );
    }
  });
}

function researchPanelFromHash(hash = window.location.hash) {
  const value = String(hash || "").replace(/^#/, "");
  const panelByAnchor = {
    "report-review": "report-review",
    "research-lab": "report-review",
    "factor-mining": "factor-mining",
    "evidence-validation": "evidence-validation",
    "ai-state": "evidence-validation",
    "sec-evidence": "evidence-validation",
    "evidence-chain": "evidence-validation",
    "data-provenance": "evidence-validation",
    "news-analysis": "news-analysis",
  };
  return panelByAnchor[value] || "report-review";
}

function initializeResearchPanels() {
  const panel = researchPanelFromHash();
  activateResearchPanel(panel, { updateHash: false });
  const targetId = String(window.location.hash || "").replace(/^#/, "");
  if (targetId && targetId !== panel) {
    window.setTimeout(() => {
      document.getElementById(targetId)?.scrollIntoView({ block: "start" });
    }, 0);
  }
}

function activateResearchPanel(panel, { updateHash = false } = {}) {
  const supported = new Set([
    "report-review",
    "factor-mining",
    "evidence-validation",
    "news-analysis",
  ]);
  const selected = supported.has(panel) ? panel : "report-review";
  state.activePanel = selected;
  elements.researchPanelButtons.forEach((button) => {
    const active = button.dataset.researchPanel === selected;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
  });
  elements.researchPanelSections.forEach((section) => {
    section.hidden = section.dataset.researchPanelSection !== selected;
  });
  if (updateHash) {
    const url = new URL(window.location.href);
    url.hash = selected;
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
    document.querySelector(".research-mode-tabs")?.scrollIntoView({ block: "start" });
  }
}

function initializeCatalogFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const market = params.get("market") || "";
  const status = params.get("status") || "";
  const page = Number(params.get("page") || 1);
  const reportId = Number(params.get("report") || 0);
  state.catalog.query = (params.get("q") || "").slice(0, 200);
  state.catalog.marketRegion = ["us", "china"].includes(market) ? market : "";
  state.catalog.status = ["running", "completed", "failed"].includes(status)
    ? status
    : "";
  state.catalog.createdFrom = params.get("from") || "";
  state.catalog.createdTo = params.get("to") || "";
  state.catalog.page = Number.isInteger(page) && page > 0 ? page : 1;
  state.selectedInquiryId = Number.isInteger(reportId) && reportId > 0 ? reportId : null;
  state.showAllInquiries = params.get("all") === "1";
  hydrateCatalogControls();
}

function hydrateCatalogControls() {
  if (elements.catalogQuery) elements.catalogQuery.value = state.catalog.query;
  if (elements.catalogMarket) elements.catalogMarket.value = state.catalog.marketRegion;
  if (elements.catalogStatus) elements.catalogStatus.value = state.catalog.status;
  if (elements.catalogFrom) elements.catalogFrom.value = state.catalog.createdFrom;
  if (elements.catalogTo) elements.catalogTo.value = state.catalog.createdTo;
}

function syncResearchUrl() {
  const url = new URL(window.location.href);
  const values = {
    q: state.catalog.query,
    market: state.catalog.marketRegion,
    status: state.catalog.status,
    from: state.catalog.createdFrom,
    to: state.catalog.createdTo,
    page: state.catalog.page > 1 ? String(state.catalog.page) : "",
    report: state.selectedInquiryId ? String(state.selectedInquiryId) : "",
    all: state.showAllInquiries ? "1" : "",
  };
  Object.entries(values).forEach(([key, value]) => {
    if (value) url.searchParams.set(key, value);
    else url.searchParams.delete(key);
  });
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

async function copyCurrentViewLink() {
  syncResearchUrl();
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(window.location.href);
    } else {
      const textarea = document.createElement("textarea");
      textarea.value = window.location.href;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      const copied = document.execCommand("copy");
      textarea.remove();
      if (!copied) throw new Error("clipboard unavailable");
    }
    showNotice(i18n.t("audit.catalogCopied"));
  } catch (error) {
    console.warn("could not copy research URL", error);
    showNotice(i18n.t("audit.catalogCopyFailed"), true);
  }
}

async function loadIntegrations() {
  const payload = await api("/integrations/status");
  state.integrations = payload.integrations;
  state.openaiConfigured = Boolean(
    state.integrations.find((item) => item.key === "openai_review")?.configured,
  );
}

async function loadResearch({ forceDetail = true } = {}) {
  const params = new URLSearchParams({
    page: String(state.catalog.page),
    page_size: String(state.catalog.pageSize),
  });
  if (state.catalog.query) params.set("q", state.catalog.query);
  if (state.catalog.marketRegion) params.set("market_region", state.catalog.marketRegion);
  if (state.catalog.status) params.set("status", state.catalog.status);
  if (state.catalog.createdFrom) params.set("created_from", state.catalog.createdFrom);
  if (state.catalog.createdTo) params.set("created_to", state.catalog.createdTo);
  const payload = await api(`/research/inquiries/summaries?${params.toString()}`);
  state.inquirySummaries = payload.inquiries;
  state.catalog.total = Number(payload.total || 0);
  state.catalog.page = Number(payload.page || 1);
  state.catalog.pageSize = Number(payload.page_size || state.catalog.pageSize);
  state.catalog.pages = Number(payload.pages || 0);
  let selectedStillAvailable = state.inquirySummaries.some(
    (item) => item.id === state.selectedInquiryId,
  );
  let requestedDetailLoaded = false;
  if (!selectedStillAvailable && state.selectedInquiryId) {
    try {
      const requested = state.inquiryCache.get(state.selectedInquiryId)
        || await api(`/research/inquiries/${state.selectedInquiryId}/workspace`);
      storeInquiryDetail(requested);
      selectedStillAvailable = true;
      requestedDetailLoaded = true;
    } catch (error) {
      console.warn("requested report is unavailable", error);
    }
  }
  if (!state.inquirySummaries.length) {
    state.inquiries = [];
    state.selectedInquiryId = null;
    state.showAllInquiries = false;
    state.reportComparison = null;
    syncResearchUrl();
    return;
  }
  if (!selectedStillAvailable) state.selectedInquiryId = state.inquirySummaries[0].id;
  await Promise.all([
    loadVisibleResearchDetails({ force: forceDetail && !requestedDetailLoaded }),
    loadReportComparison(),
  ]);
  syncResearchUrl();
}

async function reloadResearchCatalog() {
  state.researchLoading = true;
  renderResearchContext();
  try {
    await loadResearch({ forceDetail: false });
    renderResearch();
  } catch (error) {
    showNotice(`${i18n.t("audit.loadFailed")}: ${error.message}`, true);
  } finally {
    state.researchLoading = false;
    renderResearchContext();
  }
}

function visibleResearchIds() {
  if (state.showAllInquiries) {
    return state.inquirySummaries.slice(0, 4).map((item) => item.id);
  }
  return state.selectedInquiryId ? [state.selectedInquiryId] : [];
}

async function loadVisibleResearchDetails({ force = false } = {}) {
  const ids = visibleResearchIds();
  const details = await Promise.all(ids.map(async (inquiryId) => {
    if (!force && state.inquiryCache.has(inquiryId)) {
      return state.inquiryCache.get(inquiryId);
    }
    const inquiry = await api(`/research/inquiries/${inquiryId}/workspace`);
    state.inquiryCache.set(inquiry.id, inquiry);
    return inquiry;
  }));
  state.inquiries = details;
}

async function selectResearchReport(value) {
  const previousInquiryId = state.selectedInquiryId;
  const previousShowAll = state.showAllInquiries;
  const previousComparison = state.reportComparison;
  state.showAllInquiries = value === "all";
  if (!state.showAllInquiries) state.selectedInquiryId = Number(value);
  state.researchLoading = true;
  if (state.selectedInquiryId !== previousInquiryId || state.showAllInquiries) {
    state.reportComparison = null;
  }
  renderResearchContext();
  renderReportComparison();
  try {
    await Promise.all([
      loadVisibleResearchDetails(),
      loadReportComparison({ force: true }),
    ]);
    syncResearchUrl();
    renderResearch();
  } catch (error) {
    state.selectedInquiryId = previousInquiryId;
    state.showAllInquiries = previousShowAll;
    state.reportComparison = previousComparison;
    state.inquiries = visibleResearchIds()
      .map((id) => state.inquiryCache.get(id))
      .filter(Boolean);
    syncResearchUrl();
    renderResearch();
    showNotice(`${i18n.t("audit.loadFailed")}: ${error.message}`, true);
  } finally {
    state.researchLoading = false;
    renderResearchContext();
    renderReportComparison();
  }
}

async function loadReportComparison({ force = false } = {}) {
  const inquiryId = state.selectedInquiryId;
  if (state.showAllInquiries || !inquiryId) {
    state.reportComparison = null;
    state.reportComparisonLoading = false;
    renderReportComparison();
    return;
  }
  if (!force && Number(state.reportComparison?.selected_inquiry_id) === inquiryId) return;
  const requestId = ++state.reportComparisonRequest;
  state.reportComparisonLoading = true;
  renderReportComparison();
  try {
    const payload = await api(`/research/inquiries/${inquiryId}/comparison?limit=12`);
    if (requestId !== state.reportComparisonRequest || inquiryId !== state.selectedInquiryId) return;
    state.reportComparison = payload;
    const selectedVersion = payload.versions?.find(
      (item) => Number(item.inquiry_id) === inquiryId,
    );
    if (selectedVersion) ensureComparisonSummary(selectedVersion, payload);
  } catch (error) {
    if (requestId === state.reportComparisonRequest) {
      state.reportComparison = { selected_inquiry_id: inquiryId, error: error.message };
    }
  } finally {
    if (requestId === state.reportComparisonRequest) {
      state.reportComparisonLoading = false;
      renderReportComparison();
    }
  }
}

async function loadReportChangeAlerts() {
  state.reportChangeAlertsLoading = true;
  renderReportChangeAlerts();
  try {
    state.reportChangeAlerts = await api("/research/report-change-alerts?limit=24");
  } finally {
    state.reportChangeAlertsLoading = false;
  }
}

function ensureComparisonSummary(version, comparison = state.reportComparison) {
  const existing = state.inquirySummaries.find(
    (item) => Number(item.id) === Number(version.inquiry_id),
  );
  const summary = {
    ...existing,
    id: Number(version.inquiry_id),
    question: version.question,
    mode: existing?.mode || "autonomous",
    status: version.status,
    local_model: version.local_model,
    has_result: version.status === "completed",
    market_region: comparison?.market_region || existing?.market_region || null,
    ticker: comparison?.ticker || existing?.ticker || null,
    company_name: comparison?.company_name || existing?.company_name || null,
    sector: comparison?.sector || existing?.sector || null,
    error: existing?.error || null,
    created_at: version.created_at,
    updated_at: version.updated_at,
  };
  state.inquirySummaries = [
    ...state.inquirySummaries.filter(
      (item) => Number(item.id) !== Number(version.inquiry_id),
    ),
    summary,
  ];
  state.inquirySummaries.sort((left, right) => {
    const byDate = String(right.created_at).localeCompare(String(left.created_at));
    return byDate || Number(right.id) - Number(left.id);
  });
}

function ensureChangeAlertSummary(alert) {
  const inquiryId = Number(alert.latest_inquiry_id);
  const existing = state.inquirySummaries.find((item) => Number(item.id) === inquiryId);
  const summary = {
    ...existing,
    id: inquiryId,
    question: existing?.question || `${alert.ticker} material report change review`,
    mode: existing?.mode || "autonomous",
    status: "completed",
    local_model: existing?.local_model || "local-research",
    has_result: true,
    market_region: alert.market_region,
    ticker: alert.ticker,
    company_name: alert.company_name,
    sector: alert.sector || null,
    error: null,
    created_at: alert.latest_created_at,
    updated_at: alert.latest_created_at,
  };
  state.inquirySummaries = [
    ...state.inquirySummaries.filter((item) => Number(item.id) !== inquiryId),
    summary,
  ].sort((left, right) => {
    const byDate = String(right.created_at).localeCompare(String(left.created_at));
    return byDate || Number(right.id) - Number(left.id);
  });
}

function storeInquiryDetail(inquiry, { select = false } = {}) {
  state.inquiryCache.set(inquiry.id, inquiry);
  const existingSummary = state.inquirySummaries.find((item) => item.id === inquiry.id);
  const summary = {
    id: inquiry.id,
    question: inquiry.question,
    mode: inquiry.mode,
    status: inquiry.status,
    local_model: inquiry.local_model,
    has_result: Boolean(inquiry.result),
    market_region: existingSummary?.market_region || null,
    ticker: existingSummary?.ticker || null,
    company_name: existingSummary?.company_name || null,
    sector: existingSummary?.sector || null,
    error: inquiry.error,
    created_at: inquiry.created_at,
    updated_at: inquiry.updated_at,
  };
  state.inquirySummaries = [
    summary,
    ...state.inquirySummaries.filter((item) => item.id !== inquiry.id),
  ].sort((left, right) => {
    const byDate = String(right.created_at).localeCompare(String(left.created_at));
    return byDate || right.id - left.id;
  });
  if (select) {
    state.selectedInquiryId = inquiry.id;
    state.showAllInquiries = false;
  }
  state.inquiries = visibleResearchIds()
    .map((id) => state.inquiryCache.get(id))
    .filter(Boolean);
  syncResearchUrl();
  if (select) {
    state.reportComparison = null;
    void loadReportComparison({ force: true });
  }
}

async function loadResearchBatches() {
  const payload = await api("/research/batches?limit=4");
  state.researchBatches = payload.batches;
}

async function loadReportAuditQueue() {
  state.reportAuditQueue = await api("/research/audits/status");
}

async function refreshResearchQueues() {
  try {
    await Promise.all([loadResearchBatches(), loadReportAuditQueue()]);
    renderResearchQueues();
    if (state.researchBatches.some((batch) => ["queued", "running"].includes(batch.status))) {
      await loadResearch();
      renderResearch();
    }
  } catch (error) {
    console.warn("research queues unavailable", error);
  }
}

async function createEquityBatch() {
  if (!elements.createEquityBatch) return;
  elements.createEquityBatch.disabled = true;
  try {
    const batch = await apiMutation("/research/batches", {
      method: "POST",
      body: JSON.stringify({ regions: ["us", "china"], limit_per_region: 1 }),
    });
    showNotice(`${i18n.t("audit.batchCreated")}: #${batch.id}`);
    await refreshResearchQueues();
  } catch (error) {
    showNotice(`${i18n.t("audit.requestFailed")}: ${error.message}`, true);
  } finally {
    elements.createEquityBatch.disabled = false;
  }
}

async function queueHistoricalReportAudits() {
  if (!elements.queueReportAudits) return;
  elements.queueReportAudits.disabled = true;
  try {
    const queued = await apiMutation("/research/audits/queue", {
      method: "POST",
      body: JSON.stringify({ mode: "audit_only", limit: 100 }),
    });
    showNotice(`${i18n.t("audit.auditsQueued")}: ${queued.queued_jobs}`);
    await refreshResearchQueues();
  } catch (error) {
    showNotice(`${i18n.t("audit.requestFailed")}: ${error.message}`, true);
  } finally {
    elements.queueReportAudits.disabled = false;
  }
}

async function retryResearchBatch(batchId) {
  try {
    await apiMutation(`/research/batches/${batchId}/retry`, { method: "POST" });
    await refreshResearchQueues();
  } catch (error) {
    showNotice(`${i18n.t("audit.requestFailed")}: ${error.message}`, true);
  }
}

async function loadEventChain() {
  const jobId = state.mapData?.latest_cluster_job_id;
  state.eventChain = jobId ? await api(`/event-chains/${jobId}`) : null;
}

async function loadLogicChain() {
  const jobId = state.mapData?.latest_logic_job_id
    || state.mapData?.latest_cluster_job_id;
  state.logicChain = jobId ? await api(`/logic-chains/${jobId}`) : null;
}

async function loadCoverage() {
  state.coverage = await api("/coverage/status");
}

async function loadDataAudit() {
  state.dataAudit = await api("/research/data-audit");
}

async function archiveDataAudit() {
  if (!elements.archiveDataAudit) return;
  elements.archiveDataAudit.disabled = true;
  elements.archiveDataAudit.textContent = i18n.t("audit.archivingDataAudit");
  try {
    state.dataAudit = await apiMutation("/research/data-audit", { method: "POST" });
    renderDataAudit();
    showNotice(`${i18n.t("audit.dataAuditArchived")}: ${state.dataAudit.archive_path || state.dataAudit.archive_status}`);
  } catch (error) {
    showNotice(`${i18n.t("audit.requestFailed")}: ${error.message}`, true);
  } finally {
    elements.archiveDataAudit.disabled = false;
    elements.archiveDataAudit.textContent = i18n.t("audit.archiveDataAudit");
  }
}

async function loadCycle() {
  state.cycle = await api("/markets/cycle");
}

async function loadCycleModels() {
  state.cycleModels = await api("/markets/cycle-models");
}

async function loadCompanies() {
  const payload = await api("/companies?limit=50");
  state.companies = payload.companies;
}

async function loadAIStatus() {
  state.aiStatus = await api("/research/ai-status");
}

async function loadFactorExperiments() {
  state.factorExperimentsLoading = true;
  renderFactorExperiments();
  try {
    state.factorExperiments = await api("/research/factors/experiments?limit=40");
  } finally {
    state.factorExperimentsLoading = false;
  }
}

async function settleMatureFactorExperiments() {
  if (!elements.settleFactorExperiments) return;
  elements.settleFactorExperiments.disabled = true;
  try {
    const result = await api("/research/factors/experiments/settle", { method: "POST" });
    await loadFactorExperiments();
    showNotice(`${i18n.t("audit.factorExperimentSettled")}: ${Number(result.settled || 0)}`);
  } catch (error) {
    showNotice(`${i18n.t("audit.loadFailed")}: ${error.message}`, true);
  } finally {
    elements.settleFactorExperiments.disabled = false;
  }
}

async function loadSecEvidence() {
  state.secEvidence = await api("/markets/historical-delisting-evidence?limit=100");
}

async function loadLifecycleResolutions() {
  state.lifecycleResolutions = await api("/markets/historical-lifecycle-resolutions");
}

async function refreshAIStatus() {
  try {
    await loadAIStatus();
    renderAIStatus();
  } catch (error) {
    console.warn("AI status unavailable", error);
  }
}

function renderAll() {
  renderMetrics();
  renderAIStatus();
  renderResearch();
  renderReportChangeAlerts();
  renderFactorExperiments();
  renderResearchQueues();
  renderEvidence();
  renderLogic();
  renderIntegrations();
  renderCoverage();
  renderDataAudit();
  renderCycle();
  renderCycleModels();
  renderCompanies();
  renderSecEvidence();
  renderLifecycleResolutions();
}

function renderReportChangeAlerts() {
  if (!elements.reportChangeAlertSummary || !elements.reportChangeAlertList) return;
  if (state.reportChangeAlertsLoading) {
    elements.reportChangeAlertSummary.textContent = i18n.t("audit.alertLoading");
    elements.reportChangeAlertList.innerHTML = `
      <div class="report-change-alert-loading" aria-hidden="true"><span></span><span></span><span></span></div>
    `;
    return;
  }
  const payload = state.reportChangeAlerts;
  if (!payload || payload.error) {
    elements.reportChangeAlertSummary.textContent = i18n.t("audit.alertFailed");
    elements.reportChangeAlertList.innerHTML = payload?.error
      ? `<div class="empty-card">${escapeHtml(payload.error)}</div>`
      : "";
    return;
  }
  const allAlerts = payload.alerts || [];
  const alerts = state.reportChangeAlertFilter === "all"
    ? allAlerts
    : allAlerts.filter((item) => item.assessment === state.reportChangeAlertFilter);
  elements.reportChangeAlertSummary.innerHTML = `
    <b>${Number(payload.total_companies_with_history || 0)} ${escapeHtml(i18n.t("audit.alertCompanies"))}</b>
    <span>${alerts.length} ${escapeHtml(i18n.t("audit.alertShown"))}</span>
  `;
  if (!alerts.length) {
    elements.reportChangeAlertList.innerHTML = `
      <div class="empty-card">${escapeHtml(i18n.t("audit.alertEmpty"))}</div>
    `;
    return;
  }
  elements.reportChangeAlertList.innerHTML = `
    <p class="report-change-alert-boundary">${escapeHtml(i18n.t("audit.alertEvidenceBoundary"))}</p>
    <div class="report-change-alert-grid">
      ${alerts.map((alert) => renderReportChangeAlertCard(alert)).join("")}
    </div>
  `;
}

function renderReportChangeAlertCard(alert) {
  const change = alert.change_summary || {};
  const deltas = [];
  if (change.confidence_delta !== null && change.confidence_delta !== undefined) {
    deltas.push(`${i18n.t("audit.comparisonConfidence")} ${formatSignedChange(
      Number(change.confidence_delta) * 100,
      "pp",
    )}`);
  }
  if (change.data_readiness_delta !== null && change.data_readiness_delta !== undefined) {
    deltas.push(`${i18n.t("audit.comparisonReadiness")} ${formatSignedChange(
      Number(change.data_readiness_delta) * 100,
      "pp",
    )}`);
  }
  if (change.verified_steps_delta) {
    deltas.push(`${i18n.t("audit.comparisonVerified")} ${formatSignedChange(
      change.verified_steps_delta,
    )}`);
  }
  if (change.unresolved_steps_delta) {
    deltas.push(`${i18n.t("audit.comparisonUnresolved")} ${formatSignedChange(
      change.unresolved_steps_delta,
    )}`);
  }
  const newMix = renderEvidenceCategoryMix(change.new_category_counts);
  if (newMix) deltas.push(`${i18n.t("audit.changeAddedMix")}: ${newMix}`);
  const signalChanged = change.primary_signal_from !== change.primary_signal_to;
  const timingChanged = change.timing_from !== change.timing_to;
  return `
    <article class="report-change-alert-card is-${escapeAttribute(alert.severity)} is-${escapeAttribute(alert.assessment)}">
      <header>
        <div>
          <span>${escapeHtml(alert.market_region === "china"
            ? i18n.t("audit.catalogChina")
            : i18n.t("audit.catalogUS"))}</span>
          <h3>${escapeHtml(alert.ticker)} · ${escapeHtml(alert.company_name)}</h3>
          <small>${escapeHtml(alert.sector || "—")}</small>
        </div>
        <div class="report-change-alert-score">
          <span>${escapeHtml(reportChangeSeverityLabel(alert.severity))}</span>
          <b>${Number(alert.alert_score)}</b>
          <small>${escapeHtml(i18n.t("audit.alertPriority"))}</small>
        </div>
      </header>
      <div class="report-change-alert-assessment">
        <b>${escapeHtml(reportChangeAssessmentLabel(alert.assessment))}</b>
        <span>${escapeHtml(i18n.t("audit.alertLatest"))} ${escapeHtml(formatDate(alert.latest_created_at))}</span>
      </div>
      <div class="report-change-alert-metrics">
        <span><small>${escapeHtml(i18n.t("audit.comparisonConfidence"))}</small><b>${escapeHtml(comparisonPercent(alert.current_confidence))}</b></span>
        <span><small>${escapeHtml(i18n.t("audit.comparisonReadiness"))}</small><b>${escapeHtml(comparisonPercent(alert.current_readiness))}</b></span>
        <span><small>${escapeHtml(i18n.t("audit.alertPrevious"))}</small><b>#${Number(alert.previous_inquiry_id)}</b></span>
      </div>
      ${(signalChanged || timingChanged) ? `<div class="report-change-alert-transitions">
        ${signalChanged ? `<span>${escapeHtml(i18n.t("audit.comparisonSignal"))}<b>${escapeHtml(
          comparisonSignalLabel(change.primary_signal_from),
        )} → ${escapeHtml(comparisonSignalLabel(change.primary_signal_to))}</b></span>` : ""}
        ${timingChanged ? `<span>${escapeHtml(i18n.t("audit.comparisonTiming"))}<b>${escapeHtml(
          change.timing_from || "—",
        )} → ${escapeHtml(change.timing_to || "—")}</b></span>` : ""}
      </div>` : ""}
      <ul>${deltas.slice(0, 5).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      <footer>
        <span>#${Number(alert.latest_inquiry_id)}</span>
        <button class="button ghost" type="button" data-change-alert-report="${Number(alert.latest_inquiry_id)}">
          ${escapeHtml(i18n.t("audit.alertOpen"))}
        </button>
      </footer>
    </article>
  `;
}

function reportChangeAssessmentLabel(assessment) {
  const key = {
    evidence_upgrade: "audit.alertUpgrade",
    evidence_downgrade: "audit.alertDowngrade",
    mixed_change: "audit.alertMixed",
    parameter_refresh: "audit.alertRefresh",
  }[assessment] || "audit.alertMixed";
  return i18n.t(key);
}

function reportChangeSeverityLabel(severity) {
  return i18n.t({
    critical: "audit.alertCritical",
    high: "audit.alertHigh",
    medium: "audit.alertMedium",
    low: "audit.alertLow",
  }[severity] || "audit.alertLow");
}

function renderFactorExperiments() {
  if (!elements.factorExperimentStatus) return;
  if (state.factorExperimentsLoading) {
    elements.factorExperimentStatus.innerHTML = `
      <div class="factor-experiment-loading">${escapeHtml(i18n.t("audit.factorExperimentLoading"))}</div>
    `;
    return;
  }
  const payload = state.factorExperiments;
  if (!payload || payload.error) {
    elements.factorExperimentStatus.innerHTML = payload?.error
      ? `<div class="empty-card">${escapeHtml(payload.error)}</div>`
      : "";
    return;
  }
  const groups = payload.groups || [];
  const recent = payload.recent_experiments || [];
  elements.factorExperimentStatus.innerHTML = `
    <div class="factor-experiment-metrics">
      <span><small>${escapeHtml(i18n.t("audit.factorExperimentTotal"))}</small><b>${Number(payload.total_experiments || 0)}</b></span>
      <span><small>${escapeHtml(i18n.t("audit.factorExperimentPending"))}</small><b>${Number(payload.pending_experiments || 0)}</b></span>
      <span><small>${escapeHtml(i18n.t("audit.factorExperimentPassed"))}</small><b>${Number(payload.future_validated || 0)}</b></span>
      <span><small>${escapeHtml(i18n.t("audit.factorExperimentFailed"))}</small><b>${Number(payload.future_failed || 0)}</b></span>
    </div>
    <p class="factor-experiment-method">${escapeHtml(payload.methodology || "")}</p>
    ${groups.length ? `<section>
      <h4>${escapeHtml(i18n.t("audit.factorExperimentGroups"))}</h4>
      <div class="factor-experiment-groups">${groups.map((group) => `
        <article class="is-${escapeAttribute(group.reliability_status)}">
          <header><b>${escapeHtml(group.target_series_id)} · ${Number(group.forecast_horizon_observations)}d</b>
            <span>${escapeHtml(factorReliabilityLabel(group.reliability_status))}</span></header>
          <p>${(group.factor_ids || []).map(escapeHtml).join(" × ")}</p>
          <small>${escapeHtml(group.method_version)} · ${escapeHtml(group.protocol_version)}</small>
          <div>
            <span>${escapeHtml(i18n.t("audit.factorExperimentMatured"))}<b>${Number(group.matured)} / ${Number(group.experiments)}</b></span>
            <span>${escapeHtml(i18n.t("audit.factorExperimentHit"))}<b>${group.prospective_hit_rate == null ? "—" : percent(group.prospective_hit_rate)}</b></span>
            <span>${escapeHtml(i18n.t("audit.factorExperimentMean"))}<b>${group.mean_strategy_return == null ? "—" : percent(group.mean_strategy_return)}</b></span>
          </div>
        </article>
      `).join("")}</div>
    </section>` : `<div class="empty-card">${escapeHtml(i18n.t("audit.factorExperimentEmpty"))}</div>`}
    ${recent.length ? `<details class="factor-experiment-ledger">
      <summary>${escapeHtml(i18n.t("audit.factorExperimentTotal"))} · ${recent.length}</summary>
      <div>${recent.map((item) => `
        <article class="is-${escapeAttribute(item.status)}">
          <b>${escapeHtml(item.target_name)} · ${Number(item.forecast_horizon_observations)}d</b>
          <span>${escapeHtml(i18n.t("audit.factorExperimentPosition"))}: ${escapeHtml(item.predicted_position.toUpperCase())}</span>
          <span>${escapeHtml(i18n.t("audit.factorExperimentAnchor"))}: ${escapeHtml(item.anchor_observed_on)}</span>
          <small>${item.strategy_return == null ? escapeHtml(item.status) : `${escapeHtml(item.status)} · ${percent(item.strategy_return)}`}</small>
        </article>
      `).join("")}</div>
    </details>` : ""}
  `;
}

function factorReliabilityLabel(status) {
  return i18n.t({
    awaiting_future_samples: "audit.factorExperimentAwaiting",
    insufficient_future_samples: "audit.factorExperimentInsufficient",
    prospectively_retained: "audit.factorExperimentRetained",
    prospectively_rejected: "audit.factorExperimentRejected",
  }[status] || "audit.factorExperimentAwaiting");
}

function renderLifecycleResolutions() {
  if (!elements.lifecycleResolutionList) return;
  if (!state.lifecycleResolutions.length) {
    elements.lifecycleResolutionList.innerHTML = `<div class="empty-card">${escapeHtml(i18n.t("audit.lifecycleEmpty"))}</div>`;
    return;
  }
  elements.lifecycleResolutionList.innerHTML = state.lifecycleResolutions.map((item) => {
    const className = item.resolution_type === "provider_conflict_active"
      ? "is-conflict"
      : (item.resolution_type.endsWith("_pending") || item.resolution_type === "adr_program_terminated" ? "is-blocked" : "");
    const providerDate = item.provider_delisting_date || "—";
    const authoritativeDate = item.authoritative_delisting_date || "ACTIVE";
    return `
      <article class="lifecycle-resolution-card ${className}">
        <header>
          <b>${escapeHtml(item.symbol)}</b>
          <span>${escapeHtml(lifecycleResolutionLabel(item.resolution_type))}</span>
        </header>
        <p>${escapeHtml(i18n.t("audit.providerRecord"))}: ${escapeHtml(item.provider_status)} · ${escapeHtml(providerDate)}<br>
          ${escapeHtml(i18n.t("audit.authoritativeRecord"))}: ${escapeHtml(item.authoritative_status)} · ${escapeHtml(authoritativeDate)}</p>
        <p>${escapeHtml(item.evidence_note)}<br>
          <a href="${escapeAttribute(item.evidence_url)}" target="_blank" rel="noreferrer">${escapeHtml(i18n.t("audit.secSource"))}</a></p>
      </article>
    `;
  }).join("");
}

function lifecycleResolutionLabel(type) {
  const labels = {
    provider_conflict_active: "audit.providerConflictActive",
    adr_program_terminated: "audit.adrProgramTerminated",
    bankruptcy_pending: "audit.bankruptcyPending",
    liquidation_pending: "audit.liquidationPending",
    verified_delisted: "audit.verifiedDelisted",
    bankruptcy_final: "audit.bankruptcyFinal",
    liquidation_final: "audit.liquidationFinal",
  };
  return i18n.t(labels[type] || "audit.verifiedDelisted");
}

function renderSecEvidence() {
  if (!elements.secEvidenceList || !elements.secEvidenceSummary) return;
  const payload = state.secEvidence;
  if (!payload) {
    elements.secEvidenceList.innerHTML = `<div class="empty-card">${escapeHtml(i18n.t("audit.secEvidenceLoading"))}</div>`;
    return;
  }
  const summary = [
    ["audit.secAssets", payload.evidence_assets_searched, ""],
    ["audit.secFilings", payload.evidence_metadata_candidates, ""],
    ["audit.secValues", payload.evidence_value_candidates, ""],
    ["audit.secPending", payload.evidence_review_ready, payload.evidence_review_ready ? "is-blocked" : "is-ready"],
    ["audit.secTerminalAccepted", payload.evidence_terminal_accepted, payload.evidence_terminal_accepted ? "is-ready" : ""],
    ["audit.secSupportingAccepted", payload.evidence_supporting_accepted, ""],
    ["audit.secLifecycleSegmented", payload.evidence_lifecycle_segmented_assets, payload.evidence_lifecycle_segmented_assets ? "is-ready" : ""],
    ["audit.secBodyAccess", payload.body_retrieval_ready ? i18n.t("audit.secReady") : i18n.t("audit.secBlocked"), payload.body_retrieval_ready ? "is-ready" : "is-blocked"],
  ];
  elements.secEvidenceSummary.innerHTML = summary.map(([label, value, className]) => `
    <article class="sec-summary-card ${className}">
      <span>${escapeHtml(i18n.t(label))}</span>
      <strong>${escapeHtml(value)}</strong>
    </article>
  `).join("");

  const assets = payload.assets.map((asset) => ({
    ...asset,
    valueCandidates: asset.candidates.filter((candidate) => (
      ["filing_body_extract", "human_primary_source_extract"].includes(candidate.evidence_basis)
      && (state.secFilter === "all" || candidate.review_status === state.secFilter)
    )),
  })).filter((asset) => asset.valueCandidates.length);

  elements.secEvidenceStatus.textContent = `${i18n.t("audit.secEvidenceLoaded")} · ${formatDate(payload.generated_at)}`;
  if (!assets.length) {
    elements.secEvidenceList.innerHTML = `<div class="empty-card">${escapeHtml(i18n.t("audit.secNoCandidates"))}</div>`;
    return;
  }
  elements.secEvidenceList.innerHTML = assets.map((asset) => `
    <article class="sec-asset-card">
      <header>
        <div class="sec-asset-title">
          <b>${escapeHtml(asset.symbol)} · ${escapeHtml(asset.name)}</b>
          <span>CIK ${escapeHtml(asset.sec_cik || "—")} · ${escapeHtml(asset.delisting_date)}</span>
        </div>
        ${secAssetFact("audit.secIdentity", secIdentityLabel(asset.identity_status), asset.identity_status === "verified")}
        ${secAssetFact("audit.secOutcome", secOutcomeLabel(asset.outcome_status), asset.outcome_status === "verified")}
        ${secAssetFact("audit.secFactorGate", asset.factor_eligible ? i18n.t("audit.secFactorReady") : i18n.t("audit.secFactorBlocked"), asset.factor_eligible)}
      </header>
      <div class="sec-candidate-list">
        ${asset.valueCandidates.map((candidate) => renderSecCandidate(asset, candidate)).join("")}
      </div>
    </article>
  `).join("");
}

function secAssetFact(labelKey, value, ready) {
  return `<div class="sec-asset-fact"><span>${escapeHtml(i18n.t(labelKey))}</span><b class="${ready ? "is-ready" : "is-blocked"}">${escapeHtml(value)}</b></div>`;
}

function renderSecCandidate(asset, candidate) {
  const busy = state.secBusyKey === candidate.evidence_key;
  const canMaterialize = (
    candidate.review_status === "accepted"
    && candidate.review_role === "terminal_outcome"
    && asset.factor_eligible
    && candidate.candidate_value !== null
    && ["cash_consideration_per_share", "implied_stock_consideration_per_share"].includes(candidate.evidence_type)
  );
  const canReviewAsTerminal = (
    ["8-K", "6-K", "20-F"].includes(candidate.form)
    && [
      "cash_consideration_per_share",
      "share_exchange_ratio",
      "zero_recovery_per_share",
      "liquidation_distribution_per_share",
      "adr_cash_distribution_per_share",
    ].includes(candidate.evidence_type)
  );
  const defaultOutcome = candidate.evidence_type === "implied_stock_consideration_per_share"
    ? "stock_acquisition"
    : "cash_acquisition";
  return `
    <section class="sec-candidate-card is-${escapeAttribute(candidate.review_status)}">
      <div class="sec-candidate-overview">
        <header>
          <span>${escapeHtml(candidate.form)} · ${escapeHtml(candidate.filed_on)}</span>
          <b>${escapeHtml(secReviewStatusLabel(candidate.review_status))}</b>
        </header>
        <div class="sec-candidate-value">${escapeHtml(secCandidateValue(candidate))}</div>
        <div class="sec-candidate-type">${escapeHtml(secEvidenceTypeLabel(candidate.evidence_type))}</div>
        <div class="sec-candidate-meta">
          ${escapeHtml(i18n.t("audit.secConfidence"))}: ${escapeHtml(percent(candidate.confidence))}<br>
          ${candidate.observed_on ? `${escapeHtml(i18n.t("audit.secEvidenceDate"))}: ${escapeHtml(candidate.observed_on)}<br>` : ""}
          ${candidate.subject_symbol ? `${escapeHtml(i18n.t("audit.secSubject"))}: ${escapeHtml(candidate.subject_symbol)} · CIK ${escapeHtml(candidate.subject_sec_cik || "—")}<br>` : ""}
          <a href="${escapeAttribute(candidate.source_url)}" target="_blank" rel="noreferrer">${escapeHtml(i18n.t("audit.secSource"))}</a>
        </div>
        <div class="factor-gate ${asset.factor_eligible ? "is-ready" : ""}">
          ${escapeHtml(secFactorGateText(asset))}
        </div>
      </div>
      <div class="sec-candidate-body">
        <p class="sec-candidate-excerpt">${escapeHtml(candidate.evidence_excerpt || "—")}</p>
        ${candidate.review_note ? `<p class="sec-recorded-note"><b>${escapeHtml(secReviewStatusLabel(candidate.review_status))}</b>${candidate.review_role ? ` · ${escapeHtml(secReviewRoleLabel(candidate.review_role))}` : ""} · ${escapeHtml(candidate.review_note)}${candidate.reviewed_at ? ` · ${escapeHtml(formatDate(candidate.reviewed_at))}` : ""}</p>` : ""}
        <textarea class="sec-review-note" data-sec-note="${escapeAttribute(candidate.evidence_key)}" maxlength="2000" placeholder="${escapeAttribute(i18n.t("audit.secReviewNote"))}">${escapeHtml(candidate.review_note || "")}</textarea>
        <div class="sec-review-actions">
          ${canReviewAsTerminal ? `<button type="button" data-evidence-key="${escapeAttribute(candidate.evidence_key)}" data-sec-decision="accepted" data-sec-role="terminal_outcome" ${busy ? "disabled" : ""}>${escapeHtml(i18n.t("audit.secAcceptTerminal"))}</button>` : ""}
          <button type="button" data-evidence-key="${escapeAttribute(candidate.evidence_key)}" data-sec-decision="accepted" data-sec-role="supporting_evidence" ${busy ? "disabled" : ""}>${escapeHtml(i18n.t("audit.secAcceptSupporting"))}</button>
          <button type="button" data-evidence-key="${escapeAttribute(candidate.evidence_key)}" data-sec-decision="needs_more_evidence" ${busy ? "disabled" : ""}>${escapeHtml(i18n.t("audit.secNeedEvidence"))}</button>
          <button type="button" data-evidence-key="${escapeAttribute(candidate.evidence_key)}" data-sec-decision="rejected" ${busy ? "disabled" : ""}>${escapeHtml(i18n.t("audit.secReject"))}</button>
        </div>
        ${canMaterialize ? `
          <div class="factor-admission">
            <label>${escapeHtml(i18n.t("audit.secPaymentDate"))}
              <input type="date" data-sec-payment="${escapeAttribute(candidate.evidence_key)}" value="${escapeAttribute(candidate.filed_on)}">
            </label>
            <label>${escapeHtml(i18n.t("audit.secOutcomeType"))}
              <select data-sec-outcome="${escapeAttribute(candidate.evidence_key)}">
                <option value="cash_acquisition" ${defaultOutcome === "cash_acquisition" ? "selected" : ""}>${escapeHtml(i18n.t("audit.secCashAcquisition"))}</option>
                <option value="stock_acquisition" ${defaultOutcome === "stock_acquisition" ? "selected" : ""}>${escapeHtml(i18n.t("audit.secStockAcquisition"))}</option>
              </select>
            </label>
            <button type="button" data-sec-factor="${escapeAttribute(candidate.evidence_key)}" data-evidence-key="${escapeAttribute(candidate.evidence_key)}" data-asset-key="${escapeAttribute(asset.asset_key)}" ${busy ? "disabled" : ""}>${escapeHtml(i18n.t("audit.secAddFactor"))}</button>
          </div>
        ` : ""}
      </div>
    </section>
  `;
}

function secCandidateValue(candidate) {
  if (candidate.candidate_value === null) return "—";
  if (candidate.value_unit === "acquirer_shares_per_share") {
    return `${Number(candidate.candidate_value).toFixed(4).replace(/0+$/, "").replace(/\.$/, "")}×`;
  }
  return new Intl.NumberFormat(i18n.language === "zh" ? "zh-CN" : "en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(Number(candidate.candidate_value));
}

function secEvidenceTypeLabel(type) {
  const labels = {
    cash_consideration_per_share: "audit.secFinalCash",
    historical_offer_per_share: "audit.secHistoricalOffer",
    implied_stock_consideration_per_share: "audit.secImpliedStock",
    share_exchange_ratio: "audit.secExchangeRatio",
    acquirer_closing_price: "audit.secAcquirerPrice",
    zero_recovery_per_share: "audit.secZeroRecovery",
    liquidation_distribution_per_share: "audit.secLiquidationDistribution",
    adr_cash_distribution_per_share: "audit.secAdrDistribution",
    possible_worthlessness: "audit.secPossibleWorthless",
  };
  return i18n.t(labels[type] || "audit.secValues");
}

function secReviewStatusLabel(status) {
  const labels = {
    candidate: "audit.secStatusCandidate",
    accepted: "audit.secStatusAccepted",
    rejected: "audit.secStatusRejected",
    needs_more_evidence: "audit.secStatusDeferred",
  };
  return i18n.t(labels[status] || "audit.secStatusCandidate");
}

function secReviewRoleLabel(role) {
  return role === "terminal_outcome"
    ? i18n.t("audit.secRoleTerminal")
    : i18n.t("audit.secRoleSupporting");
}

function secIdentityLabel(status) {
  if (status === "verified") return i18n.t("audit.identityVerified");
  if (status === "lifecycle_conflict") return i18n.t("audit.identityLifecycleConflict");
  if (status === "mismatch") return i18n.t("audit.identityMismatch");
  return i18n.t("audit.identityPending");
}

function secOutcomeLabel(status) {
  return status === "verified" ? i18n.t("audit.terminalVerified") : i18n.t("audit.terminalPending");
}

function secFactorGateText(asset) {
  if (asset.factor_eligible) return i18n.t("audit.secFactorReady");
  if (asset.factor_block_reason === "terminal_outcome_already_verified") {
    return i18n.t("audit.secAlreadyVerified");
  }
  if (asset.factor_block_reason === "price_series_not_ready") {
    return i18n.t("audit.secPriceBlocked");
  }
  if (asset.factor_block_reason === "terminal_evidence_not_accepted") {
    return i18n.t("audit.secTerminalEvidenceBlocked");
  }
  if (asset.factor_block_reason === "lifecycle_resolution_pending") {
    return lifecycleResolutionLabel(asset.lifecycle_resolution_type);
  }
  return i18n.t("audit.secIdentityBlocked");
}

async function reviewSecEvidence(evidenceKey, decision, reviewRole = null) {
  const note = elements.secEvidenceList.querySelector(`[data-sec-note="${evidenceKey}"]`)?.value.trim() || "";
  if (note.length < 10) {
    elements.secEvidenceStatus.textContent = i18n.t("audit.secReviewNote");
    return;
  }
  state.secBusyKey = evidenceKey;
  renderSecEvidence();
  let statusMessage = i18n.t("audit.secReviewSaved");
  try {
    await apiMutation(`/markets/historical-delisting-evidence/${encodeURIComponent(evidenceKey)}/review`, {
      method: "POST",
      body: JSON.stringify({ decision, review_role: reviewRole, review_note: note }),
    });
    await loadSecEvidence();
  } catch (error) {
    statusMessage = `${i18n.t("audit.secReviewFailed")}: ${error.message}`;
  } finally {
    state.secBusyKey = null;
    renderSecEvidence();
    elements.secEvidenceStatus.textContent = statusMessage;
  }
}

async function materializeSecEvidence(assetKey, evidenceKey) {
  const asset = state.secEvidence?.assets.find((item) => item.asset_key === assetKey);
  const candidate = asset?.candidates.find((item) => item.evidence_key === evidenceKey);
  const paymentDate = elements.secEvidenceList.querySelector(`[data-sec-payment="${evidenceKey}"]`)?.value;
  const outcomeType = elements.secEvidenceList.querySelector(`[data-sec-outcome="${evidenceKey}"]`)?.value;
  if (!candidate || !paymentDate || !outcomeType) return;
  state.secBusyKey = evidenceKey;
  renderSecEvidence();
  let statusMessage = i18n.t("audit.secFactorAdded");
  try {
    await apiMutation(`/markets/historical-identity-audit/${encodeURIComponent(assetKey)}/outcome`, {
      method: "POST",
      body: JSON.stringify({
        evidence_key: candidate.evidence_key,
        outcome_type: outcomeType,
        terminal_value_per_share: candidate.candidate_value,
        payment_date: paymentDate,
        evidence_url: candidate.source_url,
        evidence_note: `${candidate.review_note || "Human-reviewed SEC evidence."} SEC ${candidate.form} filed ${candidate.filed_on}.`,
      }),
    });
    await loadSecEvidence();
  } catch (error) {
    statusMessage = `${i18n.t("audit.secFactorFailed")}: ${error.message}`;
  } finally {
    state.secBusyKey = null;
    renderSecEvidence();
    elements.secEvidenceStatus.textContent = statusMessage;
  }
}

function renderAIStatus() {
  if (!elements.aiStatePanel || !state.aiStatus) return;
  const { chains, model, training, generated_at: generatedAt } = state.aiStatus;
  const modelLabels = {
    current: "audit.modelCurrent",
    upgrade_detected: "audit.modelUpgradeDetected",
    configured_change_pending_run: "audit.modelChangePending",
    no_chain_history: "audit.modelNoHistory",
  };
  const trainingLabels = {
    retraining_confirmed: "audit.trainingConfirmed",
    signals_collected: "audit.trainingSignalsReady",
    no_signals: "audit.trainingNoSignals",
    manifest_invalid: "audit.trainingManifestInvalid",
  };
  const refreshLabels = {
    current: "audit.logicRefreshCurrent",
    pending: "audit.logicRefreshWaiting",
    retrying: "audit.logicRefreshRetrying",
  };
  elements.aiStatePanel.innerHTML = `
    <div class="ai-state-grid">
      <article class="ai-state-card is-new">
        <header><span>${escapeHtml(i18n.t("audit.newChains"))}</span>
          <strong>${Number(chains.new_24h).toLocaleString()}</strong></header>
        <dl>
          ${statusFact("audit.chainInventory", Number(chains.total).toLocaleString())}
          ${statusFact("audit.pendingReview", Number(chains.pending_review).toLocaleString())}
          ${statusFact("audit.chainsSinceTraining", Number(chains.since_last_training).toLocaleString())}
          ${statusFact("audit.researchRuns", Number(chains.research_runs).toLocaleString())}
        </dl>
      </article>
      <article class="ai-state-card is-validation">
        <header><span>${escapeHtml(i18n.t("audit.enhancedValidation"))}</span>
          <strong>${Number(chains.enhanced_evidence_validated).toLocaleString()} / ${Number(chains.validated).toLocaleString()}</strong></header>
        <p>${escapeHtml(i18n.t("audit.enhancedValidationDetail"))}</p>
        <dl>
          ${statusFact("audit.latestValidation", statusDate(chains.latest_validation_at))}
          ${statusFact("audit.latestEvidence", statusDate(chains.latest_evidence_snapshot_at))}
          ${statusFact("audit.latestClusterJob", chains.latest_completed_cluster_job_id || i18n.t("audit.noTimestamp"))}
          ${statusFact("audit.latestLogicJob", chains.latest_logic_cluster_job_id || i18n.t("audit.noTimestamp"))}
          ${statusFact("audit.logicRefreshPending", Number(chains.logic_refresh_pending_jobs || 0).toLocaleString())}
          ${statusFact("audit.logicRefreshState", i18n.t(refreshLabels[chains.logic_refresh_state] || "audit.logicRefreshCurrent"))}
        </dl>
      </article>
      <article class="ai-state-card is-${escapeHtml(model.state)}">
        <header><span>${escapeHtml(i18n.t("audit.modelUpgrade"))}</span>
          <b>${escapeHtml(i18n.t(modelLabels[model.state] || "audit.modelCurrent"))}</b></header>
        <dl>
          ${statusFact("audit.runtimeModel", model.runtime_model)}
          ${statusFact("audit.lastChainModel", model.last_chain_model || i18n.t("audit.noTimestamp"))}
          ${statusFact("audit.promptVersion", model.prompt_version || i18n.t("audit.noTimestamp"))}
          ${statusFact("audit.appVersion", model.app_version)}
        </dl>
      </article>
      <article class="ai-state-card is-training-${escapeHtml(training.state)}">
        <header><span>${escapeHtml(i18n.t("audit.trainingState"))}</span>
          <b>${escapeHtml(i18n.t(trainingLabels[training.state] || "audit.trainingNoSignals"))}</b></header>
        <dl>
          ${statusFact("audit.reviewSignals", Number(training.review_signal_count).toLocaleString())}
          ${statusFact("audit.signalsUsed", Number(training.signal_count_used).toLocaleString())}
          ${statusFact("audit.signalsPending", Number(training.pending_signal_count).toLocaleString())}
          ${statusFact("audit.verifiedMemory", Number(training.verified_memory_count || 0).toLocaleString())}
          ${statusFact("audit.externalPending", Number(training.external_pending_count || 0).toLocaleString())}
          ${statusFact("audit.externalApproved", Number(training.external_approved_count || 0).toLocaleString())}
          ${statusFact("audit.datasetReady", Number(training.training_dataset_ready_count || 0).toLocaleString())}
          ${training.training_run_id ? statusFact("audit.trainingRun", training.training_run_id) : ""}
          ${training.trained_at ? statusFact("audit.trainedAt", statusDate(training.trained_at)) : ""}
        </dl>
      </article>
    </div>
    <footer class="ai-state-footer">
      <p>${escapeHtml(i18n.t("audit.trainingBoundary"))}</p>
      <span>${escapeHtml(i18n.t("audit.statusSnapshot"))}: ${escapeHtml(statusDate(generatedAt))}</span>
    </footer>
  `;
}

function statusFact(labelKey, value) {
  return `<div><dt>${escapeHtml(i18n.t(labelKey))}</dt><dd>${escapeHtml(value)}</dd></div>`;
}

function statusDate(value) {
  return value ? formatDate(value) : i18n.t("audit.noTimestamp");
}

function renderMetrics() {
  const latestModel = state.inquiries.find((item) => item.local_model)?.local_model;
  elements.localModelStatus.textContent = latestModel || i18n.t("audit.ready");
  elements.openaiStatus.textContent = state.openaiConfigured
    ? i18n.t("audit.ready")
    : i18n.t("audit.notConfigured");
  const fixedCount = state.eventChain?.relations.filter((item) => item.pinned).length || 0;
  elements.fixedChainCount.textContent = `${fixedCount} ${i18n.t("audit.fixedCount")}`;
  elements.logicTrainingCount.textContent = `${
    state.aiStatus?.training.review_signal_count
      ?? state.logicChain?.training_signal_count
      ?? 0
  } ${i18n.t("audit.trainingCount")}`;
}

async function submitResearchQuestion() {
  const question = elements.researchQuestion.value.trim();
  if (question.length < 6) {
    elements.researchStatus.textContent = i18n.t("audit.researchRequired");
    return;
  }
  await runResearch("/research/inquiries", { question }, "audit.researchRunning");
}

function fillQuestionExample(kind) {
  const examples = i18n.language === "zh"
    ? {
        equity: "苹果（AAPL）未来6到12个月还能涨吗？哪些条件成立才更有可能，哪些证据会推翻这个判断？",
        event: "最近油价为什么上涨？请找出具体事件、传导过程、替代解释和能验证每一步的数据。",
        risk: "微软（MSFT）未来一年最重要的经营、估值、流动性和供应链风险是什么？",
      }
    : {
        equity: "Can Apple (AAPL) keep rising over the next 6–12 months? What conditions would support it and what evidence would invalidate the view?",
        event: "Why did oil rise recently? Find the event, transmission path, alternative explanations and data that verify each step.",
        risk: "What are Microsoft's (MSFT) most important operating, valuation, liquidity and supply-chain risks over the next year?",
      };
  elements.researchQuestion.value = examples[kind] || "";
  elements.researchQuestion.focus();
}

async function runAutonomousResearch() {
  await runResearch("/research/autonomous", null, "audit.autonomousRunning");
}

async function refreshForecasts() {
  elements.refreshForecasts.disabled = true;
  elements.researchStatus.textContent = i18n.t("audit.forecastRefreshing");
  try {
    const result = await apiMutation("/research/forecasts/revalidate", {
      method: "POST",
    });
    await loadResearch();
    elements.researchStatus.textContent = `${i18n.t("audit.forecastRefreshed")}: ${
      Number(result.forecasts_updated || 0)
    } / ${Number(result.forecasts_checked || 0)}`;
    renderResearch();
  } catch (error) {
    elements.researchStatus.textContent =
      `${i18n.t("audit.requestFailed")}: ${error.message}`;
  } finally {
    elements.refreshForecasts.disabled = false;
  }
}

async function reviewResearchReport(inquiryId, decision) {
  const note = elements.researchResults.querySelector(
    `[data-report-note="${inquiryId}"]`,
  )?.value.trim() || null;
  try {
    const inquiry = await apiMutation(`/research/inquiries/${inquiryId}/reviews`, {
      method: "POST",
      body: JSON.stringify({ decision, reviewer_note: note }),
    });
    storeInquiryDetail(inquiry);
    elements.researchStatus.textContent = i18n.t("audit.reportReviewRecorded");
    renderResearch();
  } catch (error) {
    elements.researchStatus.textContent =
      `${i18n.t("audit.requestFailed")}: ${error.message}`;
  }
}

async function remineFactors(inquiryId) {
  const button = (elements.factorResults || document).querySelector(
    `[data-factor-mine="${inquiryId}"]`,
  );
  if (button) button.disabled = true;
  elements.researchStatus.textContent = i18n.t("audit.factorMining");
  try {
    const inquiry = await apiMutation(
      `/research/inquiries/${inquiryId}/factor-mine`,
      { method: "POST" },
    );
    storeInquiryDetail(inquiry);
    elements.researchStatus.textContent = i18n.t("audit.factorMined");
    renderResearch();
  } catch (error) {
    elements.researchStatus.textContent =
      `${i18n.t("audit.requestFailed")}: ${error.message}`;
    if (button) button.disabled = false;
  }
}

async function runResearch(endpoint, body, pendingKey) {
  setResearchBusy(true);
  elements.researchStatus.textContent = i18n.t(pendingKey);
  try {
    const inquiry = await apiMutation(endpoint, {
      method: "POST",
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    storeInquiryDetail(inquiry, { select: true });
    elements.researchStatus.textContent = i18n.t("audit.researchCompleted");
    renderMetrics();
    renderResearch();
    void refreshAIStatus();
  } catch (error) {
    elements.researchStatus.textContent =
      `${i18n.t("audit.researchFailed")}: ${error.message}`;
  } finally {
    setResearchBusy(false);
  }
}

function setResearchBusy(busy) {
  elements.researchSubmit.disabled = busy;
  elements.researchAutonomous.disabled = busy;
}

async function requestResearchReview(inquiryId) {
  const button = elements.researchResults.querySelector(
    `[data-chatgpt-review="${inquiryId}"]`,
  );
  if (button) button.disabled = true;
  elements.researchStatus.textContent = i18n.t("audit.chatgptRunning");
  try {
    const inquiry = await apiMutation(
      `/research/inquiries/${inquiryId}/chatgpt-review`,
      { method: "POST" },
    );
    storeInquiryDetail(inquiry);
    elements.researchStatus.textContent = i18n.t("audit.chatgptComplete");
    renderResearch();
  } catch (error) {
    elements.researchStatus.textContent =
      `${i18n.t("audit.requestFailed")}: ${error.message}`;
    if (button) button.disabled = false;
  }
}

function renderResearchQueues() {
  if (elements.researchBatchList) {
    if (!state.researchBatches.length) {
      elements.researchBatchList.innerHTML = `<div class="empty-card">${escapeHtml(i18n.t("audit.batchEmpty"))}</div>`;
    } else {
      elements.researchBatchList.innerHTML = state.researchBatches.map((batch) => {
        const statusKey = {
          queued: "audit.queueQueued",
          running: "audit.queueRunning",
          completed: "audit.queueCompleted",
          partial_failed: "audit.queuePartial",
          failed: "audit.queueFailed",
        }[batch.status] || batch.status;
        const canRetry = batch.failed_count > 0 && !["queued", "running"].includes(batch.status);
        return `
          <article class="research-batch-card is-${escapeAttribute(batch.status)}">
            <header>
              <b>#${Number(batch.id)} · ${escapeHtml(batch.name)}</b>
              <span>${escapeHtml(i18n.t(statusKey))} · ${Number(batch.completed_count)}/${Number(batch.target_count)}</span>
            </header>
            <div class="research-progress"><i style="width:${Math.max(0, Math.min(100, Number(batch.progress_percent || 0)))}%"></i></div>
            <div class="research-batch-items">
              ${batch.items.map((item) => `
                <div class="research-batch-item is-${escapeAttribute(item.status)}">
                  <span class="research-item-main"><b>${escapeHtml(item.company_name)} · ${escapeHtml(item.ticker)}</b><br>
                    <small>${escapeHtml(i18n.t(item.market_region === "us" ? "audit.scopeUS" : "audit.scopeChina"))}</small>
                    <span class="research-item-progress"><i style="width:${Math.max(0, Math.min(100, Number(item.progress_percent || 0)))}%"></i></span>
                    <small>${escapeHtml(item.progress_message || item.progress_stage || "")}${item.status === "running" ? ` · ${Math.round(Number(item.progress_percent || 0))}%` : ""}</small></span>
                  <small>${escapeHtml(i18n.t({
                    queued: "audit.queueQueued",
                    running: "audit.queueRunning",
                    completed: "audit.queueCompleted",
                    failed: "audit.queueFailed",
                  }[item.status] || item.status))}${item.inquiry_id ? ` · #${Number(item.inquiry_id)}` : ""}</small>
                </div>
              `).join("")}
            </div>
            ${canRetry ? `<button class="button ghost" type="button" data-retry-batch="${Number(batch.id)}">${escapeHtml(i18n.t("audit.retryBatch"))}</button>` : ""}
          </article>
        `;
      }).join("");
    }
  }
  if (!elements.reportAuditQueue) return;
  const queue = state.reportAuditQueue;
  if (!queue) {
    elements.reportAuditQueue.innerHTML = `<div class="empty-card">${escapeHtml(i18n.t("audit.auditQueueEmpty"))}</div>`;
    return;
  }
  elements.reportAuditQueue.innerHTML = `
    <article class="report-audit-card">
      <header><b>${escapeHtml(i18n.t("audit.frozenAudit"))}</b>
        <span>${escapeHtml(formatDate(queue.latest_completed_at))}</span></header>
      <div class="report-audit-metrics">
        <span><b>${Number(queue.queued)}</b>${escapeHtml(i18n.t("audit.queueQueued"))}</span>
        <span><b>${Number(queue.running)}</b>${escapeHtml(i18n.t("audit.queueRunning"))}</span>
        <span><b>${Number(queue.completed)}</b>${escapeHtml(i18n.t("audit.queueCompleted"))}</span>
        <span><b>${Number(queue.failed)}</b>${escapeHtml(i18n.t("audit.queueFailed"))}</span>
        <span><b>${Number(queue.superseded)}</b>${escapeHtml(i18n.t("audit.queueSuperseded"))}</span>
      </div>
    </article>
  `;
}

function renderResearchContext() {
  if (!elements.researchInquirySelect || !elements.researchContextMeta) return;
  renderCatalogPagination();
  if (!state.inquirySummaries.length) {
    elements.researchInquirySelect.innerHTML = `<option value="">${escapeHtml(i18n.t("audit.contextEmpty"))}</option>`;
    elements.researchInquirySelect.disabled = true;
    elements.researchContextMeta.textContent = i18n.t("audit.contextEmpty");
    return;
  }
  elements.researchInquirySelect.disabled = state.researchLoading;
  const options = state.inquirySummaries.map((inquiry) => {
    const question = inquiry.question || `#${inquiry.id}`;
    const conciseQuestion = question.length > 72 ? `${question.slice(0, 69)}…` : question;
    const subject = [inquiry.ticker, inquiry.company_name].filter(Boolean).join(" · ");
    return `<option value="${Number(inquiry.id)}">#${Number(inquiry.id)} · ${
      escapeHtml(formatDate(inquiry.created_at))
    }${subject ? ` · ${escapeHtml(subject)}` : ""} · ${escapeHtml(conciseQuestion)}</option>`;
  });
  elements.researchInquirySelect.innerHTML = [
    ...options,
    `<option value="all">${escapeHtml(i18n.t("audit.contextAll"))}</option>`,
  ].join("");
  elements.researchInquirySelect.value = state.showAllInquiries
    ? "all"
    : String(state.selectedInquiryId || state.inquirySummaries[0].id);

  if (state.researchLoading) {
    elements.researchContextMeta.textContent = i18n.t("audit.contextLoading");
    return;
  }

  if (state.showAllInquiries) {
    elements.researchContextMeta.textContent = `${i18n.t("audit.contextAll")} · ${Math.min(4, state.inquirySummaries.length)} / ${state.inquirySummaries.length}`;
    return;
  }
  const selected = state.inquirySummaries.find((item) => item.id === state.selectedInquiryId)
    || state.inquirySummaries[0];
  elements.researchContextMeta.innerHTML = `
    <span>${escapeHtml(i18n.t("audit.contextLocal"))}<b>${escapeHtml(selected.local_model || "—")}</b></span>
    <span>${escapeHtml(i18n.t("audit.contextCreated"))}<b>${escapeHtml(formatDate(selected.created_at))}</b></span>
    <span>ID<b>#${Number(selected.id)}</b></span>
  `;
}

function renderCatalogPagination() {
  if (!elements.catalogStats) return;
  const currentPage = state.catalog.pages ? state.catalog.page : 0;
  elements.catalogStats.textContent = `${state.catalog.total} ${i18n.t("audit.catalogReports")} · ${i18n.t("audit.catalogPage")} ${currentPage}/${state.catalog.pages}`;
  if (elements.catalogPrev) {
    elements.catalogPrev.disabled = state.researchLoading || state.catalog.page <= 1;
  }
  if (elements.catalogNext) {
    elements.catalogNext.disabled = state.researchLoading
      || state.catalog.pages === 0
      || state.catalog.page >= state.catalog.pages;
  }
}

function renderReportComparison() {
  if (!elements.reportComparisonSummary || !elements.reportComparisonList) return;
  if (state.showAllInquiries) {
    elements.reportComparisonSummary.textContent = i18n.t("audit.contextAll");
    elements.reportComparisonList.innerHTML = "";
    return;
  }
  if (state.reportComparisonLoading) {
    elements.reportComparisonSummary.textContent = i18n.t("audit.comparisonLoading");
    elements.reportComparisonList.innerHTML = `
      <div class="report-comparison-loading" aria-hidden="true"><span></span><span></span><span></span></div>
    `;
    return;
  }
  const comparison = state.reportComparison;
  if (!comparison) {
    elements.reportComparisonSummary.textContent = "—";
    elements.reportComparisonList.innerHTML = "";
    return;
  }
  if (comparison.error) {
    elements.reportComparisonSummary.textContent = i18n.t("audit.comparisonFailed");
    elements.reportComparisonList.innerHTML = `
      <div class="empty-card">${escapeHtml(comparison.error)}</div>
    `;
    return;
  }
  const versions = comparison.versions || [];
  const selectedIndex = versions.findIndex((item) => item.is_selected);
  const selected = versions[selectedIndex >= 0 ? selectedIndex : 0];
  const previous = selectedIndex >= 0 ? versions[selectedIndex + 1] : null;
  const subject = [comparison.ticker, comparison.company_name].filter(Boolean).join(" · ");
  elements.reportComparisonSummary.innerHTML = `
    <b>${escapeHtml(subject || i18n.t("audit.comparisonUnavailable"))}</b>
    <span>${Number(comparison.total_versions || versions.length)} ${escapeHtml(i18n.t("audit.comparisonVersions"))}</span>
  `;
  if (!selected) {
    elements.reportComparisonList.innerHTML = `
      <div class="empty-card">${escapeHtml(i18n.t("audit.comparisonUnavailable"))}</div>
    `;
    return;
  }
  const overview = `
    <div class="report-comparison-overview">
      ${comparisonMetric(
        "audit.comparisonConfidence",
        comparisonPercent(selected.confidence),
        comparisonDelta(selected.confidence, previous?.confidence, true),
      )}
      ${comparisonMetric(
        "audit.comparisonReadiness",
        comparisonPercent(selected.data_readiness_score),
        comparisonDelta(selected.data_readiness_score, previous?.data_readiness_score, true),
      )}
      ${comparisonMetric(
        "audit.comparisonEvidence",
        String(Number(selected.evidence_count || 0)),
        evidenceDelta(selected),
      )}
      ${comparisonMetric(
        "audit.comparisonVerified",
        String(Number(selected.verified_steps || 0)),
        comparisonDelta(selected.verified_steps, previous?.verified_steps),
      )}
      ${comparisonMetric(
        "audit.comparisonUnresolved",
        String(Number(selected.unresolved_steps || 0)),
        comparisonDelta(selected.unresolved_steps, previous?.unresolved_steps),
      )}
    </div>
  `;
  const notice = comparison.comparable
    ? ""
    : `<p class="report-comparison-note">${escapeHtml(
      comparison.reason === "historical_reconstruction"
        ? (i18n.language === "en" ? "Retrospective report: not mixed with live market reports for trend or return calculations." : "历史回溯报告：不与当前市场报告混合计算趋势或收益。")
        : comparison.reason === "single_company_report"
        ? i18n.t("audit.comparisonSingle")
        : i18n.t("audit.comparisonUnavailable"),
    )}</p>`;
  elements.reportComparisonList.innerHTML = `
    ${comparison.reason === "historical_reconstruction" ? "" : overview}
    ${notice}
    <div class="report-version-track">
      ${versions.map((version) => renderReportVersion(version)).join("")}
    </div>
  `;
}

function comparisonMetric(labelKey, value, delta = "") {
  return `<span><small>${escapeHtml(i18n.t(labelKey))}</small><b>${escapeHtml(value)}</b>${
    delta ? `<em>${escapeHtml(delta)}</em>` : ""
  }</span>`;
}

function comparisonPercent(value) {
  return value === null || value === undefined
    ? i18n.t("audit.comparisonNoValue")
    : `${Math.round(Number(value) * 100)}%`;
}

function comparisonDelta(current, previous, asPercent = false) {
  if (current === null || current === undefined || previous === null || previous === undefined) {
    return "";
  }
  const difference = Number(current) - Number(previous);
  if (Math.abs(difference) < 0.0001) return "±0";
  const rendered = asPercent
    ? `${Math.abs(difference * 100).toFixed(0)}pp`
    : Math.abs(difference).toLocaleString();
  return `${difference > 0 ? "+" : "−"}${rendered}`;
}

function evidenceDelta(version) {
  if (version.new_evidence_count === null || version.new_evidence_count === undefined) return "";
  return `+${Number(version.new_evidence_count)} ${i18n.t("audit.comparisonNewEvidence")} · −${
    Number(version.retired_evidence_count || 0)
  } ${i18n.t("audit.comparisonRetiredEvidence")}`;
}

function renderReportVersion(version) {
  const signalKey = {
    bullish: "audit.signalBullish",
    bearish: "audit.signalBearish",
    mixed: "audit.signalMixed",
    unknown: "audit.signalUnknown",
  }[version.primary_signal] || "audit.signalUnknown";
  const priceReferences = [
    ["audit.comparisonEntry", version.entry_reference],
    ["audit.comparisonStop", version.stop_reference],
    ["audit.comparisonTarget", version.target_reference],
  ].filter(([, value]) => value !== null && value !== undefined);
  return `
    <article class="report-version-card is-${escapeAttribute(version.primary_signal || "unknown")}${
      version.is_selected ? " is-selected" : ""
    }">
      <header>
        <div>
          <span class="report-version-dot"></span>
          <b>#${Number(version.inquiry_id)} · ${escapeHtml(formatDate(version.created_at))}</b>
        </div>
        <span>${escapeHtml(version.is_selected
          ? i18n.t("audit.comparisonSelected")
          : reportVersionStatus(version.status))}</span>
      </header>
      <div class="report-version-metrics">
        <span><small>${escapeHtml(i18n.t("audit.comparisonConfidence"))}</small><b>${escapeHtml(comparisonPercent(version.confidence))}</b></span>
        <span><small>${escapeHtml(i18n.t("audit.comparisonReadiness"))}</small><b>${escapeHtml(comparisonPercent(version.data_readiness_score))}</b></span>
        <span><small>${escapeHtml(i18n.t("audit.comparisonSignal"))}</small><b>${escapeHtml(i18n.t(signalKey))}</b></span>
        <span><small>${escapeHtml(i18n.t("audit.comparisonTiming"))}</small><b>${escapeHtml(version.timing_assessment || i18n.t("audit.comparisonNoValue"))}</b></span>
        <span><small>${escapeHtml(i18n.t("audit.comparisonCitations"))}</small><b>${Number(version.cited_reference_count || 0)}</b></span>
        <span><small>${escapeHtml(i18n.t("audit.comparisonRiskReward"))}</small><b>${version.reward_risk_ratio === null || version.reward_risk_ratio === undefined
          ? escapeHtml(i18n.t("audit.comparisonNoValue"))
          : `${Number(version.reward_risk_ratio).toFixed(2)}×`}</b></span>
      </div>
      ${priceReferences.length ? `<div class="report-version-prices">${priceReferences.map(
        ([label, value]) => `<span>${escapeHtml(i18n.t(label))}<b>${escapeHtml(
          Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 }),
        )}</b></span>`,
      ).join("")}</div>` : ""}
      ${renderComparisonChangeSummary(version)}
      ${renderComparisonEvidenceChanges(version)}
      <p>${escapeHtml(version.summary || version.question || i18n.t("audit.comparisonNoValue"))}</p>
      <footer>
        <span>${escapeHtml(evidenceDelta(version))}</span>
        <button class="button ghost" type="button" data-comparison-report="${Number(version.inquiry_id)}"
          ${version.is_selected ? "disabled" : ""}>${escapeHtml(version.is_selected
            ? i18n.t("audit.comparisonSelected")
            : i18n.t("audit.comparisonOpen"))}</button>
      </footer>
    </article>
  `;
}

function renderComparisonChangeSummary(version) {
  const change = version.change_summary;
  if (!change) return "";
  const reasons = [];
  if (change.confidence_delta !== null && Math.abs(change.confidence_delta) >= 0.005) {
    reasons.push(`${i18n.t("audit.comparisonConfidence")}: ${formatSignedChange(
      change.confidence_delta * 100,
      "pp",
    )}`);
  }
  if (change.data_readiness_delta !== null && Math.abs(change.data_readiness_delta) >= 0.005) {
    reasons.push(`${i18n.t("audit.comparisonReadiness")}: ${formatSignedChange(
      change.data_readiness_delta * 100,
      "pp",
    )}`);
  }
  if (change.verified_steps_delta) {
    reasons.push(`${i18n.t("audit.changeVerified")}: ${formatSignedChange(
      change.verified_steps_delta,
    )}`);
  }
  if (change.unresolved_steps_delta) {
    reasons.push(`${i18n.t("audit.changeUnresolved")}: ${formatSignedChange(
      change.unresolved_steps_delta,
    )}`);
  }
  const addedMix = renderEvidenceCategoryMix(change.new_category_counts);
  const retiredMix = renderEvidenceCategoryMix(change.retired_category_counts);
  if (addedMix) reasons.push(`${i18n.t("audit.changeAddedMix")}: ${addedMix}`);
  if (retiredMix) reasons.push(`${i18n.t("audit.changeRetiredMix")}: ${retiredMix}`);
  if (change.primary_signal_from !== change.primary_signal_to) {
    reasons.push(`${i18n.t("audit.changeSignal")}: ${comparisonSignalLabel(
      change.primary_signal_from,
    )} → ${comparisonSignalLabel(change.primary_signal_to)}`);
  }
  if (change.timing_from !== change.timing_to) {
    reasons.push(`${i18n.t("audit.changeTiming")}: ${change.timing_from || "—"} → ${
      change.timing_to || "—"
    }`);
  }
  if (change.current_price_delta !== null && Math.abs(change.current_price_delta) >= 0.0001) {
    reasons.push(`${i18n.t("audit.changeCurrentPrice")}: ${formatSignedChange(
      change.current_price_delta,
    )}`);
  }
  if (change.reward_risk_delta !== null && Math.abs(change.reward_risk_delta) >= 0.0001) {
    reasons.push(`${i18n.t("audit.changeRiskReward")}: ${formatSignedChange(
      change.reward_risk_delta,
    )}`);
  }
  if (change.model_changed) reasons.push(i18n.t("audit.changeModel"));
  if (change.audit_status_from !== change.audit_status_to) {
    reasons.push(`${i18n.t("audit.changeAudit")}: ${change.audit_status_from || "—"} → ${
      change.audit_status_to || "—"
    }`);
  }
  if (change.summary_changed) reasons.push(i18n.t("audit.changeConclusion"));
  return `
    <section class="report-change-summary">
      <header><b>${escapeHtml(i18n.t("audit.changeSummaryTitle"))}</b></header>
      <p>${escapeHtml(i18n.t("audit.changeSummaryNotice"))}</p>
      <ul>${(reasons.length ? reasons : [i18n.t("audit.changeNoMaterial")]).map(
        (reason) => `<li>${escapeHtml(reason)}</li>`,
      ).join("")}</ul>
    </section>
  `;
}

function formatSignedChange(value, suffix = "") {
  const number = Number(value);
  const absolute = Math.abs(number);
  const rendered = absolute >= 10
    ? absolute.toFixed(0)
    : absolute.toFixed(2).replace(/\.00$/, "").replace(/(\.\d)0$/, "$1");
  if (Math.abs(number) < 0.0001) return `±0${suffix}`;
  return `${number > 0 ? "+" : "−"}${rendered}${suffix}`;
}

function renderEvidenceCategoryMix(counts) {
  return Object.entries(counts || {}).map(([category, count]) =>
    `${comparisonEvidenceCategoryLabel(category)} ×${Number(count)}`
  ).join(i18n.language === "zh" ? "、" : ", ");
}

function comparisonEvidenceCategoryLabel(category) {
  const labels = {
    derived_company_financial_trend: ["财务趋势", "Financial trend"],
    derived_market_technical: ["技术面", "Technicals"],
    derived_macro_sensitivity: ["宏观敏感度", "Macro sensitivity"],
    derived_company_valuation: ["公司估值", "Valuation"],
    derived_institutional_positioning: ["机构持仓", "Institutional positioning"],
    derived_supplier_factor: ["供应商因子", "Supplier factor"],
    company_filing: ["公司公告/财报", "Company filing"],
    company_news_document: ["公司新闻", "Company news"],
    product_operating_evidence: ["产品经营", "Product operations"],
    institutional_holding: ["机构申报", "Institutional filing"],
    insider_transaction: ["内部人交易", "Insider transaction"],
    verified_supply_chain_edge: ["已核验供应链", "Verified supply chain"],
    supply_chain_site_exposure: ["供应链设施风险", "Supply-chain site exposure"],
    treasury_yield: ["国债收益率", "Treasury yield"],
    currency_index: ["汇率/美元指数", "Currency index"],
    uncategorized: ["未分类", "Uncategorized"],
  };
  const pair = labels[category];
  return pair ? pair[i18n.language === "zh" ? 0 : 1] : category;
}

function comparisonSignalLabel(signal) {
  const key = {
    bullish: "audit.signalBullish",
    bearish: "audit.signalBearish",
    mixed: "audit.signalMixed",
    unknown: "audit.signalUnknown",
  }[signal] || "audit.signalUnknown";
  return i18n.t(key);
}

function renderComparisonEvidenceChanges(version) {
  const added = version.new_evidence || [];
  const removed = version.retired_evidence || [];
  const hasComparison = version.new_evidence_count !== null
    && version.new_evidence_count !== undefined;
  if (!hasComparison) return "";
  const lists = [
    ["audit.comparisonAdded", added, version.new_evidence_count, "is-added"],
    ["audit.comparisonRemoved", removed, version.retired_evidence_count, "is-removed"],
  ].filter(([, items, count]) => items.length || Number(count || 0) > 0);
  return `
    <details class="report-evidence-changes">
      <summary>${escapeHtml(i18n.t("audit.comparisonEvidenceDetails"))}
        <span>+${Number(version.new_evidence_count || 0)} / −${Number(
          version.retired_evidence_count || 0,
        )}</span>
      </summary>
      ${lists.length ? lists.map(([labelKey, items, count, className]) => `
        <section class="${className}">
          <header><b>${escapeHtml(i18n.t(labelKey))}</b><span>${Number(count || 0)}</span></header>
          <ul>${items.map((item) => `
            <li>
              <b>${escapeHtml(item.title || item.evidence_id)}</b>
              <small>${escapeHtml([
                item.category,
                item.observed_at,
                item.source,
              ].filter(Boolean).join(" · ") || i18n.t("audit.comparisonNoValue"))}</small>
              <code title="${escapeAttribute(item.evidence_id)}">${escapeHtml(item.evidence_id)}</code>
            </li>
          `).join("")}</ul>
          ${Number(count || 0) > items.length ? `<p>${escapeHtml(
            i18n.t("audit.comparisonShowing"),
          )}</p>` : ""}
        </section>
      `).join("") : `<p>${escapeHtml(i18n.t("audit.comparisonNoEvidenceChanges"))}</p>`}
    </details>
  `;
}

function reportVersionStatus(status) {
  const labels = {
    completed: "audit.queueCompleted",
    running: "audit.queueRunning",
    failed: "audit.queueFailed",
  };
  return i18n.t(labels[status] || status);
}

function renderResearch() {
  renderResearchContext();
  renderReportComparison();
  const empty = (key) => `<div class="empty-card">${escapeHtml(i18n.t(key))}</div>`;
  if (!state.inquiries.length) {
    elements.researchResults.innerHTML = empty("audit.noResearch");
    if (elements.factorResults) elements.factorResults.innerHTML = empty("audit.noFactorResults");
    if (elements.inquiryEvidenceResults) elements.inquiryEvidenceResults.innerHTML = empty("audit.noEvidenceResults");
    if (elements.newsResults) elements.newsResults.innerHTML = empty("audit.noNewsResults");
    return;
  }

  const reportCards = [];
  const factorCards = [];
  const evidenceCards = [];
  const newsCards = [];

  const visibleInquiries = state.showAllInquiries
    ? state.inquiries
    : state.inquiries.filter((item) => item.id === state.selectedInquiryId);

  visibleInquiries.forEach((inquiry) => {
    const result = inquiry.result;
    if (!result) {
      reportCards.push(`<article class="research-card">
        <h3>${escapeHtml(inquiry.question)}</h3>
        <p>${escapeHtml(inquiry.error || inquiry.status)}</p>
      </article>`);
      return;
    }
    const citedEvidence = new Set(
      (result.hypotheses || []).flatMap((hypothesis) =>
        hypothesis.steps.flatMap((step) => step.evidence_refs || [])
      ),
    );
    const header = renderInquiryWorkspaceHeader(inquiry, result);

    reportCards.push(`
      <article class="research-card report-review-card">
        ${header}
        <p><a class="button ghost" href="/provenance-console?kind=report&id=${Number(inquiry.id)}">${i18n.language === "en" ? "Provenance & submission" : "查看此报告存证与提交"}</a></p>
        ${renderQuestionAssistance(inquiry.evidence_snapshot?.question_assistance)}
        ${renderPlainLanguageReport(
          inquiry.evidence_snapshot?.plain_language_report,
          inquiry.evidence_snapshot?.directional_confidence,
        )}
        ${renderTradingScenario(
          inquiry.evidence_snapshot?.derived_equity_evidence,
        )}
        ${renderCanslimAndCompetitor(
          inquiry.evidence_snapshot?.derived_equity_evidence,
        )}
        ${renderPaperReport(result.paper_report)}
        ${inquiry.evidence_snapshot?.report_audit?.reviewer === "codex_assistant" ? `<details class="report-audit-notes"><summary>${i18n.language === "en" ? "Codex review changes (not human acceptance)" : "Codex 审计修订记录（不等于人工接受）"}</summary><ul>${(inquiry.evidence_snapshot.report_audit.corrections || []).map(note => `<li>${escapeHtml(note)}</li>`).join("")}</ul></details>` : ""}
        <p class="research-summary">${escapeHtml(result.summary)}</p>
        ${renderEquityDimensions(result.equity_dimensions)}
        ${renderEquityDecisionFramework(result.equity_decision_framework)}
        ${renderSecondOpinion(inquiry.chatgpt_review)}
        ${renderResearchReview(inquiry)}
        ${renderInquiryWorkspaceFooter(inquiry)}
      </article>
    `);

    const factorBody = renderFactorResearch(result.factor_research, inquiry.id);
    if (factorBody) {
      factorCards.push(`<article class="research-card factor-workspace-card">
        ${header}${factorBody}
      </article>`);
    }

    const evidenceBody = `
      ${renderResearchWorkflow(inquiry.evidence_snapshot?.research_workflow)}
      ${renderResearchEventTable(
        inquiry.evidence_snapshot?.research_event_table,
        inquiry.evidence_snapshot?.preferred_research_period,
      )}
      ${renderResearchRetrieval(inquiry.evidence_snapshot?.evidence_retrieval)}
      ${renderEvidenceCompletion(inquiry.evidence_snapshot?.bridge_evidence_completion)}
      ${renderResearchHypotheses(inquiry, result.hypotheses || [])}
    `.trim();
    if (evidenceBody) {
      evidenceCards.push(`<article class="research-card evidence-workspace-card">
        ${header}${evidenceBody}
      </article>`);
    }

    const newsBody = `
      ${renderNewsEvidenceSequences(
        inquiry.evidence_snapshot?.news_evidence_sequences,
        citedEvidence,
      )}
      ${renderNewsForecasts(
        result.news_forecasts,
        inquiry.evidence_snapshot?.forecast_validation_cases,
      )}
    `.trim();
    if (newsBody) {
      newsCards.push(`<article class="research-card news-workspace-card">
        ${header}${newsBody}
      </article>`);
    }
  });

  elements.researchResults.innerHTML = reportCards.join("") || empty("audit.noResearch");
  if (elements.factorResults) {
    elements.factorResults.innerHTML = factorCards.join("") || empty("audit.noFactorResults");
  }
  if (elements.inquiryEvidenceResults) {
    elements.inquiryEvidenceResults.innerHTML = evidenceCards.join("") || empty("audit.noEvidenceResults");
  }
  if (elements.newsResults) {
    elements.newsResults.innerHTML = newsCards.join("") || empty("audit.noNewsResults");
  }
}

function renderInquiryWorkspaceHeader(inquiry, result) {
  return `<header>
    <div>
      <span>${escapeHtml(i18n.t(
        inquiry.mode === "autonomous" ? "audit.aiQuestion" : "audit.userQuestion",
      ))}</span>
      <h3>${escapeHtml(result.question)}</h3>
    </div>
    <small>${escapeHtml(inquiry.local_model)} · ${escapeHtml(formatDate(inquiry.created_at))}</small>
  </header>`;
}

function renderInquiryWorkspaceFooter(inquiry) {
  return `<footer>
    <time>${escapeHtml(formatDate(inquiry.created_at))}</time>
    <button type="button" data-chatgpt-review="${inquiry.id}" ${
      !state.openaiConfigured || inquiry.chatgpt_review ? "disabled" : ""
    }>${escapeHtml(
      inquiry.chatgpt_review
        ? i18n.t("audit.chatgptReviewed")
        : state.openaiConfigured
          ? i18n.t("audit.chatgptReview")
          : i18n.t("audit.chatgptUnavailable"),
    )}</button>
  </footer>`;
}

function renderResearchHypotheses(inquiry, hypotheses) {
  return hypotheses.map((hypothesis) => `
    <section class="research-hypothesis">
      <div class="score-heading">
        <h4>${escapeHtml(hypothesis.title)}</h4>
        <strong>${percent(hypothesis.confidence)}</strong>
      </div>
      ${renderDirectionalConfidence(inquiry.evidence_snapshot?.directional_confidence)}
      <div class="scope-list">${renderScope(hypothesis.scope)}</div>
      <ol class="research-steps">
        ${hypothesis.steps.map((step) => `
          <li class="is-${escapeHtml(step.status)}">
            <i>${step.sequence}</i>
            <div>
              <b>${escapeHtml(step.label)}</b>
              <small>${escapeHtml(researchStatusLabel(step.status))}
                · ${percent(step.confidence)}${
                  step.evidence_refs?.length
                    ? ` · ${escapeHtml(step.evidence_refs.join(" · "))}`
                    : ""
                }</small>
            </div>
          </li>
        `).join("")}
      </ol>
      ${hypothesis.evidence_gaps?.length ? `
        <details>
          <summary>${escapeHtml(i18n.t("audit.evidenceGaps"))}</summary>
          <ul>${hypothesis.evidence_gaps.map(
            (item) => `<li>${escapeHtml(item)}</li>`,
          ).join("")}</ul>
        </details>
      ` : ""}
    </section>
  `).join("");
}

function localizedField(value, stem) {
  if (!value) return "";
  return i18n.language === "zh"
    ? (value[`${stem}_zh`] || value[`${stem}_en`] || "")
    : (value[`${stem}_en`] || value[`${stem}_zh`] || "");
}

function renderQuestionAssistance(assistance) {
  if (!assistance?.applied) return "";
  return `
    <details class="question-assistance-card">
      <summary>${escapeHtml(i18n.t("audit.questionExpanded"))}</summary>
      <b>${escapeHtml(i18n.t("audit.originalQuestion"))}</b>
      <p>${escapeHtml(assistance.original_question)}</p>
      <b>${escapeHtml(i18n.t("audit.expandedBrief"))}</b>
      <p>${escapeHtml(assistance.expanded_research_brief)}</p>
    </details>
  `;
}

function renderPlainLanguageReport(report, confidence) {
  if (!report) return "";
  const terms = report.terms || [];
  return `
    <section class="plain-language-report">
      <header><div><span>PLAIN-LANGUAGE LAYER</span>
        <h4>${escapeHtml(localizedField(report, "title") || i18n.t("audit.plainReport"))}</h4></div>
        <strong>${confidence?.score == null ? "—" : percent(confidence.score)}</strong></header>
      <p>${escapeHtml(localizedField(report, "summary"))}</p>
      <div class="plain-verdicts">
        <span>${escapeHtml(localizedField(report, "data_quality"))}</span>
        <span>${escapeHtml(localizedField(report, "trade_signal"))}</span>
      </div>
      <p class="confidence-note">${escapeHtml(localizedField(report, "confidence_note"))}</p>
      ${terms.length ? `<details open><summary>${escapeHtml(i18n.t("audit.professionalTerms"))}</summary>
        <div class="term-glossary">${terms.map((item) => `<article>
          <b>${escapeHtml(item.term)} · ${escapeHtml(localizedField(item, "name"))}</b>
          <p>${escapeHtml(localizedField(item, "plain"))}</p>
        </article>`).join("")}</div></details>` : ""}
    </section>
  `;
}

function renderDirectionalConfidence(confidence) {
  if (!confidence?.components?.length) return "";
  const blockers = i18n.language === "zh"
    ? confidence.blockers_zh || [] : confidence.blockers_en || [];
  const actions = i18n.language === "zh"
    ? confidence.improvement_actions_zh || [] : confidence.improvement_actions_en || [];
  return `
    <details class="directional-confidence" open>
      <summary>${escapeHtml(i18n.t("audit.directionalSupport"))} · ${percent(confidence.score)}</summary>
      <p>${escapeHtml(i18n.t("audit.notProbability"))}</p>
      <div class="directional-components">${confidence.components.map((item) => `
        <span class="is-${escapeAttribute(item.status)}"><i style="width:${Math.max(0, Math.min(100, Number(item.score || 0) * 100))}%"></i>
          <b>${Number(item.sequence)} · ${percent(item.score)}</b><small>${escapeHtml(researchStatusLabel(item.status))}</small></span>
      `).join("")}</div>
      ${blockers.length ? `<b>${escapeHtml(i18n.t("audit.scoreBlockers"))}</b><ul>${blockers.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
      ${actions.length ? `<b>${escapeHtml(i18n.t("audit.howImprove"))}</b><ul>${actions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
    </details>
  `;
}

function renderEvidenceCompletion(completion) {
  if (!completion) return "";
  const statusKeys = {
    candidate_data_found: "audit.evidenceCandidateFound",
    partial_data: "audit.evidencePartial",
    missing_data: "audit.evidenceMissing",
    rejected_anomaly: "audit.evidenceRejected",
  };
  return `
    <section class="evidence-completer">
      <header>
        <div><span>DETERMINISTIC DATA RESOLVER</span>
          <h4>${escapeHtml(i18n.t("audit.evidenceCompleter"))}</h4>
          <small>${escapeHtml(i18n.t("audit.evidenceCompleterNotice"))}</small>
        </div>
        <b>${completion.candidate_data_segments}/${completion.segment_count}</b>
      </header>
      <ol>${(completion.segments || []).map((segment) => `
        <li class="is-${escapeHtml(segment.status)}">
          <i>${Number(segment.sequence)}</i>
          <div>
            <b>${escapeHtml(segment.source)} → ${escapeHtml(segment.target)}</b>
            <span>${escapeHtml(i18n.t(statusKeys[segment.status] || segment.status))}</span>
            <div class="evidence-candidates">${(segment.candidates || []).map((candidate) => `
              <span class="${candidate.quality.can_verify_claims ? "is-usable" : "is-blocked"}"
                title="${escapeAttribute((candidate.quality.flags || []).join(", "))}">
                <b>${escapeHtml(candidate.series_id)}</b>
                ${escapeHtml(i18n.t(candidate.quality.can_verify_claims
                  ? "audit.evidenceCanVerify" : "audit.evidenceBlocked"))}
                · ${Math.round(candidate.quality.quality_score * 100)}%
              </span>
            `).join("")}</div>
            ${(segment.missing_data || []).length
              ? `<small>${segment.missing_data.map(escapeHtml).join(" · ")}</small>` : ""}
          </div>
        </li>
      `).join("")}</ol>
    </section>
  `;
}

function renderFactorResearch(research, inquiryId) {
  if (!research) return "";
  const statusKey = {
    insufficient_data: "audit.factorInsufficient",
    exploratory: "audit.factorExploratory",
    out_of_sample_positive: "audit.factorPositive",
    out_of_sample_negative: "audit.factorNegative",
  };
  const nullablePercent = (value) => value == null ? "—" : percent(value);
  const nullableDecimal = (value) => value == null ? "—" : Number(value).toFixed(3);
  const bucketKey = {
    long: "audit.bucketLong",
    short: "audit.bucketShort",
    neutral: "audit.bucketNeutral",
    unavailable: "audit.bucketUnavailable",
  };
  const survivorshipStatusKey = {
    survivor_only: "audit.survivorshipSurvivorOnly",
    partial_historical: "audit.survivorshipPartial",
    point_in_time_audited: "audit.survivorshipAudited",
  };
  return `
    <section class="factor-research">
      <header>
        <div><span>LOCAL FACTOR LAB · ${escapeHtml(research.method_version)}</span>
          <h4>${escapeHtml(i18n.t("audit.factorResearch"))}</h4>
          <small>${escapeHtml(i18n.t("audit.factorNotice"))}</small></div>
        <button type="button" data-factor-mine="${inquiryId}">${escapeHtml(
          i18n.t("audit.factorRemine"),
        )}</button>
      </header>
      <div class="factor-track-badge">LINEAR ✓ · NONLINEAR ${
        Number(research.nonlinear_links?.length || 0)
      }</div>
      <section>
        <h5>${escapeHtml(i18n.t("audit.factorCandidates"))}</h5>
        <div class="factor-grid">${(research.factors || []).map((factor) => `
          <article>
            <span>${escapeHtml(factor.factor_type)} · ${escapeHtml(factor.transformation)}</span>
            <b>${escapeHtml(factor.name)}</b>
            <p>${escapeHtml(factor.hypothesis)}</p>
            <small>${escapeHtml(i18n.t("audit.factorDirection"))}: ${escapeHtml(factor.direction)}
              · ${escapeHtml(i18n.t("audit.factorLag"))}: ${Number(factor.lag_days)}d
              · ${percent(factor.confidence)}${factor.training_p_value == null ? "" : `
              · ${escapeHtml(i18n.t("audit.factorPValue"))}: ${nullableDecimal(factor.training_p_value)}
              · ${escapeHtml(i18n.t("audit.factorQValue"))}: ${nullableDecimal(factor.adjusted_q_value)}`}</small>
          </article>
        `).join("")}</div>
      </section>
      ${(research.nonlinear_links || []).length ? `<section>
        <h5>${escapeHtml(i18n.t("audit.nonlinearLinks"))}</h5>
        <div class="nonlinear-links">${research.nonlinear_links.map((link) => `
          <article>
            <b>${escapeHtml(link.input_factor_ids.join(" × "))}</b>
            <span>${escapeHtml(i18n.t("audit.factorOperator"))}: ${escapeHtml(link.operator)}</span>
            <span>${escapeHtml(i18n.t("audit.relationshipClass"))}: ${escapeHtml(
              link.relationship_class || "exploratory_nonlinear",
            )}</span>
            <p>${escapeHtml(link.condition)}</p>
            <p>→ ${escapeHtml(link.expected_output)}</p>
            ${(link.bridge_variables || []).length ? `
              <div class="bridge-variables">
                <small>${escapeHtml(i18n.t("audit.bridgeVariables"))}</small>
                <b>${link.bridge_variables.map((item) => escapeHtml(item)).join(" → ")}</b>
              </div>` : ""}
            ${(link.linear_segments || []).length ? `
              <div class="linear-subchains">
                <small>${escapeHtml(i18n.t("audit.linearSubchains"))}</small>
                <ol>${link.linear_segments.map((segment) => `
                  <li class="is-${escapeHtml(segment.status)}">
                    <i>${Number(segment.sequence)}</i>
                    <div>
                      <b>${escapeHtml(segment.source)} → ${escapeHtml(segment.target)}</b>
                      <span>${escapeHtml(researchStatusLabel(segment.status))}
                        · ${percent(segment.confidence)}</span>
                      <p>${escapeHtml(segment.mechanism)}</p>
                    </div>
                  </li>`).join("")}</ol>
              </div>` : ""}
          </article>
        `).join("")}</div>
      </section>` : ""}
      <section>
        <h5>${escapeHtml(i18n.t("audit.profitValidation"))}</h5>
        ${(research.profit_validations || []).map((validation) => `
          <article class="factor-validation is-${escapeHtml(validation.status)}">
            <header><div><b>${escapeHtml(validation.target_name)}</b>
              <small>${escapeHtml(i18n.t("audit.factorHorizon"))} · ${Number(validation.forecast_horizon_days)}d</small></div>
              <span>${escapeHtml(i18n.t(statusKey[validation.status] || validation.status))}</span></header>
            <div class="factor-metrics">
              <span>${escapeHtml(i18n.t("audit.factorTrain"))}<b>${Number(validation.train_observations)}</b></span>
              <span>${escapeHtml(i18n.t("audit.factorTest"))}<b>${Number(validation.test_observations)}</b></span>
              <span>${escapeHtml(i18n.t("audit.factorStrategyReturn"))}<b>${nullablePercent(validation.strategy_return)}</b></span>
              <span>${escapeHtml(i18n.t("audit.factorBaselineReturn"))}<b>${nullablePercent(validation.baseline_return)}</b></span>
              <span>${escapeHtml(i18n.t("audit.factorExcessReturn"))}<b>${nullablePercent(validation.excess_return)}</b></span>
              <span>${escapeHtml(i18n.t("audit.factorHitRate"))}<b>${nullablePercent(validation.hit_rate)}</b></span>
              <span>${escapeHtml(i18n.t("audit.factorDrawdown"))}<b>${nullablePercent(validation.max_drawdown)}</b></span>
              <span>${escapeHtml(i18n.t("audit.factorCost"))}<b>${Number(validation.transaction_cost_bps)} bps</b></span>
            </div>
            ${renderFactorReplication(validation.replication)}
            <p>${escapeHtml(validation.signal_rule)}</p>
            <details><summary>${escapeHtml(i18n.t("audit.factorLeakageGuard"))}</summary>
              <p>${escapeHtml(validation.leakage_guard)}</p>
              <ul>${(validation.limitations || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
            </details>
          </article>
        `).join("")}
      </section>
      ${(research.cross_sectional_validations || []).length ? `<section>
        <h5>${escapeHtml(i18n.t("audit.crossSectionValidation"))}</h5>
        ${research.cross_sectional_validations.map((validation) => `
          <article class="factor-validation cross-validation is-${escapeHtml(validation.status)}">
            <header><div><b>${escapeHtml(validation.universe_name)}</b>
              <small>${escapeHtml(i18n.t("audit.crossUniverse"))} · ${Number(validation.asset_count)} / ${Number(validation.expected_asset_count || validation.asset_count)} assets · ${escapeHtml(i18n.t("audit.factorHorizon"))} ${Number(validation.rebalance_horizon_days)}d</small></div>
              <span>${escapeHtml(i18n.t(statusKey[validation.status] || validation.status))}</span></header>
            <div class="factor-metrics cross-metrics">
              <span>${escapeHtml(i18n.t("audit.assetCoverage"))}<b>${Number(validation.asset_count)} / ${Number(validation.expected_asset_count || validation.asset_count)}</b></span>
              <span>${escapeHtml(i18n.t("audit.crossTrainRebalances"))}<b>${Number(validation.train_rebalances)}</b></span>
              <span>${escapeHtml(i18n.t("audit.crossTestRebalances"))}<b>${Number(validation.test_rebalances)}</b></span>
              <span>${escapeHtml(i18n.t("audit.crossTopReturn"))}<b>${nullablePercent(validation.top_bucket_return)}</b></span>
              <span>${escapeHtml(i18n.t("audit.crossBottomReturn"))}<b>${nullablePercent(validation.bottom_bucket_return)}</b></span>
              <span>${escapeHtml(i18n.t("audit.crossLongShort"))}<b>${nullablePercent(validation.long_short_return)}</b></span>
              <span>${escapeHtml(i18n.t("audit.crossEqualReturn"))}<b>${nullablePercent(validation.equal_weight_return)}</b></span>
              <span>${escapeHtml(i18n.t("audit.crossTopExcess"))}<b>${nullablePercent(validation.top_vs_equal_excess)}</b></span>
              <span>${escapeHtml(i18n.t("audit.factorHitRate"))}<b>${nullablePercent(validation.hit_rate)}</b></span>
              <span>${escapeHtml(i18n.t("audit.factorDrawdown"))}<b>${nullablePercent(validation.max_drawdown)}</b></span>
              <span>${escapeHtml(i18n.t("audit.crossSharpe"))}<b>${nullableDecimal(validation.sharpe_like)}</b></span>
              <span>${escapeHtml(i18n.t("audit.factorCost"))}<b>${Number(validation.transaction_cost_bps)} bps</b></span>
            </div>
            <p class="asset-category-mix"><b>${escapeHtml(i18n.t("audit.assetCategoryMix"))}:</b> ${Object.entries(validation.asset_category_counts || {}).map(([category, count]) => `${escapeHtml(category)} ${Number(count)}`).join(" · ") || "—"}</p>
            ${validation.survivorship_audit ? `<section class="survivorship-audit is-${escapeHtml(validation.survivorship_audit.status)}">
              <header><div><b>${escapeHtml(i18n.t("audit.survivorshipTitle"))}</b>
                <small>${escapeHtml(i18n.t(survivorshipStatusKey[validation.survivorship_audit.status] || validation.survivorship_audit.status))}</small></div>
                <span>${validation.survivorship_audit.point_in_time_membership_enforced ? "PIT ON" : "PIT OFF"}</span></header>
              <div class="factor-metrics survivorship-metrics">
                <span>${escapeHtml(i18n.t("audit.pointInTimeRule"))}<b>${validation.survivorship_audit.point_in_time_membership_enforced ? "ON" : "OFF"}</b></span>
                <span>${escapeHtml(i18n.t("audit.historicalAssets"))}<b>${Number(validation.survivorship_audit.historical_assets)}</b></span>
                <span>${escapeHtml(i18n.t("audit.discoveredDelisted"))}<b>${Number(validation.survivorship_audit.discovered_delisted_assets || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.localDelistedPrices"))}<b>${Number(validation.survivorship_audit.local_price_covered_delisted_assets || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.missingDelistedPrices"))}<b>${Number(validation.survivorship_audit.missing_price_delisted_assets || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.priceBackfillQueue"))}<b>${Number(validation.survivorship_audit.price_backfill_queued_assets || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.priceBackfillPending"))}<b>${Number(validation.survivorship_audit.price_backfill_pending_assets || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.priceFactorReady"))}<b>${Number(validation.survivorship_audit.price_backfill_factor_ready_assets || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.pricePartial"))}<b>${Number(validation.survivorship_audit.price_backfill_partial_assets || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.priceUnavailable"))}<b>${Number(validation.survivorship_audit.price_backfill_unavailable_assets || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.priceTickerReuse"))}<b>${Number(validation.survivorship_audit.price_backfill_ticker_reused_assets || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.identityVerified"))}<b>${Number(validation.survivorship_audit.identity_verified_assets || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.identityPending"))}<b>${Number(validation.survivorship_audit.identity_unresolved_assets || 0) + Number(validation.survivorship_audit.identity_ambiguous_assets || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.identityMismatch"))}<b>${Number(validation.survivorship_audit.identity_mismatched_assets || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.identityLifecycleConflict"))}<b>${Number(validation.survivorship_audit.identity_lifecycle_conflict_assets || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.identityCik"))}<b>${Number(validation.survivorship_audit.identity_sec_cik_assets || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.terminalVerified"))}<b>${Number(validation.survivorship_audit.terminal_outcomes_verified || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.terminalPending"))}<b>${Number(validation.survivorship_audit.terminal_outcomes_requiring_evidence || 0) + Number(validation.survivorship_audit.terminal_outcomes_requiring_identity || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.secAuditAcceptedTerminal"))}<b>${Number(validation.survivorship_audit.terminal_evidence_accepted || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.secAuditAcceptedSupporting"))}<b>${Number(validation.survivorship_audit.supporting_evidence_accepted || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.secLifecycleSegmented"))}<b>${Number(validation.survivorship_audit.terminal_evidence_lifecycle_segmented_assets || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.terminalEvidenceSearched"))}<b>${Number(validation.survivorship_audit.terminal_evidence_assets_searched || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.terminalEvidenceCik"))}<b>${Number(validation.survivorship_audit.terminal_evidence_cik_resolved || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.terminalEvidenceMetadata"))}<b>${Number(validation.survivorship_audit.terminal_evidence_metadata_candidates || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.terminalEvidenceValues"))}<b>${Number(validation.survivorship_audit.terminal_evidence_value_candidates || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.terminalEvidenceReview"))}<b>${Number(validation.survivorship_audit.terminal_evidence_review_ready || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.terminalEvidenceContact"))}<b>${Number(validation.survivorship_audit.terminal_evidence_body_contact_required || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.terminalEvidenceLifecycle"))}<b>${Number(validation.survivorship_audit.terminal_evidence_lifecycle_conflicts || 0)}</b></span>
                <span>${escapeHtml(i18n.t("audit.lifecycleCatalogRange"))}<b>${escapeHtml(validation.survivorship_audit.lifecycle_catalog_start && validation.survivorship_audit.lifecycle_catalog_end ? `${validation.survivorship_audit.lifecycle_catalog_start} → ${validation.survivorship_audit.lifecycle_catalog_end}` : "—")}</b></span>
                <span>${escapeHtml(i18n.t("audit.explicitLifecycle"))}<b>${Number(validation.survivorship_audit.assets_with_explicit_lifecycle)}</b></span>
                <span>${escapeHtml(i18n.t("audit.delistingReturnCoverage"))}<b>${Number(validation.survivorship_audit.delisting_returns_covered)} / ${Number(validation.survivorship_audit.historical_assets)}</b></span>
                <span>${escapeHtml(i18n.t("audit.eligibleRange"))}<b>${Number(validation.survivorship_audit.min_eligible_assets)} / ${Number(validation.survivorship_audit.median_eligible_assets).toFixed(1)} / ${Number(validation.survivorship_audit.max_eligible_assets)}</b></span>
              </div>
              <p>${escapeHtml(validation.survivorship_audit.methodology)}</p>
              <details><summary>${escapeHtml(i18n.t("audit.knownGaps"))}</summary><ul>${(validation.survivorship_audit.known_gaps || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></details>
            </section>` : ""}
            <p>${escapeHtml(validation.methodology)}</p>
            ${validation.robustness ? `
              <section class="factor-robustness is-${escapeHtml(validation.robustness.status)}">
                <header><div><b>${escapeHtml(i18n.t("audit.robustValidation"))}</b>
                  <small>${escapeHtml(i18n.t("audit.robustNotice"))}</small></div>
                  <span>${escapeHtml(i18n.t(statusKey[validation.robustness.status] || validation.robustness.status))}</span></header>
                <div class="factor-metrics robust-metrics">
                  <span>${escapeHtml(i18n.t("audit.robustWindow"))}<b>${Number(validation.robustness.training_window_rebalances)}</b></span>
                  <span>${escapeHtml(i18n.t("audit.robustReestimate"))}<b>${Number(validation.robustness.reestimate_every_rebalances)}</b></span>
                  <span>${escapeHtml(i18n.t("audit.robustCandidateTests"))}<b>${Number(validation.robustness.candidate_factor_tests)}</b></span>
                  <span>${escapeHtml(i18n.t("audit.robustPassed"))}<b>${Number(validation.robustness.adjusted_significant_factors)}</b></span>
                  <span>${escapeHtml(i18n.t("audit.robustGroups"))}<b>${Number(validation.robustness.neutralization_group_count)}</b></span>
                  <span>${escapeHtml(i18n.t("audit.crossTestRebalances"))}<b>${Number(validation.robustness.test_rebalances)}</b></span>
                  <span>${escapeHtml(i18n.t("audit.robustRawLongShort"))}<b>${nullablePercent(validation.long_short_return)}</b></span>
                  <span>${escapeHtml(i18n.t("audit.robustLongShort"))}<b>${nullablePercent(validation.robustness.long_short_return)}</b></span>
                  <span>${escapeHtml(i18n.t("audit.crossTopExcess"))}<b>${nullablePercent(validation.robustness.top_vs_equal_excess)}</b></span>
                  <span>${escapeHtml(i18n.t("audit.factorHitRate"))}<b>${nullablePercent(validation.robustness.hit_rate)}</b></span>
                  <span>${escapeHtml(i18n.t("audit.factorDrawdown"))}<b>${nullablePercent(validation.robustness.max_drawdown)}</b></span>
                  <span>${escapeHtml(i18n.t("audit.crossSharpe"))}<b>${nullableDecimal(validation.robustness.sharpe_like)}</b></span>
                </div>
                ${(validation.robustness.contribution_attribution || []).length ? `<details class="factor-attribution" open>
                  <summary>${escapeHtml(i18n.t("audit.attributionTitle"))} · ${escapeHtml(i18n.t(validation.robustness.attribution_reconciled ? "audit.attributionReconciled" : "audit.attributionUnreconciled"))}</summary>
                  <p>${escapeHtml(i18n.t("audit.attributionNotice"))}</p>
                  <div class="attribution-grid">${validation.robustness.contribution_attribution.map((item) => `<article class="is-${item.contribution >= 0 ? "positive" : "negative"}">
                    <span>${escapeHtml(item.dimension)} · ${escapeHtml(item.group)}</span>
                    <b>${escapeHtml(i18n.t("audit.contribution"))} ${nullablePercent(item.contribution)}</b>
                    <small>${escapeHtml(i18n.t("audit.longPeriods"))} ${Number(item.long_periods)} · ${escapeHtml(i18n.t("audit.shortPeriods"))} ${Number(item.short_periods)}</small>
                  </article>`).join("")}</div>
                </details>` : ""}
                <p>${escapeHtml(validation.robustness.methodology)}</p>
                <small>${escapeHtml(validation.robustness.multiple_testing_method)}</small>
                <details><summary>${escapeHtml(i18n.t("audit.factorLeakageGuard"))}</summary>
                  <ul>${(validation.robustness.limitations || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
                </details>
              </section>` : ""}
            ${(validation.incomplete_assets || []).length ? `<details class="pending-assets"><summary>${escapeHtml(i18n.t("audit.pendingAssets"))} · ${Number(validation.incomplete_assets.length)}</summary><p>${validation.incomplete_assets.map(escapeHtml).join(" · ")}</p></details>` : ""}
            <details class="cross-exposure-details">
              <summary>${escapeHtml(i18n.t("audit.crossExposures"))}</summary>
              <div class="cross-exposure-table">${(validation.asset_exposures || []).map((exposure) => `
                <article class="is-${escapeHtml(exposure.latest_bucket)}">
                  <span><b>${escapeHtml(exposure.name)}</b><small>${escapeHtml(exposure.series_id)} · ${escapeHtml(exposure.category)} · ${escapeHtml(exposure.sector || exposure.region || "—")}</small></span>
                  <span class="bucket">${escapeHtml(i18n.t(bucketKey[exposure.latest_bucket] || exposure.latest_bucket))}<small>${escapeHtml(i18n.t("audit.robustBucket"))}: ${escapeHtml(i18n.t(bucketKey[exposure.robust_latest_bucket] || exposure.robust_latest_bucket))}</small></span>
                  <span>${escapeHtml(i18n.t("audit.crossScore"))}<b>${nullableDecimal(exposure.latest_score)}</b><small>${escapeHtml(i18n.t("audit.robustValidation"))}: ${nullableDecimal(exposure.robust_latest_score)}</small></span>
                  <span>${escapeHtml(i18n.t("audit.crossLoading"))}<small>${Object.entries(exposure.factor_loadings || {}).map(([id, value]) => `${escapeHtml(id)} ${nullableDecimal(value)}`).join(" · ") || "—"}</small></span>
                  <span class="neutral-group">${escapeHtml(i18n.t("audit.neutralizationGroup"))}<small>${escapeHtml(exposure.neutralization_group || "—")}</small></span>
                </article>
              `).join("")}</div>
            </details>
            <details><summary>${escapeHtml(i18n.t("audit.factorLeakageGuard"))}</summary>
              <p>${escapeHtml(validation.leakage_guard)}</p>
              <ul>${(validation.limitations || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
            </details>
          </article>
        `).join("")}
      </section>` : ""}
      <footer><span>${escapeHtml(research.research_caveat)}</span>
        <small>${escapeHtml(i18n.t("audit.factorArchive"))}: ${escapeHtml(
          research.archive_path || research.archive_status,
        )}</small></footer>
    </section>
  `;
}

function renderFactorReplication(replication) {
  if (!replication) return "";
  const retentionKey = {
    provisional_retained: "audit.replicationRetained",
    rejected: "audit.replicationRejected",
    insufficient_evidence: "audit.replicationInsufficient",
  }[replication.retention_status] || "audit.replicationInsufficient";
  const interval = replication.pooled_excess_ci_low == null
    || replication.pooled_excess_ci_high == null
    ? "—"
    : `${percent(replication.pooled_excess_ci_low)} → ${percent(replication.pooled_excess_ci_high)}`;
  return `
    <section class="factor-replication is-${escapeAttribute(replication.retention_status)}">
      <header>
        <div><b>${escapeHtml(i18n.t("audit.replicationTitle"))}</b>
          <small>${escapeHtml(i18n.t("audit.replicationNotice"))}</small></div>
        <span>${escapeHtml(i18n.t(retentionKey))}</span>
      </header>
      <div class="factor-metrics replication-metrics">
        <span>${escapeHtml(i18n.t("audit.replicationTrials"))}<b>${Number(replication.valid_trials)} / ${Number(replication.total_trials)}</b></span>
        <span>${escapeHtml(i18n.t("audit.replicationPasses"))}<b>${Number(replication.passed_trials)}</b></span>
        <span>${escapeHtml(i18n.t("audit.replicationMedian"))}<b>${replication.median_excess_return == null ? "—" : percent(replication.median_excess_return)}</b></span>
        <span>${escapeHtml(i18n.t("audit.replicationCI"))}<b>${escapeHtml(interval)}</b></span>
      </div>
      <p>${escapeHtml(replication.retention_reason)}</p>
      <p><b>${escapeHtml(i18n.t("audit.replicationStable"))}:</b> ${(replication.stable_factor_ids || []).map(escapeHtml).join(" × ") || "—"}</p>
      ${(replication.trials || []).length ? `<div class="factor-replication-trials">${replication.trials.map((trial) => `
        <article class="is-${escapeAttribute(trial.status)}">
          <header><b>${escapeHtml(trial.trial_id)}</b><span>${escapeHtml(trial.status)}</span></header>
          <small>${escapeHtml(trial.test_start_date)} → ${escapeHtml(trial.test_end_date)} · n=${Number(trial.test_observations)}</small>
          <p>${(trial.selected_factor_ids || []).map(escapeHtml).join(" × ") || "—"}</p>
          <div><span>EXCESS <b>${trial.excess_return == null ? "—" : percent(trial.excess_return)}</b></span><span>HIT <b>${trial.hit_rate == null ? "—" : percent(trial.hit_rate)}</b></span></div>
        </article>
      `).join("")}</div>` : ""}
    </section>
  `;
}

function renderPaperReport(report) {
  if (!report) return "";
  const listSection = (labelKey, items) => items?.length ? `
    <section><h5>${escapeHtml(i18n.t(labelKey))}</h5>
      <ol>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ol></section>
  ` : "";
  return `
    <section class="paper-report">
      <header><div><span>RESEARCH PAPER</span><h4>${escapeHtml(report.title)}</h4></div>
        <b>${escapeHtml(i18n.t("audit.paperReport"))}</b></header>
      <section><h5>${escapeHtml(i18n.t("audit.paperAbstract"))}</h5>
        <p>${escapeHtml(report.abstract)}</p></section>
      <section><h5>${escapeHtml(i18n.t("audit.paperMethod"))}</h5>
        <p>${escapeHtml(report.methodology)}</p></section>
      <div class="paper-grid">
        ${listSection("audit.paperEvidenceChain", report.evidence_chain)}
        ${listSection("audit.paperFindings", report.findings)}
        ${listSection("audit.paperAlternatives", report.alternative_explanations)}
        ${listSection("audit.paperLimitations", report.limitations)}
      </div>
      <section class="paper-conclusion"><h5>${escapeHtml(i18n.t("audit.paperConclusion"))}</h5>
        <p>${escapeHtml(report.conclusion)}</p></section>
      ${report.evidence_refs?.length
        ? `<footer>${escapeHtml(report.evidence_refs.join(" · "))}</footer>`
        : ""}
    </section>
  `;
}

function renderNewsForecasts(forecasts, validationCases) {
  if (!forecasts?.length) return "";
  const facts = new Map(
    (validationCases || []).flatMap((item) => item.candidate_evidence || [])
      .map((item) => [item.evidence_id, item]),
  );
  const statusKey = {
    unresolved: "audit.forecastUnresolved",
    candidate_evidence_found: "audit.forecastCandidate",
    supported: "audit.forecastSupported",
    partially_supported: "audit.forecastPartial",
    contradicted: "audit.forecastContradicted",
    expired_insufficient_evidence: "audit.forecastExpired",
  };
  const evidenceList = (labelKey, refs) => refs?.length ? `
    <div class="forecast-evidence"><b>${escapeHtml(i18n.t(labelKey))}</b>
      <ul>${refs.map((ref) => {
        const fact = facts.get(ref);
        return `<li>${escapeHtml(fact?.title || fact?.name || ref)}
          <small>${escapeHtml(fact?.source || ref)}</small></li>`;
      }).join("")}</ul></div>` : "";
  return `
    <section class="news-forecasts">
      <header><div><b>${escapeHtml(i18n.t("audit.newsForecasts"))}</b>
        <small>${escapeHtml(i18n.t("audit.forecastNotice"))}</small></div>
        <strong>${forecasts.length}</strong></header>
      ${forecasts.map((forecast) => `
        <article class="is-${escapeHtml(forecast.status)}">
          <header><div><span>${escapeHtml(
            i18n.t(forecast.evaluation_mode === "live_prospective"
              ? "audit.forecastLive" : "audit.forecastBacktest"),
          )} · ${escapeHtml(formatDate(forecast.as_of))}</span>
            <h4>${escapeHtml(forecast.anchor_title)}</h4></div>
            <b>${escapeHtml(i18n.t(statusKey[forecast.status] || forecast.status))}
              · ${percent(forecast.confidence)}</b></header>
          <p>${escapeHtml(forecast.hypothesis)}</p>
          <div class="forecast-block"><b>${escapeHtml(i18n.t("audit.forecastMechanism"))}</b>
            <ol>${forecast.mechanism_chain.map(
              (item) => `<li>${escapeHtml(item)}</li>`,
            ).join("")}</ol></div>
          <div class="forecast-block"><b>${escapeHtml(i18n.t("audit.forecastOutcome"))}</b>
            <p>${escapeHtml(forecast.expected_outcome)}</p>
            <small>${escapeHtml(i18n.t("audit.forecastHorizon"))}: ${Number(forecast.horizon_days)} days</small></div>
          <div class="forecast-block"><b>${escapeHtml(i18n.t("audit.forecastFalsifiers"))}</b>
            <ul>${forecast.falsification_conditions.map(
              (item) => `<li>${escapeHtml(item)}</li>`,
            ).join("")}</ul></div>
          ${forecast.validation_summary
            ? `<p class="forecast-validation">${escapeHtml(forecast.validation_summary)}</p>`
            : ""}
          ${evidenceList("audit.supportingEvidence", forecast.supporting_evidence_refs)}
          ${evidenceList("audit.contradictingEvidence", forecast.contradicting_evidence_refs)}
        </article>
      `).join("")}
    </section>
  `;
}

function renderResearchReview(inquiry) {
  const latest = inquiry.review_signals?.at(-1);
  return `
    <section class="research-review">
      <header><b>${escapeHtml(i18n.t("audit.reportReview"))}</b>
        ${latest ? `<span>${escapeHtml(logicStatusLabel(latest.decision))} · ${
          escapeHtml(formatDate(latest.created_at))
        }</span>` : ""}</header>
      ${latest?.reviewer_note ? `<p>${escapeHtml(latest.reviewer_note)}</p>` : ""}
      <textarea data-report-note="${inquiry.id}" rows="3"
        placeholder="${escapeAttribute(i18n.t("audit.reportReviewNote"))}"></textarea>
      <div>
        ${reportDecisionButton(inquiry.id, "rejected", "audit.reject")}
        ${reportDecisionButton(inquiry.id, "deferred", "audit.defer")}
        ${reportDecisionButton(inquiry.id, "revised_accepted", "audit.reviseAccept")}
        ${reportDecisionButton(inquiry.id, "accepted", "audit.accept")}
      </div>
    </section>
  `;
}

function reportDecisionButton(inquiryId, decision, labelKey) {
  return `<button type="button" data-inquiry-id="${inquiryId}"
    data-report-decision="${decision}">${escapeHtml(i18n.t(labelKey))}</button>`;
}

function renderNewsEvidenceSequences(sequences, citedEvidence) {
  if (!sequences?.length) return "";
  const relationLabel = {
    initial_report: "audit.initialReport",
    follow_up_report: "audit.followUpReport",
    latest_report: "audit.latestReport",
  };
  return `
    <section class="news-evidence-sequences">
      <header><div><b>${escapeHtml(i18n.t("audit.newsSequences"))}</b>
        <small>${escapeHtml(i18n.t("audit.newsSequencesNotice"))}</small></div>
        <strong>${sequences.length}</strong></header>
      ${sequences.map((sequence) => `
        <article>
          <h4>${escapeHtml(sequence.title)}</h4>
          <small>${escapeHtml(formatDate(sequence.starts_at))} →
            ${escapeHtml(formatDate(sequence.ends_at))} · ${Number(sequence.report_count || 0)}</small>
          <ol>${(sequence.entries || []).map((entry) => {
            const cited = citedEvidence.has(entry.evidence_id);
            return `<li class="${cited ? "is-cited" : ""}">
              <i>${Number(entry.sequence || 0)}</i><div>
                <span>${escapeHtml(i18n.t(relationLabel[entry.relation] || entry.relation))}
                  · ${escapeHtml(formatDate(entry.published_at))}</span>
                <a href="${escapeAttribute(entry.source_url)}" target="_blank" rel="noreferrer">
                  ${escapeHtml(entry.title)}</a>
                <small>${escapeHtml(entry.source)} · ${escapeHtml(i18n.t(
                  entry.evidence_status === "source_text" ? "audit.sourceText" : "audit.leadOnly",
                ))}${entry.content_storage === "cold"
                  ? ` · ${escapeHtml(i18n.t("audit.coldEvidence"))}`
                  : ""}${cited ? ` · ${escapeHtml(i18n.t("audit.citedInChain"))}` : ""}</small>
              </div></li>`;
          }).join("")}</ol>
        </article>
      `).join("")}
    </section>
  `;
}

function renderResearchWorkflow(workflow) {
  if (!workflow) return "";
  const episode = workflow.episode_window;
  const stageLabels = {
    local_draft: "audit.localDraft",
    openai_review: "audit.openaiAudit",
    local_revision: "audit.localRevision",
    local_episode_repair: "audit.localEpisodeRepair",
    final_evidence_guard: "audit.finalEvidenceGuard",
    evidence_gap_search: "audit.evidenceGapSearch",
    local_evidence_revision: "audit.localEvidenceRevision",
    openai_confirmation: "audit.openaiConfirmation",
    bridge_evidence_completion: "audit.bridgeEvidenceCompletion",
    factor_mining: "audit.factorMiningStage",
    local_report_audit: "audit.localReportAudit",
  };
  const stageStatusLabels = {
    completed: "audit.stageCompleted",
    skipped: "audit.stageSkipped",
    pending: "audit.stagePending",
    failed: "audit.stageFailed",
  };
  const stageReasonLabels = {
    automatic_review_disabled: "audit.autoReviewDisabled",
  };
  const stages = workflow.stages || [];
  const statusKey = workflow.status === "completed"
    ? "audit.workflowCompleted"
    : workflow.status === "local_report_audited"
      ? "audit.workflowLocalAudited"
    : workflow.status === "needs_human_review"
      ? "audit.workflowNeedsReview"
      : "audit.workflowFailed";
  return `
    <section class="research-workflow is-${escapeHtml(workflow.status || "unknown")}">
      <header>
        <b>${escapeHtml(i18n.t("audit.workflow"))}</b>
        <span>${escapeHtml(i18n.t(statusKey))}</span>
      </header>
      ${episode ? `
        <p><strong>${escapeHtml(i18n.t("audit.episodeWindow"))}</strong>
          ${escapeHtml(episode.start)} → ${escapeHtml(episode.end)}
          · ${Number(episode.duration_days) || "—"} days</p>
        <small>${escapeHtml(i18n.t("audit.historyContext"))}</small>
      ` : ""}
      <ol>${stages.map((stage) => `
        <li class="is-${escapeHtml(stage.status || "unknown")}">
          <i></i>
          <span><b>${escapeHtml(i18n.t(stageLabels[stage.stage] || stage.stage))}</b>
            <small>${escapeHtml([
              i18n.t(stageStatusLabels[stage.status] || stage.status),
              stage.reason ? i18n.t(stageReasonLabels[stage.reason] || stage.reason) : null,
              stage.recommendation,
              stage.error,
              stage.finding_count !== undefined
                ? `${stage.finding_count} findings`
                : null,
              stage.remaining_findings !== undefined
                ? `${stage.remaining_findings} remaining`
                : null,
            ].filter(Boolean).join(" · "))}</small>
          </span>
        </li>
      `).join("")}</ol>
    </section>
  `;
}

function renderResearchRetrieval(reports) {
  if (!reports?.length) return "";
  const added = reports.reduce(
    (total, report) => total + Number(report.added_total || 0),
    0,
  );
  const latest = reports[reports.length - 1];
  return `
    <section class="research-retrieval">
      <header><b>${escapeHtml(i18n.t("audit.retrievalTitle"))}</b>
        <span>${escapeHtml(i18n.t("audit.retrievalPasses"))}: ${reports.length}</span></header>
      <dl>
        <div><dt>${escapeHtml(i18n.t("audit.retrievalAdded"))}</dt><dd>${added}</dd></div>
        <div><dt>${escapeHtml(i18n.t("audit.retrievalAvailable"))}</dt>
          <dd>${Number(latest.available_total || 0).toLocaleString()}</dd></div>
        <div><dt>${escapeHtml(i18n.t("audit.retrievalRefs"))}</dt>
          <dd>${Number(latest.required_ref_hits || 0)} / ${Number(latest.required_ref_count || 0)}</dd></div>
        <div><dt>${escapeHtml(i18n.t("audit.retrievalSeries"))}</dt>
          <dd>${Number(latest.selected_market_series?.length || 0)}</dd></div>
      </dl>
    </section>
  `;
}

function renderResearchEventTable(table, preferred) {
  if (!table?.periods?.length) return "";
  const visiblePeriods = table.periods
    .slice()
    .sort((a, b) => Number(a.year) - Number(b.year));
  const periodStatus = (item) => {
    if (item.eligible) return i18n.t("audit.researchReady");
    if (item.cross_domain_ready) return i18n.t("audit.crossDomainOnly");
    if (item.structured_ready) return i18n.t("audit.structuredOnly");
    return i18n.t("audit.monitorOnly");
  };
  return `
    <section class="research-event-table">
      <header>
        <div><b>${escapeHtml(i18n.t("audit.eventTableTitle"))}</b>
          <small>${escapeHtml(i18n.t("audit.eventTableNotice"))}</small></div>
        <span>${escapeHtml(i18n.t("audit.preferredPeriod"))}: <strong>${escapeHtml(preferred?.year || "—")}</strong></span>
      </header>
      <dl>
        <div><dt>${escapeHtml(i18n.t("audit.structuredStart"))}</dt><dd>${escapeHtml(table.structured_start || "—")}</dd></div>
        <div><dt>${escapeHtml(i18n.t("audit.crossDomainStart"))}</dt><dd>${escapeHtml(table.cross_domain_start || "—")}</dd></div>
        <div><dt>${escapeHtml(i18n.t("audit.reliableStart"))}</dt><dd>${escapeHtml(table.reliable_start || "—")}</dd></div>
        <div><dt>${escapeHtml(i18n.t("audit.reliableEnd"))}</dt><dd>${escapeHtml(table.reliable_end || "—")}</dd></div>
        <div><dt>${escapeHtml(i18n.t("audit.mediaRichStart"))}</dt><dd>${escapeHtml(table.media_rich_start || "—")}</dd></div>
        <div><dt>${escapeHtml(i18n.t("audit.coverageScore"))}</dt><dd>${preferred ? percent(preferred.coverage_score) : "—"}</dd></div>
      </dl>
      <details>
        <summary>${escapeHtml(i18n.t("audit.viewEventTable"))} · ${visiblePeriods.length}</summary>
        <div class="research-event-table-scroll">
          <table>
            <thead><tr><th>Year</th><th>${escapeHtml(i18n.t("audit.coverageScore"))}</th>
              <th>${escapeHtml(i18n.t("audit.evidenceDomains"))}</th><th>${escapeHtml(i18n.t("audit.fullDocuments"))}</th>
              <th>${escapeHtml(i18n.t("audit.newsSources"))}</th>
              <th>Events</th><th>${escapeHtml(i18n.t("audit.marketSeries"))}</th>
              <th>${escapeHtml(i18n.t("audit.companyTickers"))}</th><th>Status</th></tr></thead>
            <tbody>${visiblePeriods.map((item) => `
              <tr class="${Number(item.year) === Number(preferred?.year) ? "is-preferred" : ""}">
                <td>${Number(item.year)}</td><td>${percent(item.coverage_score)}</td>
                <td>${Number(item.evidence_domains || 0)} / 5</td>
                <td>${Number(item.full_documents || 0).toLocaleString()}</td>
                <td>${Number(item.news_sources || 0).toLocaleString()}</td>
                <td>${Number(item.events || 0).toLocaleString()}</td>
                <td>${Number(item.market_series || 0).toLocaleString()}</td>
                <td>${Number(item.company_tickers || 0).toLocaleString()}</td>
                <td>${escapeHtml(periodStatus(item))}</td>
              </tr>`).join("")}</tbody>
          </table>
        </div>
      </details>
    </section>
  `;
}

function renderScope(scope) {
  const groups = [
    ["audit.scopeCompanies", scope?.companies],
    ["audit.scopeSectors", scope?.sectors],
    ["audit.scopeInputs", scope?.supply_chain_inputs],
    ["audit.scopeInfrastructure", scope?.infrastructure],
    ["audit.scopeGeographies", scope?.geographies],
  ].filter(([, values]) => values?.length);
  return groups.map(([key, values]) => `
    <span><b>${escapeHtml(i18n.t(key))}</b>${escapeHtml(values.slice(0, 6).join(" · "))}</span>
  `).join("");
}

function renderEquityDimensions(dimensions) {
  if (!dimensions?.length) return "";
  return `
    <section class="equity-research-block">
      <h4>${escapeHtml(i18n.t("audit.equityDimensions"))}</h4>
      <div class="equity-dimension-grid">
        ${dimensions.map((item) => `
          <article class="equity-dimension signal-${escapeHtml(item.signal)}">
            <header>
              <b>${escapeHtml(i18n.t(`audit.${item.dimension}`))}</b>
              <span>${escapeHtml(equitySignalLabel(item.signal))} · ${percent(item.confidence)}</span>
            </header>
            <p>${escapeHtml(item.assessment)}</p>
            ${item.evidence_refs?.length
              ? `<small>${escapeHtml(item.evidence_refs.join(" · "))}</small>`
              : ""}
            ${item.evidence_gaps?.length ? `
              <details>
                <summary>${escapeHtml(i18n.t("audit.evidenceGaps"))}</summary>
                <ul>${item.evidence_gaps.map(
                  (gap) => `<li>${escapeHtml(gap)}</li>`,
                ).join("")}</ul>
              </details>
            ` : ""}
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function renderCanslimAndCompetitor(evidence) {
  if (!Array.isArray(evidence)) return "";
  const zh = i18n.language === "zh";
  const scorecard = evidence.find(
    (item) => item?.category === "derived_canslim_scorecard",
  );
  const comparison = evidence.find(
    (item) => item?.category === "competitive_operating_comparison",
  );
  const criterionStatus = (value) => ({
    pass: zh ? "通过" : "Pass",
    partial: zh ? "部分" : "Partial",
    fail: zh ? "未通过" : "Fail",
    missing: zh ? "缺数据" : "Missing",
  }[value] || value || "—");
  const isFiniteValue = (value) => value !== null
    && value !== undefined
    && value !== ""
    && Number.isFinite(Number(value));
  const ratio = (value) => isFiniteValue(value)
    ? `${(Number(value) * 100).toFixed(1)}%`
    : "—";
  const price = (value) => isFiniteValue(value)
    ? `$${Number(value).toFixed(2)}`
    : "—";
  const qualityLabel = (flag) => ({
    extreme_revenue_change_review_corporate_actions: zh
      ? "收入变化极端，需核对并购/重述"
      : "Extreme revenue move: review corporate actions",
    gross_margin_unavailable_in_standard_taxonomy: zh
      ? "标准分类缺少毛利"
      : "Gross margin unavailable in standard taxonomy",
    gross_margin_outside_expected_accounting_range: zh
      ? "毛利率超出常见会计区间"
      : "Gross margin outside expected accounting range",
    extreme_net_margin_review_one_offs: zh
      ? "净利率极端，需核对一次性损益"
      : "Extreme net margin: review one-off gains/losses",
    research_intensity_unavailable_in_standard_taxonomy: zh
      ? "标准分类缺少研发费用"
      : "R&D intensity unavailable in standard taxonomy",
  }[flag] || flag);
  const canslimMarkup = scorecard ? `
    <section class="local-canslim-panel">
      <header><div><span>CAN SLIM · ${escapeHtml(scorecard.version || "")}</span><h4>${zh ? "七项成长筛选与交易纪律审计" : "Seven-factor growth screen and discipline audit"}</h4><p>${zh ? "点时 SEC、OHLCV、标普500与13F证据；不采信图片中的941%宣传结果。" : "Point-in-time SEC, OHLCV, S&P 500 and 13F evidence; the advertised 941% result is not accepted as evidence."}</p></div><strong>${Number(scorecard.overall_score || 0).toFixed(0)}<small>/ 100 · ${zh ? "覆盖" : "coverage"} ${Number(scorecard.coverage_score || 0).toFixed(0)}%</small></strong></header>
      <div class="local-canslim-grid">${(scorecard.criteria || []).map((item) => `<article class="${escapeHtml(item.status || "missing")}"><header><b>${escapeHtml(item.code)}</b><span><strong>${escapeHtml(zh ? item.label_zh : item.label_en)}</strong><small>${escapeHtml(criterionStatus(item.status))} · ${Number(item.weight || 0)}%</small></span><em>${Number(item.score || 0).toFixed(0)}</em></header><p>${escapeHtml(item.observed)}</p><footer>${zh ? "门槛" : "Threshold"}: ${escapeHtml(item.threshold)} · ${(item.evidence_refs || []).length} refs</footer></article>`).join("")}</div>
      ${scorecard.discipline?.pivot_proxy ? `<div class="local-canslim-discipline"><span><small>${zh ? "机械突破位代理" : "Mechanical pivot proxy"}</small><b>${price(scorecard.discipline.pivot_proxy)}</b></span><span><small>${zh ? "传统买入区间代理" : "Traditional buy-zone proxy"}</small><b>${price(scorecard.discipline.traditional_buy_zone_proxy?.[0])} — ${price(scorecard.discipline.traditional_buy_zone_proxy?.[1])}</b></span><span><small>${zh ? "历史风控纪律" : "Historical discipline"}</small><b>-7% / -8% · +20% / +25%</b></span></div>` : ""}
      <footer>${zh ? "筛选通过不等于未来盈利、买点或订单指令；仍须样本外验证。" : "A pass is not a profit forecast, entry signal or order instruction; out-of-sample validation remains required."}</footer>
    </section>` : "";
  const comparisonMarkup = comparison ? `
    <section class="local-competitor-panel">
      <header><div><span>${zh ? "同口径竞争比较" : "Like-for-like competitor comparison"}</span><h4>${escapeHtml(comparison.ticker || "")} · ${escapeHtml((comparison.peer_group || []).join(" / "))}</h4><p>${zh ? "10-Q单季度与年度SEC指标分别同口径比较；不混用累计季度，也不把不同产品名称强行混排。" : "Single-quarter 10-Q and annual SEC metrics are aligned separately; YTD contexts and unlike product labels are not mixed."}</p></div><b>${escapeHtml(comparison.as_of || "—")}</b></header>
      <div class="local-competitor-scroll"><table><thead><tr><th>${zh ? "公司" : "Company"}</th><th>10-Q ${zh ? "收入同比" : "revenue YoY"}</th><th>10-Q ${zh ? "毛利率" : "gross margin"}</th><th>10-Q ${zh ? "净利率" : "net margin"}</th><th>${zh ? "财季/可得日" : "Quarter / available"}</th><th>${zh ? "年度收入同比" : "Annual revenue YoY"}</th><th>${zh ? "年度毛利率" : "Annual gross margin"}</th><th>${zh ? "年度净利率" : "Annual net margin"}</th><th>${zh ? "年度研发强度" : "Annual R&D / revenue"}</th><th>${zh ? "财年/可得日" : "Fiscal period / available"}</th></tr></thead><tbody>${(comparison.rows || []).map((item) => `<tr class="${item.ticker === comparison.ticker ? "subject" : ""}"><td><b>${escapeHtml(item.ticker)}</b><small>${escapeHtml(item.company)}</small></td><td>${ratio(item.quarterly?.revenue_yoy)}</td><td>${ratio(item.quarterly?.gross_margin)}</td><td>${ratio(item.quarterly?.net_margin)}</td><td>${escapeHtml(item.quarterly?.period_end || "—")}<small>${escapeHtml(item.quarterly?.available_at || "—")}</small></td><td>${ratio(item.revenue_yoy)}</td><td>${ratio(item.gross_margin)}</td><td>${ratio(item.net_margin)}</td><td>${ratio(item.research_and_development_to_revenue)}</td><td>${escapeHtml(item.period_end || "—")}<small>${escapeHtml(item.available_at || "—")}</small></td></tr>`).join("")}</tbody></table></div>
      ${(comparison.rows || []).some((item) => item.quarterly?.quality_flags?.length) ? `<div class="local-competitor-quality"><b>${zh ? "10-Q异常值复核" : "10-Q anomaly review"}</b>${(comparison.rows || []).filter((item) => item.quarterly?.quality_flags?.length).map((item) => `<p><strong>${escapeHtml(item.ticker)}</strong> · ${escapeHtml(item.quarterly.quality_flags.map(qualityLabel).join("；"))}</p>`).join("")}</div>` : ""}
      ${(comparison.product_disclosures || []).length ? `<details><summary>${zh ? "查看10-Q / 10-K产品经营原文" : "Inspect 10-Q / 10-K product disclosures"} · ${comparison.product_disclosures.length}</summary><div class="local-product-disclosures">${comparison.product_disclosures.map((item) => `<article><header><b>${escapeHtml(item.ticker)} · ${escapeHtml(item.product)}</b><span>${escapeHtml(item.filing_form || "")} · ${escapeHtml(item.period_end || "")}</span></header><strong>${escapeHtml(item.metric_name)}</strong><p>${escapeHtml(item.source_excerpt)}</p>${item.source_url ? `<a href="${escapeHtml(item.source_url)}" target="_blank" rel="noreferrer">SEC source</a>` : ""}</article>`).join("")}</div></details>` : ""}
    </section>` : "";
  return `${canslimMarkup}${comparisonMarkup}`;
}

function renderTradingScenario(evidence) {
  if (!Array.isArray(evidence)) return "";
  const isFiniteValue = (value) => value !== null
    && value !== undefined
    && value !== ""
    && Number.isFinite(Number(value));
  const technical = evidence.find(
    (item) => item?.category === "derived_market_technical",
  );
  if (!technical?.risk_reward) return "";
  const positioning = evidence.find(
    (item) => item?.category === "derived_institutional_positioning",
  );
  const risk = technical.risk_reward;
  const structure = technical.price_structure || technical.close_only_structure || {};
  const points = Array.isArray(technical.chart_points)
    ? technical.chart_points.filter((item) => isFiniteValue(item?.close)).slice(-90)
    : [];
  const hasOhlcv = technical.bar_data_status === "complete_ohlcv"
    && points.every((item) => [item.open, item.high, item.low].every(isFiniteValue));
  const width = 840;
  const height = hasOhlcv ? 330 : 270;
  const padX = 42;
  const padY = 24;
  const priceBottom = hasOhlcv ? 245 : height - padY;
  const values = points.flatMap((item) => [item.low, item.high, item.close, item.sma_20, item.sma_50])
    .concat([risk.stop_reference, risk.target_reference])
    .filter(isFiniteValue)
    .map(Number);
  const rawMin = values.length ? Math.min(...values) : 0;
  const rawMax = values.length ? Math.max(...values) : 1;
  const chartPadding = Math.max((rawMax - rawMin) * 0.1, 1);
  const minY = rawMin - chartPadding;
  const maxY = rawMax + chartPadding;
  const x = (index) => padX + (points.length <= 1 ? 0 : index * (width - padX * 2) / (points.length - 1));
  const y = (value) => priceBottom - (Number(value) - minY) * (priceBottom - padY) / (maxY - minY || 1);
  const line = (field) => points.map((item, index) => (
    isFiniteValue(item[field])
      ? `${x(index).toFixed(1)},${y(item[field]).toFixed(1)}`
      : null
  )).filter(Boolean).join(" ");
  const zh = i18n.language === "zh";
  const price = (value) => isFiniteValue(value)
    ? `$${Number(value).toFixed(2)}`
    : "—";
  const ratio = isFiniteValue(risk.reward_risk_ratio)
    ? `1 : ${Number(risk.reward_risk_ratio).toFixed(2)}`
    : "—";
  const percentValue = (value) => isFiniteValue(value)
    ? `${(Number(value) * 100).toFixed(1)}%`
    : "—";
  const oneWeek = structure.one_week_volatility_band || {};
  const twoWeek = structure.two_week_volatility_band || {};
  const support = structure.nearest_support || {};
  const resistance = structure.nearest_resistance || {};
  const managers = Array.isArray(positioning?.top_manager_proxies)
    ? positioning.top_manager_proxies
    : [];
  const candleWidth = Math.max(2.2, Math.min(6, (width - padX * 2) / Math.max(points.length, 1) * 0.62));
  const maxVolume = Math.max(1, ...points.map((item) => isFiniteValue(item.volume) ? Number(item.volume) : 0));
  const volumeTop = 266;
  const volumeBottom = 316;
  const candleMarkup = hasOhlcv ? points.map((item, index) => {
    const up = Number(item.close) >= Number(item.open);
    const center = x(index);
    const bodyTop = y(Math.max(Number(item.open), Number(item.close)));
    const bodyBottom = y(Math.min(Number(item.open), Number(item.close)));
    const bodyHeight = Math.max(1.4, bodyBottom - bodyTop);
    const volumeHeight = isFiniteValue(item.volume)
      ? Number(item.volume) / maxVolume * (volumeBottom - volumeTop)
      : 0;
    return `<g class="candle ${up ? "up" : "down"}"><line x1="${center}" x2="${center}" y1="${y(item.high)}" y2="${y(item.low)}"/><rect x="${center - candleWidth / 2}" y="${bodyTop}" width="${candleWidth}" height="${bodyHeight}"/><rect class="volume" x="${center - candleWidth / 2}" y="${volumeBottom - volumeHeight}" width="${candleWidth}" height="${volumeHeight}"/></g>`;
  }).join("") : "";
  const chartMarkup = points.length > 1 ? `
    <div class="local-technical-chart">
      <header><div><b>${zh ? (hasOhlcv ? "90日K线、成交量、均线与波段结构" : "90日收盘、均线回踩与顶底结构") : (hasOhlcv ? "90-day candlesticks, volume, averages and swing structure" : "90-day close, moving-average pullbacks and structure")}</b><small>${escapeHtml(points[0].date)} — ${escapeHtml(points[points.length - 1].date)}</small></div><span>${hasOhlcv ? "OHLCV · ATR14" : "Close"} · SMA20 · SMA50</span></header>
      <div class="local-chart-scroll"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="technical price chart">
        ${[0, 0.25, 0.5, 0.75, 1].map((part) => {
          const value = maxY - (maxY - minY) * part;
          const chartY = padY + (priceBottom - padY) * part;
          return `<line x1="${padX}" x2="${width - padX}" y1="${chartY}" y2="${chartY}" class="grid"/><text x="4" y="${chartY + 4}">${value.toFixed(0)}</text>`;
        }).join("")}
        ${candleMarkup}
        ${hasOhlcv ? `<text x="4" y="${volumeTop + 9}">VOL</text><line x1="${padX}" x2="${width - padX}" y1="${volumeBottom}" y2="${volumeBottom}" class="grid"/>` : ""}
        ${isFiniteValue(risk.stop_reference) ? `<line x1="${padX}" x2="${width - padX}" y1="${y(risk.stop_reference)}" y2="${y(risk.stop_reference)}" class="level stop"/>` : ""}
        ${isFiniteValue(risk.target_reference) ? `<line x1="${padX}" x2="${width - padX}" y1="${y(risk.target_reference)}" y2="${y(risk.target_reference)}" class="level target"/>` : ""}
        <polyline points="${line("sma_50")}" class="series sma50"/><polyline points="${line("sma_20")}" class="series sma20"/><polyline points="${line("close")}" class="series close"/>
      </svg></div>
      <p>${zh ? (hasOhlcv ? "K线使用拆股调整日线；支撑阻力来自真实波段高低点，止损缓冲使用ATR14。成交量仅表示参与度，不能据此识别机构。" : "顶/底只按收盘高低点、均线和历史波动识别；缺少完整OHLC与成交量时，不宣称完整K线形态。") : (hasOhlcv ? "Candlesticks use split-adjusted daily bars. Swing highs/lows set structure and ATR14 sets the stop buffer; volume does not identify institutions." : "Top/bottom structure is limited to closes, averages and historical volatility; no full candlestick claim is made without OHLC and volume.")}</p>
    </div>` : "";
  return `
    <section class="local-trading-scenario">
      <header><div><span>POINT-IN-TIME · ${escapeHtml(technical.ticker || "")}</span><h4>${zh ? "当前价盈亏比、止盈止损参考与技术图" : "Current-price risk/reward, scenario levels and chart"}</h4><p>${zh ? `截止 ${escapeHtml(technical.observed_on || "—")}；研究情景，不是交易指令。` : `Cutoff ${escapeHtml(technical.observed_on || "—")}; research scenario, not an order instruction.`}</p></div><strong>${ratio}<small>${zh ? "风险 : 潜在收益" : "risk : potential reward"}</small></strong></header>
      <div class="local-scenario-metrics">
        <span><small>${zh ? "当前价" : "Entry reference"}</small><b>${price(risk.entry_reference)}</b></span>
        <span class="risk"><small>${zh ? "失效/止损参考" : "Invalidation / stop"}</small><b>${price(risk.stop_reference)}</b><em>-${percentValue(risk.downside_fraction)}</em></span>
        <span class="reward"><small>${zh ? "目标/止盈参考" : "Target / take-profit"}</small><b>${price(risk.target_reference)}</b><em>+${percentValue(risk.upside_fraction)}</em></span>
        <span><small>${zh ? "一周历史波动区间" : "1-week historical-vol band"}</small><b>${price(oneWeek.lower)} — ${price(oneWeek.upper)}</b></span>
        <span><small>${zh ? "两周历史波动区间" : "2-week historical-vol band"}</small><b>${price(twoWeek.lower)} — ${price(twoWeek.upper)}</b></span>
        <span><small>${zh ? "最近支撑 / 阻力" : "Nearest support / resistance"}</small><b>${price(support.value)} / ${price(resistance.value)}</b><em>${escapeHtml(support.label || "—")} · ${escapeHtml(resistance.label || "—")}</em></span>
        <span><small>ATR14</small><b>${price(technical.atr_14)}</b><em>${zh ? "真实波动区间均值" : "average true range"}</em></span>
        <span><small>${zh ? "最新量 / 20日均量" : "Latest / 20-day volume"}</small><b>${isFiniteValue(technical.volume_ratio_20) ? `${Number(technical.volume_ratio_20).toFixed(2)}×` : "—"}</b><em>${escapeHtml(technical.volume_confirmation?.status || "—")}</em></span>
      </div>
      ${chartMarkup}
      <div class="local-institutional-cost"><div><b>${zh ? "机构真实平均成本：不可得" : "Actual institutional average cost: unavailable"}</b><p>${zh ? "SEC 13F不披露买入价或成本基础。期末申报价值÷股数只能作为有日期的估值代理，不能当成机构买入均价。" : "SEC Form 13F does not disclose purchase price or cost basis. Quarter-end reported value per share is only a dated valuation proxy."}</p></div><span><small>${zh ? "13F期末价值代理" : "13F quarter-end value proxy"}</small><strong>${price(positioning?.quarter_end_value_per_share_proxy)}</strong><em>${escapeHtml(positioning?.report_period || "—")}</em></span></div>
      ${managers.length ? `<div class="local-manager-grid">${managers.slice(0, 5).map((item) => `<span><b>${escapeHtml(item.manager_name || "—")}</b><strong>${price(item.quarter_end_value_per_share_proxy)}</strong><small>${zh ? "期末价值代理，不是成本" : "value proxy, not cost"}</small></span>`).join("")}</div>` : ""}
      <footer>${zh ? (hasOhlcv ? "结构位来自拆股调整OHLCV、真实波段、ATR14、SMA20/50/200和63日历史波动；不保证可成交，也不构成个性化投资建议。" : "结构位来自拆股调整收盘价、SMA20/50/200和63日历史波动；不保证可成交，也不构成个性化投资建议。") : (hasOhlcv ? "Levels use split-adjusted OHLCV, swing structure, ATR14, SMA20/50/200 and 63-day historical volatility; they are not guaranteed executable prices or personalized advice." : "Levels use adjusted closes, SMA20/50/200 and 63-day historical volatility; they are not guaranteed executable prices or personalized advice.")}</footer>
    </section>`;
}

function renderEquityDecisionFramework(framework) {
  if (!framework) return "";
  const groups = [
    ["audit.valuationScenarios", framework.valuation_scenarios],
    ["audit.entryConditions", framework.entry_conditions],
    ["audit.invalidationConditions", framework.invalidation_conditions],
    ["audit.monitoringIndicators", framework.monitoring_indicators],
  ].filter(([, values]) => values?.length);
  return `
    <section class="equity-decision-framework">
      <header>
        <h4>${escapeHtml(i18n.t("audit.decisionFramework"))}</h4>
        <span>${escapeHtml(framework.timing_assessment)}</span>
      </header>
      <p>${escapeHtml(framework.current_price_context)}</p>
      <div class="decision-groups">
        ${groups.map(([label, values]) => `
          <div>
            <b>${escapeHtml(i18n.t(label))}</b>
            <ul>${values.map((value) => `<li>${escapeHtml(value)}</li>`).join("")}</ul>
          </div>
        `).join("")}
      </div>
      <small>${escapeHtml(i18n.t("audit.researchDisclaimer"))}</small>
    </section>
  `;
}

function equitySignalLabel(signal) {
  return i18n.t({
    bullish: "audit.signalBullish",
    bearish: "audit.signalBearish",
    mixed: "audit.signalMixed",
    unknown: "audit.signalUnknown",
  }[signal] || "audit.signalUnknown");
}

function renderSecondOpinion(review) {
  if (!review) return "";
  return `
    <section class="second-opinion">
      <header>
        <b>${escapeHtml(i18n.t("audit.secondOpinion"))}</b>
        <span>${escapeHtml(review.model)} · ${
          escapeHtml(logicStatusLabel(review.recommendation))
        }</span>
      </header>
      <p>${escapeHtml(review.overall_assessment)}</p>
      <strong>${escapeHtml(i18n.t("audit.revisedSummary"))}</strong>
      <p>${escapeHtml(review.revised_summary)}</p>
      ${review.findings?.length ? `<ul>${review.findings.map((item) => `
        <li>${escapeHtml(item.finding)}
          <small>${escapeHtml(item.suggested_revision)}</small>
        </li>`).join("")}</ul>` : ""}
    </section>
  `;
}

function renderEvidence() {
  const relations = state.eventChain?.relations || [];
  const fixedCount = relations.filter((item) => item.pinned).length;
  elements.fixedChainCount.textContent = `${fixedCount} ${i18n.t("audit.fixedCount")}`;
  if (!relations.length) {
    elements.evidenceList.innerHTML =
      `<div class="empty-card">${escapeHtml(i18n.t("audit.noRelations"))}</div>`;
    return;
  }
  elements.evidenceList.innerHTML = [...relations]
    .filter((relation) => relation.status !== "rejected")
    .sort((left, right) => Number(right.pinned) - Number(left.pinned)
      || right.confidence - left.confidence)
    .map((relation) => `
      <article class="evidence-card ${relation.pinned ? "is-fixed" : ""}">
        <p>${escapeHtml(relation.source_title)}</p>
        <span>↓ ${escapeHtml(i18n.t(
          relation.relation_type === "reported_follow_up"
            ? "audit.responseCue"
            : "audit.temporalSuggestion",
        ))}</span>
        <p>${escapeHtml(relation.target_title)}</p>
        <footer>
          <b>${percent(relation.confidence)}</b>
          <small>${escapeHtml(i18n.t("audit.evidenceDocuments"))}: ${
            relation.evidence_document_ids?.length || 0
          }</small>
          <button type="button" data-pin-relation="${relation.id}" ${
            relation.pinned ? "disabled" : ""
          }>${escapeHtml(i18n.t(
            relation.pinned ? "audit.fixedEvidence" : "audit.pinEvidence",
          ))}</button>
        </footer>
      </article>
    `).join("");
}

async function pinEvidenceRelation(relationId) {
  const relation = state.eventChain?.relations.find((item) => item.id === relationId);
  if (!relation || relation.pinned) return;
  try {
    await apiMutation(`/event-chains/relations/${relationId}`, {
      method: "PATCH",
      body: JSON.stringify({
        status: "accepted",
        pinned: true,
        review_note: localized(
          "由 AI 核验工作台人工接受并固定",
          "Human accepted and fixed from the AI audit workspace",
        ),
      }),
    });
    relation.status = "accepted";
    relation.pinned = true;
    renderMetrics();
    renderEvidence();
  } catch (error) {
    showNotice(`${i18n.t("audit.requestFailed")}: ${error.message}`, true);
  }
}

function renderLogic() {
  const hypotheses = state.logicChain?.hypotheses || [];
  elements.logicTrainingCount.textContent = `${
    state.aiStatus?.training.review_signal_count
      ?? state.logicChain?.training_signal_count
      ?? 0
  } ${i18n.t("audit.trainingCount")}`;
  if (!hypotheses.length) {
    elements.logicChainList.innerHTML =
      `<div class="empty-card">${escapeHtml(i18n.t("audit.noLogic"))}</div>`;
    return;
  }
  elements.logicChainList.innerHTML = [...hypotheses]
    .sort((left, right) => statusRank(left.status) - statusRank(right.status)
      || right.composite_score - left.composite_score)
    .map((hypothesis) => `
      <article class="logic-card is-${escapeHtml(hypothesis.status)}">
        <header class="logic-card-header">
          <div>
            <small>${escapeHtml(logicStatusLabel(hypothesis.status))}</small>
            <h4>${escapeHtml(hypothesis.title)}</h4>
          </div>
          <strong>${percent(hypothesis.composite_score)}</strong>
        </header>
        <div class="logic-scores">
          ${scoreChip("audit.compositeScore", hypothesis.composite_score)}
          ${scoreChip("audit.associationScore", hypothesis.association_score)}
          ${scoreChip("audit.evidenceCoverage", hypothesis.evidence_coverage_score)}
        </div>
        <ol class="logic-steps">
          ${hypothesis.steps.map((step) => `
            <li class="${escapeHtml(step.step_type)}">
              <b>${escapeHtml(logicStepLabel(step.step_type))}</b>
              <span>${escapeHtml(step.text)}</span>
              <small>${percent(step.confidence)} · ${percent(step.relevance)}
                ${escapeHtml(i18n.t("audit.relevance"))}${
                  step.evidence_refs?.length
                    ? ` · ${escapeHtml(step.evidence_refs.join(" · "))}`
                    : ""
                }</small>
            </li>
          `).join("")}
        </ol>
        ${hypothesis.counterevidence?.length ? `
          <section class="counterevidence">
            <b>${escapeHtml(i18n.t("audit.counterevidence"))}</b>
            <ul>${hypothesis.counterevidence.map(
              (item) => `<li>${escapeHtml(item)}</li>`,
            ).join("")}</ul>
          </section>
        ` : ""}
        ${renderCausalValidation(
          hypothesis.causal_validation,
          hypothesis.steps,
          hypothesis.historical_cases,
        )}
        ${renderSecondOpinion(hypothesis.chatgpt_review)}
        <p class="logic-rationale">${escapeHtml(hypothesis.rationale)}</p>
        <textarea data-logic-correction="${hypothesis.id}" rows="2"
          placeholder="${escapeAttribute(i18n.t("audit.correctionPlaceholder"))}">${
            escapeHtml(hypothesis.suggested_correction || "")
          }</textarea>
        <footer class="logic-review-actions">
          <button type="button" data-logic-chatgpt="${hypothesis.id}" ${
            !state.openaiConfigured || hypothesis.chatgpt_review ? "disabled" : ""
          }>${escapeHtml(
            hypothesis.chatgpt_review
              ? i18n.t("audit.chatgptReviewed")
              : state.openaiConfigured
                ? i18n.t("audit.chatgptReview")
                : i18n.t("audit.chatgptUnavailable"),
          )}</button>
          ${decisionButton(hypothesis.id, "rejected", "audit.reject")}
          ${decisionButton(hypothesis.id, "deferred", "audit.defer")}
          ${decisionButton(hypothesis.id, "revised_accepted", "audit.reviseAccept")}
          ${decisionButton(hypothesis.id, "accepted", "audit.accept")}
        </footer>
      </article>
    `).join("");
}

function renderCausalValidation(validation, steps, historicalCases) {
  if (!validation) return "";
  const summary = localized(validation.summary_zh, validation.summary_en);
  const recommendation = localized(
    validation.recommendation_zh,
    validation.recommendation_en,
  );
  const citedFacts = (validation.evidence_facts || []).filter(
    (fact) => fact.used_by_checks?.length,
  );
  return `
    <section class="causal-validation is-${escapeHtml(validation.conclusion)}">
      <header>
        <div>
          <b>${escapeHtml(i18n.t("audit.causalValidator"))}</b>
          <span>${escapeHtml(causalConclusionLabel(validation.conclusion))}</span>
        </div>
        <strong>${percent(validation.recalculated_confidence)}</strong>
      </header>
      <div class="causal-meta">
        <span>${escapeHtml(i18n.t("audit.recalculatedConfidence"))}</span>
        <span>${escapeHtml(i18n.t("audit.validationWindow"))}: ${
          validation.time_window_hours
        } ${escapeHtml(i18n.t("audit.hours"))}</span>
      </div>
      ${renderConfidenceBreakdown(validation.confidence_breakdown)}
      ${renderCausalFlow(steps, validation.checks)}
      ${validation.evidence_sources?.length ? `
        <section class="validation-sources">
          <h5>${escapeHtml(i18n.t("audit.validationSources"))}</h5>
          <div>${validation.evidence_sources.map((source) => `
            <a href="${escapeAttribute(source.source_url)}" target="_blank"
              rel="noreferrer" class="is-${escapeHtml(source.status)}">
              <b>${escapeHtml(source.name)}</b>
              <span>${escapeHtml(source.status)} · ${source.observation_count}
                ${escapeHtml(i18n.t("audit.observations"))}</span>
            </a>
          `).join("")}</div>
        </section>
      ` : ""}
      ${validation.evidence_facts?.length ? `
        <details class="evidence-facts" open>
          <summary>${escapeHtml(i18n.t("audit.citedEvidence"))} · ${
            citedFacts.length
          } / ${validation.evidence_facts.length}</summary>
          <ul>${validation.evidence_facts.map((fact) => `
            <li class="${fact.used_by_checks?.length ? "is-cited" : "is-context"}">
              <a href="${escapeAttribute(fact.source_url)}" target="_blank"
                rel="noreferrer">${escapeHtml(fact.label)}</a>
              <b>${escapeHtml(fact.value_text)}</b>
              <small>${escapeHtml(
                [fact.observed_at, fact.source].filter(Boolean).join(" · "),
              )}</small>
              <em>${escapeHtml(
                fact.used_by_checks?.length
                  ? `${i18n.t("audit.usedBy")}: ${fact.used_by_checks.map(
                    causalCheckLabel,
                  ).join(" · ")}`
                  : i18n.t("audit.contextOnly"),
              )}</em>
            </li>
          `).join("")}</ul>
        </details>
      ` : ""}
      <h5>${escapeHtml(i18n.t("audit.reasoningTrace"))}</h5>
      <ol class="reasoning-trace">
        ${(validation.reasoning_trace?.length
          ? validation.reasoning_trace
          : validation.checks).map((check, index) => `
          <li class="is-${escapeHtml(check.status)}">
            <i>${check.sequence || index + 1}</i>
            <div>
              <b>${escapeHtml(causalCheckLabel(check.check_key))}</b>
              <span>${escapeHtml(causalCheckStatusLabel(check.status))}
                · ${percent(check.score)}</span>
              <p>${escapeHtml(localized(check.explanation_zh, check.explanation_en))}</p>
              ${check.evidence_refs?.length
                ? `<small>${escapeHtml(check.evidence_refs.join(" · "))}</small>`
                : ""}
            </div>
          </li>
        `).join("")}
      </ol>
      <section class="validation-summary">
        <b>${escapeHtml(i18n.t("audit.validationSummary"))}</b>
        <p>${escapeHtml(summary)}</p>
      </section>
      <details class="missing-evidence" ${
        validation.missing_evidence?.length ? "open" : ""
      }>
        <summary>${escapeHtml(i18n.t("audit.missingEvidence"))} · ${
          validation.missing_evidence?.length || 0
        }</summary>
        ${validation.missing_evidence?.length
          ? `<ul>${validation.missing_evidence.map(
            (item) => `<li>${escapeHtml(item)}</li>`,
          ).join("")}</ul>`
          : `<p>${escapeHtml(i18n.t("audit.noMissing"))}</p>`}
      </details>
      ${validation.next_data_suggestions?.length ? `
        <section class="next-evidence">
          <b>${escapeHtml(i18n.t("audit.nextEvidence"))}</b>
          <ul>${validation.next_data_suggestions.map((item) => `
            <li class="is-${escapeHtml(item.priority)}">
              <span>${escapeHtml(localized(item.label_zh, item.label_en))}</span>
              <small>${escapeHtml(localized(item.reason_zh, item.reason_en))}</small>
            </li>
          `).join("")}</ul>
        </section>
      ` : ""}
      ${historicalCases?.length ? `
        <details class="historical-cases">
          <summary>${escapeHtml(i18n.t("audit.historicalCases"))} · ${
            historicalCases.length
          }</summary>
          <ul>${historicalCases.map((item) => `
            <li>
              <b>${escapeHtml(item.title)}</b>
              <span>${percent(item.similarity_score)}</span>
              <p>${escapeHtml(localized(item.summary_zh, item.summary_en))}</p>
            </li>
          `).join("")}</ul>
        </details>
      ` : ""}
      <section class="reviewer-recommendation is-${escapeHtml(
        validation.reviewer_recommendation,
      )}">
        <b>${escapeHtml(i18n.t("audit.reviewerRecommendation"))}</b>
        <span>${escapeHtml(logicStatusLabel(validation.reviewer_recommendation))}</span>
        <p>${escapeHtml(recommendation)}</p>
      </section>
    </section>
  `;
}

function renderConfidenceBreakdown(breakdown) {
  if (!breakdown) return "";
  return `
    <details class="confidence-breakdown" open>
      <summary>${escapeHtml(i18n.t("audit.confidenceBreakdown"))}</summary>
      <div class="confidence-limits">
        ${scoreChip("audit.originalConfidence", breakdown.original_confidence)}
        ${scoreChip("audit.weightedGateScore", breakdown.weighted_gate_score)}
        ${scoreChip("audit.conclusionCap", breakdown.conclusion_cap)}
      </div>
      <div class="confidence-components">
        ${breakdown.components.map((component) => `
          <div class="is-${escapeHtml(component.status)}">
            <span>${escapeHtml(causalCheckLabel(component.check_key))}</span>
            <i><b style="width:${Math.round(component.score * 100)}%"></b></i>
            <small>${percent(component.weight)} ${escapeHtml(i18n.t("audit.weight"))}
              · +${percent(component.contribution)}</small>
          </div>
        `).join("")}
      </div>
    </details>
  `;
}

function renderCausalFlow(steps, checks) {
  if (!steps?.length) return "";
  const checkMap = new Map(checks.map((check) => [check.check_key, check]));
  return `
    <section class="causal-flow-wrap">
      <h5>${escapeHtml(i18n.t("audit.causalFlow"))}</h5>
      <ol class="causal-flow">
        ${steps.map((step, index) => {
          const check = checkMap.get(stepCheckKey(step, index, steps.length));
          return `<li class="is-${escapeHtml(check?.status || "missing_evidence")}">
            <small>${escapeHtml(logicStepLabel(step.step_type))}</small>
            <span>${escapeHtml(step.text)}</span>
            <b>${escapeHtml(causalCheckStatusLabel(
              check?.status || "missing_evidence",
            ))}</b>
          </li>`;
        }).join("")}
      </ol>
    </section>
  `;
}

async function generateLogicChains() {
  const jobId = state.mapData?.latest_cluster_job_id;
  if (!jobId) return;
  setLogicBusy(true, "audit.generating");
  try {
    state.logicChain = await apiMutation(`/logic-chains/${jobId}/generate`, {
      method: "POST",
    });
    elements.logicStatus.textContent = i18n.t("audit.logicUpdated");
    renderMetrics();
    renderLogic();
    void refreshAIStatus();
  } catch (error) {
    elements.logicStatus.textContent =
      `${i18n.t("audit.requestFailed")}: ${error.message}`;
  } finally {
    setLogicBusy(false);
  }
}

async function validateLogicChains() {
  const jobId = state.mapData?.latest_cluster_job_id;
  if (!jobId) return;
  setLogicBusy(true, "audit.validating");
  try {
    state.logicChain = await apiMutation(`/logic-chains/${jobId}/validate`, {
      method: "POST",
    });
    elements.logicStatus.textContent = i18n.t("audit.logicUpdated");
    renderMetrics();
    renderLogic();
    void refreshAIStatus();
  } catch (error) {
    elements.logicStatus.textContent =
      `${i18n.t("audit.requestFailed")}: ${error.message}`;
  } finally {
    setLogicBusy(false);
  }
}

function setLogicBusy(busy, labelKey = null) {
  elements.generateLogic.disabled = busy;
  elements.validateLogic.disabled = busy;
  if (busy && labelKey) elements.logicStatus.textContent = i18n.t(labelKey);
}

async function requestLogicReview(hypothesisId) {
  const button = elements.logicChainList.querySelector(
    `[data-logic-chatgpt="${hypothesisId}"]`,
  );
  if (button) button.disabled = true;
  elements.logicStatus.textContent = i18n.t("audit.chatgptRunning");
  try {
    const review = await apiMutation(
      `/logic-chains/hypotheses/${hypothesisId}/chatgpt-review`,
      { method: "POST" },
    );
    const hypothesis = state.logicChain?.hypotheses.find(
      (item) => item.id === hypothesisId,
    );
    if (hypothesis) hypothesis.chatgpt_review = review;
    elements.logicStatus.textContent = i18n.t("audit.chatgptComplete");
    renderLogic();
  } catch (error) {
    elements.logicStatus.textContent =
      `${i18n.t("audit.requestFailed")}: ${error.message}`;
    if (button) button.disabled = false;
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
        reviewer_note: localized(
          "通过 AI 核验工作台作出人工判断",
          "Human decision made in the AI audit workspace",
        ),
        suggested_correction: correction,
      }),
    });
    state.logicChain = await api(
      `/logic-chains/${state.logicChain.cluster_job_id}`,
    );
    renderMetrics();
    renderLogic();
    void refreshAIStatus();
  } catch (error) {
    elements.logicStatus.textContent =
      `${i18n.t("audit.requestFailed")}: ${error.message}`;
  }
}

function renderIntegrations() {
  elements.integrationList.innerHTML = state.integrations.map((item) => `
    <a href="${escapeAttribute(item.application_url)}" target="_blank"
      rel="noreferrer">
      <b>${escapeHtml(item.name)}</b>
      <span class="${item.configured ? "ready" : "required"}">${
        escapeHtml(i18n.t(item.configured ? "audit.configured" : "audit.required"))
      }</span>
    </a>
  `).join("");
}

function renderCoverage() {
  if (!state.coverage) return;
  elements.coverageWindow.textContent =
    `${state.coverage.target_starts_at} → ${state.coverage.target_ends_at}`;
  elements.coverageList.innerHTML = state.coverage.datasets
    .map(coverageRow)
    .join("");
  elements.sourceCoverageList.innerHTML = state.coverage.sources
    .map(coverageRow)
    .join("");
}

function renderDataAudit() {
  if (!state.dataAudit || !elements.dataAuditMetrics) return;
  const report = state.dataAudit;
  const backlog = report.fulltext_backlog || {};
  const metrics = [
    ["audit.auditSeries", Number(report.market_series_count).toLocaleString()],
    ["audit.auditObservations", Number(report.market_observation_count).toLocaleString()],
    ["audit.auditChinaLeaders", Number(report.china_leader_count).toLocaleString()],
    ["audit.auditUsEquities", Number(report.us_equity_count).toLocaleString()],
    ["audit.auditSuspicious", Number(report.suspicious_series_count).toLocaleString()],
    ["audit.auditUnusable", Number(report.unusable_series_count).toLocaleString()],
    ["audit.auditCompanyPriceCoverage", `${Math.round(report.company_price_coverage * 100)}%`],
    ["audit.auditHeadlineBacklog", Number(backlog.headline_only_count || 0).toLocaleString()],
    ["audit.auditNeverAttempted", Number(backlog.never_attempted_count || 0).toLocaleString()],
    ["audit.auditRetryableNow", Number(backlog.retryable_now_count || 0).toLocaleString()],
    ["audit.auditPermanentBlocked", Number(backlog.permanent_block_count || 0).toLocaleString()],
  ];
  elements.dataAuditMetrics.innerHTML = metrics.map(([label, value]) => `
    <span><small>${escapeHtml(i18n.t(label))}</small><b>${escapeHtml(value)}</b></span>
  `).join("");
  const completion = report.latest_evidence_completion;
  elements.dataAuditEvidence.innerHTML = completion ? `
    <b>${escapeHtml(i18n.t("audit.auditEvidenceCompletion"))}</b>
    <span>${escapeHtml(i18n.t("audit.auditCandidateSegments"))}: ${completion.candidate_data_segments}/${completion.segment_count}</span>
    <span>${escapeHtml(i18n.t("audit.auditRejectedSegments"))}: ${completion.rejected_anomaly_segments}</span>
    <span>${escapeHtml(i18n.t("audit.auditMissingSegments"))}: ${completion.missing_segments}</span>
  ` : `<span>${escapeHtml(i18n.t("audit.auditNoCompletion"))}</span>`;
  elements.dataAuditFindings.innerHTML = [
    ...(report.report_findings || []),
    ...(report.provider_findings || []),
  ].map((finding) => `<p>${escapeHtml(finding)}</p>`).join("");
  if (elements.dataAuditEquities) {
    elements.dataAuditEquities.innerHTML = [
      ["audit.chinaSectorLeaders", report.china_sector_leaders || {}],
      ["audit.usSectorUniverse", report.us_sector_equities || {}],
    ].map(([title, sectors]) => `
      <details>
        <summary>${escapeHtml(i18n.t(title))} · ${Object.values(sectors)
          .reduce((total, items) => total + items.length, 0)}</summary>
        <div>${Object.entries(sectors).map(([sector, items]) => `
          <section><b>${escapeHtml(sector)}</b><p>${items.map((item) =>
            `<span title="${escapeAttribute(item.ranking_metric)}">${escapeHtml(item.symbol)} · ${escapeHtml(item.name)}${item.ranking_value === null || item.ranking_value === undefined ? "" : ` · ${Number(item.ranking_value).toFixed(1)}`} · ${Math.round(item.quality_score * 100)}%</span>`
          ).join("")}</p></section>
        `).join("")}</div>
      </details>
    `).join("");
  }
  elements.dataAuditAbnormalList.innerHTML = (report.abnormal_series || []).slice(0, 24)
    .map((item) => `
      <article>
        <span><b>${escapeHtml(item.series_id)}</b><small>${escapeHtml(item.name)}</small></span>
        <span>${Math.round(item.quality_score * 100)}% · ${escapeHtml((item.flags || []).join(", "))}</span>
      </article>
    `).join("");
  elements.dataAuditMetrics.dataset.status = report.status;
}

function coverageRow(item) {
  const ratio = item.completeness_ratio;
  const percentValue = ratio === null || ratio === undefined
    ? 0
    : Math.max(0, Math.min(100, Math.round(ratio * 100)));
  const timestampValue = item.timestamp_ratio === null
    || item.timestamp_ratio === undefined
    ? "—"
    : `${Math.round(item.timestamp_ratio * 100)}%`;
  const contentValue = item.content_ratio === null
    || item.content_ratio === undefined
    ? "—"
    : `${Math.round(item.content_ratio * 100)}%`;
  const range = item.starts_at && item.ends_at
    ? `${item.starts_at} → ${item.ends_at}`
    : i18n.t("audit.coverageUnknown");
  const statusLabels = {
    complete: "audit.coverageComplete",
    partial: "audit.coveragePartial",
    stale: "audit.coverageStale",
    missing: "audit.coverageMissing",
  };
  return `
    <article class="coverage-row is-${escapeHtml(item.status)}">
      <div class="coverage-row-heading">
        <span>
          <b>${escapeHtml(item.name)}</b>
          <small>${escapeHtml(item.provider)} · ${escapeHtml(item.category)}</small>
        </span>
        <strong>${escapeHtml(i18n.t(statusLabels[item.status] || item.status))}</strong>
      </div>
      <div class="coverage-range">${escapeHtml(range)}</div>
      <div class="coverage-progress" aria-label="${percentValue}%">
        <i style="width:${percentValue}%"></i>
      </div>
      <div class="coverage-meta">
        <span>${Number(item.record_count).toLocaleString()} ${escapeHtml(i18n.t("audit.coverageRecords"))}</span>
        <span>${escapeHtml(i18n.t("audit.coverageTimestamp"))}: ${escapeHtml(timestampValue)}</span>
        <span>${escapeHtml(i18n.t("audit.coverageContent"))}: ${escapeHtml(contentValue)}</span>
        ${item.headline_only_count === null || item.headline_only_count === undefined
          ? ""
          : `<span>${escapeHtml(i18n.t("audit.coverageHeadlineOnly"))}: ${Number(item.headline_only_count).toLocaleString()}</span>`}
        <span>${percentValue}%</span>
      </div>
      ${item.notes?.length ? `
        <p>${item.notes.map(escapeHtml).join(" · ")}</p>
      ` : ""}
    </article>
  `;
}

function renderCycle() {
  if (!state.cycle) return;
  const regimeLabels = {
    expansion: "audit.cycleExpansion",
    late_cycle: "audit.cycleLate",
    slowdown: "audit.cycleSlowdown",
    contraction: "audit.cycleContraction",
    recovery: "audit.cycleRecovery",
    insufficient_data: "audit.cycleInsufficient",
  };
  const components = state.cycle.components
    .filter((item) => item.value !== null && item.value !== undefined)
    .map((item) => `
      <span title="${escapeAttribute(item.label)}">
        <small>${escapeHtml(item.series_id)}</small>
        <b>${Number(item.value).toLocaleString()}</b>
      </span>
    `).join("");
  elements.cycleSummary.innerHTML = `
    <div>
      <small>${escapeHtml(i18n.t("audit.cycleTitle"))}</small>
      <strong>${escapeHtml(i18n.t(
        regimeLabels[state.cycle.regime] || "audit.cycleInsufficient",
      ))}</strong>
      <em>${escapeHtml(i18n.t("audit.cycleAsOf"))} ${
        escapeHtml(state.cycle.as_of || "—")
      } · ${Math.round(state.cycle.score * 100)}</em>
    </div>
    <div class="cycle-components">${components}</div>
  `;
}

function renderCycleModels() {
  if (!state.cycleModels) return;
  const regimes = {
    expansion: "audit.modelExpansion",
    transition: "audit.modelTransition",
    contraction: "audit.modelContraction",
    insufficient_data: "audit.cycleInsufficient",
  };
  elements.cycleModelList.innerHTML = `
    <h4>${escapeHtml(i18n.t("audit.cycleModels"))}</h4>
    <div>
      ${state.cycleModels.models.map((model) => `
        <article class="cycle-model is-${escapeHtml(model.regime)}">
          <header>
            <b>${escapeHtml(model.name)}</b>
            <span>${escapeHtml(i18n.t(regimes[model.regime]
              || "audit.cycleInsufficient"))}</span>
          </header>
          <p>${escapeHtml(model.theory)}</p>
          <small>${escapeHtml(model.horizon)} · ${
            escapeHtml(i18n.t("audit.modelConfidence"))
          }: ${Math.round(model.confidence * 100)}% · ${
            Math.round(model.score * 100)
          }</small>
          <div>${model.signals.map((signal) => `
            <span title="${escapeAttribute(signal.label)}">
              ${escapeHtml(signal.series_id)}:
              ${signal.value === null ? "—" : Number(signal.value).toLocaleString()}
            </span>
          `).join("")}</div>
        </article>
      `).join("")}
    </div>
  `;
}

function renderCompanies() {
  if (!elements.companyList) return;
  if (!state.companies.length) {
    elements.companyList.innerHTML =
      `<div class="empty-card">${escapeHtml(i18n.t("audit.companyPending"))}</div>`;
    return;
  }
  elements.companyList.innerHTML = state.companies.map((company) => {
    const fact = company.latest_facts?.[0];
    const price = company.latest_price === null
      ? "—"
      : `$${Number(company.latest_price).toLocaleString()}`;
    const filing = company.latest_filing_form
      ? `${company.latest_filing_form} · ${company.latest_filing_date || "—"}`
      : "—";
    const factValue = fact
      ? `${fact.label}: ${Number(fact.value).toLocaleString()} ${fact.unit}`
      : "—";
    return `
      <article class="company-row ${company.last_error ? "has-error" : ""}">
        <header>
          <span><b>${escapeHtml(company.ticker)}</b>${escapeHtml(company.name)}</span>
          <small>${escapeHtml(company.sector)} · ${escapeHtml(company.industry)}</small>
        </header>
        <dl>
          <div><dt>${escapeHtml(i18n.t("audit.companyPrice"))}</dt>
            <dd>${escapeHtml(price)} · ${escapeHtml(company.price_observed_on || "—")}</dd></div>
          <div><dt>${escapeHtml(i18n.t("audit.companyFiling"))}</dt>
            <dd>${escapeHtml(filing)}</dd></div>
          <div><dt>${escapeHtml(i18n.t("audit.companyFact"))}</dt>
            <dd>${escapeHtml(factValue)}</dd></div>
        </dl>
        <footer>
          <a href="${escapeAttribute(company.source_url)}" target="_blank"
            rel="noreferrer">SEC</a>
          <time>${escapeHtml(formatDate(company.last_success_at))}</time>
          ${company.last_error ? `<span title="${escapeAttribute(
            company.last_error,
          )}">sync warning</span>` : ""}
        </footer>
      </article>
    `;
  }).join("");
}

function decisionButton(id, decision, labelKey) {
  return `<button type="button" data-hypothesis-id="${id}"
    data-logic-decision="${decision}">${escapeHtml(i18n.t(labelKey))}</button>`;
}

function scoreChip(labelKey, value) {
  return `<span><small>${escapeHtml(i18n.t(labelKey))}</small><b>${
    percent(value)
  }</b></span>`;
}

function researchStatusLabel(status) {
  const labels = {
    verified: "audit.verified",
    partially_supported: "audit.partial",
    evidence_missing: "audit.missing",
    hypothesis: "audit.hypothesis",
  };
  return i18n.t(labels[status] || status);
}

function logicStepLabel(stepType) {
  const labels = {
    reported_event: "audit.reportedEvent",
    economic_context: "audit.economicContext",
    market_observation: "audit.marketObservation",
    inferred_mechanism: "audit.inferredMechanism",
    counterevidence: "audit.counterevidence",
    possible_outcome: "audit.possibleOutcome",
  };
  return i18n.t(labels[stepType] || "audit.possibleOutcome");
}

function logicStatusLabel(status) {
  const labels = {
    suggested: "audit.statusSuggested",
    accept: "audit.statusAccepted",
    accepted: "audit.statusAccepted",
    revise_and_accept: "audit.statusRevised",
    revised_accepted: "audit.statusRevised",
    defer_for_evidence: "audit.statusDeferred",
    deferred: "audit.statusDeferred",
    reject: "audit.statusRejected",
    rejected: "audit.statusRejected",
  };
  return i18n.t(labels[status] || status);
}

function statusRank(status) {
  return {
    suggested: 0,
    deferred: 1,
    revised_accepted: 2,
    accepted: 3,
    rejected: 4,
  }[status] ?? 5;
}

function causalConclusionLabel(conclusion) {
  if (conclusion === "mechanism_supported_not_causal") {
    return i18n.t("audit.causalSupported");
  }
  if (conclusion === "mechanism_partially_supported") {
    return i18n.t("audit.causalPartial");
  }
  return i18n.t("audit.causalTemporal");
}

function causalCheckLabel(key) {
  const labels = {
    premise_reported: "audit.checkPremise",
    outcome_time_window: "audit.checkTiming",
    mechanism_evidence: "audit.checkMechanism",
    market_expectations: "audit.checkExpectations",
    alternative_explanations: "audit.checkAlternatives",
    causal_sufficiency: "audit.checkSufficiency",
  };
  return i18n.t(labels[key] || key);
}

function causalCheckStatusLabel(status) {
  const labels = {
    passed: "audit.checkPassed",
    partially_supported: "audit.checkPartial",
    missing_evidence: "audit.checkMissing",
    failed: "audit.checkFailed",
    not_applicable: "audit.checkNA",
  };
  return i18n.t(labels[status] || status);
}

function stepCheckKey(step, index, length) {
  if (index === 0 || step.step_type === "reported_event") return "premise_reported";
  if (index === length - 1 || step.step_type === "possible_outcome") {
    return "outcome_time_window";
  }
  if (step.step_type === "market_observation") return "market_expectations";
  if (step.step_type === "counterevidence") return "alternative_explanations";
  return "mechanism_evidence";
}

function localized(zhValue, enValue) {
  return i18n.language === "zh" ? (zhValue || enValue || "") : (enValue || zhValue || "");
}

function percent(value) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

function formatDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat(i18n.language === "zh" ? "zh-CN" : "en-CA", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function showNotice(message, isError = false) {
  elements.notice.textContent = message;
  elements.notice.classList.toggle("is-error", isError);
  elements.notice.hidden = false;
}

async function api(path) {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(await responseMessage(response));
  return response.json();
}

async function apiMutation(path, options) {
  const response = await fetch(path, {
    ...options,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) throw new Error(await responseMessage(response));
  if (response.status === 204) return null;
  const payload = await response.text();
  return payload ? JSON.parse(payload) : null;
}

async function responseMessage(response) {
  try {
    const payload = await response.json();
    return payload.detail || `${response.status} ${response.statusText}`;
  } catch {
    return `${response.status} ${response.statusText}`;
  }
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
  return escapeHtml(value);
}
