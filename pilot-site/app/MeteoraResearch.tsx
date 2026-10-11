"use client";
import {useState} from 'react';
import useResearchData from './useResearchData';
import styles from './MeteoraResearch.module.css';
const address=(key:string)=>`https://explorer.solana.com/address/${key}?cluster=devnet`;
const transaction=(sig:string)=>`https://explorer.solana.com/tx/${sig}?cluster=devnet`;
const short=(s:string)=>s.slice(0,7)+'…'+s.slice(-6);
export default function MeteoraResearch({language}:{language:'zh'|'en'}){
 const zh=language==='zh',t=(a:string,b:string)=>zh?a:b;
 const [refresh,setRefresh]=useState(0),[hashCheck,setHashCheck]=useState('');
 const {data,error}=useResearchData('/api/meteora-research?refresh='+refresh),s=data?.state,d=data?.demo,p=data?.proof;
 const external=(href:string,label:string)=><a href={href} target="_blank" rel="noreferrer">{label} ↗</a>;
 async function verify(){try{const bytes=new TextEncoder().encode(JSON.stringify(d)),hash=await crypto.subtle.digest('SHA-256',bytes);setHashCheck([...new Uint8Array(hash)].map(n=>n.toString(16).padStart(2,'0')).join('')===p.contentHash?'match':'mismatch');}catch{setHashCheck('unavailable');}}
 function download(){const href=URL.createObjectURL(new Blob([JSON.stringify(d)],{type:'application/json'})),a=document.createElement('a');a.href=href;a.download='orakt-meteora-evidence-v1.json';a.click();setTimeout(()=>URL.revokeObjectURL(href),1000);}
 return <section className={styles.panel} aria-labelledby="meteora-title">
  <header className={styles.header}><div><span className={styles.kicker}>ORAKT × METEORA</span><h2 id="meteora-title">{t('让链上市场回到证据','Bring on-chain markets back to evidence')}</h2><p>{t('一个可观察的 DBC 测试池，一份可核对的版本承诺。研究与流动性相连，会员资金保持独立。','An observable DBC test pool, tied to a verifiable version commitment. Research meets liquidity; membership funds stay separate.')}</p></div><span className={styles.badge}>DEVNET · {t('只读','READ ONLY')}</span></header>
  <div className={styles.warning}>{t('OREVTEST 是测试资产，不代表苹果或中国股票；无赎回、分红、美元价值或收益承诺。','OREVTEST is a test asset, not Apple or Chinese shares. No redemption, dividends, dollar valuation or promised returns.')}</div>
  {!data&&!error&&<p role="status">{t('正在读取最终确认的链上状态…','Reading finalized on-chain state…')}</p>}
  {(error||data&&!data.available)&&<p role="alert" className={styles.error}>{t('暂时无法核验 Devnet 状态；不会用模拟余额代替。请稍后重试。','Devnet state cannot be verified right now; no simulated balances are substituted. Please retry shortly.')}</p>}
  {data&&<>
   <div className={styles.route} aria-label={t('研究到流动性关联','Research-to-liquidity link')}><div><small>01 / EVIDENCE</small><b>{t('关联说明 v1','Integration study v1')}</b><span>{t('原文 → SHA-256 → ORAKT 记录','Source → SHA-256 → ORAKT record')}</span></div><i aria-hidden="true">→</i><div><small>02 / DBC</small><b>OREVTEST / Devnet SOL</b><span>{t('已创建测试池 · 不开放交易','Test pool created · no trading interface')}</span></div><i aria-hidden="true">→</i><div><small>03 / DAMM V2</small><b>{s?.migrated?t('链上迁移标志已置位','Migration flag set'):t('待达到毕业条件','Graduation pending')}</b><span>{t('目标配置，不代表迁移已验收','Configured destination, not migration acceptance')}</span></div></div>
   {s&&<><div className={styles.metrics}>
    <div><span>{t('池内报价储备','Pool quote reserve')}</span><strong>{s.quoteReserve}</strong><small>Devnet SOL</small></div>
    <div><span>{t('曲线当前价格','Current curve price')}</span><strong>{s.spotQuotePerBase}</strong><small>SOL / OREVTEST · {t('非成交报价','not executable')}</small></div>
    <div><span>{t('初始基础费率','Initial base fee')}</span><strong>{s.initialBaseFeeBps} <small>bps</small></strong><small>{t('不是当前交易费用或平台收入','Not a current fee quote or platform revenue')}</small></div>
    <div><span>{t('链上证据核对','On-chain evidence check')}</span><strong className={styles.verified}>{s.evidenceVerified?t('哈希匹配','HASH MATCH'):t('未核验','NOT VERIFIED')}</strong><small>{t('一致性 ≠ 事实正确','Consistency ≠ factual truth')}</small></div>
   </div><div className={styles.progress}><div><b>{t('曲线毕业进度','Curve graduation progress')}</b><span>{(s.progressBps/100).toFixed(2)}%</span></div><progress max="10000" value={s.progressBps} aria-label={t('毕业进度','Graduation progress')}/><p>{s.quoteReserve} / {s.migrationQuoteThreshold} Devnet SOL · {t('尚未查验毕业后的 DAMM 池','Graduated DAMM pool not verified')}</p></div></>}
   <div className={styles.actions}>{external(address(d.pool),t('查验 DBC 池','Inspect DBC pool'))}{external(address(p.record),t('查验 ORAKT 存证','Inspect ORAKT record'))}{external(transaction(p.signature),t('查看存证交易','View proof transaction'))}<button type="button" onClick={()=>setRefresh(n=>n+1)}>{t('刷新状态','Refresh state')}</button></div>
   <p className={styles.timestamp}>{t('观测时间','Observed')} {new Date(data.checkedAt).toLocaleString(zh?'zh-CN':'en-US')} · {s?`finalized slot ${s.slot}`:t('数据不可用','unavailable')} · {t('最多缓存 60 秒','cached for up to 60 seconds')}</p>
   <details className={styles.details}><summary>{t('研究说明、参数与可复核证据','Study, parameters & reproducible evidence')}</summary><div className={styles.detailGrid}>
    <article><h3>{t('研究对象与边界','Scope & boundaries')}</h3><p>{t('本报告研究的是 ORAKT 与 Meteora 的技术连接，不是公司估值报告。配置、池和存证已经存在；未进行买卖，也没有证明市场需求或收益。','This study covers the ORAKT–Meteora integration, not a company valuation. The configuration, pool and commitment exist. No swaps were executed; demand and returns are not established.')}</p><p>{t('毕业目标为 DAMM v2。下列比例仅为毕业后配置，不是当前已锁定的 LP 持仓证明。','DAMM v2 is the graduation target. These percentages are post-graduation configuration, not proof of currently locked LP positions.')}</p>{s&&<ul><li>{t('创建者永久锁定配置','Creator permanent-lock allocation')}: {s.configuredCreatorPermanentLockPct}%</li><li>{t('创建者可用配置','Creator liquid allocation')}: {s.configuredCreatorLiquidityPct}%</li><li>{t('合作方永久锁定 / 可用配置','Partner permanent / liquid allocation')}: {s.configuredPartnerPermanentLockPct}% / {s.configuredPartnerLiquidityPct}%</li></ul>}<p>{t('未实现：主网交易、滑点报价、自动迁移、真实股票发行和托管。','Not implemented: mainnet trading, slippage quotes, automated migration, real-share issuance or custody.')}</p></article>
    <article><h3>{t('证据与身份','Evidence & identity')}</h3><dl><dt>DBC program</dt><dd>{external(address(d.program),short(d.program))}</dd><dt>Pool configuration</dt><dd>{external(address(d.config),short(d.config))}</dd><dt>OREVTEST mint</dt><dd>{external(address(d.baseMint),short(d.baseMint))}</dd><dt>SHA-256 / v{p.version}</dt><dd><code>{p.contentHash}</code></dd><dt>Merkle root</dt><dd><code>{p.evidenceRoot}</code></dd></dl><div className={styles.actions}><button type="button" onClick={download}>{t('下载存证原文','Download committed source')}</button><button type="button" onClick={verify}>{t('本地核对原文哈希','Check source hash locally')}</button></div>{hashCheck&&<p role="status">{hashCheck==='match'?t('原文哈希与发布记录匹配；不等于独立事实审核。','Source hash matches the published record; this is not independent fact checking.'):t('无法确认匹配，请勿视为核验通过。','Match not established; do not treat this as verified.')}</p>}{external('https://github.com/MeteoraAg/dynamic-bonding-curve-sdk',t('官方 SDK 与接口来源','Official SDK and interface source'))}</article>
   </div></details>
  </>}
 </section>;
}
