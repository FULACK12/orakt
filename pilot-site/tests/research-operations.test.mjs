import test from 'node:test';
import assert from 'node:assert/strict';
import {metricCount,economicValue,reportFilterDate} from '../app/metric-format.mjs';
import {publicationResponse} from '../worker/publication.mjs';
import {memberDatabase} from './member-fixture.mjs';
test('missing, invalid, zero and unit formats remain distinct',()=>{
 for(const value of [null,undefined,NaN,Infinity]){assert.equal(metricCount(value),'—');assert.equal(economicValue(value,'%'),'—');}
 assert.equal(metricCount(0),'0');assert.equal(economicValue(2.5,'%'),'2.5%');assert.equal(economicValue(1200,'people'),'1,200 people');assert.equal(economicValue(1200,'USD'),'$1,200.00');
});
test('historical evidence date is not generated date',()=>{
 const r={createdAt:'2026-10-06T00:00:00Z',historical:{asOf:'2025-08-01'}};
 assert.equal(reportFilterDate(r,'generated'),'2026-10-06');assert.equal(reportFilterDate(r,'evidence'),'2025-08-01');assert.equal(reportFilterDate({},'evidence'),'');
});
test('publication is admin-only, same-origin, reviewed hash and idempotent',async()=>{
 const {DB,sql}=memberDatabase();const env={DB},admin={row:{id:'owner'},access:{permissions:{manageUsers:true}}},viewer={access:{permissions:{manageUsers:false}}};
 const records=[{reportId:'local-707',payloadHash:'a'.repeat(64)}];
 const make=(body,origin='https://orakt.test')=>new Request('https://orakt.test/api/publication/requests',{method:'POST',headers:{Origin:origin,'Content-Type':'application/json','X-ORAKT-Publish':'review'},body:JSON.stringify(body)});
 const payload={...records[0],kind:'solana_devnet'};
 assert.equal((await publicationResponse(make(payload),env,viewer,records)).status,403);
 assert.equal((await publicationResponse(make(payload,'https://evil.test'),env,admin,records)).status,403);
 assert.equal((await publicationResponse(make({...payload,payloadHash:'b'.repeat(64)}),env,admin,records)).status,409);
 for(let i=0;i<2;i++){const r=await publicationResponse(make(payload),env,admin,records);assert.equal(r.status,200);assert.equal((await r.json()).broadcast,false);}
 assert.equal(sql.prepare('SELECT count(*) AS n FROM publication_requests').get().n,1);
});
