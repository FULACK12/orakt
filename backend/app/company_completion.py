"""Resumable originals-first completion, with separate ingestion and model queues.

Source coverage never implies report approval. No paid models or auto-publication.
Each invocation targets a fixed date. Pause files are cooperative and retained.
"""
import argparse, asyncio, hashlib, json, re, shutil, sqlite3, time, zipfile
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlsplit, unquote
import httpx
from sqlalchemy import select, text
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.db.models import CompanyProfile, CompanyFiling, CompanyFinancialFact
from app.company_history_dossier import write_json
from app.sec_bulk_import import insert_absent, partition_variants
from app.companies import _submission_rows, _submission_rows_from_columns, _historical_submission_files, _company_fact_rows

REPORT_FORMS=('10-K','10-Q','10-K/A','10-Q/A','20-F','20-F/A','40-F','40-F/A')
SOURCE_FORMS=REPORT_FORMS+('8-K','8-K/A','6-K','6-K/A','DEF 14A','DEFA14A')

def now():return datetime.now(UTC).isoformat()

def connect(root):
 root.mkdir(parents=True,exist_ok=True)
 db=sqlite3.connect(root/'completion.sqlite3',timeout=60);db.row_factory=sqlite3.Row
 db.execute('PRAGMA journal_mode=WAL')
 db.execute('CREATE TABLE IF NOT EXISTS jobs(kind TEXT,key TEXT,ticker TEXT,state TEXT,detail TEXT,updated_at TEXT,PRIMARY KEY(kind,key))')
 return db

def mark(db,kind,key,ticker,state,detail=None,commit=True):
 db.execute('INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?,?)',(kind,key,ticker,state,json.dumps(detail or {},ensure_ascii=False),now()))
 if commit:db.commit()

def done(db,kind,key):
 r=db.execute('SELECT state FROM jobs WHERE kind=? AND key=?',(kind,key)).fetchone()
 return bool(r and r['state']=='complete')

def check_pause(root,kind):
 if (root/'pause').exists() or (root/f'pause-{kind}').exists():raise InterruptedError('cooperative_pause_requested')
 if shutil.disk_usage(get_settings().cold_data_root).free<30*1024**3:raise InterruptedError('cold_disk_reserve_below_30_GiB')
 hot=get_settings().hot_data_root
 if hot.exists() and shutil.disk_usage(hot).free<50*1024**3:raise InterruptedError('hot_disk_reserve_below_50_GiB')

def heartbeat(root,kind,state,**values):
 write_json(root/f'{kind}-progress.json',{'checkedAt':now(),'state':state,'published':False,**values})

def ua():
 s=get_settings();return s.sec_user_agent+(' '+s.sec_contact_email.get_secret_value() if s.sec_contact_email else '')

def profile_candidate(payload):
 """Do not silently classify funds, warrants or historical tickers as companies."""
 if payload.get('entityType')!='operating':return None
 forms=payload.get('filings',{}).get('recent',{}).get('form',[])
 if not set(forms).intersection(REPORT_FORMS):return None
 symbols=payload.get('tickers') or [];exchanges=payload.get('exchanges') or []
 ticker=next((t for t,e in zip(symbols,exchanges) if e in ('Nasdaq','NYSE','NYSE American','Cboe') and re.fullmatch(r'[A-Z][A-Z0-9.-]{0,15}',t)),None)
 if not ticker:return None
 cik=str(payload.get('cik','')).zfill(10)
 if not re.fullmatch(r'\d{10}',cik):return None
 return {'ticker':ticker,'cik':cik,'name':str(payload['name'])[:255],'sector':'Unclassified (SEC)','industry':str(payload.get('sicDescription') or 'Unclassified')[:255],'source_url':f'https://www.sec.gov/edgar/browse/?CIK={int(cik)}'}

