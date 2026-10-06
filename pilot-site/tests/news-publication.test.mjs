import test from 'node:test';
import assert from 'node:assert/strict';
import {memberDatabase} from './member-fixture.mjs';
import {newsPublicationResponse,newsHash,newsMemo,validReceipt,unsignedMemo} from '../worker/news-publication.mjs';
import {localizeReport} from '../app/report-language.mjs';
const origin='https://orakt.test';
const member=(id,admin=false)=>({row:{id},access:{permissions:{manageUsers:admin}}});
const req=(v,host=origin)=>new Request(origin+'/api/news-publication',v?{method:'POST',headers:{Origin:host,'Content-Type':'application/json','X-ORAKT-News':'review'},body:JSON.stringify(v)}:{});
const payload={action:'submit',title:'Test sourced news',body:'An original, sourced summary for review. '.repeat(5),sourceUrls:['https://example.com/source'],eventDate:'2025-08-01',rightsConfirmed:true};
test('news is durable, private until approved, and review is admin-only with conflict protection',async t=>{
 const {DB,sql}=memberDatabase();t.after(()=>sql.close());const env={DB},a=member('author'),b=member('other'),admin=member('reviewer',true);
 assert.equal((await newsPublicationResponse(req(payload,'https://evil.test'),env,a)).status,403);
 assert.equal((await newsPublicationResponse(req({...payload,sourceUrls:['javascript:alert(1)']}),env,a)).status,400);
 const sent=await newsPublicationResponse(req(payload),env,a);assert.equal(sent.status,201);const {id}=await sent.json();
 await newsPublicationResponse(req(payload),env,a);assert.equal(sql.prepare('SELECT count(*) n FROM news_submissions').get().n,1);
 assert.equal((await (await newsPublicationResponse(req(),env,b)).json()).items.length,0);
 assert.equal((await newsPublicationResponse(req({action:'prepare',id,wallet:'11111111111111111111111111111111'}),env,a)).status,409);
 const review={action:'review',id,decision:'approved',note:'Reviewed original source and publication rights.'};
 assert.equal((await newsPublicationResponse(req(review),env,a)).status,403);
 assert.equal((await newsPublicationResponse(req(review),env,admin)).status,200);
 assert.equal((await newsPublicationResponse(req(review),env,admin)).status,409);
 const visible=(await (await newsPublicationResponse(req(),env,b)).json()).items[0];assert.equal(visible.state,'approved');assert.equal(visible.canAnchor,false);assert.equal(visible.chainState,'not_anchored');assert.equal(visible.author_id,undefined);
 assert.equal((await newsPublicationResponse(req({action:'prepare',id,wallet:'11111111111111111111111111111111'}),env,b)).status,404);
});
test('hash includes immutable content and receipt must match single memo, signer and successful transaction',()=>{
 assert.notEqual(newsHash(payload),newsHash({...payload,body:'different'}));
 const row={id:'news-one',content_hash:'a'.repeat(64),wallet:'11111111111111111111111111111111'};
 const tx={meta:{err:null},transaction:{message:{accountKeys:[{pubkey:row.wallet,signer:true}],instructions:[{programId:'MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr',parsed:newsMemo(row)}]}}};
 assert.equal(validReceipt(tx,row),true);assert.equal(validReceipt({...tx,meta:{err:'failed'}},row),false);
 assert.equal(validReceipt(tx,{...row,content_hash:'b'.repeat(64)}),false);
 tx.transaction.message.instructions.push({programId:'transfer'});assert.equal(validReceipt(tx,row),false);
 const bytes=unsignedMemo(row.wallet,row.wallet,newsMemo(row));assert.equal(bytes[0],1);assert.equal(bytes[65],1);assert.ok(bytes.length<1232);
});
test('report language changes actual content without altering financial values or source metadata',()=>{
 const r={question:'中文',confidence:40,evidence:[{value:100}],translations:{en:{question:'English'}}};const en=localizeReport(r,'en');assert.equal(en.question,'English');assert.equal(en.confidence,40);assert.equal(en.evidence[0].value,100);assert.equal(localizeReport(r,'zh').question,'中文');assert.equal(localizeReport(null,'en'),null);
});
