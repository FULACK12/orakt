import {createHash} from 'node:crypto';
import {isDeepStrictEqual} from 'node:util';
const hash=raw=>createHash('sha256').update(raw).digest('hex');
export function validateConsolidatedReceipt(d, report, bytes, receiptBytes){
 if(!bytes||!receiptBytes||!isDeepStrictEqual(JSON.parse(bytes),d))throw Error('Exact retained dossier bytes required');
 const r=JSON.parse(receiptBytes);
 const checks=['periods_and_values','cross_chapter_consistency','bilingual_scope','source_and_claims','gaps_and_eligibility'];
 if(r.version!=='consolidated-publication/v1'||r.siteDossierSha256!==hash(bytes)||r.ticker!==d.ticker||r.asOf!==d.asOf||r.reviewedDossierSha256!==d.provenance?.reviewedDossierHash)throw Error('Consolidated publication receipt mismatch');
 if(d.review?.state!=='assistant_reviewed_research_only'||r.reviewState!==d.review.state||d.review.reviewer!=='codex_assistant'||d.review.humanAccepted!==false||d.review.independentVerification!==false||d.review.chapterReviews!==9||report.confidence!==null)throw Error('Historical research review required; no invented confidence');
 if(d.eligibleForPredictiveBacktest!==false||d.validatedAlpha!==false||r.eligibleForPredictiveBacktest!==false||r.validatedAlpha!==false||r.humanAccepted!==false)throw Error('Research must remain non-predictive');
 const a=d.wholeReportAudit;
 if(!isDeepStrictEqual(a,r.wholeReportAudit)||a?.reviewer!=='codex_assistant'||a.state!==d.review.state||a.sourceFingerprint!==d.provenance.sourceFingerprint||a.parentSha256!==d.review.parentSha256||checks.some(k=>typeof a.checks?.[k]!=='string'||a.checks[k].trim().length<30))throw Error('Whole-report audit missing or mismatched');
 if(d.dataCoverage!=='partial_with_explicit_gaps')throw Error('Do not silently upgrade evidence coverage');
 return d;
}
