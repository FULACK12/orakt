"""Original-filing peer comparison and explicitly retrospective factor diagnostics.

Never feeds later prices into the report's historical information set. No model,
confidence upgrade, portfolio trade, or prospective-experiment registration.
"""
import argparse
import hashlib
import json
import math
import time
from bisect import bisect_right
from datetime import date, datetime, UTC
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select
from app.core.config import get_settings
from app.db.models import CompanyFiling, MarketSeries, MarketObservation
from app.db.session import get_session_factory
from app.inline_filing_facts import monetary_facts
from app.financial_period_ledger import build_ledger, period_type
from app.company_history_dossier import write_json

REVENUE=('RevenueFromContractWithCustomerExcludingAssessedTax','RevenueFromContractWithCustomerIncludingAssessedTax','Revenues','SalesRevenueNet')
METRICS={'revenue':REVENUE,'grossProfit':('GrossProfit',),'operatingIncome':('OperatingIncomeLoss',),'netIncome':('NetIncomeLoss',),'operatingCashFlow':('NetCashProvidedByUsedInOperatingActivities',)}
HORIZONS=(5,10,20)
POLICY={'id':'quarter-growth-margin/v1','formula':'revenue_yoy > 0 AND gross_margin_yoy_pp > 0','position':'long_only','entry':'first SPY trading-session close strictly after SEC filing date','horizons':list(HORIZONS),'roundTripCostBps':25,'minimumIndependentEvents':20,'industryBenchmark':'TD:SOXX','marketBenchmark':'TD:SPY','selection':'AMD 10-Q filings from 2023-01-01 through report cutoff, first 12 in chronological order','mode':'retrospective_diagnostic','prospective':False}

def unique_quarter(facts,concepts,end):
    rows=[f for f in facts if f['concept'] in concepts and not f.get('dimensions') and f['unit']=='USD' and f['period_end']==end and period_type(f)=='quarter']
    identities={(f['period_start'],f['period_end'],Decimal(f['value'])) for f in rows}
    if len(identities)!=1 or not all(x[2].is_finite() for x in identities):return None
    return rows[0]

def financial_summary(packet):
    metrics={k:unique_quarter(packet['facts'],concepts,packet['period_end']) for k,concepts in METRICS.items()}
    ledger=build_ledger(packet)
    selected={}
    for key in ['revenue','grossProfit']:
        fact=metrics[key]
        if fact:
            candidates=[c for c in ledger['comparisons'] if c['periodType']=='quarter' and c['current']['evidence_id']==fact['evidence_id']]
            if len(candidates)==1:selected[key]=candidates[0]
    r,g=metrics['revenue'],metrics['grossProfit']
    margin=None
    if r and g and r['period_start']==g['period_start'] and Decimal(r['value'])>0:
        margin=float(Decimal(g['value'])/Decimal(r['value'])*100)
    yoy=selected.get('revenue',{}).get('changePercent');change=None
    rc,gc=selected.get('revenue'),selected.get('grossProfit')
    if margin is not None and rc and gc:
        a,b=rc['previous'],gc['previous']
        if (a['period_start'],a['period_end'])==(b['period_start'],b['period_end']) and Decimal(a['value'])>0:
            change=margin-float(Decimal(b['value'])/Decimal(a['value'])*100)
    return {'metrics':metrics,'grossMarginPercent':margin,'revenueYoYPercent':float(yoy) if yoy is not None else None,'grossMarginYoYPoints':change,'comparisons':list(selected.values())}

