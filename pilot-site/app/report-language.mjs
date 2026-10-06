/** Body localization uses immutable generated variants, never UI-only relabeling. */
export function localizeReport(report,language){
 if(!report)return null;
 const translated=language==='en'?report.translations?.en:null;
 const merge=(a,b)=>Array.isArray(b)?b.map((v,i)=>typeof v==='object'&&v?merge(a?.[i]||{},v):v):b&&typeof b==='object'?Object.fromEntries(Object.entries({...a,...b}).map(([k,v])=>[k,k in b?merge(a?.[k],b[k]):v])):b;
 return translated?merge(report,translated):report;
}
