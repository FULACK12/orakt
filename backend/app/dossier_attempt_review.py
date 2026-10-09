"""Explicit assistant repair of retained model attempts, without GPU retries.

Source binding alone does not approve prose. The caller must supply substantive
bilingual corrections and findings; the normal reviewed-chapter checks still run.
"""
import hashlib
import json
from pathlib import Path
from sqlalchemy import text
from app.company_history_dossier import Section, write_json, validate_section
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.dossier_chapter_review import revise, apply_claim_corrections
from app.dossier_compact_writer import check_cash_evidence_use
from app.dossier_reviewed_synthesis import bind_narrative_context
from app.dossier_cash_bridge import packet_passages, guard_cash_narrative
from app.dossier_passages import check_claims
from app.dossier_semantic_guards import guard_known_semantics
from app.dossier_accounting_checks import disclosed_reference_terms
from app.review_frozen_dossier import load_frozen_packet
from app.leader_report_batch import now


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review_attempt(source, attempt, key, audit, output):
    if output.exists():
        raise ValueError('Preserve previous content review')
    if audit.get('reviewer') != 'codex_assistant' or not audit.get('findings'):
        raise ValueError('Explicit substantive assistant review required')
    fields={'analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'}
    if set(audit.get('corrections',{})) != fields:
        raise ValueError('Raw attempt repair requires explicit replacement of all narrative fields')
    original, _ = load_frozen_packet(source, get_settings().cold_data_root)
    packet = original['packet']
    raw = json.loads(attempt.read_text(encoding='utf-8'))
    if raw.get('done') is not True or raw.get('done_reason') == 'length':
        raise ValueError('Incomplete raw response requires separate recovery')
    view_path = attempt.parent/'writer-view.json'
    view = json.loads(view_path.read_text(encoding='utf-8'))
    if view['company'] != packet['ticker'] or view['chapter'] != key:
        raise ValueError('Attempt company/chapter mismatch')
    body = json.loads(raw['message']['content'])
    allowed = {p['id'] for p in view['passages']}
    originals = {p['id']:p for p in packet['chapter_passages'][key]}
    if not allowed <= originals.keys():
        raise ValueError('Attempt evidence outside frozen chapter')
    narrative, contexts = bind_narrative_context({k:v for k,v in body.items() if k!='claims'}, allowed, unreviewed_archive=True)
    claims = []
    for c in body['claims']:
        if c['passage_id'] not in allowed:
            raise ValueError('Unknown raw claim source')
        claims.append({**c, 'quote': originals[c['passage_id']]['text']})
    section = Section.model_validate({**narrative, 'grounded_claims':claims,
        'evidence_refs':[packet['filing_ref'], *sorted(allowed)], 'comparison_checks':[]})
    parent = output/'unreviewed-bound-attempt.json'
    draft = {'ticker':packet['ticker'], 'chapter':key, 'sourceFingerprint':original['fingerprint'],
        'sourcePacketSha256':sha(source), 'section':section.model_dump(), 'evidenceContext':contexts,
        'state':'failed_model_attempt_pending_explicit_review', 'published':False, 'completeDossier':False,
        'authorship':{'narrative':'local_model_unvalidated','groundedClaims':'local_model_unvalidated'},
        'retainedModelAttempt':{'path':str(attempt), 'sha256':sha(attempt),
            'writerViewPath':str(view_path), 'writerViewSha256':sha(view_path), 'model':raw.get('model')}}
    write_json(parent, draft)
    audit = {**audit, 'state':'accepted_with_revisions', 'parentSha256':sha(parent)}
    review = output/'explicit-review.json'
    write_json(review, audit)
    target = output/'reviewed-chapter.json'
    revise(parent, review, source, target)
    d = json.loads(target.read_text(encoding='utf-8'))
    d.update(reviewParentPath=str(parent), reviewDocumentPath=str(review))
    write_json(target,d)
    validate_checkpoint(source,target,key)
    return target


def validate_checkpoint(source, chapter, key):
    original, _ = load_frozen_packet(source,get_settings().cold_data_root)
    packet=original['packet'];d=json.loads(chapter.read_text(encoding='utf-8'))
    if (d['state']!='assistant_reviewed' or d['published'] is not False
        or d['ticker']!=packet['ticker'] or d['chapter']!=key
        or d['sourceFingerprint']!=original['fingerprint'] or d['sourcePacketSha256']!=sha(source)):
        raise ValueError('Reviewed checkpoint identity mismatch')
    parent_path=Path(d['reviewParentPath']);audit_path=Path(d['reviewDocumentPath'])
    if sha(parent_path)!=d['review']['parentSha256'] or sha(audit_path)!=d['review']['reviewSha256']:
        raise ValueError('Reviewed checkpoint provenance changed')
    parent=json.loads(parent_path.read_text(encoding='utf-8'))
    retained=parent['retainedModelAttempt']
    if sha(Path(retained['path']))!=retained['sha256'] or sha(Path(retained['writerViewPath']))!=retained['writerViewSha256']:
        raise ValueError('Retained model attempt changed')
    audit=json.loads(audit_path.read_text(encoding='utf-8'))
    if audit!=d['reviewDocument'] or audit['reviewer']!='codex_assistant' or not audit['findings']:
        raise ValueError('Review must remain explicit and intact')
    expected=apply_claim_corrections(parent['section'],audit.get('claimCorrections',{}))
    expected.update(audit['corrections'])
    s=Section.model_validate(d['section'])
    if s.model_dump()!=Section.model_validate(expected).model_dump():
        raise ValueError('Reviewed text differs from explicit corrections')
    ps=list(packet_passages(packet).values())
    validate_section(s,{packet['filing_ref'],*(p['id'] for p in ps)},packet['financial_ledger'],technical_terms=disclosed_reference_terms(packet))
    check_claims(s.grounded_claims,ps,required=True)
    guard_known_semantics(s,packet);check_cash_evidence_use(s,packet,key)
    if key in {'financial','capital'}:guard_cash_narrative(s,packet)
    return d


def register_checkpoint(root, accession, chapter):
    with get_session_factory()().get_bind().connect() as lock:
        if not lock.scalar(text('SELECT pg_try_advisory_lock(624730015831)')):
            raise RuntimeError('Report worker is still running')
        try:
            plan=json.loads((root/'plan.json').read_text(encoding='utf-8'))
            item=next(i for i in plan['items'] if i['accession']==accession)
            source=Path(item['sourcePath'])
            if sha(source)!=item['sourceSha256']:raise ValueError('Frozen queue source changed')
            doc=json.loads(chapter.read_text(encoding='utf-8'));key=doc['chapter']
            validate_checkpoint(source,chapter,key)
            state_path=root/'generation-progress.json'
            state=json.loads(state_path.read_text(encoding='utf-8'));job=state['jobs'][accession]
            if key in job['chapters']:raise ValueError('Existing checkpoint must not be replaced')
            job.setdefault('interventions',[]).append({'chapter':key,'reason':'Explicit source-grounded assistant revision',
                'previousError':job.get('error'),'reviewedPath':str(chapter),'at':now()})
            job['chapters'][key]={'path':str(chapter),'sha256':sha(chapter)}
            job.update(state='checkpoint_assistant_revised',failures=0,error=None)
            state.update(stage='checkpoint_assistant_revised',checkedAt=now(),activeChapter=None)
            write_json(state_path,state)
            from app.leader_history_batch import readable_status
            readable_status(root,state)
        finally:
            lock.execute(text('SELECT pg_advisory_unlock(624730015831)'))
