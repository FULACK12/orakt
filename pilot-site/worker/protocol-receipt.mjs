// Read-only bridge candidate. NEVER settles orders or mutates membership.
import {Buffer} from 'node:buffer';
import {createHash} from 'node:crypto';
import {PublicKey} from '@solana/web3.js';
import {MERCHANT,MINTS,PRICES} from './payment-policy.mjs';
const FIXTURE='BaAX5nB9yxMh5K1tdEserFDq7MMcisVGVNshrVNLqDyn';
const LOADER='BPFLoaderUpgradeab1e11111111111111111111111';
const TOKEN='TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA';
const GENESIS='5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d';
const hash=value=>createHash('sha256').update(value).digest();
const fail=(message,status=409)=>Object.assign(Error(message),{status});
const requireThat=(condition,reason)=>{if(!condition)throw fail(reason);};
const key=value=>new PublicKey(value);
const address=value=>{try{return typeof value==='string'&&key(value).toBase58()===value;}catch{return false;}};
const pda=(program,...seeds)=>PublicKey.findProgramAddressSync(seeds.map(s=>typeof s==='string'?Buffer.from(s):s instanceof PublicKey?s.toBuffer():s),key(program));
const pub=(bytes,offset)=>key(bytes.subarray(offset,offset+32)).toBase58();
export function protocolPolicy(env={}){
 if(env.ORAKT_PROTOCOL_PREVIEW_ENABLED!=='true')throw fail('protocol_preview_disabled',503);
 const programId=env.ORAKT_PROTOCOL_PROGRAM_ID,authority=env.ORAKT_PROTOCOL_AUTHORITY,upgradeAuthority=env.ORAKT_PROTOCOL_UPGRADE_AUTHORITY,governor=env.ORAKT_PROTOCOL_GOVERNOR;
 const slot=env.ORAKT_PROTOCOL_DEPLOY_SLOT;
 if(!address(programId)||programId===FIXTURE||!address(authority)||!address(governor)||!(upgradeAuthority==='none'||address(upgradeAuthority))||!/^\d{1,16}$/.test(slot||'')||!Number.isSafeInteger(Number(slot))||Number(slot)<=0)throw fail('protocol_deployment_not_pinned',503);
 const config=pda(programId,'config',key(authority))[0].toBase58();
 return {programId,authority,governor,upgradeAuthority,deploySlot:Number(slot),config,governance:pda(programId,'governance',key(config))[0].toBase58(),genesis:GENESIS};
}
export function protocolCheckoutPolicy(env={}){
 if(env.ORAKT_PROTOCOL_CHECKOUT_ENABLED!=='true')throw fail('protocol_checkout_disabled',503);
 return protocolPolicy({...env,ORAKT_PROTOCOL_PREVIEW_ENABLED:'true'});
}
// Receipt reconciliation is independently authorized; it never prepares a payment.
export function protocolReconcilePolicy(env={}){
 if(env.ORAKT_PROTOCOL_RECONCILE_ENABLED!=='true'&&env.ORAKT_PROTOCOL_CHECKOUT_ENABLED!=='true')throw fail('protocol_reconciliation_disabled',503);
 return protocolPolicy({...env,ORAKT_PROTOCOL_PREVIEW_ENABLED:'true'});
}
export function protocolCheckoutStatus(env={}){try{const p=protocolCheckoutPolicy(env);return {enabled:true,programId:p.programId,config:p.config,network:'solana:mainnet-beta',mode:'custom_contract'};}catch(e){return {enabled:false,mode:'custom_contract',reason:e.message};}}
export function protocolPreviewStatus(env={}){try{const p=protocolPolicy(env);return {enabled:true,mode:'admin_read_only',grantsAccess:false,programId:p.programId,config:p.config,network:'solana:mainnet-beta'};}catch(e){return {enabled:false,mode:'admin_read_only',grantsAccess:false,reason:e.message};}}
// Canonical commitment to a durable, server-created order. Never an email hash.
export function orderInvoice(order){return hash(JSON.stringify(['orakt-contract-order-v1',order.id,order.member_id,order.reference]));}
export function receiptAddresses(policy,order){
 const plan=order.plan==='signal'?1:2,invoice=orderInvoice(order),config=key(policy.config),buyer=key(order.payer);
 const [receipt,receiptBump]=pda(policy.programId,'receipt',config,buyer,invoice);
 const [subscription,subscriptionBump]=pda(policy.programId,'subscription',config,buyer,Buffer.from([plan]));
 const [programData]=pda(LOADER,key(policy.programId));
 return {plan,invoice,receipt:receipt.toBase58(),receiptBump,subscription:subscription.toBase58(),subscriptionBump,programData:programData.toBase58()};
}
function bytes(account,owner,length,tag,executable=false){
 requireThat(account?.owner===owner&&account.executable===executable&&Array.isArray(account.data)&&account.data[1]==='base64'&&typeof account.data[0]==='string'&&account.data[0].length<=1024,'invalid_protocol_account');
 const data=Buffer.from(account.data[0],'base64');
 requireThat(data.toString('base64')===account.data[0]&&data.length===length,'invalid_protocol_account');
 if(tag)requireThat(data.subarray(0,8).equals(hash('account:'+tag).subarray(0,8)),'account_discriminator_mismatch');
 return data;
}
const alphabet='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
async function verifyGovernance(rpc,policy,slot,forPayment){
 const snap=await rpc('getAccountInfo',[policy.governance,{encoding:'base64',commitment:'finalized',minContextSlot:slot}]);
 requireThat(Number.isSafeInteger(snap?.context?.slot)&&snap.context.slot>=slot,'stale_governance_snapshot');
 const g=bytes(snap.value,policy.programId,138,'Governance');
 requireThat(pub(g,8)===policy.config&&g[137]===pda(policy.programId,'governance',key(policy.config))[1],'governance_mismatch');
 if(forPayment)requireThat(pub(g,40)===policy.governor&&g[136]===1&&g.subarray(104,136).equals(Buffer.alloc(32)),'payments_disabled_or_governance_changed');
 return g;
}
export async function verifyProtocolDeployment(rpc,policy,snapshot){
 requireThat(await rpc('getGenesisHash')===policy.genesis,'wrong_rpc_network');
 const a=receiptAddresses(policy,{plan:'signal',payer:policy.authority,id:'deployment',member_id:'deployment',reference:policy.authority});
 const snap=snapshot||await rpc('getMultipleAccounts',[[policy.programId,policy.config],{encoding:'base64',commitment:'finalized',minContextSlot:policy.deploySlot}]);
 requireThat(Number.isSafeInteger(snap?.context?.slot)&&snap.context.slot>=policy.deploySlot&&snap.value?.length>=2,'stale_account_snapshot');
 const program=bytes(snap.value[0],LOADER,36,null,true);
 requireThat(program.readUInt32LE(0)===2&&pub(program,4)===a.programData,'program_loader_mismatch');
 const metadata=await rpc('getAccountInfo',[a.programData,{encoding:'base64',commitment:'finalized',minContextSlot:snap.context.slot,dataSlice:{offset:0,length:45}}]);
 requireThat(Number.isSafeInteger(metadata?.context?.slot)&&metadata.context.slot>=snap.context.slot,'stale_program_snapshot');
 const pd=bytes(metadata.value,LOADER,45);
 requireThat(pd.readUInt32LE(0)===3&&pd.readBigUInt64LE(4)===BigInt(policy.deploySlot),'program_upgrade_requires_review');
 requireThat((policy.upgradeAuthority==='none'&&pd[12]===0)||(pd[12]===1&&pub(pd,13)===policy.upgradeAuthority),'upgrade_authority_mismatch');
 const config=bytes(snap.value[1],policy.programId,42,'Config');
 requireThat(pub(config,8)===policy.authority&&config[40]===0&&config[41]===pda(policy.programId,'config',key(policy.authority))[1],'config_paused_or_mismatched');
 await verifyGovernance(rpc,policy,metadata.context.slot,true);
 return {slot:metadata.context.slot};
}
export function decodeBase58(value,max=128){
 requireThat(typeof value==='string'&&value.length>0&&value.length<=max,'invalid_base58');
 let n=0n;for(const ch of value){const i=alphabet.indexOf(ch);requireThat(i>=0,'invalid_base58');n=n*58n+BigInt(i);}
 const tail=n?Buffer.from(n.toString(16).padStart(Math.ceil(n.toString(16).length/2)*2,'0'),'hex'):Buffer.alloc(0);
 return Buffer.concat([Buffer.alloc(value.match(/^1*/)[0].length),tail]);
}
function validateOrder(order,member,now,binding){
 requireThat(order?.status==='pending'&&order.member_id===member?.id,'order_not_pending_or_owned');
 requireThat(member.status==='active','account_suspended');
 requireThat(binding===undefined?(member.provider==='phantom'&&member.subject===order.payer):(binding?.memberId===member.id&&binding?.address===order.payer&&['explicit_signature','phantom_login'].includes(binding?.kind)),'verified_wallet_binding_required');
 requireThat(order.network==='solana:mainnet-beta'&&Object.hasOwn(PRICES,order.plan)&&MINTS[order.currency]===order.mint&&order.recipient===MERCHANT&&address(order.payer)&&order.payer!==MERCHANT,'invalid_protocol_order');
 requireThat(order.amount_units===String(BigInt(PRICES[order.plan])*1000000n)&&typeof order.id==='string'&&typeof order.reference==='string'&&address(order.reference),'invalid_protocol_order');
 requireThat(Number.isSafeInteger(now)&&Number.isSafeInteger(order.created_at)&&Number.isSafeInteger(order.expires_at)&&order.expires_at>order.created_at&&order.created_at<=now,'invalid_protocol_order');
}
export async function verifyProtocolReceipt({rpc,policy,order,member,signature,now=Date.now(),binding}){
 validateOrder(order,member,now,binding);
 requireThat(decodeBase58(signature,88).length===64,'invalid_signature');
 requireThat(await rpc('getGenesisHash')===policy.genesis,'wrong_rpc_network');
 const status=(await rpc('getSignatureStatuses',[[signature],{searchTransactionHistory:true}]))?.value?.[0];
 requireThat(status?.confirmationStatus==='finalized'&&status.err===null&&Number.isSafeInteger(status.slot),'not_finalized_or_failed');
 requireThat(policy.deploySlot<=status.slot,'transaction_predates_pinned_deployment');
 const tx=await rpc('getTransaction',[signature,{encoding:'jsonParsed',commitment:'finalized',maxSupportedTransactionVersion:0}]);
 requireThat(tx?.meta?.err===null&&tx.slot===status.slot&&tx.transaction?.signatures?.[0]===signature,'transaction_mismatch');
 requireThat(Number.isSafeInteger(tx.blockTime)&&tx.blockTime*1000>=order.created_at&&tx.blockTime*1000<=order.expires_at&&tx.blockTime*1000<=now,'outside_order_window');
 const a=receiptAddresses(policy,order),message=tx.transaction.message;
 requireThat(message?.accountKeys?.some(k=>k.pubkey===order.payer&&k.signer===true),'payer_signature_missing');
 const calls=message.instructions?.filter(i=>i.programId===policy.programId);
 requireThat(calls?.length===1,'purchase_instruction_missing_or_ambiguous');
 const call=calls[0],data=decodeBase58(call.data);
 requireThat(data.length===58&&data.subarray(0,8).equals(hash('global:purchase').subarray(0,8))&&data[8]===a.plan&&data.subarray(9,41).equals(a.invoice)&&data[41]===1&&data.readBigUInt64LE(42)===BigInt(order.amount_units),'purchase_arguments_mismatch');
 const k=call.accounts;
 requireThat(Array.isArray(k)&&k.length===10&&k[0]===order.payer&&k[1]===policy.config&&k[2]===order.mint&&address(k[3])&&address(k[4])&&k[3]!==k[4]&&k[5]===a.subscription&&k[6]===a.receipt&&k[7]===TOKEN&&k[8]==='11111111111111111111111111111111'&&k[9]===policy.governance,'purchase_accounts_mismatch');
 const snapshot=await rpc('getMultipleAccounts',[[policy.programId,policy.config,a.receipt,a.subscription],{encoding:'base64',commitment:'finalized',minContextSlot:status.slot}]);
 requireThat(Number.isSafeInteger(snapshot?.context?.slot)&&snapshot.context.slot>=status.slot&&snapshot.value?.length===4,'stale_account_snapshot');
 const [programAccount,configAccount,receiptAccount,subAccount]=snapshot.value;
 const programBytes=bytes(programAccount,LOADER,36,null,true);
 requireThat(programBytes.readUInt32LE(0)===2&&pub(programBytes,4)===a.programData,'program_loader_mismatch');
 const metadata=await rpc('getAccountInfo',[a.programData,{encoding:'base64',commitment:'finalized',minContextSlot:snapshot.context.slot,dataSlice:{offset:0,length:45}}]);
 requireThat(Number.isSafeInteger(metadata?.context?.slot)&&metadata.context.slot>=snapshot.context.slot,'stale_program_snapshot');
 const pd=bytes(metadata.value,LOADER,45);
 requireThat(pd.readUInt32LE(0)===3&&pd.readBigUInt64LE(4)===BigInt(policy.deploySlot),'program_upgrade_requires_review');
 requireThat((policy.upgradeAuthority==='none'&&pd[12]===0)||(pd[12]===1&&pub(pd,13)===policy.upgradeAuthority),'upgrade_authority_mismatch');
 const config=bytes(configAccount,policy.programId,42,'Config');
 // Historical finalized payments remain recoverable while new writes/payments
 // are paused or the operational governor rotates; code/upgrade pins still hold.
 requireThat(pub(config,8)===policy.authority&&config[40]<=1&&config[41]===pda(policy.programId,'config',key(policy.authority))[1],'config_paused_or_mismatched');
 await verifyGovernance(rpc,policy,metadata.context.slot,false);
 const r=bytes(receiptAccount,policy.programId,163,'Receipt'),s=bytes(subAccount,policy.programId,82,'Subscription');
 requireThat(pub(r,8)===policy.config&&pub(r,40)===order.payer&&r.subarray(72,104).equals(a.invoice)&&pub(r,104)===order.mint&&r.readBigUInt64LE(136)===BigInt(order.amount_units)&&r[144]===a.plan&&r[145]===1&&r[162]===a.receiptBump,'receipt_order_mismatch');
 const paidAt=r.readBigInt64LE(146),expiresAt=r.readBigInt64LE(154),deadline=data.readBigInt64LE(50),nowSec=BigInt(Math.floor(now/1000));
 requireThat(paidAt*1000n>=BigInt(order.created_at)&&paidAt*1000n<=BigInt(order.expires_at)&&paidAt<=nowSec&&paidAt>=BigInt(tx.blockTime)-60n&&paidAt<=BigInt(tx.blockTime)+60n&&deadline>=paidAt&&deadline<=paidAt+600n,'receipt_time_mismatch');
 requireThat(expiresAt>nowSec&&expiresAt>paidAt&&expiresAt<13569465600n,'receipt_expired_or_invalid');
 requireThat(pub(s,8)===policy.config&&pub(s,40)===order.payer&&s[72]===a.plan&&s.readBigInt64LE(73)>=expiresAt&&s[81]===a.subscriptionBump,'subscription_mismatch');
 // Independent exact source/destination delta check, in addition to program-owned receipt.
 const delta=(rows,account,owner)=>{const ix=message.accountKeys.findIndex(x=>x.pubkey===account);const matches=rows?.filter(b=>b.accountIndex===ix);requireThat(ix>=0&&matches?.length===1,'token_balance_missing');const b=matches[0];requireThat(b.owner===owner&&b.mint===order.mint&&b.uiTokenAmount?.decimals===6&&/^\d+$/.test(b.uiTokenAmount.amount),'token_balance_mismatch');return BigInt(b.uiTokenAmount.amount);};
 const pre=tx.meta.preTokenBalances,post=tx.meta.postTokenBalances,amount=BigInt(order.amount_units);
 requireThat(delta(pre,k[3],order.payer)-delta(post,k[3],order.payer)===amount&&delta(post,k[4],MERCHANT)-delta(pre,k[4],MERCHANT)===amount,'payment_delta_mismatch');
 return {verified:true,mode:'admin_read_only',grantsAccess:false,memberId:member.id,memberRevision:member.revision,signature,receipt:a.receipt,plan:order.plan,expiresAt:Number(expiresAt)*1000,paidAt:Number(paidAt)*1000,amountUnits:order.amount_units,network:'solana:mainnet-beta',programId:policy.programId,checkedSlot:metadata.context.slot};
}
