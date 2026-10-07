import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateDossier} from '../scripts/reviewed-dossier.mjs';
const id='dossier-NVDA-20090820-97979407';
const file=path=>readFileSync(new URL('../'+path,import.meta.url));
const bytes=file(`private-data/company-dossiers/${id}.json`),receipt=file(`private-data/dossier-reviews/${id}.json`),d=JSON.parse(bytes),report=JSON.parse(file(`private-data/research-reports/${id}.json`)).report;
test('nine-chapter historical research keeps original review state and bilingual text',()=>{
 const v=validateDossier(d,report,bytes,receipt);
 assert.equal(v.chapters.length,9);assert.equal(v.review.state,'assistant_reviewed_research_only');
 assert.equal(report.confidence,null);assert.equal(v.validatedAlpha,false);
 assert.equal(v.cashBridge.residual,'0');assert.equal(v.financialLedger.comparisons.length,20);
 const en=JSON.parse(file(`private-data/report-translations/${id}.en.json`));
 assert.match(en.question,/historical/);assert.equal(en.thesis,v.chapters.at(-1).analysis.en);
 assert.doesNotMatch(bytes.toString(),/[A-Z]:\\/);
});
test('content mutation, missing receipt and inflated confidence fail closed',()=>{
 assert.throws(()=>validateDossier(d,report));
 for(const change of [x=>x.chapters[0].analysis.en+=' changed',x=>x.validatedAlpha=true,x=>x.review.humanAccepted=true,x=>x.wholeReportAudit.checks={}]){
  const x=structuredClone(d);change(x);assert.throws(()=>validateDossier(x,report,bytes,receipt));
  assert.throws(()=>validateDossier(x,report,Buffer.from(JSON.stringify(x)),receipt));
 }
 assert.throws(()=>validateDossier(d,{...report,confidence:.9},bytes,receipt));
});
test('catalog references the private report once and includes historical cutoff',()=>{
 const index=JSON.parse(file('snapshot/research-report-index.json'));
 assert.equal(index.reports.filter(r=>r.id===id).length,1);
 const row=index.reports.find(r=>r.id===id);assert.equal(row.historical.asOf,'2009-08-20');
 const c=JSON.parse(file('snapshot/equity-report-catalog.json')).companies.find(c=>c.ticker==='NVDA');
 assert.ok(c.reportIds.includes(id));
});
