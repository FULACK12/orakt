const json=(body,status=200)=>Response.json(body,{status});
export function validTickers(value,allowed){
 if(!Array.isArray(value)||value.length>50||value.some(v=>typeof v!=='string'||!allowed.has(v)))throw Error('invalid_tickers');
 return [...new Set(value)];
}
export async function watchlistResponse(request,env,member,companies){
 if(!env.DB)return json({error:'storage_unavailable'},503);
 if(member.access.status!=='active')return json({error:'account_suspended'},403);
 const allowed=new Set(companies.map(c=>c.ticker));
 try{
  if(request.method==='GET'){
   const row=await env.DB.prepare('SELECT tickers, updated_at FROM member_watchlists WHERE member_id = ?').bind(member.row.id).first();
   return json({tickers:row?JSON.parse(row.tickers).filter(t=>allowed.has(t)):[],updatedAt:row?.updated_at||null,companies:companies.map(c=>({ticker:c.ticker,name:c.companyName,market:c.marketRegion}))});
  }
  if(request.method!=='PUT')return json({error:'method_not_allowed'},405);
  if(request.headers.get('Origin')!==new URL(request.url).origin||request.headers.get('X-ORAKT-Preferences')!=='watchlist')return json({error:'cross_origin_request'},403);
  if(!request.headers.get('Content-Type')?.startsWith('application/json'))return json({error:'invalid_request'},400);
  const reader=request.body?.getReader();if(!reader)return json({error:'invalid_request'},400);
  let size=0,chunks=[];while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>4096){await reader.cancel();return json({error:'body_too_large'},413);}chunks.push(value);}
  let body,tickers;try{body=JSON.parse(new TextDecoder().decode(new Uint8Array(chunks.flatMap(v=>[...v]))));if(Object.keys(body).some(k=>k!=='tickers'))throw Error();tickers=validTickers(body.tickers,allowed);}catch{return json({error:'invalid_tickers'},400);}
  const now=Date.now();
  await env.DB.prepare('INSERT INTO member_watchlists (member_id, tickers, updated_at) VALUES (?, ?, ?) ON CONFLICT(member_id) DO UPDATE SET tickers = excluded.tickers, updated_at = excluded.updated_at').bind(member.row.id,JSON.stringify(tickers),now).run();
  return json({tickers,updatedAt:now});
 }catch{return json({error:'preferences_unavailable'},503);}
}
