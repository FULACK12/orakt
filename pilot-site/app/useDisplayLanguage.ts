"use client";
import {useEffect,useState} from "react";
export default function useDisplayLanguage(){
  const [language,setState]=useState<"zh"|"en">("zh");
  useEffect(()=>{const sync=()=>{try{const v=localStorage.getItem("orakt-language");if(v==="zh"||v==="en")setState(v);}catch{}};sync();window.addEventListener("storage",sync);return()=>window.removeEventListener("storage",sync);},[]);
  function setLanguage(v:"zh"|"en"){setState(v);try{localStorage.setItem("orakt-language",v);}catch{}}
  return [language,setLanguage] as const;
}
