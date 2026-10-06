import {createHash} from 'node:crypto';
const horizons=[5,10,20];
const near=(a,b)=>a===b||(typeof a==='number'&&typeof b==='number'&&Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<1e-9);
const same=(a,b)=>{if(typeof a==='number'||typeof b==='number')return near(a,b);if(!a||!b||typeof a!=='object'||typeof b!=='object')return a===b;return JSON.stringify(Object.keys(a).sort())===JSON.stringify(Object.keys(b).sort())&&Object.keys(a).every(k=>same(a[k],b[k]));};
const day=s=>{if(typeof s!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(s)||!Number.isFinite(Date.parse(s))||new Date(s).toISOString().slice(0,10)!==s)throw Error('Invalid study date');return Date.parse(s)/86400000;};
export function replayFactor(events,prices,evaluationEnd){
 const calendar=Object.keys(prices['TD:SPY']||{}).filter(d=>d<=evaluationEnd).sort(),rows=[],lastExit={};
 for(const e of [...events].sort((a,b)=>a.filedAt.localeCompare(b.filedAt)||a.accession.localeCompare(b.accession)))for(const h of horizons){
  const row={accession:e.accession,filedAt:e.filedAt,horizon:h,signal:null,state:'financial_inputs_missing',strategyReturn:null,marketExcess:null,industryExcess:null};rows.push(row);
  const s=e.summary||{};if(s.revenueYoYPercent==null||s.grossMarginYoYPoints==null)continue;
  row.signal=s.revenueYoYPercent>0&&s.grossMarginYoYPoints>0;
  if(!row.signal){row.state='no_signal';continue;}
  const pos=calendar.findIndex(d=>d>e.filedAt);
  if(pos<0||pos+h>=calendar.length){row.state='outcome_window_incomplete';continue;}
  const entry=calendar[pos],exit=calendar[pos+h];Object.assign(row,{entryDate:entry,exitDate:exit});
  if(entry<=(lastExit[h]||'')){row.state='overlap_excluded';continue;}
  const window=calendar.slice(pos,pos+h+1);
  const ret=id=>{const p=prices[id]||{};return window.some(d=>typeof p[d]!=='number'||!Number.isFinite(p[d])||p[d]<=0)?null:p[exit]/p[entry]-1;};
  const stock=ret('EQ:AMD'),market=ret('TD:SPY'),industry=ret('TD:SOXX');
  if(stock===null||market===null){row.state='price_window_missing';continue;}
  lastExit[h]=exit;const strategy=stock-.0025;
  Object.assign(row,{strategyReturn:strategy,marketReturn:market,industryReturn:industry,marketExcess:strategy-market,industryExcess:industry===null?null:strategy-industry,state:industry===null?'industry_benchmark_missing':'diagnostic_only'});
 }
 const groups=horizons.map(h=>{const eligible=rows.filter(r=>r.horizon===h&&r.strategyReturn!==null),dual=eligible.filter(r=>r.industryExcess!==null);return {horizon:h,pricedIndependentEvents:eligible.length,dualBenchmarkEvents:dual.length,meanMarketExcess:eligible.length?eligible.reduce((s,r)=>s+r.marketExcess,0)/eligible.length:null,meanIndustryExcess:dual.length?dual.reduce((s,r)=>s+r.industryExcess,0)/dual.length:null,confidenceInterval:null,validatedAlpha:false};});
 return {rows,groups,status:'not_validated',confidenceIntervalStatus:'not_estimated_in_exploratory_pilot',prospectiveValidation:false};
}
function checkSummary(summary,record,cutoff){
 const metrics=summary.metrics;
 for(const f of Object.values(metrics))if(f){
  if(f.unit!=='USD'||Object.keys(f.dimensions||{}).length||f.period_end!==record.periodEnd||f.filed_at!==record.filedAt||f.filed_at>cutoff||!f.source_url?.startsWith(record.sourceUrl+'#')||!Number.isFinite(Number(f.value)))throw Error('Peer fact scope mismatch');
  const duration=day(f.period_end)-day(f.period_start)+1;if(duration<70||duration>110)throw Error('Peer quarter duration mismatch');
 }
 const revenue=metrics.revenue,gross=metrics.grossProfit;
 const margin=revenue&&gross&&revenue.period_start===gross.period_start&&Number(revenue.value)>0?Number(gross.value)/Number(revenue.value)*100:null;
 if(!near(summary.grossMarginPercent,margin))throw Error('Gross margin arithmetic mismatch');
 const find=f=>f?(summary.comparisons||[]).find(c=>c.current.evidence_id===f.evidence_id):null;
 const r=find(revenue),g=find(gross);
 for(const c of summary.comparisons||[]){
  if(c.periodType!=='quarter'||c.current.period_end!==record.periodEnd||c.current.source_url.split('#')[0]!==record.sourceUrl||c.previous.source_url.split('#')[0]!==record.sourceUrl)throw Error('Comparison scope mismatch');
  if(!Object.values(metrics).some(f=>same(f,c.current)))throw Error('Comparison does not match shown metric');
  if(c.previous.filed_at!==record.filedAt||c.previous.unit!=='USD'||Object.keys(c.previous.dimensions||{}).length)throw Error('Prior fact scope mismatch');
  const d=day(c.current.period_end)-day(c.previous.period_end),start=day(c.current.period_start)-day(c.previous.period_start);
  if(d<350||d>380||start<350||start>380||Math.abs(d-start)>14)throw Error('Comparison year mismatch');
 }
 const yoy=r&&Number(r.previous.value)>0?(Number(r.current.value)/Number(r.previous.value)-1)*100:null;
 const change=margin!==null&&r&&g&&r.previous.period_start===g.previous.period_start&&r.previous.period_end===g.previous.period_end&&Number(r.previous.value)>0?margin-Number(g.previous.value)/Number(r.previous.value)*100:null;
 if(!near(summary.revenueYoYPercent,yoy)||!near(summary.grossMarginYoYPoints,change))throw Error('Factor input arithmetic mismatch');
}
export function validatePeerStudy(data,report,dossier,inputBytes){
 if(data.ticker!=='AMD'||data.ticker!==report.ticker||data.asOf!==report.dataCutoff||data.periodEnd!==dossier.periodEnd||data.reportRevisionHash!==dossier.review.assistantRevisionHash||data.changesReportConfidence!==false||data.rankingEligible!==false)throw Error('Peer study identity mismatch');
 if(createHash('sha256').update(inputBytes).digest('hex')!==data.factor.inputFingerprint)throw Error('Factor input hash mismatch');
 const input=JSON.parse(inputBytes.toString('utf8')),f=data.factor,p=f.policy;
 if(p.id!=='quarter-growth-margin/v1'||p.roundTripCostBps!==25||p.position!=='long_only'||p.mode!=='retrospective_diagnostic'||p.prospective!==false||p.minimumIndependentEvents!==20||p.industryBenchmark!=='TD:SOXX'||p.marketBenchmark!=='TD:SPY'||p.formula!=='revenue_yoy > 0 AND gross_margin_yoy_pp > 0'||!same(p.horizons,horizons)||!same(input.policy,p)||!same(input.events,f.events)||input.evaluationEnd!==f.evaluationEnd)throw Error('Frozen factor protocol mismatch');
 day(data.asOf);day(f.evaluationEnd);
 if(new Set(f.events.map(e=>e.accession)).size!==f.events.length)throw Error('Duplicate filing events');
 for(const e of [...data.peers,...f.events]){
  if(e.filedAt){day(e.filedAt);if(e.filedAt>data.asOf||day(e.periodEnd)>day(e.filedAt))throw Error('Future filing input');}
  if(e.rankingEligible===true)throw Error('Automatic peer ranking forbidden');
  if(e.summary)checkSummary(e.summary,e,data.asOf);
 }
 const subject=data.peers.find(e=>e.ticker===data.ticker),start=subject?.summary?.metrics.revenue?.period_start;
 if(subject?.sourceDocumentHash!==dossier.provenance.sourceDocumentHash)throw Error('Subject filing mismatch');
 for(const e of data.peers)if(e.summary){const r=e.summary.metrics.revenue,aligned=!!(r&&start&&Math.abs(day(e.periodEnd)-day(data.periodEnd))<=14&&Math.abs(day(r.period_start)-day(start))<=14);if(e.calendarAligned!==aligned)throw Error('Peer calendar alignment mismatch');}
 const actual=replayFactor(f.events,input.prices,f.evaluationEnd);
 for(const k of Object.keys(actual))if(!same(actual[k],f[k]))throw Error('Factor replay differs from published result');
 return data;
}
