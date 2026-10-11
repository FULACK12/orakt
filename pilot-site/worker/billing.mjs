import {randomUUID,createHash} from 'node:crypto';
import {Buffer} from 'node:buffer';
import {PublicKey,Transaction,Keypair} from '@solana/web3.js';
import {getAssociatedTokenAddressSync,createAssociatedTokenAccountIdempotentInstruction,createTransferCheckedInstruction,TOKEN_PROGRAM_ID} from './solana-payment-instructions.mjs';
import {catalogFor,MERCHANT,MINTS,PRICES,addCalendarMonth,verifyStablecoinReceipt} from './payment-policy.mjs';
import {protocolPolicy,protocolPreviewStatus,verifyProtocolReceipt} from './protocol-receipt.mjs';

const MAINNET_GENESIS='5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d';
const json=(body,status=200)=>Response.json(body,{status,headers:{'Cache-Control':'private, no-store'}});
const fail=(code,status=400)=>Object.assign(Error(code),{status});
export function publicOrder(row){return {id:row.id,plan:row.plan,currency:row.currency,network:row.network,mint:row.mint,recipient:row.recipient,payer:row.payer,reference:row.reference,amountUnits:row.amount_units,amount:String(BigInt(row.amount_units)/1000000n),createdAt:row.created_at,expiresAt:row.expires_at,status:row.status,signature:row.signature,paidAt:row.paid_at,accessFrom:row.access_from,accessUntil:row.access_until};}
function address(value){try{return typeof value==='string'&&new PublicKey(value).toBase58()===value;}catch{return false;}}
function activeTerm(row,now){return row.status==='active'&&['signal','research'].includes(row.plan)&&['onchain_paid','manual_paid','complimentary'].includes(row.grant_kind)&&row.expires_at>now;}
async function smallBody(request){
 if(!request.headers.get('Content-Type')?.startsWith('application/json'))throw fail('invalid_request');
 const reader=request.body?.getReader();if(!reader)throw fail('invalid_request');const d=new TextDecoder();let text='',size=0;
 while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>2048){await reader.cancel();throw fail('invalid_request');}text+=d.decode(value,{stream:true});}
 try{const body=JSON.parse(text+d.decode());if(!body||typeof body!=='object'||Array.isArray(body))throw Error();return body;}catch{throw fail('invalid_request');}
}
async function rate(env,memberId,action,now,limit){
 const bucket=createHash('sha256').update(`billing:${memberId}:${action}:${Math.floor(now/60000)}`).digest('hex');
 if(!await env.DB.prepare('INSERT INTO wallet_auth_limits (bucket, count, expires_at) VALUES (?, 1, ?) ON CONFLICT(bucket) DO UPDATE SET count = count + 1 WHERE count < ? RETURNING count').bind(bucket,now+120000,limit).first())throw fail('rate_limited',429);
}
export function rpcFor(env,fetcher=fetch){return async(method,params=[])=>{
 const endpoint=env.ORAKT_SOLANA_RPC_URL||'https://api.mainnet-beta.solana.com';
 if(new URL(endpoint).protocol!=='https:')throw fail('rpc_unavailable',503);
 let data;try{const r=await fetcher(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:AbortSignal.timeout(12000)});if(!r.ok)throw Error();data=await r.json();}catch{throw fail('rpc_unavailable',503);}
 if(data.error||!Object.hasOwn(data,'result'))throw fail('rpc_unavailable',503);return data.result;
};}
export async function assertMainnet(rpc){if(await rpc('getGenesisHash')!==MAINNET_GENESIS)throw fail('wrong_rpc_network',503);}
export async function preparePayment(order,rpc){
 await assertMainnet(rpc);
 const payer=new PublicKey(order.payer),merchant=new PublicKey(order.recipient),mint=new PublicKey(order.mint);
 const source=getAssociatedTokenAddressSync(mint,payer),destination=getAssociatedTokenAddressSync(mint,merchant);
 const accounts=await rpc('getMultipleAccounts',[[source.toBase58(),destination.toBase58()],{encoding:'jsonParsed',commitment:'finalized'}]);
 const [from,to]=accounts?.value||[],sourceInfo=from?.data?.parsed?.info;
 if(from?.owner!==TOKEN_PROGRAM_ID.toBase58()||sourceInfo?.owner!==order.payer||sourceInfo?.mint!==order.mint||sourceInfo?.tokenAmount?.decimals!==6||!/^\d+$/.test(sourceInfo?.tokenAmount?.amount||'')||BigInt(sourceInfo.tokenAmount.amount)<BigInt(order.amountUnits))throw fail('insufficient_token_balance');
 if(to&&(to.owner!==TOKEN_PROGRAM_ID.toBase58()||to.data?.parsed?.info?.owner!==order.recipient||to.data?.parsed?.info?.mint!==order.mint))throw fail('recipient_account_mismatch',503);
 const latest=await rpc('getLatestBlockhash',[{commitment:'finalized'}]);
 const transaction=new Transaction({feePayer:payer,recentBlockhash:latest.value.blockhash});
 if(!to)transaction.add(createAssociatedTokenAccountIdempotentInstruction(payer,destination,merchant,mint));
 const transfer=createTransferCheckedInstruction(source,mint,destination,payer,BigInt(order.amountUnits),6);
 transfer.keys.push({pubkey:new PublicKey(order.reference),isSigner:false,isWritable:false});transaction.add(transfer);
 const message=Buffer.from(transaction.serializeMessage()).toString('base64');
 const fee=await rpc('getFeeForMessage',[message,{commitment:'finalized'}]);
 const rent=to?0:await rpc('getMinimumBalanceForRentExemption',[165]);
 if(!Number.isSafeInteger(fee?.value)||!Number.isSafeInteger(rent))throw fail('fee_unavailable',503);
 const balance=await rpc('getBalance',[order.payer,{commitment:'finalized'}]);
 if(balance.value<fee.value+rent)throw fail('insufficient_sol_for_fee');
 return {transaction:Buffer.from(transaction.serialize({requireAllSignatures:false,verifySignatures:false})).toString('base64'),network:order.network,recipient:order.recipient,amount:order.amount,currency:order.currency,feeLamports:fee.value,recipientRentLamports:rent,lastValidBlockHeight:latest.value.lastValidBlockHeight};
}
// Atomic durable settlement. A unique signature, conditional revision update and an audit
// row are committed together. A retry can never extend the same payment twice.
export async function settleOrder(DB,orderId,memberId,signature,paidAt,now=Date.now()){
 const order=await DB.prepare('SELECT * FROM billing_orders WHERE id = ? AND member_id = ?').bind(orderId,memberId).first();
 if(!order)throw fail('order_not_found',404);if(order.status==='settled')return publicOrder(order);
 const member=await DB.prepare('SELECT * FROM member_accounts WHERE id = ?').bind(memberId).first();
 if(!member||member.status!=='active')throw fail('account_suspended',403);
 if(activeTerm(member,now)&&member.plan!==order.plan)throw fail('active_plan_changed_contact_support',409);
 const start=activeTerm(member,now)?Math.max(now,member.expires_at):now,end=addCalendarMonth(start),change=`payment:${order.id}`;
 try{
  const result=await DB.batch([
   DB.prepare("UPDATE billing_orders SET status = 'settled', signature = ?, paid_at = ?, access_from = ?, access_until = ?, settlement_revision = ?, active_member_key = NULL WHERE id = ? AND member_id = ? AND status = 'pending' AND EXISTS (SELECT 1 FROM member_accounts WHERE id = ? AND revision = ? AND status = 'active')").bind(signature,paidAt,start,end,member.revision,order.id,memberId,memberId,member.revision),
   DB.prepare("UPDATE member_accounts SET plan = ?, grant_kind = 'onchain_paid', expires_at = ?, revision = revision + 1, last_change_id = ? WHERE id = ? AND revision = ? AND status = 'active' AND EXISTS (SELECT 1 FROM billing_orders WHERE id = ? AND signature = ? AND status = 'settled' AND settlement_revision = ?)").bind(order.plan,end,change,memberId,member.revision,order.id,signature,member.revision),
   DB.prepare("INSERT INTO member_audit (id, actor_id, target_id, before_json, after_json, reason, created_at) SELECT ?, 'solana:settlement', id, ?, ?, 'Finalized Solana stablecoin payment; one calendar month; no automatic renewal', ? FROM member_accounts WHERE id = ? AND last_change_id = ? AND revision = ? ON CONFLICT(id) DO NOTHING").bind(change,JSON.stringify({plan:member.plan,grantKind:member.grant_kind,expiresAt:member.expires_at,revision:member.revision}),JSON.stringify({plan:order.plan,grantKind:'onchain_paid',expiresAt:end,orderId:order.id,signature}),now,memberId,change,member.revision+1),
  ]);
  const saved=await DB.prepare('SELECT * FROM billing_orders WHERE id = ? AND member_id = ?').bind(order.id,memberId).first();
  if(saved.status==='settled')return publicOrder(saved);
  if(result[0].meta.changes!==1)throw fail('revision_conflict_retry',409);
  throw fail('settlement_unavailable',503);
 }catch(e){if(e.status)throw e;const duplicate=await DB.prepare('SELECT id FROM billing_orders WHERE signature = ?').bind(signature).first();if(duplicate)throw fail('payment_already_used',409);throw fail('settlement_unavailable',503);}
}
export async function billingResponse(request,env,member,dependencies={}){
 const url=new URL(request.url),now=dependencies.now??Date.now(),rpc=dependencies.rpc||rpcFor(env),catalog=catalogFor(env);
 if(member.access.status!=='active')return json({error:'account_suspended'},403);
 if(url.pathname==='/api/billing/catalog'&&request.method==='GET')return json({...catalog,currentPlan:member.access.effectivePlan,currentExpiresAt:member.access.expiresAt});
 try{
  if(['/api/billing/protocol-status','/api/billing/protocol-preview'].includes(url.pathname)){
   if(!member.access.permissions.manageUsers)throw fail('admin_required',403);
   if(url.pathname.endsWith('/protocol-status')&&request.method==='GET')return json(protocolPreviewStatus(env));
   if(url.pathname.endsWith('/protocol-status')||request.method!=='POST')throw fail('method_not_allowed',405);
   if(request.headers.get('Origin')!==url.origin||request.headers.get('X-ORAKT-Billing')!=='checkout')throw fail('cross_origin_request',403);
   const policy=protocolPolicy(env),body=await smallBody(request);
   if(!body||typeof body.orderId!=='string'||body.orderId.length>80||typeof body.signature!=='string'||Object.keys(body).some(k=>!['orderId','signature'].includes(k)))throw fail('invalid_request');
   await rate(env,member.row.id,'protocol-preview',now,6);
   const order=await env.DB.prepare('SELECT * FROM billing_orders WHERE id = ?').bind(body.orderId).first();if(!order)throw fail('order_not_found',404);
   const target=await env.DB.prepare('SELECT * FROM member_accounts WHERE id = ?').bind(order.member_id).first();if(!target)throw fail('account_not_found',404);
   const result=await verifyProtocolReceipt({rpc,policy,order,member:target,signature:body.signature,now});
   const fresh=await env.DB.prepare('SELECT * FROM member_accounts WHERE id = ?').bind(order.member_id).first();
   if(!fresh||fresh.revision!==target.revision||fresh.status!=='active'||fresh.provider!==target.provider||fresh.subject!==target.subject)throw fail('account_changed_retry',409);
   const freshOrder=await env.DB.prepare('SELECT * FROM billing_orders WHERE id=?').bind(order.id).first();
   if(!freshOrder||JSON.stringify(freshOrder)!==JSON.stringify(order))throw fail('order_changed_retry',409);
   return json({...result,notice:'preview_only_no_membership_or_payment_state_changed'});
  }
  if(url.pathname==='/api/billing/health'&&request.method==='GET'){
   if(!member.access.permissions.manageUsers)throw fail('admin_required',403);
   await rate(env,member.row.id,'health',now,6);await assertMainnet(rpc);
   await rpc('getSignatureStatuses',[[ '1'.repeat(64) ],{searchTransactionHistory:true}]);
   await rpc('getTransaction',['1'.repeat(64),{encoding:'jsonParsed',commitment:'finalized',maxSupportedTransactionVersion:0}]);
   const check=await rpc('getMultipleAccounts',[[MINTS.USDC,MINTS.USDT],{encoding:'jsonParsed',commitment:'finalized'}]);
   if(check?.value?.length!==2||!check.value.every(a=>a?.owner===TOKEN_PROGRAM_ID.toBase58()&&a?.data?.parsed?.info?.decimals===6))throw fail('token_rpc_check_failed',503);
   return json({ok:true,network:catalog.network,mintsVerified:true,realPaymentTested:false});
  }
  if(url.pathname==='/api/billing/orders'&&request.method==='GET'){
   const rows=await env.DB.prepare('SELECT * FROM billing_orders WHERE member_id = ? ORDER BY created_at DESC LIMIT 20').bind(member.row.id).all();return json({orders:rows.results.map(publicOrder)});
  }
  if(!catalog.enabled)throw fail('payments_not_enabled',503);
  if(request.method!=='POST'||!['/api/billing/orders','/api/billing/prepare','/api/billing/verify'].includes(url.pathname))throw fail('method_not_allowed',405);
  if(request.headers.get('Origin')!==url.origin||request.headers.get('X-ORAKT-Billing')!=='checkout')throw fail('cross_origin_request',403);
  const body=await smallBody(request);await rate(env,member.row.id,url.pathname,now,url.pathname.endsWith('/orders')?5:12);
  if(url.pathname==='/api/billing/orders'){
   if(Object.keys(body).some(k=>!['plan','currency','payer'].includes(k))||!Object.hasOwn(PRICES,body.plan)||!Object.hasOwn(MINTS,body.currency)||!address(body.payer)||!PublicKey.isOnCurve(new PublicKey(body.payer).toBytes())||body.payer===MERCHANT)throw fail('invalid_order');
   if(activeTerm(member.row,now)&&member.row.plan!==body.plan)throw fail('renew_same_plan_only',409);
   await env.DB.prepare('UPDATE billing_orders SET active_member_key = NULL WHERE member_id = ? AND expires_at <= ? AND active_member_key IS NOT NULL').bind(member.row.id,now).run();
   const existing=await env.DB.prepare('SELECT * FROM billing_orders WHERE active_member_key = ?').bind(member.row.id).first();
   if(existing){if(existing.plan!==body.plan||existing.currency!==body.currency||existing.payer!==body.payer)throw fail('pending_order_exists',409);return json({order:publicOrder(existing)});}
   await assertMainnet(rpc);
   const id=randomUUID(),reference=Keypair.generate().publicKey.toBase58(),created=Math.floor(now/1000)*1000;
   // The reference key is just a random public identifier, never a custody account.
   try{await env.DB.prepare('INSERT INTO billing_orders (id, member_id, plan, currency, network, mint, recipient, payer, reference, amount_units, created_at, expires_at, active_member_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)').bind(id,member.row.id,body.plan,body.currency,catalog.network,MINTS[body.currency],MERCHANT,body.payer,reference,String(BigInt(PRICES[body.plan])*1000000n),created,created+30*60000,member.row.id).run();}catch{throw fail('pending_order_exists',409);}
   return json({order:publicOrder(await env.DB.prepare('SELECT * FROM billing_orders WHERE id = ?').bind(id).first())},201);
  }
  if(typeof body.orderId!=='string'||body.orderId.length>80||Object.keys(body).some(k=>!['orderId',...(url.pathname.endsWith('/verify')?['signature']:[])].includes(k)))throw fail('invalid_request');
  const row=await env.DB.prepare('SELECT * FROM billing_orders WHERE id = ? AND member_id = ?').bind(body.orderId,member.row.id).first();if(!row)throw fail('order_not_found',404);
  const order=publicOrder(row);if(order.status==='settled')return json({order});
  if(url.pathname.endsWith('/prepare')){if(now>=order.expiresAt)throw fail('order_expired',409);if(activeTerm(member.row,now)&&member.row.plan!==order.plan)throw fail('renew_same_plan_only',409);return json(await preparePayment(order,rpc));}
  if(body.signature!==undefined&&(typeof body.signature!=='string'||!/^[1-9A-HJ-NP-Za-km-z]{64,88}$/.test(body.signature)))throw fail('invalid_signature');
  await assertMainnet(rpc);
  let signatures=body.signature?[body.signature]:(await rpc('getSignaturesForAddress',[order.reference,{limit:3,commitment:'finalized'}])).filter(x=>!x.err).map(x=>x.signature);
  for(const signature of signatures){
   const statuses=await rpc('getSignatureStatuses',[[signature],{searchTransactionHistory:true}]),status=statuses?.value?.[0];if(status?.confirmationStatus!=='finalized'||status.err!==null)continue;
   const tx=await rpc('getTransaction',[signature,{encoding:'jsonParsed',commitment:'finalized',maxSupportedTransactionVersion:0}]);
   if(tx?.transaction?.signatures?.[0]!==signature)continue;
   const result=verifyStablecoinReceipt(order,tx,status,now);
   if(result.ok)return json({order:await settleOrder(env.DB,order.id,member.row.id,signature,tx.blockTime*1000,now)});
   if(body.signature)throw fail(result.reason,409);
  }
  return json({order,pending:true,message:'not_finalized_do_not_pay_again'},202);
 }catch(e){return json({error:e.status?e.message:'billing_service_unavailable'},e.status||503);}
}
