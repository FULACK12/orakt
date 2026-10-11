import {randomUUID,createHash,timingSafeEqual} from 'node:crypto';
import {Buffer} from 'node:buffer';
import {readSmallJson} from './research-publication-api.mjs';
import {publications,publicationHash} from './research-publications.mjs';
import {accessFor} from './membership.mjs';
const json=(v,status=200)=>Response.json(v,{status,headers:{'Cache-Control':'private, no-store'}});
export const RESEARCH_MODEL='orakt-14b:latest';
const digest=v=>createHash('sha256').update(v).digest();
export function bridgeAuthorized(request,env){const secret=env.ORAKT_RESEARCH_BRIDGE_TOKEN,got=request.headers.get('Authorization')||'';return typeof secret==='string'&&secret.length>=32&&timingSafeEqual(digest(got),digest('Bearer '+secret));}
export const publicJob=r=>({id:r.id,prompt:r.prompt,language:r.language,state:r.state,result:r.result?JSON.parse(r.result):null,error:r.error,createdAt:r.created_at,updatedAt:r.updated_at,model:RESEARCH_MODEL,reviewStatus:'draft_not_semantically_reviewed'});
async function workerState(env){const r=await env.DB.prepare('SELECT updated_at,status FROM research_worker WHERE id=1').bind().first();return {online:!!r&&Date.now()-r.updated_at<180000,status:r?.status||'offline',lastSeenAt:r?.updated_at||null};}
export async function localResearchResponse(request,env,member){
 if(!member.access.permissions.research)return json({error:'research_plan_required'},403);
 const url=new URL(request.url);
 if(request.method==='GET'){
  const id=url.searchParams.get('id'),r=id?await env.DB.prepare('SELECT * FROM research_jobs WHERE id=? AND actor_id=?').bind(id,member.row.id).first():null;
  if(id&&!r)return json({error:'not_found'},404);
  const jobs=id?[publicJob(r)]:(await env.DB.prepare('SELECT * FROM research_jobs WHERE actor_id=? ORDER BY created_at DESC LIMIT 20').bind(member.row.id).all()).results.map(publicJob);
  return json({jobs,worker:await workerState(env),model:RESEARCH_MODEL,evidence:publications.map(r=>({id:r.id,title:r.title})),dailyLimit:5});
 }
 if(request.method!=='POST')return json({error:'method_not_allowed'},405);
 if(request.headers.get('Origin')!==url.origin||request.headers.get('X-ORAKT-Research')!=='generate')return json({error:'same_origin_required'},403);
 try{
  const v=await readSmallJson(request);
  if(v.action==='cancel'){const r=await env.DB.prepare("UPDATE research_jobs SET state='cancelled',updated_at=? WHERE id=? AND actor_id=? AND state IN ('queued','running') RETURNING id").bind(Date.now(),v.id,member.row.id).first();return r?json({state:'cancelled'}):json({error:'not_cancellable'},409);}
  if(typeof v.prompt!=='string'||v.prompt.trim().length<5||v.prompt.length>3000||!['zh','en'].includes(v.language)||!Array.isArray(v.evidenceIds)||!v.evidenceIds.length||v.evidenceIds.length>3||v.evidenceIds.some(id=>!publications.some(r=>r.id===id)))return json({error:'invalid_research_request'},400);
  const status=await workerState(env);if(!status.online)return json({error:'local_worker_offline',worker:status},503);
  const evidence=publications.filter(r=>v.evidenceIds.includes(r.id)).map(r=>({report:r,sha256:publicationHash(r)})),now=Date.now(),id=randomUUID();
  // One statement: rate/active limits cannot race across simultaneous requests.
  const result=await env.DB.prepare("INSERT INTO research_jobs(id,actor_id,prompt,language,evidence,state,created_at,updated_at) SELECT ?,?,?,?,?,'queued',?,? WHERE NOT EXISTS(SELECT 1 FROM research_jobs WHERE actor_id=? AND state IN ('queued','running')) AND (SELECT count(*) FROM research_jobs WHERE actor_id=? AND created_at>?)<5 RETURNING id").bind(id,member.row.id,v.prompt.trim(),v.language,JSON.stringify(evidence),now,now,member.row.id,member.row.id,now-86400000).first();
  return result?json({id,state:'queued',model:RESEARCH_MODEL},201):json({error:'active_job_or_daily_limit'},429);
 }catch{return json({error:'invalid_request_or_queue_unavailable'},400);}
}
export async function researchBridgeResponse(request,env){
 if(!bridgeAuthorized(request,env))return json({error:'unauthorized'},401);
 if(request.method!=='POST')return json({error:'method_not_allowed'},405);
 try{
  const v=await readSmallJson(request,180000),now=Date.now();
  if(v.action==='heartbeat'){
   if(!['ready','busy','cooling','lock_busy'].includes(v.status))return json({error:'invalid_status'},400);
   await env.DB.prepare('INSERT INTO research_worker(id,status,updated_at) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,updated_at=excluded.updated_at').bind(v.status,now).run();return json({ok:true});
  }
  if(v.action==='claim'){
   await env.DB.prepare("UPDATE research_jobs SET state='failed',error='worker_lease_expired',updated_at=? WHERE state='running' AND lease_until<?").bind(now,now).run();
   const token=randomUUID(),row=await env.DB.prepare("UPDATE research_jobs SET state='running',lease_token=?,lease_until=?,updated_at=? WHERE id=(SELECT id FROM research_jobs WHERE state='queued' ORDER BY created_at LIMIT 1) AND state='queued' AND NOT EXISTS(SELECT 1 FROM research_jobs WHERE state='running') RETURNING *").bind(token,now+180000,now).first();
   if(!row)return json({job:null});
   const owner=await env.DB.prepare('SELECT * FROM member_accounts WHERE id=?').bind(row.actor_id).first();
   if(!owner||!accessFor(owner,env).permissions.research){await env.DB.prepare("UPDATE research_jobs SET state='cancelled',error='entitlement_revoked',updated_at=? WHERE id=?").bind(now,row.id).run();return json({job:null});}
   return json({job:{id:row.id,prompt:row.prompt,language:row.language,evidence:JSON.parse(row.evidence),leaseToken:token},model:RESEARCH_MODEL});
  }
  const row=await env.DB.prepare("SELECT * FROM research_jobs WHERE id=? AND lease_token=? AND state='running' AND lease_until>?").bind(v.id,v.leaseToken,now).first();if(!row)return json({error:'lease_lost_or_cancelled'},409);
  const owner=await env.DB.prepare('SELECT * FROM member_accounts WHERE id=?').bind(row.actor_id).first();
  if(!owner||!accessFor(owner,env).permissions.research){await env.DB.prepare("UPDATE research_jobs SET state='cancelled',error='entitlement_revoked',updated_at=? WHERE id=?").bind(now,row.id).run();return json({error:'entitlement_revoked'},409);}
  if(v.action==='renew'){await env.DB.prepare('UPDATE research_jobs SET lease_until=?,updated_at=? WHERE id=? AND lease_token=? AND state=\'running\'').bind(now+180000,now,row.id,v.leaseToken).run();return json({ok:true});}
  if(v.action==='fail'){await env.DB.prepare("UPDATE research_jobs SET state='failed',error='local_generation_failed',updated_at=? WHERE id=? AND lease_token=? AND state='running'").bind(now,row.id,v.leaseToken).run();return json({state:'failed'});}
  if(v.action==='complete'){
   if(v.model!==RESEARCH_MODEL||typeof v.text!=='string'||v.text.length<80||v.text.length>100000)return json({error:'invalid_result'},400);
   const result={text:v.text,model:RESEARCH_MODEL,generatedAt:new Date(now).toISOString(),evidenceHashes:JSON.parse(row.evidence).map(e=>({id:e.report.id,sha256:e.sha256})),reviewStatus:'draft_not_semantically_reviewed',investmentApproved:false};
   const r=await env.DB.prepare("UPDATE research_jobs SET state='draft',result=?,updated_at=? WHERE id=? AND lease_token=? AND state='running' RETURNING id").bind(JSON.stringify(result),now,row.id,v.leaseToken).first();return r?json({state:'draft'}):json({error:'lease_lost'},409);
  }
  return json({error:'invalid_action'},400);
 }catch{return json({error:'bridge_unavailable'},503);}
}
