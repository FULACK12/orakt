// Pinned Devnet read-only inspection. No wallet/key loading or transaction methods.
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
const require=createRequire(new URL('../../../pilot-site/package.json',import.meta.url));
const {PublicKey}=require('@solana/web3.js');
const manifest=JSON.parse(readFileSync(new URL('../devnet-deployment-v145.json',import.meta.url),'utf8'));
const GENESIS='EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG';
const LOADER='BPFLoaderUpgradeab1e11111111111111111111111';
const hash=b=>createHash('sha256').update(b).digest();
const pub=(b,n)=>new PublicKey(b.subarray(n,n+32)).toBase58();
const check=(ok,why)=>{if(!ok)throw Error(why);};
const pda=(...seeds)=>PublicKey.findProgramAddressSync(seeds,new PublicKey(manifest.programId));
function decode(a,owner,size,tag,executable=false){
  check(a?.owner===owner && a.executable===executable && Array.isArray(a.data) && a.data[1]==='base64' && typeof a.data[0]==='string' && a.data[0].length<1600000,'account_metadata_mismatch');
  const b=Buffer.from(a.data[0],'base64');
  check(b.toString('base64')===a.data[0] && (size===null || b.length===size),'account_size_or_encoding_mismatch');
  if(tag)check(b.subarray(0,8).equals(hash('account:'+tag).subarray(0,8)),'account_discriminator_mismatch');
  return b;
}
export function inspectSnapshot(genesis,snapshot){
  check(genesis===GENESIS,'wrong_network');
  check(Number.isSafeInteger(snapshot?.context?.slot) && snapshot.context.slot>=manifest.deploySlot && snapshot.value?.length===4,'stale_or_incomplete_snapshot');
  const [program,metadata,config,governance]=snapshot.value;
  const p=decode(program,LOADER,36,null,true),d=decode(metadata,LOADER,null,null),c=decode(config,manifest.programId,42,'Config'),g=decode(governance,manifest.programId,138,'Governance');
  const derivedData=PublicKey.findProgramAddressSync([new PublicKey(manifest.programId).toBuffer()],new PublicKey(LOADER))[0].toBase58();
  check(p.readUInt32LE(0)===2 && pub(p,4)===manifest.programData && derivedData===manifest.programData,'programdata_address_mismatch');
  check(d.length>=45+manifest.binaryBytes && d.readUInt32LE(0)===3 && d.readBigUInt64LE(4)===BigInt(manifest.deploySlot),'deployment_changed');
  check(d[12]===1 && pub(d,13)===manifest.upgradeAuthority,'upgrade_authority_changed');
  check(hash(d.subarray(45,45+manifest.binaryBytes)).toString('hex')===manifest.binarySha256 && d.subarray(45+manifest.binaryBytes).every(b=>b===0),'binary_changed');
  const [configAddress,configBump]=pda(Buffer.from('config'),c.subarray(8,40));
  const [govAddress,govBump]=pda(Buffer.from('governance'),new PublicKey(manifest.config).toBuffer());
  check(configAddress.toBase58()===manifest.config && c[41]===configBump && c[40]<=1,'config_mismatch');
  check(govAddress.toBase58()===manifest.governance && pub(g,8)===manifest.config && g[137]===govBump && g[136]<=1,'governance_mismatch');
  const paymentsEnabled=g[136]===1,recoveryPending=!g.subarray(104,136).equals(Buffer.alloc(32));
  const authorityChanged=pub(g,40)!==pub(c,8)||pub(g,72)!==manifest.guardian;
  return {network:'solana:devnet',slot:snapshot.context.slot,program:manifest.programId,binaryMatches:true,upgradeAuthority:pub(d,13),governor:pub(g,40),guardian:pub(g,72),paused:c[40]===1,paymentsEnabled,recoveryPending,
    expectedPaymentOff:!paymentsEnabled,authorityChanged,reviewRequired:paymentsEnabled||recoveryPending||c[40]===1||authorityChanged,productionReady:false,transactionsSent:0,
    limitations:['RPC observation, not an independent security audit','Does not inspect production configuration or private membership records','Test authority and upgrade authority remain privileged']};
}
export async function readDevnetReadiness(fetcher=fetch){
  async function rpc(method,params=[]){
    check(['getGenesisHash','getMultipleAccounts'].includes(method),'write_method_forbidden');
    const response=await fetcher('https://api.devnet.solana.com',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:AbortSignal.timeout(15000)});
    check(response.ok,'rpc_unavailable');const reader=response.body?.getReader();check(reader,'rpc_unavailable');const parts=[];let total=0;
    while(true){const {done,value}=await reader.read();if(done)break;total+=value.length;if(total>2000000){await reader.cancel();throw Error('rpc_response_too_large');}parts.push(Buffer.from(value));}
    const json=JSON.parse(Buffer.concat(parts).toString('utf8'));check(!json.error && Object.hasOwn(json,'result'),'rpc_error');return json.result;
  }
  const genesis=await rpc('getGenesisHash');check(genesis===GENESIS,'wrong_network');
  return {...inspectSnapshot(genesis,await rpc('getMultipleAccounts',[[manifest.programId,manifest.programData,manifest.config,manifest.governance],{commitment:'finalized',encoding:'base64',minContextSlot:manifest.deploySlot}])),checkedAt:new Date().toISOString()};
}
if(process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href){
  if(process.argv.length!==2){console.error('No arguments allowed; Devnet and manifest are pinned.');process.exitCode=1;}
  else try{const result=await readDevnetReadiness();console.log(JSON.stringify(result,null,2));if(result.reviewRequired)process.exitCode=2;}catch(e){console.error(JSON.stringify({status:'unverified',error:e.message,productionReady:false,transactionsSent:0}));process.exitCode=1;}
}