def discover_us(root,cutoff):
 """Expand current operating issuers from the already archived official bulk."""
 from app.sec_bulk_import import read_member, run as import_bulk
 cold=get_settings().cold_data_root
 bulk=cold/'raw/sec/bulk'/str(cutoff)
 directory=cold/'orakt/us-history-v83/sec-directory.json'
 records=json.loads(directory.read_text(encoding='utf-8'))['rows']
 ciks=sorted({str(int(r['cik'])).zfill(10) for r in records})
 manifest=json.loads((bulk/'submissions.zip.manifest.json').read_text(encoding='utf-8'))
 with (bulk/'submissions.zip').open('rb') as handle:
  if hashlib.file_digest(handle,'sha256').hexdigest()!=manifest['sha256']:raise ValueError('Bulk archive hash mismatch')
 with connect(root) as db,get_session_factory()() as s,zipfile.ZipFile(bulk/'submissions.zip') as z:
  existing_ciks=set(s.scalars(select(CompanyProfile.cik)));existing_tickers=set(s.scalars(select(CompanyProfile.ticker)))
  for i,cik in enumerate(ciks):
   check_pause(root,'us-universe')
   if done(db,'us-universe',cik):continue
   try:
    candidate=profile_candidate(read_member(z,f'CIK{cik}.json'))
    if cik in existing_ciks:result='existing'
    elif not candidate:result='classification_or_non_operating_excluded'
    elif candidate['ticker'] in existing_tickers:result='ticker_collision_needs_review'
    else:
     s.add(CompanyProfile(**candidate));s.commit();existing_ciks.add(cik);existing_tickers.add(candidate['ticker']);result='operating_issuer_registered'
    mark(db,'us-universe',cik,candidate['ticker'] if candidate else '', 'complete',{'classification':result,'allShareClassesResolved':False})
   except (KeyError,ValueError,OSError):
    s.rollback();mark(db,'us-universe',cik,'','failed',{'reason':'missing_or_invalid_bulk_member'})
   if i%25==0:heartbeat(root,'us-universe','classifying',scanned=i+1,directoryIssuers=len(ciks),registeredIssuers=len(existing_ciks))
  heartbeat(root,'us-universe','importing',registeredIssuers=len(existing_ciks),note='Cold raw archives already retained; importing missing filings and period variants')
 # Small restart-safe batches: only absent facts enter the legacy store.
 while True:
  check_pause(root,'us-universe')
  import_bulk(bulk,100)
  summary=json.loads((bulk/'import-progress.json').read_text(encoding='utf-8'))
  heartbeat(root,'us-universe','importing',completedIssuers=summary.get('completedIssuers'),sourceGapIssuers=summary.get('sourceGapIssuers',0),retainedCoreObservations=summary.get('retainedCoreObservations'))
  if summary.get('state') in {'known_universe_import_complete','known_universe_processed_with_source_gaps'} or not summary.get('companies'):break
  if any(c['state']=='failed' for c in summary['companies']):raise InterruptedError('bulk_import_errors_require_review')
 heartbeat(root,'us-universe','pass_finished',sourceGapIssuers=summary.get('sourceGapIssuers',0),note='Current operating issuers processed, not complete source coverage; source/share-class/delisted gaps explicitly retained')

def archive_json(client,url,path):
 if path.exists():return json.loads(path.read_text(encoding='utf-8'))
 r=client.get(url);r.raise_for_status();p=r.json()
 if not isinstance(p,dict):raise ValueError('Expected JSON object')
 write_json(path,p)
 write_json(path.with_suffix('.manifest.json'),{'sourceUrl':url,'retrievedAt':now(),'responseSha256':hashlib.sha256(r.content).hexdigest(),'storedSha256':hashlib.sha256(path.read_bytes()).hexdigest()})
 time.sleep(1)
 return p

