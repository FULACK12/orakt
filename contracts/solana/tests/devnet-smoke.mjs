// Explicitly authorized Devnet acceptance ONLY. Requires prepare-devnet.mjs and
// a verified deployment. All assets below are synthetic, not issuer stablecoins.
// npm install --prefix .tmp/orakt-devnet-v145/client --ignore-scripts @solana/spl-token@0.4.14 @solana/web3.js@1.98.4
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {addCalendarMonth} from '../../../pilot-site/worker/payment-policy.mjs';
const root=resolve(fileURLToPath(new URL('../../../',import.meta.url)),'.tmp/orakt-devnet-v145');
const require=createRequire(resolve(root,existsSync(join(root,'client/package.json'))?'client/package.json':'../orakt-devnet-v144/client/package.json'));
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
const guardian=pair('guardian'),successor=pair('successor');
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
const config=pda('config',operator.publicKey),governance=pda('governance',config),permit=who=>pda('permit',config,key(who)),sys=meta(SystemProgram.programId);
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
if(!await read(config))await send('initialize',ix('initialize',[meta(operator,true,true),meta(config,false,true),meta(governance,false,true),sys],guardian.publicKey.toBuffer()));
assert.deepEqual((await read(config)).subarray(8,40),operator.publicKey.toBuffer());
if(!audit.checks.includes('payments default off')){assert.equal((await read(governance))[136],0);check('payments default off');}
audit.governance=governance.toBase58();audit.guardian=guardian.publicKey.toBase58();audit.successor=successor.publicKey.toBase58();save();
await send('publisher-role',ix('set_roles',[meta(operator,true,true),meta(config),meta(governance),meta(operator),meta(permit(operator),false,true),sys],Buffer.from([1])));
if(await rpc.getBalance(buyer.publicKey)<20_000_000)await send('fund-test-buyer',SystemProgram.transfer({fromPubkey:operator.publicKey,toPubkey:buyer.publicKey,lamports:100_000_000}));
const evidenceBytes=Buffer.from('ORAKT Devnet acceptance v145. SYNTHETIC evidence; not a company report, news item or investment claim.');
const leaf=hash(evidenceBytes),evidenceRoot=hash(Buffer.concat([Buffer.from('orakt-evidence-leaf-v1'),leaf]));
audit.evidence={utf8:evidenceBytes.toString(),leafHash:leaf.toString('hex'),root:evidenceRoot.toString('hex'),proof:[]};audit.config=config.toBase58();save();
for(const [kind,name]of ['report','intelligence','evidence-chain','factor','portfolio','ai-draft'].entries()){
  const item=hash('orakt-devnet-v145-synthetic:'+name),series=pda('series',config,operator.publicKey,item),record=pda('record',series,u32(1));
  await send('registry-'+name,[
   ix('open_series',[meta(operator,true,true),meta(config),meta(permit(operator)),meta(series,false,true),sys],item,Buffer.from([kind])),
   ix('publish_version',[meta(operator,true,true),meta(config),meta(permit(operator)),meta(series,false,true),meta(record,false,true),sys],u32(1),hash('SYNTHETIC v145 '+name),evidenceRoot,Buffer.alloc(32)),
   ix('verify_evidence',[meta(record)],leaf,u32(0))]);
  const recordBytes=await read(record);assert.equal(recordBytes[108],kind);assert.deepEqual(recordBytes.subarray(141,173),evidenceRoot);
  audit['record_'+name]=record.toBase58();check(name+' version and inclusion proof');
}
check('six content kinds publish while payments disabled');
const merchant=new PublicKey('9WLRmvq8a86A6q9JwrzKqyVoUXDJoXC14SKNix3xZ79Z');
for(const [mintName,plan,amount]of [['test-usdc',2,79_000_000],['test-usdt',1,19_000_000]]){
  const mint=pair(mintName),source=spl.getAssociatedTokenAddressSync(mint.publicKey,buyer.publicKey),treasury=spl.getAssociatedTokenAddressSync(mint.publicKey,merchant);
  assert.equal(mint.publicKey.toBase58(),manifest.mints[mintName==='test-usdc'?'TEST_USDC':'TEST_USDT']);
  if(!await read(mint.publicKey))await send('mint-'+mintName,[SystemProgram.createAccount({fromPubkey:operator.publicKey,newAccountPubkey:mint.publicKey,space:spl.MINT_SIZE,lamports:await rpc.getMinimumBalanceForRentExemption(spl.MINT_SIZE),programId:spl.TOKEN_PROGRAM_ID}),spl.createInitializeMint2Instruction(mint.publicKey,6,operator.publicKey,null)],[operator,mint]);
  await send('accounts-'+mintName,[spl.createAssociatedTokenAccountIdempotentInstruction(operator.publicKey,source,buyer.publicKey,mint.publicKey),spl.createAssociatedTokenAccountIdempotentInstruction(operator.publicKey,treasury,merchant,mint.publicKey)]);
  await send('faucet-'+mintName,spl.createMintToCheckedInstruction(mint.publicKey,source,operator.publicKey,1_000_000_000,6));
  const invoice=hash('orakt-devnet-v145-synthetic-invoice:'+mintName),receipt=pda('receipt',config,buyer.publicKey,invoice),subscription=pda('subscription',config,buyer.publicKey,Buffer.from([plan]));
  const time=(await read(new PublicKey('SysvarC1ock11111111111111111111111111111111'))).readBigInt64LE(32);
  const purchase=ix('purchase',[meta(buyer,true,true),meta(config),meta(mint),meta(source,false,true),meta(treasury,false,true),meta(subscription,false,true),meta(receipt,false,true),meta(spl.TOKEN_PROGRAM_ID),sys,meta(governance)],Buffer.from([plan]),invoice,Buffer.from([1]),u64(amount),u64(time+500n));
  const balance=async account=>(await read(account)).readBigUInt64LE(64);
  if(!await read(receipt)){
    if(mintName==='test-usdc'&&!audit.steps['enable-test-payments']){
      const block=await rpc.getLatestBlockhash();const attempt=new Transaction({feePayer:buyer.publicKey,...block}).add(purchase);attempt.sign(buyer);
      const rejected=await rpc.simulateTransaction(attempt);assert.deepEqual(rejected.value.err,{InstructionError:[0,{Custom:6010}]});check('direct purchase rejected while payment switch off');
    }
    await send('enable-test-payments',ix('set_payments_enabled',[meta(operator,true),meta(config,false,true),meta(governance,false,true)],Buffer.from([1])));
    const before=await balance(source),beforeTo=await balance(treasury);
    await send('purchase-'+mintName,purchase,[buyer]);
    assert.equal(before-await balance(source),BigInt(amount));assert.equal(await balance(treasury)-beforeTo,BigInt(amount));
    check(mintName+' exact transfer');
  }
  const r=await read(receipt),sub=await read(subscription);assert.equal(r.length,163);assert.equal(r.readBigUInt64LE(136),BigInt(amount));assert.equal(r[144],plan);assert.ok(r.readBigInt64LE(154)<=sub.readBigInt64LE(73));
  const balances=[await balance(source),await balance(treasury)];
  const block=await rpc.getLatestBlockhash(),retry=new Transaction({feePayer:buyer.publicKey,...block}).add(purchase);retry.sign(buyer);
  const simulation=await rpc.simulateTransaction(retry);assert.ok(simulation.value.err,'same invoice must be rejected');
  assert.deepEqual([await balance(source),await balance(treasury)],balances);assert.deepEqual(await read(receipt),r);assert.deepEqual(await read(subscription),sub);
  audit['receipt_'+mintName]=receipt.toBase58();audit['subscription_'+mintName]=subscription.toBase58();check(mintName+' receipt and duplicate rejection (simulation)');
}
// Real Devnet renewal: a new invoice extends the existing term, not now + month.
{
 const mint=pair('test-usdc'),source=spl.getAssociatedTokenAddressSync(mint.publicKey,buyer.publicKey),treasury=spl.getAssociatedTokenAddressSync(mint.publicKey,merchant);
 const invoice=hash('orakt-devnet-v145-renewal'),receipt=pda('receipt',config,buyer.publicKey,invoice),subscription=new PublicKey(audit['subscription_test-usdc']);
 const original=await read(new PublicKey(audit['receipt_test-usdc'])),expected=BigInt(addCalendarMonth(Number(original.readBigInt64LE(154))*1000)/1000);
 if(!await read(receipt)){
  const time=(await read(new PublicKey('SysvarC1ock11111111111111111111111111111111'))).readBigInt64LE(32);
  const before=(await read(source)).readBigUInt64LE(64),beforeTo=(await read(treasury)).readBigUInt64LE(64);
  await send('renew-research',ix('purchase',[meta(buyer,true,true),meta(config),meta(mint),meta(source,false,true),meta(treasury,false,true),meta(subscription,false,true),meta(receipt,false,true),meta(spl.TOKEN_PROGRAM_ID),sys,meta(governance)],Buffer.from([2]),invoice,Buffer.from([1]),u64(79000000),u64(time+500n)),[buyer]);
  assert.equal(before-(await read(source)).readBigUInt64LE(64),79000000n);assert.equal((await read(treasury)).readBigUInt64LE(64)-beforeTo,79000000n);
 }
 assert.equal((await read(receipt)).readBigInt64LE(154),expected);assert.equal((await read(subscription)).readBigInt64LE(73),expected);
 assert.deepEqual(await read(new PublicKey(audit['receipt_test-usdc'])),original);
 audit.receipt_renewal=receipt.toBase58();check('Research renewal adds one calendar month to unexpired term; old receipt immutable');
}
await send('reviewer-role',ix('set_roles',[meta(operator,true,true),meta(config),meta(governance),meta(buyer),meta(permit(buyer),false,true),sys],Buffer.from([2])));
const report=new PublicKey(audit.record_report),review=pda('review',report,buyer.publicKey);
await send('attributed-review',ix('attest',[meta(buyer,true,true),meta(config),meta(permit(buyer)),meta(report),meta(review,false,true),sys],Buffer.from([0]),hash('SYNTHETIC review fixture, not independent assurance')),[buyer]);
audit.review=review.toBase58();check('separate-wallet review, same test operator custody');
const draft=new PublicKey(audit['record_ai-draft']),retraction=pda('retraction',draft),originalDraft=await read(draft);
await send('retract-draft',ix('retract',[meta(operator,true,true),meta(draft),meta(retraction,false,true),sys],hash('SYNTHETIC draft withdrawn')));
assert.deepEqual(await read(draft),originalDraft);audit.retraction=retraction.toBase58();check('retraction preserves original record');
const subject=hash('SYNTHETIC non-person account v145 random-purpose test'),trial=pda('trial',config,subject);
await send('consented-trial',ix('issue_trial',[meta(operator,true,true),meta(buyer,true),meta(config),meta(governance),meta(trial,false,true),sys],subject),[operator,buyer]);
const trialBytes=await read(trial);assert.equal(trialBytes.readBigInt64LE(112)-trialBytes.readBigInt64LE(104),86400n);audit.trial=trial.toBase58();check('two-signature 24-hour trial proof, no web entitlement');
if(audit.steps.resume?.status!=='finalized'){await send('pause',ix('set_paused',[meta(operator,true),meta(config,false,true),meta(governance,false,true)],Buffer.from([1])));assert.equal((await read(config))[40],1);}
await send('resume',ix('set_paused',[meta(operator,true),meta(config,false,true),meta(governance,false,true)],Buffer.from([0])));assert.equal((await read(config))[40],0);check('operator pause and resume');
if(audit.steps['rotate-back-accept']?.status==='finalized'){
 assert.deepEqual((await read(governance)).subarray(40,72),operator.publicKey.toBuffer());assert.equal((await read(governance))[136],0);
 check('guardian recovery and rotation completed; payments remain off');
}
if(!audit.checks.includes('guardian recovery and rotation completed; payments remain off')){
 const controls=(actor,name,...args)=>ix(name,[meta(actor,true),meta(config,false,true),meta(governance,false,true)],...args);
 const reject=async(name,instruction,signers)=>{const block=await rpc.getLatestBlockhash();const tx=new Transaction({feePayer:operator.publicKey,...block}).add(instruction);tx.sign(operator,...signers.filter(x=>x!==operator));const r=await rpc.simulateTransaction(tx);assert.ok(r.value.err,name);check(name+' (simulation)');};
 await reject('stranger cannot propose recovery',controls(buyer,'propose_authority',successor.publicKey.toBuffer()),[buyer]);
 await send('guardian-proposal',controls(guardian,'propose_authority',successor.publicKey.toBuffer()),[operator,guardian]);
 assert.equal((await read(governance))[136],0);check('recovery disables payments');
 await reject('wrong successor rejected',controls(buyer,'accept_authority'),[buyer]);
 await reject('cannot enable payments during recovery',controls(operator,'set_payments_enabled',Buffer.from([1])),[]);
 await send('successor-accepts',controls(successor,'accept_authority'),[operator,successor]);
 await reject('old operator cannot administer',controls(operator,'set_payments_enabled',Buffer.from([1])),[]);
 await send('successor-admin',ix('set_roles',[meta(successor,true,true),meta(config),meta(governance),meta(buyer),meta(permit(buyer),false,true),sys],Buffer.from([2])),[operator,successor]);
 await send('rotate-back-proposal',controls(successor,'propose_authority',operator.publicKey.toBuffer()),[operator,successor]);
 await send('rotate-back-accept',controls(operator,'accept_authority'));
 assert.deepEqual((await read(governance)).subarray(40,72),operator.publicKey.toBuffer());assert.equal((await read(governance))[136],0);
 check('guardian recovery and rotation completed; payments remain off');
}
audit.status='passed';audit.completedAt=new Date().toISOString();save();console.log(JSON.stringify({status:audit.status,checks:audit.checks.length,config:audit.config,programId:manifest.programId,productionEntitlements:false}));
