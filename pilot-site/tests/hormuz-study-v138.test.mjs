import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,readdirSync} from 'node:fs';
import {hormuzResearch as report} from '../worker/hormuz-research.mjs';
import {hormuzChain as chain} from '../app/hormuz-network.mjs';
import {pathGeometry} from '../app/map-path-geometry.mjs';
import {memberDatabase} from './member-fixture.mjs';
test('Hormuz study has nine substantive bilingual sections, primary source boundaries and actual dates',()=>{
 assert.equal(report.sections.length,9);assert.equal(report.createdAt,'2026-10-09');assert.equal(report.forecastInputCutoff,'2026-10-01');
 assert.equal(report.status,'conditional_research_not_validated_alpha');
 const sources=new Set(report.sources.map(s=>s.id));assert.equal(sources.size,11);
 for(const section of report.sections){assert.equal(section.body.zh.length,section.body.en.length);assert.ok(section.body.en.every(p=>p.length>100));assert.ok(section.body.zh.every(p=>p.length>70));for(const id of section.sources)assert.ok(sources.has(id));}
 for(const source of report.sources){assert.ok(source.url.startsWith('https://'));assert.ok(source.boundary.zh&&source.boundary.en&&source.date);}
 assert.match(report.sections.find(s=>s.id==='supply').body.en.join(' '),/not the same cargo/);
 assert.match(report.sections.find(s=>s.id==='investment').body.en.join(' '),/No event backtest/);
 assert.match(report.sections.find(s=>s.id==='timeline').body.en.join(' '),/not a direct observation of a helium plant/);
});
test('network includes physical and non-geographic mechanisms without invented coordinates',()=>{
 const ids=new Set(chain.nodes.map(n=>n.id));assert.equal(ids.size,chain.nodes.length);
 for(const edge of chain.edges){assert.ok(ids.has(edge.from)&&ids.has(edge.to));assert.notEqual(edge.from,edge.to);assert.equal(edge.status,'hypothesis');}
 for(const id of ['purity','process','power','buffer','cost','invest'])assert.equal(chain.nodes.find(n=>n.id===id).coordinates,null);
 for(const n of chain.nodes)assert.ok(n.noteZh&&n.noteEn);
 assert.ok(chain.edges.some(e=>e.branch==='energy'));assert.ok(chain.edges.some(e=>e.branch==='buffers'));
 const geo=pathGeometry([chain],[chain.id],'en');
 for(const f of geo.features){assert.equal(f.properties.chain,chain.id);if(f.geometry.type==='LineString'){const edge=chain.edges.find(e=>e.from===f.properties.from&&e.to===f.properties.to);assert.ok(edge);assert.deepEqual(f.geometry.coordinates[0],chain.nodes.find(n=>n.id===edge.from).coordinates);assert.deepEqual(f.geometry.coordinates.at(-1),chain.nodes.find(n=>n.id===edge.to).coordinates);}}
 assert.ok(geo.features.some(f=>f.geometry.type==='LineString'&&f.geometry.coordinates.length>2));
 assert.ok(!geo.features.some(f=>f.properties.id==='cost'));
});
test('map branch selection, deselection, language and active node are deterministic',()=>{
 const all=pathGeometry([chain],[chain.id],'en'),energy=pathGeometry([chain],[chain.id],'en',{branch:'energy',activeId:'lng'});
 assert.ok(energy.features.length<all.features.length);
 assert.ok(energy.features.some(f=>f.properties.id==='lng'&&f.properties.active));
 assert.ok(!energy.features.some(f=>f.properties.id==='taiwan'));
 assert.deepEqual(pathGeometry([chain],[],'zh').features,[]);
 const cn=pathGeometry([chain],[chain.id],'zh');assert.notEqual(cn.features[0].properties.label,all.features[0].properties.label);
});
test('full report is server-only; routing and interactive mechanisms are wired',()=>{
 const dashboard=readFileSync('app/PilotDashboard.tsx','utf8');
 assert.match(dashboard,/mapChainData.chains\?\.some/);assert.match(dashboard,/HormuzMapInspector/);
 const ui=readFileSync('app/HormuzResearch.tsx','utf8');assert.match(ui,/api\/hormuz-research/);assert.match(ui,/chain=hormuz-helium/);
 const control=readFileSync('app/HormuzMapConsole.tsx','utf8');assert.match(control,/clearInterval/);assert.match(control,/prefers-reduced-motion/);
 const files=readdirSync('dist/client',{recursive:true}).filter(f=>f.endsWith('.js'));assert.ok(files.length>10);
 for(const f of files){assert.ok(!readFileSync('dist/client/'+f,'utf8').includes(report.sections[7].body.en[0]),'full investment text leaked to '+f);}
});
test('real worker preserves login and plan gates for Hormuz report and map limits',async t=>{
 const {DB,sql}=memberDatabase();t.after(()=>sql.close());const env={DB,PILOT_SESSION_SECRET:'local-test-only'},ctx={waitUntil(){},passThroughOnException(){}},app=(await import('../dist/server/index.js')).default;
 const req=(path,auth=true)=>new Request('https://orakt.test'+path,{headers:auth?{'oai-authenticated-user-id':'hormuz-reader','oai-authenticated-user-email':'test@example.invalid'}:{}});
 assert.equal((await app.fetch(req('/api/hormuz-research',false),env,ctx)).status,401);
 assert.equal((await app.fetch(req('/api/hormuz-research'),env,ctx)).status,403);
 for(const [plan,limit] of [['signal',1],['research',5]]){
 sql.prepare("UPDATE member_accounts SET plan=?,grant_kind='complimentary',expires_at=? WHERE subject='hormuz-reader'").run(plan,Date.now()+86400000);
 const response=await app.fetch(req('/api/hormuz-research'),env,ctx);assert.equal(response.status,200);assert.match(response.headers.get('cache-control'),/no-store/);
 const body=await response.json();assert.equal(body.report.id,report.id);assert.equal(body.network.edges.length,chain.edges.length);
 const maps=await(await app.fetch(req('/api/map-chains'),env,ctx)).json();assert.equal(maps.limit,limit);assert.ok(maps.chains.some(c=>c.id===chain.id&&c.edges.length===chain.edges.length));
 }
 sql.prepare("UPDATE member_accounts SET status='suspended' WHERE subject='hormuz-reader'").run();assert.equal((await app.fetch(req('/api/hormuz-research'),env,ctx)).status,403);
});
