"use client";
import useDisplayLanguage from "../useDisplayLanguage";
import {authText} from "./auth-copy.mjs";
import { useEffect, useRef, useState, type FormEvent } from "react";
import styles from "./access.module.css";
import { accessHref } from "./access-navigation.mjs";
import { authJsonGet, withAuthLock } from "./auth-request.mjs";
type Mode = "login" | "register" | "recover";
export default function LocalLogin({ returnTo, initialMode = "login" }: {
    returnTo: string;
    initialMode?: Mode;
}) {
    const [language, setLanguage] = useDisplayLanguage();
    const tr = (text: string) => authText(language, text);
    const mode = initialMode;
    const [username, setUsername] = useState(""), [password, setPassword] = useState(""), [confirm, setConfirm] = useState(""), [key, setKey] = useState("");
    const [busy, setBusy] = useState(false), [error, setError] = useState(""), [recovery, setRecovery] = useState(""), [saved, setSaved] = useState(false), [enabled, setEnabled] = useState<boolean | null>(null);
    const [configError, setConfigError] = useState(""), [retry, setRetry] = useState(0), [phase, setPhase] = useState("");
    const lifetime = useRef<AbortController | null>(null), submitting = useRef(false);
    useEffect(() => { const c = new AbortController(); lifetime.current = c; return () => c.abort(); }, []);
    useEffect(() => {
        const c = new AbortController();
        setEnabled(null);
        setConfigError("");
        authJsonGet("/api/auth/local/config", { signal: c.signal }).then(d => {
            if (c.signal.aborted)
                return;
            setEnabled(Boolean(d.enabled && navigator.locks));
            if (!d.enabled)
                setConfigError(tr("\u81EA\u4E3B\u8D26\u53F7\u670D\u52A1\u6682\u4E0D\u53EF\u7528\uFF0C\u8BF7\u7A0D\u540E\u91CD\u8BD5\u6216\u9009\u62E9\u5176\u4ED6\u767B\u5F55\u65B9\u5F0F\u3002"));
            else if (!navigator.locks)
                setConfigError(tr("\u5F53\u524D\u6D4F\u89C8\u5668\u7F3A\u5C11\u5B89\u5168\u767B\u5F55\u80FD\u529B\uFF0C\u8BF7\u66F4\u65B0\u6D4F\u89C8\u5668\u6216\u9009\u62E9\u5176\u4ED6\u767B\u5F55\u65B9\u5F0F\u3002"));
        }).catch(e => { if (!c.signal.aborted) {
            setEnabled(false);
            setConfigError(e.name === "TimeoutError" ? tr("\u8FDE\u63A5\u8D85\u65F6\uFF0C\u8BF7\u68C0\u67E5\u7F51\u7EDC\u540E\u91CD\u65B0\u52A0\u8F7D\u3002") : tr("\u65E0\u6CD5\u52A0\u8F7D\u8D26\u53F7\u670D\u52A1\uFF0C\u8BF7\u68C0\u67E5\u7F51\u7EDC\u540E\u91CD\u8BD5\u3002"));
        } });
        return () => c.abort();
    }, [retry]);
    async function submit(e: FormEvent) {
        e.preventDefault();
        if (submitting.current || !enabled)
            return;
        if (mode !== "login" && password !== confirm) {
            setError(tr("\u4E24\u6B21\u8F93\u5165\u7684\u5BC6\u7801\u4E0D\u4E00\u81F4\u3002"));
            return;
        }
        if ([...password].length < 15) {
            setError(tr("\u5BC6\u7801\u81F3\u5C11 15 \u4E2A\u5B57\u7B26\uFF0C\u53EF\u4F7F\u7528\u6613\u8BB0\u7684\u957F\u53E5\u3002"));
            return;
        }
        submitting.current = true;
        setBusy(true);
        setError("");
        setPhase(tr("\u6B63\u5728\u7B49\u5F85\u5B89\u5168\u901A\u9053\u2026"));
        const signal = lifetime.current?.signal;
        try {
            const payload = await withAuthLock(navigator.locks, "orakt-local-auth", async () => {
                setPhase(tr("\u6B63\u5728\u5B89\u5168\u9A8C\u8BC1\u2026"));
                const send = (action: string, body: unknown) => fetch(`/api/auth/local/${action}`, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-ORAKT-Auth": "local" }, body: JSON.stringify(body), signal: AbortSignal.timeout(30000) });
                const challenge = await send("challenge", { action: mode }), proof = await challenge.json();
                if (!challenge.ok)
                    throw new Error(proof.error);
                setPhase(mode === "register" ? tr("\u6B63\u5728\u521B\u5EFA\u8D26\u53F7\uFF0C\u8BF7\u52FF\u91CD\u590D\u63D0\u4EA4\u2026") : mode === "recover" ? tr("\u6B63\u5728\u66F4\u65B0\u5BC6\u7801\u4E0E\u6062\u590D\u7801\uFF0C\u8BF7\u52FF\u91CD\u590D\u63D0\u4EA4\u2026") : tr("\u6B63\u5728\u6838\u5BF9\u8D26\u53F7\u2026"));
                const response = await send(mode, { ...proof, username, password, ...(mode === "recover" ? { recoveryKey: key.trim() } : {}) }), data = await response.json();
                if (!response.ok)
                    throw new Error(data.error);
                return data;
            }, { signal });
            if (signal?.aborted)
                return;
            setPassword("");
            setConfirm("");
            setKey("");
            if (payload.recoveryKey) {
                setRecovery(payload.recoveryKey);
                setSaved(false);
            }
            else
                window.location.assign(returnTo);
        }
        catch (e) {
            if (signal?.aborted)
                return;
            const message = (e as Error).message;
            setError(({ auth_lock_timeout: tr("\u53E6\u4E00\u4E2A\u6807\u7B7E\u9875\u4ECD\u5728\u5904\u7406\u8D26\u53F7\u64CD\u4F5C\u3002\u672C\u6B21\u5C1A\u672A\u63D0\u4EA4\uFF0C\u8BF7\u7A0D\u7B49\u7247\u523B\u540E\u91CD\u8BD5\u3002"), invalid_credentials: tr("\u7528\u6237\u540D\u6216\u5BC6\u7801\u4E0D\u6B63\u786E\u3002"), registration_unavailable: tr("\u8BE5\u7528\u6237\u540D\u4E0D\u53EF\u6CE8\u518C\uFF0C\u8BF7\u6362\u4E00\u4E2A\u540D\u79F0\u6216\u524D\u5F80\u767B\u5F55\u3002"), invalid_recovery: tr("\u7528\u6237\u540D\u6216\u6062\u590D\u7801\u4E0D\u6B63\u786E\uFF0C\u65E7\u6062\u590D\u7801\u53EA\u80FD\u4F7F\u7528\u4E00\u6B21\u3002"), rate_limited: tr("\u5C1D\u8BD5\u8FC7\u4E8E\u9891\u7E41\uFF0C\u8BF7\u7A0D\u540E\u518D\u8BD5\uFF0C\u4E0D\u8981\u8FDE\u7EED\u5237\u65B0\u3002"), challenge_expired_or_used: tr("\u672C\u6B21\u9A8C\u8BC1\u5DF2\u8FC7\u671F\uFF0C\u8BF7\u91CD\u65B0\u63D0\u4EA4\u3002"), invalid_request: tr("\u8BF7\u68C0\u67E5\u7528\u6237\u540D\u3001\u5BC6\u7801\u957F\u5EA6\u548C\u6062\u590D\u7801\u683C\u5F0F\u3002") } as Record<string, string>)[message] ?? tr("\u672A\u80FD\u786E\u8BA4\u64CD\u4F5C\u7ED3\u679C\uFF0C\u8BF7\u52FF\u91CD\u590D\u6CE8\u518C\u6216\u91CD\u7F6E\u3002\u82E5\u5DF2\u63D0\u4EA4\uFF0C\u53EF\u5C1D\u8BD5\u7528\u8BE5\u5BC6\u7801\u767B\u5F55\uFF1B\u4E0D\u8981\u4E22\u5F03\u539F\u6062\u590D\u7801\u3002"));
        }
        finally {
            submitting.current = false;
            if (!signal?.aborted) {
                setBusy(false);
                setPhase("");
            }
        }
    }
    function download() { const blob = new Blob([`ORAKT account: ${username.trim().toLowerCase()}\nRecovery key: ${recovery}\nKeep offline. Anyone with this key can reset your password.\n`], { type: "text/plain" }), url = URL.createObjectURL(blob), a = document.createElement("a"); a.href = url; a.download = "orakt-recovery-key.txt"; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
    return <section className={styles.localPanel} aria-label={tr("ORAKT \u81EA\u4E3B\u6CE8\u518C\u8D26\u53F7")}>
    {recovery ? <div className={styles.recoveryPanel}>
      <h4>{mode === "register" ? tr("\u8D26\u53F7\u5DF2\u521B\u5EFA") : tr("\u5BC6\u7801\u5DF2\u91CD\u7F6E")}{tr("\u00B7 \u4FDD\u5B58\u6062\u590D\u7801")}</h4>
      <p>{tr("\u4EC5\u663E\u793A\u8FD9\u4E00\u6B21\u3002\u5FD8\u8BB0\u5BC6\u7801\u65F6\uFF0C\u7528\u7528\u6237\u540D\u548C\u6062\u590D\u7801\u91CD\u7F6E\u3002\u8BF7\u79BB\u7EBF\u4FDD\u7BA1\uFF0C\u4E0D\u8981\u53D1\u9001\u7ED9\u4ED6\u4EBA\u3002\u91CD\u7F6E\u540E\u65E7\u6062\u590D\u7801\u548C\u6240\u6709\u65E7\u767B\u5F55\u4F1A\u8BDD\u5931\u6548\u3002")}</p>
      <code>{recovery}</code><button type="button" onClick={download}>{tr("\u4E0B\u8F7D\u6062\u590D\u7801")}</button>
      <label className={styles.checkbox}><input type="checkbox" checked={saved} onChange={e => setSaved(e.target.checked)}/>{tr("\u6211\u5DF2\u59A5\u5584\u4FDD\u5B58\uFF1B\u4E22\u5931\u5BC6\u7801\u548C\u6062\u590D\u7801\u5C06\u65E0\u6CD5\u627E\u56DE\u8D26\u53F7\u3002")}</label>
      <button type="button" disabled={!saved} onClick={() => window.location.assign(accessHref("login", returnTo))}>{tr("\u8FD4\u56DE\u767B\u5F55")}</button>
    </div> : <>
      <p>{mode === "login" ? tr("\u4F7F\u7528\u4F60\u6CE8\u518C\u7684\u7528\u6237\u540D\u4E0E\u5BC6\u7801\u3002") : mode === "register" ? tr("\u65E0\u9700\u7B2C\u4E09\u65B9\u8D26\u53F7\u3002\u6CE8\u518C\u540E\u8BF7\u4FDD\u5B58\u6062\u590D\u7801\uFF0C\u7528\u4E8E\u627E\u56DE\u5BC6\u7801\u3002") : tr("\u4F7F\u7528\u7528\u6237\u540D\u548C\u6062\u590D\u7801\u91CD\u8BBE\u5BC6\u7801\u3002\u65E7\u6062\u590D\u7801\u53CA\u65E7\u767B\u5F55\u4F1A\u8BDD\u5C06\u5931\u6548\u3002")}</p>
      <form onSubmit={submit}>
        <label htmlFor="local-username">{tr("\u7528\u6237\u540D")}<small>{tr("4\u201332 \u4F4D\u82F1\u6587\u5B57\u6BCD\u3001\u6570\u5B57\u3001\u4E0B\u5212\u7EBF\u6216\u77ED\u6A2A\u7EBF")}</small></label>
        <input id="local-username" autoComplete="username" autoCapitalize="none" spellCheck={false} pattern={"[a-zA-Z0-9][a-zA-Z0-9_\\-]{3,31}"} minLength={4} maxLength={32} required value={username} onChange={e => setUsername(e.target.value)} disabled={busy}/>
        {mode === "recover" && <><label htmlFor="recovery-key">{tr("\u6062\u590D\u7801")}</label><input id="recovery-key" type="password" autoComplete="off" maxLength={64} minLength={64} required value={key} onChange={e => setKey(e.target.value)} disabled={busy}/></>}
        <label htmlFor="local-password">{mode === "recover" ? tr("\u65B0\u5BC6\u7801") : tr("\u5BC6\u7801")} <small>{tr("\u81F3\u5C11 15 \u4E2A\u5B57\u7B26\uFF0C\u6700\u591A 128 \u4E2A")}</small></label>
        <input id="local-password" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} maxLength={256} required value={password} onChange={e => setPassword(e.target.value)} disabled={busy}/>
        {mode !== "login" && <><label htmlFor="confirm-password">{tr("\u518D\u6B21\u8F93\u5165\u5BC6\u7801")}</label><input id="confirm-password" type="password" autoComplete="new-password" required value={confirm} onChange={e => setConfirm(e.target.value)} disabled={busy}/></>}
        {error && <p role="alert" className={styles.error}>{error}</p>}
        {enabled === null && <p role="status">{tr("\u6B63\u5728\u8FDE\u63A5\u8D26\u53F7\u670D\u52A1\u2026")}</p>}
        {configError && <><p role="alert" className={styles.error}>{configError}</p><button className={styles.secondaryButton} type="button" disabled={busy} onClick={() => { setEnabled(null); setConfigError(""); setRetry(v => v + 1); }}>{tr("\u91CD\u65B0\u52A0\u8F7D\u8D26\u53F7\u670D\u52A1")}</button></>}
        {busy && <p role="status">{phase}</p>}
        <button className={styles.submit} disabled={busy || !enabled} type="submit">{busy ? tr("\u5904\u7406\u4E2D\uFF0C\u8BF7\u7A0D\u5019\u2026") : mode === "login" ? tr("\u767B\u5F55 ORAKT") : mode === "register" ? tr("\u521B\u5EFA\u8D26\u53F7") : tr("\u91CD\u7F6E\u5BC6\u7801\u5E76\u66F4\u65B0\u6062\u590D\u7801")}</button>
        {mode !== "login" && <small>{tr("\u4E0D\u6536\u96C6\u90AE\u7BB1\uFF0C\u6CA1\u6709\u90AE\u4EF6\u627E\u56DE\u529F\u80FD\u3002\u72EC\u7ACB\u8D26\u53F7\u4E0D\u4F1A\u4E0E Google\u3001ChatGPT \u6216 Phantom \u81EA\u52A8\u5408\u5E76\u3002")}</small>}
      </form>
      <nav className={styles.localLinks} aria-label={tr("\u5176\u4ED6\u8D26\u53F7\u64CD\u4F5C")}>{(["login", "register", "recover"] as Mode[]).filter(v => v !== mode).map(v => <a key={v} href={accessHref(v, returnTo)} aria-disabled={busy || undefined} onClick={e => { if (busy)
            e.preventDefault(); }}>{v === "login" ? tr("\u5DF2\u6709\u8D26\u53F7\uFF0C\u53BB\u767B\u5F55") : v === "register" ? tr("\u6CE8\u518C\u8D26\u53F7") : tr("\u5FD8\u8BB0\u5BC6\u7801\uFF1F")}</a>)}</nav>
    </>}
  </section>;
}
