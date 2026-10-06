import test from "node:test";
import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import { createSceneClock, validateLandPoints } from "../app/scene-clock.mjs";

test("brand files exist and geographic scene uses actual sampled land",async()=>{
  for(const file of ["orakt-icon.webp","favicon-64.png","apple-touch-icon.png"]) assert.ok((await stat(new URL(`../public/brand/${file}`,import.meta.url))).size>100);
  const points=JSON.parse(await readFile(new URL("../public/brand/world-land-points.json",import.meta.url),"utf8"));
  assert.ok(points.length>1000);assert.ok(points.every(([x,y])=>x>=-180&&x<=180&&y>=-90&&y<=90));
});

test("motion controls preserve an offscreen pause and a reduced-motion fallback",async()=>{
  const hook=await readFile(new URL("../app/useSceneActivity.ts",import.meta.url),"utf8");
  assert.match(hook,/IntersectionObserver/);assert.match(hook,/document.hidden/);assert.match(hook,/prefers-reduced-motion/);
  const chain=await readFile(new URL("../app/OraktChainScene.tsx",import.meta.url),"utf8");
  assert.match(chain,/cancelAnimationFrame/);assert.match(chain,/aria-pressed/);assert.match(chain,/非投资结论/);
});

test("paused scenes preserve progress and resume at the exact remaining time",()=>{
  const clock=createSceneClock(4200);
  clock.resume(0);
  assert.equal(clock.tick(2800).progress,2/3);
  clock.pause();
  assert.deepEqual(clock.tick(90000),{progress:2/3,completed:false});
  clock.resume(100000);
  assert.equal(clock.tick(101399).completed,false);
  assert.deepEqual(clock.tick(101400),{progress:0,completed:true});
  clock.reset();
  clock.resume(200000);
  assert.equal(clock.tick(202100).progress,.5);
});

test("geographic assets reject malformed payloads without entering the renderer",()=>{
  for(const payload of [null,{},[],"<html>Error</html>",[[200,0]],[[0,91]],[[0]],[[0,NaN]],[[Infinity,0]],[['10',20]]]) assert.throws(()=>validateLandPoints(payload));
  assert.deepEqual(validateLandPoints([[-180,-90],[180,90],[120,35]]),[[-180,-90],[180,90],[120,35]]);
});

test("marquee repeats complete equal-width groups and hides the duplicate from readers",async()=>{
  const source=await readFile(new URL("../app/OraktLanding.tsx",import.meta.url),"utf8");
  const css=await readFile(new URL("../app/OraktLanding.module.css",import.meta.url),"utf8");
  assert.match(source,/\[0, 1\]\.map/);assert.match(source,/aria-hidden=\{group === 1/);
  assert.match(css,/width:max\(100vw, 1280px\)/);assert.match(css,/translateX\(-50%\)/);
});

test("contour wordmark is vector-only, bounded and explicitly pausable",async()=>{
 const source=await readFile(new URL("../app/OraktContour.tsx",import.meta.url),"utf8");
 const css=await readFile(new URL("../app/OraktContour.module.css",import.meta.url),"utf8");
 assert.match(source,/useSceneActivity/);assert.match(source,/length:18/);assert.match(source,/useId/);
 assert.match(source,/data-running={running&&!paused}/);assert.match(source,/aria-pressed={paused\|\|reduced}/);
 assert.match(css,/animation-play-state:paused/);assert.match(css,/prefers-reduced-motion:reduce/);
 assert.doesNotMatch(source,/canvas|requestAnimationFrame|setInterval|<img/);
 assert.match(source,/data-animation="permanent-loop"/);
 assert.match(css,/breathe 13s ease-in-out infinite alternate/);
 assert.match(css,/trace 22s linear infinite/);
});

test("new world and chain scenes have isolated styles, bounded geometry and accessible playback",async()=>{
 for(const [component,stylesheet] of [["OraktWorldScene.tsx","OraktWorldScene.module.css"],["OraktChainScene.tsx","OraktProductScenes.module.css"]]){
  const source=await readFile(new URL(`../app/${component}`,import.meta.url),"utf8");
  const css=await readFile(new URL(`../app/${stylesheet}`,import.meta.url),"utf8");
  assert.ok(source.includes(`./${stylesheet}`));
  for(const [,name] of source.matchAll(/styles\.(\w+)/g))assert.ok(css.includes(`.${name}`),`${component} uses missing style ${name}`);
  assert.match(source,/data-animation="loop"/);assert.match(source,/aria-pressed/);
  assert.match(source,/cancelAnimationFrame/);assert.match(source,/if\s*\(!?playing\)/);
  assert.match(css,/44px/);assert.match(css,/@media\(max-width:520px\)/);
 }
 const world=await readFile(new URL("../app/OraktWorldScene.tsx",import.meta.url),"utf8");
 assert.match(world,/validateLandPoints/);assert.match(world,/controller\.abort/);assert.match(world,/resize\.disconnect/);
 assert.match(world,/devicePixelRatio\|\|1,1\.75/);assert.match(world,/now-last>=32/);
 assert.match(world,/非实时数据/);assert.match(world,/not live data/);
 const chain=await readFile(new URL("../app/OraktChainScene.tsx",import.meta.url),"utf8");
 assert.match(chain,/length:30/);assert.match(chain,/useId/);assert.match(chain,/clock\.current\.reset/);
 assert.doesNotMatch(chain,/paperBack|documentStack|evidencePaper/);
});

test("product animations blend into the page without outer cards or boxed controls",async()=>{
 const read=name=>readFile(new URL(`../app/${name}`,import.meta.url),"utf8");
 for(const file of ["OraktWorldScene.module.css","OraktProductScenes.module.css"]){
  const css=await read(file),scene=css.match(/^\.scene\{([^}]+)\}/)?.[1];
  assert.ok(scene);assert.match(scene,/border:0/);assert.match(scene,/box-shadow:none/);
  assert.match(scene,/transparent 66%/);assert.doesNotMatch(scene,/#070a10|border:1px|box-shadow:0/);
  assert.doesNotMatch(css,/\.scene:after/);assert.match(css,/button:focus-visible/);
  const pause=css.match(/\.(?:sceneHeader|header) button\{([^}]+)\}/)?.[1];
  assert.match(pause,/44px/);assert.match(pause,/border:0/);assert.match(pause,/background:transparent/);
 }
 const chain=await read("OraktProductScenes.module.css"),controls=chain.match(/\.stepControls button\{([^}]+)\}/)?.[1];
 assert.match(controls,/border:0/);assert.match(controls,/background:transparent/);
 assert.match(chain,/\.engine\{[^}]*mask-image:linear-gradient/);
 assert.doesNotMatch(chain,/\.scene\{[^}]*mask-image/); // Never fade text, focus rings or hit targets.
 assert.match(chain,/min-width:821px/);
 const landing=await read("OraktLanding.module.css");
 assert.match(landing,/minmax\(0,\.85fr\) minmax\(0,1\.15fr\)/);
 const signature=await read("OraktContour.module.css");
 assert.match(signature,/^\.signature\{[^}]*border:0/);assert.match(signature,/infinite/);
});
