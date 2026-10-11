// Contract orders are separate from legacy SPL transfers. All public mutations
// require authenticated ownership; only server-fetched finalized evidence grants access.
import {randomUUID,createHash} from 'node:crypto';
import {Buffer} from 'node:buffer';
import {PublicKey,Transaction,TransactionInstruction,Keypair,SystemProgram} from '@solana/web3.js';
import {MERCHANT,MINTS,PRICES} from './payment-policy.mjs';
import {protocolCheckoutPolicy,protocolReconcilePolicy,receiptAddresses,verifyProtocolDeployment,verifyProtocolReceipt} from './protocol-receipt.mjs';
import {walletBinding} from './account-wallet.mjs';
import {getAssociatedTokenAddressSync,TOKEN_PROGRAM_ID} from './solana-payment-instructions.mjs';
const fail=(message,status=409)=>Object.assign(Error(message),{status});
const check=(ok,reason)=>{if(!ok)throw fail(reason);};
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const active=m=>m.status==='active'&&['signal','research'].includes(m.plan)&&['onchain_paid','manual_paid','complimentary'].includes(m.grant_kind);
const hash=s=>createHash('sha256').update(s).digest();
function requirePlan(m,plan,now){check(!(active(m)&&m.expires_at>now&&m.plan!==plan),'active_plan_changed_contact_support');}
// Never charge to overwrite a longer legacy/manual/complimentary term. Migration
// is explicit; this gate never fabricates chain credit or changes account grants.
export async function requireRenewalCoverage(member,order,policy,rpc,now){
 const a=receiptAddresses(policy,order);
 const snap=await rpc('getAccountInfo',[a.subscription,{encoding:'base64',commitment:'finalized',minContextSlot:policy.deploySlot}]);
 check(Number.isSafeInteger(snap?.context?.slot)&&snap.context.slot>=policy.deploySlot,'stale_subscription_snapshot');
 let until=0;
 if(snap.value){const account=snap.value;check(account.owner===policy.programId&&Array.isArray(account.data)&&account.data[1]==='base64','subscription_mismatch');
  const s=Buffer.from(account.data[0],'base64');check(s.length===82&&s.subarray(0,8).equals(hash('account:Subscription').subarray(0,8))&&new PublicKey(s.subarray(8,40)).toBase58()===policy.config&&new PublicKey(s.subarray(40,72)).toBase58()===order.payer&&s[72]===a.plan&&s[81]===a.subscriptionBump,'subscription_mismatch');
  const end=s.readBigInt64LE(73);check(end>=0n&&end<13569465600n,'subscription_mismatch');until=Number(end)*1000;
 }
 check(!(active(member)&&member.expires_at>now&&member.expires_at>until),'existing_term_requires_migration');
 return Math.max(now,until);
}
function bindingGuard(binding){return binding.kind==='explicit_signature'
 ?{sql:'EXISTS (SELECT 1 FROM account_wallet_links WHERE address=? AND member_id=? AND active_member_key=? AND revoked_at IS NULL AND change_id=?)',args:[binding.address,binding.memberId,binding.memberId,binding.changeId]}
 :{sql:"EXISTS (SELECT 1 FROM member_accounts WHERE id=? AND provider='phantom' AND subject=?) AND NOT EXISTS (SELECT 1 FROM account_wallet_links WHERE address=?)",args:[binding.memberId,binding.address,binding.address]};}
