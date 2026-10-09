export function researchTier(access){
 if(access?.status && access.status!=='active')return 'explorer';
 return access?.permissions?.research?'research':access?.permissions?.reports?'signal':'explorer';
}
export function workspaceAccess(access){
 const tier=researchTier(access);
 return {tier,alpha:{experiments:tier==='research'?3:tier==='signal'?1:0,multifactor:tier==='research',auditArchive:tier==='research'},portfolio:{recipes:tier==='research'?'all':tier==='signal'?'standard':'preview',maxDays:tier==='research'?3660:tier==='signal'?366:0,customStress:tier==='research'},chains:{limit:tier==='research'?null:tier==='signal'?12:0,mapLimit:tier==='research'?5:tier==='signal'?1:0,framework:true},billing:'monthly_non_recurring',basis:'research_depth_and_tool_scope_not_promised_returns'};
}
export function visibleAlpha(data,access){
 const tier=researchTier(access),experiments=tier==='research'?data.experiments:tier==='signal'?data.experiments.slice(0,1):[];
 return {...data,experiments,tier,lockedCount:data.experiments.length-experiments.length};
}
export function visibleChains(chains,access){
 const caps=workspaceAccess(access),limit=caps.chains.limit;
 return {chains:limit===null?chains:chains.slice(0,limit),total:chains.length,visible:limit===null?chains.length:Math.min(limit,chains.length),tier:caps.tier};
}
