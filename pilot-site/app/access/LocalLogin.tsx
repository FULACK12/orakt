"use client";
import {useEffect,useRef,useState,type FormEvent} from "react";
import styles from "./access.module.css";
import {accessHref} from "./access-navigation.mjs";
import {authJsonGet,withAuthLock} from "./auth-request.mjs";
type Mode="login"|"register"|"recover";
export default function LocalLogin({returnTo,initialMode="login"}:{returnTo:string;initialMode?:Mode}){
  const mode=initialMode;
  const [username,setUsername]=useState(""),[password,setPassword]=useState(""),[confirm,setConfirm]=useState(""),[key,setKey]=useState("");
  const [busy,setBusy]=useState(false),[error,setError]=useState(""),[recovery,setRecovery]=useState(""),[saved,setSaved]=useState(false),[enabled,setEnabled]=useState<boolean|null>(null);
  const [configError,setConfigError]=useState(""),[retry,setRetry]=useState(0),[phase,setPhase]=useState("");
  const lifetime=useRef<AbortController|null>(null),submitting=useRef(false);
  useEffect(()=>{const c=new AbortController();lifetime.current=c;return()=>c.abort();},[]);
  useEffect(()=>{
    const c=new AbortController();setEnabled(null);setConfigError("");
    authJsonGet("/api/auth/local/config",{signal:c.signal}).then(d=>{
      if(c.signal.aborted)return;
      setEnabled(Boolean(d.enabled&&navigator.locks));
      if(!d.enabled)setConfigError("自主账号服务暂不可用，请稍后重试或选择其他登录方式。");
      else if(!navigator.locks)setConfigError("当前浏览器缺少安全登录能力，请更新浏览器或选择其他登录方式。");
    }).catch(e=>{if(!c.signal.aborted){setEnabled(false);setConfigError(e.name==="TimeoutError"?"连接超时，请检查网络后重新加载。":"无法加载账号服务，请检查网络后重试。");}});
    return()=>c.abort();
  },[retry]);
  async function submit(e:FormEvent){
    e.preventDefault();if(submitting.current||!enabled)return;if(mode!=="login"&&password!==confirm){setError("两次输入的密码不一致。");return;}
    if([...password].length<15){setError("密码至少 15 个字符，可使用易记的长句。");return;}
    submitting.current=true;setBusy(true);setError("");setPhase("正在等待安全通道…");
    const signal=lifetime.current?.signal;
    try{
      const payload=await withAuthLock(navigator.locks,"orakt-local-auth",async()=>{
        setPhase("正在安全验证…");
        const send=(action:string,body:unknown)=>fetch(`/api/auth/local/${action}`,{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json","X-ORAKT-Auth":"local"},body:JSON.stringify(body),signal:AbortSignal.timeout(30000)});
        const challenge=await send("challenge",{action:mode}),proof=await challenge.json();if(!challenge.ok)throw new Error(proof.error);
        setPhase(mode==="register"?"正在创建账号，请勿重复提交…":mode==="recover"?"正在更新密码与恢复码，请勿重复提交…":"正在核对账号…");
        const response=await send(mode,{...proof,username,password,...(mode==="recover"?{recoveryKey:key.trim()}: {})}),data=await response.json();if(!response.ok)throw new Error(data.error);return data;
      },{signal});
      if(signal?.aborted)return;
      setPassword("");setConfirm("");setKey("");
      if(payload.recoveryKey){setRecovery(payload.recoveryKey);setSaved(false);}else window.location.assign(returnTo);
    }catch(e){if(signal?.aborted)return;const message=(e as Error).message;setError(({auth_lock_timeout:"另一个标签页仍在处理账号操作。本次尚未提交，请稍等片刻后重试。",invalid_credentials:"用户名或密码不正确。",registration_unavailable:"该用户名不可注册，请换一个名称或前往登录。",invalid_recovery:"用户名或恢复码不正确，旧恢复码只能使用一次。",rate_limited:"尝试过于频繁，请稍后再试，不要连续刷新。",challenge_expired_or_used:"本次验证已过期，请重新提交。",invalid_request:"请检查用户名、密码长度和恢复码格式。"} as Record<string,string>)[message]??"未能确认操作结果，请勿重复注册或重置。若已提交，可尝试用该密码登录；不要丢弃原恢复码。");}
    finally{submitting.current=false;if(!signal?.aborted){setBusy(false);setPhase("");}}
  }
  function download(){const blob=new Blob([`ORAKT account: ${username.trim().toLowerCase()}\nRecovery key: ${recovery}\nKeep offline. Anyone with this key can reset your password.\n`],{type:"text/plain"}),url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="orakt-recovery-key.txt";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  return <section className={styles.localPanel} aria-label="ORAKT 自主注册账号">
    {recovery?<div className={styles.recoveryPanel}>
      <h4>{mode==="register"?"账号已创建":"密码已重置"} · 保存恢复码</h4>
      <p>仅显示这一次。忘记密码时，用用户名和恢复码重置。请离线保管，不要发送给他人。重置后旧恢复码和所有旧登录会话失效。</p>
      <code>{recovery}</code><button type="button" onClick={download}>下载恢复码</button>
      <label className={styles.checkbox}><input type="checkbox" checked={saved} onChange={e=>setSaved(e.target.checked)}/>我已妥善保存；丢失密码和恢复码将无法找回账号。</label>
      <button type="button" disabled={!saved} onClick={()=>window.location.assign(accessHref("login",returnTo))}>返回登录</button>
    </div>:<>
      <p>{mode==="login"?"使用你注册的用户名与密码。":mode==="register"?"无需第三方账号。注册后请保存恢复码，用于找回密码。":"使用用户名和恢复码重设密码。旧恢复码及旧登录会话将失效。"}</p>
      <form onSubmit={submit}>
        <label htmlFor="local-username">用户名 <small>4–32 位英文字母、数字、下划线或短横线</small></label>
        <input id="local-username" autoComplete="username" autoCapitalize="none" spellCheck={false} pattern={"[a-zA-Z0-9][a-zA-Z0-9_\\-]{3,31}"} minLength={4} maxLength={32} required value={username} onChange={e=>setUsername(e.target.value)} disabled={busy}/>
        {mode==="recover"&&<><label htmlFor="recovery-key">恢复码</label><input id="recovery-key" type="password" autoComplete="off" maxLength={64} minLength={64} required value={key} onChange={e=>setKey(e.target.value)} disabled={busy}/></>}
        <label htmlFor="local-password">{mode==="recover"?"新密码":"密码"} <small>至少 15 个字符，最多 128 个</small></label>
        <input id="local-password" type="password" autoComplete={mode==="login"?"current-password":"new-password"} maxLength={256} required value={password} onChange={e=>setPassword(e.target.value)} disabled={busy}/>
        {mode!=="login"&&<><label htmlFor="confirm-password">再次输入密码</label><input id="confirm-password" type="password" autoComplete="new-password" required value={confirm} onChange={e=>setConfirm(e.target.value)} disabled={busy}/></>}
        {error&&<p role="alert" className={styles.error}>{error}</p>}
        {enabled===null&&<p role="status">正在连接账号服务…</p>}
        {configError&&<><p role="alert" className={styles.error}>{configError}</p><button className={styles.secondaryButton} type="button" disabled={busy} onClick={()=>{setEnabled(null);setConfigError("");setRetry(v=>v+1);}}>重新加载账号服务</button></>}
        {busy&&<p role="status">{phase}</p>}
        <button className={styles.submit} disabled={busy||!enabled} type="submit">{busy?"处理中，请稍候…":mode==="login"?"登录 ORAKT":mode==="register"?"创建账号":"重置密码并更新恢复码"}</button>
        {mode!=="login"&&<small>不收集邮箱，没有邮件找回功能。独立账号不会与 Google、ChatGPT 或 Phantom 自动合并。</small>}
      </form>
      <nav className={styles.localLinks} aria-label="其他账号操作">{(["login","register","recover"] as Mode[]).filter(v=>v!==mode).map(v=><a key={v} href={accessHref(v,returnTo)} aria-disabled={busy||undefined} onClick={e=>{if(busy)e.preventDefault();}}>{v==="login"?"已有账号，去登录":v==="register"?"注册账号":"忘记密码？"}</a>)}</nav>
    </>}
  </section>;
}
