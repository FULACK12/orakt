"""Retain provider corporate-action evidence without claiming total-return coverage."""
import argparse,asyncio,json
from datetime import UTC,datetime
from pathlib import Path
import httpx
from app.core.config import get_settings
from app.company_history_dossier import write_json
from app.dossier_study_evidence import SYMBOLS
from app.twelve_data_client import request_twelve_data


def classify(payload,symbol,kind):
    if payload.get('status')=='error':
        return {'state':'provider_unavailable','providerCode':payload.get('code'),
                'rule':'Unavailable is not proof that no corporate actions exist.'}
    if payload.get('meta',{}).get('symbol')!=symbol or not isinstance(payload.get(kind),list):
        return {'state':'unverified_schema'}
    rows=payload[kind]
    return {'state':'retained_unreconciled','records':len(rows),'completeCoverage':False,
            'rule':'Event dates, currency and split basis still require reconciliation; not a total-return attestation.'}


async def run(output):
    if output.exists():raise ValueError('Preserve previous corporate-action audit')
    output.mkdir(parents=True)
    key=get_settings().twelve_data_api_key
    if not key:raise ValueError('Configured provider credential required')
    statuses=[];i=0
    async with httpx.AsyncClient(timeout=35) as client:
        for kind in ('dividends','splits'):
            for symbol in SYMBOLS:
                if i:await asyncio.sleep(16)
                i+=1
                try:
                    r=await request_twelve_data(client,'https://api.twelvedata.com/'+kind,params={
                        'symbol':symbol,'start_date':'2010-01-01','end_date':'2026-10-05',
                        'apikey':key.get_secret_value()},max_attempts=1)
                    if r.status_code!=200:status={'state':'provider_unavailable','httpStatus':r.status_code}
                    else:
                        payload=r.json();status=classify(payload,symbol,kind)
                        if status['state']=='retained_unreconciled':
                            write_json(output/f'{symbol}-{kind}.json',{'symbol':symbol,'kind':kind,'requestedStart':'2010-01-01',
                                'requestedEnd':'2026-10-05','fetchedAt':datetime.now(UTC).isoformat(),'response':payload})
                except (httpx.HTTPError,ValueError):status={'state':'request_failed','detail':'Transport/JSON failure; credentials withheld'}
                statuses.append({'symbol':symbol,'kind':kind,**status})
                write_json(output/'status.json',{'results':statuses,'totalReturnVerified':False,
                    'rule':'No subscription upgrade or inferred zero dividends; original split-price studies unchanged.'})
                print(symbol,kind,status['state'],flush=True)
                if status.get('httpStatus') in (401,402,403,429) or status.get('providerCode') in (401,402,403,429):
                    return  # stop on entitlement/rate limit, never bypass or upgrade


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    asyncio.run(run(p.parse_args().output))
