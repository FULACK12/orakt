// Read-only, fixed Devnet integration. No wallet, transaction building or arbitrary RPC URLs.
import {Buffer} from 'node:buffer';
import {createHash} from 'node:crypto';
import {PublicKey} from '@solana/web3.js';
import layouts from './meteora-layout.mjs';
import {DEMO_EVIDENCE as demo} from './meteora-demo.mjs';
import proof from './meteora-proof.mjs';
export const DEVNET_GENESIS='EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG';
const TOKEN='TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA';
const hash=x=>createHash('sha256').update(x).digest();
const fail=code=>{throw Error(code)};
export function decodeAccount(name,account){
 const layout=layouts[name];
 if(!layout||!account||account.owner!==demo.program||account.executable)fail('account_identity_mismatch');
 if(!Array.isArray(account.data)||account.data[1]!=='base64'||typeof account.data[0]!=='string'||account.data[0].length>4096)fail('unsupported_account_data');
 const bytes=Buffer.from(account.data[0],'base64');
 if(bytes.length!==layout.size||!bytes.subarray(0,8).equals(Buffer.from(layout.discriminator)))fail('unsupported_account_layout');
 const result={};for(const field of layout.fields){
  const b=bytes.subarray(field.offset,field.offset+field.size);
  if(field.type==='pubkey')result[field.path]=new PublicKey(b).toBase58();
  else {let n=0n;for(let i=b.length-1;i>=0;i--)n=(n<<8n)+BigInt(b[i]);result[field.path]=n.toString();}
 }return result;
}
export function units(raw,decimals){
 if(!Number.isSafeInteger(decimals)||decimals<0||decimals>18||!/^\d+$/.test(String(raw)))fail('invalid_units');
 const s=String(raw).padStart(decimals+1,'0');return decimals?s.slice(0,-decimals)+'.'+s.slice(-decimals):s;
}
export function sqrtPrice(raw,baseDecimals,quoteDecimals){
 const q=BigInt(raw),scale=10n**12n;
 return units(q*q*10n**BigInt(baseDecimals)*scale/((1n<<128n)*10n**BigInt(quoteDecimals)),12);
}
function mintDecimals(account){
 if(!account||account.owner!==TOKEN||account.executable||account.data?.[1]!=='base64')fail('unsupported_mint');
 const bytes=Buffer.from(account.data[0],'base64');if(bytes.length!==82||bytes[45]!==1||bytes[44]>18)fail('unsupported_mint');return bytes[44];
}
export function verifyRecord(account){
 const b=account?.data?.[1]==='base64'?Buffer.from(account.data[0],'base64'):Buffer.alloc(0);
 const content=hash(JSON.stringify(demo)),root=hash(Buffer.concat([Buffer.from('orakt-evidence-leaf-v1'),content]));
 if(account?.owner!==proof.program||account.executable||b.length!==214||!b.subarray(0,8).equals(hash('account:Record').subarray(0,8))||new PublicKey(b.subarray(8,40)).toBase58()!==proof.config||new PublicKey(b.subarray(40,72)).toBase58()!==proof.series||b.readUInt32LE(104)!==1||b[108]!==0||!b.subarray(109,141).equals(content)||!b.subarray(141,173).equals(root)||content.toString('hex')!==proof.contentHash)fail('evidence_commitment_mismatch');
 return true;
}
export function summarizeAccounts(result){
 if(!Number.isSafeInteger(result?.context?.slot)||!Array.isArray(result.value)||result.value.length!==6)fail('rpc_snapshot_invalid');
 const [poolAccount,configAccount,base,quote,record,program]=result.value;
 if(!program?.executable||program.owner!=='BPFLoaderUpgradeab1e11111111111111111111111')fail('dbc_program_unavailable');
 const pool=decodeAccount('VirtualPool',poolAccount),config=decodeAccount('PoolConfig',configAccount);
 if(pool['pool_state.config']!==demo.config||pool['pool_state.base_mint']!==demo.baseMint||config.quote_mint!==demo.quoteMint)fail('pool_config_mint_mismatch');
 const bd=mintDecimals(base),qd=mintDecimals(quote);if(Number(config.token_decimal)!==bd)fail('mint_decimals_mismatch');
 verifyRecord(record);
 const threshold=BigInt(config.migration_quote_threshold),reserve=BigInt(pool['pool_state.quote_reserve']);
 const progressBps=threshold?Number(reserve*10000n/threshold):0;
 return {slot:result.context.slot,baseDecimals:bd,quoteDecimals:qd,baseReserve:units(pool['pool_state.base_reserve'],bd),quoteReserve:units(reserve,qd),migrationQuoteThreshold:units(threshold,qd),progressBps:Math.max(0,Math.min(10000,progressBps)),spotQuotePerBase:sqrtPrice(pool['pool_state.sqrt_price'],bd,qd),priceUnit:'Devnet SOL per OREVTEST; not USD, not an executable quote',migrated:pool['pool_state.is_migrated']==='1',migrationOption:config.migration_option==='1'?'DAMM v2':'legacy / unsupported',graduatedPoolAddress:null,graduatedPoolVerified:false,initialBaseFeeBps:Number(config['pool_fees.base_fee.cliff_fee_numerator'])/100000,dynamicFeeEnabled:config['pool_fees.dynamic_fee.initialized']==='1',configuredCreatorPermanentLockPct:Number(config.creator_permanent_locked_liquidity_percentage),configuredCreatorLiquidityPct:Number(config.creator_liquidity_percentage),configuredPartnerPermanentLockPct:Number(config.partner_permanent_locked_liquidity_percentage),configuredPartnerLiquidityPct:Number(config.partner_liquidity_percentage),curve:[{sqrtPrice:config.sqrt_start_price,price:sqrtPrice(config.sqrt_start_price,bd,qd)},...Array.from({length:20},(_,i)=>({sqrtPrice:config[`curve.${i}.sqrt_price`],liquidity:config[`curve.${i}.liquidity`]})).filter(p=>BigInt(p.sqrtPrice)>0n&&BigInt(p.liquidity)>0n).map(p=>({...p,price:sqrtPrice(p.sqrtPrice,bd,qd)}))],evidenceVerified:true};
}
export async function devnetRpc(method,params=[],fetcher=fetch){
 if(!['getGenesisHash','getMultipleAccounts'].includes(method))fail('rpc_method_forbidden');
 const r=await fetcher('https://api.devnet.solana.com',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:AbortSignal.timeout(7000)});
 if(!r.ok)fail('devnet_rpc_unavailable');
 const reader=r.body?.getReader();if(!reader)fail('devnet_rpc_unavailable');let length=0;const chunks=[];
 while(true){const {done,value}=await reader.read();if(done)break;length+=value.length;if(length>65536){await reader.cancel();fail('rpc_response_too_large');}chunks.push(Buffer.from(value));}
 const data=JSON.parse(Buffer.concat(chunks).toString('utf8'));if(data.error||!Object.hasOwn(data,'result'))fail('devnet_rpc_unavailable');return data.result;
}
export async function readMeteora(rpc=devnetRpc){
 if(await rpc('getGenesisHash')!==DEVNET_GENESIS)fail('wrong_rpc_network');
 return summarizeAccounts(await rpc('getMultipleAccounts',[[demo.pool,demo.config,demo.baseMint,demo.quoteMint,proof.record,demo.program],{encoding:'base64',commitment:'finalized'}]));
}
// One known pool, one bounded 60s cache, single-flight upstream request. Never return
// an old snapshot labelled live; errors are explicit and don't become zero values.
export function createMeteoraReader(rpc=devnetRpc,clock=Date.now){
 let cached=null,inflight=null,until=0;
 return async()=>{
  if(cached&&clock()<until)return {...cached,cache:'cached'};
  if(inflight)return inflight;
  inflight=(async()=>{const checkedAt=new Date(clock()).toISOString();let response;
   try{response={available:true,mode:'finalized_rpc_snapshot',checkedAt,state:await readMeteora(rpc)};}
   catch(e){response={available:false,mode:'unavailable',checkedAt,state:null,error:['wrong_rpc_network','pool_config_mint_mismatch','evidence_commitment_mismatch','unsupported_account_layout'].includes(e.message)?e.message:'devnet_rpc_unavailable'};}
   cached=response;until=clock()+(response.available?60000:15000);return {...response,cache:'fresh'};
  })();try{return await inflight;}finally{inflight=null;}
 };
}
const current=createMeteoraReader();
export async function meteoraResponse(request){
 if(request.method!=='GET')return Response.json({error:'method_not_allowed'},{status:405});
 return Response.json({network:'solana:devnet',executionEnabled:false,integration:'read_only_evidence_linked_pool',demo,proof,...await current()},{headers:{'Cache-Control':'private, no-store'}});
}
