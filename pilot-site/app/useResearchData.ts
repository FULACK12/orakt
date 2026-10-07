"use client";
import {useEffect,useState} from 'react';
export default function useResearchData(path:string|null){
 const [data,setData]=useState<any>(null),[error,setError]=useState('');
 useEffect(()=>{setData(null);setError('');if(!path)return;const c=new AbortController();let active=true;const timer=setTimeout(()=>c.abort(),20000);fetch(path,{signal:c.signal,cache:'no-store'}).then(async r=>{if(!r.ok)throw Error(r.status===403?'当前账号等级或日期跨度不支持此项 / Access level or date span not permitted':'数据或日期范围不可用 / Data or date range unavailable');return r.json();}).then(v=>{if(active)setData(v)}).catch(e=>{if(active)setError(e.name==='AbortError'?'读取超时，请刷新重试 / Timed out; reload to retry':String(e.message));}).finally(()=>clearTimeout(timer));return()=>{active=false;clearTimeout(timer);c.abort()};},[path]);
 return {data,error};
}
