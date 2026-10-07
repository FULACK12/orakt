// Never show another company or later filings beside a historical report.
export function reportChartMetrics(metrics, {asOf,periodEnd}={}) {
 const result={};
 for(const [key,points] of Object.entries(metrics||{}))result[key]=points.filter(p=>Number.isFinite(p.value)&&(!periodEnd||p.end<=periodEnd)&&(!asOf||(p.filedAt&&p.filedAt.slice(0,10)<=asOf.slice(0,10))));
 return result;
}
