import {scrypt, timingSafeEqual, createHmac, createHash, randomBytes, randomUUID} from "node:crypto";
import {Buffer} from "node:buffer";

const SESSION="__Host-orakt_local", CONTEXT="__Host-orakt_local_pending", TTL=43200;
const params={N:32768,r:8,p:3,maxmem:64*1024*1024};
const random=()=>randomBytes(32).toString("hex");
const hash=v=>createHash("sha256").update(v).digest("hex");
const valid=v=>typeof v==="string" && /^[a-f0-9]{64}$/.test(v);
const cookie=(name,value,age)=>`${name}=${value}; Path=/; Max-Age=${age}; HttpOnly; Secure; SameSite=Lax`;
const readCookie=(r,name)=>(r.headers.get("Cookie")??"").split(";").map(v=>v.trim()).find(v=>v.startsWith(`${name}=`))?.slice(name.length+1);
const json=(body,status=200,headers={})=>Response.json(body,{status,headers:{"Cache-Control":"private, no-store",...headers}});
const ready=env=>Boolean(env.DB && env.LOCAL_AUTH_PEPPER && env.LOCAL_AUTH_ENABLED==="true");
const pepper=(value,env)=>createHmac("sha256",env.LOCAL_AUTH_PEPPER).update(value).digest();
export const passwordKey=(password,salt,env)=>new Promise((resolve,reject)=>scrypt(pepper(password,env),Buffer.from(salt,"hex"),32,params,(error,key)=>error?reject(error):resolve(key.toString("hex"))));
const usernameOf=value=>typeof value==="string" ? value.trim().toLowerCase() : "";
const validUsername=value=>/^[a-z0-9][a-z0-9_-]{3,31}$/.test(value);
const validPassword=value=>typeof value==="string" && [...value].length>=15 && [...value].length<=128 && Buffer.byteLength(value,"utf8")<=512;
const recoveryDigest=(value,env)=>pepper(`recovery:${value}`,env).toString("hex");

export async function readLocalSession(request,env,strict=false){
  const token=readCookie(request,SESSION);if(!valid(token))return null;
  try{
    if(!ready(env))return null;
    return await env.DB.prepare("SELECT s.id, s.browser, s.expires_at AS expiresAt, a.id AS accountId, a.username, a.created_at AS createdAt FROM local_auth_sessions s JOIN local_auth_accounts a ON a.id = s.account_id AND a.auth_version = s.auth_version WHERE s.id = ? AND s.origin = ? AND s.expires_at > ?").bind(hash(token),new URL(request.url).origin,Date.now()).first();
  }catch(error){if(strict)throw error;return null;}
}
export async function revokeLocalSession(request,env){
  const token=readCookie(request,SESSION),pending=readCookie(request,CONTEXT);
  if(!valid(token)&&!valid(pending))return;
  if(!env.DB)throw new Error("storage_unavailable");
  const session=await readLocalSession(request,env,true),browser=valid(pending)?pending:"";
  await env.DB.batch([
    env.DB.prepare("DELETE FROM local_auth_challenges WHERE browser IN (?, ?)").bind(browser,session?.browser??""),
    env.DB.prepare("DELETE FROM local_auth_sessions WHERE browser IN (?, ?) OR id = ?").bind(browser,session?.browser??"",valid(token)?hash(token):""),
  ]);
}
export function clearLocalCookies(headers){for(const name of [SESSION,CONTEXT])headers.append("Set-Cookie",cookie(name,"",0));}
async function smallJson(request){
  if(!request.headers.get("Content-Type")?.startsWith("application/json"))throw new Error("invalid_request");
  const reader=request.body?.getReader();if(!reader)throw new Error("invalid_request");
  let bytes=0,text="";const decoder=new TextDecoder();
  while(true){const {done,value}=await reader.read();if(done)break;bytes+=value.length;if(bytes>4096){await reader.cancel();throw new Error("invalid_request");}text+=decoder.decode(value,{stream:true});}
  const body=JSON.parse(text+decoder.decode());if(!body||Array.isArray(body)||typeof body!=="object")throw new Error("invalid_request");return body;
}
async function permit(env,key,max,seconds,now){
  const bucket=pepper(`limit:${key}:${Math.floor(now/(seconds*1000))}`,env).toString("hex");
  return Boolean(await env.DB.prepare("INSERT INTO wallet_auth_limits (bucket, count, expires_at) VALUES (?, 1, ?) ON CONFLICT(bucket) DO UPDATE SET count = count + 1 WHERE count < ? RETURNING count").bind(bucket,now+seconds*2000,max).first());
}

