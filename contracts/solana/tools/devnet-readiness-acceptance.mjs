// Explicit read-only public Devnet acceptance. Mutations below are IN MEMORY ONLY.
// Never invoked by CI; no keypair, sendTransaction, or account-writing API.
import assert from 'node:assert/strict';
import {readDevnetReadiness,inspectSnapshot} from './devnet-readiness.mjs';
let retained;
try {
  const observed=await readDevnetReadiness(async(url,options)=>{
    const r=await fetch(url,options);
    if(JSON.parse(options.body).method==='getMultipleAccounts' && r.ok)retained=(await r.clone().json()).result;
    return r;
  });
  const genesis='EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG';
  assert.equal(observed.reviewRequired,false);
  const checks=['finalized deployed binary, PDA, ownership and payment-OFF state match'];
  function mutate(account,offset,change){const s=structuredClone(retained),b=Buffer.from(s.value[account].data[0],'base64');b[offset]=change(b[offset]);s.value[account].data[0]=b.toString('base64');return s;}
  for(const [name,account,offset,reason] of [
    ['tampered binary',1,45,/binary_changed/],['changed deployment slot',1,4,/deployment_changed/],
    ['changed upgrade authority',1,13,/upgrade_authority_changed/],['substituted ProgramData',0,4,/programdata_address_mismatch/],
    ['substituted config namespace',2,8,/config_mismatch/],['wrong config discriminator',2,0,/discriminator/],
    ['substituted governance namespace',3,8,/governance_mismatch/],['wrong governance bump',3,137,/governance_mismatch/]
  ]){assert.throws(()=>inspectSnapshot(genesis,mutate(account,offset,b=>b^1)),reason);checks.push('reject '+name);}
  for(const [name,account,offset] of [['payment switch',3,136],['pause',2,40],['pending recovery',3,104],['governor',3,40],['guardian',3,72]]){
    const r=inspectSnapshot(genesis,mutate(account,offset,b=>b^1));assert.equal(r.reviewRequired,true);assert.equal(r.productionReady,false);checks.push('flag '+name+' drift');
  }
  const stale=structuredClone(retained);stale.context.slot=0;assert.throws(()=>inspectSnapshot(genesis,stale),/stale/);checks.push('reject stale snapshot');
  console.log(JSON.stringify({status:'passed',observed,checks,checksPassed:checks.length,mutationScope:'in-memory copies only; public accounts unchanged',transactionsSent:0},null,2));
}catch(e){console.error(JSON.stringify({status:'unverified_or_failed',error:e.message,transactionsSent:0}));process.exitCode=1;}
