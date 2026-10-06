export function comparableYoY(point, points) {
 const duration=p=>p.start?(Date.parse(p.end)-Date.parse(p.start))/86400000:0;
 const candidates=points.filter(p=>p.basis===point.basis&&p.unit===point.unit&&Date.parse(p.end)<Date.parse(point.end)&&Math.abs((Date.parse(point.end)-Date.parse(p.end))/86400000-365.25)<16&&Math.abs(duration(point)-duration(p))<16);
 if(candidates.length!==1||candidates[0].value<=0)return null;
 return (point.value/candidates[0].value-1)*100;
}
export function ratioPoints(numerators,denominators){return numerators.flatMap(n=>{const d=denominators.filter(p=>p.end===n.end&&p.start===n.start&&p.unit===n.unit);return d.length===1&&d[0].value>0?[{...n,value:n.value/d[0].value*100,unit:'%',sourceUrl:n.sourceUrl,denominatorSource:d[0].sourceUrl}]:[];});}
