// Devnet-only deployment from the isolated prepared build. No mainnet switch.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
const workspace=fileURLToPath(new URL('../../../',import.meta.url));
const root=resolve(workspace,'.tmp/orakt-devnet-v144'),cache=resolve(workspace,'.tmp/orakt-solana-build-cache');
const require=createRequire(join(root,'client/package.json'));
const {Connection,PublicKey,Keypair}=require('@solana/web3.js');
const manifest=JSON.parse(readFileSync(join(root,'manifest.json'))),binary=readFileSync(join(cache,'devnet-source/target/deploy/orakt_protocol.so'));
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
assert.equal(manifest.network,'solana:devnet');assert.equal(manifest.testOnly,true);assert.equal(manifest.productionEntitlements,false);
assert.equal(sha(readFileSync(join(cache,'devnet-source/programs/orakt-protocol/src/lib.rs'))),manifest.sourceSha256);
assert.equal(binary.readUInt32LE(48),3,'SBPFv3 architecture');
const idl=JSON.parse(readFileSync(join(cache,'devnet-source/target/idl/orakt_protocol.json')));assert.equal(idl.address,manifest.programId);
const rpc=new Connection('https://api.devnet.solana.com','finalized');
assert.equal(await rpc.getGenesisHash(),'EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG');
const operator=new PublicKey(manifest.operator),program=new PublicKey(manifest.programId),loader=new PublicKey('BPFLoaderUpgradeab1e11111111111111111111111');
const [programData]=PublicKey.findProgramAddressSync([program.toBuffer()],loader);
let current=await rpc.getAccountInfo(program);
if(!current){
  const bufferFile=join(root,'buffer-keypair.json');
  if(!existsSync(bufferFile))writeFileSync(bufferFile,JSON.stringify([...Keypair.generate().secretKey]),{flag:'wx',mode:0o600});
  const buffer=Keypair.fromSecretKey(Uint8Array.from(JSON.parse(readFileSync(bufferFile)))).publicKey;
  const rent=await rpc.getMinimumBalanceForRentExemption(binary.length+45),balance=await rpc.getBalance(operator),bufferInfo=await rpc.getAccountInfo(buffer);
  const needed=rent+(bufferInfo?0:rent)+20_000_000;
  assert.ok(balance>=needed,'Need rent + resumable buffer + fees in test SOL');
  assert.ok(needed<5_000_000_000,'Test budget cap');
  const args=['run','--rm','--name','orakt-v144-devnet-deploy','-v',cache+':/cache:ro','-v',root+':/devnet:ro',
    'solanafoundation/anchor@sha256:21ab8a16e19df4301a198d7a55ab2988549aa2d996e6b5ad229c1d95b9f2d326',
    '/cache/agave/solana-release/bin/solana','--url',process.env.ORAKT_DEVNET_LOOPBACK_PROXY==='1'?'http://host.docker.internal:4194':'https://api.devnet.solana.com','--keypair','/devnet/operator-keypair.json',
    '--commitment','finalized','program','deploy','/cache/devnet-source/target/deploy/orakt_protocol.so',
    '--program-id','/devnet/program-keypair.json','--buffer','/devnet/buffer-keypair.json','--max-len',String(binary.length),'--use-rpc','--output','json'];
  console.log(JSON.stringify({network:manifest.network,programId:manifest.programId,bytes:binary.length,rentLamports:rent,balanceLamports:balance}));
  const result=spawnSync('docker',args,{encoding:'utf8',maxBuffer:10_000_000});
  // An explicit persistent buffer avoids CLI seed-phrase recovery output.
  if(result.status!==0){console.error('Devnet deploy exited '+result.status);console.error(result.stderr.replace(/(?:\r?\n)?(?:Recover|Seed phrase)[\s\S]*/i,' [recovery details withheld]'));process.exit(1);}
  const deployment=JSON.parse(result.stdout);writeFileSync(join(root,'deployment-cli.json'),JSON.stringify(deployment,null,2));console.log(JSON.stringify(deployment));
  current=await rpc.getAccountInfo(program);
}
assert.ok(current?.executable);assert.ok(current.owner.equals(loader));assert.equal(current.data.readUInt32LE(0),2);assert.deepEqual(current.data.subarray(4,36),programData.toBuffer());
const data=await rpc.getAccountInfo(programData);assert.ok(data.owner.equals(loader));assert.equal(data.data.readUInt32LE(0),3);assert.equal(data.data[12],1);assert.deepEqual(data.data.subarray(13,45),operator.toBuffer());
assert.deepEqual(data.data.subarray(45,45+binary.length),binary,'Finalized on-chain bytes must equal built binary');
manifest.status='deployed_finalized';manifest.programData=programData.toBase58();manifest.deploySlot=Number(data.data.readBigUInt64LE(4));manifest.binarySha256=sha(binary);manifest.binaryBytes=binary.length;manifest.verifiedAt=new Date().toISOString();manifest.upgradeAuthority=operator.toBase58();
writeFileSync(join(root,'manifest.json'),JSON.stringify(manifest,null,2));console.log(JSON.stringify(manifest));
