import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {inspectSnapshot,readDevnetReadiness} from '../tools/devnet-readiness.mjs';
const m=JSON.parse(readFileSync(new URL('../devnet-deployment-v145.json',import.meta.url)));
const genesis='EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG';
const reply=result=>Response.json({jsonrpc:'2.0',id:1,result});
test('wrong network fails before account fetch; no write method or custom URL',async()=>{
  const seen=[];await assert.rejects(readDevnetReadiness(async(url,options)=>{seen.push({url,body:JSON.parse(options.body)});return reply('not-devnet');}),/wrong_network/);
  assert.deepEqual(seen,[{url:'https://api.devnet.solana.com',body:{jsonrpc:'2.0',id:1,method:'getGenesisHash',params:[]}}]);
});
test('only pinned public accounts are fetched at finalized minimum deployment slot',async()=>{
  const seen=[];await assert.rejects(readDevnetReadiness(async(url,options)=>{const body=JSON.parse(options.body);seen.push(body);return reply(body.method==='getGenesisHash'?genesis:{context:{slot:m.deploySlot},value:[null,null,null,null]});}),/account_metadata/);
  assert.deepEqual(seen.map(x=>x.method),['getGenesisHash','getMultipleAccounts']);
  assert.deepEqual(seen[1].params,[[m.programId,m.programData,m.config,m.governance],{commitment:'finalized',encoding:'base64',minContextSlot:m.deploySlot}]);
});
for(const [name,response,error] of [['HTTP',()=>new Response('',{status:503}),/rpc_unavailable/],['RPC',()=>Response.json({error:{code:-32005}}),/rpc_error/],['missing result',()=>Response.json({id:1}),/rpc_error/],['oversize',()=>new Response('x'.repeat(2000001)),/rpc_response_too_large/]])test(`fails closed on ${name}`,async()=>{await assert.rejects(readDevnetReadiness(async()=>response()),error);});
test('truncated and stale snapshots cannot be certified',()=>{
  assert.throws(()=>inspectSnapshot('mainnet',{}),/wrong_network/);
  for(const s of [{},{context:{slot:m.deploySlot-1},value:Array(4).fill(null)},{context:{slot:m.deploySlot},value:[]},{context:{slot:NaN},value:Array(4).fill(null)}])assert.throws(()=>inspectSnapshot(genesis,s),/stale_or_incomplete/);
});
test('substituted owners, executability and encoding fail before parsing',()=>{
  for(const a of [{owner:'wrong',executable:true,data:['','base64']},{owner:'BPFLoaderUpgradeab1e11111111111111111111111',executable:false,data:['','base64']},{owner:'BPFLoaderUpgradeab1e11111111111111111111111',executable:true,data:['','jsonParsed']}])assert.throws(()=>inspectSnapshot(genesis,{context:{slot:m.deploySlot},value:[a,null,null,null]}),/account_metadata/);
});
