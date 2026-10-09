import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {aaplxProfile as p,aaplxReport as r,effectiveMultiplier} from '../worker/aaplx-research.mjs';
import {assetLinks} from '../worker/asset-links.mjs';
import {memberDatabase} from './member-fixture.mjs';
const evidence=JSON.parse(readFileSync(new URL('../private-data/aaplx-evidence-v135.json',import.meta.url)));
test('AAPLx identity is matched to an issuer-listed Solana mainnet mint, separate from provenance',()=>{
 assert.equal(p.mint,'XsbEhLAtcf6HdfpFZ5xEMdqW8nfAvcsP5bdudRLJzJp');assert.equal(p.isin,'CH1436219187');assert.equal(p.underlyingIsin,'US0378331005');
 assert.equal(p.network,'solana:mainnet-beta');assert.equal(p.provenanceNetwork,'solana:devnet');assert.equal(p.mintStatus,'issuer_and_mainnet_matched');assert.equal(p.executionEnabled,false);
 assert.equal(p.deployments.length,12);assert.equal(p.solana.decimals,8);assert.equal(p.solana.standard,'spl-token-2022');assert.equal(p.solana.paused,false);
 for(const label of ['Mint authority','Freeze authority','Permanent delegate','Pause authority'])assert.ok(p.solana.authorities.find(x=>x.label===label).address);
 const assets=assetLinks({items:[]});assert.equal(assets.assets[0].mint,p.mint);assert.equal(assets.assets[0].network,p.network);assert.equal(assets.assets[1].mint,null);
});
test('effective multiplier handles the activation boundary rather than trusting pending values',()=>{
 const config={multiplier:1.2,newMultiplier:1.3,newMultiplierEffectiveTimestamp:100};
 assert.equal(effectiveMultiplier(config,'1970-01-01T00:01:39Z'),1.2);assert.equal(effectiveMultiplier(config,'1970-01-01T00:01:40Z'),1.3);assert.equal(effectiveMultiplier(config,'1970-01-01T00:01:41Z'),1.3);assert.equal(effectiveMultiplier(null,new Date().toISOString()),null);
 assert.equal(p.solana.multiplier,p.metrics.issuerMultiplier);
});
test('captured measurements retain provenance and distinguish incompatible supply scopes',()=>{
 assert.equal(p.capturedAt,evidence.capturedAt);assert.equal(p.metrics.indicativePrice,evidence.evidence.price.data.quote);
 assert.equal(p.metrics.reserves.sharesHeld,evidence.evidence.reserves.data.sharesHeld);assert.notEqual(p.metrics.circulatingSupply,p.solana.baseSupply);
 for(const item of p.evidence){assert.match(item.sha256,/^[a-f0-9]{64}$/);assert.ok(Date.parse(item.retrievedAt));assert.ok(item.url.startsWith('https://'));}
 assert.equal(p.evidence.length,7);assert.equal(p.gaps.length,4);assert.equal(p.metrics.reserveRatio,undefined);
});
test('ten bilingual report sections cite resolvable sources and do not turn research into approval',()=>{
 assert.equal(r.sections.length,10);assert.equal(new Set(r.sections.map(x=>x.id)).size,10);assert.equal(r.investmentApproved,false);assert.equal(r.executionEnabled,false);
 assert.ok(Date.parse(r.generatedAt)>=Date.parse(p.capturedAt));
 for(const s of r.sections){assert.ok(s.title.zh&&s.title.en&&s.body.zh&&s.body.en);assert.ok(s.sources.length);for(const id of s.sources)assert.ok(p.sources.find(x=>x.id===id));}
 assert.match(r.sections.find(x=>x.id==='reserves').body.en,/not a reserve audit/);assert.match(r.sections.find(x=>x.id==='liquidity').body.en,/No reliable DEX/);
});
test('production worker authenticates profiles and gates report payloads by actual membership',async t=>{
 const {DB,sql}=memberDatabase();t.after(()=>sql.close());const app=(await import('../dist/server/index.js')).default,env={DB,PILOT_SESSION_SECRET:'local-test-only'},ctx={waitUntil(){},passThroughOnException(){}};
 const req=(path,auth=true)=>new Request('https://orakt.test'+path,{headers:auth?{'oai-authenticated-user-id':'aaplx-reader','oai-authenticated-user-email':'aaplx@example.invalid'}:{}});
 for(const path of ['/api/aaplx-profile','/api/aaplx-report'])assert.equal((await app.fetch(req(path,false),env,ctx)).status,401);
 let response=await app.fetch(req('/api/aaplx-profile'),env,ctx);assert.equal(response.status,200);assert.match(response.headers.get('cache-control'),/no-store/);assert.equal((await response.json()).mint,p.mint);
 let data=await (await app.fetch(req('/api/aaplx-report'),env,ctx)).json();assert.equal(data.locked,true);assert.equal(data.sections,undefined);
 for(const plan of ['signal','research']){sql.prepare("UPDATE member_accounts SET plan=?,grant_kind='complimentary',expires_at=? WHERE subject='aaplx-reader'").run(plan,Date.now()+86400000);response=await app.fetch(req('/api/aaplx-report'),env,ctx);assert.match(response.headers.get('cache-control'),/no-store/);data=await response.json();assert.equal(data.sections.length,10);}
 sql.prepare("UPDATE member_accounts SET status='suspended' WHERE subject='aaplx-reader'").run();for(const path of ['/api/aaplx-profile','/api/aaplx-report'])assert.equal((await app.fetch(req(path),env,ctx)).status,403);
});
