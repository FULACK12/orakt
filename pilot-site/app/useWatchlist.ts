"use client";
import {useEffect,useState} from 'react';
export default function useWatchlist(){
 const [tickers,setTickers]=useState<string[]>([]),[companies,setCompanies]=useState<any[]>([]),[ready,setReady]=useState(false),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{let active=true;const c=new AbortController();const read=()=>fetch('/api/account/watchlist',{cache:'no-store',signal:c.signal}).then(r=>{if(!r.ok)throw Error();return r.json()}).then(d=>{if(active){setTickers(d.tickers);setCompanies(d.companies);setReady(true);setError('');}}).catch(()=>{if(active)setError('自选读取失败 / Watchlist unavailable')});read();window.addEventListener('orakt-watchlist',read);return()=>{active=false;c.abort();window.removeEventListener('orakt-watchlist',read)};},[]);
 async function save(next:string[]){if(busy)return false;setBusy(true);setError('');try{const r=await fetch('/api/account/watchlist',{method:'PUT',headers:{'Content-Type':'application/json','X-ORAKT-Preferences':'watchlist'},body:JSON.stringify({tickers:next}),signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error();const d=await r.json();setTickers(d.tickers);window.dispatchEvent(new Event('orakt-watchlist'));return true;}catch{setError('保存失败，未改变自选 / Save failed; watchlist unchanged');return false;}finally{setBusy(false)}}
 return {tickers,companies,ready,error,busy,save};
}
