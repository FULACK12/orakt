"use client";
import {useState} from 'react';
import useResearchData from './useResearchData';
import FinancialPeriodLedger from './FinancialPeriodLedger';
function Records({language}:{language:'zh'|'en'}){
 const zh=language==='zh',{data,error}=useResearchData('/api/disclosure-reviews'),[id,setId]=useState('');
 const report=data?.reports.find((r:any)=>r.id===id)||data?.reports[0];
 if(error)return <p role="alert">{error}</p>;
 if(!data)return <p role="status">{zh?'读取披露核验记录…':'Loading disclosure reviews…'}</p>;
 return <><p>{data.reports.length} {zh?'份披露证据核验记录；不是新增完整九章研究报告。历史补全仍在进行。':'disclosure evidence reviews; not new complete nine-chapter research dossiers. Historical backfill is incomplete.'}</p><label>{zh?'公司与原始披露版本':'Company and original filing'}<select value={report?.id||''} onChange={e=>setId(e.target.value)}>{data.reports.map((r:any)=><option key={r.id} value={r.id}>{r.ticker} · {r.filedAt} · {r.form} · {r.id.replace('filing-','')}</option>)}</select></label>{report&&<article><h3>{report.ticker} · {report.name} · {report.form}</h3><p>{report.summary[language]}</p><p><a href={report.sourceUrl} target="_blank" rel="noreferrer">{zh?'原始申报 ↗':'Original filing ↗'}</a> · {zh?'披露日期':'Filed'} {report.filedAt} · {zh?'财务期末':'Period end'} {report.periodEnd}</p><details><summary>{zh?'原文 SHA-256':'Source SHA-256'}</summary><code className="study-fingerprint">{report.sourceHash}</code></details><FinancialPeriodLedger language={language} ledger={{comparisons:report.comparisons,excluded:report.issues,accountingRules:[]}}/><h3>{zh?'尚未解决的研究缺口':'Research gaps remaining'}</h3><ul>{report.gaps[language].map((gap:string)=><li key={gap}>{gap}</li>)}</ul></article>}</>;
}
export default function DisclosureReviews({language}:{language:'zh'|'en'}){
 const [open,setOpen]=useState(false),zh=language==='zh';
 return <section className="orakt-ops disclosure-reviews"><span className="eyebrow">DISCLOSURE → EVIDENCE</span><h2>{zh?'一份披露，一份核验记录。':'One disclosure. One evidence review.'}</h2><p>{zh?'从有原文和财务事实的最早披露开始逐家公司核对。保留原始期间、单位与证据链接，数值变化由程序计算；不让模型凭空补齐投资结论。':'Review companies from their earliest retained filings with source text and financial facts. Preserve original periods, units and links; compute changes rather than invent investment conclusions.'}</p><button aria-expanded={open} onClick={()=>setOpen(!open)}>{open?(zh?'收起披露核验':'Hide disclosure reviews'):(zh?'查验公司披露':'Inspect company disclosures')}</button>{open&&<Records language={language}/>}</section>;
}
