import assert from "node:assert/strict";
import test from "node:test";
import {readFile} from "node:fs/promises";
import ts from "typescript";
import {marketingGuides} from "../app/marketing-guide-content.ts";
import {methodNotes} from "../app/marketing-method-notes.ts";

const copyFiles=[
 "OraktLanding.tsx", "OraktMegaNav.tsx", "SiteFooter.tsx", "PilotDashboard.tsx",
 "account/AccountCenter.tsx", "admin/users/AdminUsers.tsx", "product-plans.ts",
 "marketing-guide-content.ts", "marketing-method-notes.ts", "marketing-pages.ts",
 "access/AccessPortal.tsx", "access/AccessScreen.tsx", "access/GoogleLogin.tsx",
 "access/LocalLogin.tsx", "access/WalletLogin.tsx", "MarketExpansion.tsx",
 "ReportCatalogPreview.tsx",
];
const read=file=>readFile(new URL("../app/"+file,import.meta.url),"utf8");

// Read literal UI copy rather than renaming compatibility paths, API fields or CSS classes.
function literalCopy(source,file){
 const tree=ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
 const result=[];
 function visit(node){
  if(ts.isStringLiteralLike(node)||ts.isTemplateHead(node)||ts.isTemplateMiddle(node)||ts.isTemplateTail(node)||ts.isJsxText(node)){
   const text=node.text.trim();
   const parent=node.parent;
   const attribute=parent&&ts.isJsxAttribute(parent)?parent.name.getText(tree):null;
   if(text&&!/^(?:\.\.?\/|\/|https?:)/.test(text)&&!['className','id','href','src'].includes(attribute))result.push(text);
  }
  ts.forEachChild(node,visit);
 }
 visit(tree);return result;
}

test("public interface copy has no beta, pilot or snapshot positioning",async()=>{
 for(const file of copyFiles){
  for(const text of literalCopy(await read(file),file)){
   // Financial beta is a model definition, not release-stage branding.
   if(text.includes("Beta 则描述")||text.includes("Beta describes sensitivity"))continue;
   assert.doesNotMatch(text,/\b(?:bata|beta|pilot|snapshots?)\b|快照|测试版|测试快照|密码测试站|进入内测|公测|赠送 \/ 测试|Complimentary \/ test/i,file+": "+text);
  }
 }
});

test("release wording retains data cutoffs, non-live status and read-only access",async()=>{
 const footer=await read("SiteFooter.tsx"),account=await read("account/AccountCenter.tsx"),dashboard=await read("PilotDashboard.tsx");
 assert.match(footer,/数据版本日期/);assert.match(footer,/不是实时交易终端/);assert.match(footer,/not a live trading terminal/);
 assert.match(account,/非实时更新/);assert.match(account,/Not a live feed/);assert.match(account,/snapshotAt/);
 assert.match(await read("DataLibrary.tsx"),/目录反映已发布内容/);assert.match(await read("DataLibrary.tsx"),/不再用历史快照扮演系统运行状态/);
 assert.match(dashboard,/not current executable prices/);assert.match(dashboard,/仅供只读查阅/);
 assert.match(dashboard,/Public generation and feedback writes are disabled/);
 assert.match(dashboard,/fetch\("\/api\/snapshot"/);
});

test("grant wording removes test labels without implying payment",async()=>{
 const account=await read("account/AccountCenter.tsx"),admin=await read("admin/users/AdminUsers.tsx");
 assert.match(account,/赠送授权，不代表付款/);assert.match(account,/Complimentary access, not a payment/);
 assert.match(admin,/value="complimentary"/);assert.match(admin,/value="manual_paid"/);
 assert.match(admin,/已人工确认线下付款/);
});

test("technical definitions and financial limitations remain explicit",async()=>{
 const guides=JSON.stringify(marketingGuides),notes=JSON.stringify(methodNotes),landing=await read("OraktLanding.tsx");
 assert.match(guides,/Beta 则描述/);assert.match(guides,/假设例子 · 不是 ORAKT 业绩/);
 assert.match(guides,/历史回测属于模拟，不是实际交易业绩/);assert.match(guides,/不能保证未来结果/);
 assert.match(notes,/测试集/);assert.match(notes,/不是本站已估计的业绩结果/);
 assert.match(landing,/尚未开放在线订阅与自动扣费/);assert.match(landing,/automatic billing are not active yet/);
});
