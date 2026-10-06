import {readFileSync,readdirSync,mkdirSync,writeFileSync,existsSync} from 'node:fs';
import {gzipSync} from 'node:zlib';
import {validateSupplement} from './report-supplement.mjs';
import {validateDossier} from './reviewed-dossier.mjs';
import {validateCompletion} from './research-completion.mjs';
import {validatePeerStudy} from './peer-study.mjs';
const root=new URL('../',import.meta.url),folder=new URL('private-data/research-reports/',root);
if(existsSync(new URL('public/snapshot/research-reports/',root)))throw Error('Report bodies must never be published as public static assets');
const index=JSON.parse(readFileSync(new URL('snapshot/research-report-index.json',root),'utf8'));
const reports=Object.create(null);
for(const item of index.reports){
 if(!/^[A-Za-z0-9_-]+$/.test(item.id))throw Error('Invalid report identifier');
 let raw=readFileSync(new URL(`${item.id}.json`,folder));const body=JSON.parse(raw.toString('utf8'));
 const translation=new URL(`private-data/report-translations/${item.id}.en.json`,root);
 const supplement=new URL(`private-data/report-supplements/${item.id}.json`,root);
 const completion=new URL(`private-data/research-completions/${item.id}.json`,root);
 if(existsSync(completion)){body.report.researchCompletion=validateCompletion(JSON.parse(readFileSync(completion,'utf8')),body.report);raw=Buffer.from(JSON.stringify(body));}
 const dossier=new URL(`private-data/company-dossiers/${item.id}.json`,root);
 if(existsSync(dossier)){body.report.dossier=validateDossier(JSON.parse(readFileSync(dossier,'utf8')),body.report);raw=Buffer.from(JSON.stringify(body));}
 const peerStudy=new URL(`private-data/peer-studies/${item.id}.json`,root);
 if(existsSync(peerStudy)){body.report.peerStudy=validatePeerStudy(JSON.parse(readFileSync(peerStudy,'utf8')),body.report,body.report.dossier,readFileSync(new URL(`private-data/peer-studies/${item.id}.inputs.json`,root)));raw=Buffer.from(JSON.stringify(body));}
 if(existsSync(supplement)){body.report.financialSupplement=validateSupplement(JSON.parse(readFileSync(supplement,'utf8')),body.report);raw=Buffer.from(JSON.stringify(body));}
 if(existsSync(translation)){body.report.translations={en:JSON.parse(readFileSync(translation,'utf8'))};raw=Buffer.from(JSON.stringify(body));}
 reports[item.id]=gzipSync(raw,{level:9}).toString('base64');
}
if(readdirSync(folder).filter(v=>v.endsWith('.json')).length!==index.reports.length)throw Error('Report index/body count mismatch');
mkdirSync(new URL('generated/',root),{recursive:true});
writeFileSync(new URL('generated/private-reports.mjs',root),`// Generated server-only report archive. Never import from app/ client code.\nexport default ${JSON.stringify(reports)};\n`);
console.log(`Packed ${index.reports.length} private report bodies for the server.`);
