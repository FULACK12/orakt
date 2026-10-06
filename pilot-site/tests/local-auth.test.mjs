import test from "node:test";
import assert from "node:assert/strict";
import {DatabaseSync} from "node:sqlite";
import {readFileSync,readdirSync} from "node:fs";
import {localAuthResponse,readLocalSession,revokeLocalSession} from "../worker/local-auth.mjs";
const origin="https://orakt.test",password="a long test passphrase for ORAKT",newPassword="a changed passphrase for ORAKT";
function setup(t){
 const sql=new DatabaseSync(":memory:");t.after(()=>sql.close());
 for(const file of readdirSync(new URL("../drizzle/",import.meta.url)).filter(f=>f.endsWith(".sql")).sort())sql.exec(readFileSync(new URL(`../drizzle/${file}`,import.meta.url),"utf8"));
 let queue=Promise.resolve();
 const DB={prepare(query){return{bind(...args){const stmt=sql.prepare(query);return{first:async()=>stmt.get(...args)??null,run:async()=>({meta:{changes:stmt.run(...args).changes}})};}};},batch(queries){const run=async()=>{sql.exec("BEGIN");try{const out=[];for(const q of queries)out.push(await q.run());sql.exec("COMMIT");return out;}catch(e){sql.exec("ROLLBACK");throw e;}};const result=queue.then(run);queue=result.catch(()=>{});return result;}};
 return{sql,env:{DB,LOCAL_AUTH_PEPPER:"local-test-only-independent-pepper",LOCAL_AUTH_ENABLED:"true",PILOT_SESSION_SECRET:"local-test-only-session-secret"}};
}
const req=(action,body={},cookie="",headers={})=>new Request(`${origin}/api/auth/local/${action}`,{method:"POST",headers:{Origin:origin,"Content-Type":"application/json","X-ORAKT-Auth":"local",Cookie:cookie,...headers},body:JSON.stringify(body)});
const view=cookie=>new Request(`${origin}/account`,{headers:{cookie}});
async function proof(env,action,cookie="") {const r=await localAuthResponse(req("challenge",{action},cookie),env);assert.equal(r.status,200);return{data:await r.json(),cookie:r.headers.getSetCookie()[0].split(";")[0]};}
async function run(env,action,extra={},cookie=""){const p=await proof(env,action,cookie),response=await localAuthResponse(req(action,{...p.data,username:"test_reader",password,...extra},p.cookie),env);return{response,p,body:await response.json(),cookie:response.headers.getSetCookie().map(v=>v.split(";")[0]).join("; ")};}

