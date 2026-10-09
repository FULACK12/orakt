import {randomUUID,createHash} from 'node:crypto';
const select="SELECT id, provider, subject, display_name, legacy_ref, created_at, first_seen_at, last_seen_at, status, plan, grant_kind, expires_at, revision FROM member_accounts";
const json=(body,status=200)=>Response.json(body,{status,headers:{'Cache-Control':'private, no-store'}});
const admin=(row,env)=>Boolean((env.ORAKT_ADMIN_ACCOUNT_ID&&row.id===env.ORAKT_ADMIN_ACCOUNT_ID)||(!env.ORAKT_ADMIN_ACCOUNT_ID&&env.ORAKT_ADMIN_REFERENCE&&`${row.provider}:${row.legacy_ref}`===env.ORAKT_ADMIN_REFERENCE));

// One durable row per proven provider identity. No email matching or first-user promotion.
export async function memberFor(env,identity,active=false){
 if(!env.DB)throw Error('membership_unavailable');
 const now=Date.now();
 await env.DB.prepare("INSERT INTO member_accounts (id, provider, subject, display_name, legacy_ref, created_at, first_seen_at, last_seen_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(provider, subject) DO NOTHING").bind(randomUUID(),identity.provider,identity.subject,identity.displayName,identity.accountId,identity.createdAt?Date.parse(identity.createdAt):now,now,active?now:null).run();
 if(active)await env.DB.prepare("UPDATE member_accounts SET last_seen_at = ? WHERE provider = ? AND subject = ? AND status = 'active' AND (last_seen_at IS NULL OR last_seen_at < ?)").bind(now,identity.provider,identity.subject,now-60000).run();
 const row=await env.DB.prepare(`${select} WHERE provider = ? AND subject = ?`).bind(identity.provider,identity.subject).first();
 if(!row)throw Error('membership_unavailable');
 return {row,access:accessFor(row,env,now)};
}
export function accessFor(row,env,now=Date.now()){
 const isAdmin=admin(row,env),active=row.status==='active',paidPlan=['signal','research'].includes(row.plan),expired=paidPlan&&(!Number.isSafeInteger(row.expires_at)||row.expires_at<=now||!['manual_paid','complimentary','onchain_paid'].includes(row.grant_kind));
 const effectivePlan=active&&paidPlan&&!expired?row.plan:'explorer';
 return {role:isAdmin?'admin':'member',status:row.status,plan:row.plan,effectivePlan,grantKind:row.grant_kind,expiresAt:row.expires_at?new Date(row.expires_at).toISOString():null,expired,
 permissions:{map:active,reports:active&&(isAdmin||effectivePlan!=='explorer'),research:active&&(isAdmin||effectivePlan==='research'),manageUsers:active&&isAdmin,generateAI:false},billing:'monthly_non_recurring'};
}
export function publicMember(member,identity){return {provider:member.row.provider,displayName:member.row.display_name,accountId:member.row.id,previousAccountId:member.row.legacy_ref,expiresAt:identity.expiresAt,createdAt:new Date(member.row.created_at).toISOString(),membership:member.access};}

