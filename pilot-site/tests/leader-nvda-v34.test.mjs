import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateDossier} from '../scripts/reviewed-dossier.mjs';
const id='dossier-NVDA-20260826-da949048';
const raw=readFileSync(new URL('../private-data/company-dossiers/'+id+'.json',import.meta.url));
const read=p=>JSON.parse(readFileSync(new URL('../'+p,import.meta.url)));
const d=JSON.parse(raw),r=read('private-data/research-reports/'+id+'.json').report;
test('new leader report remains bilingual, reviewed and research-only',()=>{
 assert.doesNotThrow(()=>validateDossier(d,r,raw,readFileSync(new URL('../private-data/dossier-reviews/'+id+'.json',import.meta.url))));
 assert.equal(d.chapters.length,9);assert.equal(d.periodEnd,'2026-07-26');assert.equal(d.asOf,'2026-08-26');
 assert.equal(d.review.humanAccepted,false);assert.equal(d.review.independentVerification,false);
 assert.equal(d.eligibleForPredictiveBacktest,false);assert.equal(d.validatedAlpha,false);assert.equal(r.confidence,null);
 for(const c of d.chapters)for(const k of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan']){
  assert.match(c[k].zh,/[\u4e00-\u9fff]/);assert.doesNotMatch(c[k].en,/[\u4e00-\u9fff]/);
 }
 const en=read('private-data/report-translations/'+id+'.en.json');assert.match(en.thesis,/Data Center/);
 assert.ok(read('snapshot/research-report-index.json').reports.some(x=>x.id===id));
 assert.ok(read('snapshot/equity-report-catalog.json').companies.find(x=>x.ticker==='NVDA').reportIds.includes(id));
});
