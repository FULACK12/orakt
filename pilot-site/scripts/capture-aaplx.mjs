// Read-only public issuer/RPC evidence capture. Never connects a wallet or submits transactions.
import {writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
const base='https://api.xstocks.fi/api/v2';
async function capture(url,options){const retrievedAt=new Date().toISOString();try{const r=await fetch(url,{...options,signal:AbortSignal.timeout(18000)}),raw=await r.text();if(!r.ok)throw Error('HTTP '+r.status);const data=JSON.parse(raw);if(data.error)throw Error(JSON.stringify(data.error));return {url,retrievedAt,sha256:createHash('sha256').update(raw).digest('hex'),status:'retrieved',data};}catch(e){return {url,retrievedAt,status:'unavailable',error:String(e.message),data:null};}}
const paths={asset:'/public/assets/AAPLx',price:'/public/assets/AAPLx/price-data',multiplier:'/public/assets/AAPLx/multiplier?network=Solana',circulating:'/public/assets/AAPLx/circulating-supply',total:'/public/assets/AAPLx/total-supply',reserves:'/public/proof-of-reserves/AAPLx'};
const evidence=Object.fromEntries(await Promise.all(Object.entries(paths).map(async([k,path])=>[k,await capture(base+path)])));
if(evidence.asset.data?.symbol!=='AAPLx'||evidence.asset.data?.underlying?.symbol!=='AAPL')throw Error('Issuer identity verification failed');
const mint=evidence.asset.data.deployments.find(d=>d.network==='Solana')?.address;
if(!mint)throw Error('Issuer does not list a Solana mint');
evidence.solanaMint=await capture('https://api.mainnet-beta.solana.com',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method:'getAccountInfo',params:[mint,{encoding:'jsonParsed',commitment:'finalized'}]})});
const output={schema:'aaplx-evidence/v1',capturedAt:new Date().toISOString(),executionEnabled:false,evidence};
writeFileSync(new URL('../private-data/aaplx-evidence-v135.json',import.meta.url),JSON.stringify(output,null,2));
console.log(JSON.stringify(Object.fromEntries(Object.entries(evidence).map(([k,v])=>[k,k==='asset'?{status:v.status,networks:v.data?.deployments.map(d=>d.network)}:v])),null,2));
