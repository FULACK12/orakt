// Explicit account ownership proof only. No RPC, transactions, merging or grants.
import {randomBytes,createHash} from 'node:crypto';
import {Buffer} from 'node:buffer';
import {PublicKey} from '@solana/web3.js';
const COOKIE='__Host-orakt_wallet_link';
const json=(body,status=200,headers={})=>Response.json(body,{status,headers:{'Cache-Control':'private, no-store',...headers}});
const fail=(message,status=400)=>Object.assign(Error(message),{status});
const readBrowser=r=>(r.headers.get('Cookie')||'').split(';').map(x=>x.trim()).find(x=>x.startsWith(COOKIE+'='))?.slice(COOKIE.length+1)||'';
const cookie=(value,age)=>`${COOKIE}=${value}; Path=/; Max-Age=${age}; HttpOnly; Secure; SameSite=Strict`;
const random=()=>randomBytes(32).toString('hex');
export async function cancelWalletLink(request,env){const browser=readBrowser(request);if(/^[a-f0-9]{64}$/.test(browser)&&env.DB)await env.DB.prepare('DELETE FROM account_wallet_challenges WHERE browser=?').bind(browser).run();}
export function clearWalletLinkCookie(headers){headers.append('Set-Cookie',cookie('',0));}
export async function walletBinding(DB,member,address){
 const link=await DB.prepare('SELECT * FROM account_wallet_links WHERE address=?').bind(address).first();
 // A revocation must not be bypassed by an implicit Phantom identity fallback.
 if(link)return link.active_member_key===member.id&&link.member_id===member.id&&link.revoked_at===null?{kind:'explicit_signature',memberId:member.id,address,changeId:link.change_id}:null;
 return member.provider==='phantom'&&member.subject===address?{kind:'phantom_login',memberId:member.id,address,changeId:null}:null;
}
async function bodyOf(request){
 if(!request.headers.get('Content-Type')?.startsWith('application/json'))throw fail('invalid_request');
 const reader=request.body?.getReader();if(!reader)throw fail('invalid_request');let size=0,text='';const decoder=new TextDecoder();
 while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>4096){await reader.cancel();throw fail('invalid_request');}text+=decoder.decode(value,{stream:true});}
 try{const b=JSON.parse(text+decoder.decode());if(!b||typeof b!=='object'||Array.isArray(b))throw Error();return b;}catch{throw fail('invalid_request');}
}
async function snapshot(DB,member){
 const link=await DB.prepare('SELECT * FROM account_wallet_links WHERE active_member_key=?').bind(member.id).first();
 const own=member.provider==='phantom'?await walletBinding(DB,member,member.subject):null;
 const rows=await DB.prepare('SELECT address,action,created_at FROM account_wallet_audit WHERE member_id=? ORDER BY created_at DESC,id DESC LIMIT 10').bind(member.id).all();
 return {memberId:member.id,binding:link?{address:link.address,verifiedAt:link.verified_at,kind:'explicit_signature'}:own?{address:member.subject,verifiedAt:null,kind:'phantom_login'}:null,history:rows.results,mergesAccounts:false,grantsAccess:false};
}
export async function accountWalletResponse(request,env,member,dependencies={}){
 const url=new URL(request.url),clock=dependencies.clock||Date.now;
 try{
  if(!env.DB||!member?.row)throw fail('account_required',401);
  const current=await env.DB.prepare('SELECT * FROM member_accounts WHERE id=?').bind(member.row.id).first();
  if(!current||current.status!=='active')throw fail('account_suspended',403);
  if(request.method==='GET')return json(await snapshot(env.DB,current));
  if(request.method!=='POST')throw fail('method_not_allowed',405);
  if(request.headers.get('Origin')!==url.origin||request.headers.get('X-ORAKT-Wallet-Link')!=='account')throw fail('cross_origin_request',403);
  const body=await bodyOf(request),now=clock(),bucket=createHash('sha256').update(`wallet-link:${current.id}:${Math.floor(now/60000)}`).digest('hex');
  if(!await env.DB.prepare('INSERT INTO wallet_auth_limits (bucket,count,expires_at) VALUES (?,1,?) ON CONFLICT(bucket) DO UPDATE SET count=count+1 WHERE count<12 RETURNING count').bind(bucket,now+120000).first())throw fail('rate_limited',429);
  if(body.operation==='challenge'){
   if(Object.keys(body).some(k=>!['operation','action','address'].includes(k))||!['link','unlink'].includes(body.action))throw fail('invalid_request');
   let pub;try{pub=new PublicKey(body.address);if(typeof body.address!=='string'||body.address==='11111111111111111111111111111111'||pub.toBase58()!==body.address||!PublicKey.isOnCurve(pub.toBytes()))throw Error();}catch{throw fail('invalid_address');}
   if(current.provider==='phantom'&&current.subject!==body.address)throw fail('use_signin_wallet',409);
   const link=await env.DB.prepare('SELECT * FROM account_wallet_links WHERE address=?').bind(body.address).first();
   const active=await env.DB.prepare('SELECT * FROM account_wallet_links WHERE active_member_key=?').bind(current.id).first();
   if(body.action==='link'){
    if(active)throw fail('account_already_linked',409);
    if(link?.active_member_key)throw fail('wallet_unavailable',409);
    if(await env.DB.prepare("SELECT id FROM member_accounts WHERE provider='phantom' AND subject=? AND id<>?").bind(body.address,current.id).first())throw fail('wallet_has_separate_account',409);
   }else if(!active||active.address!==body.address)throw fail('explicit_binding_required',409);
   const previous=readBrowser(request),browser=/^[a-f0-9]{64}$/.test(previous)?previous:random(),nonce=random(),expiresAt=now+300000;
   const action=body.action==='link'?'LINK':'UNLINK';
   const message=`ORAKT wallet ownership proof\n\nAction: ${action} wallet to account\nAccount: ${current.id}\nWallet: ${body.address}\nOrigin: ${url.origin}\nURI: ${url.origin}/account\nNetwork: Solana\nNonce: ${nonce}\nIssued At: ${new Date(now).toISOString()}\nExpiration Time: ${new Date(expiresAt).toISOString()}\n\nThis is an account binding message, not a login, transaction, token approval or account merge. No funds move and no membership is granted.`;
   await env.DB.batch([
    env.DB.prepare('DELETE FROM account_wallet_challenges WHERE browser=? OR expires_at<=?').bind(browser,now),
    env.DB.prepare('DELETE FROM wallet_auth_limits WHERE expires_at<=?').bind(now),
    env.DB.prepare('INSERT INTO account_wallet_challenges (nonce,browser,member_id,member_revision,address,action,origin,message,expires_at,expected_change_id) VALUES (?,?,?,?,?,?,?,?,?,?)').bind(nonce,browser,current.id,current.revision,body.address,body.action,url.origin,message,expiresAt,active?.change_id||''),
   ]);
   return json({nonce,message,address:body.address,action:body.action,origin:url.origin,memberId:current.id,expiresAt},200,{'Set-Cookie':cookie(browser,300)});
  }
  if(body.operation!=='verify'||Object.keys(body).some(k=>!['operation','nonce','signature'].includes(k))||!/^[a-f0-9]{64}$/.test(body.nonce||'')||!/^[A-Za-z0-9_-]{86}$/.test(body.signature||''))throw fail('invalid_request');
  const browser=readBrowser(request),q=await env.DB.prepare('SELECT * FROM account_wallet_challenges WHERE nonce=? AND browser=? AND member_id=? AND origin=? AND expires_at>?').bind(body.nonce,browser,current.id,url.origin,now).first();
  if(!q)throw fail('challenge_expired_or_used',409);
  const signature=Buffer.from(body.signature,'base64url');if(signature.length!==64||signature.toString('base64url')!==body.signature)throw fail('invalid_signature',401);
  const pub=await crypto.subtle.importKey('raw',new PublicKey(q.address).toBytes(),{name:'Ed25519'},false,['verify']);
  if(!await crypto.subtle.verify('Ed25519',pub,signature,new TextEncoder().encode(q.message)))throw fail('invalid_signature',401);
  const at=clock();
  // Recheck challenge, account revision, address ownership and pending orders INSIDE
  // the atomic batch; logout and concurrent verification cannot reuse a proof.
  const guard=`EXISTS (SELECT 1 FROM account_wallet_challenges c JOIN member_accounts m ON m.id=c.member_id WHERE c.nonce=? AND c.browser=? AND c.member_id=? AND c.origin=? AND c.expires_at>? AND m.status='active' AND m.revision=c.member_revision)`;
  const args=[q.nonce,browser,current.id,url.origin,at];
  const statement=q.action==='link'
   ?env.DB.prepare(`INSERT INTO account_wallet_links (address,member_id,active_member_key,verified_at,revoked_at,change_id) SELECT ?,?,?,?,NULL,? WHERE ${guard} AND NOT EXISTS (SELECT 1 FROM account_wallet_links WHERE active_member_key=?) AND NOT EXISTS (SELECT 1 FROM member_accounts WHERE provider='phantom' AND subject=? AND id<>?) ON CONFLICT(address) DO UPDATE SET member_id=excluded.member_id,active_member_key=excluded.active_member_key,verified_at=excluded.verified_at,revoked_at=NULL,change_id=excluded.change_id WHERE account_wallet_links.active_member_key IS NULL`).bind(q.address,current.id,current.id,at,q.nonce,...args,current.id,q.address,current.id)
   :env.DB.prepare(`UPDATE account_wallet_links SET active_member_key=NULL,revoked_at=?,change_id=? WHERE address=? AND member_id=? AND active_member_key=? AND change_id=? AND ${guard} AND NOT EXISTS (SELECT 1 FROM billing_orders WHERE member_id=? AND payer=? AND status='pending' AND expires_at>?)`).bind(at,q.nonce,q.address,current.id,current.id,q.expected_change_id,...args,current.id,q.address,at);
  const result=await env.DB.batch([
   statement,
   env.DB.prepare('INSERT INTO account_wallet_audit (id,member_id,address,action,message,signature,created_at) SELECT ?,?,?,?,?,?,? WHERE EXISTS (SELECT 1 FROM account_wallet_links WHERE address=? AND member_id=? AND change_id=?) ON CONFLICT(id) DO NOTHING').bind(q.nonce,current.id,q.address,q.action,q.message,body.signature,at,q.address,current.id,q.nonce),
   env.DB.prepare('DELETE FROM account_wallet_challenges WHERE nonce=? AND browser=?').bind(q.nonce,browser),
  ]);
  if(result[0].meta.changes!==1)throw fail('binding_changed_or_pending_order',409);
  return json({...await snapshot(env.DB,current),ok:true},200,{'Set-Cookie':cookie('',0)});
 }catch(e){return json({error:e.status?e.message:'wallet_binding_unavailable'},e.status||503);}
}
