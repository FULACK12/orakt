import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {alignPrices,runFactor} from '../worker/factor-study.mjs';
import {memberDatabase} from './member-fixture.mjs';
const raw=readFileSync(new URL('../private-data/portfolio-prices.json',import.meta.url)),input=JSON.parse(raw),rows=alignPrices(input.assets),saved=JSON.parse(readFileSync(new URL('../private-data/factor-study-v134.json',import.meta.url)));
test('factor artifact exactly reproduces retained input, all segments, sensitivities and hashes',()=>{
 assert.equal(saved.inputHash,createHash('sha256').update(raw).digest('hex'));
 assert.deepEqual(saved.full,runFactor(rows));assert.deepEqual(saved.early,runFactor(rows,{end:'2021-12-31'}));assert.deepEqual(saved.later,runFactor(rows,{start:'2022-01-01'}));
 assert.equal(saved.validatedAlpha,false);assert.equal(saved.executionEnabled,false);assert.equal(saved.sections.length,8);assert.ok(saved.sections.every(s=>s.body.zh&&s.body.en));
 for(const c of saved.sensitivity)assert.equal(c.netReturnPercent,runFactor(rows,{costBps:c.costBps}).stats.netReturnPercent);
 assert.ok(saved.later.stats.excessMarketPP<0);assert.ok(saved.full.stats.excessIndustryPP<0);
});
test('signal precedes execution, no target return before execution; independent arithmetic replay',()=>{
 const f=runFactor(rows),cost=.0012;let nav=100,position=0;
 for(let j=1;j<f.points.length;j++){
  const p=f.points[j],i=rows.findIndex(r=>r.date===p.date);nav*=1+position*(rows[i].stock/rows[i-1].stock-1);
  for(const trade of f.trades.filter(t=>t.executionDate===p.date)){
   if(trade.reason==='monthly_signal'){assert.equal(trade.signalDate,rows[i-1].date);assert.notEqual(trade.signalDate.slice(0,7),p.date.slice(0,7));assert.equal(trade.to,Number(rows[i-1].stock>rows[i-253].stock));}
   assert.equal(trade.from,position);assert.notEqual(trade.from,trade.to);nav*=1-cost;position=trade.to;
  }
  assert.ok(Math.abs(nav-p.strategy)<1e-8);
 }
 assert.equal(position,0);assert.ok(f.stats.turnover<30);
});
test('future prices do not affect past signal or NAV; later split starts in cash',()=>{
 const altered=rows.map((r,i)=>i>1500?{...r,stock:r.stock*2}:r),a=runFactor(rows),b=runFactor(altered);
 assert.deepEqual(a.points.filter(p=>p.date<=rows[1500].date),b.points.filter(p=>p.date<=rows[1500].date));
 assert.equal(saved.later.points[0].strategy,100);assert.equal(saved.later.points[0].position,0);
 assert.ok(saved.sensitivity[0].netReturnPercent>saved.sensitivity[1].netReturnPercent);assert.ok(saved.sensitivity[1].netReturnPercent>saved.sensitivity[2].netReturnPercent);
});
test('bad inputs fail rather than invent missing prices',()=>{
 const assets=structuredClone(input.assets);assets['EQ:AAPL'].points.push(assets['EQ:AAPL'].points[0]);assert.throws(()=>alignPrices(assets),/duplicate/);
 assert.throws(()=>runFactor(rows,{costBps:-1}),/Invalid cost/);assert.throws(()=>runFactor(rows,{start:'2099-01-01'}),/Insufficient/);
 assert.equal(rows.length,2946);assert.equal(rows.at(-1).date,'2026-09-22');
});
test('real worker gates the attached factor report and full data',async t=>{
 const {DB,sql}=memberDatabase();t.after(()=>sql.close());const env={DB,PILOT_SESSION_SECRET:'factor-fixture-only'},ctx={waitUntil(){},passThroughOnException(){}},app=(await import('../dist/server/index.js')).default;
 const req=(auth=true)=>new Request('https://orakt.test/api/alpha-study',{headers:auth?{'oai-authenticated-user-id':'factor-reader','oai-authenticated-user-email':'factor@example.invalid'}:{}});
 assert.equal((await app.fetch(req(false),env,ctx)).status,401);
 let r=await app.fetch(req(),env,ctx);assert.deepEqual(await r.json(),{locked:true,tier:'explorer'});
 for(const plan of ['signal','research']){sql.prepare("UPDATE member_accounts SET plan=?,grant_kind='complimentary',expires_at=? WHERE subject='factor-reader'").run(plan,Date.now()+86400000);r=await app.fetch(req(),env,ctx);assert.equal(r.status,200);const d=await r.json();assert.equal(d.id,saved.id);assert.equal(d.sections.length,8);assert.match(r.headers.get('cache-control'),/no-store/);}
 sql.prepare("UPDATE member_accounts SET status='suspended' WHERE subject='factor-reader'").run();assert.equal((await app.fetch(req(),env,ctx)).status,403);
});