test("registration, persistent password login, protected account totals, and logout",async t=>{
 const {env,sql}=setup(t),created=await run(env,"register",{username:"Test_Reader"});assert.equal(created.response.status,201);assert.match(created.body.recoveryKey,/^[a-f0-9]{64}$/);assert.equal(created.body.requiresLogin,true);
 const row=sql.prepare("SELECT * FROM local_auth_accounts").get();assert.equal(row.username,"test_reader");assert.equal(row.kdf,"scrypt-v1");assert.notEqual(row.password_hash,password);assert.notEqual(row.recovery_hash,created.body.recoveryKey);
 const logged=await run(env,"login");assert.equal(logged.response.status,200);assert.match(logged.response.headers.getSetCookie()[0],/HttpOnly; Secure; SameSite=Lax/);
 assert.equal((await readLocalSession(view(logged.cookie),env)).username,"test_reader");assert.equal(await readLocalSession(new Request("https://other.test/account",{headers:{cookie:logged.cookie}}),env),null);
 const app=(await import("../dist/server/index.js")).default,ctx={waitUntil(){},passThroughOnException(){}};
 const overview=await app.fetch(new Request(`${origin}/api/account/overview`,{headers:{cookie:logged.cookie}}),env,ctx);assert.equal(overview.status,200);assert.equal((await overview.json()).account.displayName,"test_reader");
 assert.equal((await app.fetch(new Request(`${origin}/api/research/generate`,{method:"POST",headers:{cookie:logged.cookie}}),env,ctx)).status,405);
 const logout=await app.fetch(new Request(`${origin}/api/access/session`,{method:"DELETE",headers:{Origin:origin,cookie:logged.cookie}}),env,ctx);assert.equal(logout.status,200);assert.equal(logout.headers.getSetCookie().length,7);assert.equal(await readLocalSession(view(logged.cookie),env),null);
});
test("recovery rotates the key and password and revokes every old local session",async t=>{
 const {env}=setup(t),created=await run(env,"register"),first=await run(env,"login"),second=await run(env,"login");
 const reset=await run(env,"recover",{password:newPassword,recoveryKey:created.body.recoveryKey});assert.equal(reset.response.status,200);assert.notEqual(reset.body.recoveryKey,created.body.recoveryKey);
 assert.equal(await readLocalSession(view(first.cookie),env),null);assert.equal(await readLocalSession(view(second.cookie),env),null);
 assert.equal((await run(env,"login")).response.status,401);assert.equal((await run(env,"recover",{password:newPassword,recoveryKey:created.body.recoveryKey})).response.status,401);
 assert.equal((await run(env,"login",{password:newPassword})).response.status,200);
});
test("username normalization is unique and unknown/wrong passwords share the same error",async t=>{
 const {env,sql}=setup(t);await run(env,"register");assert.equal((await run(env,"register",{username:"TEST_READER"})).response.status,409);
 assert.equal(sql.prepare("SELECT count(*) AS n FROM local_auth_accounts").get().n,1);
 const unknown=await run(env,"login",{username:"not_registered"}),wrong=await run(env,"login",{password:newPassword});assert.equal(unknown.response.status,401);assert.deepEqual(unknown.body,wrong.body);
});
test("CSRF, browser and action binding, disabled configuration and bounded inputs fail closed",async t=>{
 const {env,sql}=setup(t),p=await proof(env,"register");
 assert.equal((await localAuthResponse(req("register",{...p.data,username:"test_reader",password}),env)).status,401);
 assert.equal((await localAuthResponse(req("login",{...p.data,username:"test_reader",password},p.cookie),env)).status,401);
 assert.equal((await localAuthResponse(req("challenge",{action:"login"},"",{Origin:"https://evil.test"}),env)).status,403);
 assert.equal((await localAuthResponse(req("challenge",{action:"login"},"",{"X-ORAKT-Auth":""}),env)).status,403);
 assert.equal((await localAuthResponse(req("challenge",{action:"login",extra:"x".repeat(5000)}),env)).status,400);
 assert.equal((await localAuthResponse(req("challenge",{action:"login"}),{...env,LOCAL_AUTH_ENABLED:"false"})).status,503);
 sql.exec("UPDATE local_auth_challenges SET expires_at=1");assert.equal((await localAuthResponse(req("register",{...p.data,username:"test_reader",password},p.cookie),env)).status,401);
});
test("concurrent login proof is consumed exactly once; pending logout cancels KDF result",async t=>{
 const {env}=setup(t);await run(env,"register");const p=await proof(env,"login"),body={...p.data,username:"test_reader",password};
 const results=await Promise.all([1,2].map(()=>localAuthResponse(req("login",body,p.cookie),env)));assert.deepEqual(results.map(r=>r.status).sort(),[200,401]);
 const q=await proof(env,"login"),pending=localAuthResponse(req("login",{...q.data,username:"test_reader",password},q.cookie),env);await revokeLocalSession(view(q.cookie),env);assert.equal((await pending).status,401);
});
test("username throttling applies before more password checks",async t=>{
 const {env}=setup(t);for(let i=0;i<8;i++)assert.equal((await run(env,"login",{username:"unknown_user"})).response.status,401);
 assert.equal((await run(env,"login",{username:"unknown_user"})).response.status,429);
});
