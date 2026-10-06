import {createHash} from 'node:crypto';
export function validateSupplement(s,report){
 if(s?.ticker!==report.ticker||s?.asOf!==report.dataCutoff||s?.review?.status!=='arithmetic_checked_narrative_not_replaced'||!/^[a-f0-9]{64}$/.test(s?.sourceDocumentHash||''))throw Error('Supplement identity, cutoff or review mismatch');
 if(!Array.isArray(s.financialLedger?.comparisons)||!s.financialLedger.comparisons.length)throw Error('No financial comparisons');
 for(const r of s.financialLedger.comparisons){
  const a=Number(r.current?.value),b=Number(r.previous?.value);
  if(!Number.isFinite(a)||!Number.isFinite(b)||r.current?.unit!==r.previous?.unit||r.current?.unit!==r.unit||!r.evidence_refs?.length)throw Error('Invalid financial comparison');
  const direction=a>b?'increase':a<b?'decrease':'unchanged';
  if(direction!==r.direction||r.current.period_end!==s.periodEnd||r.previous.period_end>=s.periodEnd)throw Error('Comparison direction or cutoff mismatch');
  if(b>0){if(r.changePercent===null||!Number.isFinite(Number(r.changePercent))||Math.abs(Number(r.changePercent)-(a/b-1)*100)>1e-6)throw Error('Percentage mismatch');}
  else if(r.changePercent!==null)throw Error('Undefined percentage must remain missing');
  if(r.periodType==='instant'){if(r.current.period_start||r.previous.period_start||r.comparisonBasis!=='prior_reported_balance')throw Error('Invalid balance period');}
  else {
   const days=v=>(Date.parse(v.period_end)-Date.parse(v.period_start))/86400000+1;
   const bounds={quarter:[70,110],six_month_cumulative:[165,200],nine_month_cumulative:[250,295],annual:[345,385]}[r.periodType];
   if(!bounds||![days(r.current),days(r.previous)].every(n=>n>=bounds[0]&&n<=bounds[1])||Math.abs(days(r.current)-days(r.previous))>14)throw Error('Quarter/cumulative mismatch');
   for(const boundary of ['period_start','period_end']){const gap=(Date.parse(r.current[boundary])-Date.parse(r.previous[boundary]))/86400000;if(gap<350||gap>380)throw Error('Not a year-over-year comparator');}
  }
 }
 return s;
}
export function sourceDigest(raw){return createHash('sha256').update(raw).digest('hex');}
