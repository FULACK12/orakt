"""Disclosure-based backlog, not a claim of complete historical market coverage.

Originals and drafts remain on the cold disk. Only aggregate company coverage is
exportable to the website. Missing dates, unparsed A-share windows and failed
drafts never become completed reports. This module does not invoke a model.
"""
import argparse,json,re,sqlite3
from collections import Counter,defaultdict
from datetime import date,datetime,UTC
from pathlib import Path
from sqlalchemy import select
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.db.models import CompanyProfile,CompanyFiling
from app.company_completion import REPORT_FORMS,filing_target
from app.company_history_dossier import CHAPTERS,write_json


def published_periods(site):
    """Resolve actual attached dossiers, never old narrative report counts."""
    result=defaultdict(list)
    index=json.loads((site/'snapshot/research-report-index.json').read_text(encoding='utf-8'))
    for item in index['reports']:
        if not item.get('historical'):continue
        path=site/'private-data/company-dossiers'/f"{item['id']}.json"
        if not path.is_file():continue
        d=json.loads(path.read_text(encoding='utf-8'))
        if {c['key'] for c in d.get('chapters',[])}!={c[0] for c in CHAPTERS}:continue
        for source in d.get('sources',[]):
            match=re.fullmatch(r'SEC:(\d{10}-\d{2}-\d{6})',source.get('id',''))
            if match:result[(item['ticker'],match[1])].append(item['id'])
    return result,index


def summarize_company(company,filings,published,cold,cutoff):
    jobs=[]
    for f in filings:
        if f.filed_at>cutoff or f.form not in REPORT_FORMS:continue
        ids=published.get((f.ticker,f.accession_number),[])
        try:archived=filing_target(f,cold).is_file()
        except ValueError:archived=False
        state='published' if ids else 'period_unknown' if not f.report_date else 'source_archived' if archived else 'waiting_source'
        jobs.append({'ticker':f.ticker,'accession':f.accession_number,'form':f.form,'periodEnd':str(f.report_date) if f.report_date else None,
            'disclosedAt':str(f.filed_at),'state':state,'sourceArchived':archived,'reportIds':ids,
            'versionRole':'amendment' if f.form.endswith('/A') else 'base','templateVersion':'company-periodic/v1'})
    jobs.sort(key=lambda x:(x['disclosedAt'],x['accession']))
    base=[j for j in jobs if j['versionRole']=='base' and j['periodEnd']]
    periods={(j['form'],j['periodEnd']) for j in base}
    covered={(j['form'],j['periodEnd']) for j in base if j['state']=='published'}
    totals=Counter(j['state'] for j in jobs)
    return {'ticker':company.ticker,'companyName':company.name,'market':'us','indexedDisclosures':len(jobs),'indexedPeriods':len(periods),
        'publishedPeriods':len(covered),'publishedVersions':sum(len(j['reportIds']) for j in jobs),
        'sourceArchived':sum(j['sourceArchived'] for j in jobs),'waitingSource':totals['waiting_source'],
        'periodUnknown':totals['period_unknown'],'earliestDisclosure':jobs[0]['disclosedAt'] if jobs else None,
        'latestDisclosure':jobs[-1]['disclosedAt'] if jobs else None,'latestPeriod':max((j['periodEnd'] for j in base),default=None),
        'missingPeriods':len(periods-covered),'complete':False,'coverageBasis':'indexed_disclosures_only'},jobs


def build(root,site,output,cutoff):
    published,index=published_periods(site);settings=get_settings();companies=[];jobs=[]
    with get_session_factory()() as session:
        profiles=session.scalars(select(CompanyProfile).order_by(CompanyProfile.ticker)).all()
        groups=defaultdict(list)
        for f in session.scalars(select(CompanyFiling).where(CompanyFiling.form.in_(REPORT_FORMS),CompanyFiling.filed_at<=cutoff)):
            groups[f.ticker].append(f)
        for p in profiles:
            summary,planned=summarize_company(p,groups[p.ticker],published,settings.cold_data_root,cutoff)
            companies.append(summary);jobs.extend(planned)
    catalogue=json.loads((site/'snapshot/equity-report-catalog.json').read_text(encoding='utf-8'))
    windows=defaultdict(list)
    database=root/'completion.sqlite3'
    if database.is_file():
        with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True,timeout=60) as db:
            for ticker,state,detail in db.execute("SELECT ticker,state,detail FROM jobs WHERE kind='cn-history'"):
                windows[ticker].append({'state':state,**json.loads(detail or '{}')})
    for c in catalogue['companies']:
        if c.get('marketRegion')!='china':continue
        w=windows[c['ticker']]
        companies.append({'ticker':c['ticker'],'companyName':c.get('companyName') or c.get('name') or c['ticker'],'market':'china',
            'indexedDisclosures':None,'indexedPeriods':None,'publishedPeriods':0,'publishedVersions':0,'sourceArchived':None,'waitingSource':None,
            'earliestDisclosure':None,'latestDisclosure':None,'missingPeriods':None,'complete':False,
            'checkedYearWindows':len(w),'completeYearWindows':sum(x['state']=='complete' for x in w),
            'partialYearWindows':sum(x['state']!='complete' for x in w),'coverageBasis':'annual_provider_windows_not_normalized_to_periods'})
    jobs.sort(key=lambda j:(j['disclosedAt'],j['ticker'],j['accession']))
    result={'version':'company-report-inventory/v1','checkedAt':datetime.now(UTC).isoformat(),'cutoff':str(cutoff),'complete':False,
        'template':{'version':'company-periodic/v1','chapters':[{'key':k,'zh':zh,'en':en} for k,zh,en in CHAPTERS],
            'granularity':'annual_quarterly_with_separate_amendments','requiredFields':['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'],
            'generationTimeSeparateFromEvidenceCutoff':True,'publicationRequiresContentReview':True},
        'totals':{'companies':len(companies),'usCompanies':len(profiles),'chinaCompanies':sum(c['market']=='china' for c in companies),
            'indexedPeriodicFilings':len(jobs),'publishedHistoricalVersions':sum(bool(r.get('historical')) for r in index['reports']),
            'legacyResearchVersions':sum(not r.get('historical') for r in index['reports']),
            'sourceArchived':sum(j['sourceArchived'] for j in jobs),'waitingSource':sum(j['state']=='waiting_source' for j in jobs),
            'unpublishedIndexedPeriods':sum(c.get('missingPeriods') or 0 for c in companies)},
        'companies':companies,'limitations':['Only indexed disclosures are counted; no all-market or pre-digital completeness claim.',
            'Archived source is not an approved or generated report. A-share fiscal-period normalization remains pending.',
            'Publication and generation timestamps are retained separately from historical analysis cutoffs.']}
    write_json(output/'company-report-inventory.json',result)
    write_json(output/'report-backlog.json',{'checkedAt':result['checkedAt'],'cutoff':str(cutoff),'order':'oldest_disclosure_first','jobs':jobs,'inferenceStarted':False})
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--site',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--cutoff',type=date.fromisoformat,default=date.today());a=p.parse_args()
    if a.cutoff>date.today():p.error('Future cutoff is not allowed')
    data=build(a.root,a.site,a.output,a.cutoff);print(json.dumps(data['totals']))
