"""Reconnect immutable reviewed chapters to one report; never auto-approve it.

Structure, source coverage, whole-report review and predictive eligibility are
separate states. Reusing validated prose makes no new GPU/model request.
"""
import argparse
import hashlib
import json
import re
import time
from datetime import UTC, datetime
from decimal import Decimal
from html import escape
from pathlib import Path

from app.company_history_dossier import CHAPTERS, Section, validate_section, write_json
from app.dossier_cash_bridge import packet_passages, cash_bridge, guard_cash_narrative
from app.dossier_passages import check_claims
from app.dossier_market_readiness import market_readiness
from app.dossier_readable_bundle import bi, render
from app.review_frozen_dossier import load_frozen_packet
from app.dossier_accounting_checks import disclosed_reference_terms

CONCEPTS = {
    'RevenueFromContractWithCustomerExcludingAssessedTax':('营业收入','Revenue'),
    'Revenues':('营业收入','Revenue'), 'SalesRevenueNet':('销售净收入','Net sales'),
    'GrossProfit':('毛利','Gross profit'), 'OperatingIncomeLoss':('营业利润／亏损','Operating income/loss'),
    'NetIncomeLoss':('净利润／亏损','Net income/loss'),
    'EarningsPerShareDiluted':('稀释每股收益','Diluted EPS'),
    'Assets':('总资产','Assets'), 'Liabilities':('总负债','Liabilities'),
    'StockholdersEquity':('股东权益','Equity'), 'InventoryNet':('存货净额','Inventory, net'),
    'InventoryFinishedGoodsNetOfReserves':('产成品存货净额','Finished goods, net'),
    'NetCashProvidedByUsedInOperatingActivities':('经营现金流','Operating cash flow'),
    'NetCashProvidedByUsedInInvestingActivities':('投资现金流','Investing cash flow'),
    'NetCashProvidedByUsedInFinancingActivities':('融资现金流','Financing cash flow'),
    'PaymentsToAcquirePropertyPlantAndEquipment':('固定资产购置支出','Capital expenditure'),
    'SimplifiedFreeCashFlow':('简化自由现金流（计算值）','Simplified free cash flow (derived)'),
}


def financial_tables(ledger):
    parts=['<section id="financial-tables"><h2>'+bi('财务原值与同口径比较','Reported financial values and matched comparisons')+'</h2><p>'+bi('数值由冻结资料确定性计算，不由模型编写。金额按原始单位显示；时点余额、单季、累计和年度期间不能相加或混用。变化率不代表股价收益。','Values are deterministically derived from frozen evidence, not authored by the model. Original units are retained. Instant balances, quarters, cumulative and annual periods must not be mixed. Changes are not stock returns.')+'</p>']
    rows=ledger['comparisons']
    for core in (True, False):
        selected=[c for c in rows if (c['concept'] in CONCEPTS)==core]
        if not selected:continue
        if not core:parts.append('<details><summary>'+bi('全部其余科目与维度明细','Other concepts and dimensional breakdowns')+'</summary>')
        parts.append('<div class="table-wrap"><table><tr>'+''.join('<th>'+bi(*x)+'</th>' for x in [('科目／单位','Concept / unit'),('本期区间／值','Current period / value'),('比较期区间／值','Comparison period / value'),('口径／变化','Basis / change')])+'</tr>')
        for c in selected:
            parts.append('<tr><td>'+bi(*CONCEPTS.get(c['concept'],(c['concept'],c['concept'])))+'<br><code>'+escape(c['concept'])+'</code><br>'+escape(c['unit'])+'</td>')
            for side in ('current','previous'):
                r=c[side];v=Decimal(str(r['value']))
                if not v.is_finite():raise ValueError('Non-finite source figure')
                span=(str(r.get('period_start'))+' — ' if r.get('period_start') else '')+str(r['period_end'])
                parts.append('<td>'+escape(span)+'<br><strong>'+escape(format(v,',f'))+'</strong><br><code>'+escape(r['evidence_id'])+'</code></td>')
            change='—' if c.get('changePercent') is None else format(Decimal(str(c['changePercent'])),'.2f')+'%'
            parts.append('<td>'+escape(c['periodType']+' / '+c['comparisonBasis'])+'<br>'+escape(change)+'<br><code>'+escape(c['id'])+'</code></td></tr>')
        parts.append('</table></div>')
        if not core:parts.append('</details>')
    return ''.join(parts)+'</section>'


