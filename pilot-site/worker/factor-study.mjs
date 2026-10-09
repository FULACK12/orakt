// Fixed specification, no parameter search. Prices are retained closes, not certified total returns.
export const specification = Object.freeze({id:'ORAKT-TSM252-AAPL-v1',lookback:252,rebalance:'last_common_session_of_month',execution:'following_common_session_close',side:'long_or_cash',oneWayCostBps:12,split:'2022-01-01',cashRate:0,annualSessions:252});
export function alignPrices(assets){
 const keys=['EQ:AAPL','TD:SPY','TD:XLK'];
 const maps=keys.map(k=>{const rows=assets[k]?.points;if(!rows?.length)throw Error('Missing '+k);const m=new Map();for(const [date,p] of rows){if(!/^\d{4}-\d{2}-\d{2}$/.test(date)||!Number.isFinite(p)||p<=0||m.has(date))throw Error('Invalid or duplicate price '+k);m.set(date,p);}return m;});
 const rows=[...maps[0].keys()].filter(d=>maps.every(m=>m.has(d))).sort().map(date=>({date,stock:maps[0].get(date),market:maps[1].get(date),industry:maps[2].get(date)}));
 if(rows.length<300)throw Error('Insufficient aligned history');
 return rows;
}
export function runFactor(rows,{start=rows[252]?.date,end=rows.at(-1)?.date,costBps=12}={}){
 if(!Number.isFinite(costBps)||costBps<0||costBps>=10000)throw Error('Invalid cost');
 const indices=rows.map((r,i)=>i>=252&&r.date>=start&&r.date<=end?i:-1).filter(i=>i>=0);
 if(indices.length<2)throw Error('Insufficient segment');
 const first=indices[0],last=indices.at(-1),base=rows[first],nav={strategy:100,stock:100,market:100,industry:100};
 let position=0,peak=100,invested=0,turnover=0;const trades=[],returns=[],points=[{date:base.date,...nav,drawdown:0,position:0}];
 for(let i=first+1;i<=last;i++){
  const r=rows[i],prev=rows[i-1],before=nav.strategy;invested+=position;
  nav.strategy*=1+position*(r.stock/prev.stock-1);
  for(const k of ['stock','market','industry'])nav[k]*=r[k]/prev[k];
  // Signal is known at t close; the old holding earns t→t+1; change only at t+1 close.
  if(i-1>=252&&prev.date.slice(0,7)!==r.date.slice(0,7)){
   const signal=prev.stock/rows[i-253].stock-1,target=Number(signal>0);
   if(target!==position){nav.strategy*=1-costBps/10000;turnover++;trades.push({signalDate:prev.date,executionDate:r.date,signal,from:position,to:target,costBps,reason:'monthly_signal'});position=target;}
  }
  if(i===last&&position){nav.strategy*=1-costBps/10000;turnover++;trades.push({signalDate:null,executionDate:r.date,signal:null,from:1,to:0,costBps,reason:'terminal_liquidation'});position=0;}
  peak=Math.max(peak,nav.strategy);returns.push(nav.strategy/before-1);points.push({date:r.date,...nav,drawdown:100*(nav.strategy/peak-1),position});
 }
 const years=(Date.parse(rows[last].date)-Date.parse(base.date))/86400000/365.25,mean=returns.reduce((a,b)=>a+b,0)/returns.length;
 const stats={netReturnPercent:nav.strategy-100,cagrPercent:100*((nav.strategy/100)**(1/years)-1),maxDrawdownPercent:Math.min(...points.map(p=>p.drawdown)),volatilityPercent:100*Math.sqrt(252*returns.reduce((s,r)=>s+(r-mean)**2,0)/(returns.length-1)),exposurePercent:100*invested/returns.length,turnover,sessions:returns.length,stockReturnPercent:nav.stock-100,marketReturnPercent:nav.market-100,industryReturnPercent:nav.industry-100,excessMarketPP:nav.strategy-nav.market,excessIndustryPP:nav.strategy-nav.industry};
 const yearly=[];let previous=points[0];for(let i=1;i<points.length;i++){if(i===points.length-1||points[i].date.slice(0,4)!==points[i+1].date.slice(0,4)){const p=points[i];yearly.push({year:p.date.slice(0,4),start:previous.date,end:p.date,strategy:100*(p.strategy/previous.strategy-1),stock:100*(p.stock/previous.stock-1),market:100*(p.market/previous.market-1),industry:100*(p.industry/previous.industry-1)});previous=p;}}
 return {start:base.date,end:rows[last].date,costBps,stats,points,trades,yearly};
}
