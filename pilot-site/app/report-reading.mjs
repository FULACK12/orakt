// Presentation-only citation numbering. Never edits retained reports, quotes or hashes.
const passagePattern=/PASSAGE:[a-zA-Z0-9_-]+/g;
const rawFields=new Set(['id','url','sourceUrl','quote','originalQuote','originalPassages','passage_id','evidence_refs','evidence_id','sources','facts','translations','provenance','wholeReportAudit','financialLedger','cashBridge']);
export function readingReferences(report){
 const found=new Set();
 const collect=(value,key='')=>{if(rawFields.has(key))return;if(typeof value==='string')for(const id of value.match(passagePattern)||[])found.add(id);else if(Array.isArray(value))value.forEach(v=>collect(v));else if(value&&typeof value==='object')Object.entries(value).forEach(([k,v])=>collect(v,k));};
 collect(report);const ids=[...found].sort();
 const d=report?.dossier||{},quotes=new Map();
 for(const rows of Object.values(d.originalPassages||{}))if(Array.isArray(rows))for(const p of rows)quotes.set(p.id,p.text);
 for(const c of d.chapters||[])for(const p of c.grounded_claims||[])if(!quotes.has(p.passage_id))quotes.set(p.passage_id,p.quote);
 const url=d.sources?.length===1&&/^https:\/\//.test(d.sources[0].url||'')?d.sources[0].url:null;
 return ids.map((id,i)=>({id,number:i+1,quote:quotes.get(id)||null,url}));
}
export function readableEvidenceText(value,refs,language){
 if(typeof value!=='string')return value;
 const label=id=>{const n=refs.find(r=>r.id===id)?.number;return n?`${language==='zh'?'证据':'Ref'} ${n}`:(language==='zh'?'原始证据':'Source reference')};
 return value.replace(/\[((?:\s*PASSAGE:[a-zA-Z0-9_-]+\s*[,;，；]?)+)\]/g,(_,group)=>'〔'+(group.match(passagePattern)||[]).map(label).join(' · ')+'〕').replace(passagePattern,id=>'〔'+label(id)+'〕');
}
export function reportForReading(report,language){
 if(!report)return null;
 const refs=readingReferences(report);
 const visit=(value,key='')=>rawFields.has(key)?value:typeof value==='string'?readableEvidenceText(value,refs,language):Array.isArray(value)?value.map(v=>visit(v)):value&&typeof value==='object'?Object.fromEntries(Object.entries(value).map(([k,v])=>[k,visit(v,k)])):value;
 return {...visit(report),readingReferences:refs};
}
