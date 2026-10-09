import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateDossier} from '../scripts/reviewed-dossier.mjs';
import {isSafeReportIdentifier} from '../scripts/report-identifier.mjs';
const id='dossier-BRK.B-20260810-a86f4de7';
const file=p=>readFileSync(new URL('../'+p,import.meta.url));
const bytes=file(`private-data/company-dossiers/${id}.json`),receipt=file(`private-data/dossier-reviews/${id}.json`);
const d=JSON.parse(bytes),r=JSON.parse(file(`private-data/research-reports/${id}.json`)).report;
const chapters=Object.fromEntries(d.chapters.map(c=>[c.key,c]));
test('class-share report identifiers allow BRK.B without permitting traversal',()=>{
 for(const value of [id,'local-707','dossier-AAPL-20091027-123456ab'])assert.equal(isSafeReportIdentifier(value),true);
 for(const value of ['..','../secret','dossier-BRK..B-20260810-a86f4de7','dossier-BRK.B-20260810-a86f4de7/secret','local-707.json','%2e%2e','x?y','x#y','C:\\secret',null])assert.equal(isSafeReportIdentifier(value),false);
});
test('BRK.B nine bilingual chapters retain descriptive-only review and actual timestamps',()=>{
 const v=validateDossier(d,r,bytes,receipt);
 assert.equal(v.chapters.length,9);assert.equal(v.periodEnd,'2026-06-30');assert.equal(v.asOf,'2026-08-10');
 assert.ok(v.createdAt>v.asOf);assert.equal(v.validatedAlpha,false);assert.equal(v.eligibleForPredictiveBacktest,false);
 assert.equal(v.review.humanAccepted,false);assert.equal(r.confidence,null);
 const inspect=x=>{if(typeof x==='string')assert.doesNotMatch(x,/[A-Z]:[\\/]|retainedModelAttempt|\[(quantity|amount|value|year|数量|数值|numeric value)\]/);else if(x&&typeof x==='object')for(const child of Object.values(x))inspect(child);};inspect(d);
});
test('BRK.B references resolve to original frozen passages, not only a structural label',()=>{
 for(const c of d.chapters){const ids=new Set(d.originalPassages[c.key].map(p=>p.id));
  for(const f of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'])for(const lang of ['zh','en'])
   for(const ref of c[f][lang].match(/PASSAGE:[a-f0-9]{16}/g)||[]){assert.ok(ids.has(ref));assert.ok(c.evidence_refs.includes(ref));}
 }
});
test('BRK.B bilingual projections preserve entity, accounting and FX direction boundaries',()=>{
 assert.match(chapters.business.analysis.en,/rail-cargo category/);
 assert.match(chapters.financial.analysis.en,/not reporting adoption/);
 assert.match(chapters.capital.analysis.en,/does not guarantee BHE, BNSF/);
 assert.match(chapters.macro.analysis.en,/reduces the dollar liability and creates an exchange gain/);
 assert.match(chapters.valuation.analysis.en,/proportionate share of Occidental equity/);
 assert.match(chapters.conclusion.analysis.en,/not a buy recommendation or validated Alpha/);
 const en=JSON.parse(file(`private-data/report-translations/${id}.en.json`));
 assert.equal(en.thesis,chapters.conclusion.analysis.en);assert.equal(en.newsReport.narrative,chapters.financial.analysis.en);
 assert.equal(JSON.parse(file('snapshot/research-report-index.json')).reports.filter(r=>r.id===id).length,1);
 assert.ok(JSON.parse(file('snapshot/equity-report-catalog.json')).companies.find(c=>c.ticker==='BRK.B').reportIds.includes(id));
});
