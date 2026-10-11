"use client";
import {useEffect,useState} from 'react';
import useDisplayLanguage from '../../useDisplayLanguage';
import ResearchPublication from '../../ResearchPublication';
export default function PublicationPage(){const [language,setLanguage]=useDisplayLanguage(),[id,setId]=useState<string|undefined>();useEffect(()=>setId(new URLSearchParams(window.location.search).get('id')||undefined),[]);return <main className="orakt-publish-page"><nav><a href="/platform/chains">← ORAKT</a><button onClick={()=>setLanguage(language==='zh'?'en':'zh')}>{language==='zh'?'EN':'中文'}</button></nav><ResearchPublication key={id||'list'} language={language} id={id}/></main>;}
