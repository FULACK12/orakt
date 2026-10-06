import test from "node:test";
import assert from "node:assert/strict";
import {DatabaseSync} from "node:sqlite";
import {readFileSync,readdirSync} from "node:fs";
import {SignJWT,generateKeyPair,createLocalJWKSet,exportJWK} from "jose";
import {googleAuthResponse,readGoogleSession,revokeGoogleSession,verifyGoogleCredential,googleConfig} from "../worker/google-auth.mjs";
const origin="https://orakt.test",clientId="test-client.apps.googleusercontent.com";
const keys=await generateKeyPair("RS256");
const jwk={...await exportJWK(keys.publicKey),kid:"local-test-key",use:"sig",alg:"RS256"};
const resolver=createLocalJWKSet({keys:[jwk]});
function setup(t){
  const sql=new DatabaseSync(":memory:");t.after(()=>sql.close());
  for(const file of readdirSync(new URL("../drizzle/",import.meta.url)).filter(f=>f.endsWith(".sql")).sort())sql.exec(readFileSync(new URL(`../drizzle/${file}`,import.meta.url),"utf8"));
  let queue=Promise.resolve();
  const DB={prepare(query){return{bind(...args){const s=sql.prepare(query);return{first:async()=>s.get(...args)??null,run:async()=>({meta:{changes:s.run(...args).changes}})};}};},batch(queries){const run=async()=>{sql.exec("BEGIN");try{const output=[];for(const q of queries)output.push(await q.run());sql.exec("COMMIT");return output;}catch(e){sql.exec("ROLLBACK");throw e;}};const result=queue.then(run);queue=result.catch(()=>{});return result;}};
  return{sql,env:{DB,GOOGLE_CLIENT_ID:clientId,GOOGLE_AUTH_ORIGIN:origin,PILOT_SESSION_SECRET:"local-test-secret"}};
}
const req=(path,body={},cookie="",headers={})=>new Request(`${origin}/api/auth/google/${path}`,{method:"POST",headers:{Origin:origin,"Content-Type":"application/json","X-ORAKT-Auth":"google",Cookie:cookie,...headers},body:JSON.stringify(body)});
async function jwt(nonce,overrides={},privateKey=keys.privateKey){const now=Math.floor(Date.now()/1000);return new SignJWT({sub:"stable-google-sub",iss:"https://accounts.google.com",aud:clientId,iat:now,exp:now+3600,nonce,...overrides}).setProtectedHeader({alg:"RS256",kid:jwk.kid}).sign(privateKey);}
async function challenge(env,cookie=""){
  const response=await googleAuthResponse(req("challenge",{},cookie),env,resolver);assert.equal(response.status,200);
  const data=await response.json();return{data,cookie:response.headers.getSetCookie()[0].split(";")[0],proof:{nonce:data.nonce,csrf:data.csrf,credential:await jwt(data.nonce)}};
}

test("Google RS256 login creates server-revocable, hashed, host-bound read-only session",async t=>{
  const {env,sql}=setup(t),item=await challenge(env);
  const response=await googleAuthResponse(req("verify",item.proof,item.cookie),env,resolver);assert.equal(response.status,200);
  const cookie=response.headers.getSetCookie()[0].split(";")[0];assert.match(response.headers.getSetCookie()[0],/HttpOnly; Secure; SameSite=Lax/);
  const request=new Request(`${origin}/platform`,{headers:{cookie}});const session=await readGoogleSession(request,env);
  assert.equal(session.subject,"stable-google-sub");assert.notEqual(sql.prepare("SELECT id FROM google_auth_sessions").get().id,cookie.split("=")[1]);
  assert.equal(await readGoogleSession(new Request("https://wrong.test/",{headers:{cookie}}),env),null);
  const app=(await import("../dist/server/index.js")).default,ctx={waitUntil(){},passThroughOnException(){}};
  assert.equal((await app.fetch(new Request(`${origin}/api/research-report-index`,{headers:{cookie}}),env,ctx)).status,200);
  assert.equal((await app.fetch(new Request(`${origin}/api/research/generate`,{method:"POST",headers:{cookie}}),env,ctx)).status,405);
  assert.equal((await (await app.fetch(new Request(`${origin}/api/access/session`,{headers:{cookie}}),env,ctx)).json()).provider,"google");
  assert.equal((await app.fetch(new Request(`${origin}/api/access/session`,{method:"DELETE",headers:{Origin:origin,cookie}}),env,ctx)).status,200);
  assert.equal(await readGoogleSession(request,env),null);
});

