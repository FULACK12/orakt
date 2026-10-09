"use client";
import {useEffect,useState} from "react";
import {resolveDisplayLanguage} from './display-language.mjs';
export default function useDisplayLanguage(){
  const [language,setState]=useState<"zh"|"en">("zh");
  useEffect(()=>{const sync=()=>{let saved=null;try{saved=localStorage.getItem("orakt-language");}catch{}const v=resolveDisplayLanguage(saved,navigator.languages?.length?navigator.languages:[navigator.language]);setState(v);document.documentElement.lang=v==='zh'?'zh-CN':'en';};sync();window.addEventListener("storage",sync);window.addEventListener('orakt-language-change',sync);return()=>{window.removeEventListener("storage",sync);window.removeEventListener('orakt-language-change',sync);};},[]);
  function setLanguage(v:"zh"|"en"){setState(v);document.documentElement.lang=v==='zh'?'zh-CN':'en';try{localStorage.setItem("orakt-language",v);window.dispatchEvent(new Event('orakt-language-change'));}catch{}}
  return [language,setLanguage] as const;
}
