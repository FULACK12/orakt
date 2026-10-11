import {Buffer} from 'node:buffer';
import {publications,publicationHash,canonical,publicPublicationIndex} from './research-publications.mjs';
import {unsignedMemo,validReceipt} from './news-publication.mjs';
import {decodeAddress} from './wallet-auth.mjs';
export const MAINNET_RPC='https://api.mainnet-beta.solana.com';
export const MAINNET_GENESIS='5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d';
export const memoFor=r=>`ORAKT:research:v1:${r.id}:${publicationHash(r)}`;
const json=(v,status=200)=>Response.json(v,{status,headers:{'Cache-Control':'private, no-store'}});
export async function readSmallJson(request,limit=16000){
 if(!request.headers.get('Content-Type')?.startsWith('application/json'))throw Error('json_required');
 const reader=request.body?.getReader();if(!reader)throw Error('body_required');const chunks=[];let size=0;
 while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>limit){await reader.cancel();throw Error('body_too_large');}chunks.push(value);}
 return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}
export async function researchPublicationResponse(request,env,member,fetcher=fetch){
 const url=new URL(request.url),id=url.searchParams.get('id');
 const canRead=r=>r.category==='intelligence'||member.access.permissions.reports||member.access.permissions.research;
 if(request.method==='GET'){
  if(!id)return json({items:publicPublicationIndex().filter(r=>canRead(r)),canAnchor:!!member.access.permissions.manageUsers,network:'solana:mainnet'});
  const report=publications.find(r=>r.id===id);if(!report)return json({error:'not_found'},404);if(!canRead(report))return json({error:'plan_required'},403);
  const hash=publicationHash(report),receipt=await env.DB.prepare('SELECT wallet,signature,confirmed_at AS confirmedAt FROM report_provenance WHERE id=? AND signature IS NOT NULL').bind(hash).first();
  if(url.searchParams.get('format')==='canonical')return new Response(canonical(report),{headers:{'Content-Type':'application/json','Content-Disposition':`attachment; filename="${report.id}.json"`,'Cache-Control':'private, no-store'}});
  return json({report,hash,memo:memoFor(report),receipt,canAnchor:!!member.access.permissions.manageUsers,network:'solana:mainnet',state:receipt?'finalized':'not_anchored'});
 }
 if(request.method!=='POST')return json({error:'method_not_allowed'},405);
 if(!member.access.permissions.manageUsers)return json({error:'admin_required'},403);
 if(request.headers.get('Origin')!==url.origin||request.headers.get('X-ORAKT-Publish')!=='review')return json({error:'same_origin_required'},403);
 try{
  const v=await readSmallJson(request,2500),report=publications.find(r=>r.id===v.id);if(!report||v.hash!==publicationHash(report))return json({error:'exact_published_revision_required'},409);
  const hash=publicationHash(report),memo=memoFor(report);
  const rpc=async(method,params=[])=>{const response=await fetcher(MAINNET_RPC,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:AbortSignal.timeout(12000)});if(!response.ok)throw Error('rpc_unavailable');const value=await response.json();if(value.error)throw Error('rpc_error');return value.result;};
  if(await rpc('getGenesisHash')!==MAINNET_GENESIS)return json({error:'mainnet_mismatch'},503);
  if(v.action==='prepare'){
   decodeAddress(v.wallet);
   const existing=await env.DB.prepare('SELECT signature FROM report_provenance WHERE id=?').bind(hash).first();if(existing?.signature)return json({error:'already_finalized'},409);
   const block=await rpc('getLatestBlockhash',[{commitment:'finalized'}]),tx=unsignedMemo(v.wallet,block.value.blockhash,memo);
   const fee=await rpc('getFeeForMessage',[Buffer.from(tx.slice(65)).toString('base64'),{commitment:'confirmed'}]);
   if(!Number.isSafeInteger(fee?.value)||fee.value<0||fee.value>100000)return json({error:'fee_unavailable_or_exceeds_0_0001_sol_cap'},409);
   const balance=await rpc('getBalance',[v.wallet,{commitment:'confirmed'}]);if(balance?.value<fee.value)return json({error:'insufficient_sol_for_network_fee',feeLamports:fee.value},409);
   await env.DB.prepare('INSERT INTO report_provenance(id,report_id,network,wallet,actor_id,created_at) VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET wallet=excluded.wallet,actor_id=excluded.actor_id WHERE signature IS NULL').bind(hash,report.id,'solana:mainnet',v.wallet,member.row.id,Date.now()).run();
   return json({transaction:Array.from(tx),memo,hash,network:'solana:mainnet',feeLamports:fee.value,lastValidBlockHeight:block.value.lastValidBlockHeight,noTransfer:true});
  }
  if(v.action==='confirm'){
   if(typeof v.signature!=='string'||!/^[1-9A-HJ-NP-Za-km-z]{64,88}$/.test(v.signature))return json({error:'invalid_signature'},400);
   const prepared=await env.DB.prepare('SELECT * FROM report_provenance WHERE id=? AND actor_id=?').bind(hash,member.row.id).first();if(!prepared)return json({error:'prepare_required'},409);
   if(prepared.signature)return prepared.signature===v.signature?json({state:'finalized',signature:v.signature}):json({error:'receipt_conflict'},409);
   const tx=await rpc('getTransaction',[v.signature,{commitment:'finalized',encoding:'jsonParsed',maxSupportedTransactionVersion:0}]);
   if(!validReceipt(tx,prepared,memo))return json({error:'not_finalized_or_mismatched_memo'},409);
   const changed=await env.DB.prepare('UPDATE report_provenance SET signature=?,confirmed_at=? WHERE id=? AND actor_id=? AND wallet=? AND signature IS NULL').bind(v.signature,Date.now(),hash,member.row.id,prepared.wallet).run();
   return changed.meta.changes?json({state:'finalized',signature:v.signature}):json({error:'receipt_conflict'},409);
  }
  return json({error:'invalid_action'},400);
 }catch{return json({error:'publication_or_rpc_unavailable'},503);}
}
