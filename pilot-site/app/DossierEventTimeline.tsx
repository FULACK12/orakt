export default function DossierEventTimeline({dossier,language}:{dossier:any;language:'zh'|'en'}){
 const zh=language==='zh';
 const events=dossier.eventTimeline||[];
 if(!events.length)return null;
 const recognition:Record<string,string>=zh?{disclosed_transaction:'已披露交易',expected_charge:'预期费用 · 非已实现损失',expected_benefit:'预期税务收益 · 非当季利润'}:{disclosed_transaction:'Disclosed transaction',expected_charge:'Expected charge · not realized loss',expected_benefit:'Expected tax benefit · not current-quarter profit'};
 return <section className="report-section dossier-event-timeline" aria-labelledby="dossier-timeline-title">
  <h2 id="dossier-timeline-title">{zh?'事件时间线与会计期间边界':'Event timeline & accounting-period boundaries'}</h2>
  <p>{zh?`财季截止 ${dossier.periodEnd}，研究信息截止 ${dossier.asOf}。季后事项可以进入风险分析，但不得直接算入当季已实现业绩。`:`Quarter ended ${dossier.periodEnd}; research cutoff ${dossier.asOf}. Later disclosed events may inform risk analysis but are not automatically part of realized quarterly results.`}</p>
  <p><small>{zh?'下列来源日期为本次引用文件的提交日期，不代表事件首次公开日期。':'Source dates below are the filing dates of the cited document, not necessarily the first public disclosure.'}</small></p>
  <ol>{events.map((e:any)=><li key={e.id}>
   <div><time dateTime={e.eventDate}>{e.eventDate}</time><span>{e.periodRelation==='within_report_period'?(zh?'报告期内':'Within report period'):(zh?'季后 · 截止日前已知':'Post-period · known by cutoff')}</span></div>
   <h3>{e.title[language]}</h3><small>{recognition[e.recognition]}</small>
   <p>{e.interpretation[language]}</p>
   <a href={e.sourceUrl} target="_blank" rel="noopener noreferrer">{e.evidenceRef} · {zh?'文件提交':'Filed'} {e.sourceFiledAt}</a>
  </li>)}</ol>
 </section>;
}
