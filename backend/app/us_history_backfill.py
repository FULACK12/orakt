"""Issuer/filing coverage ledger. No index count is called a completed report."""
import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime,UTC
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from sqlalchemy import select,func,text,and_
from app.core.config import get_settings
from app.db.models import CompanyProfile,CompanyFiling,CompanyFinancialFact
from app.db.session import get_session_factory
from app.company_history_dossier import write_json,enrich_inline,enrich_market,VERSION
from app.historical_earnings_report import build_packet
from app.financial_period_ledger import build_ledger
from app.orakt_history_queue import resource_gate

FORMS=('10-Q','10-K','10-Q/A','10-K/A','20-F','20-F/A','40-F','40-F/A')
def now():return datetime.now(UTC).isoformat()
def connect(root):
 root.mkdir(parents=True,exist_ok=True);db=sqlite3.connect(root/'coverage.sqlite3',timeout=30);db.row_factory=sqlite3.Row
 db.execute('PRAGMA journal_mode=WAL')
 db.execute('CREATE TABLE IF NOT EXISTS filings(accession TEXT PRIMARY KEY,ticker TEXT,form TEXT,filed_at TEXT,period_end TEXT,source_url TEXT,document TEXT,fact_count INTEGER,body_present INTEGER,state TEXT,detail TEXT,updated_at TEXT)')
 return db

def classify(form,period,body,facts,reviewed=False,draft=False):
 if reviewed:return 'published_reviewed'
 if draft:return 'draft_retained'
 if form not in ('10-Q','10-K'):return 'adapter_required'
 if not period:return 'period_missing'
 if not body:return 'body_missing'
 if facts<10:return 'facts_missing'
 return 'ready_preflight'

def catalog(root,client):
 target=root/'sec-directory.json'
 if target.exists():return json.loads(target.read_text(encoding='utf-8'))
 r=client.get('https://www.sec.gov/files/company_tickers_exchange.json');r.raise_for_status();p=r.json()
 if not {'fields','data'}<=p.keys() or not {'cik','ticker','exchange','name'}<=set(p['fields']):raise ValueError('SEC directory schema mismatch')
 rows=[dict(zip(p['fields'],r)) for r in p['data']]
 value={'retrievedAt':now(),'sourceUrl':'https://www.sec.gov/files/company_tickers_exchange.json','sourceHash':hashlib.sha256(r.content).hexdigest(),'rows':rows,'scope':'SEC current ticker directory; asset-type and historical/delisted-universe completeness not established'}
 write_json(target,value);return value

def plan(root,site,fetch_directory=False):
 settings=get_settings();published=set();drafts=set()
 index_path=site/'snapshot/research-report-index.json'
 published_ids={r['id'] for r in json.loads(index_path.read_text(encoding='utf-8'))['reports']} if index_path.exists() else set()
 for path in (site/'private-data/company-dossiers').glob('*.json'):
  if path.stem not in published_ids:continue
  d=json.loads(path.read_text(encoding='utf-8'))
  if d.get('review',{}).get('state')=='assistant_reviewed':published.update(s['id'].removeprefix('SEC:') for s in d.get('sources',[]) if s['id'].startswith('SEC:'))
 for path in (settings.cold_data_root/'orakt').glob('history*/reports/*/*/source.json'):drafts.add(path.parent.name)
 ua=settings.sec_user_agent+(' '+settings.sec_contact_email.get_secret_value() if settings.sec_contact_email else '')
 directory=None
 if fetch_directory:
  with httpx.Client(headers={'User-Agent':ua},timeout=45,follow_redirects=False) as client:directory=catalog(root,client)
 elif (root/'sec-directory.json').exists():directory=json.loads((root/'sec-directory.json').read_text(encoding='utf-8'))
 with get_session_factory()() as s,connect(root) as db:
  companies=list(s.scalars(select(CompanyProfile).order_by(CompanyProfile.ticker)))
  # Same-accession facts available by that filing date, not later restatements.
  counts=dict(s.execute(select(CompanyFinancialFact.accession_number,func.count()).join(CompanyFiling,and_(CompanyFiling.accession_number==CompanyFinancialFact.accession_number,CompanyFiling.ticker==CompanyFinancialFact.ticker)).where(CompanyFiling.form.in_(FORMS),CompanyFinancialFact.filed_at<=CompanyFiling.filed_at,CompanyFinancialFact.period_end<=CompanyFiling.report_date).group_by(CompanyFinancialFact.accession_number)).all())
  filings=s.scalars(select(CompanyFiling).where(CompanyFiling.form.in_(FORMS)).order_by(CompanyFiling.filed_at,CompanyFiling.accession_number)).all()
  for f in filings:
   base=(settings.cold_data_root/'raw/sec/company-filings'/f.ticker).resolve();path=(base/f.accession_number.replace('-','')/(f.primary_document or '')).resolve()
   body=bool(f.primary_document and path.is_relative_to(base) and path.is_file() and path.stat().st_size>=5000)
   state=classify(f.form,f.report_date,body,counts.get(f.accession_number,0),f.accession_number in published,f.accession_number in drafts)
   old=db.execute('SELECT state,detail FROM filings WHERE accession=?',(f.accession_number,)).fetchone()
   if old and old['state'] in ('running','content_review_pending','draft_repair_required','failed','interrupted','download_failed','preflight_blocked') and state!='published_reviewed':
    state=old['state']
    if state=='content_review_pending' and old['detail']:
     if any(c.get('state')=='needs_assistant_repair' for c in json.loads(old['detail']).get('chapters',[])):state='draft_repair_required'
   db.execute('INSERT INTO filings VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(accession) DO UPDATE SET fact_count=excluded.fact_count,body_present=excluded.body_present,state=excluded.state,updated_at=excluded.updated_at',(f.accession_number,f.ticker,f.form,str(f.filed_at),str(f.report_date) if f.report_date else None,f.source_url,f.primary_document,counts.get(f.accession_number,0),int(body),state,None,now()))
  universe={'knownIssuers':len(companies),'target':'all_us_equity_history','complete':False,'directoryRows':len(directory['rows']) if directory else None,'directoryIssuers':len({str(r['cik']) for r in directory['rows']}) if directory else None,'directoryObservedAt':directory['retrievedAt'] if directory else None,'historicalDelistedCoverage':'not_established','nonCompanyShareClasses':'classification_pending'}
  if directory:
   known={str(int(c.cik)) for c in companies};universe['directoryIssuersNotIndexed']=len({str(int(r['cik'])) for r in directory['rows']}-known)
  write_json(root/'universe.json',universe)
 return snapshot(root)

