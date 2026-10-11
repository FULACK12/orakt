import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture,now,key,put} from './protocol-fixture.mjs';
import {verifyProtocolDeployment,verifyProtocolReceipt} from '../worker/protocol-receipt.mjs';
import {requireRenewalCoverage,createProtocolOrder} from '../worker/protocol-checkout.mjs';
import {memberDatabase} from './member-fixture.mjs';
import {memberFor} from '../worker/membership.mjs';

test('legacy/manual/complimentary active term cannot buy overlapping chain term',async()=>{
 for(const grant_kind of ['manual_paid','complimentary','onchain_paid']){
  const f=fixture();f.member={...f.member,plan:'research',grant_kind,expires_at:now+90*86400000};
  await assert.rejects(requireRenewalCoverage(f.member,f.order,f.policy,f.rpc,now),/existing_term_requires_migration/);
 }
});
test('unexpired aligned chain renewal and expired service are accepted, invalid chain data is not',async()=>{
 const f=fixture();f.member={...f.member,plan:'research',grant_kind:'onchain_paid',expires_at:Number(f.bytes.sub.readBigInt64LE(73))*1000};
 const account={owner:f.policy.programId,data:[f.bytes.sub.toString('base64'),'base64']};
 const rpc=async()=>({context:{slot:103},value:account});
 assert.equal(await requireRenewalCoverage(f.member,f.order,f.policy,rpc,now),f.member.expires_at);
 f.member.expires_at+=1;await assert.rejects(requireRenewalCoverage(f.member,f.order,f.policy,rpc,now),/requires_migration/);
 f.member.expires_at=now-1;assert.equal(await requireRenewalCoverage(f.member,f.order,f.policy,f.rpc,now),now);
 account.owner=key();await assert.rejects(requireRenewalCoverage(f.member,f.order,f.policy,rpc,now),/subscription_mismatch/);
});
test('90-day existing membership blocks order creation before billing records are inserted',async t=>{
 const {DB,sql}=memberDatabase();t.after(()=>sql.close());const f=fixture();
 const m=await memberFor({DB},{provider:'google',subject:'v145',accountId:'v145',displayName:'Test'});
 sql.prepare("UPDATE member_accounts SET plan='research',grant_kind='complimentary',expires_at=? WHERE id=?").run(now+90*86400000,m.row.id);
 sql.prepare('INSERT INTO account_wallet_links(address,member_id,active_member_key,verified_at,change_id) VALUES (?,?,?,?,?)').run(f.order.payer,m.row.id,m.row.id,now-1,'test');
 await assert.rejects(createProtocolOrder(DB,f.policy,m.row,{plan:'research',currency:'USDC',payer:f.order.payer},f.rpc,now),/requires_migration/);
 assert.equal(sql.prepare('SELECT count(*) n FROM billing_orders').get().n,0);
});
for(const mode of ['paused','payment-off','recovery-pending','governor-rotated'])test(`new charge blocked but original finalized receipt recoverable: ${mode}`,async()=>{
 const f=fixture();if(mode==='paused')f.bytes.config[40]=1;
 if(mode==='payment-off')f.bytes.governance[136]=0;
 if(mode==='recovery-pending')put(f.bytes.governance,104,key());
 if(mode==='governor-rotated')put(f.bytes.governance,40,key());
 f.refresh();await assert.rejects(verifyProtocolDeployment(f.rpc,f.policy),/paused|payments_disabled/);
 assert.equal((await verifyProtocolReceipt(f)).verified,true);
});
test('recovery still rejects unreviewed code upgrade and substituted governance',async()=>{
 const f=fixture();f.bytes.config[40]=1;f.bytes.metadata.writeBigUInt64LE(91n,4);f.refresh();
 await assert.rejects(verifyProtocolReceipt(f),/upgrade_requires_review/);
 f.bytes.metadata.writeBigUInt64LE(90n,4);put(f.bytes.governance,8,key());f.refresh();
 await assert.rejects(verifyProtocolReceipt(f),/governance_mismatch/);
});
