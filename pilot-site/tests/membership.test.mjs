import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync,existsSync,readdirSync} from "node:fs";
import {memberDatabase} from "./member-fixture.mjs";
import {memberFor,accessFor,memberAdminResponse} from "../worker/membership.mjs";
const origin="https://orakt.test",ctx={waitUntil(){},passThroughOnException(){}};
const identity=(s="reader")=>({provider:"chatgpt",subject:s,displayName:"Test "+s,accountId:"ref-"+s,expiresAt:null,createdAt:null});
function setup(t){const db=memberDatabase();t.after(()=>db.sql.close());return{...db,env:{DB:db.DB,PILOT_SESSION_SECRET:"test-only-membership-secret",ASSETS:{fetch:async()=>new Response("should not serve reports",{status:500})}}};}
const req=(path,subject="reader",method="GET",body,extra={})=>new Request(origin+path,{method,headers:{"oai-authenticated-user-id":subject,"oai-authenticated-user-email":"test@example.com",...(method==="POST"?{Origin:origin,"Content-Type":"application/json","X-ORAKT-Admin":"access"}:{}),...extra},...(body?{body:JSON.stringify(body)}:{})});
const worker=async()=> (await import("../dist/server/index.js")).default;
test("durable identities deduplicate without merging providers and polling does not inflate activity",async t=>{
 const {env,sql}=setup(t);const a=await memberFor(env,identity()),b=await memberFor(env,identity());assert.equal(a.row.id,b.row.id);assert.equal(a.row.last_seen_at,null);assert.equal(a.access.permissions.reports,false);assert.equal(a.access.permissions.manageUsers,false);
 await memberFor(env,{...identity(),provider:"google"});assert.equal(sql.prepare("SELECT COUNT(*) n FROM member_accounts").get().n,2);
 await memberFor(env,identity(),true);assert.ok((await memberFor(env,identity())).row.last_seen_at);assert.equal(sql.prepare("SELECT COUNT(*) n FROM member_accounts").get().n,2);
});
test("grants fail closed for expiry, invalid kinds, suspension and unbound admin",()=>{
 const row={id:"one",provider:"local",legacy_ref:"ref",status:"active",plan:"signal",expires_at:Date.now()+10000,grant_kind:"complimentary"};
 assert.equal(accessFor(row,{}).permissions.reports,true);
 for(const changes of [{expires_at:1},{expires_at:null},{grant_kind:"free"},{grant_kind:"invalid"},{status:"suspended"}])assert.equal(accessFor({...row,...changes},{}).permissions.reports,false);
 assert.equal(accessFor(row,{ORAKT_ADMIN_REFERENCE:"local:ref"}).permissions.manageUsers,true);
 assert.equal(accessFor(row,{ORAKT_ADMIN_ACCOUNT_ID:"different",ORAKT_ADMIN_REFERENCE:"local:ref"}).permissions.manageUsers,false);
});
test("free catalog is sanitized; bodies, raw files and premium aggregates require server authorization",async t=>{
 const {env}=setup(t),app=await worker();
 const index=await (await app.fetch(req("/api/research-report-index"),env,ctx)).json();assert.equal(index.reports.length,406);assert.deepEqual(Object.keys(index.reports[0]).sort(),["companyName","createdAt","id","marketRegion","sector","ticker"].sort());
 for(const path of ["/api/research-report?id=local-566&plan=research","/api/sec-evidence","/api/entry-backtest-status","/api/semiconductor-comparison","/api/supply-chain-sites","/api/admin/users"])assert.equal((await app.fetch(req(path),env,ctx)).status,403,path);
 assert.equal((await app.fetch(req("/snapshot/research-reports/local-566.json"),env,ctx)).status,404);
 assert.equal((await app.fetch(req("/api/research/generate","reader","POST",{}),env,ctx)).status,405);
 const overview=await (await app.fetch(req("/api/account/overview"),env,ctx)).json();assert.equal(overview.account.provider,"chatgpt");assert.equal(overview.account.membership.effectivePlan,"explorer");assert.doesNotMatch(JSON.stringify(overview),/test@example.com/);
 const logout=await (await app.fetch(req("/api/access/session","reader","DELETE",null,{Origin:origin}),env,ctx)).json();assert.equal(logout.signOutHref,"/signout-with-chatgpt?return_to=%2Faccess");
 assert.equal((await app.fetch(new Request(origin+"/api/research-report-index",{headers:{"oai-authenticated-user-id":"alone"}}),env,ctx)).status,401);
});
test("explicit administrator can grant, audit, expire and revoke access; users cannot self-upgrade",async t=>{
 const {env,sql}=setup(t),owner=await memberFor(env,identity("owner")),reader=await memberFor(env,identity()),app=await worker();env.ORAKT_ADMIN_ACCOUNT_ID=owner.row.id;
 const body={id:reader.row.id,revision:0,plan:"signal",status:"active",grantKind:"complimentary",expiresAt:Date.now()+86400000,reason:"Approved test access"};
 assert.equal((await app.fetch(req("/api/admin/user-access","reader","POST",body),env,ctx)).status,403);
 assert.equal((await app.fetch(req("/api/admin/user-access","owner","POST",body,{Origin:"https://evil.test"}),env,ctx)).status,403);
 assert.equal((await app.fetch(req("/api/admin/user-access","owner","POST",{...body,role:"admin"}),env,ctx)).status,400);
 assert.equal((await app.fetch(req("/api/admin/user-access","owner","POST",body),env,ctx)).status,200);
 const detail=await app.fetch(req("/api/research-report?id=local-566"),env,ctx);assert.equal(detail.status,200);const full=await detail.json();assert.equal(full.report.competitorComparison,undefined);assert.deepEqual(full.restrictedSections,["competitorComparison"]);
 assert.equal((await app.fetch(req("/api/entry-backtest-status"),env,ctx)).status,403);
 assert.equal((await app.fetch(req("/api/admin/users"),env,ctx)).status,403);
 assert.equal((await app.fetch(req("/api/admin/user-access","owner","POST",body),env,ctx)).status,409);
 assert.equal(sql.prepare("SELECT COUNT(*) n FROM member_audit").get().n,1);
 const directory=await (await app.fetch(req("/api/admin/users","owner"),env,ctx)).json();assert.equal(directory.stats.totalAccounts,2);assert.equal(directory.stats.complimentary,1);assert.equal(directory.stats.manuallyConfirmedPaid,0);
 sql.prepare("UPDATE member_accounts SET expires_at=1 WHERE id=?").run(reader.row.id);assert.equal((await app.fetch(req("/api/research-report?id=local-566"),env,ctx)).status,403);
 assert.equal((await app.fetch(req("/api/admin/user-access","owner","POST",{...body,revision:1,plan:"research",grantKind:"manual_paid"}),env,ctx)).status,200);
 assert.equal((await app.fetch(req("/api/entry-backtest-status"),env,ctx)).status,200);
 assert.equal((await app.fetch(req("/api/admin/user-access","owner","POST",{...body,revision:2,plan:"explorer",grantKind:"free",expiresAt:null,status:"suspended"}),env,ctx)).status,200);
 assert.equal((await app.fetch(req("/api/snapshot"),env,ctx)).status,403);assert.equal((await app.fetch(req("/api/account/overview"),env,ctx)).status,200);
});
test("concurrent updates produce exactly one audit; GET does not import historical accounts",async t=>{
 const {env,sql}=setup(t),owner=await memberFor(env,identity("owner"));env.ORAKT_ADMIN_ACCOUNT_ID=owner.row.id;const actor=await memberFor(env,identity("owner")),reader=await memberFor(env,identity());
 const body={id:reader.row.id,revision:0,plan:"signal",status:"active",grantKind:"complimentary",expiresAt:Date.now()+86400000,reason:"Concurrent access test"};
 const out=await Promise.all([1,2].map(()=>memberAdminResponse(req("/api/admin/user-access","owner","POST",body),env,actor)));assert.deepEqual(out.map(r=>r.status).sort(),[200,409]);assert.equal(sql.prepare("SELECT COUNT(*) n FROM member_audit").get().n,1);
 sql.prepare("INSERT INTO local_auth_accounts (id,username,salt,password_hash,kdf,recovery_hash,auth_version,created_at) VALUES ('legacy','legacy','s','p','scrypt-v1','r','v',1)").run();
 const list=await (await memberAdminResponse(req("/api/admin/users","owner"),env,actor)).json();assert.equal(list.pendingLocalAccounts,1);assert.equal(list.stats.totalAccounts,2);
 assert.equal((await memberAdminResponse(req("/api/admin/import-local","owner","POST"),env,actor)).status,200);assert.equal(sql.prepare("SELECT COUNT(*) n FROM member_accounts").get().n,3);
});
test("private report bodies are absent from static files and client bundles",()=>{
 assert.equal(existsSync(new URL("../public/snapshot/research-reports",import.meta.url)),false);
 assert.equal(existsSync(new URL("../dist/client/snapshot/research-reports",import.meta.url)),false);
 const dir=new URL("../dist/client/assets/",import.meta.url);if(existsSync(dir))for(const f of readdirSync(dir).filter(f=>f.endsWith(".js")))assert.ok(!readFileSync(new URL(f,dir),"utf8").includes("H4sIAAAAA"),"compressed report map must not enter client assets");
});

