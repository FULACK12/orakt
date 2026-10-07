import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {workspaceAccess,visibleAlpha,visibleChains,researchTier} from '../worker/research-tiers.mjs';
import {portfolioCatalog,portfolioStudy,recipes} from '../worker/portfolio-studies.mjs';
import {accessFor} from '../worker/membership.mjs';
import {validateDossier} from '../scripts/reviewed-dossier.mjs';
const free={status:'active',permissions:{}},signal={status:'active',permissions:{reports:true}},research={status:'active',permissions:{reports:true,research:true}};
const json=path=>JSON.parse(readFileSync(new URL('../'+path,import.meta.url)));
test('tiers gate data rather than only hiding buttons, including expired and suspended grants',()=>{
 const chains=Array.from({length:20},(_,i)=>({id:String(i)})),a={experiments:[1,2,3]};
 assert.deepEqual(visibleAlpha(a,free).experiments,[]);assert.deepEqual(visibleAlpha(a,signal).experiments,[1]);assert.equal(visibleAlpha(a,research).experiments.length,3);
 assert.equal(visibleChains(chains,free).chains.length,0);assert.equal(visibleChains(chains,signal).chains.length,12);assert.equal(visibleChains(chains,research).chains.length,20);
 assert.equal(workspaceAccess(signal).portfolio.maxDays,366);assert.equal(workspaceAccess(research).portfolio.maxDays,3660);
 assert.equal(researchTier({...research,status:'suspended'}),'explorer');
 assert.equal(researchTier(accessFor({id:'a',status:'active',plan:'research',grant_kind:'manual_paid',expires_at:1},{},2)),'explorer');
});
const dates=Array.from({length:15},(_,i)=>`2025-01-${String(i+1).padStart(2,'0')}`);
function fixture(){return {cutoff:'2026-10-06',assets:Object.fromEntries([...new Set(recipes.flatMap(r=>Object.keys(r.weights))), 'FX:CNYUSD'].filter(k=>k!=='CASH:USD').map(k=>[k,{currency:k.startsWith('CN:')?'CNY':'USD',points:dates.map((d,i)=>[d,k==='FX:CNYUSD'?7:k.startsWith('CN:')?700:100])}]))};}
test('catalog exposes coverage, not prices; date ranges and research recipes are server gated',()=>{
 const d=fixture(),c=portfolioCatalog(d,signal);assert.equal(c.recipes.filter(r=>!r.locked).length,3);assert.doesNotMatch(JSON.stringify(c),/"points"/);
 for(const r of recipes)assert.ok(Math.abs(Object.values(r.weights).reduce((s,w)=>s+w,0)-1)<1e-10);
 assert.throws(()=>portfolioStudy(d,free,{recipe:'tech-core',start:dates[0],end:dates.at(-1)}),/plan_required/);
 assert.throws(()=>portfolioStudy(d,signal,{recipe:'china-us',start:dates[0],end:dates.at(-1)}),/plan_required/);
 assert.throws(()=>portfolioStudy(d,signal,{recipe:'tech-core',start:'2024-01-01',end:'2025-02-01'}),/date_range_exceeds_plan/);
 for(const end of ['2025-02-30','2027-01-01','bad'])assert.throws(()=>portfolioStudy(d,research,{recipe:'tech-core',start:dates[0],end}),/invalid_date_range/);
});
test('fees preserve negative outcomes, FX converts CNY to USD in correct direction, gaps never interpolate',()=>{
 const d=fixture(),p={recipe:'china-us',start:dates[0],end:dates.at(-1)};
 const flat=portfolioStudy(d,research,p);assert.ok(Math.abs(flat.returnPercent-(-.1999))<1e-8);assert.ok(flat.maxDrawdownPercent<0);assert.equal(flat.annualizedReturn,null);
 d.assets['FX:CNYUSD'].points.at(-1)[1]=14;
 const fx=portfolioStudy(d,research,p);assert.ok(Math.abs(fx.returnPercent-(75*.998001-100))<1e-8);assert.notEqual(fx.inputHash,flat.inputHash);
 d.assets['FX:CNYUSD'].points.splice(4,1);const gap=portfolioStudy(d,research,p);assert.equal(gap.missingReferenceDates,1);assert.equal(gap.points.length,14);assert.ok(!gap.points.find(p=>p.date===dates[4]));
 d.assets['CN:600519'].points=[];const missing=portfolioStudy(d,research,p);assert.equal(missing.state,'insufficient_data');assert.deepEqual(missing.points,[]);
});
test('retained China/US and crypto data produce bounded auditable curves for all 11 recipes',()=>{
 const data=json('private-data/portfolio-prices.json');assert.ok(data.assets['CB:BTC-USD'].points.length>2000);assert.ok(data.assets['FX:CNYUSD'].points.length>2000);
 for(const r of recipes){const result=portfolioStudy(data,research,{recipe:r.id,start:'2025-01-01',end:'2026-09-22'});assert.ok(result.points.length>100,r.id);assert.ok(Number.isFinite(result.returnPercent));assert.ok(result.points.every(p=>p.date<='2026-09-22'&&Number.isFinite(p.nav)));assert.equal(result.validatedAlpha,false);assert.equal(result.inputHash.length,64);}
});
for(const id of ['dossier-AAPL-20090722-18d3a8e3','dossier-ADBE-20090626-bbc87b22'])test(id+' retains review receipt and bilingual nine-chapter evidence',()=>{
 const raw=readFileSync(new URL('../private-data/company-dossiers/'+id+'.json',import.meta.url)),d=JSON.parse(raw),r=json('private-data/research-reports/'+id+'.json').report;
 assert.doesNotThrow(()=>validateDossier(d,r,raw,readFileSync(new URL('../private-data/dossier-reviews/'+id+'.json',import.meta.url))));
 assert.equal(d.chapters.length,9);assert.ok(json('private-data/report-translations/'+id+'.en.json').question);assert.equal(r.confidence,null);assert.equal(r.historical.eligibleForPredictiveBacktest,false);
});
