import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {gunzipSync} from 'node:zlib';
import {reportKind,reportHref,classifyReport} from '../app/report-taxonomy.mjs';
import {inventoryPage} from '../worker/report-inventory.mjs';
import reports from '../generated/private-reports.mjs';
import chains from '../generated/private-chain-index.mjs';
const read=p=>readFile(new URL('../'+p,import.meta.url),'utf8');
test('all retained report IDs are accounted for without counting narratives as historical periods',async()=>{
 const index=JSON.parse(await read('snapshot/research-report-index.json'));
 const historical=index.reports.filter(r=>reportKind(r)==='company_periodic'),legacy=index.reports.filter(r=>reportKind(r)==='evidence_research');
 assert.ok(historical.length>=11);assert.equal(legacy.length,403);assert.equal(historical.length+legacy.length,index.reports.length);
 for(const r of legacy){assert.ok(chains.some(c=>c.id===r.id&&c.fullReportAvailable));assert.match(reportHref(r),/^\/platform\/chains\?report=/);}
 for(const r of historical)assert.match(reportHref(r),/^\/platform\/research\?report=/);
});
test('reclassification preserves original narratives, dates and evidence in every packed report',async()=>{
 for(const [id,packed] of Object.entries(reports)){
  const original=JSON.parse(await read('private-data/research-reports/'+id+'.json')).report,current=JSON.parse(gunzipSync(Buffer.from(packed,'base64'))).report;
  for(const key of ['id','createdAt','dataCutoff','thesis','verdict','newsReport','chain','evidence','limitations','alternatives','nextData','scores','tradingScenario','canslim'])assert.deepEqual(current[key],original[key],id+' '+key);
  assert.equal(current.templateVersion,classifyReport(original).templateVersion);
 }
});
test('coverage is bounded and retains unknown A-share periods instead of manufacturing completion',async()=>{
 const data=JSON.parse(await read('private-data/company-report-inventory.json'));
 const page=inventoryPage(data,new URL('http://localhost/?page=NaN'));assert.equal(page.page,1);assert.equal(page.companies.length,25);assert.equal(page.complete,false);
 const apple=inventoryPage(data,new URL('http://localhost/?q=AAPL&market=us'));assert.equal(apple.companies[0].ticker,'AAPL');assert.ok(apple.companies[0].missingPeriods>0);
 const cn=inventoryPage(data,new URL('http://localhost/?market=china'));assert.ok(cn.companies.every(c=>c.indexedPeriods===null&&c.missingPeriods===null&&c.complete===false));
 const index=JSON.parse(await read('snapshot/research-report-index.json'));
 assert.equal(data.totals.publishedHistoricalVersions,index.reports.filter(r=>reportKind(r)==='company_periodic').length);assert.equal(data.totals.legacyResearchVersions,403);
 const amazon=data.companies.find(c=>c.market==='us'&&c.ticker==='AMZN');assert.ok(amazon.publishedPeriods>=1);assert.ok(amazon.missingPeriods>0);
});
test('full report mounts only after expansion and shares the same body renderer as company reports',async()=>{
 const detail=await read('app/EvidenceChains.tsx'),dashboard=await read('app/PilotDashboard.tsx');
 assert.doesNotMatch(detail,/onToggle/);assert.match(detail,/aria-expanded=\{expanded\}/);assert.match(detail,/expanded&&<div/);assert.match(detail,/renderReport\(r,language\)/);
 assert.match(dashboard,/renderReport=\{\(r,l\)=><FullResearchBody report=\{r\} language=\{l\}\/>/);assert.match(dashboard,/<FullResearchBody report=\{report\} language=\{language\}\/>/);
 assert.match(dashboard,/match&&!isCompanyReport\(match\)/);
});
