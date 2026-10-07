"use client";
import {useEffect,useRef,useState} from "react";
import {ArrowUpRight,BookOpen,Building2,Globe2,LogOut,ShieldCheck,UserRound} from "lucide-react";
import OraktBrandIcon from "../OraktBrandIcon";
import ReleaseStatus from "../ReleaseStatus";
import WatchlistEditor from '../WatchlistEditor';
import useDisplayLanguage from "../useDisplayLanguage";
import styles from "./account.module.css";
import {authJsonGet} from "../access/auth-request.mjs";
import {accountAccessView,createReadSequence,nextAccountCheck} from "./account-state.mjs";
type Overview={checkedAt:string;account:{provider:string;displayName:string;accountId:string;expiresAt:string|null;createdAt:string|null;membership:{role:string;status:string;effectivePlan:string;grantKind:string;expiresAt:string|null;expired:boolean;permissions:{map:boolean;reports:boolean;research:boolean;manageUsers:boolean}}};scope:string;platform:{reports:number;companies:number;chinaCompanies:number;usCompanies:number;newsRecords:number;fullTextArticles:number;conflictRecords:number;snapshotAt:string;newsFrom:string;newsTo:string;conflictFrom:string;conflictTo:string}};
export default function AccountCenter(){
  const [language,setLanguage]=useDisplayLanguage(),zh=language==="zh";
  const [data,setData]=useState<Overview|null>(null),[error,setError]=useState(false),[retry,setRetry]=useState(0),[busy,setBusy]=useState(false),[logoutError,setLogoutError]=useState(false),[theme,setTheme]=useState<"dark"|"light">("dark");
  const [loading,setLoading]=useState(true),[clock,setClock]=useState(Date.now);
  const reads=useRef(createReadSequence()),loggingOut=useRef(false);
  useEffect(()=>{try{const v=localStorage.getItem("orakt-report-theme");if(v==="light"||v==="dark")setTheme(v);}catch{}},[]);
  useEffect(()=>{
    const request=reads.current.begin();let timer:ReturnType<typeof setTimeout>|undefined;
    setLoading(true);setError(false);
    authJsonGet("/api/account/overview",{signal:request.signal}).then((v:Overview)=>{
      if(!request.isCurrent())return;setData(v);setLoading(false);setClock(Date.now());
      timer=setTimeout(()=>{setClock(Date.now());if(document.visibilityState==="visible"){setLoading(true);setRetry(n=>n+1);}},nextAccountCheck(v.account));
    }).catch(e=>{if(!request.isCurrent())return;if(e.status===401){location.replace("/access?return_to=%2Faccount");return;}setError(true);setLoading(false);});
    return()=>{request.cancel();clearTimeout(timer);};
  },[retry]);
  useEffect(()=>{
    let last=Date.now();
    const check=(force:boolean)=>{if(document.visibilityState!=="visible"||(!force&&Date.now()-last<5000))return;last=Date.now();setClock(last);setLoading(true);setRetry(v=>v+1);};
    const focus=()=>check(false),visible=()=>check(true);
    window.addEventListener("focus",focus);document.addEventListener("visibilitychange",visible);
    return()=>{window.removeEventListener("focus",focus);document.removeEventListener("visibilitychange",visible);};
  },[]);
  async function logout(){if(loggingOut.current)return;loggingOut.current=true;setBusy(true);setLogoutError(false);try{const r=await fetch("/api/access/session",{method:"DELETE",credentials:"same-origin",signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error();const result=await r.json();location.assign(result.signOutHref||"/access");}catch{setLogoutError(true);setBusy(false);loggingOut.current=false;}}
  function chooseTheme(value:"light"|"dark"){setTheme(value);try{localStorage.setItem("orakt-report-theme",value);}catch{}}
  const format=(n:number)=>n.toLocaleString(zh?"zh-CN":"en-US"),date=(v:string)=>new Date(v).toLocaleString(zh?"zh-CN":"en-CA",{hour12:false}),platform=data?.platform;
  const access=data?accountAccessView(data.account.membership,clock):null;
  return <main className={styles.page} data-theme={theme}>
    <header className={styles.header}><a href="/" aria-label={zh?"返回官网":"ORAKT home"} className={styles.brand}><OraktBrandIcon/><strong>ORAKT</strong></a><nav><a href="/">{zh?"官网":"Home"}</a><a href="/platform/research">{zh?"研究报告":"Reports"}</a><button onClick={()=>setLanguage(zh?"en":"zh")}>{zh?"EN":"中文"}</button></nav></header>
    <div className={styles.workspace}>
      <section className={styles.heading}><div><span>ORAKT / ACCOUNT</span><h1>{zh?"账号中心":"Account center"}</h1><p>{zh?"你的访问身份，以及当前可查验的数据。":"Your identity and the published research available to you."}</p></div><a className={styles.primary} href="/platform/research">{zh?"继续研究":"Explore reports"}<ArrowUpRight size={20}/></a></section>
      {error?<section className={styles.notice} role="alert"><h2>{zh?"账号信息加载失败":"Account information unavailable"}</h2><p>{zh?"未显示缓存或猜测的数据。请检查网络后重试。":"No guessed or cached account data is shown. Please try again."}</p><button onClick={()=>setRetry(v=>v+1)}>{zh?"重新加载":"Retry"}</button></section>:!data?<section className={styles.notice} role="status">{zh?"正在读取账号与数据概览…":"Loading your account and data overview…"}</section>:<>
        <div className={styles.accountGrid}>
          <section className={styles.identity}><div className={styles.sectionTitle}><UserRound size={20}/><h2>{zh?"当前账号":"Your account"}</h2><span>{zh?"已登录":"Signed in"}</span></div><h3>{data.account.displayName}</h3><dl><div><dt>{zh?"登录方式":"Sign-in method"}</dt><dd>{data.account.provider==="local"?(zh?"用户名与密码":"Username & password"):data.account.provider==="google"?"Google":data.account.provider==="chatgpt"?"ChatGPT":"Phantom · Solana"}</dd></div><div><dt>{zh?"账号标识":"Account reference"}</dt><dd className={styles.reference}>{data.account.accountId}</dd></div><div><dt>{zh?"会话有效至":"Session expires"}</dt><dd>{data.account.expiresAt?date(data.account.expiresAt):(zh?"由 ChatGPT 管理":"Managed by ChatGPT")}</dd></div>{data.account.createdAt&&<div><dt>{zh?"注册时间":"Registered"}</dt><dd>{date(data.account.createdAt)}</dd></div>}</dl><p>{zh?"不同登录方式目前为独立身份，不会按邮箱或昵称自动合并。":"Sign-in methods remain separate identities; they are not merged by email or name."}</p></section>
          <section className={styles.permissions} aria-busy={loading}><div className={styles.sectionTitle}><ShieldCheck size={20}/><h2>{zh?"访问权限":"Access"}</h2></div>
            <div className={styles.accessFreshness}><small>{zh?"最近核验":"Last checked"} · {date(data.checkedAt)}</small><button disabled={loading} onClick={()=>{setLoading(true);setRetry(v=>v+1);}}>{zh?"刷新权限":"Refresh access"}</button></div>
            {loading?<p role="status">{zh?"正在重新核验权限，请稍候…":"Rechecking current access…"}</p>:<>
              <h3>{access!.plan}</h3>
              {data.account.membership.status==="suspended"&&<p role="alert">{zh?"账号已暂停，请联系站点管理员。":"Account suspended. Contact the administrator."}</p>}
              <ul className={styles.permissionList}>{[
                {label:zh?"地图与报告目录":"Map & report catalog",enabled:access!.map},
                {label:zh?"完整研究报告":"Full research reports",enabled:access!.reports},
                {label:zh?"回测与供应链比较":"Backtest & supply-chain comparisons",enabled:access!.research},
                {label:zh?"在线 AI 生成":"Online AI generation",enabled:false},
              ].map(item=><li key={item.label}><span>{item.label}</span><strong data-enabled={item.enabled}>{item.enabled?(zh?"已开放":"Enabled"):(zh?"未开放":"Not enabled")}</strong></li>)}</ul>
              {data.account.membership.expiresAt&&<p>{zh?"会员授权截止":"Membership grant ends"}: {date(data.account.membership.expiresAt)} {access!.inactiveGrant&&(zh?"（会员授权已失效）":"(membership grant inactive)")}</p>}
              <p>{zh?"授权来源记录：":"Grant source: "}{data.account.membership.grantKind==="manual_paid"?(zh?"管理员人工确认的线下付款；是否有效以当前权限为准。":"Manually confirmed offline payment; current permissions determine access."):data.account.membership.grantKind==="complimentary"?(zh?"赠送授权，不代表付款。":"Complimentary access, not a payment."):(zh?"免费账号。":"Free account.")}</p>
              {data.account.membership.role==="admin"&&<p>{zh?"管理员权限独立于会员套餐有效期。":"Administrator access is independent of membership expiry."}</p>}
              {access!.manageUsers&&<a className={styles.primary} href="/admin/users">{zh?"账号与权限管理":"Users & permissions"}</a>}
            </>}
            <div className={styles.boundary}>{zh?"在线收款尚未接通。授权不会自动扣费；所有账号均不能调用后台 AI 生成。需开通报告时，将账号标识发送给管理员。":"Online billing is not connected. Access never triggers a charge. AI generation is disabled for all users. Send your account reference to the administrator to request access."}</div>
          </section>
        </div>
        <section className={styles.overview}><div className={styles.overviewTitle}><h2>{zh?"平台数据概览":"Published data"}</h2><span>{zh?"平台总量，不是你的个人使用量":"Platform totals, not your personal usage"}</span></div><p className={styles.snapshot}>{zh?"数据版本日期":"Data version date"} · {date(platform!.snapshotAt)} · {zh?"非实时更新":"Not a live feed"}</p>
          <div className={styles.metrics}>{[
            {title:zh?"研究报告":"Research reports",value:platform!.reports,detail:zh?"已发布，可按公司与时间查验":"Published and available by company and date",icon:BookOpen,href:"/platform/research"},
            {title:zh?"覆盖公司":"Companies",value:platform!.companies,detail:zh?`A股 ${platform!.chinaCompanies} · 美股 ${platform!.usCompanies}`:`China ${platform!.chinaCompanies} · US ${platform!.usCompanies}`,icon:Building2,href:"/platform/research"},
            {title:zh?"新闻索引":"News index",value:platform!.newsRecords,detail:zh?`${format(platform!.fullTextArticles)} 篇具备正文，其余为发现线索`:`${format(platform!.fullTextArticles)} with substantive text; others are discovery leads`,icon:Globe2,href:"/platform/data"},
            {title:zh?"冲突记录":"Conflict records",value:platform!.conflictRecords,detail:`${platform!.conflictFrom} — ${platform!.conflictTo}`,icon:Globe2,href:"/platform"},
          ].map(m=><a key={m.title} href={m.href}><div><m.icon size={20}/><ArrowUpRight size={18}/></div><span>{m.title}</span><strong>{format(m.value)}</strong><small>{m.detail}</small></a>)}</div>
          <p className={styles.snapshot}>{zh?"新闻索引时间范围":"News index date range"}: {date(platform!.newsFrom)} — {date(platform!.newsTo)}</p>
        </section>
      </>}
      {data?.account.membership.status==='active'&&<WatchlistEditor language={language}/>}
      <div className={styles.settingsGrid}>
        <section className={styles.settings}><h2>{zh?"显示偏好":"Display preferences"}</h2><p>{zh?"仅保存在当前浏览器。报告阅读主题与这里保持一致。":"Saved only in this browser. The report reader uses this theme too."}</p><fieldset><legend>{zh?"界面语言":"Language"}</legend><button aria-pressed={zh} onClick={()=>setLanguage("zh")}>中文</button><button aria-pressed={!zh} onClick={()=>setLanguage("en")}>English</button></fieldset><fieldset><legend>{zh?"阅读主题":"Reading theme"}</legend><button aria-pressed={theme==="light"} onClick={()=>chooseTheme("light")}>{zh?"浅色":"Light"}</button><button aria-pressed={theme==="dark"} onClick={()=>chooseTheme("dark")}>{zh?"深色":"Dark"}</button></fieldset></section>
        <section className={styles.security}><h2>{zh?"安全与退出":"Security & sign out"}</h2><p>{zh?"退出会撤销此浏览器的 ORAKT 会话，不会退出 Google 账号，也不会转移钱包资产。":"Signing out revokes this browser’s ORAKT sessions. It does not sign out of Google or move wallet assets."}</p>{data?.account.provider==="local"&&<p>{zh?"忘记密码时，请在登录页使用保存的恢复码。请勿将恢复码分享给任何人。":"Use your saved recovery key on the sign-in page if you forget your password. Never share it."}</p>}<button className={styles.logout} onClick={logout} disabled={busy}><LogOut size={18}/>{busy?(zh?"正在安全退出…":"Signing out…"):(zh?"退出当前登录":"Sign out")}</button>{logoutError&&<p role="alert">{zh?"退出未完成；会话尚未确认撤销，请重试。":"Sign-out could not be confirmed. Please try again."}</p>}</section>
      </div>
      <footer className={styles.footer}><span>ORAKT · INSOLVE TECH</span><ReleaseStatus/><a href="/">{zh?"返回官网":"Back to home"}</a></footer>
    </div>
  </main>;
}
