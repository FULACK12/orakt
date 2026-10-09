import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
// Compile only local presentational components in memory; no files or routes are exposed.
const nativeRequire=createRequire(import.meta.url),cache=new Map();
function component(url){
 if(cache.has(url.href))return cache.get(url.href);
 const code=ts.transpileModule(readFileSync(url,'utf8'),{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 const module={exports:{}};cache.set(url.href,module.exports);
 const req=name=>name.startsWith('.')?component(new URL(name+'.tsx',url)):nativeRequire(name);
 new Function('require','module','exports',code)(req,module,module.exports);
 return module.exports;
}
const Dossier=component(new URL('../app/CompanyDossier.tsx',import.meta.url)).default;
const latestGoogle=JSON.parse(readFileSync(new URL('../private-data/company-dossiers/dossier-GOOGL-20260723-89aae521.json',import.meta.url)));
for(const language of ['zh','en'])test(`Google nine reviewed chapters render in ${language} with investment-income boundary`,()=>{
 const html=renderToStaticMarkup(React.createElement(Dossier,{dossier:latestGoogle,language}));
 assert.equal((html.match(/id="chapter-/g)||[]).length,9);
 assert.match(html,/2026-07-23/);assert.match(html,/119,796/);
 assert.match(html,language==='zh'?/成本金额上升但成本占收入比例下降/:/Cost dollars increase but their revenue share declines/);
 assert.doesNotMatch(html,/NaN|undefined/);
});
const latestAmd=JSON.parse(readFileSync(new URL('../private-data/company-dossiers/dossier-AMD-20260805-e812de14.json',import.meta.url)));
for(const language of ['zh','en'])test(`AMD reviewed nine chapters render in ${language} with correct retirement boundary`,()=>{
 const html=renderToStaticMarkup(React.createElement(Dossier,{dossier:latestAmd,language}));
 assert.equal((html.match(/id="chapter-/g)||[]).length,9);
 assert.match(html,/2026-08-05/);assert.match(html,/11,536/);
 assert.match(html,language==='zh'?/注销本身不是本季度再次回购/:/Retirement is not another current-quarter repurchase/);
 assert.doesNotMatch(html,/NaN|undefined/);
});
const d=JSON.parse(readFileSync(new URL('../private-data/company-dossiers/dossier-NVDA-20090820-97979407.json',import.meta.url)));
for(const language of ['zh','en'])test(`complete historical report renders in ${language} without losing audit boundaries`,()=>{
 const html=renderToStaticMarkup(React.createElement(Dossier,{dossier:d,language}));
 assert.equal((html.match(/id="chapter-/g)||[]).length,9);
 assert.match(html,/277,245,000/);assert.match(html,/2009-08-20/);assert.match(html,/MARKET:DGS2/);
 assert.match(html,language==='zh'?/预测置信度未估计/:/Predictive confidence is unestimated/);
 assert.match(html,language==='zh'?/增加分母会降低而非提高每股收益/:/an increased denominator lowers EPS/);
 assert.doesNotMatch(html,/NaN|undefined/);
});
const latestApple=JSON.parse(readFileSync(new URL('../private-data/company-dossiers/dossier-AAPL-20260731-a1f9adca.json',import.meta.url)));
const latestAmazon=JSON.parse(readFileSync(new URL('../private-data/company-dossiers/dossier-AMZN-20260731-a766a6bf.json',import.meta.url)));
const latestMeta=JSON.parse(readFileSync(new URL('../private-data/company-dossiers/dossier-META-20260730-1fe49853.json',import.meta.url)));
for(const language of ['zh','en'])test(`META reviewed nine chapters render in ${language}`,()=>{
 const html=renderToStaticMarkup(React.createElement(Dossier,{dossier:latestMeta,language}));
 assert.equal((html.match(/id="chapter-/g)||[]).length,9);
 assert.match(html,/2026-07-30/);assert.match(html,/60,801/);
 assert.match(html,language==='zh'?/没有回购普通股/:/no common-share repurchases/);
 assert.doesNotMatch(html,/NaN|undefined/);
});
for(const language of ['zh','en'])test(`AMZN nine chapters and unreconciled cash boundary render in ${language}`,()=>{
 const html=renderToStaticMarkup(React.createElement(Dossier,{dossier:latestAmazon,language}));
 assert.equal((html.match(/id="chapter-/g)||[]).length,9);
 assert.match(html,/2026-07-31/);
 assert.match(html,language==='zh'?/滚动自由现金流/:/rolling free cash flow/i);
 assert.match(html,language==='zh'?/十二个月区间/:/Twelve-month window/);
 assert.doesNotMatch(html,/NaN|undefined/);
 assert.equal(latestAmazon.cashBridge.state,'unavailable');
});
for(const language of ['zh','en'])test(`latest AAPL leader report renders nine reviewed chapters in ${language}`,()=>{
 const html=renderToStaticMarkup(React.createElement(Dossier,{dossier:latestApple,language}));
 assert.equal((html.match(/id="chapter-/g)||[]).length,9);
 assert.match(html,/2026-07-31/);assert.match(html,/109,417/); // USD millions, as labeled by the reader.
 assert.match(html,language==='zh'?/销售额而非销量|不等于已经证明销量增长/:/does not establish higher unit volume/);
 assert.doesNotMatch(html,/NaN|undefined/);
 assert.equal(latestApple.validatedAlpha,false);
 assert.equal(latestApple.review.humanAccepted,false);
});
