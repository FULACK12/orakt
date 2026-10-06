"""Auditable price-path experiments and event windows, never certified Alpha."""
import argparse, hashlib, json, math, random, re
from datetime import date, datetime, UTC
from pathlib import Path
from statistics import fmean
from urllib.parse import urljoin
import httpx
from sqlalchemy import select
from app.db.session import get_session_factory
from app.db.models import MarketObservation, MarketSeries
from app.company_history_dossier import write_json

def series_rows(session, key):
    return [(r.observed_on,float(r.value)) for r in session.scalars(select(MarketObservation).where(MarketObservation.series_id==key).order_by(MarketObservation.observed_on)) if math.isfinite(r.value) and r.value>0]

def momentum_study(stock,market,industry):
    maps=[dict(r) for r in (stock,market,industry)]
    dates=sorted(set(maps[0]) & set(maps[1]) & set(maps[2]))
    if len(dates)<100:return {'state':'insufficient_data','points':[]}
    # Immutable research rule: 20-session momentum, one-session execution lag,
    # five-session nonoverlapping holdings. No train-set selection or optimization.
    trades=[];points=[];nav=[100.,100.,100.];peak=100.;max_dd=0.
    for entry in range(21,len(dates)-5,5):
        end=entry+5;signal=entry-1
        if (dates[end]-dates[entry]).days>12:continue
        position=int(maps[0][dates[signal]]>maps[0][dates[signal-20]])
        changes=[m[dates[end]]/m[dates[entry]]-1 for m in maps]
        net=position*changes[0]-(0.0024 if position else 0.)
        if not points:points.append({'date':str(dates[entry]),'strategy':100.,'market':100.,'industry':100.,'drawdown':0.})
        for i,r in enumerate([net,changes[1],changes[2]]):nav[i]*=1+r
        peak=max(peak,nav[0]);dd=nav[0]/peak-1;max_dd=min(max_dd,dd)
        points.append({'date':str(dates[end]),'strategy':round(nav[0],6),'market':round(nav[1],6),'industry':round(nav[2],6),'drawdown':round(dd*100,6)})
        trades.append({'signalDate':str(dates[signal]),'entryDate':str(dates[entry]),'exitDate':str(dates[end]),'position':position,'netReturn':net,'marketReturn':changes[1],'industryReturn':changes[2]})
    if not trades:return {'state':'insufficient_data','points':[]}
    # Moving-block bootstrap: preserve short-range dependence across holdings.
    def interval(key):
        values=[r['netReturn']-r[key] for r in trades];rng=random.Random(82);samples=[];n=len(values)
        for _ in range(500):
            sample=[]
            while len(sample)<n:
                start=rng.randrange(n);sample.extend(values[(start+j)%n] for j in range(5))
            samples.append(fmean(sample[:n])*100)
        samples.sort();return {'lower':samples[12],'upper':samples[487],'level':.95,'unit':'percentage_points_per_5_session_holding','method':'circular moving-block bootstrap; block=5 holdings; 500 resamples; seed=82'}
    return {'state':'exploratory_not_validated','rule':'momentum20_lag1_hold5_long_or_cash_v1','points':points,'trades':trades,'samples':len(trades),'maxDrawdownPercent':max_dd*100,'meanExcessVsMarketCI':interval('marketReturn'),'meanExcessVsIndustryCI':interval('industryReturn'),'netReturnPercent':nav[0]-100,'roundTripCostBps':24,'validatedAlpha':False,'inputHash':hashlib.sha256(json.dumps([[str(d),*[m[d] for m in maps]] for d in dates]).encode()).hexdigest()}

def event_window(rows, event_date, horizon, yield_series=False):
    before=[(d,v) for d,v in rows if d<event_date]
    after=[(d,v) for d,v in rows if d>=event_date]
    if not before or len(after)<horizon:return None
    start,value=before[-1];end,final=after[horizon-1]
    if (event_date-start).days>7 or (end-event_date).days>horizon*2+7:return None
    return {'start':str(start),'end':str(end),'startValue':value,'endValue':final,'change':(final-value)*100 if yield_series else (final/value-1)*100,'unit':'bp' if yield_series else '%'}

