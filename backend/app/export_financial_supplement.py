"""Export mechanically verified filing data without replacing reviewed prose."""
import argparse, json, hashlib, re
from pathlib import Path
from datetime import datetime, UTC
from app.financial_period_ledger import build_ledger
from app.company_history_dossier import write_json


def export(source,site_root,report_id):
    if not re.fullmatch(r'local-\d+',report_id):raise ValueError('Invalid report ID')
    envelope=json.loads(source.read_text(encoding='utf-8'));packet=envelope['packet']
    original=json.loads((site_root/'private-data/research-reports'/f'{report_id}.json').read_text(encoding='utf-8'))['report']
    if original['ticker']!=packet['ticker'] or original['dataCutoff']!=packet['as_of_date']:raise ValueError('Report identity/cutoff mismatch')
    ledger=build_ledger(packet)
    if not ledger['comparisons'] or ledger['excluded']:raise ValueError('Resolve excluded/conflicting source facts before export')
    coverage=[{'id':s['id'],'name':s['name'],'unit':s['unit'],'count':len(s['observations']),'start':s['observations'][0]['date'],'end':s['observations'][-1]['date'],'sourceUrl':s['source_url'],'vintage':s['vintage']} for s in packet.get('market_evidence',[]) if s['observations']]
    result={'ticker':packet['ticker'],'asOf':packet['as_of_date'],'periodEnd':packet['period_end'],'sourceDocumentHash':packet['raw_sha256'],
            'sourceUrl':packet['source_url'],'packetFingerprint':envelope['fingerprint'],'sourceEnvelopeHash':hashlib.sha256(source.read_bytes()).hexdigest(),
            'financialLedger':ledger,'marketCoverage':coverage,'inlineCoverage':packet.get('inline_coverage'),
            'review':{'status':'arithmetic_checked_narrative_not_replaced','reviewer':'deterministic_period_ledger','checkedAt':datetime.now(UTC).isoformat(),'humanAccepted':False,'changesReportConfidence':False,'predictiveBacktestEligible':False}}
    output=site_root/'private-data/report-supplements'/f'{report_id}.json';write_json(output,result)
    print(json.dumps({'path':str(output),'comparisons':len(ledger['comparisons']),'marketSeries':len(coverage),'oldNarrativePreserved':True}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--site-root',type=Path,required=True);p.add_argument('--report-id',required=True)
    a=p.parse_args();export(a.source,a.site_root,a.report_id)