def refresh_us(root,cutoff):
 """Preserve raw updates and all period variants; insert absent legacy rows only."""
 cold=get_settings().cold_data_root/'raw/sec/live'/root.name
 cold.mkdir(parents=True,exist_ok=True)
 with sqlite3.connect(cold/'import-ledger.sqlite3',timeout=60) as ledger,connect(root) as db,get_session_factory()() as s,httpx.Client(headers={'User-Agent':ua()},timeout=120,follow_redirects=False) as client:
  ledger.execute('CREATE TABLE IF NOT EXISTS issuers(cik TEXT PRIMARY KEY,ticker TEXT,state TEXT,result TEXT)')
  ledger.execute('CREATE TABLE IF NOT EXISTS observations(hash TEXT PRIMARY KEY,ticker TEXT,period_start TEXT,period_end TEXT,filed_at TEXT,source_archive TEXT,payload TEXT)')
  ledger.execute('CREATE INDEX IF NOT EXISTS observations_ticker_date ON observations(ticker,filed_at)')
  profiles=list(s.scalars(select(CompanyProfile).order_by(CompanyProfile.ticker)))
  for i,p in enumerate(profiles):
   check_pause(root,'us-refresh')
   if done(db,'us-refresh',p.cik):continue
   heartbeat(root,'us-refresh','running',ticker=p.ticker,company=i+1,totalCompanies=len(profiles),cutoff=str(cutoff))
   try:
    base=cold/p.cik
    sub=archive_json(client,f'https://data.sec.gov/submissions/CIK{p.cik}.json',base/'submissions.json')
    filings=_submission_rows(p,sub)
    for name in _historical_submission_files(sub):
     check_pause(root,'us-refresh')
     if not re.fullmatch(r'CIK\d+-submissions-\d+\.json',name):raise ValueError('Invalid SEC historical filename')
     filings.extend(_submission_rows_from_columns(p,archive_json(client,'https://data.sec.gov/submissions/'+name,base/name)))
    fact_path=base/'companyfacts.json'
    payload=archive_json(client,f'https://data.sec.gov/api/xbrl/companyfacts/CIK{p.cik}.json',fact_path)
    observations=[r for r in _company_fact_rows(p,payload,retain_period_variants=True) if r['filed_at']<=cutoff]
    digest=hashlib.sha256(fact_path.read_bytes()).hexdigest()
    for row in observations:
     raw=json.dumps(row,sort_keys=True,default=str);h=hashlib.sha256(raw.encode()).hexdigest()
     ledger.execute('INSERT OR IGNORE INTO observations VALUES(?,?,?,?,?,?,?)',(h,p.ticker,str(row['period_start'] or ''),str(row['period_end']),str(row['filed_at']),digest,raw))
    safe,ambiguous=partition_variants(observations)
    result={'newFilings':insert_absent(s,CompanyFiling,list({r['accession_number']:r for r in filings if r['filed_at']<=cutoff}.values())),'newFacts':insert_absent(s,CompanyFinancialFact,safe),'retainedPeriodVariants':len(observations),'ambiguousVariantsNotFlattened':ambiguous}
    s.commit();ledger.execute('INSERT OR REPLACE INTO issuers VALUES(?,?,?,?)',(p.cik,p.ticker,'complete',json.dumps(result)));ledger.commit()
    mark(db,'us-refresh',p.cik,p.ticker,'complete',result)
   except (httpx.HTTPError,ValueError,KeyError,OSError) as e:
    s.rollback();mark(db,'us-refresh',p.cik,p.ticker,'failed',{'errorType':type(e).__name__})
    if isinstance(e,httpx.HTTPStatusError) and e.response.status_code in (403,429):raise InterruptedError('source_access_backoff')
   print(json.dumps({'kind':'us-refresh','ticker':p.ticker,'checkedAt':now()}),flush=True)
  heartbeat(root,'us-refresh','pass_finished',cutoff=str(cutoff),note='Per-company errors remain in ledger; not a completeness assertion')

def filing_target(f,cold):
 base=(cold/'raw/sec/company-filings'/f.ticker).resolve();target=(base/f.accession_number.replace('-','')/unquote(f.primary_document or '')).resolve();u=urlsplit(f.source_url)
 if not f.primary_document or not target.is_relative_to(base) or u.scheme!='https' or u.netloc!='www.sec.gov' or not u.path.startswith('/Archives/edgar/data/'):raise ValueError('Invalid SEC archive target')
 return target

def download_body(client,f,cold):
 path=filing_target(f,cold)
 if path.is_file() and path.stat().st_size>=500:return 'existing'
 if path.exists():raise ValueError('Short existing document retained for inspection')
 part=path.with_suffix(path.suffix+'.partial')
 if part.exists():raise ValueError('Interrupted partial retained; explicit retry required')
 path.parent.mkdir(parents=True,exist_ok=True);size=0;digest=hashlib.sha256();prefix=b''
 with client.stream('GET',f.source_url) as r:
  r.raise_for_status()
  with part.open('xb') as out:
   for block in r.iter_bytes(1024*1024):
    size+=len(block)
    if size>80*1024**2:raise ValueError('Document exceeds 80 MiB safety cap')
    if len(prefix)<4096:prefix=(prefix+block)[:4096]
    digest.update(block);out.write(block)
 if size<500 or any(x in prefix.lower() for x in [b'undeclared automated tool',b'request rate threshold exceeded',b'access denied']):raise ValueError('Not usable original filing')
 part.rename(path)
 write_json(path.with_suffix(path.suffix+'.manifest.json'),{'sourceUrl':f.source_url,'retrievedAt':now(),'filedAt':str(f.filed_at),'form':f.form,'bytes':size,'sha256':digest.hexdigest(),'exhibitsComplete':False})
 return 'downloaded'

