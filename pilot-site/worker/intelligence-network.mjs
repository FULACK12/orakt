import {DEVNET_RPC,DEVNET_GENESIS} from './solana-network.mjs';
import {decodeAddress} from './wallet-auth.mjs';
const RPC=DEVNET_RPC,GENESIS=DEVNET_GENESIS;
const json=(data,status=200)=>Response.json(data,{status,headers:{'Cache-Control':'private, no-store'}});
// Read-only fixed-host RPC. No caller-selected endpoint, signing, faucet or broadcast.
export async function intelligenceNetwork(request,fetcher=fetch){
 if(request.method!=='GET')return json({error:'method_not_allowed'},405);
 const wallet=new URL(request.url).searchParams.get('wallet');
 if(wallet){try{decodeAddress(wallet);}catch{return json({error:'invalid_wallet'},400);}}
 const call=async(method,params=[])=>{const r=await fetcher(RPC,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:AbortSignal.timeout(8000)});if(!r.ok)throw Error('rpc_unavailable');const d=await r.json();if(d.error||d.result===undefined)throw Error('rpc_unavailable');return d.result;};
 try{
  const [genesis,epoch,balance]=await Promise.all([call('getGenesisHash'),call('getEpochInfo',[{commitment:'finalized'}]),wallet?call('getBalance',[wallet,{commitment:'finalized'}]):null]);
  if(genesis!==GENESIS)return json({error:'network_mismatch',network:'solana:devnet'},503);
  if(!['absoluteSlot','epoch','slotIndex','slotsInEpoch'].every(k=>Number.isSafeInteger(epoch?.[k])&&epoch[k]>=0)||epoch.slotsInEpoch===0||epoch.slotIndex>=epoch.slotsInEpoch||balance&&(!Number.isSafeInteger(balance.value)||balance.value<0))throw Error('invalid_rpc_response');
  return json({network:'solana:devnet',commitment:'finalized',checkedAt:new Date().toISOString(),endpoint:RPC,slot:epoch.absoluteSlot,epoch:epoch.epoch,slotIndex:epoch.slotIndex,slotsInEpoch:epoch.slotsInEpoch,wallet:wallet||null,lamports:balance?.value??null,balanceSlot:balance?.context?.slot??null,mainnet:false});
 }catch{return json({error:'rpc_unavailable',network:'solana:devnet',checkedAt:new Date().toISOString()},503);}
}
