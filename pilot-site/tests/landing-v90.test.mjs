import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';
import {resolveDisplayLanguage} from '../app/display-language.mjs';
import {authText} from '../app/access/auth-copy.mjs';
const read=path=>readFile(new URL('../'+path,import.meta.url),'utf8');
test('language prefers explicit choice then first supported browser preference',()=>{
 assert.equal(resolveDisplayLanguage('en',['zh-CN']),'en');assert.equal(resolveDisplayLanguage('zh',['en-US']),'zh');
 assert.equal(resolveDisplayLanguage(null,['fr-FR','zh-TW','en']),'zh');assert.equal(resolveDisplayLanguage(null,['en-CA','zh']),'en');
 assert.equal(resolveDisplayLanguage('invalid',['zh-Hans']),'zh');assert.equal(resolveDisplayLanguage(null,[]),'en');
});
test('every translated Chinese auth literal has an English counterpart',async()=>{
 for(const name of ['AccessPortal','GoogleLogin','LocalLogin','WalletLogin']){
  const source=await read('app/access/'+name+'.tsx'),file=ts.createSourceFile(name+'.tsx',source,99,true,4);let count=0;
  function visit(n){if(ts.isCallExpression(n)&&n.expression.getText(file)==='tr'&&ts.isStringLiteral(n.arguments[0])){const str=n.arguments[0].text;if(/[\u3400-\u9fff]/.test(str)){count++;assert.notEqual(authText('en',str),str,`${name}: ${str}`);assert.equal(authText('zh',str),str);assert.doesNotMatch(authText('en',str),/[\u3400-\u9fff]/);}}ts.forEachChild(n,visit);}visit(file);assert.ok(count>5);
 }
});
test('mobile hero uses natural inline glyphs, unclipped line entry and reduced motion',async()=>{
 const css=await read('app/OraktLanding.module.css');assert.match(css,/\.hero h1 \.motionGlyph\{display:inline;opacity:1;filter:none;transform:none;animation:none/);assert.match(css,/mobileLineEnter/);assert.match(css,/prefers-reduced-motion:reduce\)\{\.hero h1 \.motionLine\{animation:none\}/);
});
test('world keeps graphic-only treatment; matrix is pointer aware and bounded',async()=>{
 const world=await read('app/OraktWorldScene.tsx');assert.doesNotMatch(world,/fillText\(|className=\{styles.caption\}|className=\{styles.footer\}/);
 const chain=await read('app/OraktChainScene.tsx');assert.match(chain,/length:64/);assert.match(chain,/onPointerLeave=\{reset\}/);assert.match(chain,/e.pointerType==='touch'/);assert.match(chain,/useSceneActivity/);assert.match(chain,/disabled=\{reduced\}/);
});
test('published totals and legal pages are publicly readable without exposing reports',async()=>{
 const app=(await import('../dist/server/index.js')).default,ctx={waitUntil(){},passThroughOnException(){}};
 const r=await app.fetch(new Request('http://localhost/api/public-stats'),{},ctx);assert.equal(r.status,200);assert.match(r.headers.get('cache-control'),/no-store/);const stats=await r.json();assert.equal(stats.mode,'published_library_not_live_feed');assert.equal(stats.reports,JSON.parse(await read('snapshot/research-report-index.json')).reports.length);assert.ok(Number.isFinite(Date.parse(stats.checkedAt)));assert.ok(Number.isFinite(Date.parse(stats.generatedAt)));assert.deepEqual(Object.keys(stats).sort(),['newsRecords','events','articles','reports','companies','generatedAt','checkedAt','mode'].sort());assert.equal(stats.newsRecords,JSON.parse(await read('snapshot/snapshot-manifest.json')).remoteSnapshot.newsIndexRecords);
 assert.equal((await app.fetch(new Request('http://localhost/api/public-stats',{method:'POST'}),{},ctx)).status,405);
 for(const path of ['/privacy','/terms']){const p=await app.fetch(new Request('http://localhost'+path),{},ctx);assert.equal(p.status,200);const body=await p.text();assert.match(body,/返回登录/);assert.match(body,/2026-10-06/);}
 const protectedReport=await app.fetch(new Request('http://localhost/api/research-report?id=325'),{},ctx);assert.equal(protectedReport.status,401);
});
