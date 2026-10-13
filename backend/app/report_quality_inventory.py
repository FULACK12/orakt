"""Read-only mining of retained drafts/reviews. Outputs a new audit directory.

Counts are audit-record category mentions, not a measured error rate. Pairing
uses hashes, never filenames alone. The holdout candidates are NOT new evidence
of generalisation: these historical reviews have already influenced prompts.
"""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from app.report_quality import FIELDS, RULESET, REF, passages, rules_digest
from app.report_quality_evaluation import split, evaluate
from app.report_usage import collect_usage, digest, save

TAXONOMY = {
    'period_scope': {'pattern': r'quarter|cumulative|fiscal|period|期间|季度|半年|财年', 'route': 'parsing_and_retrieval', 'fix': '绑定每项陈述自己的期间、单季/累计/时点，不以报告年份替代摘录年份。'},
    'accounting_calculation': {'pattern': r'cash|margin|debt|EPS|income|ratio|现金|毛利|债务|利润|勾稽', 'route': 'calculation_and_fact_binding', 'fix': '使用同口径事实表和确定性计算；区分毛利金额/比例、利润/现金、授权/执行、现金/非现金。'},
    'disclosure_retrieval': {'pattern': r'missing|undisclosed|disclosed|mask|hidden|缺失|未披露|遮蔽', 'route': 'retrieval', 'fix': '先核对完整原文与事实表；摘录未包含不等于公司未披露。'},
    'causal_overclaim': {'pattern': r'causal|cause|proof|prove|guarantee|risk|alpha|因果|保证|风险|证明', 'route': 'writing_and_semantic_review', 'fix': '区分披露事实、管理层归因、条件机制和已验证结论，检查替代解释。'},
    'policy_transition': {'pattern': r'policy|adopt|recognition|restat|准则|政策|追溯|确认', 'route': 'retrieval_and_semantic_review', 'fix': '区分现行政策、政策变化、尚未实施准则，保留采用与生效日期方向。'},
    'units_currency_translation': {'pattern': r'unit|billion|million|currency|translation|单位|币种|亿|百万|汇率|翻译', 'route': 'parsing_and_bilingual_review', 'fix': '绑定原始单位/币种/倍率，逐项检查中英文数量级，销售额不等于销量。'},
    'entity_scope': {'pattern': r'segment|company|issuer|subsidiary|公司|分部|主体|地区', 'route': 'parsing_and_retrieval', 'fix': '绑定公司、分部和地区；不可把单一分部的归因移植到全公司。'},
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def mine(cold, output, site=None):
    if output.exists():
        raise ValueError('Preserve previous inventory; choose a new output directory')
    roots = sorted(cold.glob('leader-*'))
    parents, sources, reviewed, forms = {}, {}, [], {}
    for root in roots:
        if not root.is_dir():
            continue
        if (root/'plan.json').exists():
            for item in read(root/'plan.json').get('items', []):
                if item.get('form'):
                    forms[(item.get('ticker'), item.get('accession'))] = item['form']
        for path in root.rglob('*.json'):
            if path.name in ('chapter.json', 'unreviewed-bound-attempt.json'):
                parents[hashlib.sha256(path.read_bytes()).hexdigest()] = path
            elif path.name == 'source.json':
                d = read(path)
                if 'packet' in d and 'fingerprint' in d:
                    sources[d['fingerprint']] = path
            elif path.name == 'reviewed-chapter.json':
                reviewed.append(path)
    records, counts, seen, omitted = [], Counter(), set(), Counter()
    for path in reviewed:
        d = read(path); review = d.get('reviewDocument', {})
        identity = (review.get('parentSha256'), d.get('review', {}).get('reviewSha256'))
        if identity in seen:
            continue
        seen.add(identity)
        parent = parents.get(review.get('parentSha256'))
        source = sources.get(d.get('sourceFingerprint'))
        if not parent or not source:
            omitted['missing_parent_or_frozen_source'] += 1; continue
        before, original = read(parent), read(source)
        ps = passages(original['packet'])
        finding_text = '\n'.join(str(x) for x in review.get('findings', []))
        categories = [k for k, v in TAXONOMY.items() if re.search(v['pattern'], finding_text, re.I)]
        counts.update(categories)
        changes = []
        for field in FIELDS:
            old, new = before['section'].get(field), d['section'].get(field)
            if old != new:
                ids = sorted(set(REF.findall(json.dumps([old, new], ensure_ascii=False))))
                changes.append({'location': 'section/' + field, 'errorVersion': old,
                                'correctedVersion': new, 'originalEvidence': [ps[i] for i in ids if i in ps],
                                'pairMeaning': 'Full changed paragraph, may include correct unchanged statements; not every sentence was erroneous.'})
        old_claims = {c['passage_id']: c for c in before['section'].get('grounded_claims', [])}
        for c in d['section'].get('grounded_claims', []):
            old = old_claims.get(c['passage_id'])
            if old and old['statement'] != c['statement']:
                changes.append({'location': 'grounded_claims/' + c['passage_id'],
                                'errorVersion': old['statement'], 'correctedVersion': c['statement'],
                                'originalEvidence': [ps[c['passage_id']]] if c['passage_id'] in ps else []})
        records.append({'id': digest(identity), 'ticker': d['ticker'], 'chapter': d['chapter'],
                        'accession': original['packet']['accession'], 'categories': categories,
                        'classification': 'keyword-assisted candidate; not independently adjudicated error taxonomy',
                        'findings': review.get('findings', []), 'changes': changes,
                        'parentPath': str(parent), 'parentSha256': identity[0],
                        'correctedPath': str(path), 'correctedSha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'sourcePath': str(source), 'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                        'sourceUrl': original['packet'].get('source_url'),
                        'rawSha256': original['packet'].get('raw_sha256')})
    # Store one record per chapter, not a giant repeated full-corpus context.
    for r in records:
        save(output / 'errors' / (r['id'] + '.json'), r)
    summary = {'ruleset': RULESET, 'reviewRecords': len(records), 'omitted': dict(omitted),
               'countingUnit': 'Distinct hash-bound reviewed chapter mentioning category; categories overlap. Not error incidence or root-cause proof.',
               'categoryMentions': dict(counts.most_common()), 'taxonomy': TAXONOMY,
               'records': [{k: r[k] for k in ('id', 'ticker', 'accession', 'chapter', 'categories')} for r in records]}
    save(output / 'error-catalog.json', summary)
    usage = []
    for root in roots:
        for report_dir in sorted((root / 'drafts').glob('*/*')):
            if not report_dir.is_dir():
                continue
            row = collect_usage(report_dir)
            if not row['callCount']:
                continue
            row.update(ticker=report_dir.parent.name, accession=report_dir.name, queue=str(root))
            save(output / 'usage' / (digest(str(report_dir)) + '.json'), row)
            usage.append({k: v for k, v in row.items() if k != 'calls'})
    save(output / 'usage-index.json', {'reportsOrQueueRevisions': usage,
        'note': 'A report can span multiple queue revisions; group ticker+accession when totaling. Review/Codex data remain unknown.'})
    reports = {}
    for r in records:
        packet = read(Path(r['sourcePath']))['packet']
        identity = r['ticker'] + '/' + r['accession']
        historical = packet['period_end'] < '2020-01-01'
        form = packet.get('form') or forms.get((r['ticker'], r['accession']))
        kind = 'annual' if form in ('10-K','20-F','40-F') else 'quarter' if form in ('10-Q','6-K') else 'unknown'
        reports[identity] = {'id': identity, 'groupId': r['ticker'],
            'split': 'development', 'proposedGroupSplit': split(r['ticker']),
            'stratum': 'us_' + kind + ('_historical' if historical else '_recent'), 'form':form,
            'labelStatus': 'existing_review_used_for_tuning', 'usedForTuning': True, 'synthetic': False,
            'sourcePath': r['sourcePath'], 'sourceSha256': r['sourceSha256']}
    manifest = {'ruleset': RULESET, 'rulesetSha256': rules_digest(),
                'rulesFrozenBeforeHoldout': False, 'cases': list(reports.values()),
                'requiredNewHoldout': 'Previously reviewed reports influenced prompts and must remain development. Acquire independently labeled unseen issuer groups across all required strata before enablement.'}
    save(output / 'evaluation-manifest.json', manifest)
    save(output / 'evaluation-status.json', evaluate(manifest, []))
    if site:
        published = []
        for item in read(site/'snapshot/research-report-index.json')['reports']:
            detail = site/'private-data/company-dossiers'/f"{item['id']}.json"
            accession = None
            if detail.exists():
                accession = next((s['id'][4:] for s in read(detail).get('sources', []) if s['id'].startswith('SEC:')), None)
            matched = [u for u in usage if accession and u['accession']==accession and u['ticker']==item.get('ticker')]
            published.append({'reportId':item['id'],'ticker':item.get('ticker'),'accession':accession,
                'inputTokensKnown':sum(u['inputTokensKnown'] for u in matched) if matched else None,
                'outputTokensKnown':sum(u['outputTokensKnown'] for u in matched) if matched else None,
                'modelSecondsKnown':sum(u['modelSecondsKnown'] for u in matched) if matched else None,
                'codexTokens':None,'reviewWallSeconds':None,'publicationWallSeconds':None,
                'coverage':'partial_retained_local_calls' if matched else 'historical_counters_unavailable',
                'queueRevisions':[u['queue'] for u in matched]})
        save(output/'published-report-usage.json',{'reports':published,
            'note':'Unknown values are null. These are partial historical measurements, not invoice totals. Distinct report versions may share generation calls; do not sum rows as separate spend.'})
    return {'reviewRecords': len(records), 'categories': dict(counts.most_common()),
            'usageGroups': len(usage), 'developmentReports': len(reports), 'automaticApprovalEnabled': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--cold', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--site', type=Path)
    a = p.parse_args()
    print(json.dumps(mine(a.cold, a.output, a.site), ensure_ascii=False))
