// Isolated non-redeemable TEST token / DBC pool. No buys, sells or mainnet.
// Default is inspect/simulate only. --submit permits FREE DEVNET SOL only.
import {Connection,Keypair,PublicKey} from '@solana/web3.js';
import {DynamicBondingCurveClient,buildCurveWithMarketCap,deriveDbcPoolAddress} from '@meteora-ag/dynamic-bonding-curve-sdk';
import {readFileSync,writeFileSync,mkdirSync,existsSync} from 'node:fs';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
const root=resolve(import.meta.dirname,'../../.tmp/orakt-meteora-v146');mkdirSync(root,{recursive:true});
const operator=Keypair.fromSecretKey(Uint8Array.from(JSON.parse(readFileSync(resolve(root,'../orakt-devnet-v145/operator-keypair.json')))));
let tail=Promise.resolve();const slowFetch=(...args)=>{const p=tail.then(async()=>{await new Promise(r=>setTimeout(r,400));return fetch(...args)});tail=p.catch(()=>{});return p;};
const rpc=new Connection('https://api.devnet.solana.com',{commitment:'finalized',fetch:slowFetch,disableRetryOnRateLimit:true});
assert.equal(await rpc.getGenesisHash(),'EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG');
const client=new DynamicBondingCurveClient(rpc,'finalized');
const pair=name=>{const path=resolve(root,name+'-keypair.json');if(existsSync(path))return Keypair.fromSecretKey(Uint8Array.from(JSON.parse(readFileSync(path))));const p=Keypair.generate();writeFileSync(path,JSON.stringify([...p.secretKey]));return p;};
const config=pair('config'),mint=pair('base-mint'),quote=new PublicKey('So11111111111111111111111111111111111111112');
const pool=deriveDbcPoolAddress(quote,mint.publicKey,config.publicKey);
const file=resolve(root,'acceptance.json');
const audit=existsSync(file)?JSON.parse(readFileSync(file)):{network:'solana:devnet',synthetic:true,redeemable:false,realStock:false,swapsSubmitted:0,program:'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN',pool:pool.toBase58(),config:config.publicKey.toBase58(),baseMint:mint.publicKey.toBase58(),quoteMint:quote.toBase58(),name:'ORAKT Evidence TEST',symbol:'OREVTEST',steps:{},startedAt:new Date().toISOString()};
const save=()=>writeFileSync(file,JSON.stringify(audit,null,2));save();
const curve=buildCurveWithMarketCap({
 initialMarketCap:1,migrationMarketCap:10,
 token:{tokenType:0,tokenBaseDecimal:6,tokenQuoteDecimal:9,tokenAuthorityOption:1,totalTokenSupply:1_000_000,leftover:0},
 fee:{baseFeeParams:{baseFeeMode:0,feeSchedulerParam:{startingFeeBps:100,endingFeeBps:100,numberOfPeriod:0,totalDuration:0}},dynamicFeeEnabled:false,collectFeeMode:0,creatorTradingFeePercentage:0,poolCreationFee:0,enableFirstSwapWithMinFee:false},
 migration:{migrationOption:1,migrationFeeOption:0,migrationFee:{feePercentage:0,creatorFeePercentage:0}},
 liquidityDistribution:{partnerPermanentLockedLiquidityPercentage:0,partnerLiquidityPercentage:0,creatorPermanentLockedLiquidityPercentage:100,creatorLiquidityPercentage:0},
 lockedVesting:{totalLockedVestingAmount:0,numberOfVestingPeriod:0,cliffUnlockAmount:0,totalVestingDuration:0,cliffDurationFromMigrationTime:0},activationType:0
});
async function execute(label,tx,signers){
 if(audit.steps[label]?.status==='finalized')return;
 let step=audit.steps[label];
 if(!step?.raw){
  const block=await rpc.getLatestBlockhash();tx.feePayer=operator.publicKey;tx.recentBlockhash=block.blockhash;tx.sign(operator,...signers);
  const sim=await rpc.simulateTransaction(tx);assert.equal(sim.value.err,null,JSON.stringify(sim.value.logs));
  console.log(JSON.stringify({label,simulated:true,computeUnits:sim.value.unitsConsumed,bytes:tx.serialize().length}));
  if(!process.argv.includes('--submit'))return false;
  const fee=(await rpc.getFeeForMessage(tx.compileMessage())).value;assert.ok(fee<100_000);
  step={status:'prepared',raw:tx.serialize().toString('base64'),...block};audit.steps[label]=step;save();
 }
 assert.ok(process.argv.includes('--submit'),'Explicit test-only submit flag required');
 if(!step.signature){step.signature=await rpc.sendRawTransaction(Buffer.from(step.raw,'base64'));step.status='sent';save();}
 for(let n=0;n<55;n++){
  const s=(await rpc.getSignatureStatuses([step.signature],{searchTransactionHistory:true})).value[0];assert.ok(!s?.err,JSON.stringify(s?.err));
  if(s?.confirmationStatus==='finalized'){step.status='finalized';delete step.raw;save();console.log('FINALIZED '+label+' '+step.signature);return true;}
  await new Promise(r=>setTimeout(r,1000));
 }
 throw Error('Original signature pending; inspect without creating a replacement');
}
const balance=await rpc.getBalance(operator.publicKey);audit.balanceBefore??=balance;save();
assert.ok(balance>100_000_000,'Requires at least 0.1 FREE Devnet SOL; never fund this identity on mainnet');
if(!await rpc.getAccountInfo(config.publicKey)){
 const tx=await client.partner.createConfig({...curve,config:config.publicKey,payer:operator.publicKey,feeClaimer:operator.publicKey,leftoverReceiver:operator.publicKey,quoteMint:quote});
 if(await execute('config',tx,[config])===false){console.log('Dry run only; pool creation requires finalized config');process.exit(0);}
}
if(!await rpc.getAccountInfo(pool))await execute('pool',await client.creator.createPool({name:audit.name,symbol:audit.symbol,uri:'',payer:operator.publicKey,poolCreator:operator.publicKey,config:config.publicKey,baseMint:mint.publicKey}),[mint]);
const state=await client.state.getPool(pool);if(!state)throw Error('Pool not finalized');
assert.equal(state.poolState.config.toBase58(),config.publicKey.toBase58());assert.equal(state.poolState.baseMint.toBase58(),mint.publicKey.toBase58());
audit.balanceAfter=await rpc.getBalance(operator.publicKey);audit.freeDevnetLamportsSpent=audit.balanceBefore-audit.balanceAfter;assert.ok(audit.freeDevnetLamportsSpent<100_000_000,'Test budget exceeded; do not continue');
audit.completedAt=new Date().toISOString();audit.status='finalized';save();
console.log(JSON.stringify({...audit,steps:Object.fromEntries(Object.entries(audit.steps).map(([k,s])=>[k,{status:s.status,signature:s.signature}]))},null,2));
