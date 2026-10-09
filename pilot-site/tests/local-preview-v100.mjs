// Isolated UI fixture: loopback only, in-memory database, never real user accounts.
import http from 'node:http';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {memberDatabase} from './member-fixture.mjs';
import {memberFor} from '../worker/membership.mjs';
import worker from '../dist/server/index.js';
const {DB}=memberDatabase(),root=path.resolve('dist/client'),publicRoot=path.resolve('public');
const types={'.js':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.webp':'image/webp','.woff2':'font/woff2'};
async function asset(request){const pathname=decodeURIComponent(new URL(request.url).pathname);for(const folder of [root,publicRoot]){const file=path.resolve(folder,'.'+pathname);if(!file.startsWith(folder+path.sep))continue;try{return new Response(await readFile(file),{headers:{'Content-Type':types[path.extname(file)]||'application/octet-stream'}});}catch{}}return new Response('Not found',{status:404});}
const env={DB,ASSETS:{fetch:asset},PILOT_SESSION_SECRET:'local-fixture-only-not-a-production-secret'};
const identity={provider:'chatgpt',subject:'local-preview-reviewer',displayName:'Local QA only',accountId:'local-preview-reviewer',createdAt:null};
const member=await memberFor(env,identity);env.ORAKT_ADMIN_ACCOUNT_ID=member.row.id;
http.createServer(async(req,res)=>{try{if(req.headers.host!=='127.0.0.1:4179'){res.writeHead(403).end();return;}const headers=new Headers();for(const [k,v] of Object.entries(req.headers))if(typeof v==='string')headers.set(k,v);headers.set('oai-authenticated-user-id',identity.subject);headers.set('oai-authenticated-user-email','fixture@example.invalid');const parts=[];for await(const p of req)parts.push(p);const request=new Request('http://127.0.0.1:4179'+req.url,{method:req.method,headers,...(!['GET','HEAD'].includes(req.method)?{body:Buffer.concat(parts)}:{})});const response=(/^\/(?:assets|_next|brand)\//.test(req.url))?await asset(request):await worker.fetch(request,env,{waitUntil(){},passThroughOnException(){}});res.writeHead(response.status,Object.fromEntries(response.headers));res.end(Buffer.from(await response.arrayBuffer()));}catch(e){console.error(e.message);res.writeHead(500).end('Local preview error');}}).listen(4179,'127.0.0.1',()=>console.log('Local QA http://127.0.0.1:4179 (isolated accounts)'));