def validate_chapters(original, documents):
    packet=original['packet'];required={c[0] for c in CHAPTERS}
    if len(documents)!=len(required) or {d['chapter'] for d in documents}!=required:
        raise ValueError('Exactly nine distinct reviewed chapters required')
    passages=list(packet_passages(packet).values());ids={p['id'] for p in passages}
    meta={k:packet.get(k) for k in ('ticker','accession','as_of_date','period_end','source_url','raw_sha256')}
    checked={}
    for d in documents:
        if d['ticker']!=packet['ticker'] or d['sourceFingerprint']!=original['fingerprint']:
            raise ValueError('Chapter company/frozen evidence mismatch')
        if d.get('state')!='assistant_reviewed' or d.get('published') is not False:
            raise ValueError('Reviewed unpublished chapter required')
        review=d.get('review',{})
        if review.get('reviewer')!='codex_assistant' or review.get('state')!='accepted_with_revisions' or not review.get('findings'):
            raise ValueError('Explicit chapter review required')
        for k in ('parentSha256','reviewSha256'):
            if not re.fullmatch('[a-f0-9]{64}',review.get(k,'')):raise ValueError('Review provenance hash missing')
        if d.get('sourceMetadata') and d['sourceMetadata']!=meta:raise ValueError('Chapter metadata conflict')
        s=Section.model_validate(d['section'])
        from app.dossier_semantic_guards import guard_known_semantics
        guard_known_semantics(s,packet)
        from app.dossier_compact_writer import check_cash_evidence_use
        check_cash_evidence_use(s,packet,d['chapter'])
        validate_section(s,ids|{packet['filing_ref']},packet['financial_ledger'],technical_terms=disclosed_reference_terms(packet))
        check_claims(s.grounded_claims,passages,required=True)
        for field in ('analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'):
            for language in ('zh','en'):
                refs=set(re.findall(r'PASSAGE:[a-f0-9]{16}',getattr(getattr(s,field),language)))
                if not refs or refs-ids:raise ValueError('Paragraph references outside frozen packet')
        if d['chapter'] in {'financial','capital'}:guard_cash_narrative(s,packet)
        copy={**d,'sourceMetadata':meta,'section':s.model_dump()}
        if d['chapter'] in {'financial','capital'}:copy['cashBridge']=cash_bridge(packet)
        if d['chapter'] in {'valuation','factors','conclusion'}:copy['marketReadiness']=market_readiness(packet)
        checked[d['chapter']]=copy
    return [checked[key] for key,*_ in CHAPTERS]