export async function localAuthResponse(request,env){
  const url=new URL(request.url),action=url.pathname.split("/").at(-1);
  if(action==="config"&&request.method==="GET")return json({enabled:ready(env),methods:["username_password"],recovery:"saved_recovery_key",emailVerification:false});
  if(request.method!=="POST")return json({error:"method_not_allowed"},405);
  if(request.headers.get("Origin")!==url.origin||request.headers.get("X-ORAKT-Auth")!=="local")return json({error:"cross_origin_request"},403);
  if(!ready(env))return json({error:"local_login_unavailable"},503);
  let body;try{body=await smallJson(request);}catch{return json({error:"invalid_request"},400);}
  try{
    const now=Date.now(),ip=request.headers.get("CF-Connecting-IP")??"unknown";
    if(!await permit(env,`local-ip:${ip}`,60,900,now))return json({error:"rate_limited"},429,{"Retry-After":"900"});
    if(action==="challenge"){
      if(!["register","login","recover"].includes(body.action))return json({error:"invalid_request"},400);
      const old=readCookie(request,CONTEXT),browser=valid(old)?old:random(),nonce=random(),csrf=random();
      await env.DB.batch([
        env.DB.prepare("DELETE FROM local_auth_challenges WHERE browser = ? OR expires_at <= ?").bind(browser,now),
        env.DB.prepare("DELETE FROM local_auth_sessions WHERE expires_at <= ?").bind(now),
        env.DB.prepare("DELETE FROM wallet_auth_limits WHERE expires_at <= ?").bind(now),
        env.DB.prepare("INSERT INTO local_auth_challenges (nonce, csrf, browser, origin, action, expires_at) VALUES (?, ?, ?, ?, ?, ?)").bind(nonce,csrf,browser,url.origin,body.action,now+300000),
      ]);
      return json({nonce,csrf},200,{"Set-Cookie":cookie(CONTEXT,browser,TTL)});
    }
    const username=usernameOf(body.username);
    if(!["register","login","recover"].includes(action)||!validUsername(username)||!validPassword(body.password)||!valid(body.nonce)||!valid(body.csrf))return json({error:"invalid_request"},400);
    const browser=readCookie(request,CONTEXT)??"";
    const proof=[body.nonce,body.csrf,browser,url.origin,action];
    const predicate="nonce = ? AND csrf = ? AND browser = ? AND origin = ? AND action = ? AND expires_at > ?";
    if(!await env.DB.prepare(`SELECT nonce FROM local_auth_challenges WHERE ${predicate}`).bind(...proof,now).first())return json({error:"challenge_expired_or_used"},401);
    if(!await permit(env,`local-user:${username}`,8,900,now)||!await permit(env,`local-kdf:${ip}`,20,900,now)||(action==="register"&&!await permit(env,`local-register:${ip}`,5,3600,now)))return json({error:"rate_limited"},429,{"Retry-After":"900"});
    const consume=()=>env.DB.prepare("DELETE FROM local_auth_challenges WHERE nonce = ? AND browser = ?").bind(body.nonce,browser);
    const account=await env.DB.prepare("SELECT id, username, salt, password_hash, auth_version, recovery_hash, kdf FROM local_auth_accounts WHERE username = ?").bind(username).first();
    if(account&&account.kdf!=="scrypt-v1")return json({error:"local_login_unavailable"},503);
    if(action==="login"){
      const calculated=await passwordKey(body.password,account?.salt??"00".repeat(16),env);
      const expected=account?.password_hash??"00".repeat(32);
      if(!timingSafeEqual(Buffer.from(calculated,"hex"),Buffer.from(expected,"hex"))||!account){await consume().run();return json({error:"invalid_credentials"},401);}
      const token=random(),id=hash(token),expiresAt=Date.now()+TTL*1000;
      const result=await env.DB.batch([
        env.DB.prepare(`INSERT INTO local_auth_sessions (id, browser, account_id, auth_version, origin, expires_at) SELECT ?, c.browser, a.id, a.auth_version, c.origin, ? FROM local_auth_accounts a JOIN local_auth_challenges c ON 1 = 1 WHERE a.id = ? AND a.auth_version = ? AND c.${predicate} `).bind(id,expiresAt,account.id,account.auth_version,...proof,Date.now()),
        consume(),
      ]);
      if(result[0].meta.changes!==1)return json({error:"challenge_expired_or_used"},401);
      const headers=new Headers({"Cache-Control":"private, no-store"});headers.append("Set-Cookie",cookie(SESSION,token,TTL));headers.append("Set-Cookie",cookie(CONTEXT,browser,TTL));
      return Response.json({ok:true,scope:"published_read_only"},{headers});
    }
    if(action==="recover"&&(!valid(body.recoveryKey)||!account||!timingSafeEqual(Buffer.from(recoveryDigest(body.recoveryKey,env),"hex"),Buffer.from(account.recovery_hash,"hex")))){
      await consume().run();return json({error:"invalid_recovery"},401);
    }
    const salt=randomBytes(16).toString("hex"),passwordHash=await passwordKey(body.password,salt,env),recoveryKey=random(),authVersion=random();
    const operation=action==="register"
      ? env.DB.prepare(`INSERT INTO local_auth_accounts (id, username, salt, password_hash, kdf, recovery_hash, auth_version, created_at) SELECT ?, ?, ?, ?, 'scrypt-v1', ?, ?, ? FROM local_auth_challenges WHERE ${predicate} ON CONFLICT(username) DO NOTHING`).bind(random(),username,salt,passwordHash,recoveryDigest(recoveryKey,env),authVersion,now,...proof,Date.now())
      : env.DB.prepare(`UPDATE local_auth_accounts SET salt = ?, password_hash = ?, recovery_hash = ?, auth_version = ? WHERE id = ? AND recovery_hash = ? AND EXISTS (SELECT 1 FROM local_auth_challenges WHERE ${predicate})`).bind(salt,passwordHash,recoveryDigest(recoveryKey,env),authVersion,account.id,recoveryDigest(body.recoveryKey,env),...proof,Date.now());
    const directory=env.DB.prepare("INSERT INTO member_accounts (id, provider, subject, display_name, legacy_ref, created_at, first_seen_at) SELECT ?, 'local', id, username, substr(id,1,16), created_at, ? FROM local_auth_accounts WHERE auth_version = ? ON CONFLICT(provider, subject) DO NOTHING").bind(randomUUID(),now,authVersion);
    const result=await env.DB.batch([operation,directory,consume(),env.DB.prepare("DELETE FROM local_auth_sessions WHERE account_id IN (SELECT id FROM local_auth_accounts WHERE auth_version = ?)").bind(authVersion)]);
    if(result[0].meta.changes!==1)return json({error:action==="register"?"registration_unavailable":"invalid_recovery"},409);
    // Recovery key is shown once, never persisted in the browser or included in URLs.
    return json({ok:true,username,recoveryKey,requiresLogin:true},action==="register"?201:200);
  }catch{return json({error:"local_login_unavailable"},503);}
}
