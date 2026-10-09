// All lines are typed relationships; never infer sequential shipping from array order.
export function appleNetwork(snapshot){
 const grouped=new Map(),ports=new Map(),edges=[];
 for(const s of snapshot.sites){
  if(!s.coordinates)continue;
  const key=s.coordinates.join(',');
  if(!grouped.has(key))grouped.set(key,{id:'apple-region-'+key,coordinates:s.coordinates,kind:'supplier',zh:s.siteName,en:s.siteName,status:'context',sites:[],sources:[]});
  const n=grouped.get(key);n.sites.push(s);
  if(!n.sources.some(x=>x.url===s.sourceUrl))n.sources.push({title:'Supplier location source',url:s.sourceUrl});
  const p=s.nearestPort;
  if(p){const id='apple-port-'+p.longitude+','+p.latitude;
   ports.set(id,{id,kind:'port',coordinates:[p.longitude,p.latitude],zh:p.name,en:p.name,status:'hypothesis',sites:[],sources:[],noteZh:'最近港口参考，不是已确认的采购或运输渠道。',noteEn:'Nearest-port reference, not a confirmed procurement or shipping route.'});
   if(!edges.some(e=>e.from===n.id&&e.to===id))edges.push({from:n.id,to:id,kind:'logistics',status:'hypothesis'});
  }
 }
 const nodes=[...grouped.values()].map(n=>({...n,contextOnly:n.sites.every(s=>s.associationScope==='supplier_facility_not_customer_linked'),zh:n.zh+' · '+n.sites.length,en:n.en+' · '+n.sites.length,noteZh:'同坐标合并，不代表同一工厂。704 条是苹果披露地区；另 20 条是供应商设施背景，不证明为苹果生产。地区事件不证明停产。',noteEn:'Shared coordinates are grouped, not necessarily one factory. 704 records are Apple-reported regions; 20 are supplier-facility context, not confirmed Apple production. Regional events do not prove disruption.',disaster:n.sites.some(s=>s.disasterEventCount>0),conflict:n.sites.some(s=>s.conflictEvents>0)}));
 return {id:'apple-network',title:{zh:'苹果 · 全球供应网络与成本传导',en:'Apple · global supply network & cost transmission'},color:'#abff00',kind:'branched_network',reviewedAt:snapshot.generatedAt,asOf:snapshot.asOf,nodes:[...nodes,...ports.values()],edges,reportHref:'/platform/chains?chain=apple-network',coverage:{suppliers:snapshot.supplierCount,locations:snapshot.siteCount,located:snapshot.geocodedSiteCount,unlocated:snapshot.siteCount-snapshot.geocodedSiteCount,regional:snapshot.regionalLocationCount,exact:snapshot.exactFacilityCount,power:'unknown',cost:'undisclosed',truncated:snapshot.truncated},unlocated:snapshot.sites.filter(s=>!s.coordinates)};
}
