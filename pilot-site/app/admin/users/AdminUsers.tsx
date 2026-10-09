"use client";
import {useEffect,useRef,useState} from "react";
import useDisplayLanguage from "../../useDisplayLanguage";
import {authJsonGet} from "../../access/auth-request.mjs";
import {createReadSequence} from "../../account/account-state.mjs";
import styles from "../../membership.module.css";

type User={id:string;provider:string;displayName:string;createdAt:string;lastSeenAt:string|null;role:string;plan:string;effectivePlan:string;status:string;grantKind:string;expiresAt:string|null;revision:number};
type Directory={asOf:string;stats:Record<string,number|null>;providers:{provider:string;accounts:number}[];pendingLocalAccounts:number;users:User[];page:number;matched:number};
type Audit={id:string;targetId:string;createdAt:number;reason:string;beforeJson:string;afterJson:string};

export default function AdminUsers(){
 const [language,setLanguage]=useDisplayLanguage(),zh=language==="zh";
 const [data,setData]=useState<Directory|null>(null),[q,setQ]=useState(""),[search,setSearch]=useState(""),[page,setPage]=useState(1),[refresh,setRefresh]=useState(0),[error,setError]=useState(""),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[message,setMessage]=useState("");
 const [selected,setSelected]=useState<User|null>(null),[plan,setPlan]=useState("explorer"),[status,setStatus]=useState("active"),[grantKind,setGrantKind]=useState("free"),[expiry,setExpiry]=useState(""),[reason,setReason]=useState(""),[confirmed,setConfirmed]=useState(false);
 const [audit,setAudit]=useState<Audit[]>([]),[auditState,setAuditState]=useState<"loading"|"ready"|"error">("loading"),[auditRetry,setAuditRetry]=useState(0);
 const directoryReads=useRef(createReadSequence()),auditReads=useRef(createReadSequence()),operation=useRef(false);

 useEffect(()=>{
   const request=directoryReads.current.begin();setLoading(true);setError("");setData(null);
   authJsonGet("/api/admin/users?page="+page+"&q="+encodeURIComponent(search),{signal:request.signal}).then((result:Directory)=>{
     if(request.isCurrent()){setData(result);setLoading(false);}
   }).catch(e=>{if(request.isCurrent()){setError(e.status===401?"session_expired":e.status===403?"admin_required":"load_failed");setLoading(false);}});
   return()=>request.cancel();
 },[page,search,refresh]);

 useEffect(()=>{
   if(!selected)return;
   const request=auditReads.current.begin(),targetId=selected.id;
   setAudit([]);setAuditState("loading");
   authJsonGet("/api/admin/user-audit?id="+encodeURIComponent(targetId),{signal:request.signal}).then((result:{targetId:string;events:Audit[]})=>{
     if(!request.isCurrent())return;
     if(result.targetId!==targetId||result.events.some(event=>event.targetId!==targetId))throw Error("audit_target_mismatch");
     setAudit(result.events);setAuditState("ready");
   }).catch(()=>{if(request.isCurrent())setAuditState("error");});
   return()=>request.cancel();
 },[selected?.id,auditRetry]);

 function closeEditor(){auditReads.current.cancel();setSelected(null);setConfirmed(false);}
 function reload(){directoryReads.current.cancel();setLoading(true);setRefresh(v=>v+1);}
 function select(u:User){
   if(operation.current||loading)return;
   auditReads.current.cancel();setAudit([]);setAuditState("loading");setAuditRetry(v=>v+1);
   setSelected(u);setPlan(u.plan);setStatus(u.status);setGrantKind(u.grantKind==='onchain_paid'?'complimentary':u.grantKind);setExpiry(u.expiresAt?u.expiresAt.slice(0,10):"");setReason("");setConfirmed(false);setMessage("");
 }
 async function submit(){
   if(operation.current||!selected||!confirmed||auditState!=="ready")return;
   if(plan!=="explorer"&&(!/^\d{4}-\d{2}-\d{2}$/.test(expiry)||Date.parse(expiry+"T23:59:59Z")<=Date.now()||!Number.isFinite(Date.parse(expiry)))){setMessage(zh?"请选择未来的有效期；付费与赠送授权都需要截止日期。":"Choose a future expiry date for paid or complimentary access.");setConfirmed(false);return;}
   const body={id:selected.id,revision:selected.revision,plan,status,grantKind:plan==="explorer"?"free":grantKind,expiresAt:plan==="explorer"?null:Date.parse(expiry+"T23:59:59Z"),reason};
   operation.current=true;setBusy(true);setMessage("");
   try{
     const r=await fetch("/api/admin/user-access",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json","X-ORAKT-Admin":"access"},body:JSON.stringify(body),signal:AbortSignal.timeout(20000)});
     const result=await r.json();
     if(r.status>=500)throw Error("write_result_unknown");
     if(!r.ok){
       if(result.error==="revision_conflict"){
         setMessage(zh?"此账号已被其他操作修改。已刷新列表，请重新选择并核对历史，不会覆盖旧变更。":"Account changed elsewhere. The list was refreshed; reselect it and review its history.");closeEditor();reload();return;
       }
       const errors:Record<string,string>={invalid_entitlement:zh?"授权信息无效：请选择未来五年以内的截止日期及正确授权来源。":"Invalid entitlement: choose a future expiry within five years and a valid grant type.",admin_required:zh?"当前登录身份没有管理员权限，请检查账号中心。":"This identity does not have administrator access. Check Account.",cross_origin_request:zh?"请求来源校验失败，请从 orakt.com 重新登录后再试。":"Origin verification failed. Sign in again at orakt.com.",same_origin_required:zh?"请求来源校验失败，请重新登录。":"Origin verification failed; sign in again."};
       setMessage(errors[result.error]||(zh?"服务器未接受变更，请核对有效期、授权类型、原因及管理权限。":"The server rejected this change. Check expiry, grant type, reason and administrator access."));setConfirmed(false);return;
     }
     setMessage(zh?"权限已更新，变更已留痕。":"Access updated and audited.");closeEditor();reload();
   }catch{
     // A lost response does not prove the write failed. Reconcile, never retry.
     setMessage(zh?"未能确认提交结果，可能已保存。已刷新列表；请重新选择该账号并查看权限记录，再决定是否需要操作，勿重复提交。":"The result is unconfirmed and may have been saved. The list was refreshed. Reselect the account and check its history before taking further action.");closeEditor();reload();
   }finally{operation.current=false;setBusy(false);}
 }
 async function importLocal(){
   if(operation.current)return;operation.current=true;setBusy(true);setMessage("");
   try{
     const r=await fetch("/api/admin/import-local",{method:"POST",credentials:"same-origin",headers:{"X-ORAKT-Admin":"access"},signal:AbortSignal.timeout(20000)});
     if(!r.ok)throw Error();await r.json();setMessage(zh?"导入已完成，正在更新统计。":"Import completed; refreshing counts.");
   }catch{setMessage(zh?"导入结果未确认，请以刷新后的待导入数量为准，不会自动重复提交。":"Import result unconfirmed. Check the refreshed pending count; no automatic retry was made.");}
   finally{closeEditor();reload();operation.current=false;setBusy(false);}
 }
 const date=(v:string|null)=>v?new Date(v).toLocaleString(zh?"zh-CN":"en-CA"):"—";
 const editorDisabled=busy||auditState!=="ready";
 return <main className={styles.adminPage}><section className={styles.panel}>
   <div className={styles.pager}><a href="/">ORAKT</a><a href="/account">{zh?"账号中心":"Account"}</a><button onClick={()=>setLanguage(zh?"en":"zh")}>{zh?"EN":"中文"}</button></div>
   <span className={styles.kicker}>PRIVATE / ACCESS CONTROL</span><h1>{zh?"账号与权限管理":"Users & access"}</h1>
   <p>{zh?"仅管理员可见。这里统计登录身份，不是去重后的自然人数；不同平台账号不会自动合并。":"Administrator only. Counts represent provider accounts, not unique people. Identities are not automatically merged."}</p>
   {error?<div role="alert"><p>{error==="session_expired"?(zh?"登录已失效，请重新登录。":"Session expired. Please sign in again."):error==="admin_required"?(zh?"当前账号没有管理权限。需要由站点所有者明确绑定管理员账号。":"Administrator access is required; the site owner must explicitly bind the account."):(zh?"读取失败或连接超时，未显示旧列表或估算数据。":"Read failed or timed out. No stale list or estimated counts are shown.")}</p>{error==="session_expired"?<a href="/access?return_to=%2Fadmin%2Fusers">{zh?"重新登录":"Sign in again"}</a>:<button disabled={busy} onClick={reload}>{zh?"重试":"Retry"}</button>}</div>:loading||!data?<p role="status">{zh?"正在读取所选查询的真实账号记录…":"Loading current account records for this query…"}</p>:<>
     <p className={styles.timestamp}>{zh?"统计读取时间":"Counts read at"} · {date(data.asOf)} · {zh?"刷新时更新，不是实时在线人数":"Updated on refresh, not a live concurrent-user count"}</p>
     <div className={styles.stats}>{[["totalAccounts","已登记账号","Registered accounts"],["active24h","24小时访问","Visited in 24h"],["active7d","7天访问","Visited in 7d"],["active30d","30天访问","Visited in 30d"],["onchainPaid","有效链上付费授权","Active on-chain paid"],["manuallyConfirmedPaid","有效人工付费授权","Active manually paid"],["complimentary","有效赠送授权","Active complimentary"],["suspended","已暂停账号","Suspended"]].map(([k,cn,en])=><article key={k}><small>{zh?cn:en}</small><strong>{data.stats[k]??0}</strong></article>)}</div>
     <div className={styles.notice}><p>{data.providers.map(p=>p.provider+": "+p.accounts).join(" · ")}</p><p>{zh?"统计开始于":"Tracking since"} {data.stats.trackedSince?date(new Date(data.stats.trackedSince).toISOString()):"—"}</p><p>{zh?"旧 Google、Phantom、ChatGPT 账号会在下次访问时登记，历史总人数无法从过期会话还原。活跃统计依据产品访问，不以账号页轮询充数。":"Legacy Google, Phantom and ChatGPT accounts register on their next visit. Expired sessions cannot reconstruct historical users. Activity reflects product visits, not account polling."}</p>{data.pendingLocalAccounts>0&&<p>{zh?"待导入本地注册账号":"Local registrations pending import"}: {data.pendingLocalAccounts} <button disabled={busy} onClick={importLocal}>{zh?"导入下一批（最多100）":"Import next batch (up to 100)"}</button></p>}<p>{zh?"链上付款与人工确认付款分别统计，赠送权限不计作付费。原付款记录不会因人工调整授权而删除。":"On-chain and manually confirmed payments are counted separately. Complimentary grants are not paid. Manual access changes do not erase payment records."}</p></div>
     <form className={styles.filters} onSubmit={e=>{e.preventDefault();if(operation.current)return;closeEditor();setSearch(q);setPage(1);reload();}}><label>{zh?"查找账号":"Find account"}<input disabled={busy} value={q} onChange={e=>setQ(e.target.value)} placeholder={zh?"标识、昵称或登录平台":"Reference, name or provider"}/></label><button disabled={busy} type="submit">{zh?"确定查询":"Search"}</button><button disabled={busy} type="button" onClick={()=>{closeEditor();reload();}}>{zh?"刷新":"Refresh"}</button></form>
     <div className={styles.table}><table><thead><tr>{(zh?["账号","平台","权限","最近访问","操作"]:["Account","Provider","Access","Last product visit","Action"]).map(s=><th key={s}>{s}</th>)}</tr></thead><tbody>{data.users.map(u=><tr key={u.id}><td>{u.displayName}<br/><small>{u.id}</small></td><td>{u.provider}</td><td>{u.role==="admin"?"ADMIN":u.effectivePlan.toUpperCase()} · {u.status}</td><td>{date(u.lastSeenAt)}</td><td><button disabled={busy} onClick={()=>select(u)}>{zh?"管理":"Manage"}</button></td></tr>)}</tbody></table>{!data.users.length&&<p>{zh?"当前查询没有匹配账号。":"No accounts match this query."}</p>}</div>
     <div className={styles.pager}><button disabled={busy||data.page===1} onClick={()=>{closeEditor();directoryReads.current.cancel();setLoading(true);setPage(data.page-1);}}>{zh?"上一页":"Previous"}</button><span>{data.page} / {Math.max(1,Math.ceil(data.matched/40))}</span><button disabled={busy||data.page*40>=data.matched} onClick={()=>{closeEditor();directoryReads.current.cancel();setLoading(true);setPage(data.page+1);}}>{zh?"下一页":"Next"}</button></div>
   </>}
   {message&&<p role="status" className={styles.notice}>{message}</p>}
   {selected&&<section className={styles.editor} aria-busy={busy||auditState==="loading"}>
     <h2>{zh?"调整账号授权":"Change access"} · {selected.displayName}</h2><code>{selected.id}</code>
     <p>{zh?"角色由站点所有者绑定，此处不能将会员升级为管理员。":"Roles are bound by the site owner; membership never grants administrator access."}</p>
     {selected.grantKind==='onchain_paid'&&<p role="alert">{zh?'此账号为链上付款授权。此处提交将覆盖为人工授权（默认赠送），不会退款或删除原付款记录；请谨慎核对。':'This account has paid on-chain access. Saving here replaces it with a manual grant (complimentary by default); it does not refund or erase the payment. Review carefully.'}</p>}
     <fieldset disabled={editorDisabled} className={styles.editorFields}>
       <legend className={styles.kicker}>{zh?"核对权限与有效期":"Verify access and expiry"}</legend>
       <div className={styles.filters}>
         <label>{zh?"套餐":"Plan"}<select aria-label={zh?"套餐":"Plan"} value={plan} onChange={e=>{setPlan(e.target.value);setGrantKind(e.target.value==="explorer"?"free":"complimentary");if(e.target.value!=="explorer"&&(!expiry||Date.parse(expiry+"T23:59:59Z")<=Date.now()))setExpiry(new Date(Date.now()+30*86400000).toISOString().slice(0,10));setConfirmed(false);}}><option value="explorer">Explorer</option><option value="signal">Signal</option><option value="research">Research</option></select></label>
         <label>{zh?"账号状态":"Account status"}<select aria-label={zh?"账号状态":"Account status"} value={status} onChange={e=>{setStatus(e.target.value);setConfirmed(false);}}><option value="active">{zh?"启用":"Active"}</option><option value="suspended" disabled={selected.role==="admin"}>{zh?"暂停":"Suspended"}</option></select></label>
         <label>{zh?"授权来源":"Grant type"}<select aria-label={zh?"授权来源":"Grant type"} disabled={plan==="explorer"} value={grantKind} onChange={e=>{setGrantKind(e.target.value);setConfirmed(false);}}>{plan==="explorer"?<option value="free">{zh?"免费":"Free"}</option>:<><option value="complimentary">{zh?"赠送授权":"Complimentary access"}</option><option value="manual_paid">{zh?"已人工确认线下付款":"Manually confirmed payment"}</option></>}</select></label>
         <label>{zh?"有效至（UTC 当日末）":"Expires (end of day UTC)"}<input type="date" required={plan!=="explorer"} min={new Date().toISOString().slice(0,10)} disabled={plan==="explorer"} value={expiry} onChange={e=>{setExpiry(e.target.value);setConfirmed(false);}}/>{plan!=="explorer"&&<small>{zh?"新授权默认填入30天，请核对后确认；这不会自动收款。":"New grants default to 30 days. Review before confirming; no automatic payment."}</small>}</label>
       </div>
       <label>{zh?"变更原因（至少5字符，勿填密码或支付凭证）":"Reason (5+ characters; no passwords or payment credentials)"}<textarea maxLength={500} value={reason} onChange={e=>{setReason(e.target.value);setConfirmed(false);}}/></label>
       <label className={styles.check}><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>{zh?"确认对象、权限和有效期正确；如选择付费，已在外部核实收到款项。":"I verified the account, access and expiry; if marked paid, payment was independently confirmed."}</label>
       <button disabled={editorDisabled||!confirmed||reason.trim().length<5||(plan!=="explorer"&&(!expiry||!Number.isFinite(Date.parse(expiry))||Date.parse(expiry+"T23:59:59Z")<=Date.now()))} onClick={submit}>{busy?(zh?"提交中…":"Saving…"):(zh?"确认变更":"Confirm change")}</button>
     </fieldset>
     <button onClick={closeEditor} disabled={busy}>{zh?"关闭编辑":"Close editor"}</button>
     <h3>{zh?"该账号最近50条权限记录":"This account’s latest 50 access changes"}</h3>
     {auditState==="loading"?<p role="status">{zh?"正在核对该账号的权限记录…":"Checking this account’s access history…"}</p>:auditState==="error"?<div role="alert"><p>{zh?"权限记录读取失败，不能据此判断没有历史变更。请重试后再调整权限。":"History could not be verified; this does not mean it is empty. Retry before changing access."}</p><button disabled={busy} onClick={()=>{setAuditState("loading");setConfirmed(false);setAuditRetry(v=>v+1);}}>{zh?"重新读取权限记录":"Retry access history"}</button></div>:audit.length?audit.map(a=><article key={a.id} className={styles.audit}><strong>{date(new Date(a.createdAt).toISOString())}</strong><p>{a.reason}</p><details><summary>{zh?"查看变更前后原始记录":"View before / after records"}</summary><p>{a.beforeJson} → {a.afterJson}</p></details></article>):<p>{zh?"已核验：该账号暂无权限变更记录。":"Verified: no access changes recorded for this account."}</p>}
   </section>}
 </section></main>;
}
