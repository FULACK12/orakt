// Publish only explicitly reviewed immutable chapter revisions, never raw drafts.
import {readFileSync,writeFileSync,mkdirSync,existsSync} from 'node:fs';
import {assembleReviewedDossier} from './reviewed-dossier.mjs';
const [draftPath,reviewPath]=process.argv.slice(2);
if(!draftPath||!reviewPath)throw Error('Usage: draft-path review-path');
const root=new URL('../',import.meta.url),read=p=>JSON.parse(readFileSync(new URL(p,root),'utf8'));
const d=JSON.parse(readFileSync(draftPath,'utf8')),bytes=readFileSync(reviewPath),review=JSON.parse(bytes);
if(!/^[A-Z]{1,8}$/.test(d.ticker)||!/^\d{4}-\d{2}-\d{2}$/.test(d.asOf))throw Error('Invalid identity');
const id=`dossier-${d.ticker}-${d.asOf.replaceAll('-','')}`;
const conclusion=d.chapters.find(c=>c.key==='conclusion'),financial=d.chapters.find(c=>c.key==='financial');
const report={id,origin:'local_ollama',ticker:d.ticker,companyName:d.ticker,marketRegion:'us',sector:'',analysisMode:'news_first',
 question:`${d.ticker} · ${d.periodEnd} · 财务增长是否转化为可持续经营质量？`,thesis:conclusion.analysis.zh,verdict:'助手逐章复审；仅用于历史研究',confidence:null,
 createdAt:d.createdAt,updatedAt:d.createdAt,syncedAt:new Date().toISOString(),model:d.model,dataCutoff:d.asOf,
 historical:{asOf:d.asOf,periodEnd:d.periodEnd,mode:'historical_reconstruction',precision:'day',reviewer:'codex_assistant',corrections:review.corrections,eligibleForPredictiveBacktest:false},
 audit:{version:'frozen_dossier_assistant_review_v1',status:'assistant_revised',recommendation:'research_only',openaiUsed:false,citedReferences:new Set(d.chapters.flatMap(c=>c.evidence_refs)).size,missingReferences:0,headlineOnlyReferences:0,futureDatedReferences:0,foreignSubjects:0,repairsApplied:review.corrections.length},
 newsReport:{headline:`${d.ticker}：经营增长、利润质量与政策约束`,narrative:financial.analysis.zh,facts:[],uncertainties:[conclusion.evidenceGaps.zh],documentsReviewed:1,fullContentReviewed:1,headlineOnlyExcluded:0},
 chain:[],evidence:d.sources.map(s=>({title:s.id,publisher:'SEC',url:s.url,observedAt:d.asOf,claim:'财报原文；模型使用有界摘录，数值按原文核对。',supports:'support',reliability:null})),
 alternatives:[conclusion.counterEvidence.zh],limitations:[conclusion.evidenceGaps.zh,'历史重建不属于当时预测；尚未估计可校准的预测置信度，不以任意分数填充。'],nextData:[conclusion.validationPlan.zh],scores:[],tradingScenario:null,canslim:null,competitorComparison:null};
const approved=assembleReviewedDossier(d,bytes,report);
if(!Array.isArray(review.correctionsEn)||review.correctionsEn.length!==review.corrections.length||review.correctionsEn.some(s=>!s?.trim()||/[\u4e00-\u9fff]/.test(s)))throw Error('Matching English review corrections required');
const translation={question:`${d.ticker} · ${d.periodEnd} · Does financial growth translate into durable operating quality?`,thesis:conclusion.analysis.en,verdict:'Assistant-reviewed chapters; historical research only',
 historical:{corrections:review.correctionsEn},
 newsReport:{headline:`${d.ticker}: operating growth, profit quality and policy constraints`,narrative:financial.analysis.en,facts:[],uncertainties:[conclusion.evidenceGaps.en]},
 evidence:report.evidence.map(s=>({...s,claim:'Official filing; bounded excerpts were supplied to the model and numbers checked against the filing.'})),
 alternatives:[conclusion.counterEvidence.en],limitations:[conclusion.evidenceGaps.en,'Retrospective research is not a contemporaneous forecast; calibrated predictive confidence is unestimated, not filled with an arbitrary score.'],nextData:[conclusion.validationPlan.en]};
report.questionEn=translation.question;
for(const folder of ['company-dossiers','research-reports','report-translations','dossier-reviews'])mkdirSync(new URL(`private-data/${folder}/`,root),{recursive:true});
const write=(p,v)=>writeFileSync(new URL(p,root),JSON.stringify(v));
const target=`private-data/company-dossiers/${id}.json`;
if(existsSync(new URL(target,root))&&read(target).review.assistantRevisionHash!==approved.review.assistantRevisionHash)throw Error('Preserve previous revision: use a versioned report identifier');
write(target,approved);write(`private-data/research-reports/${id}.json`,{report});write(`private-data/report-translations/${id}.en.json`,translation);
writeFileSync(new URL(`private-data/dossier-reviews/${id}.json`,root),bytes);
const index=read('snapshot/research-report-index.json');
const item=Object.fromEntries(['id','marketRegion','ticker','companyName','sector','analysisMode','question','model','confidence','createdAt','updatedAt','audit','historical','dataCutoff'].map(k=>[k,report[k]]));
item.tradingScenario=null;item.hasCompetitorComparison=false;
index.reports=[item,...index.reports.filter(r=>r.id!==id)].sort((a,b)=>b.createdAt.localeCompare(a.createdAt));index.total=index.reports.length;index.generatedAt=report.syncedAt;
for(const row of index.reports){const path=`private-data/report-translations/${row.id}.en.json`;if(existsSync(new URL(path,root)))row.questionEn=read(path).question;}
write('snapshot/research-report-index.json',index);
const catalog=read('snapshot/equity-report-catalog.json');for(const c of catalog.companies)c.reportIds=index.reports.filter(r=>r.marketRegion===c.marketRegion&&r.ticker===c.ticker).map(r=>r.id);write('snapshot/equity-report-catalog.json',catalog);
const completion=read('private-data/research-completions/local-707.json');
const audit=completion.draftAudit?.reports.find(r=>r.ticker===d.ticker&&r.asOf===d.asOf);
if(audit){audit.reviewedReportId=id;audit.reviewedChapters=9;audit.state='assistant_reviewed';audit.published=true;audit.issues={zh:review.corrections,en:translation.historical.corrections};completion.draftAudit.checkedAt=report.syncedAt;write('private-data/research-completions/local-707.json',completion);}
const ops=read('snapshot/orakt-research-ops.json');ops.publishedReports=index.total;ops.publishedHistoricalReports=index.reports.filter(r=>r.historical).length;ops.generatedAt=report.syncedAt;write('snapshot/orakt-research-ops.json',ops);
console.log(JSON.stringify({id,chapters:9,reports:index.total,confidence:null,localDatabaseInquiry:false}));