test("directory statistics have an explicit read time and correct activity/payment boundaries",async t=>{
 const {env,sql}=setup(t),now=Date.parse("2026-10-01T12:00:00Z");t.mock.method(Date,"now",()=>now);
 const owner=await memberFor(env,identity("stats-owner"));env.ORAKT_ADMIN_ACCOUNT_ID=owner.row.id;
 const actor=await memberFor(env,identity("stats-owner"));
 const cases=[
  ["paid",now-86400000,"signal","manual_paid",now+1,"active"],
  ["gift",now-7*86400000,"research","complimentary",now+1,"active"],
  ["expired",now-30*86400000,"signal","manual_paid",now,"active"],
  ["suspended",now-30*86400000-1,"research","manual_paid",now+1,"suspended"],
 ];
 for(const [name,seen,plan,grant,expires,status] of cases){const member=await memberFor(env,identity(name));sql.prepare("UPDATE member_accounts SET last_seen_at=?,plan=?,grant_kind=?,expires_at=?,status=? WHERE id=?").run(seen,plan,grant,expires,status,member.row.id);}
 const data=await (await memberAdminResponse(req("/api/admin/users","stats-owner"),env,actor)).json();
 assert.equal(data.asOf,new Date(now).toISOString());assert.equal(data.countsAre,"provider_accounts_not_unique_people");
 assert.equal(data.stats.totalAccounts,5);assert.equal(data.stats.active24h,1);assert.equal(data.stats.active7d,2);assert.equal(data.stats.active30d,3);
 assert.equal(data.stats.manuallyConfirmedPaid,1);assert.equal(data.stats.complimentary,1);assert.equal(data.stats.suspended,1);
});
test("admin history identifies its exact account including verified-empty results",async t=>{
 const {env}=setup(t),owner=await memberFor(env,identity("audit-owner")),a=await memberFor(env,identity("audit-a")),b=await memberFor(env,identity("audit-b"));env.ORAKT_ADMIN_ACCOUNT_ID=owner.row.id;
 const actor=await memberFor(env,identity("audit-owner"));
 const body={id:a.row.id,revision:0,plan:"signal",status:"active",grantKind:"complimentary",expiresAt:Date.now()+86400000,reason:"Account-specific audit test"};
 assert.equal((await memberAdminResponse(req("/api/admin/user-access","audit-owner","POST",body),env,actor)).status,200);
 const aHistory=await (await memberAdminResponse(req("/api/admin/user-audit?id="+a.row.id,"audit-owner"),env,actor)).json();
 const bHistory=await (await memberAdminResponse(req("/api/admin/user-audit?id="+b.row.id,"audit-owner"),env,actor)).json();
 assert.equal(aHistory.targetId,a.row.id);assert.equal(aHistory.events.length,1);assert.equal(aHistory.events[0].targetId,a.row.id);
 assert.equal(bHistory.targetId,b.row.id);assert.deepEqual(bHistory.events,[]);
});
test("account polling and local import do not manufacture product visits",async t=>{
 const {env,sql}=setup(t),owner=await memberFor(env,identity("poll-owner"));env.ORAKT_ADMIN_ACCOUNT_ID=owner.row.id;const actor=await memberFor(env,identity("poll-owner")),app=await worker();
 for(let i=0;i<2;i++){
  const overview=await (await app.fetch(req("/api/account/overview","poll-owner"),env,ctx)).json();assert.ok(Number.isFinite(Date.parse(overview.checkedAt)));
 }
 assert.equal(sql.prepare("SELECT last_seen_at FROM member_accounts WHERE id=?").get(owner.row.id).last_seen_at,null);
 sql.prepare("INSERT INTO local_auth_accounts (id,username,salt,password_hash,kdf,recovery_hash,auth_version,created_at) VALUES ('import-stat','import-stat','s','p','scrypt-v1','r','v',1)").run();
 await memberAdminResponse(req("/api/admin/import-local","poll-owner","POST"),env,actor);
 const data=await (await memberAdminResponse(req("/api/admin/users","poll-owner"),env,actor)).json();
 assert.equal(data.stats.totalAccounts,2);assert.equal(data.stats.active24h,0);assert.equal(data.pendingLocalAccounts,0);
});
