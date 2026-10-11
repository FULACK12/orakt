// Public finalized accounts only. Reproducible decoder fixture, not wallet state.
import {writeFileSync} from 'node:fs';
import {readMeteora,devnetRpc} from '../worker/meteora-reader.mjs';
let snapshot;
const result=await readMeteora(async(method,params)=>{const data=await devnetRpc(method,params);if(method==='getMultipleAccounts')snapshot=data;return data;});
writeFileSync(new URL('../tests/meteora-live-fixture.mjs',import.meta.url),'// Public Devnet account snapshot captured '+new Date().toISOString()+'. Not current prices.\nexport default '+JSON.stringify(snapshot)+';\n');
console.log(JSON.stringify({slot:result.slot,evidenceVerified:result.evidenceVerified,quoteReserve:result.quoteReserve}));
