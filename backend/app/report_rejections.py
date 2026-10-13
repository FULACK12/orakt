"""Append-only rejected examples and bounded retries; never training approval."""
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from app.report_usage import digest

DEFAULT_POLICY = {'maxChapterRejections': 3, 'maxReportReviewRejections': 2}


def retain_rejected_draft(raw, view, original, key):
    """Bind a complete failed response for diagnostics only, never approval."""
    from app.dossier_reviewed_synthesis import bind_narrative_context
    if raw.get('done') is not True or raw.get('done_reason')=='length':
        raise ValueError('Incomplete output cannot be treated as a report chapter')
    body=json.loads(raw['message']['content'])
    allowed={p['id'] for p in view['passages']}
    packet=original['packet'];sources={p['id']:p for p in packet['chapter_passages'][key]}
    if not allowed <= sources.keys():raise ValueError('View outside frozen chapter evidence')
    narrative,contexts=bind_narrative_context({k:v for k,v in body.items() if k!='claims'},allowed,unreviewed_archive=True)
    claims=[]
    for c in body['claims']:
        if c['passage_id'] not in allowed:raise ValueError('Unknown original claim identity')
        claims.append({**c,'quote':sources[c['passage_id']]['text']})
    return {'ticker':packet['ticker'],'chapter':key,'sourceFingerprint':original['fingerprint'],
            'state':'rejected_local_draft_for_review','published':False,'evidenceContext':contexts,
            'generationResponse':{'done':raw['done'],'done_reason':raw.get('done_reason')},
            'section':{**narrative,'grounded_claims':claims,'evidence_refs':[packet['filing_ref'],*sorted(allowed)],'comparison_checks':[]}}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def events(root):
    return [json.loads(p.read_text(encoding='utf-8')) for p in sorted((Path(root)/'rejections').glob('*.json'))]


def guard(root, chapter=None, policy=None):
    policy = policy or DEFAULT_POLICY
    if any(not isinstance(v,int) or v<1 for v in policy.values()):
        raise ValueError('Positive rejection limits required')
    records = events(root)
    report_count = sum(e['phase']=='whole_report_review' for e in records)
    chapter_count = sum(e['chapter']==chapter and e['phase']!='whole_report_review' for e in records) if chapter else 0
    if report_count>=policy['maxReportReviewRejections'] or chapter_count>=policy['maxChapterRejections']:
        raise RuntimeError('Rejection limit reached; quarantine retained evidence, no automatic retry')
    return {'chapterRejections':chapter_count,'reportReviewRejections':report_count,'policy':policy}


def reject(root, *, source, candidate, chapter, phase, findings, policy=None, context_paths=()):
    if not findings or phase not in ('generation_validation','semantic_review','whole_report_review'):
        raise ValueError('A rejection requires findings and an explicit stage')
    source, candidate = Path(source), Path(candidate)
    original = json.loads(source.read_text(encoding='utf-8'))
    packet = original['packet']
    candidate_raw = candidate.read_bytes()
    record = {'version':'rejected-report-example/v1','at':datetime.now(UTC).isoformat(),
        'ticker':packet['ticker'],'accession':packet['accession'],'chapter':chapter,'phase':phase,
        'findings':findings,'candidatePath':str(candidate),'candidateSha256':sha(candidate),
        'sourcePath':str(source),'sourceSha256':sha(source),'sourceFingerprint':original['fingerprint'],
        'originalDocumentSha256':packet.get('raw_sha256'),'sourceUrl':packet.get('source_url'),
        'rejectedVersion':json.loads(candidate_raw),
        'originalEvidence':packet.get('chapter_passages',{}).get(chapter,[]) if chapter else packet.get('chapter_passages',{}),
        'contextFiles':[{'path':str(p),'sha256':sha(p)} for p in context_paths if Path(p).is_file()],
        'policy':policy or DEFAULT_POLICY,
        'trainingDisposition':'quarantined_candidate_only', 'trainingEligible':False,
        'requiredBeforeTraining':['source/license/privacy review','independent error labeling','verified corrected answer','deduplication and issuer/time split','explicit training authorization'],
        'correctedAnswer':None,'published':False}
    identity=digest([str(candidate.resolve()),record['candidateSha256'],phase,chapter])
    target=Path(root)/'rejections'/(identity+'.json')
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        existing=json.loads(target.read_text(encoding='utf-8'))
        if existing['findings']!=findings:
            raise ValueError('Existing rejection findings are immutable; retain a separate review revision')
        return existing
    with target.open('x',encoding='utf-8') as f:
        json.dump(record,f,ensure_ascii=False,indent=2)
    return record
