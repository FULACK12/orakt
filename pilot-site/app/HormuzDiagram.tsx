"use client";
export const branchLabels={helium:{zh:'氦气供应',en:'Helium supply'},energy:{zh:'能源成本',en:'Energy costs'},buffers:{zh:'缓冲替代',en:'Buffers'}};
export default function HormuzDiagram({network,language,onSelect,compact=false}:{network:any;language:'zh'|'en';onSelect?:(n:any)=>void;compact?:boolean}){
 const zh=language==='zh';
 const rows=[{id:'helium',nodes:['ras','hormuz','purity','process','cost']},{id:'energy',nodes:['hormuz','lng','power','cost']},{id:'buffers',nodes:['singapore','buffer','cost']}];
 return <div className={'hormuz-diagram'+(compact?' compact':'')}><div className="hormuz-diagram-caption">{zh?'三条分支 · 箭头均为待检验传导，不是已确认供货':'Three branches · arrows are testable mechanisms, not confirmed supply'}</div>{rows.map(row=><section key={row.id} data-branch={row.id}><h3>{branchLabels[row.id as keyof typeof branchLabels][language]}</h3><ol>{row.nodes.map(id=>{const n=network.nodes.find((n:any)=>n.id===id);return <li key={id}><button onClick={()=>onSelect?.(n)} disabled={!onSelect}><span>{n[language]}</span><small>{n.status==='hypothesis'?(zh?'推演':'Hypothesis'):n.status==='conditional_buffer'?(zh?'有条件缓冲':'Conditional buffer'):(zh?'来源背景':'Sourced context')}</small></button></li>;})}</ol></section>)}<p className="hormuz-terminal">↓ {zh?'损益归因 → 估值检查 → 投资设想（未验证）':'Earnings attribution → valuation checks → investment thesis (unvalidated)'}</p></div>;
}
