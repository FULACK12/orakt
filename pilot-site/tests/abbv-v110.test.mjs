import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateDossier} from '../scripts/reviewed-dossier.mjs';
const id='dossier-ABBV-20260803-cc3ee0b7';
const file=p=>readFileSync(new URL('../'+p,import.meta.url));
const bytes=file(`private-data/company-dossiers/${id}.json`);
const receipt=file(`private-data/dossier-reviews/${id}.json`);
const d=JSON.parse(bytes),r=JSON.parse(file(`private-data/research-reports/${id}.json`)).report;
const chapters=Object.fromEntries(d.chapters.map(c=>[c.key,c]));
test('ABBV complete bilingual research retains dates and unvalidated investment status',()=>{
 const v=validateDossier(d,r,bytes,receipt);
 assert.equal(v.chapters.length,9);assert.equal(v.periodEnd,'2026-06-30');assert.equal(v.asOf,'2026-08-03');
 assert.ok(v.createdAt>v.asOf);assert.equal(v.validatedAlpha,false);assert.equal(v.eligibleForPredictiveBacktest,false);
 assert.equal(v.review.humanAccepted,false);assert.equal(r.confidence,null);
 assert.doesNotMatch(bytes.toString(),/[A-Z]:\\|retainedModelAttempt|\[(quantity|amount|数量|数值)\]/);
});
test('ABBV paragraph references resolve in both languages',()=>{
 for(const c of d.chapters){
  const refs=new Set(d.originalPassages[c.key].map(p=>p.id));
  for(const field of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'])
   for(const lang of ['zh','en'])for(const ref of c[field][lang].match(/PASSAGE:[a-f0-9]{16}/g)||[]){
    assert.ok(refs.has(ref));assert.ok(c.evidence_refs.includes(ref));
   }
 }
});
test('ABBV accounting corrections and English projection are preserved',()=>{
 assert.match(chapters.financial.analysis.en,/Comprehensive income also rises/);
 assert.match(chapters.competition.analysis.en,/belongs to Nimble, not Apogee/);
 assert.match(chapters.valuation.analysis.en,/two-class is not a two-stage/);
 assert.match(chapters.factors.analysis.en,/No validated Alpha/);
 const index=JSON.parse(file('snapshot/research-report-index.json'));
 assert.equal(index.reports.filter(r=>r.id===id).length,1);
 assert.ok(JSON.parse(file('snapshot/equity-report-catalog.json')).companies.find(c=>c.ticker==='ABBV').reportIds.includes(id));
 const en=JSON.parse(file(`private-data/report-translations/${id}.en.json`));
 assert.equal(en.thesis,chapters.conclusion.analysis.en);
 assert.equal(en.newsReport.narrative,chapters.financial.analysis.en);
});
