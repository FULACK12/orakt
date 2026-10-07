"""Bounded, resumable evidence acquisition for retrospective chapter experiments.

Never rewrites frozen report inputs or treats filing acceptance as first news.
New prices use a separate split-adjusted catalog identity, not mixed return bases.
"""
import argparse
import asyncio
import hashlib
import json
import math
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy.dialects.postgresql import insert
from app.company_history_dossier import write_json
from app.core.config import get_settings
from app.db.models import MarketSeries, MarketObservation
from app.db.session import get_session_factory
from app.twelve_data_client import request_twelve_data, TWELVE_TIME_SERIES_URL

SYMBOLS = ('NKE', 'ADBE', 'SPY', 'XLY', 'IGV')
CIKS = {'NKE': '0000320187', 'ADBE': '0000796343'}
BENCHMARKS = {
    'NKE': {'symbol': 'XLY', 'scope': 'Consumer discretionary sector proxy, not a pure footwear peer group',
            'source': 'https://www.ssga.com/us/en/individual/etfs/state-street-consumer-discretionary-select-sector-spdr-etf-xly'},
    'ADBE': {'symbol': 'IGV', 'scope': 'Software/selected interactive media proxy, not a pure Adobe peer group',
             'source': 'https://www.ishares.com/us/products/239771/ishares-us-technology-etf'},
}


def validate_prices(payload, symbol, start, end):
    meta = payload.get('meta', {})
    if meta.get('symbol') != symbol or meta.get('currency') != 'USD' or meta.get('interval') != '1day':
        raise ValueError('Provider identity, currency or interval mismatch')
    rows = {}; values = payload.get('values', [])
    for v in values:
        day = date.fromisoformat(v['datetime']); price = float(v['close'])
        if not start <= day <= end or day in rows or not math.isfinite(price) or price <= 0:
            raise ValueError('Invalid/duplicate price or observation outside requested dates')
        rows[day] = price
    if not rows or min(rows) > start+timedelta(days=7) or max(rows) < end-timedelta(days=7):
        raise ValueError('Response missing requested date edges')
    # Detect the provider default-row cap without claiming full trading coverage.
    if len(rows) < (end-start).days * .55:
        raise ValueError('Response appears truncated or sparse; not imported')
    return [{'date': str(d), 'close': rows[d]} for d in sorted(rows)]


def filing_events(columns, ticker, start, end, member_hash):
    result = []
    for i, form in enumerate(columns.get('form', [])):
        if form not in {'10-Q', '10-K'}: continue
        filed = columns['filingDate'][i]
        if not str(start) <= filed <= str(end): continue
        raw = (columns.get('acceptanceDateTime') or [''] * len(columns['form']))[i]
        stamp = None
        if raw:
            try:
                dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
                if dt.tzinfo is not None: stamp = dt.astimezone(UTC).isoformat()
            except ValueError: pass
        result.append({'ticker': ticker, 'accession': columns['accessionNumber'][i],
                       'form': form, 'filedAt': filed, 'periodEnd': columns['reportDate'][i],
                       'acceptedAt': stamp, 'rawAcceptance': raw,
                       'timestampState': 'sec_acceptance_not_first_news' if stamp else 'missing_or_timezone_unverified',
                       'sourceMemberSha256': member_hash})
    return result


def archive_filings(bulk, output, start, end):
    target = output/'filing-events.json'
    if target.exists():
        saved=json.loads(target.read_text(encoding='utf-8'))
        if saved['start']!=str(start) or saved['end']!=str(end):raise ValueError('Existing date scope mismatch')
        return saved
    events=[]; sources=[]
    with zipfile.ZipFile(bulk/'submissions.zip') as z:
        for ticker,cik in CIKS.items():
            names=['CIK'+cik+'.json']
            main=json.loads(z.read(names[0]))
            names.extend(f['name'] for f in main['filings'].get('files', []))
            for name in names:
                raw=z.read(name); digest=hashlib.sha256(raw).hexdigest(); d=json.loads(raw)
                # Retain original SEC member in the cold artifact for reproducibility.
                write_json(output/'sec-members'/name,d)
                cols=d.get('filings',{}).get('recent',d)
                sources.append({'member':name,'uncompressedSha256':digest})
                events.extend(filing_events(cols,ticker,start,end,digest))
    if len({e['accession'] for e in events})!=len(events):raise ValueError('Duplicate SEC accession')
    result={'start':str(start),'end':str(end),'fetchedFrom':'locally archived SEC bulk',
            'events':sorted(events,key=lambda e:(e['filedAt'],e['accession'])),'sources':sources,
            'rule':'SEC acceptance is not necessarily the first public earnings release. Missing times are not invented.'}
    write_json(target,result);return result