export function purchaseInstruction(policy,order){
 const a=receiptAddresses(policy,order),payer=new PublicKey(order.payer),mint=new PublicKey(order.mint);
 const source=getAssociatedTokenAddressSync(mint,payer),treasury=getAssociatedTokenAddressSync(mint,new PublicKey(MERCHANT));
 const data=Buffer.alloc(58);hash('global:purchase').copy(data,0,0,8);data[8]=a.plan;a.invoice.copy(data,9);data[41]=1;data.writeBigUInt64LE(BigInt(order.amount_units),42);data.writeBigInt64LE(BigInt(Math.floor(order.expires_at/1000)),50);
 const keys=[{pubkey:payer,isSigner:true,isWritable:true},...[policy.config,order.mint,source.toBase58(),treasury.toBase58(),a.subscription,a.receipt,TOKEN_PROGRAM_ID.toBase58(),SystemProgram.programId.toBase58(),policy.governance].map((p,i)=>({pubkey:new PublicKey(p),isSigner:false,isWritable:[2,3,4,5].includes(i)}))];
 return new TransactionInstruction({programId:new PublicKey(policy.programId),keys,data});
}
export async function prepareProtocolPayment(order,policy,rpc,now=Date.now()){
 check(order.payment_method==='protocol'&&now<order.expires_at&&order.expires_at-now<=600000,'order_expired');
 const deployed=await verifyProtocolDeployment(rpc,policy),ix=purchaseInstruction(policy,order),a=receiptAddresses(policy,order);
 // Require an existing merchant ATA. Creating it in the purchase transaction would
 // make exact pre/post balance verification ambiguous; operator setup is separate.
 const result=await rpc('getMultipleAccounts',[[ix.keys[3].pubkey.toBase58(),ix.keys[4].pubkey.toBase58(),a.subscription,a.receipt],{encoding:'jsonParsed',commitment:'finalized',minContextSlot:deployed.slot}]);
 check(Number.isSafeInteger(result?.context?.slot)&&result.context.slot>=deployed.slot&&result.value?.length===4,'stale_account_snapshot');
 const [source,destination,sub,receipt]=result.value;
 for(const [account,owner]of [[source,order.payer],[destination,MERCHANT]]){const i=account?.data?.parsed?.info;check(account?.owner===TOKEN_PROGRAM_ID.toBase58()&&i?.owner===owner&&i?.mint===order.mint&&i?.state==='initialized'&&i?.tokenAmount?.decimals===6&&/^\d+$/.test(i.tokenAmount.amount),owner===MERCHANT?'merchant_token_account_not_ready':'source_token_account_invalid');}
 check(BigInt(source.data.parsed.info.tokenAmount.amount)>=BigInt(order.amount_units),'insufficient_token_balance');
 check(!receipt,'receipt_exists_verify_original_order');check(!sub||sub.owner===policy.programId,'subscription_owner_mismatch');
 const latest=await rpc('getLatestBlockhash',[{commitment:'finalized'}]);
 const tx=new Transaction({feePayer:new PublicKey(order.payer),recentBlockhash:latest.value.blockhash}).add(ix);
 const fee=await rpc('getFeeForMessage',[Buffer.from(tx.serializeMessage()).toString('base64'),{commitment:'finalized'}]);
 const rentReceipt=await rpc('getMinimumBalanceForRentExemption',[163]),rentSub=sub?0:await rpc('getMinimumBalanceForRentExemption',[82]);
 check([fee?.value,rentReceipt,rentSub].every(v=>Number.isSafeInteger(v)&&v>=0),'fee_unavailable');
 const rent=rentReceipt+rentSub,balance=await rpc('getBalance',[order.payer,{commitment:'finalized'}]);check(balance?.value>=fee.value+rent,'insufficient_sol_for_fee');
 const serialized=Buffer.from(tx.serialize({requireAllSignatures:false,verifySignatures:false})).toString('base64');
 const simulated=await rpc('simulateTransaction',[serialized,{encoding:'base64',commitment:'finalized',sigVerify:false,replaceRecentBlockhash:true}]);check(simulated?.value?.err===null,'contract_simulation_failed');
 await verifyProtocolDeployment(rpc,policy); // Fail closed if an upgrade/pause was observed during preparation.
 return {transaction:serialized,network:order.network,recipient:order.recipient,amount:String(BigInt(order.amount_units)/1000000n),currency:order.currency,feeLamports:fee.value,recipientRentLamports:rent,protocolRentLamports:rent,lastValidBlockHeight:latest.value.lastValidBlockHeight,programId:policy.programId,config:policy.config,receipt:a.receipt,invoice:a.invoice.toString('hex'),expiresAt:order.expires_at,autoRenew:false};
}
export async function createProtocolOrder(DB,policy,member,body,rpc,now){
 check(Object.keys(body).every(k=>['plan','currency','payer'].includes(k))&&Object.hasOwn(PRICES,body.plan)&&Object.hasOwn(MINTS,body.currency),'invalid_order');
 let payer;try{payer=new PublicKey(body.payer);check(typeof body.payer==='string'&&payer.toBase58()===body.payer&&PublicKey.isOnCurve(payer.toBytes())&&body.payer!==MERCHANT,'invalid_order');}catch{throw fail('invalid_order');}
 const current=await DB.prepare('SELECT * FROM member_accounts WHERE id=?').bind(member.id).first();check(current?.status==='active','account_suspended');requirePlan(current,body.plan,now);
 const binding=await walletBinding(DB,current,body.payer);check(binding,'verified_wallet_binding_required');
 await DB.prepare('UPDATE billing_orders SET active_member_key=NULL WHERE member_id=? AND expires_at<=? AND active_member_key IS NOT NULL').bind(member.id,now).run();
 const pending=await DB.prepare('SELECT * FROM billing_orders WHERE active_member_key=?').bind(member.id).first();
 if(pending){check(pending.payment_method==='protocol'&&pending.plan===body.plan&&pending.currency===body.currency&&pending.payer===body.payer,'pending_order_exists');const saved=await DB.prepare('SELECT * FROM protocol_orders WHERE order_id=?').bind(pending.id).first();check(saved&&saved.policy_json===JSON.stringify(policy)&&saved.binding_json===JSON.stringify(binding),'protocol_order_configuration_changed');return pending;}
 await verifyProtocolDeployment(rpc,policy);
 const order={id:randomUUID(),member_id:member.id,plan:body.plan,currency:body.currency,network:'solana:mainnet-beta',mint:MINTS[body.currency],recipient:MERCHANT,payer:body.payer,reference:Keypair.generate().publicKey.toBase58(),amount_units:String(BigInt(PRICES[body.plan])*1000000n),created_at:Math.floor(now/1000)*1000,expires_at:Math.floor(now/1000)*1000+600000,payment_method:'protocol',status:'pending'};
 const a=receiptAddresses(policy,order),guard=bindingGuard(binding);
 await requireRenewalCoverage(current,order,policy,rpc,now);
 try{await DB.batch([
  DB.prepare(`INSERT INTO billing_orders (id,member_id,plan,currency,network,mint,recipient,payer,reference,amount_units,created_at,expires_at,active_member_key,payment_method) SELECT ?,?,?,?,?,?,?,?,?,?,?,?,?,'protocol' WHERE EXISTS (SELECT 1 FROM member_accounts WHERE id=? AND revision=? AND status='active') AND ${guard.sql}`).bind(order.id,member.id,order.plan,order.currency,order.network,order.mint,order.recipient,order.payer,order.reference,order.amount_units,order.created_at,order.expires_at,member.id,member.id,current.revision,...guard.args),
  DB.prepare('INSERT INTO protocol_orders (order_id,policy_json,binding_json,invoice,receipt,subscription,created_at) SELECT ?,?,?,?,?,?,? WHERE EXISTS (SELECT 1 FROM billing_orders WHERE id=?)').bind(order.id,JSON.stringify(policy),JSON.stringify(binding),a.invoice.toString('hex'),a.receipt,a.subscription,now,order.id),
 ]);}catch{throw fail('pending_order_exists');}
 const saved=await DB.prepare('SELECT * FROM billing_orders WHERE id=?').bind(order.id).first();check(saved,'account_changed_retry');return saved;
}
// Only called with proof produced internally by verifyProtocolReceipt, never client JSON.
export async function settleProtocolOrder(DB,order,protocol,member,proof,now){
 check(proof.verified===true&&proof.memberId===member.id&&proof.memberRevision===member.revision&&proof.receipt===protocol.receipt&&proof.plan===order.plan&&proof.amountUnits===order.amount_units&&proof.expiresAt>now&&proof.network===order.network&&proof.programId===JSON.parse(protocol.policy_json).programId,'invalid_settlement_evidence');
 check(member.status==='active','account_suspended');requirePlan(member,order.plan,now);
 const binding=JSON.parse(protocol.binding_json),guard=bindingGuard(binding),change='protocol:'+order.id;
 // Mirror the actual contract expiry, never add another month on retry or late reconciliation.
 const end=active(member)&&member.expires_at>now?Math.max(member.expires_at,proof.expiresAt):proof.expiresAt;
 try{const r=await DB.batch([
  DB.prepare(`UPDATE billing_orders SET status='settled',signature=?,paid_at=?,access_from=?,access_until=?,settlement_revision=?,active_member_key=NULL WHERE id=? AND member_id=? AND payment_method='protocol' AND status='pending' AND EXISTS (SELECT 1 FROM member_accounts WHERE id=? AND revision=? AND status='active') AND EXISTS (SELECT 1 FROM protocol_orders WHERE order_id=? AND policy_json=? AND binding_json=? AND receipt=?) AND ${guard.sql}`).bind(proof.signature,proof.paidAt,proof.paidAt,proof.expiresAt,member.revision,order.id,member.id,member.id,member.revision,order.id,protocol.policy_json,protocol.binding_json,protocol.receipt,...guard.args),
  DB.prepare("INSERT INTO protocol_settlements (receipt,order_id,signature,member_id,proof_json,settled_at) SELECT ?,?,?,?,?,? WHERE EXISTS (SELECT 1 FROM billing_orders WHERE id=? AND signature=? AND status='settled' AND settlement_revision=?) AND EXISTS (SELECT 1 FROM member_accounts WHERE id=? AND revision=?)").bind(proof.receipt,order.id,proof.signature,member.id,JSON.stringify(proof),now,order.id,proof.signature,member.revision,member.id,member.revision),
  DB.prepare("UPDATE member_accounts SET plan=?,grant_kind='onchain_paid',expires_at=?,revision=revision+1,last_change_id=? WHERE id=? AND revision=? AND status='active' AND EXISTS (SELECT 1 FROM protocol_settlements WHERE order_id=? AND signature=? AND settled_at=?)").bind(order.plan,end,change,member.id,member.revision,order.id,proof.signature,now),
  DB.prepare("INSERT INTO member_audit (id,actor_id,target_id,before_json,after_json,reason,created_at) SELECT ?,'solana:protocol-settlement',?,?,?,?,? WHERE EXISTS (SELECT 1 FROM member_accounts WHERE id=? AND last_change_id=? AND revision=?) ON CONFLICT(id) DO NOTHING").bind(change,member.id,JSON.stringify(member),JSON.stringify({plan:order.plan,grantKind:'onchain_paid',expiresAt:end,receiptExpiresAt:proof.expiresAt,orderId:order.id,signature:proof.signature,receipt:proof.receipt}), 'Finalized pinned contract receipt; expiry mirrored once; no automatic charge',now,member.id,change,member.revision+1),
 ]);if(r[0].meta.changes!==1)throw fail('account_or_binding_changed_retry');
 }catch(e){const saved=await DB.prepare('SELECT * FROM billing_orders WHERE id=? AND member_id=?').bind(order.id,member.id).first();if(saved?.status==='settled'&&saved.signature===proof.signature)return saved;if(e.status)throw e;const used=await DB.prepare('SELECT * FROM protocol_settlements WHERE receipt=? OR signature=?').bind(proof.receipt,proof.signature).first();if(used)throw fail('payment_already_used');throw fail('settlement_unavailable',503);}
 return DB.prepare('SELECT * FROM billing_orders WHERE id=? AND member_id=?').bind(order.id,member.id).first();
}
export async function protocolCheckoutAction(path,body,env,member,rpc,now){
 const policy=path==='/api/billing/protocol/verify'?protocolReconcilePolicy(env):protocolCheckoutPolicy(env);
 if(path==='/api/billing/protocol/orders')return {order:await createProtocolOrder(env.DB,policy,member.row,body,rpc,now)};
 check(['/api/billing/protocol/prepare','/api/billing/protocol/verify'].includes(path),'method_not_allowed');
 check(typeof body.orderId==='string'&&body.orderId.length<=80&&Object.keys(body).every(k=>['orderId',...(path.endsWith('/verify')?['signature']:[])].includes(k)),'invalid_request');
 const order=await env.DB.prepare('SELECT * FROM billing_orders WHERE id=? AND member_id=?').bind(body.orderId,member.row.id).first();check(order?.payment_method==='protocol','order_not_found');
 if(order.status==='settled')return {order};
 const protocol=await env.DB.prepare('SELECT * FROM protocol_orders WHERE order_id=?').bind(order.id).first();check(protocol&&protocol.policy_json===JSON.stringify(policy),'protocol_order_configuration_changed');
 const current=await env.DB.prepare('SELECT * FROM member_accounts WHERE id=?').bind(member.row.id).first();check(current?.status==='active','account_suspended');
 const binding=await walletBinding(env.DB,current,order.payer);check(binding&&same(binding,JSON.parse(protocol.binding_json)),'wallet_binding_changed_retry');
 if(path.endsWith('/prepare')){requirePlan(current,order.plan,now);await requireRenewalCoverage(current,order,policy,rpc,now);const prepared=await prepareProtocolPayment(order,policy,rpc,now);const fresh=await env.DB.prepare('SELECT * FROM member_accounts WHERE id=?').bind(current.id).first();check(fresh?.revision===current.revision&&fresh.status==='active'&&fresh.expires_at===current.expires_at,'account_changed_retry');return prepared;}
 if(body.signature!==undefined)check(typeof body.signature==='string'&&/^[1-9A-HJ-NP-Za-km-z]{64,88}$/.test(body.signature),'invalid_signature');
 const candidates=body.signature?[body.signature]:(await rpc('getSignaturesForAddress',[protocol.receipt,{limit:5,commitment:'finalized'}])).filter(x=>!x.err).map(x=>x.signature);
 for(const signature of candidates){let proof;try{proof=await verifyProtocolReceipt({rpc,policy,order,member:current,signature,now,binding});}catch(e){if(e.message==='not_finalized_or_failed')continue;if(body.signature)throw e;continue;}
  return {order:await settleProtocolOrder(env.DB,order,protocol,current,proof,now)};
 }
 return {order,pending:true,message:'not_finalized_do_not_pay_again'};
}
