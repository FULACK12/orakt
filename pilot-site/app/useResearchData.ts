"use client";
import {useEffect,useState} from 'react';
export default function useResearchData(path:string){
 const [data,setData]=useState<any>(null),[error,setError]=useState('');
 useEffect(()=>{const c=new AbortController();let active=true;const timer=setTimeout(()=>c.abort(),20000);setData(null);setError('');fetch(path,{signal:c.signal,cache:'no-store'}).then(async r=>{if(!r.ok)throw Error(r.status===403?'需要 Research 权限 / Research access required':'数据读取失败 / Data unavailable');return r.json();}).then(v=>{if(active)setData(v)}).catch(e=>{if(active)setError(e.name==='AbortError'?'读取超时，请刷新重试 / Timed out; reload to retry':String(e.message));}).finally(()=>clearTimeout(timer));return()=>{active=false;clearTimeout(timer);c.abort()};},[path]);
 return {data,error};
}
