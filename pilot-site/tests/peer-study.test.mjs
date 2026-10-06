import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validatePeerStudy,replayFactor} from '../scripts/peer-study.mjs';
const root=new URL('../',import.meta.url),id='dossier-AMD-20250507';
const read=p=>JSON.parse(readFileSync(new URL(p,root),'utf8'));
const d=read(`private-data/peer-studies/${id}.json`),bytes=readFileSync(new URL(`private-data/peer-studies/${id}.inputs.json`,root));
const report=read(`private-data/research-reports/${id}.json`).report,dossier=read(`private-data/company-dossiers/${id}.json`);
test('original-source peers and retrospective factor replay agree across Python and JavaScript',()=>{
 assert.equal(validatePeerStudy(d,report,dossier,bytes).peers.length,5);
 assert.equal(d.peers.find(x=>x.ticker==='NVDA').summary.metrics.revenue,null);
 assert.equal(d.peers.find(x=>x.ticker==='AVGO').calendarAligned,false);
 assert.equal(d.peers.find(x=>x.ticker==='QCOM').summary.metrics.operatingCashFlow,null);
 assert.equal(d.factor.events.length,7);
 for(const g of d.factor.groups){assert.equal(g.dualBenchmarkEvents,5);assert.equal(g.validatedAlpha,false);assert.equal(g.confidenceInterval,null);}
 assert.equal(d.factor.rows.filter(r=>r.state==='no_signal').length,6);
});
test('tampered amounts, windows, claims, hashes and peer ranking fail closed',()=>{
 for(const alter of [x=>x.asOf='2025-06-01',x=>x.peers[0].summary.metrics.revenue.value='1',x=>x.peers[0].filedAt='2026-01-01',x=>x.peers[3].rankingEligible=true,x=>x.peers[4].calendarAligned=true,x=>x.factor.groups[0].meanIndustryExcess=100,x=>x.factor.groups[0].validatedAlpha=true,x=>x.factor.groups[0].confidenceInterval=[1,2],x=>x.factor.rows[6].entryDate=x.factor.rows[6].filedAt,x=>x.factor.policy.roundTripCostBps=0,x=>x.factor.inputFingerprint='a'.repeat(64)]){
  const changed=structuredClone(d);alter(changed);assert.throws(()=>validatePeerStudy(changed,report,dossier,bytes));
 }
});
test('missing benchmark never turns into a zero-return benchmark or an independent observation',()=>{
 const input=JSON.parse(bytes);delete input.prices['TD:SOXX'];
 const r=replayFactor(input.events,input.prices,input.evaluationEnd);
 assert.equal(r.groups[0].dualBenchmarkEvents,0);assert.equal(r.groups[0].meanIndustryExcess,null);
 assert.equal(r.rows.find(x=>x.signal).state,'industry_benchmark_missing');
});
