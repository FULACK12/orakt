// Low-rate continuation of an EXISTING Devnet buffer. Does not create accounts,
// deploy/upgrade a program, change authority, or operate on mainnet.
// Loader Write ABI: solana-loader-v3-interface 5.0.0 instruction.rs (bincode).
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolve,join} from 'node:path';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
const workspace=fileURLToPath(new URL('../../../',import.meta.url)),root=resolve(workspace,'.tmp/orakt-devnet-v144');
const require=createRequire(join(root,'client/package.json'));
const {Connection,PublicKey,Keypair,Transaction,TransactionInstruction}=require('@solana/web3.js');
const rpc=new Connection('https://api.devnet.solana.com',{commitment:'finalized',disableRetryOnRateLimit:true});
assert.equal(await rpc.getGenesisHash(),'EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG');
const manifest=JSON.parse(readFileSync(join(root,'manifest.json')));assert.equal(manifest.testOnly,true);
const getPair=n=>Keypair.fromSecretKey(Uint8Array.from(JSON.parse(readFileSync(join(root,n+'-keypair.json')))));
const operator=getPair('operator'),buffer=getPair('buffer').publicKey,loader=new PublicKey('BPFLoaderUpgradeab1e11111111111111111111111');
assert.equal(operator.publicKey.toBase58(),manifest.operator);assert.ok(!await rpc.getAccountInfo(new PublicKey(manifest.programId)),'Already deployed: do not upload again');
const binary=readFileSync(resolve(workspace,'.tmp/orakt-solana-build-cache/devnet-source/target/deploy/orakt_protocol.so'));
const before=await rpc.getAccountInfo(buffer);assert.ok(before.owner.equals(loader));assert.equal(before.data.readUInt32LE(0),1);assert.equal(before.data[4],1);assert.deepEqual(before.data.subarray(5,37),operator.publicKey.toBuffer());assert.equal(before.data.length,37+binary.length);
const auditPath=join(root,'buffer-upload.json'),audit=existsSync(auditPath)?JSON.parse(readFileSync(auditPath)):{network:'solana:devnet',buffer:buffer.toBase58(),binarySha256:createHash('sha256').update(binary).digest('hex'),writes:[]};
const save=()=>writeFileSync(auditPath,JSON.stringify(audit,null,2)),delay=ms=>new Promise(r=>setTimeout(r,ms));
const missing=[];for(let offset=0;offset<binary.length;offset+=900)if(!before.data.subarray(37+offset,37+Math.min(binary.length,offset+900)).equals(binary.subarray(offset,offset+900)))missing.push(offset);
console.log(JSON.stringify({missingChunks:missing.length,bytes:binary.length,buffer:buffer.toBase58()}));
for(let start=0;start<missing.length;start+=16){
 const block=await rpc.getLatestBlockhash('confirmed'),batch=[];
 for(const offset of missing.slice(start,start+16)){
  const chunk=binary.subarray(offset,offset+900),data=Buffer.alloc(16+chunk.length);data.writeUInt32LE(1,0);data.writeUInt32LE(offset,4);data.writeBigUInt64LE(BigInt(chunk.length),8);chunk.copy(data,16);
  const tx=new Transaction({feePayer:operator.publicKey,...block}).add(new TransactionInstruction({programId:loader,keys:[{pubkey:buffer,isSigner:false,isWritable:true},{pubkey:operator.publicKey,isSigner:true,isWritable:false}],data}));tx.sign(operator);
  const signature=await rpc.sendRawTransaction(tx.serialize(),{skipPreflight:false,maxRetries:2});batch.push(signature);audit.writes.push({offset,bytes:chunk.length,signature});save();await delay(550);
 }
 let finalized=false;
 for(let poll=0;poll<40;poll++){await delay(2500);const statuses=(await rpc.getSignatureStatuses(batch,{searchTransactionHistory:true})).value;assert.ok(statuses.every(s=>!s?.err),'Write failed; inspect saved signatures before retry');if(statuses.every(s=>s?.confirmationStatus==='finalized')){finalized=true;break;}}
 assert.ok(finalized,'Pending writes: verify original signatures before retry');console.log('FINALIZED buffer chunks '+Math.min(start+16,missing.length)+' / '+missing.length);
}
const after=await rpc.getAccountInfo(buffer);assert.deepEqual(after.data.subarray(37),binary);audit.status='byte_verified_finalized';audit.verifiedAt=new Date().toISOString();save();console.log('PASS complete Devnet buffer equals built SBPFv3 binary');
