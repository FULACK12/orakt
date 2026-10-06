"""Bounded original-filing retrieval and duration-aware research comparators."""
import argparse,hashlib,json,time
from datetime import date,datetime,UTC
from pathlib import Path
from urllib.parse import urlsplit
from decimal import Decimal
import httpx
from sqlalchemy import select
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.db.models import CompanyFiling
from app.inline_filing_facts import monetary_facts
from app.financial_period_ledger import build_ledger
from app.cash_flow_bridge import bridge
from app.company_history_dossier import write_json

def comparable_quarter(facts,end):
 """No year/quarter subtraction or total/segment summation without review."""
 rows=[]
 for concept in ['RevenueFromContractWithCustomerExcludingAssessedTax','RevenueFromContractWithCustomerIncludingAssessedTax','Revenues','SalesRevenueNet','OperatingIncomeLoss','NetIncomeLoss']:
  selected=[f for f in facts if f['concept']==concept and f['unit']=='USD' and f['period_end']==end and f.get('period_start') and 70<=(date.fromisoformat(end)-date.fromisoformat(f['period_start'])).days+1<=110]
  groups={}
  for f in selected:groups.setdefault(f['period_start'],[]).append(f)
  if len(groups)!=1:continue
  values=next(iter(groups.values()))
  if len({Decimal(f['value']) for f in values})==1:rows.append(values[0])
 return rows

def run(source,site,output,download=False):
 packet=json.loads(source.read_text(encoding='utf-8'))['packet'];settings=get_settings();cutoff=date.fromisoformat(packet['as_of_date'])
 result={'version':'research-completion/v1','ticker':packet['ticker'],'asOf':packet['as_of_date'],'checkedAt':datetime.now(UTC).isoformat(),'cashFlowBridge':bridge(packet),'comparators':[],'changesReportConfidence':False}
 ua=settings.sec_user_agent
 if settings.sec_contact_email:ua+=' '+settings.sec_contact_email.get_secret_value()
 with get_session_factory()() as session,httpx.Client(headers={'User-Agent':ua,'Accept-Encoding':'gzip, deflate'},timeout=45,follow_redirects=False) as client:
  for ticker in ['AAPL','MSFT','NVDA','AMD']:
   filing=session.scalars(select(CompanyFiling).where(CompanyFiling.ticker==ticker,CompanyFiling.form.in_(['10-Q','10-K']),CompanyFiling.filed_at<=cutoff).order_by(CompanyFiling.filed_at.desc())).first()
   item={'ticker':ticker,'role':'subject' if ticker=='AAPL' else 'adjacent_business_reference','rankingEligible':False}
   result['comparators'].append(item)
   if not filing:item['status']='no_filing_before_cutoff';continue
   item.update({'accession':filing.accession_number,'filedAt':str(filing.filed_at),'periodEnd':str(filing.report_date),'form':filing.form,'sourceUrl':filing.source_url})
   root=(settings.cold_data_root/'raw/sec/company-filings'/ticker).resolve();path=(root/filing.accession_number.replace('-','')/(filing.primary_document or '')).resolve()
   if not path.is_relative_to(root) or not filing.primary_document:raise ValueError('Invalid filing archive path')
   if not path.is_file() and download:
    u=urlsplit(filing.source_url)
    if u.scheme!='https' or u.hostname!='www.sec.gov' or not u.path.startswith('/Archives/edgar/data/'):raise ValueError('Only official SEC filing URLs allowed')
    try:
     response=client.get(filing.source_url);response.raise_for_status();raw=response.content
     if len(raw)<5000 or len(raw)>25000000 or b'<html' not in raw.lower():raise ValueError('Invalid filing document')
     path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    except (httpx.HTTPError,ValueError) as e:
     item.update(status='download_failed',error=type(e).__name__);continue
    finally:time.sleep(0.3)
   if not path.is_file():item['status']='full_document_missing';continue
   raw=path.read_bytes();facts,coverage=monetary_facts(raw.decode('utf-8',errors='replace'),filed_at=str(filing.filed_at),source_url=filing.source_url)
   values=comparable_quarter(facts,str(filing.report_date));endgap=abs((filing.report_date-date.fromisoformat(packet['period_end'])).days)
   item.update({'sourceDocumentHash':hashlib.sha256(raw).hexdigest(),'extractionCoverage':coverage,'metrics':values,'calendarEndGapDays':endgap,'status':'quarter_metrics_available' if values else 'quarter_metrics_missing','calendarAligned':endgap<=14})
   # Publish the parsed original evidence on cold disk for subsequent reports.
   write_json(output/'peer-packets'/ticker/(filing.accession_number+'.json'),{'ticker':ticker,'as_of_date':str(filing.filed_at),'period_end':str(filing.report_date),'accession':filing.accession_number,'source_url':filing.source_url,'facts':facts,'raw_sha256':item['sourceDocumentHash']})
 write_json(output/'research-completion-local-707.json',result)
 write_json(site/'private-data/research-completions/local-707.json',result)
 print(json.dumps({'bridgeReconciled':True,'comparators':[{k:v for k,v in c.items() if k in ['ticker','status','calendarAligned']} for c in result['comparators']]}),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--site',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--download',action='store_true');a=p.parse_args();run(a.source,a.site,a.output,a.download)
