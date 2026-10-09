// Analyst-authored synthesis. Sources support facts; scenarios are explicitly conditional.
const section=(id,zh,en,bodyZh,bodyEn,sources)=>({id,title:{zh,en},body:{zh:bodyZh,en:bodyEn},sources});
export const appleResearch={
 id:'apple-multidimensional-20261009-v1',ticker:'AAPL',createdAt:'2026-10-09',version:1,
 title:{zh:'苹果：从供应产地到利润与现金流',en:'Apple: from supplier locations to profit and cash flow'},
 subtitle:{zh:'五维与多维证据研究 · 全球供应网络专题',en:'Five-dimensional evidence research · global supply network'},
 status:{zh:'公开证据综合研究；情景未验证，不构成投资批准',en:'Public-evidence synthesis; scenarios unvalidated, not investment approval'},
 scope:{zh:'实际编写：2026-10-09。供应名单：FY2023；财务基准：FY2025，非最新季度估值报告；区域信号窗口：2026-06-28 至 2026-09-19。不同时间层分别保留，不能合成同一时点事实。覆盖已收录名单，不等于所有层级、所有工厂或所有成本已公开。',en:'Written 2026-10-09. Supplier list: FY2023; financial baseline: FY2025, not a latest-quarter valuation. Regional signals: 2026-06-28 through 2026-09-19. These vintages remain separate, not a single point-in-time observation. Coverage of the ingested list is not coverage of every tier, factory or private cost.'},
 conclusion:{zh:'核心判断：苹果供应链的研究重点不是“地图上有多少风险点”，而是某个受影响的工艺、产地或渠道是否不可替代，以及库存能否覆盖恢复时间。当前证据支持供应产地网络的存在，不支持把全部邻近事件累加为损失。最值得跟踪的是：供应商确认的产能中断 → 合格替代与库存缺口 → 交付延迟或增量成本 → 披露中的利润、现金流变化。',en:'The key question is not how many risk markers appear, but whether an affected process, location or channel is replaceable and whether inventory covers recovery time. Evidence supports a supplier-location network, not an additive loss estimate from nearby events. Track confirmed capacity interruption → qualified alternatives and inventory gap → delivery delay or incremental cost → disclosed profit and cash-flow effects.'},
 sources:[
  {id:'S1',title:'Apple Supplier List · FY2023 · 27 pages',url:'https://www.supplychainreports.apple/Apple-Supplier-List',basis:'FY2023; checked 2026-10-09'},
  {id:'S2',title:'Apple FY2025 Form 10-K · financial statements / purchase obligations',url:'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm',basis:'Fiscal year ended 2025-09-27; filed 2025-10-31'},
  {id:'S3',title:'Apple · American Manufacturing Program',url:'https://www.apple.com/newsroom/2025/08/apple-increases-us-commitment-to-600-billion-usd-announces-ambitious-program/',basis:'2025-08-06; announcement, not completed capacity'},
  {id:'S4',title:'Apple · Environmental Progress Report 2026',url:'https://www.apple.com/environment/pdf/Apple_Environmental_Progress_Report_2026.pdf',basis:'2025 environmental reporting; aggregate, not factory uptime'},
  {id:'S5',title:'Apple · Supply Chain Innovation Reports',url:'https://www.supplychainreports.apple/home/',basis:'Current report directory checked 2026-10-09'}
 ],
 sections:[
  section('business','01 / 商业与财务：影响落在哪里？','01 / Business & finance: where does impact land?',[
   '财务锚点（FY2025，美元）：总收入 4,161.61 亿，产品收入 3,070.03 亿，服务收入 1,091.58 亿。2025-09-27 制造采购义务为 562 亿，其中 554 亿在十二个月内应付。这些是公司总量，不是供应商收入、订单份额或事件损失。[S2]',
   '分析推演：零部件中断首先影响可交付产品的数量、组合与时间。推迟交付不一定等于永久丢失收入；后续补交、替代产品和渠道库存可能抵消部分影响。服务也不能简单视为完全独立于硬件装机基础。应把交付、收入确认、毛利和现金付款分开观察。',
   '可检验路径：先确认受影响产品和有效产能，再比较交付周期、库存与管理层披露。若交付正常、库存可吸收冲击或其他产品增长抵消，供应链事件对公司总量的解释力下降。没有采购分摊数据时，不把总采购义务按供应商数量均分。'
  ],[
   'FY2025 anchors, USD: revenue $416.161bn, products $307.003bn, services $109.158bn. At 2025-09-27 manufacturing purchase obligations were $56.2bn, including $55.4bn due within twelve months. These are company totals, not supplier shares or event losses. [S2]',
   'Analytical mechanism: component interruption can change deliverable volume, mix and timing. Deferred delivery need not be permanently lost revenue; catch-up shipments, substitutes and channel inventory may absorb the shock. Services should not be assumed independent of the hardware installed base. Separate delivery, recognition, margin and cash payment.',
   'Test the affected product and effective capacity against lead times, inventory and management disclosures. Normal delivery, sufficient buffers or offsetting product growth would weaken the proposed explanation. Do not divide aggregate purchase obligations evenly across suppliers.'
  ],['S2']),
  section('network','02 / 产业与供应：从公司名单到工艺依赖','02 / Industry & supply: names are not process dependencies',[
   '官方名单覆盖 FY2023 全球材料、制造与组装直接支出的 98%；不是供应商数量的 98%，也不是完整多级供应链。此次把本地已收录的 187 家、724 条产地记录全部纳入，取消 500 条截断。同一供应商可有多个产地，多个供应商也会共享地区参考坐标。[S1]',
   '地图分层：绿色为苹果披露的 704 条地区记录，紫色为另 20 条供应商设施背景（不证明为苹果生产）；青色虚线为最近港口参考；橙色为地区风险筛选。名单不能单独证明具体产品、工厂产线、供货比例或供应商之间的交易。TSMC、Foxconn、Luxshare 等名称可直接搜索，角色和时点仍须逐项核对。',
   '研究方法：建立“部件/工艺—合格供应商—产地—替代工艺—认证时间”的依赖表。对单一来源、资格认证长、产能爬坡慢的环节优先取证。名单上有第二家企业不等于其具备同等规格、可用产能或可即时切换。',
   '反证：多地布局、双供、库存和设计替代可能降低中断风险；同时，多地供应商若共享同一材料或设备上游，也可能存在隐藏的共同瓶颈。当前没有完整二级及以上供应关系，不能把网络中心性当作已验证的供应份额。'
  ],[
   'The official list covers 98% of FY2023 direct spending on materials, manufacturing and assembly, not 98% of supplier count or all supply-chain tiers. All 187 ingested suppliers and 724 location records are included, removing the 500-row cap. Suppliers may have multiple locations and share regional reference coordinates. [S1]',
   'Green marks 704 Apple-reported region records; purple marks 20 additional supplier-facility context records, not confirmed Apple production. Cyan dashed links are nearest-port references; orange marks regional screening. A supplier tie does not establish a product, line, procurement share or inter-supplier transaction. Search TSMC, Foxconn and Luxshare, then verify role and vintage.',
   'Build a dependency table of component/process, qualified supplier, location, substitute and qualification time. Prioritize sole-source, long-qualification and slow-ramp processes. A second listed company does not imply interchangeable specifications, spare capacity or immediate switching.',
   'Alternatives include diversified production, dual sourcing, buffers and redesign. However, suppliers in different regions may share an upstream material or equipment bottleneck. Missing higher-tier links mean network centrality is not a verified measure of procurement exposure.'
  ],['S1','S5']),
  section('macro','03 / 宏观、贸易与物流：先确认真实渠道','03 / Macro, trade & logistics: verify the actual channel',[
   '分析推演：关税、出口许可、海关、汇率与跨境运输可能分别影响到岸成本、交期与需求。应按产品原产地、海关归类、适用日期、豁免、合同条款逐项核算；国家新闻不等于所有苹果产品适用同一税率。',
   '最近港口只是地理检索入口。真实供应可能采用空运、陆运、其他港口或中转仓；因此地图不会把候选线称为货运实况。验证需要提单、承运商公告、供应商说明或企业披露，缺失时路线状态保持“参考”。',
   '苹果 2025-08-06 宣布美国制造计划及未来四年 6,000 亿美元美国投入承诺。研究中把它视为计划信号，不能视为当日已投产资产、立即可替代海外产能或全部采购成本。[S3]',
   '反证和时滞：套期保值、合同转嫁、替代渠道与当地库存可削弱冲击；认证、设备安装和良率爬坡则可能延后新产能效果。必须把政策公告、法律生效、企业实施与会计体现放在不同时间轴。'
  ],[
   'Analytical mechanism: tariffs, export permissions, customs, FX and transport can separately affect landed cost, lead time and demand. Check product origin, classification, effective date, exemptions and contract terms. A country-level headline does not assign one tariff to every Apple product.',
   'A nearest port is a geographic lookup, not an observed route. Actual movement may use air, road, another port or a consolidation hub. Bills of lading, carrier notices or company disclosures are needed; absent these, every candidate route remains a reference.',
   'On 2025-08-06 Apple announced a US manufacturing program and a $600bn US commitment over four years. This is a plan signal, not already-operating assets, immediately substitutable overseas capacity or a procurement-cost total. [S3]',
   'Hedging, pass-through, alternative channels and local buffers may soften a shock. Qualification, installation and yield ramps may delay new capacity. Keep announcement, legal effectiveness, implementation and accounting recognition on separate timelines.'
  ],['S3']),
  section('physical','04 / 电力、水与灾害：从邻近到实际暴露','04 / Power, water & hazards: proximity is not impact',[
   '本次地图风险窗口是 2026-06-28 至 2026-09-19。724 条产地中，81 条匹配到地区冲突信号、53 条匹配到邻近灾害信号；这些是“有匹配的产地条数”，不能相加为独立事件数量或受灾工厂数量。共同地区事件可能重复命中多个供应商。',
   '电力信号当前匹配为零，含义是本数据集没有匹配记录，不是零停电风险。供应电网、变电站、峰值负荷、备用电源时长、电价合同和耗水强度尚无逐厂资料，地图用“未知”表达，不虚构电厂位置与供电线路。',
   '2026 环境报告披露：2025 年供应商采购并投入运行的可再生能源超过 20 GW，发电超过 3,800 万 MWh。这是供应链清洁能源总量，不能证明任何具体工厂有持续、不间断的电力保障。[S4]',
   '传导条件：灾害需与实际厂址、生产时段和受损设备重合，且备用设施与库存不能完全抵消，才可能形成交付或成本影响。应核验停工起止时间、恢复产能、报废与重启成本。地区质心尤其不能替代厂址判断。'
  ],[
   'The risk window is 2026-06-28 through 2026-09-19. Of 724 location records, 81 match regional conflict signals and 53 nearby disaster signals. These count matched location records, not independent incidents or damaged factories. One regional incident can match multiple suppliers.',
   'Zero matched power signals means no matching records in this dataset, not zero outage risk. Factory-level grid connections, substations, peak load, backup duration, power contracts and water intensity remain unknown. No invented power plants or electricity routes are drawn.',
   'The 2026 environmental report states that supplier renewable energy procured and operating in 2025 exceeded 20 GW and generated over 38 million MWh. Supply-chain renewable totals do not establish uninterrupted electricity at any particular facility. [S4]',
   'Transmission requires overlap with the actual facility, operating window and affected equipment, beyond buffers and backup capacity. Verify stoppage dates, restored capacity, scrap and restart expense. Regional centroids cannot substitute for precise facility exposure.'
  ],['S4']),
  section('market','05 / 市场、估值与可证伪性：不要跳过最后一公里','05 / Markets, valuation & falsifiability: do not skip the last link',[
   '本专题没有绑定截至今日的价格、盈利预测或事件窗口收益率，因此不提供目标价、涨跌概率、交易信号或“验证 Alpha”标签。供应关系成立，不代表股票必然按同方向反应；价格还取决于市场事先预期与其他同期信息。',
   '检验设计：确定最早公开时间与交易时区，预先指定观察窗口，比较苹果与市场/行业基准，并排查财报、产品发布、利率和监管等同日干扰。数据发布后才可使用，不能把新名单倒填进历史回测。',
   '多维结论分级：来源确认产地；邻近数据提出核查候选；机制分析解释可能的传导；实际运营与财务披露决定是否升级为已实现影响。当前最后两环没有完整逐供应商证据，保持条件结论。',
   '可推翻本报告风险假说的材料：正常交付、未受影响产线、充分替代产能、低暴露采购份额或保险和价格转嫁覆盖成本。没有发现反证也不代表因果已经成立。'
  ],[
   'No current price, earnings consensus or event-window returns are bound to this study. It therefore provides no target price, directional probability, trading signal or validated-Alpha label. A supplier relationship does not imply a particular equity reaction; expectations and concurrent information matter.',
   'Test design: establish first public availability and trading timezone, pre-specify windows, compare Apple with market/industry benchmarks and check earnings, launches, rates and regulation as confounders. Do not backfill new supplier knowledge into historical tests.',
   'Evidence ladder: sources establish location ties; proximity produces candidates; mechanism analysis explains potential transmission; operating and financial disclosures establish realized effects. The latter links lack complete supplier-specific evidence, so conclusions remain conditional.',
   'Normal deliveries, unaffected production lines, spare qualified capacity, small procurement exposure, insurance or pass-through can defeat the risk thesis. Absence of discovered counter-evidence is not proof of causality.'
  ],[]),
  section('cost','成本桥：可以计算什么，还缺什么','Cost bridge: what is calculable, what is missing?',[
   '增量成本分解：受影响采购基数 × 单位成本变化 + 加急运输 + 替代认证 + 报废/重启 + 增量库存资金占用 − 可收回保险/赔偿 − 已实现成本转嫁。各项须采用同一币种、期间及采购主体，避免供应商成本与苹果承担部分重复相加。',
   '停产和销售损失单独测算：未被库存或补产覆盖的可售数量 × 单位贡献利润。不要用全部收入代替利润损失，也不要把同一缺货同时计入销售损失和全部采购成本。服务业务应使用不同驱动假设。',
   '示例仅演示算式：若假定受影响采购基数为 1 亿美元、单位成本上升 2%，直接增量为 200 万美元。这不是苹果真实暴露；运输、认证、库存、税费、保险和销量均未包含。下方可调计算器不把缺失项默认为零。',
   '逐供应商真实影响成本目前无法完整计算：采购金额、产品份额、合同转嫁、库存、替代能力和交付批次未公开。目录为每个供应商显示“成本未披露”，禁止按地图点数平均分配公司成本。'
  ],[
   'Incremental cost = affected procurement base × unit-cost change + expedited transport + substitution qualification + scrap/restart + incremental inventory financing − recoverable insurance/compensation − realized pass-through. Align currency, period and contracting entity; do not count supplier expense and Apple’s share twice.',
   'Model lost sales separately: sellable units not covered by inventory or catch-up × unit contribution margin. Revenue is not lost profit. Avoid counting the same shortage as both lost contribution and an entire procurement expense. Services require different drivers.',
   'Arithmetic example only: an assumed $100m affected procurement base and 2% increase yield $2m direct incremental cost. This is not Apple exposure. Transport, qualification, inventory, tax, insurance and volume effects are excluded. The calculator does not convert missing items to zero.',
   'Complete supplier-level cost estimation is unavailable: spend, product allocation, pass-through, buffers, substitution and shipments are not disclosed comprehensively. Every supplier retains an undisclosed-cost status; company costs are never allocated by map-point count.'
  ],[]),
  section('scenarios','三条情景与审核清单','Three scenarios & review checklist',[
   '短时中断、库存吸收：若恢复期短于可用缓冲期，重点核验加急费与补库存现金占用；不能直接推断收入下降。',
   '关键工艺长时中断：若缺少合格替代且库存耗尽，核验产品交付、产能分配与渠道缺货；随后检查财务体现。',
   '结构性迁移：若贸易规则改变落地经济性，核验资本开支、认证周期、良率爬坡及合同变更。地域分散的长期好处与短期重复成本可以同时存在。',
   '发布前交叉核对：名单年份与来源一致；产地不被标成精确工厂；参考港口不被标成真实路线；区域事件不被累计成损失；未知电力与成本不填零；历史来源不冒充最新；英文与中文数值、单位、期间一致。此次完成的是带缺口的专题研究，不是所有供应链事实已获完整审计。'
  ],[
   'Brief interruption absorbed by inventory: if recovery is shorter than the usable buffer, investigate expediting and replenishment cash needs rather than assuming revenue declines.',
   'Prolonged critical-process interruption: absent qualified substitutes and after buffers exhaust, verify deliveries, capacity allocation and channel shortages, then examine financial recognition.',
   'Structural relocation: if trade rules change landed economics, verify capex, qualification, yield ramp and contracts. Long-run diversification benefits can coexist with near-term duplicated cost.',
   'Cross-check: source vintage consistent; regions not labeled exact factories; nearest ports not labeled actual routes; regional events not accumulated into losses; missing power/cost not zero-filled; historical sources not presented as current; bilingual values, units and periods aligned. This is a completed scoped study with explicit gaps, not a complete audit of every supply-chain fact.'
  ],[])
 ]
};
