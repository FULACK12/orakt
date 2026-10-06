"use client";
import {useEffect, useState} from "react";
import {usePathname} from "next/navigation";
import {phantomProvider} from "./access/WalletLogin";
export default function WalletSessionGuard() {
  const pathname = usePathname();
  const [logoutError, setLogoutError] = useState(false);
  useEffect(() => {
    if (!pathname.startsWith("/platform")) return;
    const provider = phantomProvider();
    if (!provider) return;
    let address = "", cancelled = false, loaded = false, hadEvent = false, signingOut = false;
    let lastKey: {toString(): string} | undefined;
    const changed = async (key?: {toString(): string}) => {
      hadEvent = true; lastKey = key;
      if (!loaded || !address || key?.toString() === address || cancelled || signingOut) return;
      signingOut = true;
      try {
        const response = await fetch("/api/access/session", {method: "DELETE", credentials: "same-origin", signal: AbortSignal.timeout(15000)});
        if (!response.ok) throw new Error("logout");
        const result=await response.json();
        window.location.assign(result.signOutHref||"/access");
      } catch { if (!cancelled) setLogoutError(true); }
      finally { signingOut = false; }
    };
    provider.on?.("accountChanged", changed); provider.on?.("disconnect", changed);
    fetch("/api/access/session", {credentials: "same-origin"}).then(r => r.json()).then(s => {
      loaded = true;
      if (!cancelled && s.provider === "phantom") {address = s.walletAddress; if (hadEvent) void changed(lastKey); else if (provider.publicKey) void changed(provider.publicKey);}
    }).catch(() => {});
    return () => {cancelled = true; provider.removeListener?.("accountChanged", changed); provider.removeListener?.("disconnect", changed);};
  }, [pathname]);
  return logoutError ? <div className="wallet-session-alert" role="alert"><strong>钱包账户已变化，但退出请求未完成。</strong><p>请在账户页重试退出；当前会话尚不能视为已撤销。</p><a href="/access">前往账户页</a><a href="/">返回官网</a></div> : null;
}
