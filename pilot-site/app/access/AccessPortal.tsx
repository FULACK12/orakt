"use client";
import useDisplayLanguage from "../useDisplayLanguage";
import {authText} from "./auth-copy.mjs";
import { useEffect, useState } from "react";
import { ArrowLeft, ChevronRight, MessageCircle, ShieldCheck, UserRound, Wallet } from "lucide-react";
import OraktBrandIcon from "../OraktBrandIcon";
import GoogleLogin from "./GoogleLogin";
import WalletLogin from "./WalletLogin";
import LocalLogin from "./LocalLogin";
import ReleaseStatus from "../ReleaseStatus";
import { accessHref } from "./access-navigation.mjs";
import { authJsonGet } from "./auth-request.mjs";
import styles from "./access.module.css";
export type AccessMethod = "chatgpt" | "google" | "phantom" | "login" | "register" | "recover";
const titles: Record<AccessMethod, string> = { chatgpt: "使用 ChatGPT 登录", google: "使用 Google 登录", phantom: "使用 Phantom 登录", login: "登录 ORAKT 账号", register: "创建 ORAKT 账号", recover: "找回 ORAKT 密码" };
const choices = [
    { method: "google", label: "Google", description: "使用 Google 账户", icon: null },
    { method: "chatgpt", label: "ChatGPT", description: "使用 ChatGPT 身份", icon: MessageCircle },
    { method: "phantom", label: "Phantom", description: "使用 Solana 钱包", icon: Wallet },
    { method: "login", label: "ORAKT 账号", description: "使用用户名与密码", icon: UserRound },
] as const;
export default function AccessPortal({ chatHref, returnTo, method }: {
    chatHref: string;
    returnTo: string;
    method?: AccessMethod;
}) {
    const [language, setLanguage] = useDisplayLanguage();
    const tr = (text: string) => authText(language, text);
    const [authorized, setAuthorized] = useState(false), [error, setError] = useState(""), [loggingOut, setLoggingOut] = useState(false);
    const [sessionState, setSessionState] = useState<"checking" | "ready" | "failed">("checking"), [sessionRetry, setSessionRetry] = useState(0);
    useEffect(() => {
        const controller = new AbortController();
        setSessionState("checking");
        authJsonGet("/api/access/session", { signal: controller.signal, timeoutMs: 8000 })
            .then(d => { if (!controller.signal.aborted) {
            setAuthorized(Boolean(d?.authorized));
            setSessionState("ready");
        } })
            .catch(() => { if (!controller.signal.aborted)
            setSessionState("failed"); });
        return () => controller.abort();
    }, [sessionRetry]);
    async function logout() {
        if (loggingOut)
            return;
        setLoggingOut(true);
        setError("");
        try {
            const r = await fetch("/api/access/session", { method: "DELETE", credentials: "same-origin", signal: AbortSignal.timeout(15000) });
            if (!r.ok)
                throw Error();
            const result = await r.json();
            location.assign(result.signOutHref || "/access");
        }
        catch {
            setError(tr("\u9000\u51FA\u672A\u5B8C\u6210\uFF0C\u8BF7\u68C0\u67E5\u7F51\u7EDC\u540E\u91CD\u8BD5\u3002"));
            setLoggingOut(false);
        }
    }
    return <main className={styles.page}>
    <header className={styles.header}>
      <a href="/" aria-label={tr("ORAKT \u5B98\u7F51")} className={styles.logo}><OraktBrandIcon /><strong>ORAKT</strong></a>
      <a href="/" className={styles.homeReturn}><ArrowLeft size={16} aria-hidden="true"/>{tr("\u8FD4\u56DE\u5B98\u7F51")}</a>
    <button className={styles.languageChoice} onClick={()=>setLanguage(language==="zh"?"en":"zh")} aria-label={language==="zh"?"Switch to English":"切换到中文"}>{language==="zh"?"English":"中文"}</button></header>
    <div className={styles.authShell}>
      {method && <a className={styles.backLink} href={accessHref("", returnTo)}><ArrowLeft size={16} aria-hidden="true"/>{tr("\u5176\u4ED6\u767B\u5F55\u65B9\u5F0F")}</a>}
      <section className={styles.accessCard} aria-labelledby="access-heading" data-access-method={method || "choose"}>
        <div className={styles.authIntro}>
          <span>ORAKT / ACCOUNT ACCESS</span>
          <h1 id="access-heading">{authorized ? tr("\u4F60\u5DF2\u767B\u5F55") : method ? tr(titles[method]) : tr("\u767B\u5F55 ORAKT")}</h1>
          {!method && !authorized && <p>{tr("\u9009\u62E9\u4E00\u79CD\u65B9\u5F0F\uFF0C\u8FDB\u5165\u4F60\u7684\u7814\u7A76\u7A7A\u95F4\u3002")}</p>}
        </div>
        {sessionState === "checking" && <p className={styles.sessionNotice} role="status">{tr("\u6B63\u5728\u68C0\u67E5\u767B\u5F55\u72B6\u6001\u2026")}</p>}
        {sessionState === "failed" && <div className={styles.sessionNotice} role="alert"><p>{tr("\u6682\u65F6\u65E0\u6CD5\u786E\u8BA4\u767B\u5F55\u72B6\u6001\uFF0C\u8BF7\u68C0\u67E5\u7F51\u7EDC\u540E\u91CD\u8BD5\u3002\u73B0\u6709\u8D26\u53F7\u4E0E\u767B\u5F55\u72B6\u6001\u4E0D\u4F1A\u88AB\u6E05\u9664\u3002")}</p><button className={styles.secondaryButton} type="button" onClick={() => { setSessionState("checking"); setSessionRetry(v => v + 1); }}>{tr("\u91CD\u65B0\u68C0\u67E5\u767B\u5F55\u72B6\u6001")}</button></div>}
        {authorized ? <section className={styles.activeSession} aria-label={tr("\u5F53\u524D\u767B\u5F55")}>
          <p>{tr("\u7EE7\u7EED\u7814\u7A76\uFF0C\u6216\u67E5\u770B\u4F60\u7684\u8D26\u53F7\u4E0E\u8BBF\u95EE\u6743\u9650\u3002")}</p>
          <a className={styles.submit} href={returnTo === "/account" ? "/platform/research" : returnTo}>{tr("\u7EE7\u7EED\u7814\u7A76")}<ChevronRight size={18} aria-hidden="true"/></a>
          <a className={styles.secondaryButton} href="/account">{tr("\u8FDB\u5165\u8D26\u53F7\u4E2D\u5FC3")}</a>
          <button className={styles.textButton} type="button" disabled={loggingOut} onClick={logout}>{loggingOut ? tr("\u6B63\u5728\u5B89\u5168\u9000\u51FA\u2026") : tr("\u9000\u51FA\u5F53\u524D\u767B\u5F55")}</button>
          {error && <p role="alert" className={styles.error}>{error}</p>}
        </section> : <>
          {!method && <>
            <nav className={styles.methodList} aria-label={tr("\u9009\u62E9\u767B\u5F55\u65B9\u5F0F")}>
              {choices.map(({ method: choice, label, description, icon: Icon }) => <a key={choice} className={styles.methodRow} href={accessHref(choice, returnTo)}>
                <span className={styles.methodIcon} aria-hidden="true">{Icon ? <Icon size={21}/> : <b>G</b>}</span>
                <span className={styles.methodCopy}><strong>{tr(label)}</strong><small>{tr(description)}</small></span>
                <ChevronRight size={18} aria-hidden="true"/>
              </a>)}
            </nav>
            <p className={styles.registerLink}>{tr("\u8FD8\u6CA1\u6709\u72EC\u7ACB\u8D26\u53F7\uFF1F")}<a href={accessHref("register", returnTo)}>{tr("\u6CE8\u518C ORAKT \u8D26\u53F7")}</a></p>
          </>}
          {sessionState === "ready" && method === "google" && <GoogleLogin returnTo={returnTo}/>}
          {sessionState === "ready" && method === "phantom" && <WalletLogin returnTo={returnTo}/>}
          {method === "chatgpt" && <section className={styles.chatPanel} aria-label={tr("ChatGPT \u8EAB\u4EFD\u767B\u5F55")}>
            <p>{tr("\u524D\u5F80 ChatGPT \u5B8C\u6210\u8EAB\u4EFD\u9A8C\u8BC1\u540E\uFF0C\u5C06\u8FD4\u56DE ORAKT\u3002\u8D26\u53F7\u6743\u9650\u7531 ORAKT \u72EC\u7ACB\u7BA1\u7406\u3002")}</p>
            <a href={chatHref} target="_top" className={styles.submit}>{tr("\u7EE7\u7EED\u4F7F\u7528 ChatGPT")}<ChevronRight size={18} aria-hidden="true"/></a>
          </section>}
          {sessionState === "ready" && (method === "login" || method === "register" || method === "recover") && <LocalLogin returnTo={returnTo} initialMode={method}/>}
        </>}
      </section>
      <p className={styles.accessNote}><ShieldCheck size={16} aria-hidden="true"/><span>{tr("\u767B\u5F55\u4E0D\u6263\u6B3E\u3002\u514D\u8D39\u8D26\u53F7\u53EF\u67E5\u770B\u5730\u56FE\u4E0E\u62A5\u544A\u76EE\u5F55\uFF1B\u6B63\u6587\u6309\u8D26\u53F7\u6743\u9650\u5F00\u653E\u3002")}</span></p>
    </div>
    <p className={styles.policyNote}>{language==="zh"?"继续前请阅读":"Before continuing, review our"} <a href="/privacy" target="_blank" rel="noreferrer">{language==="zh"?"隐私说明":"Privacy notice"}</a> · <a href="/terms" target="_blank" rel="noreferrer">{language==="zh"?"使用条件与研究风险":"Terms & research risks"}</a>{language==="zh"?"。登录不代表订阅或交易授权。":". Signing in is not a subscription or trading authorization."}</p><footer className={styles.legal}><span>© 2026 ORAKT · INSOLVE TECH</span><ReleaseStatus /></footer>
  </main>;
}
