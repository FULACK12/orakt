import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const read=p=>readFile(new URL(p,import.meta.url),'utf8');
test('protocol marketing distinguishes verified Devnet from unaudited disabled mainnet',async()=>{
 const s=await read('../app/ProtocolSection.tsx');
 for(const expected of ['DEVNET DEPLOYED · MAINNET OFF','not received an independent security audit','existing Memo provenance','wallet-free','No promised returns','source','checks','?cluster=devnet','TEST_USDC','checkout remains disabled','devnet-deployment.json'])assert.ok(s.includes(expected),expected);
 assert.doesNotMatch(s,/BaAX5nB9|onClick|signTransaction|sendTransaction/);
 for(const ix of ['open_series','publish_version','attest','retract','purchase','issue_trial','set_roles','set_paused'])assert.ok(s.includes(ix),ix);
});
test('homepage uses existing language state and contract section without changing access routes',async()=>{
 const landing=await read('../app/OraktLanding.tsx'),worker=await read('../worker/index.ts');
 assert.match(landing,/<ProtocolSection language=\{language\}/);
 const release=await read('../app/ReleaseStatus.tsx');
 assert.equal(worker.match(/version: "(\d+)"/)?.[1],release.match(/const VERSION = "(\d+)"/)?.[1]);
 assert.match(worker,/url.pathname.startsWith\("\/admin\/"\)&&!member.access.permissions.manageUsers/);
 assert.doesNotMatch(worker,/\/api\/protocol\/purchase/);
});
