import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateDossier} from '../scripts/reviewed-dossier.mjs';
const source=JSON.parse(readFileSync(new URL('../private-data/company-dossiers/local-707.json',import.meta.url),'utf8'));
const report={ticker:'AAPL',dataCutoff:'2025-08-01'};
test('nine-chapter bilingual reviewed dossier validates without claiming human approval',()=>{
 assert.equal(validateDossier(structuredClone(source),report).chapters.length,9);
});
test('unreviewed, wrong company, missing language, unknown citation and predictive claims fail closed',()=>{
 for(const alter of [d=>d.review.state='content_review_pending',d=>d.ticker='NVDA',d=>d.chapters[0].analysis.en='',d=>d.chapters[0].evidence_refs.push('FACT:fake'),d=>d.eligibleForPredictiveBacktest=true,d=>d.chapters.pop()]){
  const d=structuredClone(source);alter(d);assert.throws(()=>validateDossier(d,report));
 }
});
