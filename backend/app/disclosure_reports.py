"""One source-linked factual review per original company filing; no LLM arithmetic.

These evidence reviews do not replace nine-chapter research dossiers. Missing
valuation, competitive and macro evidence remains explicit, never filled by prose.
"""
import argparse,hashlib,json
from pathlib import Path
from datetime import UTC,datetime
from sqlalchemy import select
from app.db.models import CompanyFiling,CompanyProfile
from app.db.session import get_session_factory
from app.historical_earnings_report import build_packet
from app.financial_period_ledger import build_ledger
from app.company_history_dossier import write_json

def make_review(packet,name,form):
    ledger=build_ledger(packet)
    if not ledger['comparisons']:raise ValueError('No valid period comparisons')
    # All quantities stay in native units; translations never rescale them.
    comparisons=ledger['comparisons']
    return {'id':'filing-'+packet['accession'],'ticker':packet['ticker'],'name':name,'form':form,
        'filedAt':packet['as_of_date'],'periodEnd':packet['period_end'],'sourceUrl':packet['source_url'],
        'sourceHash':packet['raw_sha256'],'type':'disclosure_evidence_review','mode':'historical_reconstruction',
        'method':'deterministic_same_filing_period_checks_v1','predictiveConfidence':None,'comparisons':comparisons,
        'issues':ledger.get('excluded',ledger.get('problems',[])),
        'summary':{'zh':'本报告核对该次披露的财务期间、原始单位和可比变化。只报告同一申报中可追溯的计算，不把收入增长、费用下降或现金余额变化直接解释为竞争力、效率或现金流改善。',
            'en':'This review checks fiscal periods, original units and comparable changes within one filing. Revenue growth, lower expenses or balance changes do not by themselves establish competitive strength, efficiency or improved cash flow.'},
        'gaps':{'zh':['这是一份披露证据核验报告，不是完整估值或投资建议。','原文归档不代表全部业务、风险与同行证据已结构化。','需要补充产品销量、价格、合同、竞争对手同口径资料及市场预期差。','历史回溯不计入当时预测胜率；模型完整报告仍须逐条内容复审。'],
            'en':['A disclosure evidence review, not a complete valuation or investment recommendation.','An archived filing does not mean every operating, risk and peer fact is structured.','Product volume, pricing, contracts, peer-comparable disclosures and market expectations still require evidence.','Historical reconstruction is not a contemporaneous prediction; full model dossiers still require claim-level review.']}}

def run(cold,site,limit):
    root=cold/'orakt/disclosure-reviews-v82';root.mkdir(parents=True,exist_ok=True)
    retained={};published=site/'private-data/disclosure-reviews.json'
    if published.exists():retained={r['id']:r for r in json.loads(published.read_text(encoding='utf-8'))['reports']}
    added=[];coverage={};seen=set()
    with get_session_factory()() as s:
        names={r.ticker:r.name for r in s.scalars(select(CompanyProfile))}
        filings=list(s.scalars(select(CompanyFiling).where(CompanyFiling.form.in_(['10-Q','10-K'])).order_by(CompanyFiling.filed_at)))
        # Round robin by company, each company's earliest retained disclosure first.
        for f in filings:
            coverage[f.ticker]=coverage.get(f.ticker,0)+1
        for f in filings:
            if len(added)>=limit:break
            if f.ticker in seen or 'filing-'+f.accession_number in retained:continue
            base=(cold/'raw/sec/company-filings'/f.ticker).resolve();body=(base/f.accession_number.replace('-','')/(f.primary_document or '')).resolve()
            if not f.primary_document or not body.is_relative_to(base) or not body.is_file():continue
            try:
                packet=build_packet(s,ticker=f.ticker,cold_root=cold,accession=f.accession_number)
                review=make_review(packet,names.get(f.ticker,f.ticker),f.form)
            except ValueError:continue
            frozen=root/(review['id']+'.json')
            if frozen.exists() and json.loads(frozen.read_text(encoding='utf-8'))!=review:
                raise ValueError('Existing review differs; create an explicit new revision')
            if not frozen.exists():write_json(frozen,review)
            retained[review['id']]=review;added.append(review['id']);seen.add(f.ticker)
    result={'schema':'disclosure-reviews/v1','generatedAt':datetime.now(UTC).isoformat(),'reports':sorted(retained.values(),key=lambda r:(r['filedAt'],r['ticker'])),'fullDossierCount':0,'indexedOriginalFilings':sum(coverage.values()),'indexedCompanies':len(coverage),'complete':False}
    write_json(published,result)
    print(json.dumps({'added':len(added),'totalEvidenceReviews':len(retained),'fullDossiersAdded':0,'companiesThisBatch':sorted(seen),'firstDate':result['reports'][0]['filedAt'] if retained else None}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cold',type=Path,required=True);p.add_argument('--site',type=Path,required=True);p.add_argument('--limit',type=int,default=12);a=p.parse_args();run(a.cold,a.site,max(1,min(30,a.limit)))
