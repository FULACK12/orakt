// Presentation taxonomy only: preserve every original body, ID and timestamp.
export const COMPANY_TEMPLATE='company-periodic/v1';
export const CHAIN_TEMPLATE='evidence-research/v1';
export function reportKind(report){
 if(report?.reportKind==='company_periodic'||report?.reportKind==='evidence_research')return report.reportKind;
 return report?.historical?.periodEnd&&report?.historical?.asOf?'company_periodic':'evidence_research';
}
export function isCompanyReport(report){return reportKind(report)==='company_periodic';}
export function reportHref(report){return (isCompanyReport(report)?'/platform/research?report=':'/platform/chains?report=')+encodeURIComponent(report.id);}
export function classifyReport(report){const kind=reportKind(report);return {...report,reportKind:kind,templateVersion:kind==='company_periodic'?COMPANY_TEMPLATE:CHAIN_TEMPLATE,reportHref:reportHref(report)};}
