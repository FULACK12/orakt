"""Bounded, serial SEC bulk archive staging on cold storage; never imports silently."""
import argparse,hashlib,json,shutil,time
from datetime import datetime,UTC
from pathlib import Path
import httpx
from app.core.config import get_settings
from app.company_history_dossier import write_json

URLS={
 'submissions.zip':'https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip',
 'companyfacts.zip':'https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip',
}
def run(root):
 settings=get_settings();root.mkdir(parents=True,exist_ok=True)
 ua=settings.sec_user_agent+(' '+settings.sec_contact_email.get_secret_value() if settings.sec_contact_email else '')
 def status(**v):write_json(root/'progress.json',{'observedAt':datetime.now(UTC).isoformat(),'imported':False,**v})
 with httpx.Client(headers={'User-Agent':ua},timeout=httpx.Timeout(120,connect=30),follow_redirects=False) as client:
  for name,url in URLS.items():
   target=root/name;partial=root/(name+'.partial');manifest=root/(name+'.manifest.json')
   if target.exists() and manifest.exists():continue
   if target.exists() or partial.exists():raise ValueError('Existing incomplete artifact retained; inspect it before retrying')
   if shutil.disk_usage(root).free<30*1024**3:raise ValueError('Cold disk reserve insufficient')
   written=0;digest=hashlib.sha256();started=time.monotonic();last=0
   try:
    with client.stream('GET',url) as response:
     response.raise_for_status();length=int(response.headers.get('Content-Length','0')) or None
     if length and length>8*1024**3:raise ValueError('Archive exceeds per-file safety cap')
     with partial.open('xb') as out:
      for block in response.iter_bytes(1024*1024):
       if (root/'pause').exists():raise InterruptedError('Pause requested; partial archive retained')
       written+=len(block)
       if written>8*1024**3 or time.monotonic()-started>1800:raise ValueError('Size or runtime cap exceeded; partial retained')
       out.write(block);digest.update(block)
       if time.monotonic()-last>5:
        status(state='downloading',file=name,bytesReceived=written,contentLength=length,elapsedSeconds=round(time.monotonic()-started));last=time.monotonic()
     if length and written!=length:raise ValueError('Incomplete Content-Length')
     with partial.open('rb') as f:
      if f.read(4)!=b'PK\x03\x04':raise ValueError('Not a ZIP archive')
     partial.rename(target)
     write_json(manifest,{'sourceUrl':url,'retrievedAt':datetime.now(UTC).isoformat(),'bytes':written,'sha256':digest.hexdigest(),'extracted':False,'imported':False})
     status(state='archived',file=name,bytesReceived=written,sha256=digest.hexdigest())
   except Exception as exc:
    status(state='paused' if isinstance(exc,InterruptedError) else 'failed',file=name,bytesReceived=written,errorType=type(exc).__name__);raise
 status(state='bulk_archives_retained_not_imported',files=list(URLS))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();run(a.root)