def snapshot(root):
 with connect(root) as db:
  counts=dict(db.execute('SELECT state,count(*) FROM filings GROUP BY state').fetchall())
  rows=db.execute('SELECT ticker,form,filed_at,period_end,state FROM filings ORDER BY filed_at,ticker').fetchall()
  groups={}
  for r in rows:
   c=groups.setdefault(r['ticker'],{'ticker':r['ticker'],'firstIndexed':r['filed_at'],'lastIndexed':r['filed_at'],'periods':0,'states':{}});c['lastIndexed']=r['filed_at'];c['periods']+=1;c['states'][r['state']]=c['states'].get(r['state'],0)+1
 universe=json.loads((root/'universe.json').read_text(encoding='utf-8')) if (root/'universe.json').exists() else {}
 heartbeat=json.loads((root/'heartbeat.json').read_text(encoding='utf-8')) if (root/'heartbeat.json').exists() else {'state':'not_started'}
 # Publish telemetry, never model text, stack traces, local paths or error payloads.
 heartbeat={k:v for k,v in heartbeat.items() if k in ('state','ticker','asOf','checkedAt','elapsedSeconds','progress','published')}
 heartbeat['progress']={k:v for k,v in heartbeat.get('progress',{}).items() if k in ('stage','chapter','totalChapters','generatedCharacters','elapsedSeconds','checkedAt')}
 return {'schema':'us-history-coverage/v1','observedAt':now(),'live':False,'universe':universe,'counts':counts,'indexedFilings':len(rows),'firstIndexed':rows[0]['filed_at'] if rows else None,'lastIndexed':rows[-1]['filed_at'] if rows else None,'companies':list(groups.values()),'workerObservation':heartbeat,'pauseRequested':(root/'pause').exists(),'policy':'quarterly_annual_originals_first; amendments and foreign formats need adapters; drafts are not reports'}

def fetch_missing(root,limit):
 settings=get_settings();ua=settings.sec_user_agent+(' '+settings.sec_contact_email.get_secret_value() if settings.sec_contact_email else '')
 with connect(root) as db,get_session_factory()() as s,httpx.Client(headers={'User-Agent':ua},timeout=45,follow_redirects=False) as client:
  # Structured legacy gaps stay visible; first fetch the earliest dated filings
  # which already have a usable same-accession financial packet.
  rows=db.execute("SELECT * FROM filings WHERE state='body_missing' AND fact_count>=10 AND form IN ('10-Q','10-K') ORDER BY filed_at,ticker LIMIT ?",(limit,)).fetchall()
  for r in rows:
   if (root/'pause').exists():break
   if shutil.disk_usage(settings.cold_data_root).free<20*1024**3:raise RuntimeError('Cold disk reserve reached')
   from app.quarter_peer_study import filing_packet
   f=s.get(CompanyFiling,r['accession'])
   try:
    filing_packet(f,settings,client,True)
    db.execute("UPDATE filings SET state='ready_preflight',body_present=1,detail=NULL,updated_at=? WHERE accession=?",(now(),r['accession']))
    print(json.dumps({'ticker':r['ticker'],'asOf':r['filed_at'],'state':'body_downloaded'}),flush=True)
   except (httpx.HTTPError,ValueError,OSError) as e:
    db.execute("UPDATE filings SET state='download_failed',detail=?,updated_at=? WHERE accession=?",(type(e).__name__,now(),r['accession']))
   db.commit()

