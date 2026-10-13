"""Freeze explicit human/assistant findings on a development trial; no approval.

The supplied review is trusted operator input, never local-model output. Exact
wrong spans and original sources must exist. Training remains disabled.
"""
import argparse
import json
from collections import Counter
from datetime import UTC,datetime
from html import escape
from pathlib import Path
from app.report_quality import check, passages, units, repair, worklist, rules_digest
from app.report_rejections import reject, sha
from app.report_usage import save


def run(root, findings_path, output):
    if output.exists():raise ValueError('Preserve earlier review output')
    original=json.loads((root/'source.json').read_text(encoding='utf-8'))
    report_path=root/'draft-report.json'
    report=json.loads(report_path.read_text(encoding='utf-8'));documents=report['chapters'];packet=original['packet']
    explicit=json.loads(findings_path.read_text(encoding='utf-8'))
    if explicit.get('reviewer')!='codex_assistant' or explicit.get('state')!='rejected_development_trial':
        raise ValueError('Explicit rejected development review required')
    index={u['id']:u for u in units(documents,packet)};sources=passages(packet)
    bound=[]
    for finding in explicit['findings']:
        loc='/'.join((finding['chapter'],'section',finding['field'],finding['language']))
        u=index[loc]
        if finding['wrong'] not in u['text']:raise ValueError('Wrong span not found: '+finding['id'])
        if not finding['correction'] or not finding['sourceIds']:raise ValueError('Missing corrected handling/evidence')
        bound.append({**finding,'location':loc,'fingerprint':u['fingerprint'],
            'wrongVersion':u['text'],'originalEvidence':[sources[pid] for pid in finding['sourceIds']],
            'facts':[f for f in packet.get('facts',[]) if f['evidence_id'] in finding.get('factIds',[])],
            'affectedConclusions':['valuation','factors','conclusion'],
            'trainingEligible':False,'correctedHandlingIsNotApprovedFullAnswer':True})
    checked=check(packet,documents,complete=True)
    # Precisely scoped bilingual arithmetic correction; this is NOT a repaired
    # full report or permission to erase the original rejected model response.
    patches=[]
    for lang,old,new in [('zh','增加393百万美元','增加403百万美元'),('en','up $393 million','up $403 million')]:
        u=index['financial/section/counterEvidence/'+lang]
        if old not in u['text']:raise ValueError('Arithmetic patch no longer matches')
        patches.append({'id':u['id'],'fingerprint':u['fingerprint'],
            'replacement':u['text'].replace(old,new),'reason':'Original same-period cash taxes 4539 - 4136 = 403 million USD; retained source PASSAGE:af5763c1ef64e451'})
    repaired=repair(packet,documents,patches)
    before={f['location'] for f in checked['findings'] if f['code']=='cash_tax_change_arithmetic'}
    after={f['location'] for f in repaired['checks']['findings'] if f['code']=='cash_tax_change_arithmetic'}
    if len(before)!=2 or after:raise ValueError('Expected bilingual arithmetic regression did not clear')
    output.mkdir(parents=True)
    save(output/'source-bound-findings.json',{'reviewer':'codex_assistant','findings':bound,
         'reviewCoverage':'Targeted rejection review of retained nine-chapter draft, not exhaustive sentence acceptance.',
         'sourceSha256':sha(root/'source.json'),'draftSha256':sha(report_path),'reviewInputSha256':sha(findings_path)})
    save(output/'mechanical-checks.json',checked)
    save(output/'localized-repair.json',repaired)
    save(output/'semantic-worklist.json',worklist(packet,documents,complete=True))
    event=reject(root,source=root/'source.json',candidate=report_path,chapter=None,
        phase='whole_report_review',findings=bound,context_paths=[findings_path,output/'source-bound-findings.json'])
    summary={'state':'rejected_quality_review','at':datetime.now(UTC).isoformat(),'ticker':packet['ticker'],
        'chaptersGenerated':len(documents),'sourcePeriodEnd':packet['period_end'],'asOf':packet['as_of_date'],
        'developmentOnly':True,'holdoutUsed':False,'published':False,'automaticApprovalEnabled':False,
        'semanticFindingCount':len(bound),'categories':dict(Counter(f['category'] for f in bound)),
        'mechanicalFindings':dict(Counter(f['code'] for f in checked['findings'])),
        'rulesetSha256':rules_digest(),'wholeReportRejections':1,
        'rejectionPolicy':event['policy'],'trainingEligible':False,
        'localizedRepair':{'bilingualUnitsChanged':2,'arithmeticFindingsBefore':len(before),'arithmeticFindingsAfter':len(after),
                           'newDetectedErrors':0,'state':'pending_semantic_recheck_not_approved_report'},
        'usage':{k:v for k,v in json.loads((root/'usage-summary.json').read_text(encoding='utf-8')).items() if k!='calls'},
        'next':'Correct table context/retrieval and bind quantitative claims before another generation revision. Do not regenerate all nine chapters or auto-approve this draft.'}
    save(output/'summary.json',summary)
    # Reader artifact; no website deployment, links/scripts/network resources.
    html=['<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>CVX — 拒绝草稿与质量检查</title>',
      '<style>body{font:16px/1.7 system-ui,sans-serif;max-width:1020px;margin:40px auto;padding:0 24px;color:#17212d;background:#f5f7fa}h1,h2{line-height:1.3}article,section{background:white;padding:24px;margin:20px 0;border-radius:12px}aside{background:#fff0ed;border-left:4px solid #ad311b;padding:18px}p,pre{overflow-wrap:anywhere}pre{white-space:pre-wrap}summary{cursor:pointer;font-weight:600}small{color:#536273}</style>',
      '<h1>CVX 单公司报告 · 质量试跑</h1><aside><strong>拒绝草稿 · 未发布 · 不可用作投资结论或训练正确答案</strong><br>九章生成完成不等于审核通过。以下先显示审查结果，再保留原始错误草稿供核对。</aside>',
      '<p>资料截止 '+escape(packet['as_of_date'])+'；报告期末 '+escape(packet['period_end'])+'；实际生成时间见原始记录。仅为开发样本，不是独立验证集。</p>',
      '<section><h2>实质审核问题</h2>']
    for f in bound:
        html+=['<article><h3>'+escape(f['id']+' · '+f['category'])+'</h3><small>'+escape(f['location'])+'</small>',
               '<p>错误：'+escape(f['wrong'])+'</p><p>正确处理：'+escape(f['correction'])+'</p>',
               '<details><summary>原始证据</summary>'+''.join('<pre>'+escape(p['id']+'\n'+p['text'])+'</pre>' for p in f['originalEvidence'])+'</details></article>']
    html+=['</section><h2>九章原始拒绝稿（含已识别错误，不作正确答案）</h2>']
    titles={'business':'业务','financial':'财务','capital':'资本结构','competition':'竞争','supply':'供应链','macro':'宏观','valuation':'估值','factors':'因子假设','conclusion':'结论'}
    for doc in documents:
        html+=['<section><details><summary>'+escape(titles[doc['chapter']])+' · 原始拒绝稿</summary>']
        for field in ('analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'):
            pair=doc['section'][field]
            html+=['<h3>'+escape(field)+'</h3><p>'+escape(pair['zh'])+'</p><p lang="en">'+escape(pair['en'])+'</p>']
        html+=['</details></section>']
    (output/'review.html').write_text(''.join(html),encoding='utf-8')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('root','findings','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(run(a.root,a.findings,a.output),ensure_ascii=False))
