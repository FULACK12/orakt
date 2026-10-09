import {DEVNET_RPC,DEVNET_GENESIS} from './solana-network.mjs';
import {createHash,randomUUID} from 'node:crypto';
import {decodeAddress} from './wallet-auth.mjs';
const json=(v,s=200)=>Response.json(v,{status:s,headers:{'Cache-Control':'private, no-store'}});
const MEMO='MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr';
const RPC=DEVNET_RPC;
const GENESIS=DEVNET_GENESIS;
export const newsMemo=r=>`ORAKT:news:v1:${r.id}:${r.content_hash}`;
export function newsHash(v){return createHash('sha256').update(JSON.stringify({title:v.title,body:v.body,sourceUrls:v.sourceUrls,eventDate:v.eventDate})).digest('hex');}
export function validSource(v){try{const u=new URL(v);return u.protocol==='https:'&&!u.username&&!u.password&&u.hostname.includes('.')&&v.length<=1200;}catch{return false;}}
async function input(request){
 if(request.headers.get('Origin')!==new URL(request.url).origin||request.headers.get('X-ORAKT-News')!=='review'||!request.headers.get('Content-Type')?.startsWith('application/json'))throw {status:403,error:'same_origin_required'};
 const reader=request.body?.getReader();if(!reader)throw {status:400,error:'invalid_body'};let size=0,out='';const dec=new TextDecoder();
 while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>24000){await reader.cancel();throw {status:413,error:'body_too_large'};}out+=dec.decode(value,{stream:true});}
 try{return JSON.parse(out+dec.decode());}catch{throw {status:400,error:'invalid_json'};}
}
async function rpc(method,params=[]){const response=await fetch(RPC,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:AbortSignal.timeout(12000)});if(!response.ok)throw Error('rpc_unavailable');const v=await response.json();if(v.error)throw Error('rpc_error');return v.result;}
const short=n=>{const out=[];do{let b=n&127;n>>=7;out.push(b|(n?128:0));}while(n);return out;};
export function unsignedMemo(wallet,blockhash,memo){const text=new TextEncoder().encode(memo);return new Uint8Array([1,...new Uint8Array(64),1,0,1,2,...decodeAddress(wallet),...decodeAddress(MEMO),...decodeAddress(blockhash),1,1,1,0,...short(text.length),...text]);}
export function validReceipt(tx,row,expectedMemo=newsMemo(row)){
 const keys=tx?.transaction?.message?.accountKeys,ix=tx?.transaction?.message?.instructions;
 return tx?.meta?.err===null&&Array.isArray(keys)&&keys[0]?.pubkey===row.wallet&&keys[0]?.signer===true&&keys.filter(k=>k.signer).length===1&&Array.isArray(ix)&&ix.length===1&&ix[0].programId===MEMO&&ix[0].parsed===expectedMemo;
}
const publicRow=r=>({id:r.id,title:r.title,body:r.body,sourceUrls:JSON.parse(r.source_urls),eventDate:r.event_date,state:r.state,contentHash:r.content_hash,reviewNote:r.review_note,createdAt:r.created_at,reviewedAt:r.reviewed_at,chainState:r.signature?'finalized':'not_anchored',signature:r.signature,network:'solana:devnet',memo:newsMemo(r)});
export async function newsPublicationResponse(request,env,member){
 const admin=member.access.permissions.manageUsers,actor=member.row.id;
 try{
  if(request.method==='GET'){
   const result=await env.DB.prepare(admin?'SELECT * FROM news_submissions ORDER BY created_at DESC LIMIT 100':"SELECT * FROM news_submissions WHERE author_id=? OR state='approved' ORDER BY created_at DESC LIMIT 100").bind(...(admin?[]:[actor])).all();
   return json({items:result.results.map(r=>({...publicRow(r),canAnchor:admin||r.author_id===actor})),canReview:admin,checkedAt:new Date().toISOString(),source:'live_database',network:'solana:devnet'});
  }
  if(request.method!=='POST')return json({error:'method_not_allowed'},405);
  const v=await input(request);
  if(v.action==='submit'){
   if(v.rightsConfirmed!==true||typeof v.title!=='string'||v.title.trim().length<5||v.title.length>200||typeof v.body!=='string'||v.body.trim().length<80||v.body.length>10000||!Array.isArray(v.sourceUrls)||!v.sourceUrls.length||v.sourceUrls.length>5||!v.sourceUrls.every(validSource)||!/^\d{4}-\d{2}-\d{2}$/.test(v.eventDate)||!Number.isFinite(Date.parse(v.eventDate))||new Date(v.eventDate).toISOString().slice(0,10)!==v.eventDate||v.eventDate>new Date().toISOString().slice(0,10))return json({error:'invalid_submission'},400);
   const recent=await env.DB.prepare('SELECT count(*) AS n FROM news_submissions WHERE author_id=? AND created_at>?').bind(actor,Date.now()-86400000).first();if(recent.n>=10)return json({error:'daily_submission_limit'},429);
   const normalized={title:v.title.trim(),body:v.body.trim(),sourceUrls:[...new Set(v.sourceUrls)],eventDate:v.eventDate};const hash=newsHash(normalized);
   const existing=await env.DB.prepare('SELECT id FROM news_submissions WHERE author_id=? AND content_hash=?').bind(actor,hash).first();if(existing)return json({id:existing.id,state:'already_submitted'});
   const id=randomUUID();await env.DB.prepare("INSERT INTO news_submissions(id,author_id,title,body,source_urls,event_date,content_hash,state,created_at) VALUES(?,?,?,?,?,?,?,'pending',?)").bind(id,actor,normalized.title,normalized.body,JSON.stringify(normalized.sourceUrls),normalized.eventDate,hash,Date.now()).run();return json({id,state:'pending'},201);
  }
  if(typeof v.id!=='string')return json({error:'id_required'},400);
  const row=await env.DB.prepare('SELECT * FROM news_submissions WHERE id=?').bind(v.id).first();if(!row||(!admin&&row.author_id!==actor))return json({error:'not_found'},404);
  if(v.action==='review'){
   if(!admin)return json({error:'reviewer_required'},403);
   if(!['approved','rejected','changes_requested'].includes(v.decision)||typeof v.note!=='string'||v.note.trim().length<10||v.note.length>2000)return json({error:'review_reason_required'},400);
   const result=await env.DB.prepare("UPDATE news_submissions SET state=?,review_note=?,reviewer_id=?,reviewed_at=? WHERE id=? AND state='pending'").bind(v.decision,v.note.trim(),actor,Date.now(),row.id).run();return result.meta.changes?json({state:v.decision}):json({error:'review_conflict'},409);
  }
  if(row.state!=='approved')return json({error:'approved_news_required'},409);
  if(v.action==='prepare'){
   try{decodeAddress(v.wallet);}catch{return json({error:'invalid_wallet'},400);}
   if(row.signature)return json({error:'already_finalized'},409);
   if(await rpc('getGenesisHash')!==GENESIS)return json({error:'network_mismatch'},503);
   const block=await rpc('getLatestBlockhash',[{commitment:'finalized'}]);
   await env.DB.prepare('UPDATE news_submissions SET wallet=? WHERE id=? AND signature IS NULL').bind(v.wallet,row.id).run();
   return json({transaction:Array.from(unsignedMemo(v.wallet,block.value.blockhash,newsMemo(row))),memo:newsMemo(row),network:'solana:devnet',lastValidBlockHeight:block.value.lastValidBlockHeight});
  }
  if(v.action==='confirm'){
   if(typeof v.signature!=='string'||!/^[1-9A-HJ-NP-Za-km-z]{64,88}$/.test(v.signature)||!row.wallet)return json({error:'invalid_signature'},400);
   if(await rpc('getGenesisHash')!==GENESIS)return json({error:'network_mismatch'},503);
   const tx=await rpc('getTransaction',[v.signature,{commitment:'finalized',encoding:'jsonParsed',maxSupportedTransactionVersion:0}]);
   if(!tx)return json({error:'not_finalized_yet'},409);
   if(!validReceipt(tx,row))return json({error:'receipt_does_not_match_approved_content'},409);
   const result=await env.DB.prepare('UPDATE news_submissions SET signature=? WHERE id=? AND signature IS NULL AND wallet=?').bind(v.signature,row.id,row.wallet).run();
   return result.meta.changes||row.signature===v.signature?json({state:'finalized',signature:v.signature}):json({error:'receipt_conflict'},409);
  }
  return json({error:'invalid_action'},400);
 }catch(e){return json({error:e.error||'news_service_unavailable'},e.status||503);}
}
