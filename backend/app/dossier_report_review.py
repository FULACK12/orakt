"""Record an explicit whole-report assistant audit, never trading approval."""
import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

from app.company_history_dossier import write_json
from app.dossier_consolidation import validate_chapters
from app.dossier_readable_bundle import render
from app.review_frozen_dossier import load_frozen_packet

CHECKS = {'periods_and_values', 'cross_chapter_consistency', 'bilingual_scope',
          'source_and_claims', 'gaps_and_eligibility'}
STATE = 'assistant_reviewed_research_only'


def finalize(parent: Path, review_path: Path, cold_root: Path, output: Path):
    if output.exists():
        raise ValueError('Preserve existing report revision')
    raw = (parent / 'dossier.json').read_bytes()
    dossier = json.loads(raw)
    manifest = json.loads((parent / 'manifest.json').read_text(encoding='utf-8'))
    digest = hashlib.sha256(raw).hexdigest()
    if digest != manifest['dossierSha256'] or hashlib.sha256((parent / 'readable.html').read_bytes()).hexdigest() != manifest['readableSha256']:
        raise ValueError('Parent artifact changed')
    review_raw = review_path.read_bytes()
    review = json.loads(review_raw)
    if (review.get('reviewer') != 'codex_assistant' or review.get('state') != STATE
            or review.get('parentSha256') != digest
            or review.get('sourceFingerprint') != dossier['sourceFingerprint']):
        raise ValueError('Explicit matching report review required')
    checks = review.get('checks', {})
    if set(checks) != CHECKS or any(not isinstance(v, str) or len(v.strip()) < 30 for v in checks.values()):
        raise ValueError('Substantive whole-report checks required')
    if (dossier['review']['state'] != 'whole_report_review_pending'
            or dossier.get('structureComplete') is not True
            or any(dossier.get(k) is not False for k in ('published', 'eligibleForPredictiveBacktest', 'validatedAlpha'))):
        raise ValueError('Only unpublished, non-predictive pending research allowed')
    original, source_raw = load_frozen_packet(parent / 'source.json', cold_root)
    packet = original['packet']
    if (original['fingerprint'] != dossier['sourceFingerprint']
            or hashlib.sha256(source_raw).hexdigest() != dossier['sourcePacketSha256']
            or any(dossier[k] != packet[v] for k, v in
                   [('ticker', 'ticker'), ('accession', 'accession'), ('asOf', 'as_of_date'),
                    ('periodEnd', 'period_end'), ('facts', 'facts'), ('financialLedger', 'financial_ledger')])):
        raise ValueError('Report differs from frozen evidence')
    chapters = validate_chapters(original, dossier['chapters'])
    if dossier.get('cashSourceEvidence')!=packet.get('verified_cash_source'):
        raise ValueError('Cash source evidence differs from frozen attachment')
    result = deepcopy(dossier)
    result['chapters'] = chapters
    result['review'] = {'state': STATE, 'reviewer': 'codex_assistant',
                        'reviewedAt': datetime.now(UTC).isoformat(), 'chapterReviews': 9,
                        'humanAccepted': False, 'independentVerification': False,
                        'scope': 'Historical descriptive research with explicit evidence gaps; not investment or backtest approval.',
                        'parentSha256': digest,
                        'reviewSha256': hashlib.sha256(review_raw).hexdigest()}
    result['wholeReportAudit'] = review
    write_json(output / 'source.json', original)
    write_json(output / 'dossier.json', result)
    (output / 'readable.html').write_text(render(chapters, result), encoding='utf-8')
    write_json(output / 'manifest.json', {'ticker': result['ticker'], 'accession': result['accession'],
        'state': STATE, 'published': False, 'parent': str(parent), 'parentSha256': digest,
        'dossierSha256': hashlib.sha256((output / 'dossier.json').read_bytes()).hexdigest(),
        'readableSha256': hashlib.sha256((output / 'readable.html').read_bytes()).hexdigest()})
    return result


def register(root: Path, output: Path):
    """Advance only the exact pending parent; do not label research as published."""
    from app.company_completion import connect, now
    raw=(output/'dossier.json').read_bytes();d=json.loads(raw)
    manifest=json.loads((output/'manifest.json').read_text(encoding='utf-8'))
    digest=hashlib.sha256(raw).hexdigest()
    if (digest!=manifest['dossierSha256'] or d['review']['state']!=STATE
            or hashlib.sha256((output/'readable.html').read_bytes()).hexdigest()!=manifest['readableSha256']
            or any(d.get(k) is not False for k in ('published','eligibleForPredictiveBacktest','validatedAlpha'))):
        raise ValueError('Intact unpublished research review required')
    with connect(root) as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute("SELECT * FROM jobs WHERE kind='reports' AND key=?",(d['accession'],)).fetchone()
        if not old or old['ticker']!=d['ticker']:raise ValueError('Missing or mismatched report job')
        prior=json.loads(old['detail'])
        if old['state']==STATE and prior.get('dossierSha256')==digest:return False
        if old['state']!='assembled_review_pending' or prior.get('dossierSha256')!=d['review']['parentSha256']:
            raise ValueError('Pending parent changed; do not overwrite queue')
        db.execute('CREATE TABLE IF NOT EXISTS report_transitions(id INTEGER PRIMARY KEY, accession TEXT, ticker TEXT, old_state TEXT, old_detail TEXT, new_state TEXT, artifact_hash TEXT, changed_at TEXT)')
        db.execute('INSERT INTO report_transitions(accession,ticker,old_state,old_detail,new_state,artifact_hash,changed_at) VALUES(?,?,?,?,?,?,?)',
            (d['accession'],d['ticker'],old['state'],old['detail'],STATE,digest,now()))
        detail={'output':str(output),'dossierSha256':digest,'published':False,'wholeReportReview':STATE,
                'structureComplete':True,'dataCoverage':'partial_with_explicit_gaps','humanAccepted':False,
                'eligibleForPredictiveBacktest':False}
        db.execute("UPDATE jobs SET state=?,detail=?,updated_at=? WHERE kind='reports' AND key=?",
                   (STATE,json.dumps(detail,ensure_ascii=False),now(),d['accession']))
    return True
