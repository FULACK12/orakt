"""One reviewed MSFT quarter completion; preserves the prior published dataset."""
import argparse,json,hashlib
from pathlib import Path
from datetime import datetime,UTC
from sqlalchemy import select
from app.db.session import get_session_factory
from app.db.models import CompanyFiling
from app.core.config import get_settings
from app.inline_filing_facts import monetary_facts
from app.derived_fiscal_quarter import derive
from app.company_history_dossier import write_json

RELEASE='https://www.microsoft.com/en-us/Investor/earnings/FY-2025-Q4/press-release-webcast'
# Assistant checked the GAAP quarter column of the original investor release.
CHECKED={'RevenueFromContractWithCustomerExcludingAssessedTax':'76441000000','OperatingIncomeLoss':'34323000000','NetIncomeLoss':'27233000000'}

def run(site,output):
 data=json.loads((site/'private-data/research-completions/local-707.json').read_text(encoding='utf-8'));packets=[]
 with get_session_factory()() as s:
  for accession in ['0000950170-25-100235','0000950170-25-061046']:
   f=s.get(CompanyFiling,accession)
   root=(get_settings().cold_data_root/'raw/sec/company-filings/MSFT').resolve();path=(root/accession.replace('-','')/f.primary_document).resolve()
   if not path.is_relative_to(root):raise ValueError('Invalid source path')
   raw=path.read_bytes();facts,coverage=monetary_facts(raw.decode('utf-8'),filed_at=str(f.filed_at),source_url=f.source_url)
   packets.append({'facts':facts,'hash':hashlib.sha256(raw).hexdigest(),'filing':f})
  derived=[]
  for concept,expected in CHECKED.items():
   operands=[]
   for p in packets:
    matches=[v for v in p['facts'] if v['concept']==concept and v['period_start']=='2024-07-01' and v['period_end']==str(p['filing'].report_date) and v['unit']=='USD']
    if not matches or len({v['value'] for v in matches})!=1:raise ValueError('Missing/conflicting original values')
    operands.append({**matches[0],'issuer':'MSFT','accession':p['filing'].accession_number,'sourceDocumentHash':p['hash']})
   result=derive(*operands,cutoff=data['asOf'],issuer='MSFT',reviewed_basis=True)
   if result['value']!=expected:raise ValueError('Derived quarter differs from reviewed official GAAP release')
   result['derivation']['crossCheck']={'url':RELEASE,'reportedValue':expected,'filedAt':'2025-07-30','basis':'quarterly GAAP','reviewer':'codex_assistant'};derived.append(result)
  item=next(v for v in data['comparators'] if v['ticker']=='MSFT');item.update(metrics=derived,status='quarter_metrics_derived_verified',rankingEligible=False)
 data['version']='research-completion/v2-derived-quarter';data['checkedAt']=datetime.now(UTC).isoformat()
 write_json(output/'research-completion-local-707.json',data);write_json(site/'private-data/research-completions/local-707.json',data)
 print(json.dumps({'ticker':'MSFT','derivedMetrics':[{k:v for k,v in x.items() if k in ['concept','value','period_start','period_end']} for x in derived],'crossCheck':'passed','rankingEligible':False}),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--site',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.site,a.output)
