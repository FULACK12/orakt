import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {memberDatabase} from './member-fixture.mjs';
import {memberFor} from '../worker/membership.mjs';
import {watchlistResponse,validTickers} from '../worker/watchlist.mjs';
import {parseMarket,cryptoMarketResponse} from '../worker/crypto-market.mjs';
import {visibleLab} from '../worker/lab-access.mjs';
import {tradingSymbol} from '../app/market-symbols.mjs';
import {safeAccessReturnTo} from '../app/access/access-navigation.mjs';
const companies=[{ticker:'AAPL',companyName:'Apple',marketRegion:'us'},{ticker:'NVDA',companyName:'Nvidia',marketRegion:'us'}];
test('watchlists are server-scoped, durable, bounded and CSRF protected',async()=>{
 const f=memberDatabase(),env={DB:f.DB};
 const a=await memberFor(env,{provider:'google',subject:'alice',displayName:'Alice',accountId:'alice'}),b=await memberFor(env,{provider:'google',subject:'bob',displayName:'Bob',accountId:'bob'});
 const req=(tickers,extra={},headers={})=>new Request('https://orakt.com/api/account/watchlist',{method:'PUT',headers:{Origin:'https://orakt.com','Content-Type':'application/json','X-ORAKT-Preferences':'watchlist',...headers},body:JSON.stringify({tickers,...extra})});
 assert.equal((await watchlistResponse(req(['AAPL']),env,a,companies)).status,200);
 const get=m=>watchlistResponse(new Request('https://orakt.com/api/account/watchlist'),env,m,companies).then(r=>r.json());
 assert.deepEqual((await get(a)).tickers,['AAPL']);assert.deepEqual((await get(b)).tickers,[]);
 assert.equal((await watchlistResponse(req(['NVDA'],{memberId:b.row.id}),env,a,companies)).status,400);
 assert.equal((await watchlistResponse(req(['NVDA'],{},{Origin:'https://other.test'}),env,a,companies)).status,403);
 assert.equal((await watchlistResponse(req(['UNKNOWN']),env,a,companies)).status,400);
 assert.equal((await watchlistResponse(req(['AAPL'.repeat(5000)]),env,a,companies)).status,413);
 assert.deepEqual((await get(a)).tickers,['AAPL']);assert.throws(()=>validTickers(Array(51).fill('AAPL'),new Set(['AAPL'])));
 assert.equal((await watchlistResponse(req([]),env,{...a,access:{status:'suspended'}},companies)).status,403);
 assert.equal((await watchlistResponse(req([]),env,a,companies)).status,200);assert.deepEqual((await get(a)).tickers,[]);
 f.sql.close();
});
const now=Date.now(),quote=s=>({code:'0',data:[{instId:s,last:'120',open24h:'100',ts:String(now),volCcy24h:'9000'}]}),candles={code:'0',data:[[String(now-86400000),'100','125','95','120','3','360','360','1'],[String(now),'120','123','117','122','1','122','122','0']]};
test('crypto validates numbers, instruments, candles and records freshness',async()=>{
 const d=parseMarket('BTC-USDT',quote('BTC-USDT'),candles,now+1000);assert.equal(d.price,120);assert.ok(Math.abs(d.change24h-20)<1e-8);assert.equal(d.points[1].complete,false);assert.equal(d.stale,false);
 assert.equal(parseMarket('BTC-USDT',quote('BTC-USDT'),candles,now+400000).stale,true);
 assert.throws(()=>parseMarket('BTC-USDT',{code:'0',data:[{...quote('BTC-USDT').data[0],last:''}]},candles));
 assert.throws(()=>parseMarket('BTC-USDT',quote('BTC-USDT'),{code:'0',data:[]}));
 let calls=0;const fetcher=async url=>{calls++;assert.match(url,/^https:\/\/www\.okx\.com\/api\/v5\/market\//);return Response.json(url.includes('ticker?')?quote('ETH-USDT'):candles)};
 assert.equal((await cryptoMarketResponse(new Request('https://orakt.com/api/crypto-market?symbol=ETH-USDT'),fetcher)).status,200);
 await cryptoMarketResponse(new Request('https://orakt.com/api/crypto-market?symbol=ETH-USDT'),fetcher);assert.equal(calls,2);
 assert.equal((await cryptoMarketResponse(new Request('https://orakt.com/api/crypto-market?symbol=OTHER'),fetcher)).status,400);assert.equal(calls,2);
 assert.equal((await cryptoMarketResponse(new Request('https://orakt.com/api/crypto-market?symbol=SOL-USDT'),async()=>{throw Error('unavailable')})).status,503);
});
test('portfolio tiers withhold tools server-side, not bad returns; all recipes sum to one',()=>{
 const lab=JSON.parse(readFileSync(new URL('../private-data/lab-expansion.json',import.meta.url)));
 const basic=visibleLab(lab,{permissions:{reports:true,research:false}}),full=visibleLab(lab,{permissions:{research:true}});
 assert.equal(basic.baskets.length,3);assert.equal(basic.factors.length,0);assert.equal(full.baskets.length,6);assert.equal(full.factors.length,6);
 for(const b of lab.baskets){assert.ok(Math.abs(Object.values(b.weights).reduce((a,b)=>a+b,0)-1)<1e-8);for(const w of Object.values(b.windows)){assert.ok(w.points.length>=10);assert.ok(Math.abs(w.points.at(-1).nav-100-w.returnPercent)<1e-8);assert.ok(w.maxDrawdownPercent<=0);assert.equal(w.annualizedReturn,null);}}
});
test('market symbols and direct navigation remain valid',()=>{
 assert.equal(tradingSymbol('600519','china'),'SSE:600519');assert.equal(tradingSymbol('000001','china'),'SZSE:000001');assert.equal(tradingSymbol('AAPL','us'),'NASDAQ:AAPL');assert.equal(tradingSymbol('JPM','us'),'JPM');
 for(const path of ['/platform/markets','/platform/alpha','/platform/personal','/platform/intelligence'])assert.equal(safeAccessReturnTo(path),path);
});
test('report evidence renders compact sections without null% or invented scores',()=>{
 const code=ts.transpileModule(readFileSync(new URL('../app/ReportEvidence.tsx',import.meta.url),'utf8'),{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS}}).outputText;
 const nativeRequire=createRequire(import.meta.url),module={exports:{}};
 const localRequire=name=>{
  if(!name.startsWith('.'))return nativeRequire(name);
  const child={exports:{}},source=ts.transpileModule(readFileSync(new URL('../app/'+name.slice(2)+'.tsx',import.meta.url),'utf8'),{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS}}).outputText;
  new Function('require','module','exports',source)(localRequire,child,child.exports);return child.exports;
 };
 new Function('require','module','exports',code)(localRequire,module,module.exports);
 const html=renderToStaticMarkup(React.createElement(module.exports.default,{language:'zh',report:{confidence:null,chain:[{title:'机制',claim:'待验证',status:'partial',confidence:null,evidenceCount:0}],scores:[],alternatives:['另一原因'],evidence:[],nextData:['补数据'],limitations:[]}}));
 assert.match(html,/reader-chain/);assert.match(html,/<details/);assert.match(html,/替代解释/);assert.doesNotMatch(html,/null%|undefined|NaN/);
});
