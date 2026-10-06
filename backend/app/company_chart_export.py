"""Original filing facts for research charts; no fabricated consensus estimates."""
import argparse, json, sqlite3, math
from datetime import date, datetime, UTC
from pathlib import Path
from sqlalchemy import select
from app.core.config import get_settings
from app.db.models import CompanyProfile, CompanyFinancialFact
from app.db.session import get_session_factory
from app.company_history_dossier import write_json

METRICS={
 'revenue':['RevenueFromContractWithCustomerExcludingAssessedTax','RevenueFromContractWithCustomerIncludingAssessedTax','Revenues','SalesRevenueNet'],
 'netIncome':['NetIncomeLoss'], 'operatingIncome':['OperatingIncomeLoss'], 'grossProfit':['GrossProfit'],
 'eps':['EarningsPerShareDiluted'], 'assets':['Assets'], 'liabilities':['Liabilities'],
 'equity':['StockholdersEquity'], 'currentAssets':['AssetsCurrent'], 'currentLiabilities':['LiabilitiesCurrent'],
 'cfo':['NetCashProvidedByUsedInOperatingActivities'], 'cfi':['NetCashProvidedByUsedInInvestingActivities'],
 'cff':['NetCashProvidedByUsedInFinancingActivities'], 'capex':['PaymentsToAcquirePropertyPlantAndEquipment']}

def chart_facts(rows, cutoff):
    candidates={}
    for r in rows:
        end=str(r.get('period_end') or '');start=str(r.get('period_start') or '');filed=str(r.get('filed_at') or '')
        if not end or not filed or end>cutoff or filed>cutoff:continue
        try:value=float(r['value']);days=(date.fromisoformat(end)-date.fromisoformat(start)).days if start else 0
        except (ValueError,TypeError,KeyError):continue
        if not math.isfinite(value):continue
        basis='instant' if not start else 'quarter' if 60<=days<=110 else 'annual' if 330<=days<=390 else 'ytd' if 120<=days<=310 else None
        if basis is None:continue
        for metric,concepts in METRICS.items():
            if r['concept'] not in concepts or r['unit']!=('USD/shares' if metric=='eps' else 'USD'):continue
            p={'start':start or None,'end':end,'filedAt':filed,'value':value,'unit':r['unit'],'basis':basis,'concept':r['concept'],'sourceUrl':r['source_url'],'accession':r.get('accession_number'),'evidenceId':r.get('evidence_id')}
            candidates.setdefault((metric,basis,start,end),[]).append((filed,concepts.index(r['concept']),p))
    result={m:[] for m in METRICS};conflicts=0
    for (metric,*_),values in candidates.items():
        # Latest retained filed version is explicitly retrospective, not PIT.
        latest=max(v[0] for v in values);v=[x for x in values if x[0]==latest];rank=min(x[1] for x in v);v=[x[2] for x in v if x[1]==rank]
        if len({p['value'] for p in v})!=1:conflicts+=1;continue
        result[metric].append(v[0])
    for points in result.values():points.sort(key=lambda p:(p['end'],p['start'] or ''))
    return result,conflicts

def run(site,cold):
    cutoff=date.today().isoformat();companies=[];root=cold/'orakt/company-charts-v84'
    ledgers=sorted((cold/'raw/sec/bulk').glob('*/import-ledger.sqlite3'),reverse=True)
    with get_session_factory()() as session:
        for company in session.scalars(select(CompanyProfile).order_by(CompanyProfile.ticker)):
            rows=[]
            for ledger in ledgers:
                with sqlite3.connect(ledger.resolve().as_uri()+'?mode=ro',uri=True) as db:
                    done=db.execute('SELECT state FROM issuers WHERE ticker=?',(company.ticker,)).fetchone()
                    if not done or done[0]!='complete':continue
                    for digest,payload in db.execute('SELECT hash,payload FROM observations WHERE ticker=?',(company.ticker,)):
                        row=json.loads(payload);rows.append({**row,'evidence_id':'BULK:'+digest})
                    if rows:break
            if not rows:
                for f in session.scalars(select(CompanyFinancialFact).where(CompanyFinancialFact.ticker==company.ticker)):
                    rows.append({k:str(getattr(f,k)) if k in ('filed_at','period_start','period_end') and getattr(f,k) else getattr(f,k) for k in ('concept','value','unit','period_start','period_end','filed_at','source_url','accession_number')})
            metrics,conflicts=chart_facts(rows,cutoff)
            full={'ticker':company.ticker,'name':company.name,'metrics':metrics,'conflictingPeriodsOmitted':conflicts,'consensus':None,'consensusStatus':'not_licensed_or_retained','vintage':'latest_retained_filing_version_not_point_in_time'}
            if not any(metrics.values()):continue
            write_json(root/(company.ticker+'.json'),full)
            # Public endpoint is bounded; full original history stays on cold disk.
            companies.append({**full,'metrics':{m:[p for b in ('quarter','annual','ytd','instant') for p in [x for x in ps if x['basis']==b][-16:]] for m,ps in metrics.items()}})
    payload={'schema':'company-charts/v1','generatedAt':datetime.now(UTC).isoformat(),'cutoff':cutoff,'companies':companies,'scope':'existing_US_company_profiles','publicPeriodLimitPerBasis':16,'consensusAvailable':False}
    write_json(site/'private-data/company-charts.json',payload)
    print(json.dumps({'companies':len(companies),'facts':sum(len(p) for c in companies for p in c['metrics'].values()),'coldRoot':str(root),'forecastFabricated':False}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--site',type=Path,required=True);a=p.parse_args();run(a.site,get_settings().cold_data_root)
