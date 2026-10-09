import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateDossier} from '../scripts/reviewed-dossier.mjs';
const id='dossier-AMD-20260805-e812de14';
const read=p=>JSON.parse(readFileSync(new URL('../'+p,import.meta.url)));
test('AMD full bilingual report retains source review and correct accounting boundaries',()=>{
 const raw=readFileSync(new URL('../private-data/company-dossiers/'+id+'.json',import.meta.url));
 const d=JSON.parse(raw),r=read('private-data/research-reports/'+id+'.json').report;
 assert.doesNotThrow(()=>validateDossier(d,r,raw,readFileSync(new URL('../private-data/dossier-reviews/'+id+'.json',import.meta.url))));
 assert.equal(d.periodEnd,'2026-06-27');assert.equal(d.asOf,'2026-08-05');assert.equal(d.chapters.length,9);
 assert.equal(d.review.humanAccepted,false);assert.equal(d.validatedAlpha,false);assert.equal(d.eligibleForPredictiveBacktest,false);assert.equal(r.confidence,null);
 for(const c of d.chapters)for(const f of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan']){
  assert.match(c[f].zh,/[\u4e00-\u9fff]/);assert.doesNotMatch(c[f].en,/[\u4e00-\u9fff]/);assert.match(c[f].en,/PASSAGE:/);
 }
 const c=k=>d.chapters.find(x=>x.key===k);
 assert.match(c('valuation').analysis.en,/Retirement is not another current-quarter repurchase/);
 assert.match(c('financial').analysis.en,/Gaming revenue falls/);
 assert.match(c('capital').analysis.en,/no current debt\/commercial-paper issuance proceeds/);
 assert.match(c('supply').analysis.en,/Outsourcing does not eliminate/);
 assert.match(c('factors').analysis.en,/No independent global CAPEX/);
 assert.doesNotMatch(c('factors').counterEvidence.en,/Independent verification shows|8%|3nm/);
 assert.match(c('conclusion').analysis.en,/billing locations, not end users/);
 assert.ok(read('snapshot/equity-report-catalog.json').companies.find(x=>x.ticker==='AMD').reportIds.includes(id));
 assert.match(read('private-data/report-translations/'+id+'.en.json').thesis,/Gaming revenue declines/);
});
