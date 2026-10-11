// Test-only upload buffer. No deployment, upgrade, mainnet or production wallet.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolve,join} from 'node:path';
import {createRequire} from 'node:module';
const workspace=fileURLToPath(new URL('../../../',import.meta.url)),root=resolve(workspace,'.tmp/orakt-devnet-v145');
const require=createRequire(join(root,existsSync(join(root,'client/package.json'))?'client/package.json':'../orakt-devnet-v144/client/package.json'));
const {Connection,Keypair,PublicKey,SystemProgram,Transaction,TransactionInstruction}=require('@solana/web3.js');
const rpc=new Connection('https://api.devnet.solana.com',{commitment:'finalized',disableRetryOnRateLimit:true});
assert.equal(await rpc.getGenesisHash(),'EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG');
const manifest=JSON.parse(readFileSync(join(root,'manifest.json')));assert.equal(manifest.testOnly,true);
const operator=Keypair.fromSecretKey(Uint8Array.from(JSON.parse(readFileSync(join(root,'operator-keypair.json')))));
assert.equal(operator.publicKey.toBase58(),manifest.operator);
assert.ok(!await rpc.getAccountInfo(new PublicKey(manifest.programId)),'program already deployed');
const path=join(root,'buffer-keypair.json');if(!existsSync(path))writeFileSync(path,JSON.stringify([...Keypair.generate().secretKey]),{flag:'wx',mode:0o600});
const buffer=Keypair.fromSecretKey(Uint8Array.from(JSON.parse(readFileSync(path))));
const loader=new PublicKey('BPFLoaderUpgradeab1e11111111111111111111111');
const binary=readFileSync(resolve(workspace,'.tmp/orakt-solana-build-cache/devnet-source/target/deploy/orakt_protocol.so'));
const account=await rpc.getAccountInfo(buffer.publicKey);
if(!account){
 const previousPath=join(root,'buffer-create.json');
 if(existsSync(previousPath)){
  const previous=JSON.parse(readFileSync(previousPath));assert.equal(previous.buffer,buffer.publicKey.toBase58());
  const status=(await rpc.getSignatureStatuses([previous.signature],{searchTransactionHistory:true})).value[0];
  assert.ok(!status||status.err,'Previous successful/pending buffer transaction must be reconciled, not replaced');
  assert.ok(status?.err||(Number.isSafeInteger(previous.lastValidBlockHeight)&&await rpc.getBlockHeight()>previous.lastValidBlockHeight),'Previous buffer transaction can still land; retain its signature');
 }
 const rent=await rpc.getMinimumBalanceForRentExemption(binary.length+37);
 assert.ok(rent<3e9&&await rpc.getBalance(operator.publicKey)>rent+50000000,'test budget insufficient');
 const block=await rpc.getLatestBlockhash();
 const tx=new Transaction({feePayer:operator.publicKey,...block}).add(SystemProgram.createAccount({fromPubkey:operator.publicKey,newAccountPubkey:buffer.publicKey,space:binary.length+37,lamports:rent,programId:loader}),new TransactionInstruction({programId:loader,keys:[{pubkey:buffer.publicKey,isSigner:false,isWritable:true},{pubkey:operator.publicKey,isSigner:false,isWritable:false}],data:Buffer.alloc(4)}));
 tx.sign(operator,buffer);const raw=tx.serialize();const bs58=require('bs58');
 const signature=bs58.encode(tx.signature);
 // Buffer account public address makes any uncertain broadcast reconcilable.
 writeFileSync(join(root,'buffer-create.json'),JSON.stringify({network:'devnet',signature,buffer:buffer.publicKey.toBase58(),rentLamports:rent,lastValidBlockHeight:block.lastValidBlockHeight}));
 await rpc.sendRawTransaction(raw);
 for(let n=0;n<60;n++){const s=(await rpc.getSignatureStatuses([signature],{searchTransactionHistory:true})).value[0];assert.ok(!s?.err);if(s?.confirmationStatus==='finalized')break;if(n===59)throw Error('pending buffer; retain signature');await new Promise(r=>setTimeout(r,1500));}
}
const verified=await rpc.getAccountInfo(buffer.publicKey);assert.ok(verified?.owner.equals(loader));assert.equal(verified.data.length,binary.length+37);assert.equal(verified.data.readUInt32LE(0),1);assert.deepEqual(verified.data.subarray(5,37),operator.publicKey.toBuffer());
console.log(JSON.stringify({network:'devnet',buffer:buffer.publicKey.toBase58(),bytes:binary.length,status:'ready_for_upload'}));
