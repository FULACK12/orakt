import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {appleNetwork} from '../worker/apple-network.mjs';
import {appleResearch} from '../worker/apple-research.mjs';
import {mapChains} from '../worker/map-chains.mjs';
import {pathGeometry} from '../app/map-path-geometry.mjs';
import {memberDatabase} from './member-fixture.mjs';
const snapshot=JSON.parse(readFileSync('snapshot/apple-network-v132.json','utf8')),network=appleNetwork(snapshot);
test('all ingested Apple locations retained, with explicit unresolved coordinates',()=>{
 assert.equal(snapshot.sites.length,724);assert.equal(snapshot.truncated,false);assert.equal(snapshot.supplierCount,187);
 const located=network.nodes.filter(n=>n.kind==='supplier').flatMap(n=>n.sites);
 assert.equal(located.length,603);assert.equal(network.unlocated.length,121);assert.equal(new Set([...located,...network.unlocated].map(s=>s.siteId)).size,724);
 assert.equal(new Set([...located,...network.unlocated].map(s=>s.relatedCompanyName)).size,187);
 assert.equal(network.coverage.cost,'undisclosed');assert.equal(network.coverage.power,'unknown');
});
test('typed edges only connect disclosed locations to candidate ports, never array adjacency',()=>{
 const byId=new Map(network.nodes.map(n=>[n.id,n]));assert.ok(network.edges.length>40);
 for(const e of network.edges){assert.equal(byId.get(e.from).kind,'supplier');assert.equal(byId.get(e.to).kind,'port');assert.equal(e.status,'hypothesis');}
 const all=pathGeometry([network],['apple-network'],'en');assert.ok(all.features.length>100);
 assert.deepEqual(pathGeometry([network],[],'en').features,[]);
 const noPorts=pathGeometry([network],['apple-network'],'en',{logistics:false});assert.ok(noPorts.features.every(f=>f.geometry.type==='Point'&&f.properties.kind!=='port'));
 assert.ok(pathGeometry([network],['apple-network'],'en',{risks:false}).features.every(f=>!f.properties.risk));
 assert.ok(pathGeometry([network],['apple-network'],'en',{query:'Foxconn'}).features.length<all.features.length);
 assert.deepEqual(pathGeometry([network],['apple-network'],'en',{query:'__absent_supplier__'}).features,[]);
});
test('bilingual study contains five dimensions, cost bridge, counterevidence and source traceability',()=>{
 assert.deepEqual(appleResearch.sections.slice(0,5).map(s=>s.id),['business','network','macro','physical','market']);
 for(const s of appleResearch.sections){assert.equal(s.body.zh.length,s.body.en.length);assert.ok(s.body.en.every(p=>p.length>80));for(const id of s.sources)assert.ok(appleResearch.sources.some(x=>x.id===id));}
 assert.match(appleResearch.scope.en,/FY2023/);assert.match(appleResearch.scope.en,/not a latest-quarter/);assert.match(appleResearch.status.en,/unvalidated/);
 const css=readFileSync('app/OraktLanding.module.css','utf8');assert.match(css,/flex:0 0 300px; width:300px/);assert.doesNotMatch(css,/min-width:100vw/);
});
test('real worker rejects anonymous, free and suspended report access, allows paid research depths',async t=>{
 const {DB,sql}=memberDatabase();t.after(()=>sql.close());const env={DB,PILOT_SESSION_SECRET:'local-test-only'},ctx={waitUntil(){},passThroughOnException(){}},app=(await import('../dist/server/index.js')).default;
 const req=(path,auth=true)=>new Request('https://orakt.test'+path,{headers:auth?{'oai-authenticated-user-id':'apple-reader','oai-authenticated-user-email':'test@example.invalid'}:{}});
 assert.equal((await app.fetch(req('/api/apple-research',false),env,ctx)).status,401);
 assert.equal((await app.fetch(req('/api/apple-research'),env,ctx)).status,403);
 for(const [plan,limit] of [['signal',1],['research',5]]){
  sql.prepare("UPDATE member_accounts SET plan=?,grant_kind='complimentary',expires_at=? WHERE subject='apple-reader'").run(plan,Date.now()+86400000);
  const response=await app.fetch(req('/api/apple-research'),env,ctx);assert.equal(response.status,200);const body=await response.json();assert.equal(body.report.id,appleResearch.id);assert.equal(body.network.coverage.locations,724);
  const maps=await (await app.fetch(req('/api/map-chains'),env,ctx)).json();assert.equal(maps.limit,limit);assert.ok(maps.chains.some(c=>c.id==='apple-network'));
 }
 sql.prepare("UPDATE member_accounts SET status='suspended' WHERE subject='apple-reader'").run();assert.equal((await app.fetch(req('/api/apple-research'),env,ctx)).status,403);
});
