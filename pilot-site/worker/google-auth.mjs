import {createRemoteJWKSet, jwtVerify} from "jose";

const keys = createRemoteJWKSet(new URL("https://www.googleapis.com/oauth2/v3/certs"), {timeoutDuration:5000, cooldownDuration:30000, cacheMaxAge:300000});
const SESSION = "__Host-orakt_google", PENDING = "__Host-orakt_google_pending";
const TTL = 12 * 3600;
const enc = new TextEncoder();
const random = () => [...crypto.getRandomValues(new Uint8Array(32))].map(v=>v.toString(16).padStart(2,"0")).join("");
const validId = value => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
const readCookie = (r,name) => (r.headers.get("Cookie")??"").split(";").map(v=>v.trim()).find(v=>v.startsWith(`${name}=`))?.slice(name.length+1);
const cookie = (name,value,seconds) => `${name}=${value}; Path=/; Max-Age=${seconds}; HttpOnly; Secure; SameSite=Lax`;
const json = (body,status=200,headers={}) => Response.json(body,{status,headers:{"Cache-Control":"private, no-store",...headers}});
const hash = async value => [...new Uint8Array(await crypto.subtle.digest("SHA-256",enc.encode(value)))].map(v=>v.toString(16).padStart(2,"0")).join("");

export function googleConfig(request,env) {
  const configured = Boolean(env.GOOGLE_CLIENT_ID && env.GOOGLE_AUTH_ORIGIN && env.PILOT_SESSION_SECRET && env.DB);
  const enabled = configured && new URL(request.url).origin === env.GOOGLE_AUTH_ORIGIN;
  return {enabled, clientId:enabled ? env.GOOGLE_CLIENT_ID : null, canonicalUrl:configured ? `${env.GOOGLE_AUTH_ORIGIN}/access/google` : null};
}

export async function verifyGoogleCredential(credential,clientId,nonce,keyResolver=keys) {
  const {payload} = await jwtVerify(credential,keyResolver,{
    algorithms:["RS256"], issuer:["https://accounts.google.com","accounts.google.com"], audience:clientId,
    requiredClaims:["sub","iat","exp","nonce"], maxTokenAge:"1h", clockTolerance:30,
  });
  if (payload.nonce !== nonce || typeof payload.sub !== "string" || !payload.sub || payload.sub.length>255 || (payload.azp && payload.azp !== clientId)) throw new Error("invalid_google_token");
  // Identity is provider + sub; never merge identities merely because emails match.
  return {subject:payload.sub};
}

export async function readGoogleSession(request,env,requireStorage=false) {
  const token=readCookie(request,SESSION);
  if (!validId(token)) return null;
  if (!env.DB) {if(requireStorage)throw new Error("storage_unavailable");return null;}
  try {
    return await env.DB.prepare("SELECT id, browser, subject, expires_at AS expiresAt FROM google_auth_sessions WHERE id = ? AND origin = ? AND expires_at > ?").bind(await hash(token),new URL(request.url).origin,Date.now()).first();
  } catch(error) {if(requireStorage)throw error;return null;}
}

export async function revokeGoogleSession(request,env) {
  const session=await readGoogleSession(request,env,true);
  const pending=readCookie(request,PENDING);
  const browser=validId(pending)?pending:"";
  if (!session && !browser) return;
  if(!env.DB)throw new Error("storage_unavailable");
  await env.DB.batch([
    env.DB.prepare("DELETE FROM google_auth_challenges WHERE browser IN (?, ?)").bind(browser,session?.browser??""),
    env.DB.prepare("DELETE FROM google_auth_sessions WHERE browser IN (?, ?) OR id = ?").bind(browser,session?.browser??"",session?.id??""),
  ]);
}
export function clearGoogleCookies(headers) {
  headers.append("Set-Cookie",cookie(SESSION,"",0));headers.append("Set-Cookie",cookie(PENDING,"",0));
}

async function smallJson(request) {
  if(!request.headers.get("Content-Type")?.startsWith("application/json"))throw new Error("invalid_request");
  const reader=request.body?.getReader();if(!reader)throw new Error("invalid_request");
  let size=0,text="";const decoder=new TextDecoder();
  while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>16384){await reader.cancel();throw new Error("invalid_request");}text+=decoder.decode(value,{stream:true});}
  return JSON.parse(text+decoder.decode());
}