def assemble(source, chapter_paths, cold_root, output):
    if output.exists():raise ValueError('Preserve existing report revision')
    started=time.monotonic()
    original,raw=load_frozen_packet(source,cold_root);packet=original['packet']
    docs=[];inputs=[]
    for path in chapter_paths:
        body=path.read_bytes();docs.append(json.loads(body))
        inputs.append({'path':str(path),'sha256':hashlib.sha256(body).hexdigest()})
    chapters=validate_chapters(original,docs)
    # Keep all same-filing accounting values, not just qualitative prose.
    result={'version':'consolidated-company-report/v20','ticker':packet['ticker'],
        'accession':packet['accession'],'asOf':packet['as_of_date'],'periodEnd':packet['period_end'],
        'createdAt':datetime.now(UTC).isoformat(),'sourceFingerprint':original['fingerprint'],
        'structureComplete':True,'dataCoverage':'partial_with_explicit_gaps',
        'review':{'state':'whole_report_review_pending','chapterReviews':9,'humanAccepted':False},
        'published':False,'eligibleForPredictiveBacktest':False,'validatedAlpha':False,
        'valuationState':'framework_only','chapters':chapters,
        'facts':packet['facts'],'financialLedger':packet['financial_ledger'],
        'source':{'id':packet['filing_ref'],'url':packet['source_url'],'documentSha256':packet['raw_sha256']},
        'marketReadiness':market_readiness(packet),'cashBridge':cash_bridge(packet),
        'sourcePacketSha256':hashlib.sha256(raw).hexdigest(),'retainedChapterInputs':inputs,
        'evidenceGaps':[{'chapter':d['chapter'],**d['section']['evidenceGaps']} for d in chapters],
        'measurement':{'modelRequests':0,'assemblySeconds':round(time.monotonic()-started,3),
            'generationThroughputMeasured':False,'note':'Reuses reviewed local drafts; not a fresh report generation speed sample.'}}
    if packet.get('verified_cash_source'):result['cashSourceEvidence']=packet['verified_cash_source']
    html=render(chapters,result)
    write_json(output/'source.json',original)
    write_json(output/'dossier.json',result)
    from app.report_quality import write_worklist
    from app.report_usage import stage_event
    write_worklist(output/'semantic-worklist.json',packet,chapters,complete=True)
    stage_event(output,'assembly',started,outcome='whole_report_review_pending',
                identity={'ticker':packet['ticker'],'accession':packet['accession']})
    (output/'readable.html').write_text(html,encoding='utf-8')
    write_json(output/'manifest.json',{'ticker':packet['ticker'],'accession':packet['accession'],
        'dossierSha256':hashlib.sha256((output/'dossier.json').read_bytes()).hexdigest(),
        'readableSha256':hashlib.sha256((output/'readable.html').read_bytes()).hexdigest(),
        'state':'whole_report_review_pending','published':False})
    return result


def register(root, output):
    """CAS-like queue handoff preserving the old failure, not a review approval."""
    from app.company_completion import connect, now
    raw=(output/'dossier.json').read_bytes();d=json.loads(raw)
    m=json.loads((output/'manifest.json').read_text(encoding='utf-8'))
    digest=hashlib.sha256(raw).hexdigest()
    if digest!=m['dossierSha256'] or d['review']['state']!='whole_report_review_pending' or not d['structureComplete'] or d['published']:
        raise ValueError('Report is not an intact pending-review assembly')
    with connect(root) as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute("SELECT * FROM jobs WHERE kind='reports' AND key=?",(d['accession'],)).fetchone()
        if not old or old['ticker']!=d['ticker']:raise ValueError('Missing or mismatched existing report job')
        if old['state']=='assembled_review_pending':
            if json.loads(old['detail']).get('dossierSha256')==digest:return False
            raise ValueError('Different assembly already registered')
        if old['state'] not in {'repair_required','queued','content_review_pending'}:raise ValueError('Cannot supersede active or published report job')
        db.execute('CREATE TABLE IF NOT EXISTS report_transitions(id INTEGER PRIMARY KEY, accession TEXT, ticker TEXT, old_state TEXT, old_detail TEXT, new_state TEXT, artifact_hash TEXT, changed_at TEXT)')
        db.execute('INSERT INTO report_transitions(accession,ticker,old_state,old_detail,new_state,artifact_hash,changed_at) VALUES(?,?,?,?,?,?,?)',
            (d['accession'],d['ticker'],old['state'],old['detail'],'assembled_review_pending',digest,now()))
        detail={'output':str(output),'dossierSha256':digest,'published':False,'wholeReportReview':'pending','structureComplete':True,'dataCoverage':d['dataCoverage']}
        db.execute("UPDATE jobs SET state='assembled_review_pending',detail=?,updated_at=? WHERE kind='reports' AND key=?",
            (json.dumps(detail,ensure_ascii=False),now(),d['accession']))
    return True


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--chapters',type=Path,nargs='+',required=True)
    p.add_argument('--cold-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--register-root',type=Path)
    a=p.parse_args();d=assemble(a.source,a.chapters,a.cold_root,a.output)
    if a.register_root:register(a.register_root,a.output)
    print(json.dumps({'ticker':d['ticker'],'chapters':len(d['chapters']),'comparisons':len(d['financialLedger']['comparisons']),'state':d['review']['state'],'modelRequests':0}))
