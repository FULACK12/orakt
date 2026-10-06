import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
import {validateCompletion} from '../scripts/research-completion.mjs';
const input=JSON.parse(readFileSync(new URL('../private-data/research-completions/local-707.json',import.meta.url),'utf8'));
const report={ticker:'AAPL',dataCutoff:'2025-08-01'};
test('cash bridge reconciles and cross-company records never become approved peer ranks',()=>{
 const r=validateCompletion(input,report);assert.equal(r.cashFlowBridge.rows.length,10);assert.equal(r.comparators.length,4);
 assert.equal(r.comparators.find(c=>c.ticker==='MSFT').status,'quarter_metrics_derived_verified');
});
test('quarter derivation rejects altered amounts, units, fiscal starts and official cross-check',()=>{
 for(const mutate of [f=>f.derivation.operands[0].value='2',f=>f.derivation.operands[1].unit='EUR',f=>f.derivation.operands[1].period_start='2024-01-01',f=>f.derivation.crossCheck.reportedValue='1',f=>f.derivation.operands[0].issuer='NVDA']){const d=structuredClone(input);mutate(d.comparators.find(c=>c.ticker==='MSFT').metrics[0]);assert.throws(()=>validateCompletion(d,report));}
});
test('bridge rejects sign, period, missing, duplicate, future, total and eligibility changes',()=>{
 for(const mutate of [d=>d.cashFlowBridge.rows[0].sign=-1,d=>d.cashFlowBridge.rows[0].facts[0].period_start='2025-03-30',d=>d.cashFlowBridge.rows[0].current=null,d=>d.cashFlowBridge.rows.push(d.cashFlowBridge.rows[0]),d=>d.comparators[0].filedAt='2025-08-02',d=>d.cashFlowBridge.totals[0].value='1',d=>d.comparators[0].rankingEligible=true]){const d=structuredClone(input);mutate(d);assert.throws(()=>validateCompletion(d,report));}
});
