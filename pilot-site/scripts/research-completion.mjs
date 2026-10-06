export function validateCompletion(data,report){
 if(data.ticker!==report.ticker||data.asOf!==report.dataCutoff||data.changesReportConfidence!==false)throw Error('Completion identity mismatch');
 const b=data.cashFlowBridge;
 if(b?.ticker!==data.ticker||b.asOf!==data.asOf||b.unit!=='USD'||b.reconciled!==true||b.periodType!=='nine_month_cumulative'||!b.rows?.length||b.totals?.length!==2||! /^[a-f0-9]{64}$/.test(b.sourceDocumentHash||''))throw Error('Invalid cash-flow bridge');
 const num=v=>{if(v===null||v===undefined||v===''||!Number.isFinite(Number(v)))throw Error('Missing number');return Number(v);};
 const concepts=new Set();
 for(const r of b.rows){
  if(concepts.has(r.concept)||![1,-1].includes(r.sign)||r.facts?.length!==2)throw Error('Duplicate bridge line or invalid sign');concepts.add(r.concept);
  for(const [i,k] of ['current','previous'].entries()){
   const f=r.facts[i],total=b.totals[i];
   if(f.unit!==b.unit||f.period_start!==total.period_start||f.period_end!==total.period_end||f.filed_at>data.asOf||num(f.value)*r.sign!==num(r[k]))throw Error('Bridge sign/period mismatch');
  }
  if(num(r.current)-num(r.previous)!==num(r.contributionChange))throw Error('Contribution mismatch');
 }
 for(const [i,k] of ['current','previous'].entries())if(b.rows.reduce((v,r)=>v+num(r[k]),0)!==num(b.totals[i].value)||num(b.residuals?.[i])!==0)throw Error('Unreconciled bridge');
 for(const c of data.comparators||[]){
  if(c.filedAt&&c.filedAt>data.asOf||c.rankingEligible!==false)throw Error('Future or unapproved peer ranking');
  for(const f of c.metrics||[]){
   const days=(Date.parse(f.period_end)-Date.parse(f.period_start))/86400000+1;if(!(days>=70&&days<=110)||f.period_end!==c.periodEnd||f.filed_at>data.asOf||f.unit!=='USD')throw Error('Peer period/unit mismatch');num(f.value);
   if(f.derivation){
    const d=f.derivation,[a,y]=d.operands||[],allowed=['RevenueFromContractWithCustomerExcludingAssessedTax','OperatingIncomeLoss','NetIncomeLoss'];
    if(d.method!=='annual_minus_nine_months'||d.accountingBasis!=='reviewed_consolidated_US_GAAP'||!a||!y||!allowed.includes(f.concept))throw Error('Unreviewed quarter derivation');
    for(const op of [a,y])if(op.issuer!==c.ticker||op.concept!==f.concept||op.unit!==f.unit||op.filed_at>data.asOf||Object.keys(op.dimensions||{}).length||! /^[a-f0-9]{64}$/.test(op.sourceDocumentHash||''))throw Error('Derived operand mismatch');
    const duration=o=>(Date.parse(o.period_end)-Date.parse(o.period_start))/86400000+1;
    if(a.period_start!==y.period_start||a.period_end!==f.period_end||Date.parse(f.period_start)!==Date.parse(y.period_end)+86400000||duration(a)<345||duration(a)>385||duration(y)<250||duration(y)>295||num(a.value)-num(y.value)!==num(f.value))throw Error('Quarter subtraction mismatch');
    if(d.crossCheck?.basis!=='quarterly GAAP'||d.crossCheck?.filedAt>data.asOf||num(d.crossCheck?.reportedValue)!==num(f.value))throw Error('Official quarterly cross-check mismatch');
   }else if(c.status==='quarter_metrics_derived_verified')throw Error('Missing derivation');
  }
 }
 return data;
}
