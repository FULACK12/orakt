export default function DossierAccountingSummary({dossier,language}:{dossier:any;language:'zh'|'en'}){
 const zh=language==='zh',ratios=(dossier.ratioChecks||[]).filter((r:any)=>r.metric==='gross_margin');
 const n=(v:string)=>new Intl.NumberFormat(zh?'zh-CN':'en-US',{maximumFractionDigits:2}).format(Number(v));
 if(!ratios.length)return null;
 return <section className="report-section"><h2>{zh?'比例复核：毛利额不等于毛利率':'Ratio check: gross profit is not gross margin'}</h2>
  {ratios.map((r:any,i:number)=><div key={i}><p>{zh?'毛利率＝同期间毛利额 ÷ 营业收入。':'Gross margin = gross profit / revenue for the same period.'}</p><p>{zh?'本期':'Current'} {n(r.currentPercent)}% · {zh?'上期':'Prior'} {n(r.previousPercent)}% · {zh?'变化':'Change'} {n(r.changePercentagePoints)} {zh?'个百分点':'percentage points'}</p><small>{r.evidence_refs.join(' · ')}</small></div>)}
  <p>{zh?'毛利额可以上升而毛利率下降；以下九章已经按这一差别复核。报表核对不等于盈利预测已验证。':'Gross profit can rise while gross margin falls. The chapters distinguish these measures; accounting checks are not validation of investment profitability.'}</p>
 </section>;
}
