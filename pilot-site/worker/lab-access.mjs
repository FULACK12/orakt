import {researchTier} from './research-tiers.mjs';
export function visibleLab(data,access){
 const tier=researchTier(access),baskets=tier==='research'?data.baskets:tier==='signal'?data.baskets.filter(b=>b.accessTier==='standard'):[];
 return {...data,factors:tier==='research'?data.factors:[],baskets,lockedBasketCount:data.baskets.length-baskets.length,accessTier:tier,tierBasis:'research_tools_and_recipe_scope_not_returns'};
}
