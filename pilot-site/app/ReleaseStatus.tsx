"use client";
import {useEffect, useState} from "react";
const VERSION = "142";
export default function ReleaseStatus({language="zh"}:{language?:"zh"|"en"}) {
  const [latest, setLatest] = useState(VERSION);
  useEffect(() => {
    const controller = new AbortController();
    let lastCheck = 0;
    const check = () => {
      if (document.visibilityState !== "visible" || Date.now() - lastCheck < 30000) return;
      lastCheck = Date.now();
      fetch("/api/app-version", {cache: "no-store", signal: controller.signal}).then(r => r.ok ? r.json() : null).then(p => {if (p?.version) setLatest(p.version);}).catch(() => {});
    };
    check(); document.addEventListener("visibilitychange", check); window.addEventListener("pageshow", check);
    const timer = window.setInterval(check, 120000);
    return () => {controller.abort(); clearInterval(timer); document.removeEventListener("visibilitychange", check); window.removeEventListener("pageshow", check);};
  }, []);
  return <span className="release-status">{language==="zh"?"界面":"Interface"} v{VERSION}{latest !== VERSION && <button onClick={() => window.location.reload()}>{language==="zh"?"新版可用 · 刷新页面":"Update available · Reload"}</button>}</span>;
}