def diagnose(events,prices,evaluation_end):
    """SPY supplies the calendar; absent observations are not forward-filled."""
    calendar=sorted(d for d in prices.get('TD:SPY',{}) if d<=evaluation_end)
    rows=[];last_exit={h:'' for h in HORIZONS}
    for e in sorted(events,key=lambda e:(e['filedAt'],e['accession'])):
        for h in HORIZONS:
            row={'accession':e['accession'],'filedAt':e['filedAt'],'horizon':h,'signal':None,'state':'financial_inputs_missing','strategyReturn':None,'marketExcess':None,'industryExcess':None}
            rows.append(row)
            s=e.get('summary',{});growth=s.get('revenueYoYPercent');margin=s.get('grossMarginYoYPoints')
            if growth is None or margin is None:continue
            row['signal']=growth>0 and margin>0
            if not row['signal']:row['state']='no_signal';continue
            pos=bisect_right(calendar,e['filedAt'])
            if pos+h>=len(calendar):row['state']='outcome_window_incomplete';continue
            entry,exit=calendar[pos],calendar[pos+h]
            row.update(entryDate=entry,exitDate=exit)
            if entry<=last_exit[h]:row['state']='overlap_excluded';continue
            window=calendar[pos:pos+h+1]
            def ret(series):
                p=prices.get(series,{})
                if any(not isinstance(p.get(d),(int,float)) or not math.isfinite(p[d]) or p[d]<=0 for d in window):return None
                return p[exit]/p[entry]-1
            stock,market,industry=ret('EQ:AMD'),ret('TD:SPY'),ret('TD:SOXX')
            if stock is None or market is None:row['state']='price_window_missing';continue
            last_exit[h]=exit
            strategy=stock-POLICY['roundTripCostBps']/10000
            row.update(strategyReturn=strategy,marketReturn=market,industryReturn=industry,marketExcess=strategy-market,industryExcess=None if industry is None else strategy-industry,state='industry_benchmark_missing' if industry is None else 'diagnostic_only')
    groups=[]
    for h in HORIZONS:
        eligible=[r for r in rows if r['horizon']==h and r['strategyReturn'] is not None]
        dual=[r for r in eligible if r['industryExcess'] is not None]
        groups.append({'horizon':h,'pricedIndependentEvents':len(eligible),'dualBenchmarkEvents':len(dual),'meanMarketExcess':sum(r['marketExcess'] for r in eligible)/len(eligible) if eligible else None,'meanIndustryExcess':sum(r['industryExcess'] for r in dual)/len(dual) if dual else None,'confidenceInterval':None,'validatedAlpha':False})
    return {'rows':rows,'groups':groups,'status':'not_validated','confidenceIntervalStatus':'not_estimated_in_exploratory_pilot','prospectiveValidation':False}

def filing_packet(filing,settings,client,download):
    base=(settings.cold_data_root/'raw/sec/company-filings'/filing.ticker).resolve()
    path=(base/filing.accession_number.replace('-','')/(filing.primary_document or '')).resolve()
    u=urlsplit(filing.source_url)
    if not filing.primary_document or not path.is_relative_to(base) or u.scheme!='https' or u.hostname!='www.sec.gov' or not u.path.startswith('/Archives/edgar/data/'):raise ValueError('Invalid filing archive/source')
    if not path.is_file():
        if not download:raise FileNotFoundError('Original filing not archived')
        try:
            response=client.get(filing.source_url);response.raise_for_status();raw=response.content
            if not 5000<len(raw)<25000000 or b'<html' not in raw.lower():raise ValueError('Invalid filing document')
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        finally:time.sleep(.3)
    raw=path.read_bytes();facts,coverage=monetary_facts(raw.decode('utf-8',errors='replace'),filed_at=str(filing.filed_at),source_url=filing.source_url)
    return {'ticker':filing.ticker,'accession':filing.accession_number,'as_of_date':str(filing.filed_at),'period_end':str(filing.report_date),'source_url':filing.source_url,'raw_sha256':hashlib.sha256(raw).hexdigest(),'facts':facts,'coverage':coverage}

