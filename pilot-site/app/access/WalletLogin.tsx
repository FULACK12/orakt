"use client";
import useDisplayLanguage from "../useDisplayLanguage";
import {authText} from "./auth-copy.mjs";
import { useEffect, useRef, useState } from "react";
import styles from "./access.module.css";
type PublicKey = {
    toString(): string;
};
type Provider = {
    isPhantom?: boolean;
    publicKey?: PublicKey;
    connect(): Promise<{
        publicKey: PublicKey;
    }>;
    signMessage(message: Uint8Array, encoding: string): Promise<{
        signature: Uint8Array;
        publicKey: PublicKey;
    }>;
    on?(event: string, callback: (...args: any[]) => void): void;
    removeListener?(event: string, callback: (...args: any[]) => void): void;
};
export function phantomProvider(): Provider | undefined {
    return (window as unknown as {
        phantom?: {
            solana?: Provider;
        };
    }).phantom?.solana;
}
export default function WalletLogin({ returnTo }: {
    returnTo: string;
}) {
    const [language, setLanguage] = useDisplayLanguage();
    const tr = (text: string) => authText(language, text);
    const [step, setStep] = useState("");
    const [error, setError] = useState("");
    const [browse, setBrowse] = useState("");
    const attempt = useRef(0);
    const address = useRef("");
    useEffect(() => {
        setBrowse(`https://phantom.app/ul/browse/${encodeURIComponent(window.location.href)}?ref=${encodeURIComponent(window.location.origin)}`);
        const provider = phantomProvider();
        const changed = (next?: PublicKey) => {
            if (address.current && next?.toString() !== address.current) {
                attempt.current++;
                setError(tr("\u94B1\u5305\u8D26\u6237\u5DF2\u53D8\u66F4\uFF0C\u8BF7\u5173\u95ED\u539F\u7B7E\u540D\u7A97\u53E3\u540E\u91CD\u65B0\u9A8C\u8BC1\u3002"));
            }
        };
        provider?.on?.("accountChanged", changed);
        provider?.on?.("disconnect", changed);
        return () => { attempt.current++; provider?.removeListener?.("accountChanged", changed); provider?.removeListener?.("disconnect", changed); };
    }, [returnTo]);
    async function login() {
        setError("");
        const provider = phantomProvider();
        if (!provider?.isPhantom) {
            setError(tr("\u672A\u68C0\u6D4B\u5230 Phantom\u3002\u7535\u8111\u8BF7\u5B89\u88C5\u5B98\u65B9\u6269\u5C55\uFF1B\u624B\u673A\u8BF7\u70B9\u51FB\u4E0B\u65B9\u5165\u53E3\uFF0C\u5728 Phantom \u5185\u6253\u5F00\u3002"));
            return;
        }
        const current = ++attempt.current;
        address.current = "";
        const ensureCurrent = () => { if (current !== attempt.current)
            throw new Error("account_changed"); };
        const request = async (path: string, body: object) => {
            const response = await fetch(path, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal: AbortSignal.timeout(15000) });
            const payload = await response.json();
            if (!response.ok)
                throw new Error(payload.error ?? "unavailable");
            return payload;
        };
        try {
            setStep(tr("\u7B49\u5F85\u8FDE\u63A5\u94B1\u5305\u2026"));
            const connected = await provider.connect();
            ensureCurrent();
            const selectedAddress = connected.publicKey.toString();
            address.current = selectedAddress;
            setStep(tr("\u83B7\u53D6\u4E00\u6B21\u6027\u9A8C\u8BC1\u6D88\u606F\u2026"));
            const challenge = await request("/api/wallet/challenge", { address: selectedAddress });
            ensureCurrent();
            if (challenge.origin !== window.location.origin || challenge.address !== selectedAddress || !challenge.message?.startsWith(`${window.location.host} wants you to sign in with your Solana account:\n${selectedAddress}\n`))
                throw new Error("invalid_challenge");
            setStep(tr("\u8BF7\u5728\u94B1\u5305\u786E\u8BA4\u767B\u5F55\u7B7E\u540D\uFF08\u4E0D\u8F6C\u8D26\uFF09\u2026"));
            const signed = await provider.signMessage(new TextEncoder().encode(challenge.message), "utf8");
            ensureCurrent();
            if (signed.publicKey.toString() !== selectedAddress || provider.publicKey?.toString() !== selectedAddress)
                throw new Error("account_changed");
            const signature = btoa(String.fromCharCode(...signed.signature)).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
            setStep(tr("\u670D\u52A1\u5668\u9A8C\u8BC1\u7B7E\u540D\u2026"));
            await request("/api/wallet/verify", { address: selectedAddress, nonce: challenge.nonce, signature });
            if (current !== attempt.current || provider.publicKey?.toString() !== selectedAddress) {
                await fetch("/api/access/session", { method: "DELETE", credentials: "same-origin" });
                throw new Error("account_changed");
            }
            window.location.assign(returnTo);
        }
        catch (failure) {
            const issue = failure as Error & {
                code?: number;
            };
            const messages: Record<string, string> = { rate_limited: tr("\u8BF7\u6C42\u8F83\u9891\u7E41\uFF0C\u8BF7\u4E00\u5206\u949F\u540E\u91CD\u8BD5\u3002"), wallet_service_unavailable: tr("\u94B1\u5305\u9A8C\u8BC1\u670D\u52A1\u6682\u65F6\u4E0D\u53EF\u7528\uFF0C\u8BF7\u4F7F\u7528\u5176\u4ED6\u767B\u5F55\u65B9\u5F0F\u3002"), challenge_expired_or_used: tr("\u7B7E\u540D\u8BF7\u6C42\u5DF2\u8FC7\u671F\u6216\u5DF2\u4F7F\u7528\uFF0C\u8BF7\u91CD\u65B0\u8FDE\u63A5\u9A8C\u8BC1\u3002"), account_changed: tr("\u94B1\u5305\u8D26\u6237\u5DF2\u53D8\u66F4\uFF0C\u8BF7\u91CD\u65B0\u9A8C\u8BC1\u3002"), invalid_signature: tr("\u7B7E\u540D\u672A\u901A\u8FC7\u9A8C\u8BC1\uFF0C\u8BF7\u91CD\u8BD5\u3002") };
            setError(issue.code === 4001 ? tr("\u4F60\u53D6\u6D88\u4E86\u94B1\u5305\u6388\u6743\uFF0C\u672A\u8FDB\u884C\u4EFB\u4F55\u4EA4\u6613\u3002") : messages[issue.message] ?? tr("\u672A\u5B8C\u6210\u94B1\u5305\u9A8C\u8BC1\uFF0C\u8BF7\u68C0\u67E5\u8FDE\u63A5\u540E\u91CD\u8BD5\u3002"));
        }
        finally {
            setStep("");
        }
    }
    return <section className={styles.walletPanel} aria-label={tr("Solana \u94B1\u5305\u767B\u5F55")}>
    <div><span>SOLANA IDENTITY</span><b>{tr("Phantom \u94B1\u5305")}</b></div>
    <p>{tr("\u53EA\u9A8C\u8BC1\u94B1\u5305\u5F52\u5C5E\uFF0C\u83B7\u5F97\u5DF2\u53D1\u5E03\u62A5\u544A\u7684\u53EA\u8BFB\u6743\u9650\u3002\u4E0D\u8BF7\u6C42\u8F6C\u8D26\u3001\u4EA4\u6613\u6388\u6743\u6216\u52A9\u8BB0\u8BCD\u3002")}</p>
    <button type="button" onClick={login} disabled={Boolean(step)}>{step || tr("\u8FDE\u63A5 Phantom \u5E76\u7B7E\u540D\u767B\u5F55")}</button>
    <div className={styles.walletLinks}>{browse && <a href={browse} target="_top">{tr("\u624B\u673A\uFF1A\u5728 Phantom \u5185\u6253\u5F00")}</a>}<a href="https://phantom.com/download" target="_blank" rel="noopener noreferrer">{tr("\u5B89\u88C5\u5B98\u65B9\u94B1\u5305")}</a></div>
    <small>{tr("Safari / \u5FAE\u4FE1\u5185\u7F6E\u6D4F\u89C8\u5668\u4E0D\u4F1A\u6CE8\u5165\u94B1\u5305\u3002\u624B\u673A\u9A8C\u8BC1\u9700\u5728 Phantom \u6D4F\u89C8\u5668\u5B8C\u6210\uFF0C\u767B\u5F55\u72B6\u6001\u4E0D\u4F1A\u81EA\u52A8\u8F6C\u56DE Safari\u3002")}</small>
    {error && <p className={styles.error} role="alert">{error}</p>}
    {step && <span className={styles.walletProgress} role="status">{step}</span>}
  </section>;
}
