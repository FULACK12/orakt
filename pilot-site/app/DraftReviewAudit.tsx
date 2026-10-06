export default function DraftReviewAudit({audit,language}:{audit:any;language:'zh'|'en'}){
 const zh=language==='zh';
 return <section aria-label={zh?'本轮报告审核记录':'This batch review record'}>
  <h3>{zh?'本轮报告审核记录（非实时队列）':'Batch review record (not a live queue)'}</h3>
  <p>{zh?'检查时间':'Checked'}: {audit.checkedAt} · {zh?'生成已停止；下列记录分别标明原稿与修订版状态。':'Generation has stopped; original drafts and revised reports have separate statuses below.'}</p>
  {audit.reports.map((r:any)=><details key={r.ticker}><summary>{r.ticker} · {r.reviewedReportId?(zh?'修订审核完成':'Revision reviewed'):(zh?'审核未通过':'Review blocked')} · {zh?'原始合格结构章节':'Original structurally valid chapters'} {r.retainedChapters}/{r.totalChapters}</summary>
   {r.reviewedReportId&&<p><a href={`/platform/research?report=${encodeURIComponent(r.reviewedReportId)}`}>{zh?`查看修订后的 ${r.reviewedChapters} 章完整报告`:`Read the ${r.reviewedChapters}-chapter revised report`}</a> · {zh?'助手修订，非人工接受':'Assistant revised, not human accepted'}</p>}
   <ul>{r.issues[language].map((s:string)=><li key={s}>{s}</li>)}</ul>
  </details>)}
 </section>;
}
