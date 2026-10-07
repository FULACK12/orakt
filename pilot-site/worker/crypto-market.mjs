export const instruments=['BTC-USDT','ETH-USDT','SOL-USDT'];
const cached=new Map(),pending=new Map();
const num=v=>typeof v==='string'&&v.trim()!==''&&Number.isFinite(Number(v))?Number(v):NaN;
export function parseMarket(symbol,ticker,candles,now=Date.now()){
 if(ticker?.code!=='0'||candles?.code!=='0')throw Error('provider_error');
 const q=ticker.data?.find(v=>v.instId===symbol);if(!q)throw Error('missing_quote');
 const price=num(q.last),open=num(q.open24h),ts=num(q.ts),volume=num(q.volCcy24h);
 if(!(price>0&&open>0&&ts>0&&ts<=now+60000&&volume>=0))throw Error('invalid_quote');
 const points=(candles.data||[]).map(v=>({time:num(v[0]),open:num(v[1]),high:num(v[2]),low:num(v[3]),close:num(v[4]),volume:num(v[5]),complete:v[8]==='1'})).filter(v=>v.time>0&&v.time<=now&&[v.open,v.high,v.low,v.close].every(n=>n>0)&&v.high>=Math.max(v.open,v.close)&&v.low<=Math.min(v.open,v.close)&&v.high>=v.low&&v.volume>=0).sort((a,b)=>a.time-b.time);
 if(!points.length||new Set(points.map(p=>p.time)).size!==points.length)throw Error('invalid_candles');
 return {symbol,provider:'OKX',quoteCurrency:'USDT',price,change24h:(price/open-1)*100,volume24h:volume,observedAt:new Date(ts).toISOString(),fetchedAt:new Date(now).toISOString(),stale:now-ts>300000,bar:'1Dutc',points:points.slice(-90),sourceUrl:'https://www.okx.com/trade-spot/'+symbol.toLowerCase()};
}
export async function cryptoMarketResponse(request,fetcher=fetch){
 if(request.method!=='GET')return Response.json({error:'method_not_allowed'},{status:405});
 const symbol=new URL(request.url).searchParams.get('symbol')||'BTC-USDT';
 if(!instruments.includes(symbol))return Response.json({error:'unsupported_instrument'},{status:400});
 const hit=cached.get(symbol);if(hit&&hit.expires>Date.now())return Response.json(hit.body,{status:hit.status});
 if(!pending.has(symbol))pending.set(symbol,(async()=>{
  try{
   const read=async path=>{const r=await fetcher('https://www.okx.com/api/v5/market/'+path,{signal:AbortSignal.timeout(8000),headers:{Accept:'application/json'}});if(!r.ok)throw Error('upstream_unavailable');return r.json()};
   const [quote,candles]=await Promise.all([read('ticker?instId='+symbol),read('candles?instId='+symbol+'&bar=1Dutc&limit=90')]);
   const body=parseMarket(symbol,quote,candles);cached.set(symbol,{body,status:200,expires:Date.now()+60000});return {body,status:200};
  }catch{const body={error:'market_unavailable',provider:'OKX',symbol,notice:'Provider unavailable, restricted or invalid data. No simulated quote substituted.'};cached.set(symbol,{body,status:503,expires:Date.now()+15000});return {body,status:503};}
  finally{pending.delete(symbol);}
 })());
 const result=await pending.get(symbol);return Response.json(result.body,{status:result.status});
}
