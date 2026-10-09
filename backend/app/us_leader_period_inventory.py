"""Read-only source inventory for curated US leaders, one report per period.

Amendments remain provenance, not additional targets. Q4 is not fabricated.
An amendment needs a base+changes review before the period is called complete.
"""
import argparse
import json
from collections import Counter,defaultdict
from datetime import date
from pathlib import Path
from sqlalchemy import select
from app.company_completion import REPORT_FORMS,filing_target
from app.company_history_dossier import write_json
from app.core.config import get_settings
from app.db.models import CompanyFiling
from app.db.session import get_session_factory
from app.leader_report_batch import leaders,now
from app.leader_history_batch import reviewed_index


def period_groups(rows,cutoff):
    groups=defaultdict(list);undated=[]
    for f in rows:
        if f.form not in REPORT_FORMS or f.filed_at>cutoff:continue
        if not f.report_date:
            undated.append(f.accession_number);continue
        if f.report_date>cutoff:continue
        groups[(f.ticker,str(f.report_date))].append(f)
    result=[]
    for (ticker,end),filings in sorted(groups.items()):
        filings=sorted(filings,key=lambda f:(f.filed_at,f.accession_number))
        forms={f.form.removesuffix('/A') for f in filings}
        annual=bool(forms & {'10-K','20-F','40-F'})
        bases=[f for f in filings if not f.form.endswith('/A') and (not annual or f.form in {'10-K','20-F','40-F'})]
        base=bases[-1] if bases else None
        result.append({'periodKey':ticker+':'+end,'ticker':ticker,'periodEnd':end,
            'reportKind':'annual' if annual else 'quarterly','primaryAccession':base.accession_number if base else None,
            'initialDisclosure':str(filings[0].filed_at),'latestDisclosure':str(filings[-1].filed_at),
            'requiresAmendmentMerge':any(f.form.endswith('/A') for f in filings) or len(bases)>1,
            'annualAndQuarterlySameEnd':annual and '10-Q' in forms,
            'versions':[{'accession':f.accession_number,'form':f.form,'filedAt':str(f.filed_at),
                'sourceUrl':f.source_url,'primaryDocument':f.primary_document} for f in filings]})
    return result,undated


def inventory(catalog,reviewed,output,cutoff):
    selected=[c for c in leaders(json.loads(catalog.read_text(encoding='utf-8'))) if c['marketRegion']=='us']
    tickers=[c['ticker'] for c in selected];known=reviewed_index(reviewed);settings=get_settings()
    with get_session_factory()() as db:
        rows=db.scalars(select(CompanyFiling).where(CompanyFiling.ticker.in_(tickers),
            CompanyFiling.form.in_(REPORT_FORMS),CompanyFiling.filed_at<=cutoff)).all()
    groups,undated=period_groups(rows,cutoff);by_accession={f.accession_number:f for f in rows}
    for group in groups:
        archives=[];missing=[]
        for v in group['versions']:
            f=by_accession[v['accession']]
            try:exists=filing_target(f,settings.cold_data_root).is_file()
            except ValueError:exists=False
            (archives if exists else missing).append(v['accession'])
        group.update(archivedVersions=archives,missingOriginalVersions=missing)
        key=(group['ticker'],group['primaryAccession'])
        if group['requiresAmendmentMerge']:state='amendment_merge_review_required'
        elif key in known:state='existing_review_record'
        elif missing or not group['primaryAccession']:state='waiting_original'
        else:state='originals_present_financial_preflight_required'
        group['state']=state
        if key in known:group['existingReview']=known[key]
    companies=[]
    for c in selected:
        items=[g for g in groups if g['ticker']==c['ticker']]
        companies.append({**c,'targetPeriods':len(items),'byState':dict(Counter(g['state'] for g in items)),
            'earliestPeriod':min((g['periodEnd'] for g in items),default=None),
            'latestPeriod':max((g['periodEnd'] for g in items),default=None)})
    result={'version':'us-leader-period-scope/v33','createdAt':now(),'cutoff':str(cutoff),
        'scope':'Existing curated US leaders only; no A-shares or other issuers',
        'frequency':'One report per company/report-period end. Annual report includes Q4; no invented standalone 10-Q.',
        'q4Policy':'A standalone Q4 metric requires audited annual minus first-nine-month cumulative values of identical unit, accounting basis and vintage. Mark derived; never subtract balance-sheet stocks. No Q4 report added by this inventory.',
        'amendmentPolicy':'Keep all originals/amendments as provenance of one period; revised conclusions need base+amendment review and separate actual review date. Do not backdate amended information into original disclosure.',
        'coverageLimit':'Indexed periods only; unindexed gaps and pre-EDGAR history are not claimed complete. Foreign issuers may have annual SEC forms without quarterly 10-Q.',
        'summary':{'companies':len(companies),'filingVersions':len(rows),'targetReports':len(groups),
            'annualReports':sum(g['reportKind']=='annual' for g in groups),'quarterlyReports':sum(g['reportKind']=='quarterly' for g in groups),
            'deduplicatedVersions':len(rows)-len(groups)-len(undated),'undatedVersions':len(undated),
            'byState':dict(Counter(g['state'] for g in groups))},
        'companies':companies,'periods':groups,'undatedAccessions':undated,'published':False}
    write_json(output,result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--catalog',type=Path,required=True);p.add_argument('--reviewed',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--cutoff',type=date.fromisoformat,required=True);a=p.parse_args()
    r=inventory(a.catalog,a.reviewed,a.output,a.cutoff);print(json.dumps(r['summary']))
