"""Bounded ten-report readiness plan and explicit one-report local benchmark.

Planning is not generation. Missing oldest filings remain gaps; the oldest
locally ready filing is never presented as the company's earliest existence.
"""
import argparse
import hashlib
import json
import time
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from sqlalchemy import select
from app.company_history_dossier import VERSION, CHAPTERS, enrich_inline, enrich_market, write_json
from app.company_completion import filing_target, check_pause
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.db.models import CompanyFiling
from app.historical_earnings_report import build_packet
from app.financial_period_ledger import build_ledger
from app.dossier_passages import add_passages

TICKERS=('NKE','ADBE','AAPL','NVDA','AMD')


def ready_packet(packet):
    gaps=[key for key,*_ in CHAPTERS if len(packet.get('chapter_passages',{}).get(key,[]))<2]
    if gaps:raise ValueError('Insufficient chapter passages: '+','.join(gaps))
    if not packet.get('financial_ledger',{}).get('comparisons'):raise ValueError('No financial comparisons')
    if any(f.get('filed_at','')>packet['as_of_date'] or f.get('period_end','')>packet['period_end'] for f in packet['facts']):
        raise ValueError('Future filing fact in historical packet')
    return {'facts':len(packet['facts']),'comparisons':len(packet['financial_ledger']['comparisons']),
            'chapterPassages':{key:len(packet['chapter_passages'][key]) for key,*_ in CHAPTERS},
            'meaning':'Source readiness only; narrative correctness and data completeness not certified.'}


