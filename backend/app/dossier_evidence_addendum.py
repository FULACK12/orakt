"""Immutable, source-bound evidence addendum to an existing reviewed report."""
import argparse
import hashlib
import json
from datetime import UTC,datetime
from decimal import Decimal
from html import escape
from pathlib import Path
from urllib.parse import unquote,urlsplit

from app.company_history_dossier import write_json
from app.dossier_legacy_evidence import extract_table,reconcile,recover_context,subtotal_checks
from app.dossier_readable_bundle import bi
from app.historical_earnings_report import FilingText
from app.review_frozen_dossier import load_frozen_packet

LABELS={'operating':('经营现金流','Operating cash flow'),'investing':('投资现金流','Investing cash flow'),
        'financing':('融资现金流','Financing cash flow'),'fx':('汇率影响','FX effect'),
        'netChange':('现金净增加','Net cash increase'),'opening':('期初现金及等价物','Opening cash and equivalents'),
        'closing':('期末现金及等价物','Closing cash and equivalents')}


def panel(result):
    parts=['<section id="evidence-addendum"><h1>'+bi('历史报告 · 原始资料补全','Historical report · Source evidence addendum')+'</h1>',
        '<div class="notice">'+bi('本补证更新现金勾稽与业务上下文。下方保留原版九章，不覆盖原审核；原稿中“现金表未齐、业务名称缺失”的判断已由本附录更新。同行、供应链、估值及 Alpha 验证仍未完成。','This addendum updates cash reconciliation and business context. The nine original chapters remain below without rewriting their audit. Their cash-table and segment-identity gaps are superseded here. Peer, supply-chain, valuation and alpha validation remain incomplete.')+'</div>',
        '<p>'+bi('数据口径：半年累计；单位：百万美元。数值取自原表，不是模型估算。','Basis: six-month cumulative; USD millions. Values are from the original statement, not model estimates.')+'</p>',
        '<div class="table-wrap"><table><tr><th>'+bi('项目','Item')+'</th>'+''.join('<th>'+escape(p)+'</th>' for p in result['cashReconciliations'])+'</tr>']
    for k,label in LABELS.items():
        parts.append('<tr><td>'+bi(*label)+'</td>'+''.join('<td>'+format(Decimal(result['facts'][k][p]['value'])/1000000,',.3f')+'</td>' for p in result['cashReconciliations'])+'</tr>')
    parts.append('</table></div><p>'+bi('两期现金恒等式和经营、投资、融资三类分项加总均已核对。算术通过不代表盈利质量或投资价值已验证。','Both cash identities and operating, investing and financing subtotals were reconciled. Arithmetic agreement does not validate earnings quality or investment value.')+'</p>')
    for context in result['contexts']:
        parts.append('<article><p>'+bi(context['finding']['zh'],context['finding']['en'])+'</p><details><summary>'+bi('原始上下文','Original context')+'</summary><code>'+escape(context['id'])+'</code><blockquote>'+escape(context['text'])+'</blockquote></details></article>')
    parts.append('<p>'+bi('可复现规则：原文哈希、表格序号、列日期、行标签与符号逐项绑定；空白不是零，括号负数不丢失，口径不同的现金不得混用。','Reproducibility: source hash, table index, date columns, labels and signs are bound explicitly. Blank is not zero, parentheses preserve negatives, and incompatible cash definitions cannot be mixed.')+'</p><details><summary>'+bi('全部现金流分项及原表坐标','All cash-flow components and source coordinates')+'</summary><div class="table-wrap"><table>')
    for key,periods in result['facts'].items():
        for period,f in periods.items():
            parts.append('<tr><td>'+escape(f['rawLabel'])+'</td><td>'+escape(period)+'</td><td>'+format(Decimal(f['value'])/1000000,',.3f')+'</td><td><code>'+escape(str(f['tableIndex'])+':'+str(f['rowIndex']))+'<br>'+escape(f['evidence_id'])+'</code></td></tr>')
    parts.append('</table></div></details><p class="muted">'+bi('仅为助手复审的历史资料补证，未对外发布；不等于人工批准或收益验证。','Assistant-reviewed historical evidence supplement only; unpublished, not human approval or return validation.')+'</p></section>')
    return ''.join(parts)


