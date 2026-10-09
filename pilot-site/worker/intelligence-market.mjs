import {DEVNET_RPC,DEVNET_GENESIS} from './solana-network.mjs';
import {randomUUID} from 'node:crypto';
import {Buffer} from 'node:buffer';
import {decodeAddress} from './wallet-auth.mjs';
import {unsignedMemo,validReceipt,validSource} from './news-publication.mjs';
import {KINDS,hash,contributor,reputation,verification,intelligenceMemo} from './intelligence-policy.mjs';
const json=(v,status=200)=>Response.json(v,{status,headers:{'Cache-Control':'private, no-store'}});
const RPC=DEVNET_RPC,GENESIS=DEVNET_GENESIS;
async function rpc(method,params=[]){const r=await fetch(RPC,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:AbortSignal.timeout(12000)});if(!r.ok)throw Error('rpc');const p=await r.json();if(p.error)throw Error('rpc');return p.result;}
async function input(request){
 if(request.headers.get('Origin')!==new URL(request.url).origin||request.headers.get('X-ORAKT-Intelligence')!=='review'||!request.headers.get('Content-Type')?.startsWith('application/json'))throw {status:403,error:'same_origin_required'};
 const reader=request.body?.getReader();if(!reader)throw {status:400,error:'invalid_body'};const parts=[];let size=0;
 while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>3000000){await reader.cancel();throw {status:413,error:'payload_too_large'};}parts.push(value);}
 try{return JSON.parse(Buffer.concat(parts).toString('utf8'));}catch{throw {status:400,error:'invalid_json'};}
}
function attachment(v){
 if(!v)return {bytes:null,metadata:null};
 if(typeof v.base64!=='string'||!/^[A-Za-z0-9+/]+={0,2}$/.test(v.base64))throw {status:400,error:'invalid_attachment'};
 const bytes=Buffer.from(v.base64,'base64');if(!bytes.length||bytes.length>2*1024*1024)throw {status:413,error:'attachment_limit_2mb'};
 // Always downloaded as an attachment, never rendered as executable content.
 const types=['image/jpeg','image/png','image/webp','application/pdf','text/plain','text/csv','application/json'];
 if(!types.includes(v.type))throw {status:400,error:'unsupported_file_type'};
 return {bytes,metadata:{sha256:hash(bytes),size:bytes.length,declaredType:v.type,byteVerification:'server_received_original_bytes',safetyScan:'not_performed'}};
}
const visible=(r,actor,admin)=>admin||r.author_id===actor||r.state==='approved';
export async function intelligenceResponse(request,env,member){
 const actor=member.row.id,admin=member.access.permissions.manageUsers,url=new URL(request.url);
 try{
  if(request.method==='GET'&&url.pathname.endsWith('/asset')){
   const row=await env.DB.prepare('SELECT * FROM intelligence_items WHERE id=?').bind(url.searchParams.get('id')).first();
   if(!row||!visible(row,actor,admin)||!row.asset_key)return json({error:'not_found'},404);
   const object=await env.BUCKET?.get(row.asset_key);if(!object)return json({error:'asset_unavailable'},404);
   return new Response(object.body,{headers:{'Content-Type':'application/octet-stream','Content-Disposition':'attachment; filename="orakt-source.bin"','X-Content-Type-Options':'nosniff','Cache-Control':'private, no-store'}});
  }
  if(request.method==='GET'){
   const rows=(await env.DB.prepare(admin?'SELECT * FROM intelligence_items ORDER BY created_at DESC LIMIT 20':"SELECT * FROM intelligence_items WHERE author_id=? OR state='approved' OR (state IN ('disputed','retracted') AND EXISTS(SELECT 1 FROM intelligence_history h WHERE h.item_id=intelligence_items.id AND json_extract(h.record,'$.state')='approved')) ORDER BY created_at DESC LIMIT 20").bind(...(admin?[]:[actor])).all()).results;
   const items=[];
   for(const r of rows){
    const history=(await env.DB.prepare('SELECT record,hash,previous_hash FROM intelligence_history WHERE item_id=? ORDER BY revision').bind(r.id).all()).results;
    const anchors=(await env.DB.prepare('SELECT revision,head_hash,signature FROM intelligence_anchors WHERE item_id=? AND signature IS NOT NULL ORDER BY revision').bind(r.id).all()).results;
    const withdrawn=!admin&&r.author_id!==actor&&r.state!=='approved';
    const payload=JSON.parse(r.payload);
    items.push({id:r.id,kind:r.kind,payload:withdrawn?{title:'Content withdrawn / 内容已撤回',summary:'An earlier published verdict was disputed or retracted. Original content is no longer public. / 此前已发布结论有争议或已撤回，原始内容不再公开。',eventDate:payload.eventDate,sources:[],claims:[]}:payload,contentHash:r.content_hash,state:r.state,verdict:r.verdict,revision:r.revision,headHash:r.head_hash,contributor:contributor(r.author_id),createdAt:r.created_at,history:history.map(h=>{const record=JSON.parse(h.record);return {record:withdrawn?{revision:record.revision,action:record.action,at:record.at,actor:record.actor,contentHash:record.contentHash,previousHash:record.previousHash}:record,hash:h.hash,previousHash:h.previous_hash,redacted:withdrawn};}),anchors,canReview:admin&&actor!==r.author_id,canAnchor:admin||actor===r.author_id,hasAttachment:!withdrawn&&!!r.asset_key,ai:{state:'not_run',confidence:null}});
   }
   const own=(await env.DB.prepare('SELECT state,verdict FROM intelligence_items WHERE author_id=?').bind(actor).all()).results;
   return json({items,ownReputation:reputation(own),checkedAt:new Date().toISOString(),uploadEnabled:!!env.BUCKET,network:'solana:devnet'});
  }
  if(request.method!=='POST')return json({error:'method_not_allowed'},405);
  const v=await input(request);
  if(v.action==='submit'){
   if(!KINDS.includes(v.kind)||v.rightsConfirmed!==true||typeof v.title!=='string'||v.title.trim().length<5||v.title.length>200||typeof v.summary!=='string'||v.summary.trim().length<80||v.summary.length>10000||!Array.isArray(v.sources)||v.sources.length<1||v.sources.length>5||!v.sources.every(validSource)||!Array.isArray(v.claims)||v.claims.length<1||v.claims.length>8||v.claims.some(c=>typeof c!=='string'||c.trim().length<10||c.length>1000)||!/^\d{4}-\d{2}-\d{2}$/.test(v.eventDate)||!Number.isFinite(Date.parse(v.eventDate))||new Date(v.eventDate).toISOString().slice(0,10)!==v.eventDate||v.eventDate>new Date().toISOString().slice(0,10))return json({error:'invalid_submission'},400);
   const n=await env.DB.prepare('SELECT count(*) n FROM intelligence_items WHERE author_id=? AND created_at>?').bind(actor,Date.now()-86400000).first();if(n.n>=10)return json({error:'daily_limit'},429);
   const file=attachment(v.attachment);if(file.bytes&&!env.BUCKET)return json({error:'uploads_unavailable'},503);
   const payload={schema:'intelligence-source/v1',kind:v.kind,title:v.title.trim(),summary:v.summary.trim(),sources:[...new Set(v.sources)].sort(),claims:v.claims.map(c=>c.trim()),eventDate:v.eventDate,attachment:file.metadata,externalSourceBytesVerified:false};
   const contentHash=hash(payload),duplicate=await env.DB.prepare('SELECT id FROM intelligence_items WHERE content_hash=?').bind(contentHash).first();if(duplicate)return json({error:'duplicate_content'},409);
   const id=randomUUID(),createdAt=Date.now(),record={schema:'intelligence-history/v1',itemId:id,revision:0,action:'submitted',actor:contributor(actor),at:createdAt,contentHash,payload,previousHash:null},headHash=hash(record),assetKey=file.bytes?'intelligence/'+id+'/original':null;
   if(assetKey)await env.BUCKET.put(assetKey,file.bytes,{httpMetadata:{contentType:'application/octet-stream'}});
   try{await env.DB.batch([
    env.DB.prepare("INSERT INTO intelligence_items(id,author_id,kind,payload,content_hash,asset_key,state,verdict,revision,head_hash,created_at) VALUES(?,?,?,?,?,?,'pending','unresolved',0,?,?)").bind(id,actor,v.kind,JSON.stringify(payload),contentHash,assetKey,headHash,createdAt),
    env.DB.prepare('INSERT INTO intelligence_history(id,item_id,revision,record,hash,previous_hash,created_at) VALUES(?,?,0,?,?,NULL,?)').bind(randomUUID(),id,JSON.stringify(record),headHash,createdAt)
   ]);}catch(e){if(assetKey)await env.BUCKET.delete(assetKey);throw e;}
   return json({id,state:'pending',contentHash,headHash,aiState:'not_run'},201);
  }
  if(typeof v.id!=='string')return json({error:'id_required'},400);
  const r=await env.DB.prepare('SELECT * FROM intelligence_items WHERE id=?').bind(v.id).first();if(!r||(!admin&&r.author_id!==actor))return json({error:'not_found'},404);
  if(v.action==='review'){
   if(!admin)return json({error:'reviewer_required'},403);
   if(!Number.isInteger(v.revision)||v.revision!==r.revision)return json({error:'revision_conflict'},409);
   if(r.revision>=100)return json({error:'history_limit'},409);
   const result=verification(v,actor,r.author_id),at=Date.now(),record={schema:'intelligence-history/v1',itemId:r.id,revision:r.revision+1,action:'reviewed',actor:contributor(actor),at,contentHash:r.content_hash,previousHash:r.head_hash,...result},headHash=hash(record);
   await env.DB.batch([
    env.DB.prepare('INSERT INTO intelligence_history(id,item_id,revision,record,hash,previous_hash,created_at) VALUES(?,?,?,?,?,?,?)').bind(randomUUID(),r.id,r.revision+1,JSON.stringify(record),headHash,r.head_hash,at),
    env.DB.prepare('UPDATE intelligence_items SET state=?,verdict=?,revision=?,head_hash=? WHERE id=? AND revision=?').bind(result.state,result.verdict,r.revision+1,headHash,r.id,r.revision)
   ]);return json({state:result.state,revision:r.revision+1,headHash});
  }
  // Retractions and disputes can be anchored too: old confirmations must not erase them.
  if(r.revision<1)return json({error:'review_required'},409);
  if(v.revision!==r.revision)return json({error:'revision_conflict'},409);
  if(v.action==='prepare'){
   try{decodeAddress(v.wallet);}catch{return json({error:'invalid_wallet'},400);}
   if(await rpc('getGenesisHash')!==GENESIS)return json({error:'network_mismatch'},503);
   const block=await rpc('getLatestBlockhash',[{commitment:'finalized'}]);
   await env.DB.prepare('INSERT INTO intelligence_anchors(item_id,revision,head_hash,wallet,created_at) VALUES(?,?,?,?,?) ON CONFLICT(item_id,revision) DO UPDATE SET wallet=excluded.wallet WHERE signature IS NULL').bind(r.id,r.revision,r.head_hash,v.wallet,Date.now()).run();
   return json({transaction:Array.from(unsignedMemo(v.wallet,block.value.blockhash,intelligenceMemo(r))),network:'solana:devnet',memo:intelligenceMemo(r)});
  }
  if(v.action==='confirm'){
   if(typeof v.signature!=='string'||!/^[1-9A-HJ-NP-Za-km-z]{64,88}$/.test(v.signature))return json({error:'invalid_signature'},400);
   const anchor=await env.DB.prepare('SELECT * FROM intelligence_anchors WHERE item_id=? AND revision=?').bind(r.id,r.revision).first();if(!anchor||anchor.head_hash!==r.head_hash)return json({error:'prepare_required'},409);
   if(await rpc('getGenesisHash')!==GENESIS)return json({error:'network_mismatch'},503);
   const tx=await rpc('getTransaction',[v.signature,{commitment:'finalized',encoding:'jsonParsed',maxSupportedTransactionVersion:0}]);
   if(!validReceipt(tx,{wallet:anchor.wallet},intelligenceMemo(r)))return json({error:'receipt_not_finalized_or_mismatch'},409);
   const updated=await env.DB.prepare('UPDATE intelligence_anchors SET signature=? WHERE item_id=? AND revision=? AND wallet=? AND signature IS NULL').bind(v.signature,r.id,r.revision,anchor.wallet).run();
   return updated.meta.changes||anchor.signature===v.signature?json({state:'finalized',signature:v.signature}):json({error:'receipt_conflict'},409);
  }
  return json({error:'invalid_action'},400);
 }catch(e){return json({error:e.error||'intelligence_service_unavailable'},e.status||503);}
}
