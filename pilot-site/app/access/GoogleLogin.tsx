"use client";
import useDisplayLanguage from "../useDisplayLanguage";
import {authText} from "./auth-copy.mjs";
import { useEffect, useRef, useState } from "react";
import styles from "./access.module.css";
import { authJsonGet, withAuthLock } from "./auth-request.mjs";
type GoogleIdentity = {
    initialize(options: {
        client_id: string;
        nonce: string;
        auto_select: boolean;
        ux_mode: string;
        callback: (result: {
            credential: string;
        }) => void;
    }): void;
    renderButton(element: HTMLElement, options: Record<string, unknown>): void;
    cancel(): void;
};
const identity = () => (window as unknown as {
    google?: {
        accounts?: {
            id?: GoogleIdentity;
        };
    };
}).google?.accounts?.id;
let scriptPromise: Promise<void> | null = null;
function loadGoogle() {
    if (identity())
        return Promise.resolve();
    if (scriptPromise)
        return scriptPromise;
    scriptPromise = new Promise<void>((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "https://accounts.google.com/gsi/client";
        script.async = true;
        const failed = () => { clearTimeout(timer); script.remove(); scriptPromise = null; reject(new Error("google_script_unavailable")); };
        const timer = setTimeout(failed, 12000);
        script.onload = () => { clearTimeout(timer); identity() ? resolve() : failed(); };
        script.onerror = failed;
        document.head.appendChild(script);
    });
    return scriptPromise;
}
export default function GoogleLogin({ returnTo }: {
    returnTo: string;
}) {
    const [language, setLanguage] = useDisplayLanguage();
    const tr = (text: string) => authText(language, text);
    const element = useRef<HTMLDivElement>(null), destination = useRef(returnTo);
    const [retry, setRetry] = useState(0), [status, setStatus] = useState(tr("\u6B63\u5728\u51C6\u5907 Google \u767B\u5F55\u2026")), [error, setError] = useState(""), [canonical, setCanonical] = useState("");
    useEffect(() => { destination.current = returnTo; }, [returnTo]);
    useEffect(() => {
        let stopped = false, busy = false, expiryTimer: ReturnType<typeof setTimeout>;
        const controller = new AbortController();
        const host = element.current;
        if (host)
            host.replaceChildren();
        setError("");
        setStatus(tr("\u6B63\u5728\u51C6\u5907 Google \u767B\u5F55\u2026"));
        setCanonical("");
        const post = async (path: string, body: object) => {
            const response = await fetch(path, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-ORAKT-Auth": "google" }, body: JSON.stringify(body), signal: AbortSignal.timeout(15000) });
            const payload = await response.json();
            if (!response.ok)
                throw new Error(payload.error ?? "google_login_unavailable");
            return payload;
        };
        const showError = (failure: unknown) => {
            if (stopped)
                return;
            const messages: Record<string, string> = { browser_unsupported: tr("\u5F53\u524D\u6D4F\u89C8\u5668\u7F3A\u5C11\u5B89\u5168\u767B\u5F55\u6240\u9700\u529F\u80FD\u3002\u8BF7\u66F4\u65B0\u6D4F\u89C8\u5668\uFF0C\u6216\u4F7F\u7528\u5176\u4ED6\u767B\u5F55\u65B9\u5F0F\u3002"), google_script_unavailable: tr("\u65E0\u6CD5\u52A0\u8F7D Google \u767B\u5F55\u7EC4\u4EF6\u3002\u8BF7\u68C0\u67E5\u7F51\u7EDC\uFF0C\u6216\u4F7F\u7528\u5176\u4ED6\u767B\u5F55\u65B9\u5F0F\u3002"), challenge_expired_or_used: tr("\u767B\u5F55\u8BF7\u6C42\u5DF2\u8FC7\u671F\u6216\u5DF2\u4F7F\u7528\uFF0C\u8BF7\u5237\u65B0\u767B\u5F55\u6309\u94AE\u540E\u91CD\u8BD5\u3002"), rate_limited: tr("\u8BF7\u6C42\u8F83\u9891\u7E41\uFF0C\u8BF7\u4E00\u5206\u949F\u540E\u91CD\u8BD5\u3002"), invalid_google_token: tr("Google \u8EAB\u4EFD\u672A\u901A\u8FC7\u670D\u52A1\u5668\u9A8C\u8BC1\uFF0C\u8BF7\u91CD\u65B0\u9009\u62E9\u8D26\u6237\u3002") };
            setError((failure as Error).message === "auth_lock_timeout" ? tr("\u53E6\u4E00\u4E2A\u6807\u7B7E\u9875\u4ECD\u5728\u5904\u7406\u767B\u5F55\u3002\u8BF7\u7A0D\u7B49\u7247\u523B\uFF0C\u518D\u91CD\u65B0\u52A0\u8F7D\u6309\u94AE\u3002") : (failure as Error).name === "TimeoutError" ? tr("\u8FDE\u63A5\u8D85\u65F6\uFF0C\u8BF7\u68C0\u67E5\u7F51\u7EDC\u540E\u91CD\u65B0\u52A0\u8F7D\u767B\u5F55\u6309\u94AE\u3002") : messages[(failure as Error).message] ?? tr("Google \u767B\u5F55\u6682\u65F6\u4E0D\u53EF\u7528\uFF0C\u8BF7\u7A0D\u540E\u91CD\u8BD5\u3002"));
            setStatus("");
            host?.replaceChildren();
        };
        async function prepare() {
            try {
                const config = await authJsonGet("/api/auth/google/config", { signal: controller.signal });
                if (stopped)
                    return;
                if (!config.enabled) {
                    setStatus("");
                    if (config.canonicalUrl)
                        setCanonical(config.canonicalUrl);
                    else
                        setError(tr("Google \u767B\u5F55\u914D\u7F6E\u6682\u4E0D\u53EF\u7528\uFF0C\u5176\u4ED6\u767B\u5F55\u65B9\u5F0F\u4E0D\u53D7\u5F71\u54CD\u3002"));
                    return;
                }
                if (!navigator.locks)
                    throw new Error("browser_unsupported");
                await loadGoogle();
                if (stopped)
                    return;
                // Serializing the cookie-setting bootstrap across tabs prevents two
                // first-time tabs from creating unrelated browser revocation contexts.
                const challenge = await withAuthLock(navigator.locks, "orakt-google-challenge", () => post("/api/auth/google/challenge", {}), { signal: controller.signal });
                if (stopped)
                    return;
                identity()!.initialize({ client_id: config.clientId, nonce: challenge.nonce, auto_select: false, ux_mode: "popup", callback: async (result) => {
                        if (stopped || busy)
                            return;
                        busy = true;
                        clearTimeout(expiryTimer);
                        setStatus(tr("\u6B63\u5728\u9A8C\u8BC1 Google \u8EAB\u4EFD\u2026"));
                        host?.setAttribute("inert", "");
                        try {
                            await post("/api/auth/google/verify", { credential: result.credential, nonce: challenge.nonce, csrf: challenge.csrf });
                            if (!stopped)
                                window.location.assign(destination.current);
                        }
                        catch (failure) {
                            showError(failure);
                        }
                        finally {
                            busy = false;
                            host?.removeAttribute("inert");
                        }
                    } });
                if (host)
                    identity()!.renderButton(host, { type: "standard", theme: "filled_black", size: "large", text: "signin_with", shape: "rectangular", locale: language==="zh"?"zh_CN":"en", width: Math.min(320, Math.max(200, host.clientWidth)) });
                setStatus(tr("\u8BF7\u9009\u62E9\u4F60\u7684 Google \u8D26\u6237"));
                expiryTimer = setTimeout(() => { if (!busy)
                    showError(new Error("challenge_expired_or_used")); }, Math.max(0, challenge.expiresAt - Date.now()));
            }
            catch (failure) {
                showError(failure);
            }
        }
        void prepare();
        return () => { stopped = true; controller.abort(); clearTimeout(expiryTimer); identity()?.cancel(); host?.replaceChildren(); };
    }, [retry,language]);
    return <section className={styles.googlePanel} aria-label={tr("Google \u8D26\u6237\u767B\u5F55")}>
    <div className={styles.googleTitle}><b>Google</b><span>{tr("\u8D26\u6237\u767B\u5F55 \u00B7 \u53EA\u8BFB\u8BBF\u95EE")}</span></div>
    <div ref={element} className={styles.googleButton}/>
    {status && <p role="status">{status}</p>}
    {canonical && <a className={styles.googleCanonical} href={`${canonical}?return_to=${encodeURIComponent(returnTo)}`} target="_top">{tr("\u524D\u5F80 orakt.com \u4F7F\u7528 Google \u767B\u5F55")}</a>}
    {error && <><p className={styles.error} role="alert">{error}</p><button className={styles.googleRetry} type="button" onClick={() => setRetry(v => v + 1)}>{tr("\u91CD\u65B0\u52A0\u8F7D\u767B\u5F55\u6309\u94AE")}</button></>}
    <small>{tr("\u4EC5\u9A8C\u8BC1\u57FA\u672C\u8D26\u6237\u8EAB\u4EFD\uFF0C\u4E0D\u7533\u8BF7 Gmail\u3001\u4E91\u76D8\u6216\u4EA4\u6613\u6743\u9650\u3002\u767B\u5F55\u7531 Google \u5B98\u65B9\u7A97\u53E3\u5B8C\u6210\u3002")}</small>
  </section>;
}
