import test from "node:test";
import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {accountAccessView,createReadSequence,nextAccountCheck} from "../app/account/account-state.mjs";
import {authJsonGet} from "../app/access/auth-request.mjs";

const now=Date.parse("2026-10-01T12:00:00Z");
const member={status:"active",role:"member",effectivePlan:"research",expired:false,expiresAt:new Date(now+1000).toISOString(),permissions:{map:true,reports:true,research:true,manageUsers:false}};

test("membership display expires at the boundary, never grants client-only access",()=>{
 assert.equal(accountAccessView(member,now).reports,true);
 const expired=accountAccessView(member,now+1000);
 assert.equal(expired.inactiveGrant,true);assert.equal(expired.reports,false);assert.equal(expired.research,false);assert.equal(expired.map,true);assert.equal(expired.plan,"EXPLORER");
 assert.equal(accountAccessView({...member,permissions:{map:true,reports:false,research:false}},now).reports,false);
 assert.equal(accountAccessView({...member,expired:true},now).reports,false);
});
test("administrator grant is independent of expired membership, but suspension still wins",()=>{
 const admin={...member,role:"admin",permissions:{map:true,reports:true,research:true,manageUsers:true}};
 const view=accountAccessView(admin,now+1000);assert.equal(view.plan,"ADMIN");assert.equal(view.reports,true);assert.equal(view.manageUsers,true);
 const paused=accountAccessView({...admin,status:"suspended"},now);for(const permission of ["map","reports","research","manageUsers"])assert.equal(paused[permission],false);
});
test("renewal timer uses nearest session/grant expiry and never an unbounded timer",()=>{
 assert.equal(nextAccountCheck({membership:member},now),1025);
 assert.equal(nextAccountCheck({expiresAt:new Date(now+100).toISOString(),membership:member},now),125);
 assert.equal(nextAccountCheck({membership:{expiresAt:"invalid"}},now),60000);
 assert.equal(nextAccountCheck({membership:member},now+2000),60000);
 assert.equal(nextAccountCheck({expiresAt:new Date(now+86400000*365).toISOString()},now),60000);
});
test("switching account/query invalidates previous read and cannot cancel the new one",()=>{
 const sequence=createReadSequence(),a=sequence.begin(),b=sequence.begin();
 assert.equal(a.signal.aborted,true);assert.equal(a.isCurrent(),false);assert.equal(b.isCurrent(),true);
 a.cancel();assert.equal(b.isCurrent(),true);sequence.cancel();assert.equal(b.isCurrent(),false);
});
test("reverse-order audit completions and stale errors cannot replace current account history",async()=>{
 const sequence=createReadSequence();let finishA,shown=null,error=null;
 const a=sequence.begin();
 const first=authJsonGet("/audit/A",{signal:a.signal,fetchImpl:async()=>({ok:true,json:()=>new Promise(resolve=>{finishA=resolve;})})})
  .then(result=>{if(a.isCurrent())shown=result;}).catch(e=>{if(a.isCurrent())error=e;});
 await Promise.resolve();await Promise.resolve();
 const b=sequence.begin();
 const result=await authJsonGet("/audit/B",{signal:b.signal,fetchImpl:async()=>({ok:true,json:async()=>({targetId:"B",events:[]})})});
 if(b.isCurrent())shown=result;
 finishA({targetId:"A",events:[{targetId:"A"}]});await first;
 assert.equal(shown.targetId,"B");assert.equal(error,null);
});
test("HTTP auth failures retain status so account expiry is not mislabelled as generic loading failure",async()=>{
 await assert.rejects(authJsonGet("/account",{fetchImpl:async()=>({ok:false,status:401})}),e=>e.status===401);
 await assert.rejects(authJsonGet("/admin",{fetchImpl:async()=>({ok:false,status:403})}),e=>e.status===403);
});
test("admin UI gates stale lists, binds audit results, blocks editing while saving, and reconciles uncertain writes",async()=>{
 const source=await readFile(new URL("../app/admin/users/AdminUsers.tsx",import.meta.url),"utf8");
 for(const pattern of [/loading\|\|!data/,/setData\(null\)/,/result.targetId!==targetId/,/event.targetId!==targetId/,/fieldset disabled=\{editorDisabled\}/,/operation.current\|\|!selected/,/data.page/,/r.status>=500/,/可能已保存/,/auditState==="error"/,/已核验：该账号暂无权限变更记录/])assert.match(source,pattern);
});
test("account UI rechecks on visibility/focus, reports check time, and conceals stale positive permissions while checking",async()=>{
 const source=await readFile(new URL("../app/account/AccountCenter.tsx",import.meta.url),"utf8");
 for(const pattern of [/nextAccountCheck\(v.account\)/,/visibilitychange/,/visible=\(\)=>check\(true\)/,/addEventListener\("focus"/,/最近核验/,/loading\?<p role="status"/,/授权来源记录/,/setClock\(Date.now\(\)\)/])assert.match(source,pattern);
});
