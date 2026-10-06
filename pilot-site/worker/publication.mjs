import {createHash} from 'node:crypto';
const json=(data,status=200)=>Response.json(data,{status,headers:{'Cache-Control':'private, no-store'}});
export async function publicationResponse(request,env,member,records){
 if(!member.access.permissions.manageUsers)return json({error:'admin_required'},403);
 if(request.method==='GET'){
  const rows=await env.DB.prepare('SELECT id,report_id AS reportId,payload_hash AS payloadHash,kind,state,created_at AS createdAt FROM publication_requests ORDER BY created_at DESC LIMIT 100').bind().all();
  return json({requests:rows.results});
 }
 if(request.method!=='POST')return json({error:'method_not_allowed'},405);
 const url=new URL(request.url);
 if(request.headers.get('Origin')!==url.origin||request.headers.get('X-ORAKT-Publish')!=='review'||!request.headers.get('Content-Type')?.startsWith('application/json'))return json({error:'cross_origin_request'},403);
 const reader=request.body?.getReader();if(!reader)return json({error:'invalid_request'},400);
 let size=0,body='';const decoder=new TextDecoder();
 while(true){const {value,done}=await reader.read();if(done)break;size+=value.length;if(size>2048){await reader.cancel();return json({error:'request_too_large'},413);}body+=decoder.decode(value,{stream:true});}
 let input;try{input=JSON.parse(body+decoder.decode());}catch{return json({error:'invalid_request'},400);}
 if(!input||!['site_review','solana_devnet'].includes(input.kind)||Object.keys(input).some(k=>!['reportId','payloadHash','kind'].includes(k)))return json({error:'invalid_request'},400);
 const record=records.find(r=>r.reportId===input.reportId&&r.payloadHash===input.payloadHash);
 if(!record)return json({error:'reviewed_revision_required'},409);
 const id=createHash('sha256').update(`${record.reportId}:${record.payloadHash}:${input.kind}`).digest('hex');
 await env.DB.prepare("INSERT INTO publication_requests(id,report_id,payload_hash,kind,state,actor_id,created_at) VALUES(?,?,?,?, 'requested',?,?) ON CONFLICT(id) DO NOTHING").bind(id,record.reportId,record.payloadHash,input.kind,member.row.id,Date.now()).run();
 return json({id,state:'requested',broadcast:false,detail:'Review request saved; no transaction or automatic deployment performed.'});
}