// The key resolver argument is a code-level test seam, never an HTTP/env option.
export async function googleAuthResponse(request,env,keyResolver=keys) {
  const url=new URL(request.url);
  if(url.pathname==="/api/auth/google/config" && request.method==="GET")return json(googleConfig(request,env));
  if(request.method!=="POST")return json({error:"method_not_allowed"},405);
  if(request.headers.get("Origin")!==url.origin || request.headers.get("X-ORAKT-Auth")!=="google")return json({error:"cross_origin_request"},403);
  if(!googleConfig(request,env).enabled)return json({error:"google_login_unavailable"},503);
  let body;try{body=await smallJson(request);}catch{return json({error:"invalid_request"},400);}
  try {
    const now=Date.now();
    const bucket=await hash(`${env.PILOT_SESSION_SECRET}:google-rate:${request.headers.get("CF-Connecting-IP")??"local"}:${Math.floor(now/60000)}`);
    const permitted=await env.DB.prepare("INSERT INTO wallet_auth_limits (bucket, count, expires_at) VALUES (?, 1, ?) ON CONFLICT(bucket) DO UPDATE SET count = count + 1 WHERE count < 24 RETURNING count").bind(bucket,now+120000).first();
    if(!permitted)return json({error:"rate_limited"},429,{"Retry-After":"60"});
    if(url.pathname==="/api/auth/google/challenge"){
      const previous=readCookie(request,PENDING),browser=validId(previous)?previous:random();
      const nonce=random(),csrf=random(),expiresAt=now+300000;
      await env.DB.batch([
        env.DB.prepare("DELETE FROM google_auth_challenges WHERE browser = ? OR expires_at <= ?").bind(browser,now),
        env.DB.prepare("DELETE FROM google_auth_sessions WHERE expires_at <= ?").bind(now),
        env.DB.prepare("DELETE FROM wallet_auth_limits WHERE expires_at <= ?").bind(now),
        env.DB.prepare("INSERT INTO google_auth_challenges (nonce, csrf, browser, origin, expires_at) VALUES (?, ?, ?, ?, ?)").bind(nonce,csrf,browser,url.origin,expiresAt),
      ]);
      return json({nonce,csrf,expiresAt},200,{"Set-Cookie":cookie(PENDING,browser,TTL)});
    }
    if(url.pathname!=="/api/auth/google/verify" || !validId(body?.nonce) || !validId(body?.csrf) || typeof body?.credential!=="string" || body.credential.length>12000)return json({error:"invalid_request"},400);
    const browser=readCookie(request,PENDING)??"";
    const challenge=await env.DB.prepare("SELECT nonce FROM google_auth_challenges WHERE nonce = ? AND csrf = ? AND browser = ? AND origin = ? AND expires_at > ?").bind(body.nonce,body.csrf,browser,url.origin,now).first();
    if(!challenge)return json({error:"challenge_expired_or_used"},401);
    let identity;
    try {identity=await verifyGoogleCredential(body.credential,env.GOOGLE_CLIENT_ID,challenge.nonce,keyResolver);}
    catch(error){return json({error:error?.code==="ERR_JWKS_TIMEOUT"?"google_verification_unavailable":"invalid_google_token"},error?.code==="ERR_JWKS_TIMEOUT"?503:401);}
    const old=await readGoogleSession(request,env,true);
    const token=random(),id=await hash(token),expiresAt=now+TTL*1000;
    const results=await env.DB.batch([
      env.DB.prepare("INSERT INTO google_auth_sessions (id, browser, subject, origin, expires_at) SELECT ?, browser, ?, origin, ? FROM google_auth_challenges WHERE nonce = ? AND csrf = ? AND browser = ? AND origin = ? AND expires_at > ?").bind(id,identity.subject,expiresAt,body.nonce,body.csrf,browser,url.origin,Date.now()),
      env.DB.prepare("DELETE FROM google_auth_challenges WHERE nonce = ? AND browser = ?").bind(body.nonce,browser),
      env.DB.prepare("DELETE FROM google_auth_sessions WHERE id = ?").bind(old?.id??""),
    ]);
    if(results[0].meta.changes!==1)return json({error:"challenge_expired_or_used"},401);
    const headers=new Headers({"Cache-Control":"private, no-store"});
    headers.append("Set-Cookie",cookie(SESSION,token,TTL));headers.append("Set-Cookie",cookie(PENDING,browser,TTL));
    return Response.json({ok:true,scope:"published_read_only",expiresAt:new Date(expiresAt).toISOString()},{headers});
  } catch {return json({error:"google_login_unavailable"},503);}
}
