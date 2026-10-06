import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateDossier,assembleReviewedDossier} from '../scripts/reviewed-dossier.mjs';
const read=p=>JSON.parse(readFileSync(new URL('../'+p,import.meta.url),'utf8'));
const id='dossier-NEM-20090430';
const d=read(`private-data/company-dossiers/${id}.json`),report=read(`private-data/research-reports/${id}.json`).report;
const review=readFileSync(new URL(`../private-data/dossier-reviews/${id}.json`,import.meta.url));
test('NEM nine-chapter historical reconstruction has reviewed bilingual claims and no invented confidence',()=>{
 assert.equal(assembleReviewedDossier(d,review,report).chapters.length,9);
 assert.equal(d.chapters.flatMap(c=>c.grounded_claims).length,18);
 assert.equal(d.review.humanAccepted,false);assert.equal(d.eligibleForPredictiveBacktest,false);
 assert.equal(report.confidence,null);assert.equal(report.dataCutoff,'2009-04-30');
 assert.ok(d.provenance.retainedDrafts.length>=9);
 assert.ok(read('snapshot/equity-report-catalog.json').companies.find(c=>c.ticker==='NEM').reportIds.includes(id));
 assert.equal(read('snapshot/research-report-index.json').reports.filter(r=>r.id===id).length,1);
 assert.ok(read(`private-data/report-translations/${id}.en.json`).thesis.length>500);
});
test('quotation edits, unknown passages, duplicate claims and missing English fail closed',()=>{
 for(const alter of [
  x=>x.chapters[0].grounded_claims[0].quote='This invented claim never appeared in the original filing.',
  x=>x.chapters[0].grounded_claims[0].passage_id='PASSAGE:fake',
  x=>x.chapters[0].grounded_claims[1]=structuredClone(x.chapters[0].grounded_claims[0]),
  x=>x.chapters[0].grounded_claims[0].statement.en='',
  x=>x.originalPassages.business.find(p=>p.id===x.chapters[0].grounded_claims[0].passage_id).sourceHash='0'.repeat(64),
  x=>{const p=x.originalPassages.business.find(p=>p.id===x.chapters[0].grounded_claims[0].passage_id);p.text+=' invented';p.end+=9;},
  x=>x.chapters[0].evidence_refs.push(x.originalPassages.capital[0].id)
 ]){const changed=structuredClone(d);alter(changed);assert.throws(()=>validateDossier(changed,report));}
});
test('claim interpretation cannot change after assistant review',()=>{
 const changed=structuredClone(d);changed.chapters[0].grounded_claims[0].statement.en+=' This was not reviewed.';
 assert.throws(()=>assembleReviewedDossier(changed,review,report),/differs/);
});
