import {createHash} from 'node:crypto';
export const KINDS=['news_source','ground_photo','satellite_image','osint','local_report','dataset','analysis'];
export const hash=value=>createHash('sha256').update(typeof value==='string'||ArrayBuffer.isView(value)?value:JSON.stringify(value)).digest('hex');
export const contributor=id=>hash('ORAKT:contributor:v1:'+id);
// Counts are event-level resolved judgements, never raw submission volume.
export function reputation(rows){
 const confirmed=rows.filter(r=>r.verdict==='confirmed'&&r.state==='approved').length;
 const refuted=rows.filter(r=>r.verdict==='refuted'&&r.state==='approved').length;
 const resolved=confirmed+refuted;
 let lower=null;
 if(resolved){const z=1.96,p=confirmed/resolved;lower=(p+z*z/(2*resolved)-z*Math.sqrt(p*(1-p)/resolved+z*z/(4*resolved*resolved)))/(1+z*z/resolved);}
 return {version:'reputation/wilson-event-v1',submissions:rows.length,confirmed,refuted,unresolved:rows.length-resolved,resolved,confirmationRate:resolved?confirmed/resolved:null,resolutionCoverage:rows.length?resolved/rows.length:0,score:resolved>=20?Math.floor(1000*lower):null,scoreScale:1000,minimumResolved:20,confidenceLower95:lower,onChainAsset:false,transferable:false,limitations:['Reviewer-attested independence, not Sybil-proof identity','Unresolved and disputed items do not count as successes','No token has been minted']};
}
export function verification(v,actor,author){
 if(actor===author)throw {status:403,error:'self_verification_forbidden'};
 if(!['approved','rejected','changes_requested','disputed','retracted'].includes(v.state)||!['unresolved','confirmed','refuted'].includes(v.verdict))throw {status:400,error:'invalid_verdict'};
 if(typeof v.note!=='string'||v.note.trim().length<20||v.note.length>3000)throw {status:400,error:'review_reason_required'};
 if(v.state!=='approved'&&v.verdict!=='unresolved')throw {status:400,error:'nonapproved_verdict_must_be_unresolved'};
 const evidence=Array.isArray(v.evidence)?v.evidence:[];
 if(evidence.length>5||evidence.some(s=>{try{return new URL(s).protocol!=='https:'||new URL(s).username||new URL(s).password||s.length>1200;}catch{return true;}}))throw {status:400,error:'invalid_review_sources'};
 if(v.verdict!=='unresolved'&&(v.independenceConfirmed!==true||evidence.length<2||new Set(evidence.map(s=>new URL(s).hostname.replace(/^www\./,''))).size<2))throw {status:400,error:'independent_evidence_required'};
 return {state:v.state,verdict:v.verdict,note:v.note.trim(),evidence,independence:'reviewer_attested_not_automatically_verified',confidence:null};
}
export const intelligenceMemo=r=>`ORAKT:intel:v1:${r.id}:${r.revision}:${r.head_hash}`;
