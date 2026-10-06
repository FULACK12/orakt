"use client";

import { useEffect, useRef, useState } from "react";
import styles from "./access.module.css";

type PublicKey = { toString(): string };
type Provider = {
  isPhantom?: boolean;
  publicKey?: PublicKey;
  connect(): Promise<{ publicKey: PublicKey }>;
  signMessage(message: Uint8Array, encoding: string): Promise<{ signature: Uint8Array; publicKey: PublicKey }>;
  on?(event: string, callback: (...args: any[]) => void): void;
  removeListener?(event: string, callback: (...args: any[]) => void): void;
};
export function phantomProvider(): Provider | undefined {
  return (window as unknown as {phantom?: {solana?: Provider}}).phantom?.solana;
}

export default function WalletLogin({ returnTo }: { returnTo: string }) {
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
        attempt.current++; setError("钱包账户已变更，请关闭原签名窗口后重新验证。");
      }
    };
    provider?.on?.("accountChanged", changed);
    provider?.on?.("disconnect", changed);
    return () => { attempt.current++; provider?.removeListener?.("accountChanged", changed); provider?.removeListener?.("disconnect", changed); };
  }, [returnTo]);

  async function login() {
    setError("");
    const provider = phantomProvider();
    if (!provider?.isPhantom) { setError("未检测到 Phantom。电脑请安装官方扩展；手机请点击下方入口，在 Phantom 内打开。"); return; }
    const current = ++attempt.current;
    address.current = "";
    const ensureCurrent = () => { if (current !== attempt.current) throw new Error("account_changed"); };
    const request = async (path: string, body: object) => {
      const response = await fetch(path, {method: "POST", credentials: "same-origin", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body), signal: AbortSignal.timeout(15000)});
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error ?? "unavailable");
      return payload;
    };
    try {
      setStep("等待连接钱包…");
      const connected = await provider.connect(); ensureCurrent();
      const selectedAddress = connected.publicKey.toString();
      address.current = selectedAddress;
      setStep("获取一次性验证消息…");
      const challenge = await request("/api/wallet/challenge", {address: selectedAddress}); ensureCurrent();
      if (challenge.origin !== window.location.origin || challenge.address !== selectedAddress || !challenge.message?.startsWith(`${window.location.host} wants you to sign in with your Solana account:\n${selectedAddress}\n`)) throw new Error("invalid_challenge");
      setStep("请在钱包确认登录签名（不转账）…");
      const signed = await provider.signMessage(new TextEncoder().encode(challenge.message), "utf8"); ensureCurrent();
      if (signed.publicKey.toString() !== selectedAddress || provider.publicKey?.toString() !== selectedAddress) throw new Error("account_changed");
      const signature = btoa(String.fromCharCode(...signed.signature)).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
      setStep("服务器验证签名…");
      await request("/api/wallet/verify", {address: selectedAddress, nonce: challenge.nonce, signature});
      if (current !== attempt.current || provider.publicKey?.toString() !== selectedAddress) {
        await fetch("/api/access/session", {method: "DELETE", credentials: "same-origin"}); throw new Error("account_changed");
      }
      window.location.assign(returnTo);
    } catch (failure) {
      const issue = failure as Error & {code?: number};
      const messages: Record<string, string> = {rate_limited: "请求较频繁，请一分钟后重试。", wallet_service_unavailable: "钱包验证服务暂时不可用，请使用其他登录方式。", challenge_expired_or_used: "签名请求已过期或已使用，请重新连接验证。", account_changed: "钱包账户已变更，请重新验证。", invalid_signature: "签名未通过验证，请重试。"};
      setError(issue.code === 4001 ? "你取消了钱包授权，未进行任何交易。" : messages[issue.message] ?? "未完成钱包验证，请检查连接后重试。");
    } finally { setStep(""); }
  }

  return <section className={styles.walletPanel} aria-label="Solana 钱包登录">
    <div><span>SOLANA IDENTITY</span><b>Phantom 钱包</b></div>
    <p>只验证钱包归属，获得已发布报告的只读权限。不请求转账、交易授权或助记词。</p>
    <button type="button" onClick={login} disabled={Boolean(step)}>{step || "连接 Phantom 并签名登录"}</button>
    <div className={styles.walletLinks}>{browse && <a href={browse} target="_top">手机：在 Phantom 内打开</a>}<a href="https://phantom.com/download" target="_blank" rel="noopener noreferrer">安装官方钱包</a></div>
    <small>Safari / 微信内置浏览器不会注入钱包。手机验证需在 Phantom 浏览器完成，登录状态不会自动转回 Safari。</small>
    {error && <p className={styles.error} role="alert">{error}</p>}
    {step && <span className={styles.walletProgress} role="status">{step}</span>}
  </section>;
}
