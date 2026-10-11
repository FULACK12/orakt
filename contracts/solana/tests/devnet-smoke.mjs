// Explicitly authorized Devnet acceptance ONLY. Requires prepare-devnet.mjs and
// a verified deployment. All assets below are synthetic, not issuer stablecoins.
// npm install --prefix .tmp/orakt-devnet-v144/client --ignore-scripts @solana/spl-token@0.4.14 @solana/web3.js@1.98.4
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
const root=resolve(fileURLToPath(new URL('../../../',import.meta.url)),'.tmp/orakt-devnet-v144');
const require=createRequire(join(root,'client/package.json'));
const {Connection,Keypair,PublicKey,SystemProgram,Transaction,TransactionInstruction}=require('@solana/web3.js');
const spl=require('@solana/spl-token');
const manifest=JSON.parse(readFileSync(join(root,'manifest.json')));
assert.equal(manifest.network,'solana:devnet');assert.equal(manifest.productionEntitlements,false);
// The free shared RPC limits both requests and new connections. Serialize calls
// with a modest delay, including confirmation reads; no WebSocket churn.
let requestTail=Promise.resolve();
const slowFetch=(...args)=>{const next=requestTail.then(async()=>{await new Promise(r=>setTimeout(r,450));return fetch(...args);});requestTail=next.then(()=>{},()=>{});return next;};
const rpc=new Connection('https://api.devnet.solana.com',{commitment:'finalized',fetch:slowFetch});
assert.equal(await rpc.getGenesisHash(),'EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG');
const pair=name=>Keypair.fromSecretKey(Uint8Array.from(JSON.parse(readFileSync(join(root,name+'-keypair.json')))));
const operator=pair('operator'),buyer=pair('buyer'),program=new PublicKey(manifest.programId);
assert.equal(operator.publicKey.toBase58(),manifest.operator);assert.equal(buyer.publicKey.toBase58(),manifest.buyer);
assert.ok((await rpc.getAccountInfo(program))?.executable,'Deploy and verify program first');
const auditPath=join(root,'smoke-audit.json');
const audit=existsSync(auditPath)?JSON.parse(readFileSync(auditPath)):{network:manifest.network,programId:manifest.programId,testOnly:true,productionEntitlements:false,startedAt:new Date().toISOString(),steps:{},checks:[]};
const save=()=>writeFileSync(auditPath,JSON.stringify(audit,null,2));
const hash=s=>createHash('sha256').update(s).digest();
const key=x=>x.publicKey??x;
const meta=(x,isSigner=false,isWritable=false)=>({pubkey:key(x),isSigner,isWritable});
const pda=(...seeds)=>PublicKey.findProgramAddressSync(seeds.map(s=>typeof s==='string'?Buffer.from(s):s instanceof PublicKey?s.toBuffer():s),program)[0];
const u32=n=>{const b=Buffer.alloc(4);b.writeUInt32LE(n);return b;};
const u64=n=>{const b=Buffer.alloc(8);b.writeBigUInt64LE(BigInt(n));return b;};
const ix=(name,keys,...data)=>new TransactionInstruction({programId:program,keys,data:Buffer.concat([hash('global:'+name).subarray(0,8),...data])});
const config=pda('config',operator.publicKey),permit=who=>pda('permit',config,key(who)),sys=meta(SystemProgram.programId);
const read=async p=>(await rpc.getAccountInfo(p))?.data;
const check=name=>{if(!audit.checks.includes(name))audit.checks.push(name);save();console.log('PASS Devnet: '+name);};
async function send(label,instructions,signers=[operator]){
  let step=audit.steps[label];
  if(step?.status==='finalized')return step.signature;
  if(!step){
    const block=await rpc.getLatestBlockhash();
    const tx=new Transaction({feePayer:signers[0].publicKey,...block}).add(...(Array.isArray(instructions)?instructions:[instructions]));tx.sign(...signers);
    // Save signed bytes before broadcast. A retry only rebroadcasts these SAME bytes.
    const raw=tx.serialize();step={status:'prepared',raw:raw.toString('base64'),...block};audit.steps[label]=step;save();
  }
  if(!step.signature){step.signature=await rpc.sendRawTransaction(Buffer.from(step.raw,'base64'));step.status='sent';save();}
  let finalized=false;
  for(let attempt=0;attempt<60;attempt++){
    const status=(await rpc.getSignatureStatuses([step.signature],{searchTransactionHistory:true})).value[0];
    assert.ok(!status?.err,label+': failed transaction');
    if(status?.confirmationStatus==='finalized'){finalized=true;break;}
    await new Promise(r=>setTimeout(r,1000));
  }
  assert.ok(finalized,label+': pending original signature; do not pay twice');
  step.status='finalized';delete step.raw;save();console.log('FINALIZED '+label+' '+step.signature);return step.signature;
}
if(!await read(config))await send('initialize',ix('initialize',[meta(operator,true,true),meta(config,false,true),sys]));
assert.deepEqual((await read(config)).subarray(8,40),operator.publicKey.toBuffer());
await send('publisher-role',ix('set_roles',[meta(operator,true,true),meta(config),meta(operator),meta(permit(operator),false,true),sys],Buffer.from([1])));
if(await rpc.getBalance(buyer.publicKey)<20_000_000)await send('fund-test-buyer',SystemProgram.transfer({fromPubkey:operator.publicKey,toPubkey:buyer.publicKey,lamports:100_000_000}));
const evidenceBytes=Buffer.from('ORAKT Devnet acceptance v144. SYNTHETIC evidence; not a company report, news item or investment claim.');
const leaf=hash(evidenceBytes),evidenceRoot=hash(Buffer.concat([Buffer.from('orakt-evidence-leaf-v1'),leaf]));
audit.evidence={utf8:evidenceBytes.toString(),leafHash:leaf.toString('hex'),root:evidenceRoot.toString('hex'),proof:[]};audit.config=config.toBase58();save();
for(const [kind,name]of ['report','intelligence','evidence-chain','factor','portfolio','ai-draft'].entries()){
  const item=hash('orakt-devnet-v144-synthetic:'+name),series=pda('series',config,operator.publicKey,item),record=pda('record',series,u32(1));
  await send('registry-'+name,[
   ix('open_series',[meta(operator,true,true),meta(config),meta(permit(operator)),meta(series,false,true),sys],item,Buffer.from([kind])),
   ix('publish_version',[meta(operator,true,true),meta(config),meta(permit(operator)),meta(series,false,true),meta(record,false,true),sys],u32(1),hash('SYNTHETIC v144 '+name),evidenceRoot,Buffer.alloc(32)),
   ix('verify_evidence',[meta(record)],leaf,u32(0))]);
  const recordBytes=await read(record);assert.equal(recordBytes[108],kind);assert.deepEqual(recordBytes.subarray(141,173),evidenceRoot);
  audit['record_'+name]=record.toBase58();check(name+' version and inclusion proof');
}
const merchant=new PublicKey('9WLRmvq8a86A6q9JwrzKqyVoUXDJoXC14SKNix3xZ79Z');
for(const [mintName,plan,amount]of [['test-usdc',2,79_000_000],['test-usdt',1,19_000_000]]){
  const mint=pair(mintName),source=spl.getAssociatedTokenAddressSync(mint.publicKey,buyer.publicKey),treasury=spl.getAssociatedTokenAddressSync(mint.publicKey,merchant);
  assert.equal(mint.publicKey.toBase58(),manifest.mints[mintName==='test-usdc'?'TEST_USDC':'TEST_USDT']);
  if(!await read(mint.publicKey))await send('mint-'+mintName,[SystemProgram.createAccount({fromPubkey:operator.publicKey,newAccountPubkey:mint.publicKey,space:spl.MINT_SIZE,lamports:await rpc.getMinimumBalanceForRentExemption(spl.MINT_SIZE),programId:spl.TOKEN_PROGRAM_ID}),spl.createInitializeMint2Instruction(mint.publicKey,6,operator.publicKey,null)],[operator,mint]);
  await send('accounts-'+mintName,[spl.createAssociatedTokenAccountIdempotentInstruction(operator.publicKey,source,buyer.publicKey,mint.publicKey),spl.createAssociatedTokenAccountIdempotentInstruction(operator.publicKey,treasury,merchant,mint.publicKey)]);
  await send('faucet-'+mintName,spl.createMintToCheckedInstruction(mint.publicKey,source,operator.publicKey,1_000_000_000,6));
  const invoice=hash('orakt-devnet-v144-synthetic-invoice:'+mintName),receipt=pda('receipt',config,buyer.publicKey,invoice),subscription=pda('subscription',config,buyer.publicKey,Buffer.from([plan]));
  const time=(await read(new PublicKey('SysvarC1ock11111111111111111111111111111111'))).readBigInt64LE(32);
  const purchase=ix('purchase',[meta(buyer,true,true),meta(config),meta(mint),meta(source,false,true),meta(treasury,false,true),meta(subscription,false,true),meta(receipt,false,true),meta(spl.TOKEN_PROGRAM_ID),sys],Buffer.from([plan]),invoice,Buffer.from([1]),u64(amount),u64(time+500n));
  const balance=async account=>(await read(account)).readBigUInt64LE(64);
  if(!await read(receipt)){
    const before=await balance(source),beforeTo=await balance(treasury);
    await send('purchase-'+mintName,purchase,[buyer]);
    assert.equal(before-await balance(source),BigInt(amount));assert.equal(await balance(treasury)-beforeTo,BigInt(amount));
    check(mintName+' exact transfer');
  }
  const r=await read(receipt),sub=await read(subscription);assert.equal(r.length,163);assert.equal(r.readBigUInt64LE(136),BigInt(amount));assert.equal(r[144],plan);assert.equal(r.readBigInt64LE(154),sub.readBigInt64LE(73));
  const balances=[await balance(source),await balance(treasury)];
  const block=await rpc.getLatestBlockhash(),retry=new Transaction({feePayer:buyer.publicKey,...block}).add(purchase);retry.sign(buyer);
  const simulation=await rpc.simulateTransaction(retry);assert.ok(simulation.value.err,'same invoice must be rejected');
  assert.deepEqual([await balance(source),await balance(treasury)],balances);assert.deepEqual(await read(receipt),r);assert.deepEqual(await read(subscription),sub);
  audit['receipt_'+mintName]=receipt.toBase58();audit['subscription_'+mintName]=subscription.toBase58();check(mintName+' receipt and duplicate rejection (simulation)');
}
await send('reviewer-role',ix('set_roles',[meta(operator,true,true),meta(config),meta(buyer),meta(permit(buyer),false,true),sys],Buffer.from([2])));
const report=new PublicKey(audit.record_report),review=pda('review',report,buyer.publicKey);
await send('attributed-review',ix('attest',[meta(buyer,true,true),meta(config),meta(permit(buyer)),meta(report),meta(review,false,true),sys],Buffer.from([0]),hash('SYNTHETIC review fixture, not independent assurance')),[buyer]);
audit.review=review.toBase58();check('separate-wallet review, same test operator custody');
const draft=new PublicKey(audit['record_ai-draft']),retraction=pda('retraction',draft),originalDraft=await read(draft);
await send('retract-draft',ix('retract',[meta(operator,true,true),meta(draft),meta(retraction,false,true),sys],hash('SYNTHETIC draft withdrawn')));
assert.deepEqual(await read(draft),originalDraft);audit.retraction=retraction.toBase58();check('retraction preserves original record');
const subject=hash('SYNTHETIC non-person account v144 random-purpose test'),trial=pda('trial',config,subject);
await send('consented-trial',ix('issue_trial',[meta(operator,true,true),meta(buyer,true),meta(config),meta(trial,false,true),sys],subject),[operator,buyer]);
const trialBytes=await read(trial);assert.equal(trialBytes.readBigInt64LE(112)-trialBytes.readBigInt64LE(104),86400n);audit.trial=trial.toBase58();check('two-signature 24-hour trial proof, no web entitlement');
await send('pause',ix('set_paused',[meta(operator,true),meta(config,false,true)],Buffer.from([1])));assert.equal((await read(config))[40],1);
await send('resume',ix('set_paused',[meta(operator,true),meta(config,false,true)],Buffer.from([0])));assert.equal((await read(config))[40],0);check('operator pause and resume');
audit.status='passed';audit.completedAt=new Date().toISOString();save();console.log(JSON.stringify({status:audit.status,checks:audit.checks.length,config:audit.config,programId:manifest.programId,productionEntitlements:false}));
