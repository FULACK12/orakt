// Two isolated in-memory QA surfaces. Never a production authentication path.
import http from 'node:http';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {memberDatabase} from './member-fixture.mjs';
import {memberFor} from '../worker/membership.mjs';
import worker from '../dist/server/index.js';
const root=path.resolve('dist/client'),publicRoot=path.resolve('public');
const types={'.js':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.webp':'image/webp','.woff2':'font/woff2'};
async function asset(request){const pathname=decodeURIComponent(new URL(request.url).pathname);for(const folder of [root,publicRoot]){const file=path.resolve(folder,'.'+pathname);if(!file.startsWith(folder+path.sep))continue;try{return new Response(await readFile(file),{headers:{'Content-Type':types[path.extname(file)]||'application/octet-stream'}});}catch{}}return new Response('Not found',{status:404});}
for(const [port,admin] of [[4179,true],[4180,false]]){
 const {DB}=memberDatabase(),env={DB,ASSETS:{fetch:asset},PILOT_SESSION_SECRET:'isolated-preview-only-140'};
 const identity={provider:'chatgpt',subject:admin?'preview-admin':'preview-member',displayName:admin?'Admin QA':'Member QA',accountId:'fixture',createdAt:null};
 const m=await memberFor(env,identity);if(admin)env.ORAKT_ADMIN_ACCOUNT_ID=m.row.id;
 http.createServer(async(req,res)=>{try{if(req.headers.host!==`127.0.0.1:${port}`){res.writeHead(403).end();return;}const headers=new Headers();for(const [k,v] of Object.entries(req.headers))if(typeof v==='string')headers.set(k,v);headers.set('oai-authenticated-user-id',identity.subject);headers.set('oai-authenticated-user-email','fixture@example.invalid');const chunks=[];for await(const c of req)chunks.push(c);const r=new Request(`http://127.0.0.1:${port}`+req.url,{method:req.method,headers,...(!['GET','HEAD'].includes(req.method)?{body:Buffer.concat(chunks)}:{})});const response=/^\/(?:assets|_next|brand)\//.test(req.url)?await asset(r):await worker.fetch(r,env,{waitUntil(){},passThroughOnException(){}});res.writeHead(response.status,Object.fromEntries(response.headers));res.end(Buffer.from(await response.arrayBuffer()));}catch(e){console.error(e.message);res.writeHead(500).end('QA error');}}).listen(port,'127.0.0.1',()=>console.log(`Local QA http://127.0.0.1:${port} (${admin?'admin':'member'} fixture)`));
}
