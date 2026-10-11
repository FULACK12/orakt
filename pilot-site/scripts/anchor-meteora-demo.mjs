// Commit ONLY the public synthetic integration metadata; no mainnet or user keys.
import {Connection,Keypair,PublicKey,SystemProgram,Transaction,TransactionInstruction} from '@solana/web3.js';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
import assert from 'node:assert/strict';
import {DEMO_EVIDENCE} from '../worker/meteora-demo.mjs';
const root=resolve(import.meta.dirname,'../../.tmp/orakt-meteora-v146'),file=resolve(root,'anchor.json');
const rpc=new Connection('https://api.devnet.solana.com','finalized');
assert.equal(await rpc.getGenesisHash(),'EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG');
const p=new PublicKey('2NkTGAB6peUsDzCxZQsyzntpAeuNuoveXe2kEsUKQFa4');
const signer=Keypair.fromSecretKey(Uint8Array.from(JSON.parse(readFileSync(resolve(root,'../orakt-devnet-v145/operator-keypair.json')))));
const sha=x=>createHash('sha256').update(x).digest(),u32=x=>{let b=Buffer.alloc(4);b.writeUInt32LE(x);return b;};
const pda=(...s)=>PublicKey.findProgramAddressSync(s.map(x=>typeof x==='string'?Buffer.from(x):x instanceof PublicKey?x.toBuffer():x),p)[0];
const config=pda('config',signer.publicKey),permit=pda('permit',config,signer.publicKey),item=sha('orakt-meteora-devnet-v146-integration');
const series=pda('series',config,signer.publicKey,item),record=pda('record',series,u32(1));
const canonical=JSON.stringify(DEMO_EVIDENCE),content=sha(canonical),rootHash=sha(Buffer.concat([Buffer.from('orakt-evidence-leaf-v1'),content]));
const meta=(key,isSigner=false,isWritable=false)=>({pubkey:key,isSigner,isWritable});
const ix=(name,keys,...data)=>new TransactionInstruction({programId:p,keys,data:Buffer.concat([sha('global:'+name).subarray(0,8),...data])});
let checkpoint=existsSync(file)?JSON.parse(readFileSync(file)):null;
if(!checkpoint){
 const block=await rpc.getLatestBlockhash(),tx=new Transaction({feePayer:signer.publicKey,...block}).add(
 ix('open_series',[meta(signer.publicKey,true,true),meta(config),meta(permit),meta(series,false,true),meta(SystemProgram.programId)],item,Buffer.from([0])),
 ix('publish_version',[meta(signer.publicKey,true,true),meta(config),meta(permit),meta(series,false,true),meta(record,false,true),meta(SystemProgram.programId)],u32(1),content,rootHash,Buffer.alloc(32)),
 ix('verify_evidence',[meta(record)],content,u32(0)));
 tx.sign(signer);const sim=await rpc.simulateTransaction(tx);assert.equal(sim.value.err,null,JSON.stringify(sim.value.logs));
 checkpoint={raw:tx.serialize().toString('base64'),...block};writeFileSync(file,JSON.stringify(checkpoint));
}
if(!checkpoint.signature){checkpoint.signature=await rpc.sendRawTransaction(Buffer.from(checkpoint.raw,'base64'));writeFileSync(file,JSON.stringify(checkpoint));}
let done=false;for(let n=0;n<50;n++){const s=(await rpc.getSignatureStatuses([checkpoint.signature],{searchTransactionHistory:true})).value[0];assert.ok(!s?.err);if(s?.confirmationStatus==='finalized'){done=true;break;}await new Promise(r=>setTimeout(r,1500));}assert.ok(done,'Pending original transaction; do not create a replacement');
const account=await rpc.getAccountInfo(record);assert.equal(account.owner.toBase58(),p.toBase58());assert.deepEqual(account.data.subarray(109,141),content);assert.deepEqual(account.data.subarray(141,173),rootHash);
const proof={network:'solana:devnet',program:p.toBase58(),config:config.toBase58(),series:series.toBase58(),record:record.toBase58(),version:1,contentHash:content.toString('hex'),evidenceRoot:rootHash.toString('hex'),leafHash:content.toString('hex'),siblings:[],signature:checkpoint.signature,finalizedAt:new Date().toISOString(),canonicalization:'UTF-8 JSON.stringify(DEMO_EVIDENCE); property order retained in meteora-demo.mjs',synthetic:true,independentAudit:false};
writeFileSync(new URL('../worker/meteora-proof.mjs',import.meta.url),'// Public, finalized Devnet evidence only. No signing material.\nexport default '+JSON.stringify(proof)+';\n');
writeFileSync(resolve(root,'public-evidence.json'),JSON.stringify({evidence:DEMO_EVIDENCE,canonical,proof},null,2));
console.log(JSON.stringify(proof,null,2));
