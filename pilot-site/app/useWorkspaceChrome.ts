"use client";
import {useEffect,useRef} from 'react';
export default function useWorkspaceChrome(){
 const ref=useRef<HTMLElement>(null);
 useEffect(()=>{
  const root=ref.current;if(!root)return;
  const header=root.querySelector<HTMLElement>('.topbar');if(!header)return;
  const measure=()=>root.style.setProperty('--workspace-header-height',Math.ceil(header.getBoundingClientRect().height)+'px');
  measure();const observer=new ResizeObserver(measure);observer.observe(header);return()=>observer.disconnect();
 },[]);
 return ref;
}
