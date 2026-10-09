import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {readingReferences,readableEvidenceText,reportForReading} from '../app/report-reading.mjs';
const nativeRequire=createRequire(import.meta.url),cache=new Map();
function component(url){
 if(cache.has(url.href))return cache.get(url.href);
 const code=ts.transpileModule(readFileSync(url,'utf8'),{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 const module={exports:{}};cache.set(url.href,module.exports);
 new Function('require','module','exports',code)(name=>name.endsWith('.mjs')?nativeRequire(fileURLToPath(new URL(name,url))):name.startsWith('.')?component(new URL(name+'.tsx',url)):nativeRequire(name),module,module.exports);return module.exports;
}
const {ReadingText,default:References}=component(new URL('../app/ReadingReferences.tsx',import.meta.url));
const Dossier=component(new URL('../app/CompanyDossier.tsx',import.meta.url)).default;
const Semiconductor=component(new URL('../app/SemiconductorComparisonPanel.tsx',import.meta.url)).default;
test('deferred semiconductor comparison renders its retained data without missing helpers',()=>{
 const comparison=JSON.parse(readFileSync(new URL('../snapshot/semiconductor-comparison.json',import.meta.url)));
 for(const language of ['zh','en']){const html=renderToStaticMarkup(React.createElement(Semiconductor,{comparison,language}));assert.match(html,/NVDA/);assert.match(html,/OHLCV/);assert.doesNotMatch(html,/NaN|undefined/);}
});
test('citation presentation preserves originals, links groups and does not invent missing evidence',()=>{
 const report={id:'PASSAGE:report',thesis:'增长 [PASSAGE:bb, PASSAGE:aa]',chain:[{claim:'PASSAGE:missing'}],dossier:{sources:[{url:'https://www.sec.gov/example'}],originalPassages:{one:[{id:'PASSAGE:aa',text:'Original source A'},{id:'PASSAGE:unused',text:'Not cited'}]},chapters:[{grounded_claims:[{passage_id:'PASSAGE:bb',quote:'Original B'}],evidence_refs:['PASSAGE:bb']}]}},before=JSON.stringify(report);
 const view=reportForReading(report,'zh');
 assert.equal(JSON.stringify(report),before);assert.equal(view.id,'PASSAGE:report');assert.equal(view.thesis,'增长 〔证据 2 · 证据 1〕');assert.equal(view.dossier.chapters[0].evidence_refs[0],'PASSAGE:bb');
 assert.deepEqual(view.readingReferences.map(r=>r.id),['PASSAGE:aa','PASSAGE:bb','PASSAGE:missing']);assert.equal(view.readingReferences[2].quote,null);
 const html=renderToStaticMarkup(React.createElement(ReadingText,{text:view.thesis}));assert.match(html,/href="#reading-source-1"/);assert.match(html,/href="#reading-source-2"/);assert.doesNotMatch(html,/PASSAGE:/);
 const refs=renderToStaticMarkup(React.createElement(References,{references:view.readingReferences,language:'zh'}));assert.match(refs,/id="reading-source-1"/);assert.match(refs,/当前发布版本未附此段原文/);assert.match(refs,/Original source A/);
 assert.equal(reportForReading(null,'zh'),null);assert.deepEqual(readingReferences(undefined),[]);assert.equal(readableEvidenceText('ordinary passage',[],'en'),'ordinary passage');assert.equal(reportForReading(report,'en').thesis,'增长 〔Ref 2 · Ref 1〕');
});
for(const id of ['dossier-NVDA-20090820-97979407','dossier-NVDA-20260826-da949048','dossier-MSFT-20260729-e8b00c5f'])for(const language of ['zh','en'])test(`${id} has readable nine chapters and linked citations in ${language}`,()=>{
 const d=JSON.parse(readFileSync(new URL('../private-data/company-dossiers/'+id+'.json',import.meta.url))),view=reportForReading({dossier:d},language);
 assert.ok(view.readingReferences.length>0);assert.ok(view.readingReferences.every(r=>r.quote));
 for(const chapter of view.dossier.chapters)for(const key of ['analysis','mechanism','counterEvidence','uncertainty','evidenceSummary'])if(chapter[key]?.[language])assert.doesNotMatch(chapter[key][language],/PASSAGE:/);
 const html=renderToStaticMarkup(React.createElement(Dossier,{dossier:view.dossier,language}));assert.equal((html.match(/id="chapter-/g)||[]).length,9);assert.match(html,/href="#reading-source-/);assert.doesNotMatch(html,/NaN|undefined/);
});
test('workspace chrome and comparison flow have regression guards',()=>{
 const css=readFileSync(new URL('../app/workspace-layout.css',import.meta.url),'utf8'),ui=readFileSync(new URL('../app/PilotDashboard.tsx',import.meta.url),'utf8');
 assert.match(css,/\.app-shell \.topbar\{height:auto/);assert.match(css,/grid-template-rows:auto auto/);assert.match(css,/body:has\(\.app-shell\).*padding:0/);assert.match(css,/flex:1 1 0%;height:auto;min-height:0/);
 assert.match(ui,/ref=\{workspaceRef\}/);assert.match(ui,/comparisonMode==="macro" \? <>/);assert.match(ui,/aria-pressed=\{comparisonMode==="peers"\}/);assert.equal((ui.match(/<MacroEventReports /g)||[]).length,1);assert.doesNotMatch(ui,/独立横向报告区/);
});
