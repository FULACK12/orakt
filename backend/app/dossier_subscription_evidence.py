"""Recover subscription dimensions from original 10-Q bodies, not total sales."""
import argparse,hashlib,json,time
from pathlib import Path
import httpx
from sqlalchemy import select
from app.company_history_dossier import write_json
from app.company_completion import download_body,filing_target,ua
from app.core.config import get_settings
from app.db.models import CompanyFiling
from app.db.session import get_session_factory
from app.inline_filing_facts import monetary_facts


def subscription_rows(rows,accession):
    output=[]
    for r in rows:
        dims=r.get('dimensions',{});base=r.get('base_concept',r['concept']);tag=None
        if not dims:
            # Older Adobe original filings use these explicit extension names.
            # Keep the original name in every evidence row; no generic revenue alias.
            tag={'SubscriptionRevenue':'SubscriptionRevenue','SubscriptionRevenues':'SubscriptionRevenue',
                 'SubscriptionandCirculationRevenue':'SubscriptionRevenue',
                 'CostOfGoodsSoldSubscription':'CostOfGoodsSoldSubscription',
                 'CostofSubscriptionRevenue':'CostOfGoodsSoldSubscription',
                 'CostOfSubscriptionRevenue':'CostOfGoodsSoldSubscription'}.get(base)
        if len(dims)==1:
            axis,member=next(iter(dims.items()))
            if axis.split(':')[-1]=='ProductOrServiceAxis' and member.split(':')[-1]=='SubscriptionRevenueMember':
                tag={'Revenues':'SubscriptionRevenue','RevenueFromContractWithCustomerExcludingAssessedTax':'SubscriptionRevenue',
                     'CostOfRevenue':'CostOfGoodsSoldSubscription'}.get(base)
        if tag and r['unit']=='USD':
            output.append({'concept':tag,'originalConcept':r['concept'],'evidence_id':r['evidence_id'],
                           'dimensions':dims,'start':r['period_start'],'end':r['period_end'],
                           'val':r['value'],'filed':r['filed_at'],'accn':accession,'source_url':r['source_url']})
    return output


def run(experiment,output):
    if output.exists():raise ValueError('Preserve prior extraction')
    source=json.loads(experiment.read_text(encoding='utf-8'))
    targets={e['accession'] for e in source['companies']['ADBE']['rules']['subscription']['events'] if e['state']=='feature_gap'}
    if len(targets)>30:raise ValueError('Bounded pilot permits at most thirty original bodies')
    result={'inputSha256':hashlib.sha256(experiment.read_bytes()).hexdigest(),'filings':{},'published':False}
    cold=get_settings().cold_data_root
    with get_session_factory()() as session,httpx.Client(headers={'User-Agent':ua()},timeout=40,follow_redirects=False) as client:
        filings=session.scalars(select(CompanyFiling).where(CompanyFiling.accession_number.in_(targets)).order_by(CompanyFiling.filed_at.desc())).all()
        for f in filings:
            try:
                state=download_body(client,f,cold);path=filing_target(f,cold);raw=path.read_bytes()
                manifest=json.loads(path.with_suffix(path.suffix+'.manifest.json').read_text(encoding='utf-8'))
                digest=hashlib.sha256(raw).hexdigest()
                if digest!=manifest['sha256']:raise ValueError('Archive checksum mismatch')
                rows,coverage=monetary_facts(raw.decode('utf-8'),filed_at=str(f.filed_at),source_url=f.source_url)
                selected=subscription_rows(rows,f.accession_number)
                result['filings'][f.accession_number]={'state':'extracted' if selected else 'unsupported_or_missing_subscription_dimension',
                    'sourcePath':str(path),'sourceSha256':digest,'parserCoverage':coverage,'rows':selected}
                print(f.accession_number,len(selected),'subscription rows',flush=True)
            except (httpx.HTTPError,ValueError,OSError) as exc:
                result['filings'][f.accession_number]={'state':'source_error','errorType':type(exc).__name__}
                if isinstance(exc,httpx.HTTPStatusError) and exc.response.status_code in (403,429):
                    result['blocked']='SEC access/rate limit; no bypass';write_json(output/'result.json',result);return
            write_json(output/'result.json',result)
            time.sleep(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--experiment',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.experiment,a.output)