def plan(root,output,cutoff):
    if output.exists():raise ValueError('Preserve existing plan')
    settings=get_settings();items=[];coverage=[];started=time.monotonic()
    with get_session_factory()() as session:
        for ticker in TICKERS:
            rows=session.scalars(select(CompanyFiling).where(CompanyFiling.ticker==ticker,
                CompanyFiling.form.in_(('10-Q','10-K')),CompanyFiling.filed_at<=cutoff,
                CompanyFiling.report_date.is_not(None)).order_by(CompanyFiling.filed_at,CompanyFiling.accession_number)).all()
            for form in ('10-Q','10-K'):
                candidates=[f for f in rows if f.form==form];skips=[];picked=None
                for f in candidates:
                    check_pause(root,'reports')
                    if not f.primary_document or not filing_target(f,settings.cold_data_root).is_file():
                        skips.append({'accession':f.accession_number,'state':'body_missing'});continue
                    try:
                        packet=build_packet(session,ticker=ticker,cold_root=settings.cold_data_root,accession=f.accession_number)
                        packet=enrich_inline(enrich_market(session,packet),settings.cold_data_root)
                        packet=add_passages(packet,settings.cold_data_root);packet['financial_ledger']=build_ledger(packet)
                        readiness=ready_packet(packet)
                    except (ValueError,OSError) as exc:
                        skips.append({'accession':f.accession_number,'state':'source_not_ready','reason':str(exc)[:300]});continue
                    fingerprint=hashlib.sha256(json.dumps({'version':VERSION,'packet':packet},sort_keys=True).encode()).hexdigest()
                    path=output/'packets'/ticker/f.accession_number/'source.json'
                    write_json(path,{'version':VERSION,'packet':packet,'fingerprint':fingerprint})
                    picked={'ticker':ticker,'form':form,'accession':f.accession_number,'filedAt':str(f.filed_at),
                        'periodEnd':str(f.report_date),'state':'ready_for_generation','sourcePath':str(path),
                        'sourceSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'readiness':readiness}
                    items.append(picked);break
                coverage.append({'ticker':ticker,'form':form,'indexed':len(candidates),
                    'earliestIndexed':str(candidates[0].filed_at) if candidates else None,
                    'earliestReady':picked['filedAt'] if picked else None,'skippedOlder':skips,
                    'notClaimedCompleteHistory':True})
                write_json(output/'planning-progress.json',{'stage':'source_preflight','checkedAt':datetime.now(UTC).isoformat(),'prepared':len(items),'target':10,'modelRequests':0})
    items.sort(key=lambda x:(x['filedAt'],x['ticker'],x['accession']))
    result={'version':'historical-dossier-pilot/v20','cutoff':str(cutoff),'createdAt':datetime.now(UTC).isoformat(),
        'target':10,'planned':len(items),'generated':0,'items':items,'coverage':coverage,
        'planningSeconds':round(time.monotonic()-started,3),'modelRequests':0,'published':False,
        'rule':'One earliest locally ready annual and quarterly filing per selected company; explicit older gaps retained. No task is generated by planning.'}
    write_json(output/'plan.json',result)
    write_json(output/'planning-progress.json',{'stage':'plan_ready','planned':len(items),'generated':0,'checkedAt':datetime.now(UTC).isoformat(),'modelRequests':0})
    return result


def execute(plan_path,output,index=0):
    from app.company_history_dossier import run
    from app.orakt_history_queue import resource_gate
    if output.exists():raise ValueError('Preserve previous benchmark; explicit new revision required')
    plan_raw=plan_path.read_bytes();p=json.loads(plan_raw);job=p['items'][index]
    source=Path(job['sourcePath'])
    if hashlib.sha256(source.read_bytes()).hexdigest()!=job['sourceSha256']:raise ValueError('Planned source changed')
    reason=resource_gate()
    if reason:raise RuntimeError('Resource gate: '+reason)
    output.mkdir(parents=True);started=time.monotonic()
    measurement={'ticker':job['ticker'],'accession':job['accession'],'startedAt':datetime.now(UTC).isoformat(),
        'planSha256':hashlib.sha256(plan_raw).hexdigest(),'sourceSha256':job['sourceSha256'],
        'stage':'running','published':False,'humanAccepted':False,'fullReportAccepted':False}
    write_json(output/'measurement.json',measurement)
    try:
        run(job['ticker'],job['accession'],output/'reports',frozen_source=source,max_failed_chapters=1)
        measurement['stage']='content_review_pending'
    except InterruptedError:
        measurement['stage']='safely_paused'
    except Exception as exc:
        measurement['stage']='repair_required';measurement['errorType']=type(exc).__name__;measurement['error']=str(exc)[:1200]
    finally:
        folder=output/'reports'/job['ticker']/job['accession'];tokens=0;attempts=0
        for path in folder.glob('*passage-selection*.json'):
            raw=json.loads(path.read_text(encoding='utf-8'))
            if raw.get('done'):
                attempts+=1;tokens+=raw.get('eval_count',0)
        measurement.update({'finishedAt':datetime.now(UTC).isoformat(),'elapsedSeconds':round(time.monotonic()-started,2),
            'completedModelAttempts':attempts,'outputTokens':tokens,'completedChapters':sum((folder/f'{i:02d}-{key}.json').exists() for i,(key,*_) in enumerate(CHAPTERS,1)),
            'throughputEligible':False,'note':'Do not estimate accepted-report throughput before whole-report review.'})
        write_json(output/'measurement.json',measurement)
        write_json(output/'chapter-progress.json',{'stage':measurement['stage'],'completedChapters':measurement['completedChapters'],
            'totalChapters':9,'checkedAt':datetime.now(UTC).isoformat(),'published':False})
    return measurement


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['plan','execute']);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--root',type=Path);p.add_argument('--plan',type=Path);p.add_argument('--index',type=int,default=0)
    p.add_argument('--cutoff',type=date.fromisoformat,default=date.today());a=p.parse_args()
    if a.action=='plan':
        if not a.root:p.error('--root required')
        if a.cutoff>date.today():p.error('No future cutoff')
        r=plan(a.root,a.output,a.cutoff);print(json.dumps({'planned':r['planned'],'generated':0}))
    else:
        if not a.plan:p.error('--plan required')
        print(json.dumps(execute(a.plan,a.output,a.index),ensure_ascii=False))
