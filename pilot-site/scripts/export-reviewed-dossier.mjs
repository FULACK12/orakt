// Explicitly invoked after the assistant has audited every chapter; not a model approval agent.
import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
import {assembleReviewedDossier} from './reviewed-dossier.mjs';
const [draft,review,id]=process.argv.slice(2);
if(!draft||!review||!/^local-\d+$/.test(id||''))throw Error('Usage: draft-path review-path local-ID');
const root=new URL('../',import.meta.url);
const original=JSON.parse(readFileSync(new URL(`private-data/research-reports/${id}.json`,root),'utf8')).report;
const result=assembleReviewedDossier(JSON.parse(readFileSync(draft,'utf8')),readFileSync(review),original);
const folder=new URL('private-data/company-dossiers/',root);mkdirSync(folder,{recursive:true});
writeFileSync(new URL(`${id}.json`,folder),JSON.stringify(result));
console.log(JSON.stringify({id,chapters:result.chapters.length,state:result.review.state,humanAccepted:false}));
