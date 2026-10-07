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
const d=JSON.parse(readFileSync(new URL('../private-data/company-dossiers/dossier-NVDA-20090820-97979407.json',import.meta.url)));
for(const language of ['zh','en'])test(`complete historical report renders in ${language} without losing audit boundaries`,()=>{
 const html=renderToStaticMarkup(React.createElement(Dossier,{dossier:d,language}));
 assert.equal((html.match(/id="chapter-/g)||[]).length,9);
 assert.match(html,/277,245,000/);assert.match(html,/2009-08-20/);assert.match(html,/MARKET:DGS2/);
 assert.match(html,language==='zh'?/预测置信度未估计/:/Predictive confidence is unestimated/);
 assert.match(html,language==='zh'?/增加分母会降低而非提高每股收益/:/an increased denominator lowers EPS/);
 assert.doesNotMatch(html,/NaN|undefined/);
});
