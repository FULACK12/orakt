import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateDossier} from '../scripts/reviewed-dossier.mjs';
const id='dossier-AMZN-20260731-a766a6bf';
const read=p=>JSON.parse(readFileSync(new URL('../'+p,import.meta.url)));
const raw=readFileSync(new URL('../private-data/company-dossiers/'+id+'.json',import.meta.url));
const d=JSON.parse(raw),r=read('private-data/research-reports/'+id+'.json').report;
test('AMZN full report keeps periods, evidence hashes, bilingual content and explicit limitations',()=>{
 assert.doesNotThrow(()=>validateDossier(d,r,raw,readFileSync(new URL('../private-data/dossier-reviews/'+id+'.json',import.meta.url))));
 assert.equal(d.periodEnd,'2026-06-30');assert.equal(d.asOf,'2026-07-31');
 assert.equal(d.chapters.length,9);assert.equal(d.review.humanAccepted,false);
 assert.equal(d.eligibleForPredictiveBacktest,false);assert.equal(d.validatedAlpha,false);assert.equal(r.confidence,null);
 assert.equal(d.cashBridge.state,'unavailable'); // Do not manufacture a matched cash period or FX residual.
 for(const c of d.chapters)for(const field of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan']){
  assert.match(c[field].zh,/[\u4e00-\u9fff]/);assert.doesNotMatch(c[field].en,/[\u4e00-\u9fff]/);
  assert.match(c[field].en,/PASSAGE:/);assert.doesNotMatch(c[field].zh,/\[数值\]/);
 }
 assert.match(d.chapters.find(c=>c.key==='financial').analysis.en,/rolling window is neither the half-year nor a fiscal year/);
 assert.match(d.chapters.find(c=>c.key==='valuation').analysis.en,/treasury-stock method/);
 assert.match(d.chapters.find(c=>c.key==='macro').analysis.en,/did not significantly affect consolidated quarterly net sales/);
 assert.match(read('private-data/report-translations/'+id+'.en.json').thesis,/investment/);
 assert.ok(read('snapshot/equity-report-catalog.json').companies.find(c=>c.ticker==='AMZN').reportIds.includes(id));
});
