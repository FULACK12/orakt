export function pathGeometry(chains,selected,language,{logistics=true,risks=true,query='',branch='all',activeId=''}={}){
 const features=[];
 for(const c of chains.filter(c=>selected.includes(c.id))){
  const nodes=c.nodes.filter(n=>Array.isArray(n.coordinates)&&n.coordinates.every(Number.isFinite));
  const inBranch=e=>c.id!=='hormuz-helium'||branch==='all'||e.branch===branch||e.branch==='shared';
  const byId=new Map(nodes.map(n=>[n.id,n]));
  const matched=new Set(nodes.filter(n=>!query||[n.zh,n.en,...(n.sites||[]).map(s=>s.relatedCompanyName+' '+s.relatedTicker)].join(' ').toLowerCase().includes(query.toLowerCase())).map(n=>n.id));
  const edges=c.edges||nodes.slice(1).map((n,i)=>({from:nodes[i].id,to:n.id,kind:'hypothesis'}));
  const visibleEdges=edges.filter(e=>inBranch(e)&&(logistics||e.kind!=='logistics')&&(!query||matched.has(e.from)||matched.has(e.to)));
  const shown=new Set([...matched,...visibleEdges.flatMap(e=>[e.from,e.to])]);
  for(const n of nodes){if(!shown.has(n.id)||(!logistics&&n.kind==='port')||(c.id==='hormuz-helium'&&branch!=='all'&&n.branch!==branch&&n.branch!=='shared'&&!visibleEdges.some(e=>e.from===n.id||e.to===n.id)))continue;
   features.push({type:'Feature',geometry:{type:'Point',coordinates:n.coordinates},properties:{id:n.id,chain:c.id,active:n.id===activeId,color:c.id==='hormuz-helium'?(n.branch==='energy'?'#ffb867':n.branch==='buffers'?'#b0ef4a':'#67dce8'):n.kind==='port'?'#49dbe8':n.contextOnly?'#b49cff':c.color,label:n[language]||n.id,count:n.sites?.length||1,risk:Boolean(risks&&(n.disaster||n.conflict)),kind:n.kind||'context'}});
  }
  for(const e of visibleEdges){const a=byId.get(e.from),b=byId.get(e.to);if(!a||!b)continue;
   features.push({type:'Feature',geometry:{type:'LineString',coordinates:e.coordinates||[a.coordinates,b.coordinates]},properties:{chain:c.id,status:e.status||'hypothesis',color:c.id==='hormuz-helium'?(e.branch==='energy'?'#ffb867':e.branch==='buffers'?'#b0ef4a':'#67dce8'):e.kind==='logistics'?'#49dbe8':c.color,kind:e.kind,from:e.from,to:e.to}});
  }
 }
 return {type:'FeatureCollection',features};
}