def run(root,limit):
 settings=get_settings()
 with get_session_factory()().get_bind().connect() as lock:
  if not lock.scalar(text('SELECT pg_try_advisory_lock(624730015811)')):raise RuntimeError('A history supervisor is already running')
  try:
   with connect(root) as db:db.execute("UPDATE filings SET state='interrupted',detail='Review checkpoints before explicit resumption' WHERE state='running'")
   for _ in range(limit):
    if (root/'pause').exists():break
    reason=resource_gate()
    if reason:write_json(root/'heartbeat.json',{'state':'resource_blocked','reason':reason,'checkedAt':now()});break
    with connect(root) as db:r=db.execute("SELECT * FROM filings WHERE state='ready_preflight' ORDER BY filed_at,ticker LIMIT 1").fetchone()
    if not r:break
    try:
     with get_session_factory()() as s:
      packet=enrich_inline(enrich_market(s,build_packet(s,ticker=r['ticker'],cold_root=settings.cold_data_root,accession=r['accession'])),settings.cold_data_root)
     packet['financial_ledger']=build_ledger(packet)
     if not packet['financial_ledger']['comparisons']:
      with connect(root) as db:db.execute("UPDATE filings SET state='preflight_blocked',detail='No comparable original financial facts',updated_at=? WHERE accession=?",(now(),r['accession']))
      continue
     wrapper={'version':VERSION,'packet':packet};wrapper['fingerprint']=hashlib.sha256(json.dumps(wrapper,sort_keys=True).encode()).hexdigest()
     source=root/'inputs'/r['ticker']/r['accession']/'source.json'
     if source.exists() and json.loads(source.read_text(encoding='utf-8'))!=wrapper:raise ValueError('Frozen evidence changed; manual revision required')
     if not source.exists():write_json(source,wrapper)
     with connect(root) as db:db.execute("UPDATE filings SET state='running',updated_at=? WHERE accession=?",(now(),r['accession']))
     with (root/(r['accession']+'.log')).open('a',encoding='utf-8') as log:
      child=subprocess.Popen([sys.executable,'-m','app.complete_frozen_chapters','--source',str(source),'--output',str(root/'reports')],stdout=log,stderr=log,env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]),'PYTHONIOENCODING':'utf-8'})
      start=time.monotonic()
      while child.poll() is None:
       progress=root/'chapter-progress.json';detail=json.loads(progress.read_text(encoding='utf-8')) if progress.exists() else {}
       if detail.get('ticker')!=r['ticker'] or detail.get('asOf')!=r['filed_at'][:10]:detail={'stage':'initializing_current_report'}
       write_json(root/'heartbeat.json',{'state':'running','ticker':r['ticker'],'asOf':r['filed_at'],'checkedAt':now(),'elapsedSeconds':round(time.monotonic()-start),'progress':detail,'published':False})
       if time.monotonic()-start>36000:child.terminate();child.wait(timeout=30);raise RuntimeError('Report deadline exceeded; partial drafts retained')
       time.sleep(5)
     detail=json.loads((root/'chapter-progress.json').read_text(encoding='utf-8'))
     state='content_review_pending' if child.returncode==0 and detail.get('stage')=='awaiting_assistant_content_review' else 'interrupted' if detail.get('stage')=='safely_paused' else 'failed'
     if state=='content_review_pending' and any(c.get('state')=='needs_assistant_repair' for c in detail.get('chapters',[])):state='draft_repair_required'
     with connect(root) as db:db.execute('UPDATE filings SET state=?,detail=?,updated_at=? WHERE accession=?',(state,json.dumps(detail,ensure_ascii=False),now(),r['accession']))
     if state!='content_review_pending':break
    except (ValueError,RuntimeError,OSError) as e:
     with connect(root) as db:db.execute("UPDATE filings SET state='failed',detail=?,updated_at=? WHERE accession=?",(str(e)[:500],now(),r['accession']))
     break
   previous=json.loads((root/'heartbeat.json').read_text(encoding='utf-8')) if (root/'heartbeat.json').exists() else {}
   if previous.get('state')!='resource_blocked':write_json(root/'heartbeat.json',{**previous,'state':'paused' if (root/'pause').exists() else 'stopped','checkedAt':now(),'reason':'bounded_batch_finished_or_review_gate'})
  finally:lock.execute(text('SELECT pg_advisory_unlock(624730015811)'))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['plan','fetch','run','status','pause']);p.add_argument('--root',type=Path,required=True);p.add_argument('--site',type=Path,default=Path('pilot-site'));p.add_argument('--limit',type=int,default=1);p.add_argument('--directory',action='store_true');p.add_argument('--export',type=Path);a=p.parse_args()
 if a.action=='plan':result=plan(a.root,a.site,a.directory)
 elif a.action=='fetch':fetch_missing(a.root,max(1,min(a.limit,50)));result=snapshot(a.root)
 elif a.action=='run':run(a.root,max(1,min(a.limit,10)));result=snapshot(a.root)
 elif a.action=='pause':a.root.mkdir(parents=True,exist_ok=True);(a.root/'pause').touch();result=snapshot(a.root)
 else:result=snapshot(a.root)
 if a.export:write_json(a.export,result)
 print(json.dumps({k:result[k] for k in ['observedAt','universe','counts','indexedFilings','firstIndexed','lastIndexed']},ensure_ascii=False),flush=True)
