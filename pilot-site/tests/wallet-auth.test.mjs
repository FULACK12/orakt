import test from "node:test";
import assert from "node:assert/strict";
import {DatabaseSync} from "node:sqlite";
import {readFileSync,readdirSync} from "node:fs";
import {walletAuthResponse, readWalletSession, revokeWalletSession} from "../worker/wallet-auth.mjs";

const origin = "https://orakt.test";
const secret = "test-only-wallet-secret-not-a-production-credential";
function setup(t) {
  const sqlite = new DatabaseSync(":memory:");
  for(const f of readdirSync(new URL("../drizzle/",import.meta.url)).filter(f=>f.endsWith(".sql")).sort())sqlite.exec(readFileSync(new URL("../drizzle/"+f,import.meta.url),"utf8"));


  t.after(() => sqlite.close());
  let queue = Promise.resolve();
  const DB = {prepare(sql) {return {bind(...values) {const stmt = sqlite.prepare(sql); return {first: async () => stmt.get(...values) ?? null, run: async () => ({meta: {changes: stmt.run(...values).changes}})};}};}, batch(list) {const execute = async () => {sqlite.exec("BEGIN"); try {const results=[]; for(const q of list) results.push(await q.run()); sqlite.exec("COMMIT"); return results;} catch(e) {sqlite.exec("ROLLBACK"); throw e;}}; const result = queue.then(execute); queue = result.catch(() => {}); return result;}};
  return {env: {DB, PILOT_SESSION_SECRET: secret}, sqlite};
}
function base58(bytes) {
  let value = BigInt(`0x${Buffer.from(bytes).toString("hex")}`), result = "";
  const alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
  while(value) {result = alphabet[Number(value % 58n)] + result; value /= 58n;}
  for(const byte of bytes) {if(byte)break; result = `1${result}`;} return result;
}
const request = (path, body, cookie = "", extra = {}) => new Request(`${origin}${path}`, {method: "POST", headers: {Origin: origin, "Content-Type": "application/json", Cookie: cookie, ...extra}, body: JSON.stringify(body)});
async function identity() {
  const keys = await crypto.subtle.generateKey("Ed25519", true, ["sign", "verify"]);
  return {...keys, address: base58(new Uint8Array(await crypto.subtle.exportKey("raw", keys.publicKey)))};
}
async function challenge(env, user, cookie = "") {
  const response = await walletAuthResponse(request("/api/wallet/challenge", {address: user.address}, cookie), env);
  assert.equal(response.status, 200);
  const data = await response.json();
  const signature = Buffer.from(await crypto.subtle.sign("Ed25519", user.privateKey, new TextEncoder().encode(data.message))).toString("base64url");
  return {data, cookie: response.headers.getSetCookie()[0].split(";")[0], proof: {address: user.address, nonce: data.nonce, signature}};
}

test("real Ed25519 signature creates host-bound revocable read-only session", async t => {
  const {env} = setup(t), user = await identity(), item = await challenge(env, user);
  assert.match(item.data.nonce, /^[a-zA-Z0-9]{64}$/);
  assert.match(item.data.message, /No transaction or spending approval/);
  const response = await walletAuthResponse(request("/api/wallet/verify", item.proof, item.cookie), env);
  assert.equal(response.status, 200);
  const cookies = response.headers.getSetCookie();
  assert.ok(cookies[0].includes("HttpOnly; Secure; SameSite=Lax"));
  const authenticated = new Request(`${origin}/api/snapshot`, {headers: {Cookie: cookies[0].split(";")[0]}});
  const session = await readWalletSession(authenticated, secret, env.DB);
  assert.equal(session.address, user.address); assert.equal(session.scope, "published_read_only");
  assert.equal(await readWalletSession(new Request("https://another.example/", {headers: authenticated.headers}), secret, env.DB), null);
  await revokeWalletSession(authenticated, env);
  assert.equal(await readWalletSession(authenticated, secret, env.DB), null, "copied old cookie is invalid after logout");
});

test("nonce consumption prevents sequential and concurrent replay", async t => {
  const {env} = setup(t), item = await challenge(env, await identity());
  const responses = await Promise.all([1,2].map(() => walletAuthResponse(request("/api/wallet/verify", item.proof, item.cookie), env)));
  assert.deepEqual(responses.map(r => r.status).sort(), [200,401]);
  assert.equal((await walletAuthResponse(request("/api/wallet/verify", item.proof, item.cookie), env)).status, 401);
});

