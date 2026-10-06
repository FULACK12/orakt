import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
import {validateDossier,assembleReviewedDossier} from '../scripts/reviewed-dossier.mjs';
const read=p=>JSON.parse(readFileSync(new URL('../'+p,import.meta.url),'utf8'));
const id='dossier-NVDA-20250528',d=read(`private-data/company-dossiers/${id}.json`),r=read(`private-data/research-reports/${id}.json`).report;
test('NVDA complete bilingual revision is accessible through index/catalog without invented confidence',()=>{
 assert.equal(validateDossier(d,r).chapters.length,9);assert.equal(r.confidence,null);assert.equal(r.localInquiryId,undefined);
 assert.equal(d.provenance.retainedDrafts.length>9,true);assert.equal(d.provenance.sourceDocumentHash.length,64);
 assert.equal(read('snapshot/research-report-index.json').reports.filter(x=>x.id===id).length,1);
 assert.ok(read('snapshot/equity-report-catalog.json').companies.find(x=>x.ticker==='NVDA').reportIds.includes(id));
 assert.ok(read(`private-data/report-translations/${id}.en.json`).thesis.length>500);
 assert.equal(d.ratioChecks[0].direction,'decrease');assert.ok(Number(d.ratioChecks[0].currentPercent)<Number(d.ratioChecks[0].previousPercent));
});
test('report audit preserves original partial drafts and links reviewed revision separately',()=>{
 const a=read('private-data/research-completions/local-707.json').draftAudit;
 assert.equal(a.reports.find(x=>x.ticker==='NVDA').retainedChapters,8);
 assert.equal(a.reports.find(x=>x.ticker==='NVDA').reviewedReportId,id);
 assert.equal(a.reports.find(x=>x.ticker==='AMD').published,true);
 assert.equal(a.reports.find(x=>x.ticker==='AMD').reviewedReportId,'dossier-AMD-20250507');
 assert.equal(a.reports.find(x=>x.ticker==='AMD').retainedChapters,1);
});
test('AMD reviewed revision includes bilingual period-boundary events and original drafts',()=>{
 const id='dossier-AMD-20250507',d=read(`private-data/company-dossiers/${id}.json`),r=read(`private-data/research-reports/${id}.json`).report;
 const bytes=readFileSync(new URL(`../private-data/dossier-reviews/${id}.json`,import.meta.url));
 assert.equal(assembleReviewedDossier(d,bytes,r).chapters.length,9);
 assert.equal(d.eventTimeline.length,4);assert.equal(d.eventTimeline.filter(e=>e.periodRelation==='post_period_known_at_cutoff').length,3);
 assert.equal(d.ratioChecks[0].direction,'increase');assert.equal(r.confidence,null);
 assert.equal(d.provenance.continuation.method,'generate_missing_only_one_attempt_per_chapter');
 assert.ok(d.provenance.retainedDrafts.length>=9);
 assert.ok(read('snapshot/equity-report-catalog.json').companies.find(c=>c.ticker==='AMD').reportIds.includes(id));
 assert.equal(read(`private-data/report-translations/${id}.en.json`).historical.corrections.length,8);
 const changed=structuredClone(d);changed.eventTimeline[0].interpretation.en+=' Unreviewed claim.';
 assert.throws(()=>assembleReviewedDossier(changed,bytes,r),/differs/);
 for(const alter of [e=>e.periodRelation='within_report_period',e=>e.sourceFiledAt='2025-06-01',e=>e.eventDate='2025-02-30',e=>e.sourceUrl='https://example.test',e=>e.recognition='realized_profit',e=>e.title.en='']){
  const x=structuredClone(d);alter(x.eventTimeline[2]);assert.throws(()=>validateDossier(x,r));
 }
});
test('review artifact cannot silently differ from published prose',()=>{
 const bytes=readFileSync(new URL(`../private-data/dossier-reviews/${id}.json`,import.meta.url));
 assert.equal(assembleReviewedDossier(d,bytes,r).review.humanAccepted,false);
 const changed=structuredClone(d);changed.chapters[0].analysis.en+=' Invented revision.';
 assert.throws(()=>assembleReviewedDossier(changed,bytes,r),/differs/);
});
