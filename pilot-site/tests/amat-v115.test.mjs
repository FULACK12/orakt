import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateDossier} from '../scripts/reviewed-dossier.mjs';
const id='dossier-AMAT-20260820-e49b9fc6';
const file=p=>readFileSync(new URL('../'+p,import.meta.url));
const bytes=file(`private-data/company-dossiers/${id}.json`),receipt=file(`private-data/dossier-reviews/${id}.json`);
const d=JSON.parse(bytes),r=JSON.parse(file(`private-data/research-reports/${id}.json`)).report;
const chapters=Object.fromEntries(d.chapters.map(c=>[c.key,c]));
test('AMAT complete bilingual research keeps generation date and unvalidated status',()=>{
 const v=validateDossier(d,r,bytes,receipt);
 assert.equal(v.chapters.length,9);assert.equal(v.periodEnd,'2026-07-26');assert.equal(v.asOf,'2026-08-20');
 assert.ok(v.createdAt>v.asOf);assert.equal(v.validatedAlpha,false);assert.equal(v.eligibleForPredictiveBacktest,false);
 assert.equal(v.review.humanAccepted,false);assert.equal(r.confidence,null);
 assert.doesNotMatch(bytes.toString(),/[A-Z]:\\|retainedModelAttempt|\[(quantity|amount|数量|数值|numeric value)\]/);
});
test('AMAT paragraph citations resolve to retained original passages',()=>{
 for(const c of d.chapters){
  const refs=new Set(d.originalPassages[c.key].map(p=>p.id));
  for(const f of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'])
   for(const lang of ['zh','en'])for(const ref of c[f][lang].match(/PASSAGE:[a-f0-9]{16}/g)||[]){
    assert.ok(refs.has(ref));assert.ok(c.evidence_refs.includes(ref));
   }
 }
});
test('AMAT cash/debt/recognition corrections and English projection survive export',()=>{
 assert.match(chapters.capital.analysis.en,/below opening cash/);
 assert.match(chapters.macro.analysis.en,/not that commercial paper and senior notes are absent/);
 assert.match(chapters.conclusion.analysis.en,/not wholly over-time revenue/);
 assert.match(chapters.factors.analysis.en,/not a historical signal/);
 assert.equal(JSON.parse(file('snapshot/research-report-index.json')).reports.filter(r=>r.id===id).length,1);
 assert.ok(JSON.parse(file('snapshot/equity-report-catalog.json')).companies.find(c=>c.ticker==='AMAT').reportIds.includes(id));
 const en=JSON.parse(file(`private-data/report-translations/${id}.en.json`));
 assert.equal(en.thesis,chapters.conclusion.analysis.en);assert.equal(en.newsReport.narrative,chapters.financial.analysis.en);
});
