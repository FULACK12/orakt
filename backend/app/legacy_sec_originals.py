"""Recover named primary submission files from official legacy SEC indexes.

Only missing document pointers are filled, after archival and SGML form checks.
This does NOT normalize pre-XBRL financial tables or mark reports complete.
"""
import argparse
import json
import re
import time
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
import httpx
from sqlalchemy import select,text
from app.company_completion import REPORT_FORMS, ua, download_body, filing_target, check_pause
from app.company_history_dossier import write_json
from app.core.config import get_settings
from app.db.models import CompanyFiling
from app.db.session import get_session_factory
from app.leader_report_batch import now


def submission_name(index,accession):
    expected=accession+'.txt'
    names=[row.get('name') for row in index.get('directory',{}).get('item',[])]
    if expected not in names:raise ValueError('Official index does not name the accession submission')
    return expected


def verify_submission(body,accession,form):
    if not re.search(r'ACCESSION NUMBER:\s*'+re.escape(accession),body[:20000]):
        raise ValueError('Submission accession mismatch')
    if not re.search(r'<DOCUMENT>\s*<TYPE>\s*'+re.escape(form)+r'\s',body,re.I):
        raise ValueError('Original periodic form not found in SGML submission')


def run(root,ticker,cutoff,include_named=False,accessions=None,pause_root=None):
    settings=get_settings();progress=root/'legacy-originals-progress.json'
    state=json.loads(progress.read_text(encoding='utf-8')) if progress.exists() else {'ticker':ticker,'cutoff':str(cutoff),'results':[],'published':False}
    if state['ticker']!=ticker or state['cutoff']!=str(cutoff):raise ValueError('Frozen scope mismatch')
    def save(stage):state.update(stage=stage,checkedAt=now());write_json(progress,state)
    with get_session_factory()() as db,httpx.Client(headers={'User-Agent':ua()},timeout=60,follow_redirects=False) as client:
        # Single migration owner. Existing collector skips null document pointers.
        with db.get_bind().connect() as owner:
            if not owner.scalar(text('SELECT pg_try_advisory_lock(624730015837)')):raise RuntimeError('Legacy original recovery already running')
            try:
                rows=db.scalars(select(CompanyFiling).where(CompanyFiling.ticker==ticker,
                    CompanyFiling.form.in_(REPORT_FORMS),CompanyFiling.filed_at<=cutoff,
                    True if include_named else CompanyFiling.primary_document.is_(None)).order_by(CompanyFiling.filed_at)).all()
                done={r['accession'] for r in state['results']}
                for f in rows:
                    if accessions is not None and f.accession_number not in accessions:continue
                    if f.accession_number in done:continue
                    if pause_root:check_pause(pause_root,'reports')
                    check_pause(root,'reports');save('retrieving')
                    u=urlsplit(f.source_url)
                    if u.scheme!='https' or u.netloc!='www.sec.gov' or not u.path.startswith('/Archives/edgar/data/'):
                        raise ValueError('Unsupported original host/path')
                    folder=f.source_url.rstrip('/')+'/'
                    result={'accession':f.accession_number,'filedAt':str(f.filed_at),'state':'retrieving'}
                    try:
                        if f.primary_document:
                            outcome=download_body(client,f,settings.cold_data_root)
                            result.update(state='original_archived',path=str(filing_target(f,settings.cold_data_root)),
                                result=outcome,financialNormalization='not_completed')
                            state['results'].append(result);save('between_documents');time.sleep(1);continue
                        response=client.get(folder+'index.json');response.raise_for_status()
                        name=submission_name(response.json(),f.accession_number)
                        candidate=SimpleNamespace(ticker=f.ticker,accession_number=f.accession_number,primary_document=name,
                            source_url=folder+name,filed_at=f.filed_at,form=f.form)
                        time.sleep(1)
                        download_body(client,candidate,settings.cold_data_root)
                        path=filing_target(candidate,settings.cold_data_root)
                        verify_submission(path.read_text(encoding='utf-8',errors='replace'),f.accession_number,f.form)
                        # Never replace a concurrent non-null pointer or original report.
                        db.refresh(f)
                        if f.primary_document is not None:raise ValueError('Document pointer changed concurrently')
                        f.primary_document=name;f.source_url=candidate.source_url;db.commit()
                        result.update(state='original_archived',path=str(path),financialNormalization='not_completed')
                    except (httpx.HTTPError,ValueError,OSError) as exc:
                        db.rollback();result.update(state='source_gap',reason=str(exc)[:350])
                        if isinstance(exc,httpx.HTTPStatusError) and exc.response.status_code in (403,429):
                            state['results'].append(result);save('source_access_backoff');return state
                    state['results'].append(result);save('between_documents');time.sleep(1)
                save('pass_finished');return state
            finally:owner.execute(text('SELECT pg_advisory_unlock(624730015837)'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--ticker',required=True)
    p.add_argument('--include-named',action='store_true',help='Also retrieve indexed missing named primary documents; existing originals are never overwritten')
    p.add_argument('--cutoff',type=date.fromisoformat,required=True);a=p.parse_args()
    r=run(a.root,a.ticker,a.cutoff,a.include_named);print(json.dumps({'stage':r['stage'],'documents':len(r['results'])}))
