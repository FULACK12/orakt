// Identity only: this module never requests a transaction, RPC or token approval.
const SESSION = "__Host-orakt_wallet";
const BROWSER = "__Host-orakt_wallet_challenge";
const TTL = 12 * 60 * 60;
const alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
const enc = new TextEncoder();
const cookie = (name, value, seconds) => `${name}=${value}; Path=/; Max-Age=${seconds}; HttpOnly; Secure; SameSite=Lax`;
const readCookie = (r, name) => (r.headers.get("Cookie") ?? "").split(";").map(v => v.trim()).find(v => v.startsWith(`${name}=`))?.slice(name.length + 1);
const base64 = bytes => btoa(String.fromCharCode(...bytes)).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
const unbase64 = s => Uint8Array.from(atob(s.replaceAll("-", "+").replaceAll("_", "/")), c => c.charCodeAt(0));
const random = () => base64(crypto.getRandomValues(new Uint8Array(32)));
const randomHex = () => [...crypto.getRandomValues(new Uint8Array(32))].map(v => v.toString(16).padStart(2, "0")).join("");
const json = (body, status = 200, headers = {}) => Response.json(body, {status, headers: {"Cache-Control": "private, no-store", ...headers}});

export function decodeAddress(value) {
  if (typeof value !== "string" || !/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(value)) throw new Error("invalid_address");
  let number = 0n;
  for (const c of value) number = number * 58n + BigInt(alphabet.indexOf(c));
  const bytes = [];
  while (number) { bytes.unshift(Number(number & 255n)); number >>= 8n; }
  for (const c of value) { if (c !== "1") break; bytes.unshift(0); }
  if (bytes.length !== 32) throw new Error("invalid_address");
  return new Uint8Array(bytes);
}

async function key(secret, usage) {
  return crypto.subtle.importKey("raw", enc.encode(secret), {name: "HMAC", hash: "SHA-256"}, false, [usage]);
}
async function sign(value, secret) {
  return base64(new Uint8Array(await crypto.subtle.sign("HMAC", await key(secret, "sign"), enc.encode(value))));
}

export async function readWalletSession(request, secret, db, requireStorage = false) {
  if (!secret || !db) return null;
  let checkingStorage = false;
  try {
    const token = readCookie(request, SESSION);
    if (!token || token.length > 1500) return null;
    const [payload, signature, extra] = token.split(".");
    if (extra || !signature || !await crypto.subtle.verify("HMAC", await key(secret, "verify"), unbase64(signature), enc.encode(payload))) return null;
    const session = JSON.parse(new TextDecoder().decode(unbase64(payload)));
    if (session.version !== 1 || session.scope !== "published_read_only" || session.origin !== new URL(request.url).origin || !Number.isSafeInteger(session.expiresAt) || session.expiresAt <= Date.now() || session.expiresAt > Date.now() + (TTL + 60) * 1000) return null;
    decodeAddress(session.address);
    if (typeof session.id !== "string" || !/^[a-f0-9]{64}$/.test(session.id)) return null;
    checkingStorage = true;
    if (!await db.prepare("SELECT id FROM wallet_auth_sessions WHERE id = ? AND expires_at > ?").bind(session.id, Date.now()).first()) return null;
    return session;
  } catch (error) { if (checkingStorage && requireStorage) throw error; return null; }
}

export async function revokeWalletSession(request, env) {
  const session = await readWalletSession(request, env.PILOT_SESSION_SECRET, env.DB, true);
  const pending = readCookie(request, BROWSER) ?? "";
  const browser = /^[A-Za-z0-9_-]{43}$/.test(pending) ? pending : "";
  if (env.DB && (session || browser)) await env.DB.batch([
    env.DB.prepare("DELETE FROM wallet_auth_challenges WHERE browser IN (?, ?)").bind(browser, session?.browser ?? ""),
    env.DB.prepare("DELETE FROM wallet_auth_sessions WHERE browser IN (?, ?) OR id = ?").bind(browser, session?.browser ?? "", session?.id ?? ""),
  ]);
}

export function clearWalletCookies(headers) {
  headers.append("Set-Cookie", cookie(SESSION, "", 0));
  headers.append("Set-Cookie", cookie(BROWSER, "", 0));
}

async function smallJson(request) {
  if (!request.headers.get("Content-Type")?.startsWith("application/json")) throw new Error("invalid_request");
  const reader = request.body?.getReader();
  if (!reader) throw new Error("invalid_request");
  let text = "", size = 0;
  const decoder = new TextDecoder();
  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    size += value.length;
    if (size > 4096) { await reader.cancel(); throw new Error("request_too_large"); }
    text += decoder.decode(value, {stream: true});
  }
  return JSON.parse(text + decoder.decode());
}

