import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateDossier} from '../scripts/reviewed-dossier.mjs';
const id='dossier-CL-20260731-6cc9a5a9';
const file=p=>readFileSync(new URL('../'+p,import.meta.url));
const bytes=file(`private-data/company-dossiers/${id}.json`);
const d=JSON.parse(bytes),r=JSON.parse(file(`private-data/research-reports/${id}.json`)).report;
const c=Object.fromEntries(d.chapters.map(c=>[c.key,c]));
test('CL nine bilingual chapters preserve cutoff and non-predictive review',()=>{
 const v=validateDossier(d,r,bytes,file(`private-data/dossier-reviews/${id}.json`));
 assert.equal(v.chapters.length,9);assert.equal(v.periodEnd,'2026-06-30');assert.equal(v.asOf,'2026-07-31');
 assert.ok(v.createdAt>v.asOf);assert.equal(v.validatedAlpha,false);assert.equal(v.eligibleForPredictiveBacktest,false);
 assert.equal(v.review.humanAccepted,false);assert.equal(r.confidence,null);
});
test('CL preserves evidence binding and key reviewed financial boundaries',()=>{
 for(const ch of d.chapters){const ids=new Set(d.originalPassages[ch.key].map(p=>p.id));
  for(const f of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'])for(const lang of ['zh','en'])
   for(const ref of ch[f][lang].match(/PASSAGE:[a-f0-9]{16}/g)||[]){assert.ok(ids.has(ref));assert.ok(ch.evidence_refs.includes(ref));}
 }
 assert.match(c.financial.analysis.en,/Other comprehensive income is distinct from net income/);
 assert.match(c.capital.analysis.en,/classification does not eliminate rollover risk/);
 assert.match(c.competition.analysis.en,/rather than announce a change/);
 assert.match(c.macro.analysis.en,/rather than automatically offset tariffs/);
 assert.match(c.factors.analysis.en,/not validated Alpha/);
 assert.match(c.conclusion.analysis.en,/organic growth excludes currency/);
});
test('CL English projection and catalog reference the exact reviewed version',()=>{
 const en=JSON.parse(file(`private-data/report-translations/${id}.en.json`));
 assert.equal(en.thesis,c.conclusion.analysis.en);assert.equal(en.newsReport.narrative,c.financial.analysis.en);
 assert.equal(JSON.parse(file('snapshot/research-report-index.json')).reports.filter(x=>x.id===id).length,1);
 assert.ok(JSON.parse(file('snapshot/equity-report-catalog.json')).companies.find(x=>x.ticker==='CL').reportIds.includes(id));
});
