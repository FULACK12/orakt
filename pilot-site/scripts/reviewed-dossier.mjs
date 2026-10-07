import {createHash} from 'node:crypto';
import {validateConsolidatedReceipt} from './consolidated-dossier.mjs';
export const chapterKeys=['business','financial','capital','competition','supply','macro','valuation','factors','conclusion'];
export function validateGroundedClaims(d,c){
 const passages=d.originalPassages?.[c.key]||[];
 const claims=c.grounded_claims||[];
 if(!passages.length&&!claims.length)return; // Legacy dossiers retain their original review protocol.
 const known=new Map(passages.map(p=>[p.id,p]));
 if(new Set(claims.map(q=>q.passage_id)).size<2)throw Error('Two distinct source-grounded claims required');
 const normalize=s=>String(s||'').trim().replace(/\s+/g,' ');
 for(const q of claims){
  const p=known.get(q.passage_id);
  if(!p||!c.evidence_refs.includes(q.passage_id)||normalize(q.quote).length<30||!normalize(p.text).includes(normalize(q.quote)))throw Error('Claim quotation differs from frozen chapter passage');
  if(p.sourceHash!==d.provenance?.sourceDocumentHash||!Number.isInteger(p.start)||p.start<0||p.end!==p.start+Array.from(p.text).length)throw Error('Passage source/offset mismatch');
  const digest=createHash('sha256').update(`${p.sourceHash}:${p.start}:${p.text}`).digest('hex');
  if(p.id!==`PASSAGE:${digest.slice(0,16)}`)throw Error('Frozen passage hash mismatch');
  if(!/[\u4e00-\u9fff]/.test(q.statement?.zh||'')||!q.statement?.en?.trim()||/[\u4e00-\u9fff]/.test(q.statement.en))throw Error('Bilingual grounded statement required');
 }
}
export function validateTimeline(d){
 const ids=new Set();
 const validDate=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&Number.isFinite(Date.parse(s))&&new Date(s).toISOString().slice(0,10)===s;
 for(const e of d.eventTimeline||[]){
  if(![d.asOf,d.periodEnd,e.eventDate,e.sourceFiledAt].every(validDate)||!e.id||ids.has(e.id)||e.eventDate>e.sourceFiledAt||e.sourceFiledAt>d.asOf)throw Error('Timeline date mismatch');
  if(e.periodRelation!==(e.eventDate>d.periodEnd?'post_period_known_at_cutoff':'within_report_period'))throw Error('Timeline period mismatch');
  if(!(d.sources||[]).some(s=>s.id===e.evidenceRef&&s.url===e.sourceUrl))throw Error('Timeline source mismatch');
  if(!['disclosed_transaction','expected_charge','expected_benefit'].includes(e.recognition))throw Error('Timeline recognition required');
  for(const field of ['title','interpretation'])if(!e[field]?.zh?.trim()||!e[field]?.en?.trim()||/[\u4e00-\u9fff]/.test(e[field].en))throw Error('Bilingual timeline required');
  ids.add(e.id);
 }
}
export function validateDossier(d,report,bytes,receiptBytes){
 if(d.ticker!==report.ticker||d.asOf!==report.dataCutoff)throw Error('Dossier identity/cutoff mismatch');
 if(d.version==='consolidated-site/v1')validateConsolidatedReceipt(d,report,bytes,receiptBytes);
 else if(d.review?.state!=='assistant_reviewed'||d.review?.humanAccepted!==false||! /^[a-f0-9]{64}$/.test(d.review?.assistantRevisionHash||'')||d.eligibleForPredictiveBacktest!==false)throw Error('Dossier needs explicit review; not a validated forecast');
 if(JSON.stringify(d.chapters?.map(c=>c.key))!==JSON.stringify(chapterKeys))throw Error('Nine ordered unique chapters required');
 const known=new Set([...(d.sources||[]).map(s=>s.id),...(d.facts||[]).map(f=>f.evidence_id),...(d.marketEvidence||[]).map(s=>s.id)]);
 for(const c of d.chapters){
  const chapterKnown=new Set([...known,...(d.originalPassages?.[c.key]||[]).map(p=>p.id)]);
  if(c.authorship!=='assistant_revised'||!c.evidence_refs?.length||c.evidence_refs.some(id=>!chapterKnown.has(id)))throw Error('Unreviewed chapter or unknown citation');
  for(const field of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan']){
   if(!c[field]?.zh?.trim()||!c[field]?.en?.trim()||/[\u4e00-\u9fff]/.test(c[field].en))throw Error('Complete bilingual prose required');
  }
  validateGroundedClaims(d,c);
 }
 if(!d.financialLedger?.comparisons?.length)throw Error('Missing financial ledger');
 validateTimeline(d);
 return d;
}
export function assembleReviewedDossier(d,reviewBytes,report){
 const review=JSON.parse(reviewBytes.toString('utf8'));
 const hash=createHash('sha256').update(reviewBytes).digest('hex');
 if(review.reviewer!=='codex_assistant'||review.ticker!==d.ticker||review.asOf!==d.asOf||!review.corrections?.length||hash!==d.review?.assistantRevisionHash)throw Error('Review artifact mismatch');
 for(const c of d.chapters){
  for(const field of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan','evidence_refs','comparison_checks','grounded_claims']){
   if(field==='grounded_claims'&&!(c[field]?.length)&&!review.chapters?.[c.key]?.[field]?.length)continue;
   if(JSON.stringify(c[field])!==JSON.stringify(review.chapters?.[c.key]?.[field]))throw Error('Published prose differs from reviewed revision');
  }
 }
 if(JSON.stringify(d.eventTimeline||[])!==JSON.stringify(review.eventTimeline||[]))throw Error('Timeline differs from reviewed revision');
 return validateDossier({...d,review:{...d.review,state:'assistant_reviewed',reviewer:'codex_assistant',checkedAt:new Date().toISOString(),corrections:review.corrections,changesReportConfidence:false}},report);
}
