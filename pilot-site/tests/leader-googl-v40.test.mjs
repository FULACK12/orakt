import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateDossier} from '../scripts/reviewed-dossier.mjs';
const id='dossier-GOOGL-20260723-89aae521';
const read=p=>JSON.parse(readFileSync(new URL('../'+p,import.meta.url)));

test('Google reviewed bilingual chapters preserve accounting and validation boundaries',()=>{
 const raw=readFileSync(new URL('../private-data/company-dossiers/'+id+'.json',import.meta.url));
 const d=JSON.parse(raw),r=read('private-data/research-reports/'+id+'.json').report;
 assert.doesNotThrow(()=>validateDossier(d,r,raw,readFileSync(new URL('../private-data/dossier-reviews/'+id+'.json',import.meta.url))));
 assert.equal(d.periodEnd,'2026-06-30');assert.equal(d.asOf,'2026-07-23');assert.equal(d.chapters.length,9);
 assert.equal(d.review.humanAccepted,false);assert.equal(d.review.independentVerification,false);
 assert.equal(d.validatedAlpha,false);assert.equal(d.eligibleForPredictiveBacktest,false);assert.equal(r.confidence,null);
 for(const c of d.chapters)for(const f of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan']){
  assert.match(c[f].zh,/[\u4e00-\u9fff]/);assert.doesNotMatch(c[f].en,/[\u4e00-\u9fff]/);assert.match(c[f].en,/PASSAGE:/);
 }
 const c=k=>d.chapters.find(x=>x.key===k);
 assert.match(c('financial').analysis.en,/quarter and half-year columns are not interchangeable/);
 assert.match(c('financial').analysis.en,/Equity gains are non-operating, not automatically non-recurring/);
 assert.match(c('financial').analysis.en,/not yet adopted/);
 assert.match(c('capital').analysis.en,/authorization is not execution/);
 assert.match(c('macro').analysis.en,/Notional exposure is a potential maximum, not a realized loss/);
 assert.match(c('valuation').analysis.en,/preferred-dividend addback/);
 assert.match(c('factors').analysis.en,/TAC must not automatically become a Cloud gross-margin driver/);
 assert.match(c('factors').validationPlan.en,/broad-market and sector benchmarks/);
 assert.match(c('factors').validationPlan.en,/non-overlapping holding windows/i);
 assert.match(c('conclusion').analysis.en,/Cost dollars increase but their revenue share declines/);
 assert.match(c('conclusion').analysis.en,/quarterly revenue growth can coexist with a half-year decline/);
 assert.ok(read('snapshot/equity-report-catalog.json').companies.find(x=>x.ticker==='GOOGL').reportIds.includes(id));
 assert.match(read('private-data/report-translations/'+id+'.en.json').thesis,/investment gains/);
});
