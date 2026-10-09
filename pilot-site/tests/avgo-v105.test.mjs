import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateDossier} from '../scripts/reviewed-dossier.mjs';
const id='dossier-AVGO-20260910-2a8072e9';
const file=p=>readFileSync(new URL('../'+p,import.meta.url));
const bytes=file(`private-data/company-dossiers/${id}.json`);
const receipt=file(`private-data/dossier-reviews/${id}.json`);
const d=JSON.parse(bytes), report=JSON.parse(file(`private-data/research-reports/${id}.json`)).report;
test('AVGO retained nine-chapter research passes publication contract without investment approval',()=>{
 const v=validateDossier(d,report,bytes,receipt);
 assert.equal(v.chapters.length,9);assert.equal(v.ticker,'AVGO');
 assert.equal(v.periodEnd,'2026-08-02');assert.equal(v.asOf,'2026-09-10');
 assert.ok(v.createdAt>v.asOf);assert.equal(v.validatedAlpha,false);
 assert.equal(v.eligibleForPredictiveBacktest,false);assert.equal(report.confidence,null);
 assert.equal(v.review.humanAccepted,false);
 assert.equal(v.financialLedger.comparisons.length,279);
 assert.doesNotMatch(bytes.toString(),/[A-Z]:\\|retainedModelAttempt/);
});
test('every revised bilingual paragraph citation resolves to exported source passage',()=>{
 for(const c of d.chapters){
  const refs=new Set(d.originalPassages[c.key].map(p=>p.id));
  for(const field of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'])
   for(const lang of ['zh','en'])
    for(const ref of c[field][lang].match(/PASSAGE:[a-f0-9]{16}/g)||[]){
     assert.ok(refs.has(ref),`${c.key}/${field}/${lang}: ${ref}`);
     assert.ok(c.evidence_refs.includes(ref));
    }
 }
 assert.ok(d.originalPassages.supply.some(p=>p.id==='PASSAGE:0e62d6d4e91063d9'));
});
test('AVGO publication is indexed once and has matching English research text',()=>{
 const index=JSON.parse(file('snapshot/research-report-index.json'));
 assert.equal(index.reports.filter(r=>r.id===id).length,1);
 const company=JSON.parse(file('snapshot/equity-report-catalog.json')).companies.find(c=>c.ticker==='AVGO');
 assert.ok(company.reportIds.includes(id));
 const en=JSON.parse(file(`private-data/report-translations/${id}.en.json`));
 assert.equal(en.thesis,d.chapters.find(c=>c.key==='conclusion').analysis.en);
 assert.match(d.chapters.find(c=>c.key==='competition').analysis.en,/falls for the quarter but rises cumulatively/);
 assert.match(d.chapters.find(c=>c.key==='valuation').analysis.en,/no target, entry range/);
});
