import assert from "node:assert/strict";
import test from "node:test";
import {readFile} from "node:fs/promises";
import {authJsonGet,withAuthLock} from "../app/access/auth-request.mjs";

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const queuedLock = {request(_name,{signal}) {
  return new Promise((_,reject) => {
    if(signal.aborted) reject(signal.reason);
    else signal.addEventListener("abort",()=>reject(signal.reason),{once:true});
  });
}};

test("setup GET has bounded waiting, same-origin credentials and no automatic retry",async()=>{
  let calls=0,captured;
  await assert.rejects(authJsonGet("/setup",{timeoutMs:15,fetchImpl:async(_url,init)=>{
    calls++;captured=init;return new Promise(()=>{});
  }}),{name:"TimeoutError"});
  assert.equal(calls,1);assert.equal(captured.signal.aborted,true);
  assert.equal(captured.credentials,"same-origin");assert.equal(captured.cache,"no-store");
});
test("setup deadline includes a stalled JSON body and rejects a late response",async()=>{
  let finish;
  const result=authJsonGet("/session",{timeoutMs:15,fetchImpl:async()=>({ok:true,json:()=>new Promise(resolve=>{finish=resolve;})})});
  await assert.rejects(result,{name:"TimeoutError"});
  finish({authorized:true});
  await assert.rejects(result,{name:"TimeoutError"});
});
test("unmount cancels read and pre-aborted reads never fetch",async()=>{
  const c=new AbortController();let calls=0;
  const fetchImpl=async()=>{calls++;return new Promise(()=>{});};
  const pending=authJsonGet("/setup",{signal:c.signal,timeoutMs:100,fetchImpl});
  c.abort();await assert.rejects(pending,{name:"AbortError"});
  await assert.rejects(authJsonGet("/setup",{signal:c.signal,fetchImpl}),{name:"AbortError"});
  assert.equal(calls,1);
});
test("successful setup cleans deadline and can be manually retried after failure",async()=>{
  await assert.rejects(authJsonGet("/setup",{fetchImpl:async()=>({ok:false})}),/auth_setup_unavailable/);
  let signal;
  const value=await authJsonGet("/setup",{timeoutMs:15,fetchImpl:async(_url,init)=>{signal=init.signal;return {ok:true,json:async()=>({enabled:true})};}});
  assert.deepEqual(value,{enabled:true});await sleep(25);assert.equal(signal.aborted,false);
});
test("queued lock timeout never enters write action",async()=>{
  let writes=0;
  await assert.rejects(withAuthLock(queuedLock,"test",async()=>{writes++;},{timeoutMs:15}),{name:"TimeoutError",message:"auth_lock_timeout"});
  assert.equal(writes,0);
});
test("unmount cancels queued lock before registration starts",async()=>{
  const c=new AbortController();let writes=0;
  const result=withAuthLock(queuedLock,"test",async()=>{writes++;},{signal:c.signal,timeoutMs:100});
  c.abort();await assert.rejects(result,{name:"AbortError"});assert.equal(writes,0);
});
test("acquired registration holds lock beyond queue deadline and unmount until write finishes",async()=>{
  const c=new AbortController();let held=false,lockSignal,writes=0;
  const locks={async request(_name,{signal},action){held=true;lockSignal=signal;try{return await action();}finally{held=false;}}};
  const result=withAuthLock(locks,"test",async()=>{writes++;await sleep(45);return {recoveryKey:"test-only"};},{signal:c.signal,timeoutMs:10});
  c.abort();await sleep(20);assert.equal(held,true);assert.equal(lockSignal.aborted,false);
  assert.deepEqual(await result,{recoveryKey:"test-only"});assert.equal(held,false);assert.equal(writes,1);
});
test("failed write releases lock with no automatic retry",async()=>{
  let writes=0,held=false;
  const locks={async request(_name,_options,action){held=true;try{return await action();}finally{held=false;}}};
  await assert.rejects(withAuthLock(locks,"test",async()=>{writes++;throw new Error("registration_unavailable");}),/registration_unavailable/);
  assert.equal(writes,1);assert.equal(held,false);
});
test("local username pattern is valid with browser v-mode and rejects unsupported names",async()=>{
  const source=await readFile(new URL("../app/access/LocalLogin.tsx",import.meta.url),"utf8");
  const literal=source.match(/pattern=\{("[^"\n]+")\}/)?.[1];assert.ok(literal);
  const re=new RegExp("^(?:"+JSON.parse(literal)+")$","v");
  for(const name of ["user-1","user_2","Alice123"])assert.equal(re.test(name),true,name);
  for(const name of ["_user","abc","user name","name@example.com"])assert.equal(re.test(name),false,name);
});
