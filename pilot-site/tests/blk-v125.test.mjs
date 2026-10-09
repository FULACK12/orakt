import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateDossier} from '../scripts/reviewed-dossier.mjs';
const id='dossier-BLK-20260806-9b76670a';
const file=p=>readFileSync(new URL('../'+p,import.meta.url));
const bytes=file(`private-data/company-dossiers/${id}.json`),receipt=file(`private-data/dossier-reviews/${id}.json`);
const d=JSON.parse(bytes),r=JSON.parse(file(`private-data/research-reports/${id}.json`)).report;
const chapters=Object.fromEntries(d.chapters.map(c=>[c.key,c]));
test('BLK retains nine bilingual chapters and research-only provenance',()=>{
 const v=validateDossier(d,r,bytes,receipt);
 assert.equal(v.chapters.length,9);assert.equal(v.periodEnd,'2026-06-30');assert.equal(v.asOf,'2026-08-06');
 assert.ok(v.createdAt>v.asOf);assert.equal(v.validatedAlpha,false);assert.equal(v.eligibleForPredictiveBacktest,false);
 assert.equal(v.review.humanAccepted,false);assert.equal(r.confidence,null);
 const inspect=x=>{if(typeof x==='string')assert.doesNotMatch(x,/[A-Z]:[\\/]|retainedModelAttempt|\[(quantity|amount|数量|数值|numeric value)\]/);else if(x&&typeof x==='object')for(const child of Object.values(x))inspect(child);};inspect(d);
});
test('BLK paragraph references resolve to frozen original evidence',()=>{
 for(const c of d.chapters){const ids=new Set(d.originalPassages[c.key].map(p=>p.id));
  for(const f of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'])for(const lang of ['zh','en'])
   for(const ref of c[f][lang].match(/PASSAGE:[a-f0-9]{16}/g)||[]){assert.ok(ids.has(ref));assert.ok(c.evidence_refs.includes(ref));}
 }
});
test('BLK English preserves cash, buyback, acquisition and candidate-factor scope',()=>{
 assert.match(chapters.capital.analysis.en,/does not replace statutory statements/);
 assert.match(chapters.financial.analysis.en,/half-year contingent-consideration fair-value change reduces expense/);
 assert.match(chapters.valuation.analysis.en,/remaining capacity are disclosed/);
 assert.match(chapters.factors.analysis.en,/not validated excess-return factors/);
 assert.match(chapters.supply.analysis.en,/Preqin technology assets/);
 const en=JSON.parse(file(`private-data/report-translations/${id}.en.json`));
 assert.equal(en.thesis,chapters.conclusion.analysis.en);assert.equal(en.newsReport.narrative,chapters.financial.analysis.en);
 assert.equal(JSON.parse(file('snapshot/research-report-index.json')).reports.filter(r=>r.id===id).length,1);
 assert.ok(JSON.parse(file('snapshot/equity-report-catalog.json')).companies.find(c=>c.ticker==='BLK').reportIds.includes(id));
});
