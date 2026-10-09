import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateDossier} from '../scripts/reviewed-dossier.mjs';
const id='dossier-META-20260730-1fe49853';
const read=p=>JSON.parse(readFileSync(new URL('../'+p,import.meta.url)));
test('META reviewed source, bilingual scope and explicit limitations remain intact',()=>{
 const raw=readFileSync(new URL('../private-data/company-dossiers/'+id+'.json',import.meta.url));
 const d=JSON.parse(raw),r=read('private-data/research-reports/'+id+'.json').report;
 assert.doesNotThrow(()=>validateDossier(d,r,raw,readFileSync(new URL('../private-data/dossier-reviews/'+id+'.json',import.meta.url))));
 assert.equal(d.periodEnd,'2026-06-30');assert.equal(d.asOf,'2026-07-30');assert.equal(d.chapters.length,9);
 assert.equal(d.review.humanAccepted,false);assert.equal(d.validatedAlpha,false);assert.equal(d.eligibleForPredictiveBacktest,false);assert.equal(r.confidence,null);
 for(const c of d.chapters)for(const f of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan']){
  assert.match(c[f].zh,/[\u4e00-\u9fff]/);assert.doesNotMatch(c[f].en,/[\u4e00-\u9fff]/);assert.match(c[f].en,/PASSAGE:/);
 }
 const chapter=k=>d.chapters.find(c=>c.key===k);
 assert.match(chapter('capital').analysis.en,/no common-share repurchases/);
 assert.match(chapter('valuation').analysis.en,/two-class method/);
 assert.match(chapter('supply').analysis.en,/concentrated in Asia/);
 assert.match(chapter('financial').analysis.en,/quarterly revenue rises/);
 assert.match(chapter('factors').analysis.en,/does not by itself establish overstated/);
 assert.ok(read('snapshot/equity-report-catalog.json').companies.find(c=>c.ticker==='META').reportIds.includes(id));
 assert.match(read('private-data/report-translations/'+id+'.en.json').thesis,/quarterly FoA operating income falls/i);
});
