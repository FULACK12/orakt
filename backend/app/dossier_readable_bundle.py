"""Offline bilingual review artifact. No network, login or publication actions."""
import argparse
import hashlib
import json
from decimal import Decimal
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

LABELS={'business':('业务与收入驱动','Business and revenue drivers'),
        'financial':('财务质量与现金流','Financial quality and cash flow'),
        'capital':('资本配置与流动性','Capital allocation and liquidity'),
        'competition':('竞争与技术替代','Competition and technology substitution'),
        'supply':('供应链与生产资源','Supply chain and production resources'),
        'macro':('宏观风险与传导','Macroeconomic risks and transmission'),
        'valuation':('估值框架与多期限情景','Valuation framework and horizons'),
        'factors':('因子假设与双基准验证设计','Factor hypotheses and dual-benchmark design'),
        'conclusion':('综合判断与观察清单','Synthesis and monitoring checklist'),
        'analysis':('已披露事实与分析','Disclosed facts and analysis'),
        'mechanism':('待验证的传导假设','Conditional mechanism'),
        'counterEvidence':('替代解释与反证','Alternatives and falsification'),
        'evidenceGaps':('本次证据缺口','Gaps in selected evidence'),
        'validationPlan':('后续验证计划','Validation plan')}


def bi(zh,en):return '<span class="zh">'+escape(zh)+'</span><span class="en">'+escape(en)+'</span>'


