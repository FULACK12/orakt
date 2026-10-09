"use client";
import {useEffect,useMemo,useState,type ReactNode} from 'react';
import {hormuzChain} from './chain-catalog';
import useResearchData from './useResearchData';
import {localizeReport} from './report-language.mjs';
import {reportForReading} from './report-reading.mjs';
import ReportEvidence from './ReportEvidence';
import WorkspaceAccess from './WorkspaceAccess';
import EnglishEvidenceDigest from './EnglishEvidenceDigest';
import AppleResearch from './AppleResearch';
import HormuzResearch from './HormuzResearch';
export function ChainProtocol({language}:{language:'zh'|'en'}){const zh=language==='zh';return <section className="chain-protocol"><header><span className="eyebrow">RESEARCH PROTOCOL / 05 CHECKS</span><h2>{zh?'一条链，五道检查。':'One path. Five checks.'}</h2><p>{zh?'这是查验框架，不表示下面的链条已经全部通过。缺失项保持未知，不由模型补成事实。':'A review framework, not a claim that every path has passed. Missing evidence remains unknown.'}</p></header><ol>{[['01','事件','Event','何时发生？原始来源是什么？','When did it happen? What is the primary source?'],['02','机制','Mechanism','为何会传导？每一步是否有支持？','Why would it transmit? Is each link supported?'],['03','指标','Observations','看什么数据？窗口与单位是否一致？','Which series? Are windows and units aligned?'],['04','反证','Alternatives','什么会削弱结论？其他原因更强吗？','What weakens the claim? Are alternatives stronger?'],['05','判断','Assessment','已知、推断、缺口与下一步分别是什么？','Separate facts, inference, gaps and next checks.']].map(([n,cn,en,c,e])=><li key={n}><b>{n}</b><h3>{zh?cn:en}</h3><p>{zh?c:e}</p></li>)}</ol></section>;}
export function ChainRoute({nodes,language}:{nodes:any[];language:'zh'|'en'}){
 return <ol className="chain-route" aria-label={language==='zh'?'传导路径':'Transmission path'}>{nodes.map((n,i)=><li key={i}><span>{String(i+1).padStart(2,'0')}</span><p>{n[language]}</p></li>)}</ol>;
}
function ArchivedChain({id,language:interfaceLanguage,renderReport}:{id:string;language:'zh'|'en';renderReport:(r:any,l:'zh'|'en')=>ReactNode}){
 const [choice,setChoice]=useState<'zh'|'en'|null>(null),language=choice||interfaceLanguage;
 const {data,error}=useResearchData('/api/evidence-chain?id='+encodeURIComponent(id)),zh=language==='zh',[expanded,setExpanded]=useState(false);
 const r=useMemo(()=>data?.report?reportForReading(localizeReport(data.report,language),language):null,[data?.report,language]);
 if(error)return <p role="alert">{error}</p>;
 if(!r)return <p role="status">{zh?'读取链条…':'Loading chain…'}</p>;
 return <article className="chain-detail">
  <span className="eyebrow">{r.ticker||'ORAKT'} / {zh?'五维与多维证据研究':'Multidimensional evidence research'}</span>
  <h1>{!zh&&!r.translations?.en&&!r.dossier?`${r.ticker||'Global'} · Evidence-chain research`:r.question}</h1>
  <div className="chain-language" role="group" aria-label="Report language"><button aria-pressed={zh} onClick={()=>setChoice('zh')}>中文完整报告</button><button aria-pressed={!zh} onClick={()=>setChoice('en')}>{r.translations?.en||r.dossier?'English report':'English evidence digest'}</button></div>
  <p>{zh?'保留原报告、原始来源与核验状态。移动栏目不表示重新验证；箭头表示研究路径，不等于因果关系成立。':'Original report, sources and review status are retained. Reclassification is not revalidation; arrows express hypotheses, not established causality.'}</p>
  <dl className="chain-report-meta"><div><dt>{zh?'证据截止':'Evidence cutoff'}</dt><dd>{r.dataCutoff||r.historical?.asOf||'—'}</dd></div><div><dt>{zh?'实际生成':'Generated'}</dt><dd>{r.createdAt||'—'}</dd></div><div><dt>{zh?'原审核状态':'Original review'}</dt><dd>{r.audit?.status||'—'}</dd></div></dl>
  <ChainRoute nodes={(r.chain||[]).map((n:any,i:number)=>({zh:n.title,en:r.translations?.en?n.title:`Step ${i+1} · ${n.status||'unclassified'}`}))} language={language}/>
  <ChainProtocol language={language}/>
  <section className="chain-full-report">
   <button className="chain-more" aria-expanded={expanded} onClick={()=>setExpanded(v=>!v)}>{expanded?(zh?'收起完整报告':'Collapse full report'):(zh?'展开完整研究报告':'Expand full research report')} <small>{zh?'正文 · 财务与技术图表 · 五维推演 · 来源与反证':'Narrative · financial and technical charts · mechanisms · sources'}</small></button>
   {expanded&&<div className="evidence-report chain-report-body" key={r.id}>{!zh&&!r.translations?.en&&!r.dossier?<EnglishEvidenceDigest report={r}/>:renderReport(r,language)}</div>}
  </section>
  {!expanded&&(zh||r.translations?.en||r.dossier?<ReportEvidence report={r} language={language}/>:<EnglishEvidenceDigest report={r}/>)}
 </article>;
}
function ChainList({language}:{language:'zh'|'en'}){
 const zh=language==='zh',{data,error}=useResearchData('/api/evidence-chain-index'),[limit,setLimit]=useState(12),[query,setQuery]=useState('');
 const chains=(data?.chains||[]).filter((r:any)=>[r.ticker,r.date,r.title?.[language],...(r.nodes||[]).map((n:any)=>n[language])].join(' ').toLowerCase().includes(query.trim().toLowerCase()));
return <><WorkspaceAccess tier={data?.tier} language={language}/><section className="chain-feature apple-study-feature"><small>AAPL / GLOBAL SUPPLY ATLAS</small><a href="/platform/chains?chain=apple-network"><h2>{zh?'苹果 · 五维与多维证据研究':'Apple · multidimensional evidence research'}</h2><p>{zh?'187 家供应商 · 724 条产地 · 供应、物流、电力、灾害与成本机制':'187 suppliers · 724 locations · supply, logistics, power, hazards & cost mechanisms'}</p><span>{zh?'打开完整双语专题与地图':'Open bilingual study & map'} →</span></a></section><ChainProtocol language={language}/><section className="chain-feature"><small>{zh?'专题研究 · 来源与传导':'Featured research · sources & transmission'}</small><a href="/platform/chains?chain=hormuz-helium"><h2>{hormuzChain.title[language]}</h2><ChainRoute nodes={hormuzChain.nodes.filter(n=>hormuzChain.summaryIds.includes(n.id))} language={language}/><span className="chain-open">{zh?'逐步查看依据与待补证据':'Explore supporting and missing evidence'} →</span></a></section><div className="chain-directory-heading"><h2>{zh?'五维／多维研究与证据链报告':'Multidimensional research & evidence chains'}</h2><label><span>{zh?'搜索公司、关键词或日期':'Search company, keyword or date'}</span><input type="search" value={query} onChange={e=>{setQuery(e.target.value);setLimit(12)}} placeholder={zh?'例如 NVDA、收入、2009':'e.g. NVDA, revenue, 2009'}/></label></div>{data&&<p className="chain-directory-count" role="status">{chains.length} / {data.total} {zh?'条当前可查验 · 原报告状态，非新增核验':'matching paths · original report status, not fresh validation'}</p>}<div className="chain-list">{chains.slice(0,limit).map((r:any)=><article key={r.id}><small>{r.ticker||'GLOBAL'} · {r.date}</small><a href={'/platform/chains?report='+encodeURIComponent(r.id)}><h3>{r.title[language]}</h3><ChainRoute nodes={r.nodes||[]} language={language}/><span className="chain-open">{zh?'打开链条并展开完整报告':'Open chain & expand full report'} →</span></a></article>)}</div>{error&&<p role="alert">{error}</p>}{!data&&!error&&<p role="status">{zh?'加载已有链条目录…':'Loading retained chain index…'}</p>}{data?.tier==='explorer'&&<WorkspaceAccess tier={data.tier} language={language} locked/>}{data&&data.tier!=='explorer'&&!chains.length&&<p>{zh?'没有符合条件的链条，请尝试公司代码或缩短关键词。':'No matching paths. Try a ticker or a shorter keyword.'}</p>}{chains.length>limit&&<button className="chain-more" onClick={()=>setLimit(v=>v+12)}>{zh?'显示更多路径':'Show more paths'}</button>}</>;
}
export default function EvidenceChains({language,onMap,renderReport}:{language:'zh'|'en';onMap:()=>void;renderReport:(r:any,l:'zh'|'en')=>ReactNode}){
 const [apple,setApple]=useState(false);
 useEffect(()=>{setApple(new URLSearchParams(window.location.search).get('chain')==='apple-network');},[]);
 const zh=language==='zh',[detail,setDetail]=useState<{id:string;scenario:boolean}|null>(null);
 useEffect(()=>{const q=new URLSearchParams(window.location.search);setDetail({id:q.get('report')||'',scenario:q.get('chain')==='hormuz-helium'});},[]);
 if(!detail)return <p role="status">{zh?'读取导航…':'Loading…'}</p>;
 if(apple)return <section className="chain-workspace"><a className="chain-back" href="/platform/chains">← {zh?'全部证据链':'All evidence chains'}</a><AppleResearch language={language}/></section>;
 const inside=detail.scenario||Boolean(detail.id);
 return <section className="chain-workspace">{inside?<a className="chain-back" href="/platform/chains">← {zh?'全部证据链':'All evidence chains'}</a>:<header><span className="eyebrow">ORAKT / CAUSAL RESEARCH</span><h1>{zh?'证据链推演':'Evidence-chain research'}</h1><p>{zh?'先看传导路径，再打开查验依据。每一步都要区分事实、背景和假设；不把时间相关性当作因果证明。':'Start with the transmission path, then inspect the evidence. Distinguish facts, context and hypotheses at every step; timing alone does not prove causality.'}</p></header>}{detail.id?<ArchivedChain id={detail.id} language={language} renderReport={renderReport}/>:detail.scenario?<HormuzResearch language={language}/>:<ChainList language={language}/>}</section>;
}
