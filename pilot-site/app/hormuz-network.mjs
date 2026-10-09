export const hormuzChain = {
  "id": "hormuz-helium",
  "title": {
    "zh": "霍尔木兹—氦气—半导体",
    "en": "Hormuz → helium → semiconductors"
  },
  "kind": "evidence_research",
  "reviewedAt": "2026-10-09",
  "color": "#be9cff",
  "summaryIds": [
    "iran",
    "hormuz",
    "ras",
    "process",
    "cost"
  ],
  "nodes": [
    {
      "id": "iran",
      "zh": "中东冲突 · 3 月记录",
      "en": "Middle East conflict · March record",
      "coordinates": [
        53,
        32
      ],
      "status": "dated_fact",
      "branch": "shared",
      "kind": "region",
      "noteZh": "Shell 的 3 月披露支持停产背景；区域中心不是攻击点。",
      "noteEn": "Shell’s March disclosures support shutdown context; regional center is not an attack location.",
      "sources": [
        {
          "id": "S1",
          "title": "Shell · Middle East operational updates",
          "url": "https://www.shell.com/news-and-insights/newsroom/news-and-media-releases/2026/impact-of-middle-east-conflict-on-shell-activities.html",
          "date": "2026-03-19 / 20",
          "boundary": {
            "zh": "3 月 LNG 停产及设施影响；不证明当前氦气产量。",
            "en": "March LNG shutdown and facility impacts; not current helium output."
          }
        }
      ],
      "coordinatePrecision": "regional_reference"
    },
    {
      "id": "hormuz",
      "zh": "霍尔木兹 · 通行约束",
      "en": "Hormuz · passage constraints",
      "coordinates": [
        56.3,
        26.6
      ],
      "status": "dated_context",
      "branch": "shared",
      "kind": "region",
      "noteZh": "EIA 10 月 6 日展望基于 10 月 1 日信息；约束与逐步恢复是预测设定，不是实时封锁状态。",
      "noteEn": "EIA’s October 6 outlook uses October 1 inputs; constraints and gradual recovery are forecast assumptions, not live closure status.",
      "sources": [
        {
          "id": "S2",
          "title": "EIA · October Short-Term Energy Outlook",
          "url": "https://www.eia.gov/outlooks/steo/",
          "date": "2026-10-06 · inputs through 2026-10-01",
          "boundary": {
            "zh": "油流约束与恢复是有截止日的预测假设；不是实时氦气通航证明。",
            "en": "Dated oil-flow forecast assumptions, not live helium transit evidence."
          }
        }
      ],
      "coordinatePrecision": "regional_reference"
    },
    {
      "id": "ras",
      "zh": "Ras Laffan · 氦气产地",
      "en": "Ras Laffan · helium origin",
      "coordinates": [
        51.55,
        25.92
      ],
      "status": "context",
      "branch": "helium",
      "kind": "region",
      "noteZh": "运营资料支持氦气生产及充装。当前氦气装置状态、产量和出口量仍待核验。",
      "noteEn": "Operations sources support helium production and filling. Current helium plant status, output and exports remain unverified.",
      "sources": [
        {
          "id": "S4",
          "title": "QatarEnergy LNG · Ras Laffan Helium",
          "url": "https://www.qatarenergylng.qa/english/operations/ras-laffan-helium",
          "date": "Undated / historical operations",
          "boundary": {
            "zh": "氦气业务及历史销售安排；不据此推算 2026 年市场份额。",
            "en": "Helium operations and historical sales arrangements; not 2026 market shares."
          }
        },
        {
          "id": "S5",
          "title": "Buzwair · New liquid helium containers",
          "url": "https://buzwairgases.com/new-liquid-helium-containers",
          "date": "2023-11-12",
          "boundary": {
            "zh": "专用 ISO 容器及 Ras Laffan 充装背景；不证明亚洲某客户的货物路径。",
            "en": "Dedicated ISO containers and Ras Laffan filling context; not an Asian customer's cargo route."
          }
        }
      ],
      "coordinatePrecision": "regional_reference"
    },
    {
      "id": "oman",
      "zh": "阿曼湾 · 候选运输段",
      "en": "Gulf of Oman · candidate transit",
      "coordinates": [
        59,
        24
      ],
      "status": "hypothesis",
      "branch": "helium",
      "kind": "region",
      "noteZh": "专用低温容器的示意航段；没有船名、提单或实际航迹。",
      "noteEn": "Schematic cryogenic-container transit; no vessel, bill of lading or actual track.",
      "sources": [
        {
          "id": "S5",
          "title": "Buzwair · New liquid helium containers",
          "url": "https://buzwairgases.com/new-liquid-helium-containers",
          "date": "2023-11-12",
          "boundary": {
            "zh": "专用 ISO 容器及 Ras Laffan 充装背景；不证明亚洲某客户的货物路径。",
            "en": "Dedicated ISO containers and Ras Laffan filling context; not an Asian customer's cargo route."
          }
        },
        {
          "id": "S7",
          "title": "Linde · Helium sourcing and distribution",
          "url": "https://www.linde-gas.com/products-and-services/gases/helium",
          "date": "Undated",
          "boundary": {
            "zh": "多来源、提纯液化与转充网络；没有可立即调用的余量数据。",
            "en": "Diversified sourcing, processing and transfill network; no immediately available spare capacity."
          }
        }
      ],
      "coordinatePrecision": "regional_reference"
    },
    {
      "id": "malacca",
      "zh": "马六甲 · 候选运输段",
      "en": "Malacca · candidate transit",
      "coordinates": [
        101.2,
        2.3
      ],
      "status": "hypothesis",
      "branch": "helium",
      "kind": "region",
      "noteZh": "用于解释通往东亚的候选海路，并非已验证的订单路线。",
      "noteEn": "Illustrates a candidate maritime path toward East Asia, not a verified order route.",
      "sources": [
        {
          "id": "S7",
          "title": "Linde · Helium sourcing and distribution",
          "url": "https://www.linde-gas.com/products-and-services/gases/helium",
          "date": "Undated",
          "boundary": {
            "zh": "多来源、提纯液化与转充网络；没有可立即调用的余量数据。",
            "en": "Diversified sourcing, processing and transfill network; no immediately available spare capacity."
          }
        }
      ],
      "coordinatePrecision": "regional_reference"
    },
    {
      "id": "singapore",
      "zh": "新加坡 · 区域气体网络",
      "en": "Singapore · regional gas network",
      "coordinates": [
        103.82,
        1.35
      ],
      "status": "context",
      "branch": "buffers",
      "kind": "region",
      "noteZh": "电子材料区域布局仅为网络背景；不表示卡塔尔氦气必经此处或已有替代余量。",
      "noteEn": "Electronics footprint is network context only; not proof Qatar helium transits here or spare supply is available.",
      "sources": [
        {
          "id": "S9",
          "title": "Air Liquide · Local production in Asia",
          "url": "https://www.airliquide.com/stories/integrated-annual-report/long-term-contracts-local-production-serving-asia-semiconductor-growth",
          "date": "2026-04-14",
          "boundary": {
            "zh": "亚洲电子材料布局；先进材料本地产能不等于本地氦气开采。",
            "en": "Asian electronics footprint; local advanced materials are not local helium extraction."
          }
        }
      ],
      "coordinatePrecision": "regional_reference"
    },
    {
      "id": "taiwan",
      "zh": "新竹 · 晶圆制造参考地区",
      "en": "Hsinchu · reference fab region",
      "coordinates": [
        120.97,
        24.81
      ],
      "status": "context",
      "branch": "helium",
      "kind": "region",
      "noteZh": "TSMC 公开厂址支持地区定位；没有确认本图上游供应商与该厂的氦气采购关系。",
      "noteEn": "TSMC’s public locations support the region, not a helium procurement link from the upstream suppliers shown.",
      "sources": [
        {
          "id": "S10",
          "title": "TSMC · Fab locations",
          "url": "https://www.tsmc.com/english/aboutTSMC/TSMC_Fabs",
          "date": "Undated",
          "boundary": {
            "zh": "晶圆厂所在地区；没有确认卡塔尔氦气采购、合同与库存。",
            "en": "Fab regions; no confirmation of Qatar helium procurement, contracts or inventory."
          }
        }
      ],
      "coordinatePrecision": "regional_reference"
    },
    {
      "id": "korea",
      "zh": "华城 · 电子材料参考地区",
      "en": "Hwaseong · electronics region",
      "coordinates": [
        126.83,
        37.2
      ],
      "status": "context",
      "branch": "helium",
      "kind": "region",
      "noteZh": "Air Liquide 披露当地先进材料布局；不能将该节点当作氦气工厂或停产证据。",
      "noteEn": "Air Liquide discloses an advanced-materials footprint here; this is not a helium plant or evidence of a shutdown.",
      "sources": [
        {
          "id": "S9",
          "title": "Air Liquide · Local production in Asia",
          "url": "https://www.airliquide.com/stories/integrated-annual-report/long-term-contracts-local-production-serving-asia-semiconductor-growth",
          "date": "2026-04-14",
          "boundary": {
            "zh": "亚洲电子材料布局；先进材料本地产能不等于本地氦气开采。",
            "en": "Asian electronics footprint; local advanced materials are not local helium extraction."
          }
        }
      ],
      "coordinatePrecision": "regional_reference"
    },
    {
      "id": "lng",
      "zh": "LNG · 供应收缩路径",
      "en": "LNG · supply contraction",
      "coordinates": [
        51.2,
        25.1
      ],
      "status": "dated_context",
      "branch": "energy",
      "kind": "region",
      "noteZh": "卡塔尔区域示意点。EIA 4 月讨论的供应收缩可能影响区域气价；不是当前电价。",
      "noteEn": "Qatar regional reference. EIA’s April supply discussion informs a gas-price channel, not current electricity tariffs.",
      "sources": [
        {
          "id": "S3",
          "title": "EIA · April energy outlook release",
          "url": "https://www.eia.gov/pressroom/releases/press586.php",
          "date": "2026-04-07",
          "boundary": {
            "zh": "历史 LNG 供应与区域价差背景；旧预测不等于实现值。",
            "en": "Historical LNG supply and regional spreads; forecasts are not realized outcomes."
          }
        }
      ],
      "coordinatePrecision": "regional_reference"
    },
    {
      "id": "purity",
      "zh": "提纯 / 认证 / 库存",
      "en": "Purity / qualification / inventory",
      "coordinates": null,
      "status": "hypothesis",
      "branch": "helium",
      "kind": "mechanism",
      "noteZh": "到港不等于工艺可用：还需提纯、转充、配送、质量认证与库存覆盖。",
      "noteEn": "Arrival is not process availability: purification, transfill, delivery, qualification and stock coverage matter.",
      "sources": [
        {
          "id": "S6",
          "title": "Air Liquide · Helium applications",
          "url": "https://ph.airliquide.com/helium",
          "date": "Undated",
          "boundary": {
            "zh": "电子工艺、热管理及泄漏检测用途；不披露单厂耗量。",
            "en": "Electronics, thermal management and leak-checking uses; no fab-level consumption."
          }
        },
        {
          "id": "S7",
          "title": "Linde · Helium sourcing and distribution",
          "url": "https://www.linde-gas.com/products-and-services/gases/helium",
          "date": "Undated",
          "boundary": {
            "zh": "多来源、提纯液化与转充网络；没有可立即调用的余量数据。",
            "en": "Diversified sourcing, processing and transfill network; no immediately available spare capacity."
          }
        }
      ],
      "coordinatePrecision": "not_geographic"
    },
    {
      "id": "process",
      "zh": "热管理 / 惰性环境 / 检漏",
      "en": "Thermal control / inerting / leak checks",
      "coordinates": null,
      "status": "context",
      "branch": "helium",
      "kind": "mechanism",
      "noteZh": "氦气存在电子工艺用途，但不同设备与工艺的关键性、替代可能不同。",
      "noteEn": "Helium has electronics applications; criticality and substitutability vary by equipment and process.",
      "sources": [
        {
          "id": "S6",
          "title": "Air Liquide · Helium applications",
          "url": "https://ph.airliquide.com/helium",
          "date": "Undated",
          "boundary": {
            "zh": "电子工艺、热管理及泄漏检测用途；不披露单厂耗量。",
            "en": "Electronics, thermal management and leak-checking uses; no fab-level consumption."
          }
        }
      ],
      "coordinatePrecision": "not_geographic"
    },
    {
      "id": "power",
      "zh": "气价 → 电价 / 能源合同？",
      "en": "Gas prices → power / energy contracts?",
      "coordinates": null,
      "status": "hypothesis",
      "branch": "energy",
      "kind": "mechanism",
      "noteZh": "是否传导取决于发电结构、燃料合同、监管电价与时滞，不能一比一折算。",
      "noteEn": "Transmission depends on generation mix, fuel contracts, regulated tariffs and lag; not one-for-one.",
      "sources": [
        {
          "id": "S3",
          "title": "EIA · April energy outlook release",
          "url": "https://www.eia.gov/pressroom/releases/press586.php",
          "date": "2026-04-07",
          "boundary": {
            "zh": "历史 LNG 供应与区域价差背景；旧预测不等于实现值。",
            "en": "Historical LNG supply and regional spreads; forecasts are not realized outcomes."
          }
        }
      ],
      "coordinatePrecision": "not_geographic"
    },
    {
      "id": "buffer",
      "zh": "多源采购 / 回收 / 安全库存",
      "en": "Diversification / recovery / safety stock",
      "coordinates": null,
      "status": "conditional_buffer",
      "branch": "buffers",
      "kind": "mechanism",
      "noteZh": "多源与回收可减弱冲击，但运输设备、认证、建设周期及经济性形成约束。",
      "noteEn": "Diversification and recovery can dampen shocks, constrained by transport assets, qualification, lead times and economics.",
      "sources": [
        {
          "id": "S7",
          "title": "Linde · Helium sourcing and distribution",
          "url": "https://www.linde-gas.com/products-and-services/gases/helium",
          "date": "Undated",
          "boundary": {
            "zh": "多来源、提纯液化与转充网络；没有可立即调用的余量数据。",
            "en": "Diversified sourcing, processing and transfill network; no immediately available spare capacity."
          }
        },
        {
          "id": "S11",
          "title": "Air Liquide · Tailored helium liquefiers",
          "url": "https://engineering-technologies.airliquide.com/technologies/cryogenics/tailored-helium-liquefiers",
          "date": "Undated",
          "boundary": {
            "zh": "液化与回收技术存在；不能推定各晶圆厂已经安装。",
            "en": "Liquefaction and recovery technology exists; not proof of deployment at individual fabs."
          }
        }
      ],
      "coordinatePrecision": "not_geographic"
    },
    {
      "id": "cost",
      "zh": "采购成本 / 交期 / 开工率？",
      "en": "Procurement / lead times / utilization?",
      "coordinates": null,
      "status": "hypothesis",
      "branch": "shared",
      "kind": "mechanism",
      "noteZh": "先核对合同价格、可用库存、产线披露，再估算利润。短缺风险不能直接写成已减产。",
      "noteEn": "Verify contracted prices, usable stocks and operating disclosures before estimating profit. Shortage risk is not a realized production cut.",
      "sources": [
        {
          "id": "S6",
          "title": "Air Liquide · Helium applications",
          "url": "https://ph.airliquide.com/helium",
          "date": "Undated",
          "boundary": {
            "zh": "电子工艺、热管理及泄漏检测用途；不披露单厂耗量。",
            "en": "Electronics, thermal management and leak-checking uses; no fab-level consumption."
          }
        },
        {
          "id": "S7",
          "title": "Linde · Helium sourcing and distribution",
          "url": "https://www.linde-gas.com/products-and-services/gases/helium",
          "date": "Undated",
          "boundary": {
            "zh": "多来源、提纯液化与转充网络；没有可立即调用的余量数据。",
            "en": "Diversified sourcing, processing and transfill network; no immediately available spare capacity."
          }
        }
      ],
      "coordinatePrecision": "not_geographic"
    },
    {
      "id": "invest",
      "zh": "盈利验证 → 估值 → 投资假设",
      "en": "Earnings checks → valuation → thesis",
      "coordinates": null,
      "status": "unvalidated",
      "branch": "shared",
      "kind": "mechanism",
      "noteZh": "研究观察清单，不是交易信号：尚无企业级损益归因、事件回测或当前估值检验。",
      "noteEn": "Research watchlist, not a trading signal: issuer-level attribution, event backtest and current valuation checks remain outstanding.",
      "sources": [],
      "coordinatePrecision": "not_geographic"
    }
  ],
  "edges": [
    {
      "from": "iran",
      "to": "hormuz",
      "branch": "shared",
      "kind": "hypothesis",
      "status": "hypothesis"
    },
    {
      "from": "iran",
      "to": "ras",
      "branch": "helium",
      "kind": "hypothesis",
      "status": "hypothesis"
    },
    {
      "from": "ras",
      "to": "hormuz",
      "branch": "helium",
      "kind": "hypothesis",
      "status": "hypothesis"
    },
    {
      "from": "hormuz",
      "to": "oman",
      "branch": "helium",
      "kind": "logistics",
      "status": "hypothesis"
    },
    {
      "from": "oman",
      "to": "malacca",
      "branch": "helium",
      "kind": "logistics",
      "status": "hypothesis",
      "coordinates": [
        [
          59,
          24
        ],
        [
          65,
          19
        ],
        [
          75,
          8
        ],
        [
          84,
          5
        ],
        [
          94,
          6.5
        ],
        [
          99,
          6.5
        ],
        [
          101.2,
          2.3
        ]
      ]
    },
    {
      "from": "malacca",
      "to": "taiwan",
      "branch": "helium",
      "kind": "logistics",
      "status": "hypothesis",
      "coordinates": [
        [
          101.2,
          2.3
        ],
        [
          103.5,
          1
        ],
        [
          104.5,
          1
        ],
        [
          105,
          4
        ],
        [
          111,
          12
        ],
        [
          118,
          20
        ],
        [
          120.97,
          24.81
        ]
      ]
    },
    {
      "from": "malacca",
      "to": "korea",
      "branch": "helium",
      "kind": "logistics",
      "status": "hypothesis",
      "coordinates": [
        [
          101.2,
          2.3
        ],
        [
          103.5,
          1
        ],
        [
          104.5,
          1
        ],
        [
          105,
          4
        ],
        [
          111,
          12
        ],
        [
          125,
          24
        ],
        [
          128,
          31
        ],
        [
          126.83,
          37.2
        ]
      ]
    },
    {
      "from": "malacca",
      "to": "singapore",
      "branch": "buffers",
      "kind": "hypothesis",
      "status": "hypothesis"
    },
    {
      "from": "singapore",
      "to": "buffer",
      "branch": "buffers",
      "kind": "hypothesis",
      "status": "hypothesis"
    },
    {
      "from": "ras",
      "to": "purity",
      "branch": "helium",
      "kind": "hypothesis",
      "status": "hypothesis"
    },
    {
      "from": "taiwan",
      "to": "purity",
      "branch": "helium",
      "kind": "hypothesis",
      "status": "hypothesis"
    },
    {
      "from": "korea",
      "to": "purity",
      "branch": "helium",
      "kind": "hypothesis",
      "status": "hypothesis"
    },
    {
      "from": "purity",
      "to": "process",
      "branch": "helium",
      "kind": "hypothesis",
      "status": "hypothesis"
    },
    {
      "from": "process",
      "to": "cost",
      "branch": "helium",
      "kind": "hypothesis",
      "status": "hypothesis"
    },
    {
      "from": "hormuz",
      "to": "lng",
      "branch": "energy",
      "kind": "hypothesis",
      "status": "hypothesis"
    },
    {
      "from": "lng",
      "to": "power",
      "branch": "energy",
      "kind": "hypothesis",
      "status": "hypothesis"
    },
    {
      "from": "power",
      "to": "cost",
      "branch": "energy",
      "kind": "hypothesis",
      "status": "hypothesis"
    },
    {
      "from": "buffer",
      "to": "cost",
      "branch": "buffers",
      "kind": "hypothesis",
      "status": "hypothesis"
    },
    {
      "from": "cost",
      "to": "invest",
      "branch": "shared",
      "kind": "hypothesis",
      "status": "hypothesis"
    }
  ],
  "scope": {
    "zh": "地域参考点 · 所有连线为机制或候选路线，不是实时货运 / 企业供货证明",
    "en": "Regional references · every edge is a mechanism or candidate route, not live cargo or proof of issuer supply"
  }
};
