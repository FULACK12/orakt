export const hormuzChain={
 id:'hormuz-helium', title:{zh:'霍尔木兹—氦气—半导体',en:'Hormuz → helium → semiconductors'},
 kind:'research_scenario', reviewedAt:'2026-10-06',
 nodes:[
  {id:'iran',zh:'伊朗及周边冲突',en:'Iran / regional conflict',status:'hypothesis',coordinates:[53,32],noteZh:'本链未绑定一次具体冲突事件；需有日期的独立事件证据。',noteEn:'No specific conflict event is bound to this scenario; dated independent evidence is required.',sources:[]},
  {id:'hormuz',zh:'霍尔木兹通行受限',en:'Restricted Hormuz passage',status:'hypothesis',coordinates:[56.3,26.6],noteZh:'核对封锁时段、通航记录和保险限制；地图为海峡示意点，不是封锁坐标。',noteEn:'Check closure dates, transits and insurance restrictions. The point represents the strait, not a blockade location.',sources:[]},
  {id:'lng',zh:'LNG 运输暴露',en:'LNG shipping exposure',status:'context',coordinates:[53.1,26.5],noteZh:'EIA 确认卡塔尔 LNG 出口依赖该通道；不能仅由依赖关系推断每艘船已受阻。',noteEn:'EIA documents Qatar LNG route dependence; exposure does not prove that every vessel was delayed.',sources:[{title:'EIA · LNG and Hormuz',url:'https://www.eia.gov/TODAYINENERGY/detail.php?id=65584'}]},
  {id:'helium',zh:'卡塔尔氦气产运风险',en:'Qatar helium supply risk',status:'partial',coordinates:[51.5,25.4],noteZh:'运营方确认氦气业务。氦气使用专用低温容器，不能直接视作 LNG 船货；产量和运输须分别核验。',noteEn:'The operator documents helium operations. Helium uses dedicated cryogenic containers, not LNG cargo; production and transport need separate checks.',sources:[{title:'QatarEnergy LNG · Helium',url:'https://www.qatarenergylng.qa/english/Operations/Ras-Laffan-Helium'},{title:'Buzwair · Helium ISO containers',url:'https://buzwairgases.com/new-liquid-helium-containers'}]},
  {id:'chips',zh:'芯片制造成本与供应压力？',en:'Chipmaking cost / supply pressure?',status:'hypothesis',coordinates:null,noteZh:'USGS 确认半导体用途；影响幅度取决于库存、替代供应、回收能力和合同，尚无企业减产或价格结论。',noteEn:'USGS identifies semiconductor uses. Effects depend on inventories, alternative supply, recovery and contracts; no issuer output or price conclusion is established.',sources:[{title:'USGS · Helium supply risk',url:'https://www.usgs.gov/news/national-news-release/usgs-seeks-public-comment-helium-supply-risk'}]},
 ],
};
export function chainGeoJSON(){
 const located=hormuzChain.nodes.filter(n=>n.coordinates);
 return {type:'FeatureCollection' as const,features:[...located.map((n,i)=>({type:'Feature' as const,geometry:{type:'Point' as const,coordinates:n.coordinates!},properties:{id:n.id,order:i+1,label:n.zh,labelEn:n.en}})),...located.slice(1).map((n,i)=>({type:'Feature' as const,geometry:{type:'LineString' as const,coordinates:[located[i].coordinates!,n.coordinates!]},properties:{kind:'hypothesis'}}))]};
}
