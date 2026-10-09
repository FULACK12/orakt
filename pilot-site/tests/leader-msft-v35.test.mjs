import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateDossier} from '../scripts/reviewed-dossier.mjs';
const id='dossier-MSFT-20260729-e8b00c5f';
const read=p=>JSON.parse(readFileSync(new URL('../'+p,import.meta.url)));
const raw=readFileSync(new URL('../private-data/company-dossiers/'+id+'.json',import.meta.url));
const d=JSON.parse(raw),r=read('private-data/research-reports/'+id+'.json').report;
test('MSFT annual nine-chapter report retains reviewed provenance and research boundaries',()=>{
 assert.doesNotThrow(()=>validateDossier(d,r,raw,readFileSync(new URL('../private-data/dossier-reviews/'+id+'.json',import.meta.url))));
 assert.equal(d.periodEnd,'2026-06-30');assert.equal(d.asOf,'2026-07-29');
 assert.equal(d.chapters.length,9);assert.equal(d.review.humanAccepted,false);
 assert.equal(d.eligibleForPredictiveBacktest,false);assert.equal(d.validatedAlpha,false);assert.equal(r.confidence,null);
 for(const c of d.chapters)for(const key of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan']){
  assert.match(c[key].zh,/[\u4e00-\u9fff]/);assert.doesNotMatch(c[key].en,/[\u4e00-\u9fff]/);
  assert.doesNotMatch(c[key].zh,/\[数值\]/);assert.doesNotMatch(c[key].en,/\[numeric value\]/);
 }
 const b=d.cashBridge;assert.equal(b.state,'matched');assert.equal(Number(b.residual),0);
 assert.equal(Number(b.computedNetChange),-9307000000);assert.equal(b.periodType,'annual');
 assert.equal(Number(b.values.fx.value),-196000000);assert.match(b.values.fx.sourceConcepts[0],/DiscontinuedOperations$/);
 assert.match(d.chapters.find(c=>c.key==='financial').analysis.zh,/公司整体毛利率下降/);
 assert.match(read('private-data/report-translations/'+id+'.en.json').thesis,/Azure/);
 assert.ok(read('snapshot/equity-report-catalog.json').companies.find(c=>c.ticker==='MSFT').reportIds.includes(id));
});
