import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateDossier} from '../scripts/reviewed-dossier.mjs';
const id='dossier-TSLA-20260723-d2b3aa51';
const file=p=>readFileSync(new URL('../'+p,import.meta.url));
const bytes=file(`private-data/company-dossiers/${id}.json`);
const receipt=file(`private-data/dossier-reviews/${id}.json`);
const d=JSON.parse(bytes),r=JSON.parse(file(`private-data/research-reports/${id}.json`)).report;
const chapters=Object.fromEntries(d.chapters.map(c=>[c.key,c]));

test('TSLA complete bilingual descriptive research preserves dates and eligibility',()=>{
 const v=validateDossier(d,r,bytes,receipt);
 assert.equal(v.chapters.length,9);assert.equal(v.periodEnd,'2026-06-30');assert.equal(v.asOf,'2026-07-23');
 assert.ok(v.createdAt>v.asOf);assert.equal(v.validatedAlpha,false);assert.equal(v.eligibleForPredictiveBacktest,false);
 assert.equal(v.review.humanAccepted,false);assert.equal(r.confidence,null);
 assert.doesNotMatch(bytes.toString(),/[A-Z]:\\|retainedModelAttempt/);
});
test('TSLA additive original context and both-language paragraph citations resolve',()=>{
 for(const c of d.chapters){
  const refs=new Set(d.originalPassages[c.key].map(p=>p.id));
  for(const field of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'])
   for(const lang of ['zh','en'])for(const ref of c[field][lang].match(/PASSAGE:[a-f0-9]{16}/g)||[]){
    assert.ok(refs.has(ref));assert.ok(c.evidence_refs.includes(ref));
   }
 }
 const macro=d.originalPassages.macro.map(p=>p.text).join('\n');
 assert.match(macro,/did not elect the practical expedient/);assert.match(macro,/adoption has no impact/);
 const value=d.originalPassages.valuation.map(p=>p.text).join('\n');
 assert.match(value,/Total \$ 33,857 \$ 2,545 \$ 31,312 \$ —/);
});
test('TSLA corrected scope, faithful English and once-only discoverability',()=>{
 assert.match(chapters.macro.analysis.en,/environmental-credit standard remains under evaluation/);
 assert.match(chapters.valuation.analysis.en,/not a Tesla stock-price target framework/);
 assert.match(chapters.conclusion.analysis.en,/changeovers in the prior period/);
 assert.match(chapters.factors.validationPlan.en,/multiple-testing controls/);
 const index=JSON.parse(file('snapshot/research-report-index.json'));
 assert.equal(index.reports.filter(r=>r.id===id).length,1);
 const company=JSON.parse(file('snapshot/equity-report-catalog.json')).companies.find(c=>c.ticker==='TSLA');
 assert.ok(company.reportIds.includes(id));
 const en=JSON.parse(file(`private-data/report-translations/${id}.en.json`));
 assert.equal(en.thesis,chapters.conclusion.analysis.en);
});
