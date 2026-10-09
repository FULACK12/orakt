import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateDossier} from '../scripts/reviewed-dossier.mjs';
const id='dossier-BKNG-20260804-ed97bb00';
const file=p=>readFileSync(new URL('../'+p,import.meta.url));
const bytes=file(`private-data/company-dossiers/${id}.json`),receipt=file(`private-data/dossier-reviews/${id}.json`);
const d=JSON.parse(bytes),r=JSON.parse(file(`private-data/research-reports/${id}.json`)).report;
const chapters=Object.fromEntries(d.chapters.map(c=>[c.key,c]));
test('BKNG preserves nine bilingual chapters and research-only provenance',()=>{
 const v=validateDossier(d,r,bytes,receipt);
 assert.equal(v.chapters.length,9);assert.equal(v.periodEnd,'2026-06-30');assert.equal(v.asOf,'2026-08-04');
 assert.ok(v.createdAt>v.asOf);assert.equal(v.validatedAlpha,false);assert.equal(v.eligibleForPredictiveBacktest,false);
 assert.equal(v.review.humanAccepted,false);assert.equal(r.confidence,null);
 const inspect=value=>{if(typeof value==='string')assert.doesNotMatch(value,/[A-Z]:[\\/]|retainedModelAttempt|\[(quantity|amount|数量|数值|numeric value)\]/);else if(value&&typeof value==='object')for(const child of Object.values(value))inspect(child);};inspect(d);
});
test('BKNG paragraph references resolve to immutable original passages',()=>{
 for(const c of d.chapters){const refs=new Set(d.originalPassages[c.key].map(p=>p.id));
  for(const f of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'])for(const lang of ['zh','en'])
   for(const ref of c[f][lang].match(/PASSAGE:[a-f0-9]{16}/g)||[]){assert.ok(refs.has(ref));assert.ok(c.evidence_refs.includes(ref));}
 }
});
test('BKNG preserves transaction, split, litigation and factor boundaries in English',()=>{
 assert.match(chapters.business.analysis.en,/not ownership of all hotels/);
 assert.match(chapters.capital.analysis.en,/Remaining authorization is not repayment liquidity/);
 assert.match(chapters.valuation.analysis.en,/a split changes units/);
 assert.match(chapters.competition.analysis.en,/a liability remains recognized/);
 assert.match(chapters.factors.analysis.en,/not validated factors/);
 assert.match(chapters.factors.analysis.en,/Lack of hedge-accounting designation does not mean absence/);
 const en=JSON.parse(file(`private-data/report-translations/${id}.en.json`));
 assert.equal(en.thesis,chapters.conclusion.analysis.en);assert.equal(en.newsReport.narrative,chapters.financial.analysis.en);
 assert.equal(JSON.parse(file('snapshot/research-report-index.json')).reports.filter(r=>r.id===id).length,1);
 assert.ok(JSON.parse(file('snapshot/equity-report-catalog.json')).companies.find(c=>c.ticker==='BKNG').reportIds.includes(id));
});
