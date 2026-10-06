import {createHash} from 'node:crypto';
export const chapterKeys=['business','financial','capital','competition','supply','macro','valuation','factors','conclusion'];
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
export function validateDossier(d,report){
 if(d.ticker!==report.ticker||d.asOf!==report.dataCutoff)throw Error('Dossier identity/cutoff mismatch');
 if(d.review?.state!=='assistant_reviewed'||d.review?.humanAccepted!==false||! /^[a-f0-9]{64}$/.test(d.review?.assistantRevisionHash||'')||d.eligibleForPredictiveBacktest!==false)throw Error('Dossier needs explicit review; not a validated forecast');
 if(JSON.stringify(d.chapters?.map(c=>c.key))!==JSON.stringify(chapterKeys))throw Error('Nine ordered unique chapters required');
 const known=new Set([...(d.sources||[]).map(s=>s.id),...(d.facts||[]).map(f=>f.evidence_id),...(d.marketEvidence||[]).map(s=>s.id)]);
 for(const c of d.chapters){
  if(c.authorship!=='assistant_revised'||!c.evidence_refs?.length||c.evidence_refs.some(id=>!known.has(id)))throw Error('Unreviewed chapter or unknown citation');
  for(const field of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan']){
   if(!c[field]?.zh?.trim()||!c[field]?.en?.trim()||/[\u4e00-\u9fff]/.test(c[field].en))throw Error('Complete bilingual prose required');
  }
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
  for(const field of ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan','evidence_refs','comparison_checks']){
   if(JSON.stringify(c[field])!==JSON.stringify(review.chapters?.[c.key]?.[field]))throw Error('Published prose differs from reviewed revision');
  }
 }
 if(JSON.stringify(d.eventTimeline||[])!==JSON.stringify(review.eventTimeline||[]))throw Error('Timeline differs from reviewed revision');
 return validateDossier({...d,review:{...d.review,state:'assistant_reviewed',reviewer:'codex_assistant',checkedAt:new Date().toISOString(),corrections:review.corrections,changesReportConfidence:false}},report);
}
