"""Offline recheck of retained drafts. No model calls, mutation or auto-approval."""
import argparse,hashlib,json
from datetime import datetime,UTC
from pathlib import Path
from app.company_history_dossier import CHAPTERS,Section,chapter_packet,validate_section,write_json
from app.dossier_accounting_checks import disclosed_reference_terms,balance_narrative_errors,methodological_errors
from app.dossier_passages import bind_selected_passages,check_claims
from app.review_frozen_dossier import load_frozen_packet

def audit(source,cold_root):
 wrapper,raw=load_frozen_packet(source,cold_root);packet=wrapper['packet'];chapters=[]
 terms=disclosed_reference_terms(packet)
 for i,(key,*_) in enumerate(CHAPTERS,1):
  evidence=chapter_packet(packet,key);passages=packet.get('chapter_passages',{}).get(key,[])
  allowed={packet['filing_ref'],*(f['evidence_id'] for f in packet['facts']),*(s['id'] for s in packet.get('market_evidence',[])),*(p['id'] for p in passages)}
  required=[c['id'] for c in evidence['financial_ledger']['comparisons'] if c['concept'] in {'NetCashProvidedByUsedInOperatingActivities','OperatingIncomeLoss','RevenueFromContractWithCustomerExcludingAssessedTax','PaymentsToAcquirePropertyPlantAndEquipment','SimplifiedFreeCashFlow'} or (key=='business' and 'RevenueFromContract' in c['concept'])][:6] if key in {'business','financial','capital','conclusion'} else []
  attempts=[]
  for path in sorted(source.parent.glob(f'{i:02d}-{key}-passage-selection-v12-*.json')):
   if '.partial.' in path.name:continue
   content=path.read_bytes();result={'file':path.name,'sha256':hashlib.sha256(content).hexdigest(),'errors':[]}
   try:
    original=json.loads(content)
    if original.get('done_reason')=='length':raise ValueError('Truncated model output')
    section=Section.model_validate(bind_selected_passages(json.loads(original['message']['content']),passages))
    result['errors'].extend(balance_narrative_errors(section,packet['financial_ledger'])+methodological_errors(section))
    validate_section(section,allowed,packet['financial_ledger'],required,terms)
    check_claims(section.grounded_claims,passages,required=True)
   except (ValueError,KeyError) as exc:result['errors'].append(str(exc))
   result['errors']=list(dict.fromkeys(result['errors']))
   result['state']='rejected_structural_or_narrow_semantic' if result['errors'] else 'structure_checked_content_review_required'
   attempts.append(result)
  chapters.append({'key':key,'attempts':attempts,'passingAttempts':sum(not r['errors'] for r in attempts)})
 return {'schema':'frozen-dossier-audit/v1','checkedAt':datetime.now(UTC).isoformat(),'ticker':packet['ticker'],'asOf':packet['as_of_date'],'sourcePacketHash':hashlib.sha256(raw).hexdigest(),'sourceDocumentHash':packet['raw_sha256'],'sourceAttestedIdentifiers':terms,'chapters':chapters,'semanticApproval':False,'published':False,'modelRequests':0}

if __name__=='__main__':
 p=argparse.ArgumentParser()
 for name in ['source','cold-root','output']:p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args()
 if a.output.exists():raise ValueError('Preserve audit; choose a fresh output path')
 result=audit(a.source,a.cold_root);write_json(a.output,result)
 print(json.dumps({'ticker':result['ticker'],'chapters':[{'key':c['key'],'attempts':len(c['attempts']),'passing':c['passingAttempts']} for c in result['chapters']],'modelRequests':0,'published':False}))
