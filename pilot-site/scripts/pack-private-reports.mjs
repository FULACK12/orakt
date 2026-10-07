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
const chains=[];
for(const item of index.reports){
 if(!/^[A-Za-z0-9_-]+$/.test(item.id))throw Error('Invalid report identifier');
 let raw=readFileSync(new URL(`${item.id}.json`,folder));const body=JSON.parse(raw.toString('utf8'));
 const translation=new URL(`private-data/report-translations/${item.id}.en.json`,root);
 const supplement=new URL(`private-data/report-supplements/${item.id}.json`,root);
 const completion=new URL(`private-data/research-completions/${item.id}.json`,root);
 if(existsSync(completion)){body.report.researchCompletion=validateCompletion(JSON.parse(readFileSync(completion,'utf8')),body.report);raw=Buffer.from(JSON.stringify(body));}
 const dossier=new URL(`private-data/company-dossiers/${item.id}.json`,root);
 if(existsSync(dossier)){const bytes=readFileSync(dossier),d=JSON.parse(bytes);const receipt=d.version==='consolidated-site/v1'?readFileSync(new URL(`private-data/dossier-reviews/${item.id}.json`,root)):undefined;body.report.dossier=validateDossier(d,body.report,bytes,receipt);raw=Buffer.from(JSON.stringify(body));}
 const peerStudy=new URL(`private-data/peer-studies/${item.id}.json`,root);
 if(existsSync(peerStudy)){body.report.peerStudy=validatePeerStudy(JSON.parse(readFileSync(peerStudy,'utf8')),body.report,body.report.dossier,readFileSync(new URL(`private-data/peer-studies/${item.id}.inputs.json`,root)));raw=Buffer.from(JSON.stringify(body));}
 if(existsSync(supplement)){body.report.financialSupplement=validateSupplement(JSON.parse(readFileSync(supplement,'utf8')),body.report);raw=Buffer.from(JSON.stringify(body));}
 if(existsSync(translation)){body.report.translations={en:JSON.parse(readFileSync(translation,'utf8'))};raw=Buffer.from(JSON.stringify(body));}
 reports[item.id]=gzipSync(raw,{level:9}).toString('base64');
 if(body.report.chain?.length)chains.push({id:item.id,ticker:body.report.ticker,date:body.report.historical?.periodEnd||body.report.dataCutoff||body.report.createdAt?.slice(0,10),title:{zh:body.report.question,en:body.report.translations?.en?.question||body.report.question},nodes:body.report.chain.map((n,i)=>({zh:n.title,en:body.report.translations?.en?.chain?.[i]?.title||n.title}))});
}
if(readdirSync(folder).filter(v=>v.endsWith('.json')).length!==index.reports.length)throw Error('Report index/body count mismatch');
mkdirSync(new URL('generated/',root),{recursive:true});
writeFileSync(new URL('generated/private-chain-index.mjs',root),`// Server-only chain catalog; no report bodies.\nexport default ${JSON.stringify(chains)};\n`);
writeFileSync(new URL('generated/private-reports.mjs',root),`// Generated server-only report archive. Never import from app/ client code.\nexport default ${JSON.stringify(reports)};\n`);
console.log(`Packed ${index.reports.length} private report bodies for the server.`);
const charts=JSON.parse(readFileSync(new URL('private-data/company-charts.json',root),'utf8'));
const chartArchive={generatedAt:charts.generatedAt,companies:charts.companies.map(c=>({ticker:c.ticker,name:c.name})),bodies:Object.fromEntries(charts.companies.map(c=>[c.ticker,gzipSync(Buffer.from(JSON.stringify(c)),{level:9}).toString('base64')]))};
writeFileSync(new URL('generated/private-charts.mjs',root),`// Server-only, decompress only the requested company.\nexport default ${JSON.stringify(chartArchive)};\n`);
const lab=gzipSync(readFileSync(new URL('private-data/lab-expansion.json',root)),{level:9}).toString('base64');
writeFileSync(new URL('generated/private-labs.mjs',root),`// Server-only research archive.\nexport default ${JSON.stringify(lab)};\n`);
const prices=gzipSync(readFileSync(new URL('private-data/portfolio-prices.json',root)),{level:9}).toString('base64');
writeFileSync(new URL('generated/private-portfolio-prices.mjs',root),`// Server-only retained prices; never ship the full archive to clients.\nexport default ${JSON.stringify(prices)};\n`);
