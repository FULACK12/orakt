"""Deterministic exploratory multi-factor and basket studies, never live trading."""
import argparse,hashlib,json,math,random
from datetime import date,datetime,UTC
from pathlib import Path
from statistics import pstdev,fmean
from app.research_lab_export import series_rows
from app.db.models import MarketSeries
from app.db.session import get_session_factory
from app.company_history_dossier import write_json

def interval(values):
    if len(values)<20:return None
    rng=random.Random(84);n=len(values);draws=[]
    for _ in range(500):
        sample=[]
        while len(sample)<n:
            start=rng.randrange(n);sample.extend(values[(start+j)%n] for j in range(5))
        draws.append(fmean(sample[:n])*100)
    draws.sort();return {'lower':draws[12],'upper':draws[487],'method':'circular block bootstrap; 5 holdings; 500 draws; seed 84; no multiple-testing correction'}

def multifactor(stock,market,industry,mode):
    maps=[dict(s) for s in (stock,market,industry)];dates=sorted(maps[1]);points=[];trades=[];nav=[100.,100.,100.];peak=100.;maxdd=0
    for entry in range(61,len(dates)-5,5):
        exit=entry+5;lookback=dates[entry-61:exit+1]
        if any(d not in m for m in maps for d in lookback):continue
        s=entry-1;prices=maps[0];momentum=prices[dates[s]]/prices[dates[s-20]]-1
        trend=prices[dates[s]]/fmean(prices[d] for d in dates[s-59:s+1])-1
        vol=pstdev(prices[dates[i]]/prices[dates[i-1]]-1 for i in range(s-19,s+1))
        score=(int(momentum>0)+int(trend>0)+int(vol<.03))/3
        invest=score>=2/3 if mode=='linear' else momentum>0 and trend>0 and vol<.03
        returns=[m[dates[exit]]/m[dates[entry]]-1 for m in maps];net=(returns[0]-.0024) if invest else 0
        if not points:points.append({'date':str(dates[entry]),'strategy':100.,'market':100.,'industry':100.,'drawdown':0.})
        for i,r in enumerate([net,returns[1],returns[2]]):nav[i]*=1+r
        peak=max(peak,nav[0]);dd=(nav[0]/peak-1)*100;maxdd=min(maxdd,dd)
        points.append({'date':str(dates[exit]),'strategy':nav[0],'market':nav[1],'industry':nav[2],'drawdown':dd})
        trades.append({'signal':str(dates[s]),'entry':str(dates[entry]),'exit':str(dates[exit]),'score':score,'position':int(invest),'net':net,'market':returns[1],'industry':returns[2]})
    return {'mode':mode,'state':'exploratory_not_validated' if trades else 'insufficient_data','samples':len(trades),'netReturnPercent':nav[0]-100 if trades else None,'maxDrawdownPercent':maxdd if trades else None,'points':points,'trades':trades,'marketCI':interval([r['net']-r['market'] for r in trades]),'industryCI':interval([r['net']-r['industry'] for r in trades]),'validatedAlpha':False,'inputHash':hashlib.sha256(json.dumps([[[str(d),v] for d,v in s] for s in (stock,market,industry)]).encode()).hexdigest()}

def basket_study(data,weights,days):
    required=[s for s in weights if s!='CASH:USD']+['TD:SPY'];maps={s:dict(data.get(s,[])) for s in required}
    dates=sorted(set.intersection(*(set(m) for m in maps.values()))) if all(maps.values()) else []
    if not dates:return {'state':'insufficient_data','points':[]}
    last=dates[-1];dates=[d for d in dates if (last-d).days<=days]
    if len(dates)<10:return {'state':'insufficient_data','points':[]}
    points=[];peak=100.;dd=0.;initial=dates[0]
    for i,d in enumerate(dates):
        gross=sum(w*(1 if s=='CASH:USD' else maps[s][d]/maps[s][initial]) for s,w in weights.items())*100
        # Hypothetical 10 bp entry and 10 bp exit on risky holdings, not on cash.
        cash=weights.get('CASH:USD',0)*100;risky=gross-cash
        net=100. if i==0 else cash+risky*.999*(.999 if i==len(dates)-1 else 1)
        peak=max(peak,net);dd=min(dd,(net/peak-1)*100)
        points.append({'date':str(d),'nav':net,'benchmark':maps['TD:SPY'][d]/maps['TD:SPY'][initial]*100})
    return {'state':'retrospective_illustration','points':points,'returnPercent':points[-1]['nav']-100,'maxDrawdownPercent':dd,'observations':len(points),'annualizedReturn':None,'start':str(initial),'end':str(last),'roundTripCostBps':20,'inputHash':hashlib.sha256(json.dumps({s:[[str(d),m[d]] for d in dates] for s,m in maps.items()}).encode()).hexdigest()}

def run(site,cold):
    root=cold/'orakt/lab-v84';ids=['EQ:AAPL','EQ:NVDA','EQ:AMD','EQ:MSFT','EQ:LULU','TD:SPY','TD:XLK']
    with get_session_factory()() as session:
        data={s:series_rows(session,s) for s in ids};sources={s:session.get(MarketSeries,s).source_url for s in ids if session.get(MarketSeries,s)}
    factors=[]
    for ticker in ['AAPL','NVDA','AMD']:
        for mode in ['linear','interaction']:
            study=multifactor(data['EQ:'+ticker],data['TD:SPY'],data['TD:XLK'],mode);study.update(ticker=ticker,sources={s:sources.get(s) for s in ['EQ:'+ticker,'TD:SPY','TD:XLK']})
            write_json(root/f'{ticker}-{mode}.json',study);factors.append({k:v for k,v in study.items() if k!='trades'})
    recipes=[('tech-core',{'zh':'科技核心研究篮子','en':'Technology core study'},{'EQ:AAPL':.35,'EQ:NVDA':.25,'EQ:MSFT':.25,'CASH:USD':.15}),('chip-pair',{'zh':'半导体双公司研究篮子','en':'Semiconductor pair study'},{'EQ:NVDA':.5,'EQ:AMD':.5}),('consumer-tech',{'zh':'消费与科技研究篮子','en':'Consumer & technology study'},{'EQ:LULU':.4,'EQ:AAPL':.4,'CASH:USD':.2})]
    baskets=[{'id':key,'title':title,'weights':weights,'windows':{str(days):basket_study(data,weights,days) for days in [30,90,365]},'sources':{s:sources.get(s) for s in [*weights,'TD:SPY'] if s!='CASH:USD'},'followers':None} for key,title,weights in recipes]
    payload={'generatedAt':datetime.now(UTC).isoformat(),'factors':factors,'baskets':baskets,'multipleTests':len(factors),'multipleTestingAdjusted':False,'forwardValidated':False,'priceConvention':'retained close; split/dividend adjustment not fully verified','selectionBias':'current selected constituents; not historical investible universe'}
    write_json(root/'lab-expansion.json',payload);write_json(site/'private-data/lab-expansion.json',payload)
    print(json.dumps({'factorExperiments':len(factors),'portfolioStudies':len(baskets),'validFactorStudies':sum(bool(f['points']) for f in factors),'validPortfolioWindows':sum(bool(w['points']) for b in baskets for w in b['windows'].values())}))

if __name__=='__main__':
    from app.core.config import get_settings
    p=argparse.ArgumentParser();p.add_argument('--site',type=Path,required=True);a=p.parse_args();run(a.site,get_settings().cold_data_root)
