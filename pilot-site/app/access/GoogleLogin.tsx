"use client";
import {useEffect,useRef,useState} from "react";
import styles from "./access.module.css";
import {authJsonGet,withAuthLock} from "./auth-request.mjs";

type GoogleIdentity = {
  initialize(options:{client_id:string;nonce:string;auto_select:boolean;ux_mode:string;callback:(result:{credential:string})=>void}):void;
  renderButton(element:HTMLElement,options:Record<string,unknown>):void;
  cancel():void;
};
const identity = () => (window as unknown as {google?:{accounts?:{id?:GoogleIdentity}}}).google?.accounts?.id;
let scriptPromise:Promise<void>|null=null;
function loadGoogle() {
  if(identity())return Promise.resolve();
  if(scriptPromise)return scriptPromise;
  scriptPromise=new Promise<void>((resolve,reject)=>{
    const script=document.createElement("script");script.src="https://accounts.google.com/gsi/client";script.async=true;
    const failed=()=>{clearTimeout(timer);script.remove();scriptPromise=null;reject(new Error("google_script_unavailable"));};
    const timer=setTimeout(failed,12000);
    script.onload=()=>{clearTimeout(timer);identity()?resolve():failed();};script.onerror=failed;document.head.appendChild(script);
  });
  return scriptPromise;
}

export default function GoogleLogin({returnTo}:{returnTo:string}) {
  const element=useRef<HTMLDivElement>(null),destination=useRef(returnTo);
  const [retry,setRetry]=useState(0),[status,setStatus]=useState("正在准备 Google 登录…"),[error,setError]=useState(""),[canonical,setCanonical]=useState("");
  useEffect(()=>{destination.current=returnTo;},[returnTo]);
  useEffect(()=>{
    let stopped=false,busy=false,expiryTimer:ReturnType<typeof setTimeout>;
    const controller=new AbortController();
    const host=element.current;
    if(host)host.replaceChildren();
    setError("");setStatus("正在准备 Google 登录…");setCanonical("");
    const post=async(path:string,body:object)=>{
      const response=await fetch(path,{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json","X-ORAKT-Auth":"google"},body:JSON.stringify(body),signal:AbortSignal.timeout(15000)});
      const payload=await response.json();if(!response.ok)throw new Error(payload.error??"google_login_unavailable");return payload;
    };
    const showError=(failure:unknown)=>{
      if(stopped)return;
      const messages:Record<string,string>={browser_unsupported:"当前浏览器缺少安全登录所需功能。请更新浏览器，或使用其他登录方式。",google_script_unavailable:"无法加载 Google 登录组件。请检查网络，或使用其他登录方式。",challenge_expired_or_used:"登录请求已过期或已使用，请刷新登录按钮后重试。",rate_limited:"请求较频繁，请一分钟后重试。",invalid_google_token:"Google 身份未通过服务器验证，请重新选择账户。"};
      setError((failure as Error).message==="auth_lock_timeout"?"另一个标签页仍在处理登录。请稍等片刻，再重新加载按钮。":(failure as Error).name==="TimeoutError"?"连接超时，请检查网络后重新加载登录按钮。":messages[(failure as Error).message]??"Google 登录暂时不可用，请稍后重试。");setStatus("");host?.replaceChildren();
    };
    async function prepare() {
      try {
        const config=await authJsonGet("/api/auth/google/config",{signal:controller.signal});if(stopped)return;
        if(!config.enabled){setStatus("");if(config.canonicalUrl)setCanonical(config.canonicalUrl);else setError("Google 登录配置暂不可用，其他登录方式不受影响。");return;}
        if(!navigator.locks)throw new Error("browser_unsupported");
        await loadGoogle();if(stopped)return;
        // Serializing the cookie-setting bootstrap across tabs prevents two
        // first-time tabs from creating unrelated browser revocation contexts.
        const challenge=await withAuthLock(navigator.locks,"orakt-google-challenge",()=>post("/api/auth/google/challenge",{}),{signal:controller.signal});if(stopped)return;
        identity()!.initialize({client_id:config.clientId,nonce:challenge.nonce,auto_select:false,ux_mode:"popup",callback:async result=>{
          if(stopped||busy)return;busy=true;clearTimeout(expiryTimer);setStatus("正在验证 Google 身份…");host?.setAttribute("inert","");
          try {
            await post("/api/auth/google/verify",{credential:result.credential,nonce:challenge.nonce,csrf:challenge.csrf});
            if(!stopped)window.location.assign(destination.current);
          } catch(failure){showError(failure);} finally{busy=false;host?.removeAttribute("inert");}
        }});
        if(host)identity()!.renderButton(host,{type:"standard",theme:"filled_black",size:"large",text:"signin_with",shape:"rectangular",locale:"zh_CN",width:Math.min(320,Math.max(200,host.clientWidth))});
        setStatus("请选择你的 Google 账户");
        expiryTimer=setTimeout(()=>{if(!busy)showError(new Error("challenge_expired_or_used"));},Math.max(0,challenge.expiresAt-Date.now()));
      }catch(failure){showError(failure);}
    }
    void prepare();
    return ()=>{stopped=true;controller.abort();clearTimeout(expiryTimer);identity()?.cancel();host?.replaceChildren();};
  },[retry]);
  return <section className={styles.googlePanel} aria-label="Google 账户登录">
    <div className={styles.googleTitle}><b>Google</b><span>账户登录 · 只读访问</span></div>
    <div ref={element} className={styles.googleButton} />
    {status&&<p role="status">{status}</p>}
    {canonical&&<a className={styles.googleCanonical} href={`${canonical}?return_to=${encodeURIComponent(returnTo)}`} target="_top">前往 orakt.com 使用 Google 登录</a>}
    {error&&<><p className={styles.error} role="alert">{error}</p><button className={styles.googleRetry} type="button" onClick={()=>setRetry(v=>v+1)}>重新加载登录按钮</button></>}
    <small>仅验证基本账户身份，不申请 Gmail、云盘或交易权限。登录由 Google 官方窗口完成。</small>
  </section>;
}
