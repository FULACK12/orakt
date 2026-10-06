"use client";
import { useEffect, useId, useRef, useState, type CSSProperties } from "react";
import { useSceneActivity } from "./useSceneActivity";
import { createSceneClock } from "./scene-clock.mjs";
import styles from "./OraktProductScenes.module.css";

const scenes = {
  zh: [
    { label: "事件", title: "先确认，发生了什么。", tag: "事实输入", lines: ["航道运输中断", "报道时间与地理位置", "保留原文与来源"], status: "来源可追溯" },
    { label: "机制", title: "让每一个“因为”显形。", tag: "待验证假设", lines: ["运输受阻 → 可用供给下降？", "库存能否缓冲冲击？", "替代航线是否有效？"], status: "机制尚待检验" },
    { label: "核验", title: "证据与反证，同时入场。", tag: "逐步检索", lines: ["核对运量与库存变化", "对齐价格和事件时间", "排除需求变化等解释"], status: "缺口不会被隐藏" },
    { label: "结论", title: "结论有边界，也有来路。", tag: "研究记录", lines: ["关联不自动等于因果", "证据不足则暂缓判断", "保留版本，等待未来验证"], status: "可查验 · 可修订" },
  ],
  en: [
    { label: "EVENT", title: "Begin with what happened.", tag: "SOURCE RECORD", lines: ["Shipping route disrupted", "Time and location preserved", "Original reporting linked"], status: "TRACEABLE SOURCE" },
    { label: "MECHANISM", title: "Make every ‘because’ visible.", tag: "HYPOTHESIS", lines: ["Disruption → reduced supply?", "Can inventory absorb the shock?", "Are alternate routes viable?"], status: "REQUIRES VERIFICATION" },
    { label: "VERIFY", title: "Evidence meets counterevidence.", tag: "EVIDENCE RETRIEVAL", lines: ["Check freight and inventory", "Align event and price timestamps", "Test alternative demand effects"], status: "GAPS REMAIN VISIBLE" },
    { label: "FINDING", title: "A conclusion with boundaries.", tag: "RESEARCH RECORD", lines: ["Correlation is not causation", "Defer when evidence is thin", "Versioned for forward validation"], status: "AUDITABLE · REVISABLE" },
  ],
};

