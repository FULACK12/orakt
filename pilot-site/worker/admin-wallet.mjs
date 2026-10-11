import {decodeAddress} from './wallet-auth.mjs';
import {rpcFor,assertMainnet} from './billing.mjs';
const json=(v,status=200)=>Response.json(v,{status,headers:{'Cache-Control':'private, no-store'}});
export async function adminWalletResponse(request,env,member,fetcher=fetch){
 if(!member?.access?.permissions?.manageUsers)return json({error:'admin_required'},403);
 if(request.method!=='GET')return json({error:'method_not_allowed'},405);
 const wallet=new URL(request.url).searchParams.get('address');
 try{decodeAddress(wallet);}catch{return json({error:'invalid_wallet'},400);}
 try{
  const rpc=rpcFor(env,fetcher);await assertMainnet(rpc);
  const balance=await rpc('getBalance',[wallet,{commitment:'finalized'}]);
  if(!Number.isSafeInteger(balance?.value)||balance.value<0)throw Error();
  return json({wallet,network:'solana:mainnet',lamports:balance.value,checkedAt:new Date().toISOString(),readOnly:true,identityLinked:false});
 }catch{return json({error:'mainnet_balance_unavailable'},503);}
}
