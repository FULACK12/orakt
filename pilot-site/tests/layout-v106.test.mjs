import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const read = path => readFile(new URL(`../${path}`, import.meta.url), 'utf8');

test('MOVES uses five separate closed contours, not overlapping font strokes',async()=>{
  const word = await read('app/HeroOutlineWord.tsx');
  assert.deepEqual([...word.matchAll(/data-letter="([A-Z])"/g)].map(m=>m[1]),['M','O','V','E','S']);
  assert.match(word,/data-letter="E" d="M318 6H383V25H339V44H379V63H339V83H383V102H318Z"/);
  assert.match(word,/aria-hidden="true" focusable="false"/);
  const home = await read('app/OraktLanding.tsx');
  assert.match(home,/outline && text === "MOVES" \? <HeroOutlineWord/);
  const css = await read('app/OraktLanding.module.css');
  assert.doesNotMatch(css.match(/\.heroOutline\s*\{([^}]+)\}/)[1],/-webkit-text-stroke/);
  assert.match(css,/vector-effect:non-scaling-stroke/);
});

test('data rail items keep uniform bounded width and horizontal bilingual labels',async()=>{
  const css=await read('app/OraktLanding.module.css');
  assert.match(css,/\.statItem\s*\{[^}]*flex:0 0 300px;[^}]*width:300px;[^}]*min-width:0/);
  assert.match(css,/\.marquee span\s*\{[^}]*white-space:nowrap/);
  assert.doesNotMatch(css,/width:max\(100vw, (1280|1120)px\)/);
  assert.match(css,/\.hero\s*\{ min-height:0; padding-bottom:64px/);
  assert.match(css,/font-size:clamp\(40px,13.8vw,102px\)/);
});

test('workspace polish stays scoped, supports two themes and compact navigation',async()=>{
  const css=await read('app/workspace-polish.css');
  assert.match(await read('app/layout.tsx'),/import '.\/workspace-polish.css'/);
  assert.match(css,/var\(--work-accent\)/);
  assert.match(css,/\.app-shell \.report-filter-grid label \{ min-width:0/);
  assert.match(css,/grid-template-columns:repeat\(2,minmax\(0,1fr\)\)/);
  assert.doesNotMatch(css,/\.map-stage|\.maplibregl|\.map-workspace/);
});
