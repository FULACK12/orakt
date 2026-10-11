import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {Keypair,PublicKey} from '@solana/web3.js';
import {protocolPolicy,receiptAddresses} from '../worker/protocol-receipt.mjs';
import {MERCHANT,MINTS,addCalendarMonth} from '../worker/payment-policy.mjs';
// Synthetic RPC responses only: no network calls, funded wallets or production receipts.
const now=Date.UTC(2026,9,11,12),key=()=>Keypair.generate().publicKey.toBase58();
const LOADER='BPFLoaderUpgradeab1e11111111111111111111111',TOKEN='TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA';
const hash=s=>createHash('sha256').update(s).digest();
const alphabet='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
function encode(b){let n=BigInt('0x'+b.toString('hex')),s='';while(n){s=alphabet[Number(n%58n)]+s;n/=58n;}let z=0;while(z<b.length&&b[z]===0)z++;return '1'.repeat(z)+s;}
const put=(b,at,p)=>new PublicKey(p).toBuffer().copy(b,at);
const account=(b,owner,executable=false)=>({owner,executable,data:[b.toString('base64'),'base64']});
function fixture(currency='USDC',plan='research'){
 const env={ORAKT_PROTOCOL_PREVIEW_ENABLED:'true',ORAKT_PROTOCOL_PROGRAM_ID:key(),ORAKT_PROTOCOL_AUTHORITY:key(),ORAKT_PROTOCOL_UPGRADE_AUTHORITY:key(),ORAKT_PROTOCOL_DEPLOY_SLOT:'90'};
 const policy=protocolPolicy(env),payer=key(),member={id:'member-fixture',provider:'phantom',subject:payer,status:'active',revision:0};
 const order={id:'order-fixture',member_id:member.id,reference:key(),payer,plan,currency,mint:MINTS[currency],recipient:MERCHANT,network:'solana:mainnet-beta',amount_units:plan==='signal'?'19000000':'79000000',created_at:now-60000,expires_at:now+1200000,status:'pending'};
 const a=receiptAddresses(policy,order),paidAt=now/1000-10,expiry=addCalendarMonth(paidAt*1000)/1000,signature=encode(Buffer.alloc(64,7));
 const program=Buffer.alloc(36);program.writeUInt32LE(2);put(program,4,a.programData);
 const metadata=Buffer.alloc(45);metadata.writeUInt32LE(3);metadata.writeBigUInt64LE(90n,4);metadata[12]=1;put(metadata,13,policy.upgradeAuthority);
 const config=Buffer.alloc(42);hash('account:Config').copy(config,0,0,8);put(config,8,policy.authority);config[41]=PublicKey.findProgramAddressSync([Buffer.from('config'),new PublicKey(policy.authority).toBuffer()],new PublicKey(policy.programId))[1];
 const receipt=Buffer.alloc(163);hash('account:Receipt').copy(receipt,0,0,8);put(receipt,8,policy.config);put(receipt,40,payer);a.invoice.copy(receipt,72);put(receipt,104,order.mint);receipt.writeBigUInt64LE(BigInt(order.amount_units),136);receipt[144]=a.plan;receipt[145]=1;receipt.writeBigInt64LE(BigInt(paidAt),146);receipt.writeBigInt64LE(BigInt(expiry),154);receipt[162]=a.receiptBump;
 const sub=Buffer.alloc(82);hash('account:Subscription').copy(sub,0,0,8);put(sub,8,policy.config);put(sub,40,payer);sub[72]=a.plan;sub.writeBigInt64LE(BigInt(expiry),73);sub[81]=a.subscriptionBump;
 const instruction=Buffer.alloc(58);hash('global:purchase').copy(instruction,0,0,8);instruction[8]=a.plan;a.invoice.copy(instruction,9);instruction[41]=1;instruction.writeBigUInt64LE(BigInt(order.amount_units),42);instruction.writeBigInt64LE(BigInt(paidAt+300),50);
 const accounts=[payer,policy.config,order.mint,key(),key(),a.subscription,a.receipt,TOKEN,'11111111111111111111111111111111'];
 const bal=(accountIndex,owner,amount)=>({accountIndex,owner,mint:order.mint,uiTokenAmount:{amount,decimals:6}});
 const tx={slot:100,blockTime:paidAt,transaction:{signatures:[signature],message:{accountKeys:accounts.map((pubkey,i)=>({pubkey,signer:i===0})),instructions:[{programId:policy.programId,accounts,data:encode(instruction)}]}},meta:{err:null,preTokenBalances:[bal(3,payer,order.amount_units),bal(4,MERCHANT,'0')],postTokenBalances:[bal(3,payer,'0'),bal(4,MERCHANT,order.amount_units)]}};
 const responses={getGenesisHash:policy.genesis,getSignatureStatuses:{value:[{confirmationStatus:'finalized',err:null,slot:100}]},getTransaction:tx,getMultipleAccounts:{context:{slot:101},value:[account(program,LOADER,true),account(config,policy.programId),account(receipt,policy.programId),account(sub,policy.programId)]},getAccountInfo:{context:{slot:102},value:account(metadata,LOADER)}};
 const calls=[];const rpc=async(method,args)=>{calls.push([method,args]);assert.ok(Object.hasOwn(responses,method),'unexpected RPC '+method);return responses[method];};
 return{env,policy,order,member,signature,now,rpc,calls,responses,tx,a,bytes:{program,metadata,config,receipt,sub,instruction},refresh(){responses.getMultipleAccounts.value=[account(program,LOADER,true),account(config,policy.programId),account(receipt,policy.programId),account(sub,policy.programId)];responses.getAccountInfo.value=account(metadata,LOADER);tx.transaction.message.instructions[0].data=encode(instruction);}};
}
export {fixture,now,key,put,encode};
