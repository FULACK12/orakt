"""Bounded source export for descriptive portfolio valuation, never trade execution."""
import argparse,hashlib,json,math,time,csv,io
from datetime import date,datetime,UTC,timedelta
from pathlib import Path
import httpx
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.db.models import MarketSeries
from app.research_lab_export import series_rows
from app.company_history_dossier import write_json

def run(site,cutoff):
    settings=get_settings();root=settings.cold_data_root/'orakt/portfolio-v89';root.mkdir(parents=True,exist_ok=True)
    assets={};errors=[]
    with get_session_factory()() as session:
        for key in ['EQ:AAPL','EQ:NVDA','EQ:AMD','EQ:MSFT','EQ:LULU','TD:SPY','TD:XLK','CN:600519','CN:002594']:
            meta=session.get(MarketSeries,key)
            rows=[[str(d),v] for d,v in series_rows(session,key) if date(2015,1,1)<=d<=cutoff]
            assets[key]={'currency':meta.unit if meta else None,'sourceUrl':meta.source_url if meta else None,'points':rows}
    with httpx.Client(timeout=30,follow_redirects=True,headers={'User-Agent':'ORAKT-research/1.0'}) as client:
        # H.10 is CNY per one USD: divide the local currency price by this fixing.
        if settings.fred_api_key:
            try:
                response=client.get('https://api.stlouisfed.org/fred/series/observations',params={'series_id':'DEXCHUS','api_key':settings.fred_api_key.get_secret_value(),'file_type':'json','observation_start':'2015-01-01','observation_end':str(cutoff)})
                response.raise_for_status();raw=response.json();write_json(root/'fred-DEXCHUS.json',raw)
                points=[]
                for r in raw.get('observations',[]):
                    try:v=float(r['value'])
                    except (ValueError,TypeError):continue
                    if math.isfinite(v) and v>0 and r['date']<=str(cutoff):points.append([r['date'],v])
                assets['FX:CNYUSD']={'currency':'CNY per USD','sourceUrl':'https://fred.stlouisfed.org/series/DEXCHUS','points':sorted(points)}
            except Exception as exc:errors.append({'source':'DEXCHUS','errorType':type(exc).__name__})
        if 'FX:CNYUSD' not in assets:
            try:
                r=client.get('https://fred.stlouisfed.org/graph/fredgraph.csv',params={'id':'DEXCHUS','cosd':'2015-01-01','coed':str(cutoff)});r.raise_for_status()
                rows=list(csv.DictReader(io.StringIO(r.text)));points=[]
                for row in rows:
                    d=row.get('observation_date') or row.get('DATE');v=row.get('DEXCHUS')
                    try:value=float(v)
                    except (ValueError,TypeError):continue
                    if d and '2015-01-01'<=d<=str(cutoff) and math.isfinite(value) and value>0:points.append([d,value])
                if not points:raise ValueError('Missing FX observations')
                write_json(root/'fred-DEXCHUS-public.json',{'source':'FRED public CSV','observations':rows})
                assets['FX:CNYUSD']={'currency':'CNY per USD','sourceUrl':'https://fred.stlouisfed.org/series/DEXCHUS','points':sorted(points)}
            except Exception as exc:errors.append({'source':'DEXCHUS-public','errorType':type(exc).__name__})
        for product in ['BTC-USD','ETH-USD']:
            points={};cursor=date(2021,1,1)
            while cursor<cutoff:
                end=min(cursor+timedelta(days=280),cutoff)
                path=root/f'{product}-{cursor}-{end}.json'
                try:
                    if path.exists():raw=json.loads(path.read_text(encoding='utf-8'))
                    else:
                        r=client.get(f'https://api.exchange.coinbase.com/products/{product}/candles',params={'start':str(cursor)+'T00:00:00Z','end':str(end)+'T00:00:00Z','granularity':86400});r.raise_for_status();raw=r.json()
                        if not isinstance(raw,list):raise ValueError('Expected candle rows')
                        write_json(path,raw);time.sleep(.4)
                    for row in raw:
                        if not isinstance(row,list) or len(row)<6:continue
                        d=datetime.fromtimestamp(row[0],UTC).date();close=float(row[4])
                        if date(2021,1,1)<=d<cutoff and math.isfinite(close) and 0<float(row[1])<=close<=float(row[2]):points[str(d)]=close
                except Exception as exc:
                    errors.append({'source':product,'start':str(cursor),'errorType':type(exc).__name__});break
                cursor=end
            assets['CB:'+product]={'currency':'USD','sourceUrl':f'https://api.exchange.coinbase.com/products/{product}/candles','points':sorted(points.items()),'bar':'UTC daily; current day excluded'}
    payload={'version':'portfolio-prices/v1','generatedAt':datetime.now(UTC).isoformat(),'cutoff':str(cutoff),'assets':assets,'errors':errors,'sources':{'fx':'https://fred.stlouisfed.org/series/DEXCHUS','crypto':'https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles'},'priceConvention':'Retained closes; original vintage and dividend/split conventions not fully verified. Cross-market closes are asynchronous.'}
    write_json(root/'portfolio-prices.json',payload);write_json(site/'private-data/portfolio-prices.json',payload)
    print(json.dumps({'series':{k:{'count':len(v['points']),'from':v['points'][0][0] if v['points'] else None,'to':v['points'][-1][0] if v['points'] else None} for k,v in assets.items()},'errors':errors}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--site',type=Path,required=True);p.add_argument('--cutoff',type=date.fromisoformat,required=True);a=p.parse_args();run(a.site,a.cutoff)