// Bounded, separately executed data import: never seed/backfill via migrations.
async function importExistingLocalAccounts(env){
 const pending=await env.DB.prepare("SELECT a.id, a.username, a.created_at FROM local_auth_accounts a WHERE NOT EXISTS (SELECT 1 FROM member_accounts m WHERE m.provider = 'local' AND m.subject = a.id) ORDER BY a.created_at LIMIT 100").bind().all();
 if(pending.results.length)await env.DB.batch(pending.results.map(a=>env.DB.prepare("INSERT INTO member_accounts (id, provider, subject, display_name, legacy_ref, created_at, first_seen_at) VALUES (?, 'local', ?, ?, ?, ?, ?) ON CONFLICT(provider, subject) DO NOTHING").bind(randomUUID(),a.id,a.username,a.id.slice(0,16),a.created_at,Date.now())));
 const left=await env.DB.prepare("SELECT COUNT(*) AS n FROM local_auth_accounts a WHERE NOT EXISTS (SELECT 1 FROM member_accounts m WHERE m.provider = 'local' AND m.subject = a.id)").bind().first();return left.n;
}
function safeRow(row,env){const access=accessFor(row,env);return {id:row.id,provider:row.provider,displayName:row.display_name,createdAt:new Date(row.created_at).toISOString(),firstSeenAt:new Date(row.first_seen_at).toISOString(),lastSeenAt:row.last_seen_at?new Date(row.last_seen_at).toISOString():null,revision:row.revision,...access};}
async function smallBody(request){
 if(!request.headers.get('Content-Type')?.startsWith('application/json'))throw Error();
 const reader=request.body?.getReader();if(!reader)throw Error();let text='',size=0;const d=new TextDecoder();
 while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>4096){await reader.cancel();throw Error();}text+=d.decode(value,{stream:true});}return JSON.parse(text+d.decode());
}
export async function memberAdminResponse(request,env,actor){
 if(!actor.access.permissions.manageUsers)return json({error:'admin_required'},403);
 const url=new URL(request.url),now=Date.now();
 try{
  if(url.pathname==='/api/admin/users'&&request.method==='GET'){
   const pendingLocalAccounts=(await env.DB.prepare("SELECT COUNT(*) AS n FROM local_auth_accounts a WHERE NOT EXISTS (SELECT 1 FROM member_accounts m WHERE m.provider = 'local' AND m.subject = a.id)").bind().first()).n;
   const stats=await env.DB.prepare(`SELECT COUNT(*) AS totalAccounts, MIN(first_seen_at) AS trackedSince, SUM(CASE WHEN last_seen_at >= ? THEN 1 ELSE 0 END) AS active24h, SUM(CASE WHEN last_seen_at >= ? THEN 1 ELSE 0 END) AS active7d, SUM(CASE WHEN last_seen_at >= ? THEN 1 ELSE 0 END) AS active30d, SUM(CASE WHEN status = 'active' AND plan <> 'explorer' AND expires_at > ? AND grant_kind = 'manual_paid' THEN 1 ELSE 0 END) AS manuallyConfirmedPaid, SUM(CASE WHEN status = 'active' AND plan <> 'explorer' AND expires_at > ? AND grant_kind = 'complimentary' THEN 1 ELSE 0 END) AS complimentary, SUM(CASE WHEN status = 'suspended' THEN 1 ELSE 0 END) AS suspended FROM member_accounts`).bind(now-86400000,now-7*86400000,now-30*86400000,now,now).first();
   stats.onchainPaid=(await env.DB.prepare("SELECT COUNT(*) AS n FROM member_accounts WHERE status = 'active' AND plan IN ('signal','research') AND grant_kind = 'onchain_paid' AND expires_at > ?").bind(now).first()).n;
   const providers=await env.DB.prepare("SELECT provider, COUNT(*) AS accounts FROM member_accounts GROUP BY provider").bind().all();
   const q=(url.searchParams.get('q')??'').trim().slice(0,80),page=Math.min(10000,Math.max(1,parseInt(url.searchParams.get('page')??'1')||1)),like=`%${q}%`;
   const where=" WHERE (id LIKE ? OR display_name LIKE ? OR provider LIKE ?)";
   const rows=await env.DB.prepare(`${select}${where} ORDER BY created_at DESC, id LIMIT 40 OFFSET ?`).bind(like,like,like,(page-1)*40).all();
   const count=await env.DB.prepare(`SELECT COUNT(*) AS n FROM member_accounts${where}`).bind(like,like,like).first();
   return json({asOf:new Date(now).toISOString(),stats,providers:providers.results,pendingLocalAccounts,users:rows.results.map(r=>safeRow(r,env)),page,pageSize:40,matched:count.n,countsAre:'provider_accounts_not_unique_people',history:'Legacy Google/Phantom/ChatGPT users appear when next observed; expired historical sessions are not a complete user directory.'});
  }
  if(url.pathname==='/api/admin/user-audit'&&request.method==='GET'){
   const target=url.searchParams.get('id')??'';
   const result=await env.DB.prepare("SELECT id, actor_id AS actorId, target_id AS targetId, before_json AS beforeJson, after_json AS afterJson, reason, created_at AS createdAt FROM member_audit WHERE target_id = ? ORDER BY created_at DESC LIMIT 50").bind(target).all();return json({targetId:target,events:result.results});
  }
  if(url.pathname==='/api/admin/import-local'&&request.method==='POST'){
   if(request.headers.get('Origin')!==url.origin||request.headers.get('X-ORAKT-Admin')!=='access')return json({error:'cross_origin_request'},403);
   return json({ok:true,pendingLocalAccounts:await importExistingLocalAccounts(env)});
  }
  if(url.pathname!=='/api/admin/user-access'||request.method!=='POST')return json({error:'method_not_allowed'},405);
  if(request.headers.get('Origin')!==url.origin||request.headers.get('X-ORAKT-Admin')!=='access')return json({error:'cross_origin_request'},403);
  let body;try{body=await smallBody(request);}catch{return json({error:'invalid_request'},400);}
  if(!body||!['explorer','signal','research'].includes(body.plan)||!['active','suspended'].includes(body.status)||!['free','complimentary','manual_paid'].includes(body.grantKind)||typeof body.id!=='string'||body.id.length>80||!Number.isInteger(body.revision)||typeof body.reason!=='string'||body.reason.trim().length<5||body.reason.length>500||Object.keys(body).some(k=>!['id','revision','plan','status','grantKind','expiresAt','reason'].includes(k)))return json({error:'invalid_request'},400);
  if(body.plan==='explorer'?(body.grantKind!=='free'||body.expiresAt!==null):(body.grantKind==='free'||!Number.isSafeInteger(body.expiresAt)||body.expiresAt<=now||body.expiresAt>now+5*366*86400000))return json({error:'invalid_entitlement'},400);
  const bucket=createHash('sha256').update(`member-admin:${actor.row.id}:${Math.floor(now/60000)}`).digest('hex');
  if(!await env.DB.prepare("INSERT INTO wallet_auth_limits (bucket, count, expires_at) VALUES (?, 1, ?) ON CONFLICT(bucket) DO UPDATE SET count = count + 1 WHERE count < 30 RETURNING count").bind(bucket,now+120000).first())return json({error:'rate_limited'},429);
  const before=await env.DB.prepare(`${select} WHERE id = ?`).bind(body.id).first();if(!before)return json({error:'account_not_found'},404);
  if(admin(before,env)&&body.status!=='active')return json({error:'cannot_suspend_admin'},409);
  if(before.revision!==body.revision)return json({error:'revision_conflict'},409);
  const mutation=randomUUID(),after={plan:body.plan,status:body.status,grantKind:body.grantKind,expiresAt:body.expiresAt,revision:body.revision+1};
  const results=await env.DB.batch([
   env.DB.prepare("UPDATE member_accounts SET plan = ?, status = ?, grant_kind = ?, expires_at = ?, revision = revision + 1, last_change_id = ? WHERE id = ? AND revision = ?").bind(body.plan,body.status,body.grantKind,body.expiresAt,mutation,body.id,body.revision),
   env.DB.prepare("INSERT INTO member_audit (id, actor_id, target_id, before_json, after_json, reason, created_at) SELECT ?, ?, id, ?, ?, ?, ? FROM member_accounts WHERE id = ? AND last_change_id = ?").bind(mutation,actor.row.id,JSON.stringify({plan:before.plan,status:before.status,grantKind:before.grant_kind,expiresAt:before.expires_at,revision:before.revision}),JSON.stringify(after),body.reason.trim(),now,body.id,mutation),
  ]);
  if(results[0].meta.changes!==1)return json({error:'revision_conflict'},409);
  return json({ok:true,revision:body.revision+1});
 }catch{return json({error:'membership_service_unavailable'},503);}
}
