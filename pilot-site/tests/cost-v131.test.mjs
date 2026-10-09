import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateDossier} from '../scripts/reviewed-dossier.mjs';
const id='dossier-COST-20260603-0d4105f0';
const file=p=>readFileSync(new URL('../'+p,import.meta.url));
const bytes=file(`private-data/company-dossiers/${id}.json`);
const d=JSON.parse(bytes),r=JSON.parse(file(`private-data/research-reports/${id}.json`)).report;
const c=Object.fromEntries(d.chapters.map(c=>[c.key,c]));
test('COST nine bilingual chapters keep actual generation and research-only scope',()=>{
 const v=validateDossier(d,r,bytes,file(`private-data/dossier-reviews/${id}.json`));
 assert.equal(v.chapters.length,9);assert.equal(v.periodEnd,'2026-05-10');assert.equal(v.asOf,'2026-06-03');
 assert.ok(v.createdAt>v.asOf);assert.equal(v.validatedAlpha,false);assert.equal(v.eligibleForPredictiveBacktest,false);
 assert.equal(v.review.humanAccepted,false);assert.equal(r.confidence,null);
});
test('COST bound evidence and corrected timing/denominators survive projection',()=>{
 for(const ch of d.chapters){const ids=new Set(d.originalPassages[ch.key].map(p=>p.id));
  for(const f of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'])for(const lang of ['zh','en'])
   for(const ref of ch[f][lang].match(/PASSAGE:[a-f0-9]{16}/g)||[]){assert.ok(ids.has(ref));assert.ok(ch.evidence_refs.includes(ref));}
 }
 assert.match(c.financial.analysis.en,/cumulative reported ratio fell while the adjusted ratio rose/);
 assert.match(c.capital.analysis.en,/unpaid at period end/);
 assert.match(c.competition.analysis.en,/not a changed revenue-recognition policy/);
 assert.match(c.valuation.analysis.en,/buybacks do not guarantee falling period-end shares/);
 assert.match(c.factors.analysis.en,/not demonstrated stock excess returns/);
});
test('COST bilingual report and catalog refer to immutable reviewed dossier',()=>{
 const en=JSON.parse(file(`private-data/report-translations/${id}.en.json`));
 assert.equal(en.thesis,c.conclusion.analysis.en);assert.equal(en.newsReport.narrative,c.financial.analysis.en);
 assert.equal(JSON.parse(file('snapshot/research-report-index.json')).reports.filter(x=>x.id===id).length,1);
 assert.ok(JSON.parse(file('snapshot/equity-report-catalog.json')).companies.find(x=>x.ticker==='COST').reportIds.includes(id));
});
