import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const read=p=>readFile(new URL(p,import.meta.url),'utf8');
test('protocol marketing separates source from a deployed audited program',async()=>{
 const s=await read('../app/ProtocolSection.tsx');
 for(const expected of ['NOT DEPLOYED','not received an independent security audit','existing Memo provenance','wallet-free','No promised returns','source','checks'])assert.ok(s.includes(expected),expected);
 assert.doesNotMatch(s,/BaAX5nB9|onClick|signTransaction|sendTransaction/);
 for(const ix of ['open_series','publish_version','attest','retract','purchase','issue_trial','set_roles','set_paused'])assert.ok(s.includes(ix),ix);
});
test('homepage uses existing language state and contract section without changing access routes',async()=>{
 const landing=await read('../app/OraktLanding.tsx'),worker=await read('../worker/index.ts');
 assert.match(landing,/<ProtocolSection language=\{language\}/);
 assert.match(worker,/version: "141"/);
 assert.match(worker,/url.pathname.startsWith\("\/admin\/"\)&&!member.access.permissions.manageUsers/);
 assert.doesNotMatch(worker,/\/api\/protocol\/purchase/);
});
