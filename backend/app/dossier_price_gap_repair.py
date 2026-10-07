"""Fetch only two audited missing-session neighborhoods; retain raw responses."""
import argparse,asyncio,hashlib,json,math
from datetime import date,timedelta,UTC,datetime
from pathlib import Path
import httpx
from app.company_history_dossier import write_json
from app.core.config import get_settings
from app.dossier_study_evidence import SYMBOLS
from app.twelve_data_client import request_twelve_data,TWELVE_TIME_SERIES_URL


def select_missing(payload,symbol,day):
    meta=payload.get('meta',{})
    if meta.get('symbol')!=symbol or meta.get('currency')!='USD' or meta.get('interval')!='1day':raise ValueError('Identity mismatch')
    matches=[r for r in payload.get('values',[]) if r['datetime']==day]
    if len(matches)!=1:raise ValueError('Requested missing session not uniquely returned')
    value=float(matches[0]['close'])
    if not math.isfinite(value) or value<=0:raise ValueError('Invalid price')
    return {'date':day,'close':value}


async def run(output):
    if output.exists():raise ValueError('Preserve prior gap repair')
    output.mkdir(parents=True);result={'adjustment':'splits','prices':{s:{} for s in SYMBOLS},'attempts':[]}
    key=get_settings().twelve_data_api_key
    if not key:raise ValueError('Configured credential required')
    count=0
    async with httpx.AsyncClient(timeout=35) as client:
        for day in ('2019-12-31','2026-10-05'):
            d=date.fromisoformat(day)
            for symbol in SYMBOLS:
                if count:await asyncio.sleep(16)
                count+=1
                try:
                    r=await request_twelve_data(client,TWELVE_TIME_SERIES_URL,params={'symbol':symbol,'interval':'1day',
                        'start_date':str(d-timedelta(days=1)),'end_date':str(d+timedelta(days=1)),
                        'adjust':'splits','order':'asc','outputsize':10,'apikey':key.get_secret_value()},max_attempts=1)
                    if r.status_code!=200:
                        result['attempts'].append({'symbol':symbol,'date':day,'state':'unavailable','httpStatus':r.status_code})
                        write_json(output/'result.json',result)
                        if r.status_code in (401,402,403,429):return
                        continue
                    p=r.json();selected=select_missing(p,symbol,day)
                    path=output/f'{symbol}-{day}.json'
                    write_json(path,{'fetchedAt':datetime.now(UTC).isoformat(),'selectedDate':day,'response':p})
                    result['prices'][symbol][day]={'close':selected['close'],'archivePath':str(path),'archiveSha256':hashlib.sha256(path.read_bytes()).hexdigest()}
                    state='retained'
                except (httpx.HTTPError,ValueError,KeyError,TypeError):state='unresolved'
                result['attempts'].append({'symbol':symbol,'date':day,'state':state})
                write_json(output/'result.json',result);print(symbol,day,state,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    asyncio.run(run(p.parse_args().output))