def collect_us_bodies(root,cutoff):
 with connect(root) as db,get_session_factory()() as s,httpx.Client(headers={'User-Agent':ua()},timeout=90,follow_redirects=False) as client:
  rows=s.scalars(select(CompanyFiling).where(CompanyFiling.form.in_(SOURCE_FORMS),CompanyFiling.filed_at<=cutoff).order_by(CompanyFiling.filed_at.desc(),CompanyFiling.ticker)).all()
  for i,f in enumerate(rows):
   check_pause(root,'us-bodies')
   if done(db,'us-bodies',f.accession_number):continue
   heartbeat(root,'us-bodies','running',ticker=f.ticker,accession=f.accession_number,form=f.form,filedAt=str(f.filed_at),scanned=i+1,totalIndexed=len(rows),cutoff=str(cutoff))
   try:mark(db,'us-bodies',f.accession_number,f.ticker,'complete',{'result':download_body(client,f,get_settings().cold_data_root),'form':f.form,'filedAt':str(f.filed_at)})
   except (httpx.HTTPError,ValueError,OSError) as e:
    mark(db,'us-bodies',f.accession_number,f.ticker,'failed',{'errorType':type(e).__name__})
    if isinstance(e,httpx.HTTPStatusError) and e.response.status_code in (403,429):raise InterruptedError('source_access_backoff')
   time.sleep(1)
  heartbeat(root,'us-bodies','pass_finished',cutoff=str(cutoff),note='Includes primary documents only; exhibits and failed downloads remain gaps')

async def collect_cn(root,cutoff):
 from app.a_share_disclosures import CNINFO_BASE_URL,_active_a_share_leaders,_get_or_create_source,_resolve_org_id,_announcement,_retain_announcement
 from app.storage.archive import ColdArchive
 settings=get_settings();archive=ColdArchive(settings.cold_data_root,min_free_bytes=30*1024**3,max_used_percent=95)
 with connect(root) as db,get_session_factory()() as s:
  leaders=_active_a_share_leaders(s,set());source=_get_or_create_source(s);s.commit();orgs={}
  async with httpx.AsyncClient(base_url=CNINFO_BASE_URL,timeout=120,follow_redirects=True,headers={'User-Agent':'ORAKT/1.0 personal research','Referer':CNINFO_BASE_URL+'/new/index'}) as client:
   for year in range(cutoff.year,1989,-1):
    for leader in leaders:
     key=f'{leader.ticker}:{year}';check_pause(root,'cn-history')
     if done(db,'cn-history',key):continue
     heartbeat(root,'cn-history','running',ticker=leader.ticker,year=year,totalCompanies=len(leaders),cutoff=str(cutoff))
     try:
      if leader.ticker not in orgs:orgs[leader.ticker]=await _resolve_org_id(client,leader.ticker)
      seen=0;created=0;page=1;errors=0
      while True:
       check_pause(root,'cn-history')
       if page>1000:raise ValueError('Pagination safety cap; window is incomplete')
       sh=leader.ticker.startswith('6')
       r=await client.post('/new/hisAnnouncement/query',data={'pageNum':str(page),'pageSize':'30','column':'sse' if sh else 'szse','tabName':'fulltext','plate':'sh' if sh else 'sz','stock':f'{leader.ticker},{orgs[leader.ticker]}','searchkey':'','secid':'','category':'','trade':'','seDate':f'{year}-01-01~{min(cutoff,date(year,12,31))}','sortName':'','sortType':'','isHLtitle':'true'})
       r.raise_for_status();p=r.json()
       items,more=validate_cn_page(p)
       write_json(root/'cn-index'/leader.ticker/f'{year}-{page:04d}.json',{'retrievedAt':now(),'sourceUrl':CNINFO_BASE_URL+'/new/hisAnnouncement/query','year':year,'page':page,'payload':p})
       for raw in items:
        check_pause(root,'cn-history');ann=_announcement(raw)
        if ann is None:errors+=1;continue
        if ann.ticker!=leader.ticker or ann.published_at.date()>cutoff:errors+=1;continue
        seen+=1
        try:
         outcome,_=await _retain_announcement(s,client=client,archive=archive,source=source,announcement=ann);s.commit();created+=int(outcome=='created')
        except (httpx.HTTPError,ValueError,OSError) as e:
         s.rollback();errors+=1
         mark(db,'cn-document',ann.announcement_id,leader.ticker,'failed',{'errorType':type(e).__name__})
         if isinstance(e,httpx.HTTPStatusError) and e.response.status_code in (403,429):raise InterruptedError('source_access_backoff')
        await asyncio.sleep(1)
       heartbeat(root,'cn-history','running',ticker=leader.ticker,year=year,page=page,documentsSeen=seen,newDocuments=created,failedDocuments=errors)
       if not more:break
       page+=1;await asyncio.sleep(1)
      mark(db,'cn-history',key,leader.ticker,'complete' if not errors else 'partial',{'year':year,'seen':seen,'created':created,'errors':errors,'pages':page,'coverage':'provider_returned_documents_only'})
     except (httpx.HTTPError,ValueError,TypeError,KeyError,OSError) as e:
      s.rollback();mark(db,'cn-history',key,leader.ticker,'failed',{'errorType':type(e).__name__})
      if isinstance(e,httpx.HTTPStatusError) and e.response.status_code in (403,429):raise InterruptedError('source_access_backoff')
     await asyncio.sleep(1)
  heartbeat(root,'cn-history','pass_finished',cutoff=str(cutoff),note='Empty historical windows are not proof of pre-listing coverage')