def run(site,cold):
    root=cold/'orakt/research-lab-v82';root.mkdir(parents=True,exist_ok=True)
    now=datetime.now(UTC).isoformat()
    with get_session_factory()() as session:
        ids=['EQ:AAPL','EQ:NVDA','EQ:AMD','TD:SPY','TD:XLK','DGS2','DGS10'];data={k:series_rows(session,k) for k in ids}
        sources={k:session.get(MarketSeries,k).source_url for k in ids if session.get(MarketSeries,k)}
        studies=[]
        for ticker in ['AAPL','NVDA','AMD']:
            study=momentum_study(data['EQ:'+ticker],data['TD:SPY'],data['TD:XLK']);study.update(ticker=ticker,marketBenchmark='TD:SPY',industryBenchmark='TD:XLK',sources={k:v for k,v in sources.items() if k in ['EQ:'+ticker,'TD:SPY','TD:XLK']})
            write_json(root/f'alpha-{ticker}.json',study)
            studies.append({k:v for k,v in study.items() if k!='trades'})
        alpha={'schema':'alpha-lab/v1','generatedAt':now,'experiments':studies,'limitations':['Retrospective fixed-rule illustration, not preregistered or forward-validated.','Retained close data; original price vintages and dividend adjustment are not fully verified.','24 bp per invested holding includes assumed 20 bp fees and 4 bp slippage; no cash interest, taxes or market impact.','Disjoint holding periods can remain serially dependent. Industry benchmark XLK is a broad technology proxy.','No multiple-testing correction. These are new reference experiments, not reconstructed paths of older factor reports.']}
        write_json(site/'private-data/alpha-lab.json',alpha)
        urls={
          'https://www.federalreserve.gov/newsevents/pressreleases/monetary20090318a.htm':('FOMC','2009-03-18'),
          'https://www.bls.gov/news.release/archives/empsit_02062009.htm':('NFP','2009-02-06'),
          'https://www.bls.gov/news.release/archives/empsit_08072009.htm':('NFP','2009-08-07'),
          'https://www.bls.gov/news.release/archives/empsit_10022009.htm':('NFP','2009-10-02')}
        index='https://www.federalreserve.gov/monetarypolicy/fomchistorical2009.htm'
        errors=[]
        with httpx.Client(timeout=30,follow_redirects=False) as client:
            try:
                response=client.get(index);response.raise_for_status()
                for link in re.findall(r'href=[\"\x27]([^\"\x27]+)',response.text):
                    url=urljoin(index,link);match=re.search(r'monetary(2009\d{4})[a-z]\.htm$',url)
                    if match and url.startswith('https://www.federalreserve.gov/newsevents/pressreleases/'):
                        d=match[1];urls[url]=('FOMC',f'{d[:4]}-{d[4:6]}-{d[6:]}')
            except httpx.HTTPError:errors.append('FOMC index retrieval unavailable')
            events=[]
            for url,(kind,day) in sorted(urls.items(),key=lambda x:x[1][1]):
                record={'id':kind+'-'+day,'kind':kind,'date':day,'sourceUrl':url,'sourceStatus':'metadata_only','sourceHash':None,'windows':[],'status':'descriptive_event_study_not_causal'}
                try:
                    r=client.get(url);r.raise_for_status()
                    if len(r.content)<1000:raise ValueError('Incomplete source')
                    digest=hashlib.sha256(r.content).hexdigest();target=root/(digest+'.html')
                    if not target.exists():target.write_bytes(r.content)
                    record.update(sourceStatus='original_archived',sourceHash=digest)
                except (httpx.HTTPError,ValueError):pass
                for key in ids:
                    windows={str(h):event_window(data[key],date.fromisoformat(day),h,key.startswith('DGS')) for h in [1,5,20]}
                    record['windows'].append({'series':key,'sourceUrl':sources.get(key),'horizons':windows})
                events.append(record)
        result={'schema':'macro-event-studies/v1','generatedAt':now,'target':'FOMC and payroll releases; oldest accessible first','coverageComplete':False,'events':events,'errors':errors,'method':'Prior-session close to event-day / fifth / twentieth available session. Yield changes in basis points; equities in percent. Daily data includes other same-day news and is not a causal estimate.','missing':['Intraday release-window prices','Survey consensus / surprise measures','Original-vintage macro observations','Company-news and earnings confounder controls']}
        write_json(root/'macro-events.json',result);write_json(site/'private-data/macro-events.json',result)
    print(json.dumps({'experiments':len(studies),'eventStudies':len(events),'firstEvent':events[0]['date'] if events else None,'lastEvent':events[-1]['date'] if events else None,'sourcesArchived':sum(r['sourceStatus']=='original_archived' for r in events)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--site',type=Path,required=True);p.add_argument('--cold',type=Path,required=True);a=p.parse_args();run(a.site,a.cold)