def run(report_path,output,download=False):
    if output.exists():raise ValueError('Use a new revision output; do not overwrite a study')
    report=json.loads(report_path.read_text(encoding='utf-8'))
    if report['ticker']!='AMD':raise ValueError('Pilot protocol is AMD-only')
    cutoff=date.fromisoformat(report['asOf']);end=date.fromisoformat(report['periodEnd'])
    settings=get_settings();ua=settings.sec_user_agent
    if settings.sec_contact_email:ua+=' '+settings.sec_contact_email.get_secret_value()
    peers=[];events=[];packets={};subject_start=None
    with get_session_factory()() as session,httpx.Client(headers={'User-Agent':ua},timeout=45,follow_redirects=False) as client:
        def obtain(f):
            if f.accession_number not in packets:
                p=filing_packet(f,settings,client,download);packets[f.accession_number]=p
                write_json(output.parent/'source-packets'/f.ticker/(f.accession_number+'.json'),p)
            return packets[f.accession_number]
        for ticker in ['AMD','INTC','QCOM','NVDA','AVGO']:
            f=session.scalars(select(CompanyFiling).where(CompanyFiling.ticker==ticker,CompanyFiling.form.in_(['10-Q','10-K']),CompanyFiling.filed_at<=cutoff).order_by(CompanyFiling.filed_at.desc(),CompanyFiling.accession_number.desc())).first()
            item={'ticker':ticker,'rankingEligible':False};peers.append(item)
            if not f:item['status']='filing_missing';continue
            item.update(accession=f.accession_number,filedAt=str(f.filed_at),periodEnd=str(f.report_date),form=f.form,sourceUrl=f.source_url,calendarEndGapDays=abs((f.report_date-end).days))
            try:
                p=obtain(f);s=financial_summary(p);item.update(summary=s,sourceDocumentHash=p['raw_sha256'],status='quarter_available' if s['metrics']['revenue'] else 'direct_quarter_missing')
                r=s['metrics']['revenue']
                if ticker=='AMD':
                    if p['raw_sha256']!=report['provenance']['sourceDocumentHash'] or p['source_url']!=report['sources'][0]['url']:raise ValueError('Subject source differs from reviewed report')
                    subject_start=date.fromisoformat(r['period_start']) if r else None
                item['calendarAligned']=bool(r and subject_start and item['calendarEndGapDays']<=14 and abs((date.fromisoformat(r['period_start'])-subject_start).days)<=14)
                # Date alignment allows accounting comparison, not homogeneous businesses or a rank.
            except (httpx.HTTPError,ValueError,FileNotFoundError) as exc:item.update(status='original_unavailable',error=type(exc).__name__)
        filings=session.scalars(select(CompanyFiling).where(CompanyFiling.ticker=='AMD',CompanyFiling.form=='10-Q',CompanyFiling.filed_at>=date(2023,1,1),CompanyFiling.filed_at<=cutoff).order_by(CompanyFiling.filed_at,CompanyFiling.accession_number).limit(12)).all()
        for f in filings:
            e={'accession':f.accession_number,'filedAt':str(f.filed_at),'periodEnd':str(f.report_date),'sourceUrl':f.source_url};events.append(e)
            try:
                p=obtain(f);e.update(summary=financial_summary(p),sourceDocumentHash=p['raw_sha256'])
            except (httpx.HTTPError,ValueError,FileNotFoundError) as exc:e['error']=type(exc).__name__
        prices={};coverage=[];evaluation_end='2025-06-30'
        for sid in ['EQ:AMD','TD:SPY','TD:SOXX']:
            series=session.get(MarketSeries,sid)
            data=session.scalars(select(MarketObservation).where(MarketObservation.series_id==sid,MarketObservation.observed_on>=date(2023,1,1),MarketObservation.observed_on<=date.fromisoformat(evaluation_end)).order_by(MarketObservation.observed_on)).all()
            prices[sid]={str(r.observed_on):r.value for r in data}
            coverage.append({'id':sid,'name':series.name if series else sid,'count':len(data),'start':str(data[0].observed_on) if data else None,'end':str(data[-1].observed_on) if data else None,'sourceUrl':series.source_url if series else None,'sourceName':series.source_name if series else None,'vintage':'latest retained; original release vintage not guaranteed','priceBasis':'split-adjusted price; total-return equivalence not verified','lastFetchedAt':max(r.fetched_at for r in data).isoformat() if data else None})
    inputs={'events':events,'prices':prices,'policy':POLICY,'evaluationEnd':evaluation_end}
    write_json(output.parent/'factor-inputs.json',inputs)
    fingerprint=hashlib.sha256((output.parent/'factor-inputs.json').read_bytes()).hexdigest()
    result={'version':'quarter-peer-study/v1','ticker':'AMD','asOf':report['asOf'],'periodEnd':report['periodEnd'],'createdAt':datetime.now(UTC).isoformat(),'reportRevisionHash':report['review']['assistantRevisionHash'],'changesReportConfidence':False,'rankingEligible':False,'peers':peers,'factor':{'policy':POLICY,'inputFingerprint':fingerprint,'evaluationEnd':evaluation_end,'coverage':coverage,'events':events,**diagnose(events,prices,evaluation_end)}}
    write_json(output,result)
    print(json.dumps({'peers':[(p['ticker'],p['status']) for p in peers],'events':len(events),'groups':result['factor']['groups'],'output':str(output)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--download',action='store_true');a=p.parse_args();run(a.report,a.output,a.download)
