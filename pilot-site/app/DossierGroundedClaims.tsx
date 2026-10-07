type Claim = {passage_id:string;quote:string;statement:{zh:string;en:string}};
export default function DossierGroundedClaims({chapter,dossier,language}:{chapter:any;dossier:any;language:'zh'|'en'}){
 const claims:Claim[]=chapter.grounded_claims||[];
 if(!claims.length)return null;
 const zh=language==='zh';
 const source=dossier.sources?.find((s:any)=>chapter.evidence_refs.includes(s.id));
 const sourceUrl=typeof source?.url==='string'&&source.url.startsWith('https://www.sec.gov/')?source.url:undefined;
 return <details className="dossier-grounded-claims">
  <summary>{zh?`原文与逐项核验 · ${claims.length} 条引用`:`Source text & claim checks · ${claims.length} citations`}</summary>
  <p role="note">{zh?'原文引用匹配已经校验；下方解读经助手复审，但引用存在不等于因果关系成立。英文原文保持不变。':'Quotation matches have been checked. Interpretations are assistant-reviewed, but a matching citation does not establish causation. Original English text is preserved.'}</p>
  {claims.map((claim,i)=><article key={`${claim.passage_id}-${i}`}>
   <h4>{zh?'逐项解读':'Reviewed interpretation'} {i+1}</h4>
   <p>{claim.statement[language]}</p>
   <small>{zh?'资料截止':'Information cutoff'} {dossier.asOf}</small><details className="technical-reference"><summary>{zh?'技术编号':'Technical reference'}</summary><code>{claim.passage_id}</code></details>
   <blockquote lang="en">{claim.quote}</blockquote>
   {sourceUrl&&<a href={sourceUrl} target="_blank" rel="noopener noreferrer">{zh?'查看 SEC 原始文件':'Read original SEC filing'} ↗</a>}
  </article>)}
 </details>;
}
