import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateDossier} from '../scripts/reviewed-dossier.mjs';
const id='dossier-MU-20260625-9a1fb84e';
const file=p=>readFileSync(new URL('../'+p,import.meta.url));
const bytes=file(`private-data/company-dossiers/${id}.json`);
const receipt=file(`private-data/dossier-reviews/${id}.json`);
const d=JSON.parse(bytes),report=JSON.parse(file(`private-data/research-reports/${id}.json`)).report;
test('MU nine reviewed bilingual chapters preserve historical research boundaries',()=>{
 const v=validateDossier(d,report,bytes,receipt);
 assert.equal(v.chapters.length,9);assert.equal(v.periodEnd,'2026-05-28');assert.equal(v.asOf,'2026-06-25');
 assert.ok(v.createdAt>v.asOf);assert.equal(v.validatedAlpha,false);assert.equal(v.eligibleForPredictiveBacktest,false);
 assert.equal(v.review.humanAccepted,false);assert.equal(report.confidence,null);
 assert.doesNotMatch(bytes.toString(),/[A-Z]:\\|retainedModelAttempt/);
});
test('all MU paragraph citations resolve in both languages',()=>{
 for(const c of d.chapters){
  const refs=new Set(d.originalPassages[c.key].map(p=>p.id));
  for(const field of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'])
   for(const lang of ['zh','en'])
    for(const ref of c[field][lang].match(/PASSAGE:[a-f0-9]{16}/g)||[]){assert.ok(refs.has(ref));assert.ok(c.evidence_refs.includes(ref));}
 }
});
test('MU keeps explicit corrected source scope and bilingual index once',()=>{
 const byKey=Object.fromEntries(d.chapters.map(c=>[c.key,c]));
 assert.match(byKey.competition.analysis.en,/Samsung, SK hynix, Kioxia, Sandisk, CXMT and YMTC/);
 assert.match(byKey.capital.analysis.en,/neither category explains growth in operating cash/);
 assert.match(byKey.macro.analysis.en,/smaller backup facility is not debt repayment/);
 assert.match(byKey.factors.analysis.en,/nor does mix automatically establish nonlinearity/);
 const index=JSON.parse(file('snapshot/research-report-index.json'));
 assert.equal(index.reports.filter(r=>r.id===id).length,1);
 const company=JSON.parse(file('snapshot/equity-report-catalog.json')).companies.find(c=>c.ticker==='MU');assert.ok(company.reportIds.includes(id));
 const en=JSON.parse(file(`private-data/report-translations/${id}.en.json`));assert.equal(en.thesis,byKey.conclusion.analysis.en);
});