test("logout cancels a pending proof and revokes a proof completed with an in-flight cookie", async t => {
  const {env} = setup(t), user = await identity(), first = await challenge(env, user);
  const exiting = new Request(`${origin}/api/access/session`, {headers: {Cookie:first.cookie}});
  await revokeWalletSession(exiting, env);
  assert.equal((await walletAuthResponse(request("/api/wallet/verify",first.proof,first.cookie),env)).status,401);
  const second = await challenge(env,user);
  const completed = await walletAuthResponse(request("/api/wallet/verify",second.proof,second.cookie),env);
  assert.equal(completed.status,200);
  await revokeWalletSession(new Request(`${origin}/api/access/session`,{headers:{Cookie:second.cookie}}),env);
  const cookie = completed.headers.getSetCookie()[0].split(";")[0];
  assert.equal(await readWalletSession(new Request(`${origin}/`,{headers:{Cookie:cookie}}),secret,env.DB),null);
});

test("wrong browser, expired nonce, wrong signature and wrong address are denied", async t => {
  const {env, sqlite} = setup(t), item = await challenge(env, await identity());
  assert.equal((await walletAuthResponse(request("/api/wallet/verify", item.proof), env)).status, 401);
  const invalid = {...item.proof, signature: Buffer.alloc(64).toString("base64url")};
  assert.equal((await walletAuthResponse(request("/api/wallet/verify", invalid, item.cookie), env)).status, 401);
  assert.equal((await walletAuthResponse(request("/api/wallet/verify", {...item.proof, address: (await identity()).address}, item.cookie), env)).status, 401);
  sqlite.exec("UPDATE wallet_auth_challenges SET expires_at = 1");
  assert.equal((await walletAuthResponse(request("/api/wallet/verify", item.proof, item.cookie), env)).status, 401);
});

test("new challenge invalidates previous challenge for the same browser", async t => {
  const {env} = setup(t), user = await identity(), first = await challenge(env, user);
  const second = await challenge(env, user, first.cookie);
  assert.equal((await walletAuthResponse(request("/api/wallet/verify", first.proof, first.cookie), env)).status, 401);
  assert.equal((await walletAuthResponse(request("/api/wallet/verify", second.proof, second.cookie), env)).status, 200);
});

test("cross-origin, oversized body, malformed address and unavailable storage fail closed", async t => {
  const {env} = setup(t), body = {address: (await identity()).address};
  assert.equal((await walletAuthResponse(request("/api/wallet/challenge", body, "", {Origin: "https://evil.test"}), env)).status, 403);
  const missingOrigin = request("/api/wallet/challenge", body); missingOrigin.headers.delete("Origin");
  assert.equal((await walletAuthResponse(missingOrigin, env)).status, 403);
  assert.equal((await walletAuthResponse(request("/api/wallet/challenge", {...body, padding: "x".repeat(5000)}), env)).status, 400);
  assert.equal((await walletAuthResponse(request("/api/wallet/challenge", {address: "garbage"}), env)).status, 400);
  assert.equal((await walletAuthResponse(request("/api/wallet/challenge", body), {})).status, 503);
  assert.equal((await walletAuthResponse(new Request(`${origin}/api/wallet/challenge`), env)).status, 405);
});

test("authentication requests have a shared server-enforced rate limit", async t => {
  const {env} = setup(t), body = {address: (await identity()).address};
  for(let i=0;i<24;i++) assert.equal((await walletAuthResponse(request("/api/wallet/challenge", body), env)).status, 200);
  const response = await walletAuthResponse(request("/api/wallet/challenge", body), env);
  assert.equal(response.status,429); assert.equal(response.headers.get("Retry-After"), "60");
});

test("built worker accepts wallet read access but blocks product writes and revokes logout", async t => {
  const {env} = setup(t), item = await challenge(env, await identity());
  const app = (await import("../dist/server/index.js")).default;
  const ctx = {waitUntil(){}, passThroughOnException(){}};
  const verified = await app.fetch(request("/api/wallet/verify", item.proof, item.cookie), env, ctx);
  assert.equal(verified.status,200);
  const cookie = verified.headers.getSetCookie().find(x => x.startsWith("__Host-orakt_wallet=")).split(";")[0];
  const headers = {cookie};
  const status = await app.fetch(new Request(`${origin}/api/access/session`, {headers}), env, ctx);
  assert.equal((await status.json()).provider, "phantom");
  assert.equal((await app.fetch(new Request(`${origin}/api/research-report-index`, {headers}), env, ctx)).status,200);
  for(const path of ["/api/research/generate", "/platform/research"]) assert.equal((await app.fetch(new Request(`${origin}${path}`, {method:"POST", headers}), env, ctx)).status,405);
  const logout = await app.fetch(new Request(`${origin}/api/access/session`, {method:"DELETE", headers:{...headers, Origin:origin}}), env, ctx);
  assert.equal(logout.status,200); assert.equal(logout.headers.getSetCookie().length,7);
  assert.equal(await readWalletSession(new Request(`${origin}/`, {headers}),secret,env.DB),null);
});
