"use client";
import {useEffect,useState} from 'react';
export type PublishedMetrics={events:number;articles:number;reports:number;companies:number;newsRecords?:number;generatedAt:string};
export default function usePublishedMetrics(initial:PublishedMetrics){
 const [metrics,setMetrics]=useState(initial),[checkedAt,setCheckedAt]=useState<string|null>(null),[stale,setStale]=useState(false);
 useEffect(()=>{
  let disposed=false,busy=false,active:AbortController|null=null;
  async function check(){
   if(disposed||busy||document.visibilityState==='hidden')return;
   busy=true;active=new AbortController();const timer=setTimeout(()=>active?.abort(),8000);
   try{const r=await fetch('/api/public-stats',{cache:'no-store',signal:active.signal});if(!r.ok)throw Error('unavailable');const data=await r.json();
    if(!['events','articles','reports','companies'].every(k=>Number.isSafeInteger(data[k])&&data[k]>=0)||!Number.isFinite(Date.parse(data.generatedAt)))throw Error('invalid');
    if(!disposed){setMetrics(data);setCheckedAt(data.checkedAt);setStale(false);}
   }catch{if(!disposed)setStale(true);}finally{clearTimeout(timer);busy=false;active=null;}
  }
  void check();const interval=setInterval(check,60000);document.addEventListener('visibilitychange',check);
  return()=>{disposed=true;clearInterval(interval);active?.abort();document.removeEventListener('visibilitychange',check);};
 },[]);
 return {metrics,checkedAt,stale};
}