export default function OraktChainScene({ language }: { language: "zh" | "en" }) {
  const { ref, running, reduced } = useSceneActivity();
  const [step, setStep] = useState(0);
  const [paused, setPaused] = useState(false);
  const id = useId().replace(/:/g, "");
  const spectrum = `${id}-spectrum`, glass = `${id}-glass`, core = `${id}-core`;
  const clock = useRef(createSceneClock());
  const progressRef = useRef<HTMLDivElement>(null);
  const t = scenes[language];
  const playing = running && !paused;
  useEffect(() => {
    if (!playing) return;
    const playback = clock.current;
    let frame = 0;
    let lastPaint = 0;
    playback.resume(performance.now());
    const tick = (now: number) => {
      if (now - lastPaint >= 32) {
        const state = playback.tick(now);
        progressRef.current?.style.setProperty("--step-progress", String(state.progress));
        if (state.completed) setStep(value => (value + 1) % 4);
        lastPaint = now;
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(frame); playback.pause(); };
  }, [playing]);

  function selectStep(index: number) {
    clock.current.reset();
    progressRef.current?.style.setProperty("--step-progress", "0");
    setStep(index);
    setPaused(true);
  }

  return <div ref={ref} className={styles.scene} data-running={playing} data-step={step} data-scene="chains" data-animation="loop">
    <div className={styles.sceneHeader}><span><i/> ORAKT CHAINS <b>/ 02</b></span><button type="button" onClick={() => setPaused(value => !value)} disabled={reduced} aria-pressed={paused || reduced} aria-label={language==="zh"?(paused?"播放证据链动画":"暂停证据链动画"):(paused?"Play chain animation":"Pause chain animation")}>{paused || reduced ? "▶" : "Ⅱ"}</button></div>
    <div className={styles.chainTitle}><span>CAUSAL INTELLIGENCE</span><h4>{language==="zh"?"让证据，穿透噪声。":"Signal through the noise."}</h4></div>
    <div className={styles.chainStage}>
      <svg className={styles.engine} viewBox="0 0 700 370" role="img" aria-labelledby={`${id}-title`}>
        <title id={`${id}-title`}>{language==="zh"?"多源证据经由四层核验核心，形成可追溯结论的光路示意":"Evidence streams cross a four-layer verification core to form traceable findings"}</title>
        <defs>
          <linearGradient id={spectrum} x1="0" y1="280" x2="680" y2="90" gradientUnits="userSpaceOnUse"><stop stopColor="#a3ff12"/><stop offset=".47" stopColor="#00e5ff"/><stop offset="1" stopColor="#9b5cff"/></linearGradient>
          <linearGradient id={glass} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#323948"/><stop offset=".45" stopColor="#111b27"/><stop offset="1" stopColor="#191125"/></linearGradient>
          <radialGradient id={core}><stop stopColor="#00e5ff" stopOpacity=".19"/><stop offset=".55" stopColor="#9b5cff" stopOpacity=".08"/><stop offset="1" stopColor="#9b5cff" stopOpacity="0"/></radialGradient>
        </defs>
        <ellipse cx="350" cy="212" rx="285" ry="155" fill={`url(#${core})`}/>
        <g className={styles.engineGrid} stroke={`url(#${spectrum})`} fill="none">
          {Array.from({length:9},(_,i)=><path key={i} d={`M${110+i*40} 110 L${-35+i*40} 295 M${205+i*40} 95 L${660+i*40} 310`}/>)}
          <ellipse cx="350" cy="235" rx="206" ry="69"/><ellipse cx="350" cy="235" rx="224" ry="76" strokeDasharray="2 14"/>
        </g>
        <g className={styles.fibers} fill="none" stroke={`url(#${spectrum})`}>
          {Array.from({length:30},(_,i)=>{
            const y=30+i*10, waist=176+(i-15)*1.95;
            const path=`M-35 ${y} C120 ${y-36},180 ${waist},287 ${waist} M414 ${waist} C505 ${waist},575 ${y+24},735 ${y}`;
            return <g key={i}><path d={path} className={styles.fiberTrack} opacity={.13+(i%4)*.035}/><path d={path} pathLength="1000" className={styles.fiberPulse} style={{"--delay":`${-i*.37}s`,"--duration":`${3.8+(i%5)*.32}s`} as CSSProperties}/></g>;
          })}
        </g>
        <g className={styles.processor}>
          {[3,2,1,0].map(layer=><g key={layer} className={styles.processorLayer} style={{"--layer":layer} as CSSProperties} data-active={step===layer}>
            <path d="M250 169 L350 117 L450 169 L350 221 Z" fill={`url(#${glass})`} stroke="#749cb07a"/>
            <path d="M250 169V180L350 233V221Z" fill="#132127" stroke="#46667b55"/><path d="M350 221L450 169V180L350 233Z" fill="#10111b" stroke="#4e476555"/>
            <path className={styles.layerEdge} d="M250 169L350 221L450 169" fill="none" stroke={`url(#${spectrum})`}/>
            {[0,1,2,3,4,5,6,7].map(n=><path key={n} d={`M${362+n*10} ${220-n*5.2} v4`} stroke={layer===step?"#00e5ff":"#415163"} strokeWidth="2"/>)}
          </g>)}
          <g className={styles.coreGlyph} fill="none" stroke={`url(#${spectrum})`} strokeWidth="3" strokeLinejoin="round">
            <path d="M306 148L350 125L394 148L350 171Z M317 149L350 132L383 149L350 166Z"/>
            <path d="M330 147L350 137L370 147L350 158Z"/>
            <path d="M338 148L350 142L362 148L350 154Z" fill="#00e5ff" stroke="none"/>
          </g>
        </g>
        <g className={styles.sourcePins} stroke={`url(#${spectrum})`} fill="#080d15">
          {[[102,116],[124,244],[585,108],[579,269]].map(([x,y],i)=><g key={i}><path d={`M${x-8} ${y}l8 -4 8 4 -8 4Z`}/><circle className={styles.pinPulse} cx={x} cy={y} r="15" fill="none" style={{animationDelay:`${-i*1.1}s`}}/><circle cx={x} cy={y} r="2" fill={i<2?"#a3ff12":"#9b5cff"}/></g>)}
        </g>
      </svg>
      <div className={styles.sourceLabel}><i/>{language==="zh"?"多源证据":"SOURCE EVIDENCE"}<small>INPUT / 01</small></div>
      <div className={styles.resultLabel}><i/>{language==="zh"?"可溯结论":"TRACEABLE FINDING"}<small>OUTPUT / 04</small></div>
    </div>
    <div className={styles.stageReadout} key={`${language}-${step}`}><span className={styles.stageNumber}>0{step+1}</span><div><span>{t[step].tag}</span><h5>{t[step].title}</h5><p>{t[step].lines[0]}</p></div><span className={styles.stageStatus}><i/>{t[step].status}</span></div>
    <div ref={progressRef} className={styles.stepControls} role="group" aria-label={language==="zh"?"选择证据链演示阶段":"Choose evidence-chain stage"}>{t.map((scene,index)=><button type="button" aria-pressed={step===index} key={index} onClick={()=>selectStep(index)}><span>0{index+1}</span>{scene.label}<i aria-hidden="true"/></button>)}</div>
    <div className={styles.sceneFooter}><span>{language==="zh"?"流程示意 · 非投资结论":"ILLUSTRATIVE WORKFLOW · NOT A FINDING"}</span><span>FACT ≠ CAUSALITY</span></div>
  </div>;
}
