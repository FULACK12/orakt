import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {workspaceAccess} from '../worker/research-tiers.mjs';
import {mapChains} from '../worker/map-chains.mjs';
import {assetLinks} from '../worker/asset-links.mjs';
import {paymentCatalog,verifyStablecoinReceipt,MERCHANT,MINTS} from '../worker/payment-policy.mjs';
import {memberDatabase} from './member-fixture.mjs';
import {memberFor} from '../worker/membership.mjs';
const access=t=>({status:'active',permissions:{reports:t!=='explorer',research:t==='research'}});
test('map grants are 0/1/5 and free responses contain no premium coordinates',()=>{
 const supply={asOf:'2026-10-01',sites:['AAPL','MU','TSM','INTC'].map(contextTicker=>({contextTicker,coordinates:[10,20],sourceUrl:'https://example.com/source',nearestPort:{name:'Port',longitude:11,latitude:21},sourceExcerpt:'Published source'}))};
 for(const [tier,n] of [['explorer',0],['signal',1],['research',5]]){const result=mapChains(access(tier),{id:'hormuz',nodes:[]},supply);assert.equal(workspaceAccess(access(tier)).chains.mapLimit,n);assert.equal(result.chains.length,n);assert.equal(result.limit,n);}
 assert.equal(mapChains({status:'suspended',permissions:{research:true}}, {},supply).chains.length,0);
});
test('news-asset links require reviewed content and remain unverified candidates',()=>{
 const item={id:'one',state:'approved',payload:{title:'Apple earnings',summary:'Review',claims:[],sources:['https://example.com']},anchors:[]};
 const result=assetLinks({items:[item,{...item,id:'pending',state:'pending'},{...item,id:'withdrawn',state:'retracted'}]});assert.equal(result.executionEnabled,false);assert.deepEqual(result.assets[0].links.map(x=>x.id),['one']);assert.equal(result.assets[0].mint,'XsbEhLAtcf6HdfpFZ5xEMdqW8nfAvcsP5bdudRLJzJp');assert.equal(result.assets[1].mint,null);assert.equal(result.assets[0].links[0].status,'keyword_candidate_unverified');
});
const order={network:'solana:mainnet-beta',currency:'USDC',reference:'order-reference',mint:MINTS.USDC,payer:'payer',recipient:MERCHANT,amountUnits:'19000000',createdAt:100000,expiresAt:200000};
function tx(){const balance=(owner,amount)=>({owner,mint:MINTS.USDC,uiTokenAmount:{amount,decimals:6}});return {blockTime:150,transaction:{message:{accountKeys:[{pubkey:'order-reference'},{pubkey:'payer',signer:true}]}},meta:{err:null,preTokenBalances:[balance('payer','19000000')],postTokenBalances:[balance(MERCHANT,'19000000'),balance('payer','0')]}};}
const status={confirmationStatus:'finalized',err:null};
test('checkout fails closed; receipt checks require finality and exact settled amounts',()=>{assert.equal(paymentCatalog.enabled,false);assert.equal(paymentCatalog.recipient,MERCHANT);assert.equal(verifyStablecoinReceipt(order,tx(),status,210000).ok,true);for(const patch of [{recipient:'other'},{payer:'merchant'},{mint:'fake'},{amountUnits:'19000001'},{network:'solana:devnet'},{createdAt:NaN},{expiresAt:120000}])assert.equal(verifyStablecoinReceipt({...order,...patch},tx(),status,210000).ok,false);assert.equal(verifyStablecoinReceipt(order,tx(),{...status,confirmationStatus:'confirmed'},210000).ok,false);const failed=tx();failed.meta.err={error:'failed'};assert.equal(verifyStablecoinReceipt(order,failed,status,210000).ok,false);});
test('archived report expansion does not subscribe to nested toggle events',()=>{const source=readFileSync(new URL('../app/EvidenceChains.tsx',import.meta.url),'utf8');assert.doesNotMatch(source,/onToggle/);assert.match(source,/useMemo/);assert.match(source,/EnglishEvidenceDigest/);});
test('map glyphs and interface versions are consistent',()=>{const source=readFileSync(new URL('../app/PilotDashboard.tsx',import.meta.url),'utf8');assert.match(source,/glyphs:/);assert.doesNotMatch(source,/Open Sans Bold/);assert.match(source,/Noto Sans Regular/);const version=readFileSync(new URL('../app/ReleaseStatus.tsx',import.meta.url),'utf8').match(/VERSION = "(\d+)"/)[1];assert.ok(readFileSync(new URL('../worker/index.ts',import.meta.url),'utf8').includes(`version: "${version}"`));});
test('real worker routes enforce map tiers, keep payments closed, and require login',async t=>{
 const {DB,sql}=memberDatabase();t.after(()=>sql.close());const env={DB,PILOT_SESSION_SECRET:'local-test-only'},ctx={waitUntil(){},passThroughOnException(){}},app=(await import('../dist/server/index.js')).default;
 const req=(path,auth=true)=>new Request('https://orakt.test'+path,{headers:auth?{'oai-authenticated-user-id':'reader','oai-authenticated-user-email':'test@example.invalid'}:{}});
 for(const path of ['/api/map-chains','/api/asset-intelligence','/api/billing/catalog'])assert.equal((await app.fetch(req(path,false),env,ctx)).status,401);
 let v=await (await app.fetch(req('/api/map-chains'),env,ctx)).json();assert.equal(v.limit,0);assert.deepEqual(v.chains,[]);
 await memberFor(env,{provider:'chatgpt',subject:'reader',displayName:'Reader',accountId:'reader',createdAt:null});
for(const [plan,limit] of [['signal',1],['research',5]]){sql.prepare("UPDATE member_accounts SET plan=?,grant_kind='complimentary',expires_at=? WHERE subject='reader'").run(plan,Date.now()+86400000);v=await (await app.fetch(req('/api/map-chains'),env,ctx)).json();assert.equal(v.limit,limit);assert.equal(v.chains.length,5); /* catalog choices; simultaneous selection remains 1 / 5 */}
 assert.equal((await (await app.fetch(req('/api/billing/catalog'),env,ctx)).json()).enabled,false);
 assert.equal((await app.fetch(req('/api/billing/confirm?paid=true'),env,ctx)).status,503);
 const assets=await (await app.fetch(req('/api/asset-intelligence'),env,ctx)).json();assert.equal(assets.executionEnabled,false);assert.equal(assets.assets.length,7);
});
