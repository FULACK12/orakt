import {accessFor} from './membership.mjs';
import {readSmallJson} from './research-publication-api.mjs';
const json=(data,status=200)=>Response.json(data,{status,headers:{'Cache-Control':'private, no-store'}});
export async function trialResponse(request,env,member){
 if(!member?.row||member.row.status!=='active')return json({error:'active_account_required'},403);
 const url=new URL(request.url);
 if(request.method!=='POST')return json({error:'method_not_allowed'},405);
 if(request.headers.get('Origin')!==url.origin||request.headers.get('X-ORAKT-Trial')!=='claim')return json({error:'same_origin_required'},403);
 try{
  const body=await readSmallJson(request,1024);if(body?.action!=='claim'||Object.keys(body).some(k=>k!=='action'))return json({error:'invalid_request'},400);
  const now=Date.now(),before=await env.DB.prepare('SELECT * FROM member_accounts WHERE id=?').bind(member.row.id).first();
  const access=accessFor(before,env,now);
  if(before.trial_claimed_at!=null)return json({membership:access,alreadyClaimed:true});
  if(!access.trial.eligible)return json({error:'already_has_research_or_account_unavailable'},409);
  const until=now+86400000,auditId='trial:'+member.row.id;
  // A one-time overlay: never rewrite or shorten a paid/complimentary plan.
  await env.DB.batch([
   env.DB.prepare("UPDATE member_accounts SET trial_claimed_at=?,trial_expires_at=?,revision=revision+1 WHERE id=? AND status='active' AND trial_claimed_at IS NULL AND NOT(COALESCE(plan='research' AND expires_at>? AND grant_kind IN ('manual_paid','complimentary','onchain_paid'),0))").bind(now,until,member.row.id,now),
   env.DB.prepare("INSERT INTO member_audit(id,actor_id,target_id,before_json,after_json,reason,created_at) SELECT ?,id,id,?,?,?,? FROM member_accounts WHERE id=? AND trial_claimed_at=? ON CONFLICT(id) DO NOTHING").bind(auditId,JSON.stringify({trialClaimedAt:null}),JSON.stringify({trialClaimedAt:now,trialExpiresAt:until}), 'Account explicitly claimed one non-renewing 24-hour Research trial',now,member.row.id,now)
  ]);
  const row=await env.DB.prepare('SELECT * FROM member_accounts WHERE id=?').bind(member.row.id).first();
  return row.trial_claimed_at!=null?json({membership:accessFor(row,env),alreadyClaimed:false}):json({error:'eligibility_changed_refresh'},409);
 }catch{return json({error:'trial_unavailable'},503);}
}
