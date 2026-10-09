import {workspaceAccess} from './research-tiers.mjs';
import {appleNetwork} from './apple-network.mjs';
// Exposure paths use published source locations, never invented factory coordinates.
export function mapChains(access,hormuz,supply,apple){
 const caps=workspaceAccess(access),limit=caps.chains.mapLimit;
 if(!limit)return {tier:caps.tier,limit:0,chains:[],locked:true};
 const paths=apple?[appleNetwork(apple),{...hormuz,color:'#be9cff'}]:[{...hormuz,color:'#be9cff'}];
 for(const ticker of ['AAPL','MU','TSM','INTC']){
  if(apple&&ticker==='AAPL')continue;
  const site=supply.sites.find(s=>s.contextTicker===ticker&&Array.isArray(s.coordinates)&&s.sourceUrl&&s.nearestPort);
  if(!site)continue;
  paths.push({id:'supply-'+ticker,title:{zh:ticker+' 产地与物流暴露',en:ticker+' production / logistics exposure'},color:{AAPL:'#abff00',MU:'#49dbe8',TSM:'#ffbf69',INTC:'#ff91c5'}[ticker],kind:'research_scenario',reviewedAt:supply.asOf,nodes:[
   {id:'site-'+ticker,zh:site.siteName+' · '+(site.coordinatePrecision==='admin1_centroid'?'地区参考点':'披露设施'),en:site.siteName+' · '+site.coordinatePrecision,coordinates:site.coordinates,status:'context',noteZh:'来源支持此产地关联；不证明停产。'+site.sourceExcerpt,noteEn:site.sourceExcerpt,sources:[{title:site.relatedCompanyName||ticker,url:site.sourceUrl}]},
   {id:'port-'+ticker,zh:site.nearestPort.name+' · 最近港口参考',en:site.nearestPort.name+' · nearest port reference',coordinates:[site.nearestPort.longitude,site.nearestPort.latitude],status:'hypothesis',noteZh:'地理接近不代表实际运输路线，路线及货物影响待验证。',noteEn:'Proximity does not establish an actual shipping route; cargo impact is unverified.',sources:[]},
   {id:'cost-'+ticker,zh:'运输 / 库存 / 成本传导？',en:'Shipping / inventory / cost transmission?',coordinates:null,status:'hypothesis',noteZh:'须补充库存、采购合同和交货期，不能由附近事件直接推断损失。',noteEn:'Inventory, contracts and lead times are required. Nearby events do not prove losses.',sources:[]},
   {id:'price-'+ticker,zh:ticker+' 价格反应待验证',en:ticker+' price response unverified',coordinates:null,status:'hypothesis',noteZh:'未绑定事件窗口收益率；不显示虚构涨跌幅。',noteEn:'No event-window returns bound; no fabricated price change.',sources:[]}
  ]});
 }
 return {tier:caps.tier,limit,chains:apple?paths:paths.slice(0,limit),asOf:supply.asOf,locked:false};
}