test("Google validates signature, issuer, audience, nonce, subject and expiry",async()=>{
  const badKey=await generateKeyPair("RS256");
  for(const changes of [{iss:"https://evil.test"},{aud:"other-client"},{azp:"other-client"},{nonce:"wrong"},{sub:""},{exp:1},{iat:Math.floor(Date.now()/1000)+600}])await assert.rejects(()=>jwt("expected",changes).then(token=>verifyGoogleCredential(token,clientId,"expected",resolver)));
  await assert.rejects(()=>jwt("expected",{},badKey.privateKey).then(token=>verifyGoogleCredential(token,clientId,"expected",resolver)));
});

test("Google CSRF, browser binding, configured origin, size and expiry fail closed",async t=>{
  const {env,sql}=setup(t),item=await challenge(env);
  assert.equal((await googleAuthResponse(req("verify",item.proof),env,resolver)).status,401);
  assert.equal((await googleAuthResponse(req("verify",{...item.proof,csrf:"0".repeat(64)},item.cookie),env,resolver)).status,401);
  assert.equal((await googleAuthResponse(req("challenge",{},"",{Origin:"https://evil.test"}),env,resolver)).status,403);
  assert.equal((await googleAuthResponse(req("challenge",{},"",{"X-ORAKT-Auth":""}),env,resolver)).status,403);
  assert.equal((await googleAuthResponse(req("challenge",{extra:"a".repeat(20000)}),env,resolver)).status,400);
  assert.equal((await googleAuthResponse(req("challenge"),{...env,GOOGLE_AUTH_ORIGIN:"https://other.test"},resolver)).status,503);
  assert.equal(googleConfig(new Request("https://other.test/"),env).enabled,false);
  sql.exec("UPDATE google_auth_challenges SET expires_at=1");
  assert.equal((await googleAuthResponse(req("verify",item.proof,item.cookie),env,resolver)).status,401);
});

test("Google accepts each challenge once even under concurrent verification",async t=>{
  const {env}=setup(t),item=await challenge(env);
  const responses=await Promise.all([1,2].map(()=>googleAuthResponse(req("verify",item.proof,item.cookie),env,resolver)));
  assert.deepEqual(responses.map(r=>r.status).sort(),[200,401]);
});

test("Google logout cannot be undone by a verification already in flight",async t=>{
  const {env}=setup(t),item=await challenge(env);let release,entered;
  const started=new Promise(resolve=>entered=resolve),barrier=new Promise(resolve=>release=resolve);
  const pending=googleAuthResponse(req("verify",item.proof,item.cookie),env,async(...args)=>{entered();await barrier;return resolver(...args);});
  await started;await revokeGoogleSession(new Request(`${origin}/`,{headers:{cookie:item.cookie}}),env);release();
  assert.equal((await pending).status,401);
  const next=await challenge(env);const response=await googleAuthResponse(req("verify",next.proof,next.cookie),env,resolver);
  await revokeGoogleSession(new Request(`${origin}/`,{headers:{cookie:next.cookie}}),env);
  assert.equal(await readGoogleSession(new Request(`${origin}/`,{headers:{cookie:response.headers.getSetCookie()[0].split(";")[0]}}),env),null);
});

test("Google challenge refresh invalidates the old proof and authentication is rate-limited",async t=>{
  const {env}=setup(t),first=await challenge(env);await challenge(env,first.cookie);
  assert.equal((await googleAuthResponse(req("verify",first.proof,first.cookie),env,resolver)).status,401);
  for(let i=3;i<24;i++)assert.equal((await googleAuthResponse(req("challenge"),env,resolver)).status,200);
  assert.equal((await googleAuthResponse(req("challenge"),env,resolver)).status,429);
});