def validate_cn_page(p):
 if not isinstance(p,dict) or 'hasMore' not in p or 'announcements' not in p:raise ValueError('Unverified CNINFO page schema')
 items=p['announcements'] or []
 if not isinstance(items,list) or not isinstance(p['hasMore'],bool):raise ValueError('Invalid pagination metadata')
 if p['hasMore'] and not items:raise ValueError('Empty continuing page')
 return items,p['hasMore']

def collect_reports(root,cutoff,limit):
 from app.company_history_dossier import run as generate
 from app.historical_earnings_report import build_packet
 from app.orakt_history_queue import resource_gate
 with connect(root) as db,get_session_factory()() as s:
  # Existing published reports are not regenerated. One candidate per company
  # enters the pilot before another period of that company is considered.
  published=set()
  site=Path(__file__).resolve().parents[2]/'pilot-site/private-data/company-dossiers'
  for p in site.glob('*.json'):
   d=json.loads(p.read_text(encoding='utf-8'))
   if d.get('review',{}).get('state')=='assistant_reviewed':published.update(x['id'].removeprefix('SEC:') for x in d.get('sources',[]))
  rows=s.scalars(select(CompanyFiling).where(CompanyFiling.form.in_(('10-Q','10-K')),CompanyFiling.filed_at<=cutoff,CompanyFiling.report_date.is_not(None)).order_by(CompanyFiling.filed_at,CompanyFiling.ticker,CompanyFiling.accession_number)).all()
  heartbeat(root,'reports','planning',totalIndexed=len(rows),cutoff=str(cutoff))
  for index,f in enumerate(rows):
   prior=db.execute("SELECT state FROM jobs WHERE kind='reports' AND key=?",(f.accession_number,)).fetchone()
   if f.accession_number in published:
    if not prior:mark(db,'reports',f.accession_number,f.ticker,'published_reviewed',commit=False)
   elif prior is None or prior['state']=='waiting_source':
    ready=bool(f.primary_document and filing_target(f,get_settings().cold_data_root).is_file())
    mark(db,'reports',f.accession_number,f.ticker,'queued' if ready else 'waiting_source',{'filedAt':str(f.filed_at),'periodEnd':str(f.report_date)},commit=False)
   if index%100==0:
    db.commit();check_pause(root,'reports');heartbeat(root,'reports','planning',scanned=index+1,totalIndexed=len(rows),cutoff=str(cutoff))
  db.commit()
  pending=db.execute("SELECT count(*) FROM jobs WHERE kind='reports' AND state IN ('content_review_pending','assembled_review_pending')").fetchone()[0]
  if pending>=4:
   heartbeat(root,'reports','review_gate',pendingReview=pending,note='Review existing drafts before additional inference');return
  used=set();attempts=0;failures=0
  for f in rows:
   if f.ticker in used or f.accession_number in published:continue
   prior=db.execute("SELECT state FROM jobs WHERE kind='reports' AND key=?",(f.accession_number,)).fetchone()
   if not prior or prior['state']!='queued':continue # no silent retry of failed/interrupted drafts
   try:build_packet(s,ticker=f.ticker,cold_root=get_settings().cold_data_root,accession=f.accession_number)
   except ValueError:
    mark(db,'reports',f.accession_number,f.ticker,'waiting_facts',{'published':False});continue
   check_pause(root,'reports');reason=resource_gate()
   if reason:raise InterruptedError(reason)
   if attempts>=limit:break
   used.add(f.ticker);attempts+=1
   mark(db,'reports',f.accession_number,f.ticker,'running')
   heartbeat(root,'reports','running',ticker=f.ticker,accession=f.accession_number,attempted=attempts,cutoff=str(cutoff))
   try:
    generate(f.ticker,f.accession_number,root/'reports')
    mark(db,'reports',f.accession_number,f.ticker,'content_review_pending',{'published':False,'humanAccepted':False})
   except (ValueError,RuntimeError,httpx.HTTPError,OSError) as e:
    mark(db,'reports',f.accession_number,f.ticker,'repair_required',{'errorType':type(e).__name__,'published':False});failures+=1
   if failures>=2:break
  heartbeat(root,'reports','review_gate',attempted=attempts,failed=failures,note='No auto-publication; content review required before scaling')

