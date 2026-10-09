import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateDossier} from '../scripts/reviewed-dossier.mjs';
const id='dossier-AAPL-20091027-1fae6908';
const read=p=>JSON.parse(readFileSync(new URL('../'+p,import.meta.url)));
test('AAPL annual historical revision preserves cash, timing and factor boundaries',()=>{
 const raw=readFileSync(new URL('../private-data/company-dossiers/'+id+'.json',import.meta.url));
 const d=JSON.parse(raw),r=read('private-data/research-reports/'+id+'.json').report;
 assert.doesNotThrow(()=>validateDossier(d,r,raw,readFileSync(new URL('../private-data/dossier-reviews/'+id+'.json',import.meta.url))));
 assert.equal(d.periodEnd,'2009-09-26');assert.equal(d.asOf,'2009-10-27');assert.equal(d.chapters.length,9);
 assert.equal(d.review.humanAccepted,false);assert.equal(d.validatedAlpha,false);assert.equal(d.eligibleForPredictiveBacktest,false);assert.equal(r.confidence,null);
 for(const c of d.chapters)for(const f of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan']){
  assert.match(c[f].zh,/[\u4e00-\u9fff]/);assert.doesNotMatch(c[f].en,/[\u4e00-\u9fff]/);assert.match(c[f].en,/PASSAGE:/);
 }
 const c=k=>d.chapters.find(x=>x.key===k);
 assert.match(c('supply').analysis.en,/Retail coverage across markets describes distribution/);
 assert.match(c('competition').analysis.en,/masked model-input numbers are not missing disclosure/);
 assert.match(c('macro').analysis.en,/not an increase in cash equivalents alone/);
 assert.match(c('valuation').analysis.en,/not a customer subscription-renewal mechanism/);
 assert.match(c('factors').validationPlan.en,/non-overlapping windows/);
 assert.match(c('conclusion').analysis.en,/Cash equivalents decline/);
 assert.match(c('conclusion').analysis.en,/no outstanding debt/);
 assert.match(read('private-data/report-translations/'+id+'.en.json').thesis,/not completed independent causal validation/);
 assert.ok(read('snapshot/equity-report-catalog.json').companies.find(x=>x.ticker==='AAPL').reportIds.includes(id));
 const index=read('snapshot/research-report-index.json');assert.equal(index.reports.filter(x=>x.id===id).length,1);
});
