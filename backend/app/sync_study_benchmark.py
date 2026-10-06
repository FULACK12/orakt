"""One bounded SOXX daily-history request using the configured data provider."""
import asyncio
import math
from datetime import date,datetime,UTC
import httpx
from sqlalchemy.dialects.postgresql import insert
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.db.models import MarketSeries,MarketObservation
from app.twelve_data_client import request_twelve_data,TWELVE_TIME_SERIES_URL
from app.company_history_dossier import write_json

async def run():
    s=get_settings()
    if not s.twelve_data_api_key:raise ValueError('Configured provider credential required')
    async with httpx.AsyncClient(timeout=45) as client:
        r=await request_twelve_data(client,TWELVE_TIME_SERIES_URL,params={'symbol':'SOXX','interval':'1day','start_date':'2023-01-01','end_date':'2025-06-30','order':'asc','adjust':'splits','outputsize':5000,'apikey':s.twelve_data_api_key.get_secret_value()},max_attempts=1)
    if r.status_code!=200:raise ValueError(f'Provider HTTP {r.status_code}; no retry')
    p=r.json()
    if p.get('status')=='error':raise ValueError(f"Provider declined benchmark request (code {p.get('code')}); no retry or plan change")
    if p.get('meta',{}).get('symbol')!='SOXX' or p.get('meta',{}).get('currency')!='USD':raise ValueError('Provider identity/currency mismatch')
    now=datetime.now(UTC);values=[];seen=set()
    for v in p.get('values',[]):
        d=date.fromisoformat(v['datetime']);value=float(v['close'])
        if not date(2023,1,1)<=d<=date(2025,6,30) or d in seen or not math.isfinite(value) or value<=0:raise ValueError('Invalid or duplicate benchmark observation')
        seen.add(d);values.append({'series_id':'TD:SOXX','observed_on':d,'value':value,'fetched_at':now})
    if len(values)<500:raise ValueError('Truncated benchmark response; not imported')
    archive=s.cold_data_root/'orakt/evidence-completion-v79'/'soxx-provider-response.json'
    if archive.exists():raise ValueError('Keep existing provider archive; no overwrite')
    write_json(archive,{'provider':'Twelve Data','fetchedAt':now.isoformat(),'adjust':'splits','response':p})
    with get_session_factory()() as session:
        existing=session.get(MarketSeries,'TD:SOXX')
        if existing and (existing.source_name!='Twelve Data' or existing.unit!='USD'):raise ValueError('Existing benchmark identity mismatch')
        if not existing:session.add(MarketSeries(series_id='TD:SOXX',name='iShares Semiconductor ETF (SOXX) split-adjusted close',category='sector_etf',unit='USD',frequency='daily',source_name='Twelve Data',source_url='https://twelvedata.com/docs',sector='Semiconductors',region='US'))
        session.flush()
        result=session.execute(insert(MarketObservation).values(values).on_conflict_do_nothing(index_elements=['series_id','observed_on']))
        session.commit()
    print({'series':'TD:SOXX','retained':len(values),'start':str(min(seen)),'end':str(max(seen)),'adjustment':'splits; not total return'})

if __name__=='__main__':asyncio.run(run())
