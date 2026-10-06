"use client";
import {useEffect,useState} from "react";
import {ArrowLeft,ChevronRight,MessageCircle,ShieldCheck,UserRound,Wallet} from "lucide-react";
import OraktBrandIcon from "../OraktBrandIcon";
import GoogleLogin from "./GoogleLogin";
import WalletLogin from "./WalletLogin";
import LocalLogin from "./LocalLogin";
import ReleaseStatus from "../ReleaseStatus";
import {accessHref} from "./access-navigation.mjs";
import {authJsonGet} from "./auth-request.mjs";
import styles from "./access.module.css";

export type AccessMethod = "chatgpt" | "google" | "phantom" | "login" | "register" | "recover";
const titles:Record<AccessMethod,string> = {chatgpt:"使用 ChatGPT 登录",google:"使用 Google 登录",phantom:"使用 Phantom 登录",login:"登录 ORAKT 账号",register:"创建 ORAKT 账号",recover:"找回 ORAKT 密码"};
const choices = [
  {method:"google",label:"Google",description:"使用 Google 账户",icon:null},
  {method:"chatgpt",label:"ChatGPT",description:"使用 ChatGPT 身份",icon:MessageCircle},
  {method:"phantom",label:"Phantom",description:"使用 Solana 钱包",icon:Wallet},
  {method:"login",label:"ORAKT 账号",description:"使用用户名与密码",icon:UserRound},
] as const;

export default function AccessPortal({chatHref,returnTo,method}:{chatHref:string;returnTo:string;method?:AccessMethod}) {
  const [authorized,setAuthorized]=useState(false),[error,setError]=useState(""),[loggingOut,setLoggingOut]=useState(false);
  const [sessionState,setSessionState]=useState<"checking"|"ready"|"failed">("checking"),[sessionRetry,setSessionRetry]=useState(0);
  useEffect(()=>{
    const controller=new AbortController();
    setSessionState("checking");
    authJsonGet("/api/access/session",{signal:controller.signal,timeoutMs:8000})
      .then(d=>{if(!controller.signal.aborted){setAuthorized(Boolean(d?.authorized));setSessionState("ready");}})
      .catch(()=>{if(!controller.signal.aborted)setSessionState("failed");});
    return()=>controller.abort();
  },[sessionRetry]);
  async function logout(){
    if(loggingOut)return;
    setLoggingOut(true);setError("");
    try{
      const r=await fetch("/api/access/session",{method:"DELETE",credentials:"same-origin",signal:AbortSignal.timeout(15000)});
      if(!r.ok)throw Error();
      const result=await r.json();location.assign(result.signOutHref||"/access");
    }catch{setError("退出未完成，请检查网络后重试。");setLoggingOut(false);}
  }
  return <main className={styles.page}>
    <header className={styles.header}>
      <a href="/" aria-label="ORAKT 官网" className={styles.logo}><OraktBrandIcon/><strong>ORAKT</strong></a>
      <a href="/" className={styles.homeReturn}><ArrowLeft size={16} aria-hidden="true"/>返回官网</a>
    </header>
    <div className={styles.authShell}>
      {method&&<a className={styles.backLink} href={accessHref("",returnTo)}><ArrowLeft size={16} aria-hidden="true"/>其他登录方式</a>}
      <section className={styles.accessCard} aria-labelledby="access-heading" data-access-method={method||"choose"}>
        <div className={styles.authIntro}>
          <span>ORAKT / ACCOUNT ACCESS</span>
          <h1 id="access-heading">{authorized?"你已登录":method?titles[method]:"登录 ORAKT"}</h1>
          {!method&&!authorized&&<p>选择一种方式，进入你的研究空间。</p>}
        </div>
        {sessionState==="checking"&&<p className={styles.sessionNotice} role="status">正在检查登录状态…</p>}
        {sessionState==="failed"&&<div className={styles.sessionNotice} role="alert"><p>暂时无法确认登录状态，请检查网络后重试。现有账号与登录状态不会被清除。</p><button className={styles.secondaryButton} type="button" onClick={()=>{setSessionState("checking");setSessionRetry(v=>v+1);}}>重新检查登录状态</button></div>}
        {authorized?<section className={styles.activeSession} aria-label="当前登录">
          <p>继续研究，或查看你的账号与访问权限。</p>
          <a className={styles.submit} href={returnTo==="/account"?"/platform/research":returnTo}>继续研究<ChevronRight size={18} aria-hidden="true"/></a>
          <a className={styles.secondaryButton} href="/account">进入账号中心</a>
          <button className={styles.textButton} type="button" disabled={loggingOut} onClick={logout}>{loggingOut?"正在安全退出…":"退出当前登录"}</button>
          {error&&<p role="alert" className={styles.error}>{error}</p>}
        </section>:<>
          {!method&&<>
            <nav className={styles.methodList} aria-label="选择登录方式">
              {choices.map(({method:choice,label,description,icon:Icon})=><a key={choice} className={styles.methodRow} href={accessHref(choice,returnTo)}>
                <span className={styles.methodIcon} aria-hidden="true">{Icon?<Icon size={21}/>:<b>G</b>}</span>
                <span className={styles.methodCopy}><strong>{label}</strong><small>{description}</small></span>
                <ChevronRight size={18} aria-hidden="true"/>
              </a>)}
            </nav>
            <p className={styles.registerLink}>还没有独立账号？<a href={accessHref("register",returnTo)}>注册 ORAKT 账号</a></p>
          </>}
          {sessionState==="ready"&&method==="google"&&<GoogleLogin returnTo={returnTo}/>}
          {sessionState==="ready"&&method==="phantom"&&<WalletLogin returnTo={returnTo}/>}
          {method==="chatgpt"&&<section className={styles.chatPanel} aria-label="ChatGPT 身份登录">
            <p>前往 ChatGPT 完成身份验证后，将返回 ORAKT。账号权限由 ORAKT 独立管理。</p>
            <a href={chatHref} target="_top" className={styles.submit}>继续使用 ChatGPT<ChevronRight size={18} aria-hidden="true"/></a>
          </section>}
          {sessionState==="ready"&&(method==="login"||method==="register"||method==="recover")&&<LocalLogin returnTo={returnTo} initialMode={method}/>}
        </>}
      </section>
      <p className={styles.accessNote}><ShieldCheck size={16} aria-hidden="true"/><span>登录不扣款。免费账号可查看地图与报告目录；正文按账号权限开放。</span></p>
    </div>
    <footer className={styles.legal}><span>© 2026 ORAKT · INSOLVE TECH</span><ReleaseStatus/></footer>
  </main>;
}
