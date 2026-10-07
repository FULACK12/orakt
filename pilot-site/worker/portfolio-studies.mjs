import {createHash} from 'node:crypto';
import {workspaceAccess} from './research-tiers.mjs';
const names=(zh,en)=>({zh,en});
// Recipes are fixed economic illustrations, not selected/ranked by realized return.
export const recipes=[
 {id:'tech-core',title:names('美股科技核心','US technology core'),market:'us',tier:'signal',weights:{'EQ:AAPL':.35,'EQ:NVDA':.25,'EQ:MSFT':.25,'CASH:USD':.15}},
 {id:'consumer-tech',title:names('消费与科技','Consumer & technology'),market:'us',tier:'signal',weights:{'EQ:LULU':.4,'EQ:AAPL':.4,'CASH:USD':.2}},
 {id:'broad-tech',title:names('宽基与科技板块','Broad market & technology'),market:'us',tier:'signal',weights:{'TD:SPY':.5,'TD:XLK':.3,'CASH:USD':.2}},
 {id:'equal-tech',title:names('科技等权','Equal-weight technology'),market:'us',tier:'research',weights:{'EQ:AAPL':.25,'EQ:NVDA':.25,'EQ:AMD':.25,'EQ:MSFT':.25}},
 {id:'chip-pair',title:names('半导体双公司','Semiconductor pair'),market:'us',tier:'research',weights:{'EQ:NVDA':.5,'EQ:AMD':.5}},
 {id:'cash-buffer',title:names('科技与现金缓冲','Technology & cash buffer'),market:'us',tier:'research',weights:{'EQ:AAPL':.2,'EQ:MSFT':.2,'EQ:NVDA':.1,'CASH:USD':.5}},
 {id:'china-consumer',title:names('中国消费与制造','China consumption & manufacturing'),market:'china',tier:'research',weights:{'CN:600519':.4,'CN:002594':.4,'CASH:USD':.2}},
 {id:'china-us',title:names('中国制造 × 美国科技','China manufacturing × US technology'),market:'china-us',tier:'research',weights:{'CN:002594':.25,'CN:600519':.25,'EQ:AAPL':.25,'EQ:MSFT':.25}},
 {id:'china-us-buffer',title:names('中美资产与现金缓冲','China / US & cash buffer'),market:'china-us',tier:'research',weights:{'CN:600519':.2,'CN:002594':.2,'EQ:MSFT':.2,'CASH:USD':.4}},
 {id:'crypto-us',title:names('比特币 × 美股科技','Bitcoin × US technology'),market:'crypto-us',tier:'research',weights:{'CB:BTC-USD':.2,'EQ:AAPL':.3,'EQ:MSFT':.3,'CASH:USD':.2}},
 {id:'crypto-us-balanced',title:names('加密资产与美股平衡','Crypto & US balanced'),market:'crypto-us',tier:'research',weights:{'CB:BTC-USD':.1,'CB:ETH-USD':.1,'TD:SPY':.5,'CASH:USD':.3}},
];
const allowed=(r,caps)=>caps.tier==='research'||caps.tier==='signal'&&r.tier==='signal';
export function portfolioCatalog(data,access){
 const caps=workspaceAccess(access);
 return {generatedAt:data.generatedAt,cutoff:data.cutoff,tier:caps.tier,maxDays:caps.portfolio.maxDays,recipes:recipes.map(r=>({...r,locked:!allowed(r,caps),assets:Object.keys(r.weights).filter(k=>k!=='CASH:USD').map(k=>({symbol:k,currency:data.assets[k]?.currency||null,from:data.assets[k]?.points?.[0]?.[0]||null,to:data.assets[k]?.points?.at(-1)?.[0]||null}))})),sources:data.sources,baseCurrency:'USD'};
}
const validDate=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&Number.isFinite(Date.parse(s))&&new Date(s).toISOString().slice(0,10)===s;
export function portfolioStudy(data,access,params){
 const caps=workspaceAccess(access),r=recipes.find(r=>r.id===params.recipe);
 if(!r)throw Object.assign(Error('unknown_recipe'),{status:400});
 if(!allowed(r,caps))throw Object.assign(Error('plan_required'),{status:403});
 if(!validDate(params.start)||!validDate(params.end)||params.start>=params.end||params.end>data.cutoff)throw Object.assign(Error('invalid_date_range'),{status:400});
 if((Date.parse(params.end)-Date.parse(params.start))/86400000>caps.portfolio.maxDays)throw Object.assign(Error('date_range_exceeds_plan'),{status:403});
 const keys=[...new Set([...Object.keys(r.weights).filter(k=>k!=='CASH:USD'),'TD:SPY'])],needsFx=keys.some(k=>data.assets[k]?.currency==='CNY');
 const fx=new Map(data.assets['FX:CNYUSD']?.points||[]),maps=Object.fromEntries(keys.map(k=>[k,new Map((data.assets[k]?.points||[]).filter(([d,v])=>validDate(d)&&Number.isFinite(v)&&v>0))]));
 const dates=[...maps['TD:SPY'].keys()].filter(d=>d>=params.start&&d<=params.end).sort(),common=dates.filter(d=>keys.every(k=>maps[k].has(d))&&(!needsFx||Number.isFinite(fx.get(d))&&fx.get(d)>0));
 const base={recipe:r,requestedStart:params.start,requestedEnd:params.end,baseCurrency:'USD',cutoff:data.cutoff,generatedAt:data.generatedAt,benchmark:'SPY price proxy, not a matched China/crypto sector benchmark',roundTripCostBps:20,missingReferenceDates:dates.length-common.length,referenceDates:dates.length,validatedAlpha:false,annualizedReturn:null,sources:Object.fromEntries([...keys,...(needsFx?['FX:CNYUSD']:[])].map(k=>[k,data.assets[k]?.sourceUrl||null]))};
 if(common.length<10)return {...base,state:'insufficient_data',points:[],missingAssets:keys.filter(k=>!maps[k].size),fxAvailable:!needsFx||fx.size>0,observations:common.length};
 const price=(k,d)=>maps[k].get(d)/(data.assets[k].currency==='CNY'?fx.get(d):1),initial=common[0],last=common.at(-1),cash=r.weights['CASH:USD']||0;let peak=100,maxdd=0;
 const points=common.map((d,i)=>{const risky=Object.entries(r.weights).filter(([k])=>k!=='CASH:USD').reduce((s,[k,w])=>s+w*price(k,d)/price(k,initial),0)*100;const nav=i===0?100:cash*100+risky*.999*(i===common.length-1?.999:1);peak=Math.max(peak,nav);const dd=(nav/peak-1)*100;maxdd=Math.min(maxdd,dd);return {date:d,nav,benchmark:maps['TD:SPY'].get(d)/maps['TD:SPY'].get(initial)*100,drawdown:dd};});
 const inputHash=createHash('sha256').update(JSON.stringify({weights:r.weights,start:params.start,end:params.end,costBps:20,rule:'common_dates_buy_hold_USD_v1',prices:common.map(d=>[d,...keys.map(k=>maps[k].get(d)),needsFx?fx.get(d):null])})).digest('hex');
 return {...base,state:'historical_valuation_not_execution_backtest',points,observations:points.length,start:initial,end:last,returnPercent:points.at(-1).nav-100,benchmarkReturnPercent:points.at(-1).benchmark-100,maxDrawdownPercent:maxdd,inputHash,rangeClipped:initial>params.start||last<params.end,calendarAlignment:'Common dated closes only; no interpolation. Market closes and FX fixing times are not simultaneous. Crypto weekend risk is omitted.',rebalancing:'none'};
}
