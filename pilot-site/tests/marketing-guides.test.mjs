import assert from "node:assert/strict";
import test from "node:test";
import {readFile} from "node:fs/promises";
import {marketingGuides} from "../app/marketing-guide-content.ts";
import {methodNotes} from "../app/marketing-method-notes.ts";

const pages=Object.keys(marketingGuides);
const ctx={waitUntil(){},passThroughOnException(){}};
const env={ASSETS:{fetch:async()=>new Response("Not found",{status:404})}};
let app;
async function htmlAt(path){
 app??=(await import("../dist/server/index.js")).default;
 const response=await app.fetch(new Request("http://localhost"+path),env,ctx);
 assert.equal(response.status,200,path);
 return response.text();
}
function textFields(value,language){
 if(Array.isArray(value))return value.flatMap(item=>textFields(item,language));
 if(value&&typeof value==="object"){
  if("zh" in value||"en" in value){assert.ok(value.zh?.trim());assert.ok(value.en?.trim());return [value[language]];}
  return Object.values(value).flatMap(item=>textFields(item,language));
 }
 return [];
}

test("all six guides have substantial bilingual chapters and FAQ, with valid table rows",()=>{
 assert.equal(pages.length,6);
 for(const [page,guide] of Object.entries(marketingGuides)){
  assert.ok(guide.sections.length>=4,page);
  assert.ok(guide.faq.length>=3,page);
  assert.equal(new Set(guide.sections.map(section=>section.id)).size,guide.sections.length,page);
  for(const language of ["zh","en"])assert.ok(textFields(guide,language).join(" ").length>(language==="zh"?1000:3000),page+" "+language);
  for(const section of guide.sections)if(section.table)for(const row of section.table.rows)assert.equal(row.length,section.table.headers.length,page);
 }
});

test("each public guide renders its own chapters, native FAQs and accessible table wrappers",async()=>{
 for(const [page,guide] of Object.entries(marketingGuides)){
  const html=await htmlAt("/"+page);
  assert.ok(html.includes(`data-guide="${page}"`));
  for(const section of guide.sections){assert.ok(html.includes(`id="${section.id}"`));assert.ok(html.includes(`href="#${section.id}"`));}
  assert.equal((html.match(/<details\b/g)||[]).length,guide.faq.length,page);
  assert.equal((html.match(/id="faq"/g)||[]).length,1,page);
  if(guide.sections.some(section=>section.table)){assert.match(html,/<caption>/);assert.match(html,/role="region"[^>]+tabindex="0"/i);}
 }
});

test("home replaces learning cards with original contour artwork and keeps the site directory",async()=>{
 const html=await htmlAt("/");
 assert.doesNotMatch(html,/不熟悉术语|learning-heading|UNDERSTAND \/ THEN EXPLORE/);
 assert.match(html,/data-contour="orakt"/);
 assert.match(html,/ORAKT 三色渐变线条字标/);
 assert.match(html,/#a3ff12/);assert.match(html,/#00e5ff/);assert.match(html,/#9b5cff/);
 const footer=html.match(/<footer\b[^>]*data-site-footer[\s\S]*?<\/footer>/)?.[0];assert.ok(footer);
 assert.equal((footer.match(/<h2\b/g)||[]).length,4);
 assert.ok((footer.match(/<a\b/g)||[]).length>=24);
 assert.match(footer,/研究风险说明/);
 assert.doesNotMatch(footer,/href="(?:#|javascript:[^"]*|mailto:[^"]*)"/);
 assert.doesNotMatch(footer,/href="\/(?:privacy|terms|contact)"/);
});

test("home renders both redesigned scenes with independent playback and continuous brand artwork",async()=>{
 const html=await htmlAt("/");
 assert.equal((html.match(/data-scene="world"/g)||[]).length,1);
 assert.equal((html.match(/data-scene="chains"/g)||[]).length,1);
 assert.match(html,/GLOBAL OBSERVATORY/);assert.match(html,/CAUSAL INTELLIGENCE/);
 assert.match(html,/aria-label="暂停世界动画"/);assert.match(html,/aria-label="暂停证据链动画"/);
 assert.match(html,/data-animation="permanent-loop"/);
 assert.doesNotMatch(html,/2026 \/ BETA|ORAKT PILOT|密码测试站|已发布快照/);
 assert.match(html,/流程示意 · 非投资结论/);assert.match(html,/非实时数据/);
});

test("six distinct technical notes have bilingual abstracts, methods and explicit limitations",async()=>{
 assert.deepEqual(Object.keys(methodNotes).sort(),pages.slice().sort());
 for(const [page,note] of Object.entries(methodNotes)){
  assert.equal(note.abstract.length,2,page);assert.equal(note.methods.length,3,page);
  for(const language of ["zh","en"]){assert.ok(textFields(note,language).join(" ").length>(language==="zh"?800:2400),page+language);assert.ok(note.boundary[language]);}
  const html=await htmlAt("/"+page);
  assert.ok(html.includes(`data-method-note="${page}"`));
  for(const anchor of ["abstract","methodology"]){assert.ok(html.includes(`id="${anchor}"`));assert.ok(html.includes(`href="#${anchor}"`));}
  assert.match(html,/范围与局限/);
  for(const method of note.methods)if(method.formula){assert.ok(method.formula.definition.zh);assert.ok(method.formula.definition.en);assert.match(html,/模型定义 · 非实测结果/);}
 }
 assert.ok(methodNotes.lab.methods[0].formula.expression.includes("r_f,t"));
 assert.ok(methodNotes.research.boundary.zh.includes("不宣称"));
});

test("all footer and guide cross-page anchors resolve to published headings",async()=>{
 const home=await htmlAt("/");
 const footer=home.match(/<footer\b[^>]*data-site-footer[\s\S]*?<\/footer>/)?.[0]||"";
 const hrefs=[...footer.matchAll(/href="([^"?]+)"/g)].map(match=>match[1]);
 for(const guide of Object.values(marketingGuides))hrefs.push(...guide.next.map(link=>link.href));
 for(const href of new Set(hrefs)){
  const url=new URL(href,"http://localhost");
  if(url.pathname==="/"||pages.includes(url.pathname.slice(1))){
   const html=await htmlAt(url.pathname);
   if(url.hash)assert.ok(html.includes(`id="${url.hash.slice(1)}"`),href);
  }else assert.ok(["/platform","/platform/research","/platform/data","/platform/filings","/account","/access","/access/register","/access/recover"].includes(url.pathname),href);
 }
});

test("educational examples distinguish excess return, alpha, confidence and enabled features",async()=>{
 const lab=await htmlAt("/lab"),research=await htmlAt("/research"),plans=await htmlAt("/plans");
 assert.match(lab,/13%/);assert.match(lab,/10%/);assert.match(lab,/风险调整/);assert.match(lab,/假设例子/);
 assert.match(lab,/验证界面示意/);assert.match(research,/教学报告示意/);
 assert.match(plans,/<b>PLANNED<\/b>/);assert.match(plans,/尚未开放在线订阅与自动扣费/);
 assert.doesNotMatch(plans,/快照导出/);
 const source=await readFile(new URL("../app/SiteFooter.tsx",import.meta.url),"utf8");
 assert.match(source,/<ReleaseStatus language={language}/);
});
