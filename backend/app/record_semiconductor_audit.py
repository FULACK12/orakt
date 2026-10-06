"""Record this explicit assistant review, never turn a blocked draft into a report."""
import argparse,json
from pathlib import Path
from datetime import datetime,UTC
from app.company_history_dossier import write_json,CHAPTERS
from app.dossier_accounting_checks import gross_margin_checks

FINDINGS={
 'NVDA':{'accession':'0001045810-25-000116','issues':{'zh':['财务章将毛利率下降写成上升；毛利额与毛利率混淆。','总结章三次校验仍将经营利润同比上升写成下降。','投资现金流、资本支出归因和产品编号需修订。'],'en':['The financial chapter describes a falling gross margin as rising, confusing profit amount with margin.','The conclusion failed three checks by describing higher operating income as a decrease.','Investing-cash-flow attribution and product identifiers need revision.']}},
 'AMD':{'accession':'0000002488-25-000047','issues':{'zh':['业务章将研发和管理费用上升写成减少。','财务章两次内容不足，第三次引用了证据包之外的 ID。','完整九章尚未通过审核，不进入公开报告库。'],'en':['The business chapter describes rising R&D and administrative expenses as reductions.','The financial chapter was too brief twice, then cited an ID outside the evidence packet.','A full nine-chapter report has not passed review and is not published.']}}
}
def run(root,site,output):
 audits=[]
 for ticker,review in FINDINGS.items():
  folder=root/ticker/review['accession'];p=json.loads((folder/'source.json').read_text(encoding='utf-8'))
  audits.append({'ticker':ticker,'asOf':p['packet']['as_of_date'],'retainedChapters':sum((folder/f'{i+1:02d}-{k}.json').is_file() for i,(k,*_) in enumerate(CHAPTERS)),'totalChapters':9,'state':'blocked_by_review','published':False,'reviewer':'codex_assistant','issues':review['issues'],'ratioChecks':gross_margin_checks(p['packet']['financial_ledger'])})
 record={'checkedAt':datetime.now(UTC).isoformat(),'running':False,'reports':audits,'scope':'This bounded two-company run only; not a live global queue.'}
 write_json(output/'semiconductor-generation-audit.json',record)
 path=site/'private-data/research-completions/local-707.json';data=json.loads(path.read_text(encoding='utf-8'));data['draftAudit']=record;write_json(path,data)
 print(json.dumps({'running':False,'reports':[{k:r[k] for k in ['ticker','retainedChapters','state','published']} for r in audits]}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--site',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.root,a.site,a.output)