def run(parent,mapping_path,cold_root,output):
    if output.exists():raise ValueError('Preserve prior evidence revision')
    original,_=load_frozen_packet(parent/'source.json',cold_root);p=original['packet']
    mapping_raw=mapping_path.read_bytes();mapping=json.loads(mapping_raw)
    if mapping['ticker']!=p['ticker'] or mapping['accession']!=p['accession']:raise ValueError('Mapping identity mismatch')
    prior_raw=(parent/'dossier.json').read_bytes();prior=json.loads(prior_raw)
    manifest=json.loads((parent/'manifest.json').read_text(encoding='utf-8'))
    old_html=(parent/'readable.html').read_bytes()
    if (hashlib.sha256(prior_raw).hexdigest()!=manifest['dossierSha256'] or hashlib.sha256(old_html).hexdigest()!=manifest['readableSha256']
            or prior['sourceFingerprint']!=original['fingerprint'] or prior['review']['state']!='assistant_reviewed_research_only'):
        raise ValueError('Intact matching reviewed parent required')
    base=(cold_root/'raw/sec/company-filings'/p['ticker']).resolve()
    path=(base/p['accession'].replace('-','')/unquote(urlsplit(p['source_url']).path.rsplit('/',1)[-1])).resolve()
    if not path.is_relative_to(base):raise ValueError('Source escaped archive')
    raw=path.read_bytes();html=raw.decode('utf-8');parser=FilingText();parser.feed(html);text=parser.clean()
    if mapping['scaleEvidence'] not in text:raise ValueError('Reviewed monetary scale context missing')
    facts=extract_table(html,p['raw_sha256'],mapping)
    reconciliations={period:reconcile(facts,period) for period in mapping['columns']}
    subtotals={period:subtotal_checks(facts,mapping['subtotalGroups'],period) for period in mapping['columns']}
    if any(r['state']!='matched' for r in reconciliations.values()) or any(c['state']!='matched' for r in subtotals.values() for c in r.values()):
        raise ValueError('Cash statement does not reconcile; review before rendering')
    contexts=[{**recover_context(text,c['needle'],p['raw_sha256'],c['before'],c['after']),'finding':c['finding']} for c in mapping['contexts']]
    result={'version':'historical-evidence-addendum/v22','ticker':p['ticker'],'accession':p['accession'],
        'createdAt':datetime.now(UTC).isoformat(),'asOf':p['as_of_date'],'periodEnd':p['period_end'],
        'parent':str(parent),'parentSha256':hashlib.sha256(prior_raw).hexdigest(),'sourceFingerprint':original['fingerprint'],
        'sourceHash':p['raw_sha256'],'mappingHash':hashlib.sha256(mapping_raw).hexdigest(),'mapping':mapping,
        'facts':facts,'cashReconciliations':reconciliations,'subtotalChecks':subtotals,'contexts':contexts,
        'review':{'state':'assistant_reviewed_source_addendum','humanAccepted':False},
        'modelRequests':0,'published':False,'eligibleForPredictiveBacktest':False,'validatedAlpha':False}
    write_json(output/'addendum.json',result)
    # Archive original prose intact; prominent addendum explains superseded gaps.
    rendered=old_html.decode('utf-8').replace('<main>','<main>'+panel(result)+'<h2>'+bi('原版九章研究正文（缺口以顶部补证为准）','Original nine research chapters (see superseding evidence above)')+'</h2>',1)
    (output/'readable.html').write_text(rendered,encoding='utf-8')
    write_json(output/'manifest.json',{'state':result['review']['state'],'published':False,
        'addendumSha256':hashlib.sha256((output/'addendum.json').read_bytes()).hexdigest(),
        'readableSha256':hashlib.sha256((output/'readable.html').read_bytes()).hexdigest(),'parentSha256':result['parentSha256']})
    return result


def register(root,output):
    """Attach evidence without falsely counting another generated report."""
    from app.company_completion import connect,now
    raw=(output/'addendum.json').read_bytes();r=json.loads(raw)
    manifest=json.loads((output/'manifest.json').read_text(encoding='utf-8'))
    digest=hashlib.sha256(raw).hexdigest()
    if (digest!=manifest['addendumSha256']
            or hashlib.sha256((output/'readable.html').read_bytes()).hexdigest()!=manifest['readableSha256']
            or r['review']['state']!='assistant_reviewed_source_addendum'
            or any(r.get(k) is not False for k in ('published','eligibleForPredictiveBacktest','validatedAlpha'))):
        raise ValueError('Intact unpublished evidence addendum required')
    with connect(root) as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute("SELECT * FROM jobs WHERE kind='reports' AND key=?",(r['accession'],)).fetchone()
        if not old or old['ticker']!=r['ticker'] or old['state']!='assistant_reviewed_research_only':
            raise ValueError('Matching assistant-reviewed report required')
        detail=json.loads(old['detail'])
        if detail.get('dossierSha256')!=r['parentSha256']:raise ValueError('Reviewed parent changed')
        existing=detail.get('evidenceAddendum',{})
        if existing.get('sha256')==digest:return False
        if existing:raise ValueError('Preserve prior evidence attachment; explicit superseding review required')
        detail['evidenceAddendum']={'output':str(output),'sha256':digest,'readablePath':str(output/'readable.html'),
                                   'cashSourceCells':sum(len(v) for v in r['facts'].values()),'published':False}
        db.execute('CREATE TABLE IF NOT EXISTS report_transitions(id INTEGER PRIMARY KEY, accession TEXT, ticker TEXT, old_state TEXT, old_detail TEXT, new_state TEXT, artifact_hash TEXT, changed_at TEXT)')
        db.execute('INSERT INTO report_transitions(accession,ticker,old_state,old_detail,new_state,artifact_hash,changed_at) VALUES(?,?,?,?,?,?,?)',
            (r['accession'],r['ticker'],old['state'],old['detail'],old['state'],digest,now()))
        db.execute("UPDATE jobs SET detail=?,updated_at=? WHERE kind='reports' AND key=?",(json.dumps(detail,ensure_ascii=False),now(),r['accession']))
    return True


if __name__=='__main__':
    a=argparse.ArgumentParser()
    for k in ('parent','mapping','cold-root','output'):a.add_argument('--'+k,type=Path,required=True)
    v=a.parse_args();r=run(v.parent,v.mapping,v.cold_root,v.output)
    print(json.dumps({'ticker':r['ticker'],'cells':sum(len(v) for v in r['facts'].values()),'modelRequests':0,'published':False}))