def import_prices(symbol, rows, fetched):
    sid='TD:SPLITS:'+symbol
    with get_session_factory()() as s:
        existing=s.get(MarketSeries,sid)
        if existing and (existing.source_name!='Twelve Data' or existing.unit!='USD' or 'split-adjusted' not in existing.name):
            raise ValueError('Existing series basis/identity mismatch')
        if not existing:
            s.add(MarketSeries(series_id=sid,name=symbol+' split-adjusted close',category='equity' if symbol in CIKS else 'benchmark_etf',unit='USD',frequency='daily',source_name='Twelve Data',source_url='https://twelvedata.com/docs',region='US'))
        s.flush()
        values=[{'series_id':sid,'observed_on':date.fromisoformat(r['date']),'value':r['close'],'fetched_at':fetched} for r in rows]
        added=0
        for i in range(0,len(values),500):
            r=s.execute(insert(MarketObservation).values(values[i:i+500]).on_conflict_do_nothing(index_elements=['series_id','observed_on']).returning(MarketObservation.observed_on))
            added+=len(r.all())
        s.commit()
    return added


async def run(output, bulk, start, end):
    if start>=end or (end-start).days>3660:raise ValueError('One bounded request per symbol; maximum approximately ten years')
    if end>=datetime.now(UTC).date():raise ValueError('Use completed prior dates, not an intraday daily bar')
    settings=get_settings()
    if not settings.twelve_data_api_key:raise ValueError('Provider credential missing')
    scope={'start':str(start),'end':str(end),'adjustment':'splits','symbols':list(SYMBOLS)}
    spec=output/'scope.json'
    if spec.exists() and json.loads(spec.read_text(encoding='utf-8'))!=scope:raise ValueError('Preserve prior experiment scope')
    if not spec.exists():write_json(spec,scope)
    filings=archive_filings(bulk,output,start,end)
    results=[]; requests=0
    async with httpx.AsyncClient(timeout=45) as client:
        for symbol in SYMBOLS:
            path=output/'prices'/f'{symbol}.json'
            try:
                if path.exists(): saved=json.loads(path.read_text(encoding='utf-8'))
                else:
                    if requests: await asyncio.sleep(16)
                    requests+=1
                    r=await request_twelve_data(client,TWELVE_TIME_SERIES_URL,params={
                        'symbol':symbol,'interval':'1day','start_date':str(start),'end_date':str(end),
                        'order':'asc','adjust':'splits','outputsize':5000,
                        'apikey':settings.twelve_data_api_key.get_secret_value()},max_attempts=1)
                    if r.status_code!=200:raise ValueError('Provider HTTP '+str(r.status_code))
                    p=r.json()
                    if p.get('status')=='error':raise ValueError('Provider rejected request; code '+str(p.get('code')))
                    saved={'scope':scope,'symbol':symbol,'fetchedAt':datetime.now(UTC).isoformat(),
                           'source':'Twelve Data','response':p}
                    validate_prices(p,symbol,start,end)
                    write_json(path,saved)
                if saved['scope']!=scope or saved['symbol']!=symbol:raise ValueError('Archived request identity mismatch')
                rows=validate_prices(saved['response'],symbol,start,end)
                added=import_prices(symbol,rows,datetime.fromisoformat(saved['fetchedAt']))
                results.append({'symbol':symbol,'state':'retained','count':len(rows),'first':rows[0]['date'],
                                'last':rows[-1]['date'],'requestedEnd':str(end),
                                'coverageState':'ends_before_requested_date' if rows[-1]['date']<str(end) else 'requested_end_observed',
                                'insertedThisRun':added,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            except httpx.HTTPError:
                results.append({'symbol':symbol,'state':'source_error','reason':'Provider transport error; URL withheld'})
            except (ValueError,KeyError,TypeError):
                results.append({'symbol':symbol,'state':'source_error','reason':'Provider response/coverage validation failed; no automatic paid upgrade'})
            write_json(output/'progress.json',{'checkedAt':datetime.now(UTC).isoformat(),'prices':results,
                       'filingEvents':len(filings['events']),'benchmarkMapping':BENCHMARKS,'published':False,
                       'returnBasis':'Split-adjusted PRICE returns, not total returns. No dividend reinvestment.',
                       'eligibleForPredictiveBacktest':False})
            print(symbol,results[-1]['state'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,required=True);p.add_argument('--bulk',type=Path,required=True)
    p.add_argument('--start',type=date.fromisoformat,required=True);p.add_argument('--end',type=date.fromisoformat,required=True)
    a=p.parse_args();asyncio.run(run(a.output,a.bulk,a.start,a.end))
