export function portfolioStats(rows) {
  const valid = rows.length > 0 && rows.every(r => Number.isFinite(r.weight) && r.weight >= 0 && r.weight <= 100 && Number.isFinite(r.shock) && r.shock >= -100 && r.shock <= 100 && /^[A-Z0-9.:-]{1,24}$/.test(r.symbol)) && new Set(rows.map(r=>r.symbol)).size === rows.length;
  const total = rows.reduce((a,r)=>a+r.weight,0);
  const ready = valid && Math.abs(total-100)<0.001;
  const hhi = rows.reduce((a,r)=>a+(r.weight/100)**2,0);
  return {total,ready,maxWeight:Math.max(0,...rows.map(r=>r.weight)),effectivePositions:ready&&hhi?1/hhi:null,scenario:ready?rows.reduce((a,r)=>a+r.weight*r.shock/100,0):null};
}