def status(root):
 with connect(root) as db:counts=[dict(r) for r in db.execute('SELECT kind,state,count(*) count FROM jobs GROUP BY kind,state')]
 progress={p.name:json.loads(p.read_text(encoding='utf-8')) for p in root.glob('*-progress.json')}
 if (root/'chapter-progress.json').exists():progress['chapter-progress.json']=json.loads((root/'chapter-progress.json').read_text(encoding='utf-8'))
 return {'observedAt':now(),'counts':counts,'workers':progress,'complete':False,'scope':'all catalogued US and A-share companies; SEC bulk universe retained separately; delisted/global completeness not established'}

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['us-universe','us-refresh','us-bodies','cn-history','reports','status','pause']);p.add_argument('--root',type=Path,required=True);p.add_argument('--cutoff',type=date.fromisoformat,default=date.today());p.add_argument('--limit',type=int,default=4);a=p.parse_args()
 if a.cutoff>date.today():p.error('Future cutoff not allowed')
 a.root.mkdir(parents=True,exist_ok=True)
 if a.action=='pause':(a.root/'pause').touch();return
 if a.action=='status':print(json.dumps(status(a.root),ensure_ascii=False));return
 key={'us-universe':624730015824,'us-refresh':624730015821,'us-bodies':624730015822,'cn-history':624730015823,'reports':624730015811}[a.action]
 with get_session_factory()().get_bind().connect() as lock:
  if not lock.scalar(text('SELECT pg_try_advisory_lock(:k)'),{'k':key}):raise RuntimeError('Worker already running')
  try:
   if a.action=='us-universe':discover_us(a.root,a.cutoff)
   elif a.action=='us-refresh':refresh_us(a.root,a.cutoff)
   elif a.action=='us-bodies':collect_us_bodies(a.root,a.cutoff)
   elif a.action=='cn-history':asyncio.run(collect_cn(a.root,a.cutoff))
   else:collect_reports(a.root,a.cutoff,max(1,min(a.limit,10)))
  except InterruptedError as e:heartbeat(a.root,a.action,'paused',reason=str(e))
  except Exception as e:
   heartbeat(a.root,a.action,'failed',errorType=type(e).__name__);raise
  finally:lock.execute(text('SELECT pg_advisory_unlock(:k)'),{'k':key})

if __name__=='__main__':main()
