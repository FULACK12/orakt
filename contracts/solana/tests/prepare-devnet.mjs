// Create a SEPARATE test deployment identity and explicitly fake Devnet mints.
// Never use these disposable keys on mainnet. Nothing here reads Phantom secrets.
import {mkdirSync,existsSync,readFileSync,writeFileSync,readdirSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
const require=createRequire(new URL('../../../pilot-site/package.json',import.meta.url));
const {Keypair}=require('@solana/web3.js');
const source=fileURLToPath(new URL('../',import.meta.url));
function copy(from,to){for(const entry of readdirSync(from,{withFileTypes:true})){const src=join(from,entry.name),dst=join(to,entry.name);if(entry.isDirectory()){mkdirSync(dst,{recursive:true});copy(src,dst);}else if(entry.isFile())writeFileSync(dst,readFileSync(src));}}
const root=resolve(source,'../../.tmp/orakt-devnet-v145');
mkdirSync(root,{recursive:true});
// Reuse only the isolated Devnet fee payer, never a production/Phantom secret.
const operatorFile=join(root,'operator-keypair.json');
const priorOperator=resolve(source,'../../.tmp/orakt-devnet-v144/operator-keypair.json');
if(!existsSync(operatorFile)&&existsSync(priorOperator))writeFileSync(operatorFile,readFileSync(priorOperator),{mode:0o600,flag:'wx'});
const pairs={};for(const name of ['program','operator','test-usdc','test-usdt','buyer','guardian','successor']){const file=join(root,name+'-keypair.json');if(!existsSync(file))writeFileSync(file,JSON.stringify([...Keypair.generate().secretKey]),{mode:0o600,flag:'wx'});pairs[name]=Keypair.fromSecretKey(Uint8Array.from(JSON.parse(readFileSync(file,'utf8')))).publicKey.toBase58();}
const build=join(root,'source');mkdirSync(build,{recursive:true});
for(const f of ['Cargo.toml','Cargo.lock','Anchor.toml'])writeFileSync(join(build,f),readFileSync(join(source,f)));
mkdirSync(join(build,'programs'),{recursive:true});copy(join(source,'programs'),join(build,'programs'));
const path=join(build,'programs/orakt-protocol/src/lib.rs');let code=readFileSync(path,'utf8');
for(const [from,to]of [['BaAX5nB9yxMh5K1tdEserFDq7MMcisVGVNshrVNLqDyn',pairs.program],['EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',pairs['test-usdc']],['Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',pairs['test-usdt']]]){if(!code.includes(from))throw Error('source identity mismatch');code=code.replaceAll(from,to);}
writeFileSync(path,code);
writeFileSync(join(build,'Anchor.toml'),readFileSync(join(build,'Anchor.toml'),'utf8').replaceAll('BaAX5nB9yxMh5K1tdEserFDq7MMcisVGVNshrVNLqDyn',pairs.program));
const manifest={network:'solana:devnet',genesis:'EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG',status:'prepared_not_deployed',testOnly:true,productionEntitlements:false,operatorCustody:'Disposable test-only operator; not Phantom or production authority',programId:pairs.program,operator:pairs.operator,mints:{TEST_USDC:pairs['test-usdc'],TEST_USDT:pairs['test-usdt']},buyer:pairs.buyer,sourceSha256:createHash('sha256').update(code).digest('hex')};
const manifestPath=join(root,'manifest.json');
if(existsSync(manifestPath)){
 const previous=JSON.parse(readFileSync(manifestPath));
 if(previous.status==='deployed_finalized'){
  if(previous.sourceSha256!==manifest.sourceSha256||previous.programId!==manifest.programId)throw Error('Existing deployed identity: create a new immutable deployment workspace for changed source');
  Object.assign(manifest,previous);
 }
}
writeFileSync(manifestPath,JSON.stringify(manifest,null,2));console.log(JSON.stringify({root,...manifest}));