export async function walletAuthResponse(request, env) {
  const url = new URL(request.url);
  if (request.method !== "POST") return json({error: "method_not_allowed"}, 405);
  if (request.headers.get("Origin") !== url.origin) return json({error: "cross_origin_request"}, 403);
  if (!env.DB || !env.PILOT_SESSION_SECRET) return json({error: "wallet_service_unavailable"}, 503);
  let body;
  try { body = await smallJson(request); } catch { return json({error: "invalid_request"}, 400); }
  try {
    const addressBytes = decodeAddress(body?.address);
    const now = Date.now();
    // Hash network identifiers with a server secret; retain only a short-lived bucket.
    const bucket = await sign(`wallet-rate:${request.headers.get("CF-Connecting-IP") ?? "local"}:${Math.floor(now / 60000)}`, env.PILOT_SESSION_SECRET);
    const permitted = await env.DB.prepare("INSERT INTO wallet_auth_limits (bucket, count, expires_at) VALUES (?, 1, ?) ON CONFLICT(bucket) DO UPDATE SET count = count + 1 WHERE count < 24 RETURNING count").bind(bucket, now + 120000).first();
    if (!permitted) return json({error: "rate_limited"}, 429, {"Retry-After": "60"});

    if (url.pathname === "/api/wallet/challenge") {
      const previous = readCookie(request, BROWSER);
      const browser = previous && /^[A-Za-z0-9_-]{43}$/.test(previous) ? previous : random();
      const nonce = randomHex();
      const expiresAt = now + 5 * 60000;
      const message = `${url.host} wants you to sign in with your Solana account:\n${body.address}\n\nSign in to ORAKT read-only research. No transaction or spending approval.\n\nURI: ${url.origin}/access\nVersion: 1\nChain ID: solana:mainnet\nNonce: ${nonce}\nIssued At: ${new Date(now).toISOString()}\nExpiration Time: ${new Date(expiresAt).toISOString()}`;
      await env.DB.batch([
        env.DB.prepare("DELETE FROM wallet_auth_challenges WHERE expires_at <= ? OR browser = ?").bind(now, browser),
        env.DB.prepare("DELETE FROM wallet_auth_limits WHERE expires_at <= ?").bind(now),
        env.DB.prepare("DELETE FROM wallet_auth_sessions WHERE expires_at <= ?").bind(now),
        env.DB.prepare("INSERT INTO wallet_auth_challenges (nonce, browser, address, origin, message, expires_at) VALUES (?, ?, ?, ?, ?, ?)").bind(nonce, browser, body.address, url.origin, message, expiresAt),
      ]);
      return json({nonce, address: body.address, origin: url.origin, message, expiresAt}, 200, {"Set-Cookie": cookie(BROWSER, browser, 300)});
    }

    if (url.pathname !== "/api/wallet/verify" || typeof body.nonce !== "string" || !/^[a-f0-9]{64}$/.test(body.nonce) || typeof body.signature !== "string" || !/^[A-Za-z0-9_-]{86}$/.test(body.signature)) return json({error: "invalid_request"}, 400);
    const browser = readCookie(request, BROWSER) ?? "";
    const challenge = await env.DB.prepare("SELECT * FROM wallet_auth_challenges WHERE nonce = ? AND browser = ? AND address = ? AND origin = ? AND expires_at > ?").bind(body.nonce, browser, body.address, url.origin, now).first();
    if (!challenge) return json({error: "challenge_expired_or_used"}, 401);
    const publicKey = await crypto.subtle.importKey("raw", addressBytes, {name: "Ed25519"}, false, ["verify"]);
    const valid = await crypto.subtle.verify("Ed25519", publicKey, unbase64(body.signature), enc.encode(challenge.message));
    if (!valid) return json({error: "invalid_signature"}, 401);
    const old = await readWalletSession(request, env.PILOT_SESSION_SECRET, env.DB, true);
    if (old) await env.DB.prepare("DELETE FROM wallet_auth_sessions WHERE id = ?").bind(old.id).run();
    const session = {version: 1, id: randomHex(), browser, address: body.address, origin: url.origin, expiresAt: now + TTL * 1000, scope: "published_read_only"};
    // One transaction: logout can cancel the challenge before insertion or
    // revoke the inserted session afterwards, never resurrect an exited session.
    const results = await env.DB.batch([
      env.DB.prepare("INSERT INTO wallet_auth_sessions (id, browser, expires_at) SELECT ?, browser, ? FROM wallet_auth_challenges WHERE nonce = ? AND browser = ? AND address = ? AND origin = ? AND expires_at > ?").bind(session.id, session.expiresAt, body.nonce, browser, body.address, url.origin, Date.now()),
      env.DB.prepare("DELETE FROM wallet_auth_challenges WHERE nonce = ? AND browser = ?").bind(body.nonce, browser),
    ]);
    if (results[0].meta.changes !== 1) return json({error: "challenge_expired_or_used"}, 401);
    const payload = base64(enc.encode(JSON.stringify(session)));
    const headers = new Headers();
    headers.append("Set-Cookie", cookie(SESSION, `${payload}.${await sign(payload, env.PILOT_SESSION_SECRET)}`, TTL));
    headers.append("Set-Cookie", cookie(BROWSER, "", 0));
    headers.set("Cache-Control", "private, no-store");
    return Response.json({ok: true, address: session.address, expiresAt: new Date(session.expiresAt).toISOString(), scope: session.scope}, {headers});
  } catch (error) {
    return json({error: error?.message === "invalid_address" ? "invalid_address" : "wallet_service_unavailable"}, error?.message === "invalid_address" ? 400 : 503);
  }
}