def render(chapters, dossier=None):
    if not chapters or len({d['ticker'] for d in chapters})!=1 or len({d['sourceFingerprint'] for d in chapters})!=1:
        raise ValueError('Bundle must use one company and one frozen evidence revision')
    if any(d.get('state')!='assistant_reviewed' or d.get('completeDossier') is not False or d.get('published') is not False for d in chapters):
        raise ValueError('Only reviewed, unpublished partial chapters allowed')
    if len({d['chapter'] for d in chapters})!=len(chapters):raise ValueError('Duplicate chapter')
    if dossier is not None and (len(chapters)!=9 or dossier.get('sourceFingerprint')!=chapters[0]['sourceFingerprint']):
        raise ValueError('Consolidated report requires nine matching reviewed chapters')
    title=escape(chapters[0]['ticker']);meta=chapters[0]['sourceMetadata'];parts=[]
    parts.append('<header><p class="eyebrow">ORAKT · LOCAL RESEARCH REVIEW</p><h1>'+title+' '+bi('研究章节审阅稿','Reviewed research chapters')+'</h1><p>'+bi('截至 '+str(meta.get('as_of_date'))+' 的冻结资料；报告期末 '+str(meta.get('period_end')), 'Frozen evidence as of '+str(meta.get('as_of_date'))+'; period end '+str(meta.get('period_end')) )+'</p><div class="notice">'+bi(f'已复审 {len(chapters)} / 9 个章节。这不是完整公司报告，未发布，不构成买卖建议。本地 AI 生成后经助手修订，不等于独立第三方验证或用户人工批准。',f'{len(chapters)} / 9 chapters reviewed. Not a complete company report; unpublished and not a trading recommendation. Local-model drafts revised by the assistant, not independent verification or human approval.')+'</div></header>')
    if dossier is not None:
        parts[0]='<header><p class="eyebrow">ORAKT · COMPANY RESEARCH</p><h1>'+title+' '+bi('公司研究报告 · 整合待复核','Company research report · Integrated review pending')+'</h1><p>'+bi('披露截至日 '+str(meta.get('as_of_date'))+'；报告期末 '+str(meta.get('period_end')),'Disclosure cutoff '+str(meta.get('as_of_date'))+'; period end '+str(meta.get('period_end')))+'</p><div class="notice">'+bi('九章正文、财务数值表与原始引用已合并。章节已分别复审，整份报告仍待交叉复核；结构完整不表示证据齐全。估值为框架，因子为假设，不提供已验证目标价或交易结论。','Nine chapters, financial tables and original references consolidated. Chapters were reviewed separately; whole-report review remains pending. Structural completion does not imply complete evidence. Valuation is a framework and factors are hypotheses, not validated targets or trading conclusions.')+'</div><p>'+bi('生成时间 '+dossier['createdAt']+'。历史资料回溯重建，不是当时已发布的预测。','Assembled '+dossier['createdAt']+'. Retrospective reconstruction, not a forecast published at the historical date.')+'</p></header>'
        from app.dossier_consolidation import financial_tables
        parts.append(financial_tables(dossier['financialLedger']))
        if dossier.get('review',{}).get('state') == 'assistant_reviewed_research_only':
            review=dossier['review'];audit=dossier.get('wholeReportAudit',{})
            if review.get('reviewer')!='codex_assistant' or review.get('humanAccepted') is not False or not audit.get('checks'):
                raise ValueError('Explicit whole-report audit required')
            parts[0]='<header><p class="eyebrow">ORAKT · COMPANY RESEARCH</p><h1>'+title+' '+bi('历史公司研究报告 · 助手复审版','Historical company research · Assistant-reviewed')+'</h1><p>'+bi('披露截至日 '+str(meta.get('as_of_date'))+'；报告期末 '+str(meta.get('period_end')),'Disclosure cutoff '+str(meta.get('as_of_date'))+'; period end '+str(meta.get('period_end')))+'</p><div class="notice">'+bi('九章及跨章节一致性已由助手复审。结构齐全，但市场、同行与供应链证据仍有缺口；不是独立第三方验证或用户人工批准。仅用于历史描述性研究，未发布，不提供已验证目标价、交易建议或有效 Alpha。','Nine chapters and cross-chapter consistency reviewed by the assistant. Structurally complete, with market, peer and supply-chain evidence gaps. Not independent verification or human approval. Unpublished historical descriptive research only; no validated target price, trading advice or proven alpha.')+'</div><p>'+bi('复审时间 '+review['reviewedAt']+'。历史资料回溯重建，不是当时已发布的预测。','Reviewed '+review['reviewedAt']+'. Retrospective reconstruction, not a forecast published at the historical date.')+'</p></header>'
            parts.append('<section><h2>'+bi('整份报告核对记录','Whole-report audit')+'</h2><ul>'+''.join('<li>'+escape(k)+': '+escape(v)+'</li>' for k,v in audit['checks'].items())+'</ul><p class="muted">'+bi('审核记录保留原语言；正文和证据摘要可切换中英文。','Audit notes retain their original language; prose and claim summaries are bilingual.')+'</p></section>')
    url=meta.get('source_url','')
    if urlsplit(url).scheme=='https' and urlsplit(url).hostname:
        parts.append('<p><a target="_blank" rel="noopener noreferrer" href="'+escape(url,quote=True)+'">'+bi('查看原始申报文件','Open original filing')+'</a></p>')
    parts.append('<nav>'+''.join('<a href="#'+escape(d['chapter'])+'">'+bi(*LABELS[d['chapter']])+'</a>' for d in chapters)+'</nav>')
    readiness=[d['marketReadiness'] for d in chapters if d.get('marketReadiness')]
    if readiness:
        if any(r!=readiness[0] for r in readiness):raise ValueError('Conflicting market readiness')
        r=readiness[0]
        parts.append('<section><h2>'+bi('市场证据覆盖与可用边界','Market evidence coverage and limits')+'</h2><p class="notice">'+bi('估值仅为分析框架，因子尚未回测验证。章节齐全不等于历史数据库完整，也不等于可用于交易。以下是冻结资料内的观测范围，不代表连续交易日覆盖。','Valuation framework only; factors are untested. Chapter coverage is not database completeness or permission to trade. These ranges describe frozen observations, not verified trading-session coverage.')+'</p><div class="table-wrap"><table><thead><tr>'+''.join('<th>'+bi(*x)+'</th>' for x in [('数据','Series'),('开始','First'),('截止','Last'),('观测数','Count'),('距报告截至日／自然日','Calendar lag')])+'</tr></thead><tbody>')
        for s in r['series']:
            parts.append('<tr>'+''.join('<td>'+escape(str(v) if v is not None else '—')+'</td>' for v in [s['id'],s['firstDate'],s['lastDate'],s['count'],s['calendarLagDays']])+'</tr>')
        parts.append('</tbody></table></div><p>'+bi('尚待补证：行业基准、同口径含分红收益、交易日与复权校验、原始发布时间及数据版本、样本外回测。原始行情较新也不代表这些条件已经满足。','Still required: sector benchmark, matched total returns, trading-session and adjustment checks, original release timestamps/vintages and out-of-sample tests. Recent prices do not satisfy these requirements by themselves.')+'</p></section>')
    bridges=[d['cashBridge'] for d in chapters if d.get('cashBridge')]
    if bridges:
        if any(b!=bridges[0] for b in bridges):raise ValueError('Conflicting cash reconciliation')
        b=bridges[0]
        parts.append('<section><h2>'+bi('现金流与余额勾稽','Cash-flow reconciliation')+'</h2>')
        if b['state']=='matched':
            periods={'quarter':('单季','Quarter'),'nine_month_cumulative':('九个月累计','Nine-month cumulative')}
            parts.append('<p>'+bi(*periods.get(b['periodType'],(b['periodType'],b['periodType'])))+' · '+escape(b['periodStart'])+' — '+escape(b['periodEnd'])+' · '+bi('单位：百万美元','USD millions')+'</p><div class="table-wrap"><table><thead><tr><th>'+bi('项目','Item')+'</th><th>'+bi('原始数值','Source value')+'</th></tr></thead><tbody>')
            for key,zh,en in [('opening','期初现金口径余额','Opening cash-basis balance'),('operating','经营现金流','Operating cash flow'),('investing','投资现金流','Investing cash flow'),('financing','融资现金流','Financing cash flow'),('fx','汇率影响','Currency effect'),('netChange','现金净变动','Net change'),('closing','期末现金口径余额','Closing cash-basis balance')]:
                if key not in b['values']:continue
                v=b['values'][key];value=format(Decimal(v['value'])/Decimal(1000000),',.3f').rstrip('0').rstrip('.')
                parts.append('<tr><td>'+bi(zh,en)+'</td><td>'+value+'<details><summary>'+bi('数据引用','Evidence IDs')+'</summary><code>'+escape(', '.join(v['evidence_refs']))+'</code></details></td></tr>')
            note=('恒等式核对通过，沿用原表现金及等价物口径；未单列汇率行不代表汇率影响为零。算术一致不等于盈利质量或偿债能力已经验证。','Arithmetic identity matched on the original cash-and-equivalents basis. No separate FX row does not mean zero FX impact. Reconciliation does not establish earnings quality or solvency.') if b.get('source')=='reviewed_original_html_table' else ('恒等式核对通过。口径包含现金、等价物及对应限制性现金项目；算术一致不等于盈利质量或偿债能力已经验证。','Arithmetic identity matched on the statement cash basis, including corresponding restricted-cash items. Reconciliation does not establish earnings quality or solvency.')
            parts.append('</tbody></table></div><p class="muted">'+bi(*note)+'</p>')
        else:parts.append('<p class="notice">'+escape(b['state']+': '+b.get('reason','Reconciliation mismatch'))+'</p>')
        parts.append('</section>')
    if dossier is not None and dossier.get('cashSourceEvidence'):
        from app.dossier_cash_attachment import render_cash_source
        parts.append(render_cash_source(dossier['cashSourceEvidence']))
    for d in chapters:
        parts.append('<section id="'+escape(d['chapter'])+'"><p class="eyebrow">'+bi('本地模型草稿 · 助手复审修订','Local-model draft · Assistant-revised')+'</p><h2>'+bi(*LABELS[d['chapter']])+'</h2>')
        for k in ('analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'):
            pair=d['section'][k];parts.append('<article><h3>'+bi(*LABELS[k])+'</h3><p>'+bi(pair['zh'],pair['en'])+'</p></article>')
        parts.append('<details><summary>'+bi('原文证据与审核事实','Original evidence and reviewed claims')+'</summary>')
        for c in d['section']['grounded_claims']:
            parts.append('<div class="quote"><code>'+escape(c['passage_id'])+'</code><blockquote>'+escape(c['quote'])+'</blockquote><p>'+bi(c['statement']['zh'],c['statement']['en'])+'</p></div>')
        parts.append('</details><details><summary>'+bi('本次审核记录','Revision audit')+'</summary><ul>'+''.join('<li>'+escape(f)+'</li>' for f in d['review']['findings'])+'</ul><p class="muted">'+bi('审核操作记录保留原语言，正文可切换中英文。','Operational review notes retain their original language; chapter prose is bilingual.')+'</p><code>parent: '+escape(d['review']['parentSha256'])+'<br>review: '+escape(d['review']['reviewSha256'])+'</code></details></section>')
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ORAKT '''+title+''' — reviewed chapters</title><style>
*{box-sizing:border-box}body{margin:0;background:#101921;color:#edf2f5;font:16px/1.8 system-ui,-apple-system,"Segoe UI",sans-serif}main{max-width:1080px;margin:auto;padding:24px}h1{font-size:clamp(28px,5vw,44px);line-height:1.2}h2{font-size:25px}h3{font-size:18px;color:#94e4c2}p{overflow-wrap:anywhere}section{padding:28px 0;border-top:1px solid #334652;scroll-margin-top:65px}.eyebrow{letter-spacing:.12em;color:#89bcae;font-size:12px}.notice{background:#26313e;border-left:3px solid #d9b85c;padding:16px}.muted{color:#a7b9c5;font-size:14px}nav{display:flex;gap:12px;flex-wrap:wrap;padding:20px 0}a{color:#a4eac8}nav a{padding:8px 14px;background:#233b3a;border-radius:6px}details{margin:12px 0;border:1px solid #344652;padding:10px 14px;border-radius:6px}summary{cursor:pointer;color:#abdccf}blockquote{white-space:pre-wrap;margin:12px 0;padding-left:16px;border-left:2px solid #52697b;color:#c7d1da}code{overflow-wrap:anywhere;font-size:12px;color:#9db7cc}.quote{padding:14px 0;border-bottom:1px solid #344652}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse}td,th{text-align:left;border-bottom:1px solid #344652;padding:10px}td:last-child{text-align:right;font-variant-numeric:tabular-nums}td details{text-align:left}.language{position:sticky;top:0;background:#101921ee;padding:10px 24px;z-index:1;border-bottom:1px solid #334652}.language label{display:inline-block;padding:6px 16px;border:1px solid #52697b;cursor:pointer;margin-right:8px;border-radius:5px}.lang-input{position:absolute;clip-path:inset(50%);width:1px;height:1px}#zh:checked~main .en,#en:checked~main .zh{display:none}#zh:checked~.language label[for=zh],#en:checked~.language label[for=en]{background:#a4eac8;color:#112520}#zh:focus-visible~.language label[for=zh],#en:focus-visible~.language label[for=en]{outline:3px solid white}@media(max-width:600px){main{padding:18px}body{font-size:16px}section{padding:20px 0}td,th{padding:8px}nav a{flex:1;text-align:center}}
</style><body><input class="lang-input" type="radio" name="lang" id="zh" checked aria-label="中文"><input class="lang-input" type="radio" name="lang" id="en" aria-label="English"><div class="language"><label for="zh">中文</label><label for="en">English</label></div><main>'''+''.join(parts)+'''<footer class="muted">ORAKT · Offline review artifact · No live prices or automatic trading</footer></main></body></html>'''


def run(paths,output):
    if output.exists():raise ValueError('Preserve existing readable artifact')
    chapters=[json.loads(p.read_text(encoding='utf-8')) for p in paths]
    html=render(chapters);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(html,encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--chapters',nargs='+',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.chapters,a.output)
