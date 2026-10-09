"""Latest-period leader priority queue. Plans and drafts never imply publication.

Freeze the existing curated US/A-share catalog rather than treating every SEC
issuer as a leader. Never substitute an older filing for a missing latest one.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import re
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import select

from app.company_completion import REPORT_FORMS, check_pause, filing_target
from app.company_history_dossier import CHAPTERS, VERSION, enrich_inline, enrich_market, write_json
from app.core.config import get_settings
from app.db.models import CompanyFiling, Document, Source
from app.db.session import get_session_factory
from app.dossier_backfill_pilot import ready_packet
from app.dossier_passages import add_passages
from app.financial_period_ledger import build_ledger
from app.historical_earnings_report import build_packet

PRIORITY = ('AAPL', 'NVDA', 'MSFT', 'AMZN', 'GOOGL', 'META', 'AMD', 'AVGO', 'MU', 'TSLA', 'LULU')


def now():
    return datetime.now(UTC).isoformat()


def leaders(catalog):
    result = []; seen = set()
    for company in catalog['companies']:
        market, ticker = company['marketRegion'], company['ticker']
        if market not in {'us', 'china'}:
            raise ValueError('Unsupported catalog market')
        identity = (market, ticker)
        if identity in seen:
            raise ValueError('Duplicate catalog company')
        seen.add(identity)
        result.append({k: company.get(k) for k in ('marketRegion', 'ticker', 'companyName', 'sector', 'industry')})
    return sorted(result, key=lambda c: (PRIORITY.index(c['ticker']) if c['ticker'] in PRIORITY else len(PRIORITY), c['marketRegion'], c['ticker']))


def latest_filing(rows, cutoff):
    eligible = [f for f in rows if f.form in REPORT_FORMS and f.report_date and f.filed_at <= cutoff and f.report_date <= cutoff]
    # An amendment of an older year is not the most recent reporting period.
    return max(eligible, key=lambda f: (f.report_date, f.filed_at, f.accession_number), default=None)


def summarize(items):
    return {'totalCompanies': len(items), 'byMarket': dict(Counter(c['marketRegion'] for c in items)),
            'byState': dict(Counter(c['state'] for c in items)),
            'completeReviewedReports': sum(c['state'] in {'assistant_reviewed','published_reviewed'} for c in items),
            'publishedReports': sum(c['state'] == 'published_reviewed' for c in items)}


def register_review(plan_path, folder):
    from app.review_frozen_dossier import load_frozen_packet
    from app.dossier_consolidation import validate_chapters
    raw=(folder/'dossier.json').read_bytes();d=json.loads(raw)
    receipt=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    original,_=load_frozen_packet(folder/'source.json',get_settings().cold_data_root)
    if (hashlib.sha256(raw).hexdigest()!=receipt['dossierSha256'] or d['review']['state']!='assistant_reviewed_research_only'
        or d['sourceFingerprint']!=original['fingerprint']):raise ValueError('Intact reviewed dossier required')
    validate_chapters(original,d['chapters'])
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    item=next(c for c in plan['items'] if c['ticker']==d['ticker'] and c.get('accession')==d['accession'])
    item.update(state='assistant_reviewed',reviewedPath=str(folder),reviewedDossierSha256=receipt['dossierSha256'],published=False)
    plan.update(summary=summarize(plan['items']),checkedAt=now())
    write_json(plan_path,plan)
    return plan['summary']


def cn_period(title):
    """Only explicit statutory report titles, never publication-year guessing."""
    if re.search(r'摘要|取消|审计报告|英文|提示性|更正公告|董事|监事',title):return None
    m=re.search(r'(20\d{2})\s*年?(?:度)?\s*(半年度|年度|第一季度|一季度|第三季度|三季度)报告',title)
    if not m:return None
    suffix={'年度':'12-31','半年度':'06-30','第一季度':'03-31','一季度':'03-31','第三季度':'09-30','三季度':'09-30'}[m[2]]
    return date.fromisoformat(m[1]+'-'+suffix)


def cn_preflight(session, item, cutoff, output):
    from app.a_share_disclosures import CNINFO_SOURCE_NAME
    from app.storage.archive import ColdArchive, ArchiveReadError
    from app.disclosure_evidence import extract_structured_disclosure_evidence
    sid=session.scalar(select(Source.id).where(Source.name==CNINFO_SOURCE_NAME))
    if sid is None:
        item.update(state='waiting_cn_source',reason='CNINFO source missing');return
    rows=session.scalars(select(Document).where(Document.source_id==sid,
        Document.raw_metadata['ticker'].as_string()==item['ticker'],
        Document.published_at < datetime.combine(cutoff,datetime.max.time(),tzinfo=UTC))).all()
    eligible=[(cn_period(d.title),d) for d in rows]
    eligible=[(end,d) for end,d in eligible if end and end<=cutoff]
    if not eligible:
        item.update(state='waiting_cn_source',reason='No full dated statutory periodic report in retained CNINFO documents');return
    end,d=max(eligible,key=lambda x:(x[0],x[1].published_at,x[1].id))
    item.update(periodEnd=str(end),filedAt=str(d.published_at.date()),sourceUrl=d.url,documentId=d.id)
    archive=ColdArchive(get_settings().cold_data_root,min_free_bytes=30*1024**3,max_used_percent=95)
    try:
        entry=archive.load_entry(d.raw_object_path,expected_content_hash=d.content_hash)
        if entry['url']!=d.url or entry['metadata'].get('ticker')!=item['ticker']:
            raise ValueError('CN archive identity mismatch')
        body=entry['body']
        if len(body)<5000:raise ValueError('Insufficient full periodic text')
        pdf=(archive.root/entry['metadata']['pdf_archive_path']).resolve()
        if not pdf.is_relative_to(archive.root.resolve()) or not pdf.is_file():raise ValueError('Original PDF missing')
        evidence=extract_structured_disclosure_evidence(body,title=d.title,published_at=d.published_at)
        target=output/'cn-source-review'/item['ticker']/'source-review.json'
        write_json(target,{'ticker':item['ticker'],'periodEnd':str(end),'filedAt':str(d.published_at.date()),
            'sourceUrl':d.url,'documentId':d.id,'title':d.title,'coldObjectPath':d.raw_object_path,
            'pdfSha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'textSha256':hashlib.sha256(body.encode()).hexdigest(),
            'fullTextCharacters':len(body),'evidence':evidence,'state':'table_reconciliation_required','published':False,
            'warning':'PDF numeric candidates are NOT normalized financial facts; map table column, unit, quarter/YTD and consolidated/parent scope before writing full financial analysis.'})
        item.update(state='waiting_cn_table_review',sourceReviewPath=str(target),financialCandidates=len(evidence['financial_metrics']),fullTextCharacters=len(body),
            reason='Original full report verified and extracted; financial table columns/units/periods require normalization before nine-chapter generation')
    except (ValueError,OSError,KeyError,TypeError,ArchiveReadError) as exc:
        item.update(state='waiting_cn_source',reason=str(exc)[:400])


def plan(catalog_path, output, cutoff, *, resume=False):
    if cutoff > date.today():
        raise ValueError('Future cutoff forbidden')
    if output.exists() and not resume:
        raise ValueError('Preserve existing batch; choose a new revision')
    raw = catalog_path.read_bytes(); catalog = json.loads(raw)
    items = leaders(catalog); settings = get_settings()
    manifest = {'version': 'leader-latest-full/v1', 'createdAt': now(), 'cutoff': str(cutoff),
                'catalogSha256': hashlib.sha256(raw).hexdigest(), 'catalogAsOf': catalog.get('generatedAt'),
                'selection': 'Existing curated leader catalog; not a new current-market ranking',
                'template': 'company-periodic/v1', 'requiredChapters': [c[0] for c in CHAPTERS],
                'published': False, 'items': items}
    for item in items:
        item.update(state='source_preflight_pending', published=False)
    if resume:
        old = json.loads((output/'plan.json').read_text(encoding='utf-8'))
        # Publishing a report changes reportIds, not leader membership. Compare
        # the frozen company projection; still reject changed identities/ranks.
        frozen=[{k:c.get(k) for k in ('marketRegion','ticker','companyName','sector','industry')} for c in old['items']]
        if frozen != leaders(catalog) or old['cutoff'] != str(cutoff):
            raise ValueError('Cannot resume against changed catalog or cutoff')
        old['lastCatalogReadSha256']=manifest['catalogSha256']
        manifest = old; items = old['items']
    def save(stage):
        manifest.update(checkedAt=now(), stage=stage, summary=summarize(items))
        write_json(output/'plan.json', manifest)
    save('source_preflight')
    with get_session_factory()() as session:
        for item in items:
            if resume and item['state'] not in {'source_preflight_pending', 'waiting_archive_busy', 'waiting_evidence', 'waiting_form_adapter', 'waiting_cn_period_adapter'}:
                continue
            check_pause(output, 'leaders')
            if item['marketRegion'] == 'china':
                cn_preflight(session,item,cutoff,output)
                save('source_preflight'); continue
            rows = session.scalars(select(CompanyFiling).where(CompanyFiling.ticker == item['ticker'], CompanyFiling.form.in_(REPORT_FORMS))).all()
            filing = latest_filing(rows, cutoff)
            if filing is None:
                item.update(state='waiting_filing_index', reason='No dated periodic filing through cutoff')
                save('source_preflight'); continue
            item.update(accession=filing.accession_number, form=filing.form, periodEnd=str(filing.report_date), filedAt=str(filing.filed_at), sourceUrl=filing.source_url)
            try:
                if not filing_target(filing, settings.cold_data_root).is_file():
                    item.update(state='waiting_source', reason='Latest indexed primary document is not archived')
                    save('source_preflight'); continue
                packet = build_packet(session, ticker=item['ticker'], cold_root=settings.cold_data_root, accession=filing.accession_number)
                packet = enrich_inline(enrich_market(session, packet), settings.cold_data_root)
                packet = add_passages(packet, settings.cold_data_root)
                packet['financial_ledger'] = build_ledger(packet)
                readiness = ready_packet(packet)
                fingerprint = hashlib.sha256(json.dumps({'version': VERSION, 'packet': packet}, sort_keys=True).encode()).hexdigest()
                target = output/'packets'/item['ticker']/filing.accession_number/'source.json'
                write_json(target, {'version': VERSION, 'packet': packet, 'fingerprint': fingerprint})
                item.update(state='ready_for_generation', sourcePath=str(target), sourceSha256=hashlib.sha256(target.read_bytes()).hexdigest(), readiness=readiness)
            except (ValueError, OSError) as exc:
                item.update(state='waiting_evidence', reason=str(exc)[:500])
            except sqlite3.OperationalError as exc:
                if 'locked' not in str(exc).lower() and 'busy' not in str(exc).lower():
                    raise
                item.update(state='waiting_archive_busy', reason='Cold fact import currently locked; retry preflight without losing other company packets')
            save('source_preflight')
    save('plan_ready')
    return manifest


def execute(plan_path, output, limit=1):
    """One model slot, resumable across companies, no automatic retry or approval."""
    from app.dossier_compact_batch import batch
    from app.orakt_history_queue import resource_gate
    from sqlalchemy import text
    if not 1 <= limit <= 300:
        raise ValueError('Batch limit outside safety bound')
    raw = plan_path.read_bytes(); manifest = json.loads(raw); settings = get_settings()
    digest = hashlib.sha256(raw).hexdigest()
    state_path = output/'progress.json'
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {
        'version': 'leader-latest-full/v1', 'planSha256': digest, 'startedAt': now(), 'results': [], 'published': False}
    if state['planSha256'] != digest:
        raise ValueError('Batch plan changed; preserve old run')
    def save(stage, **values):
        state.update(stage=stage, checkedAt=now(), **values)
        write_json(state_path, state)
    with get_session_factory()() as session:
        locked = session.execute(text('SELECT pg_try_advisory_lock(624730015831)')).scalar()
        if not locked:
            raise RuntimeError('Leader worker already running')
        try:
            completed = {r['ticker'] for r in state['results']}
            count = 0
            for item in manifest['items']:
                if item['state'] != 'ready_for_generation' or item['ticker'] in completed:
                    continue
                check_pause(output, 'leaders')
                reason = resource_gate()
                if reason:
                    raise InterruptedError(reason)
                if count >= limit:
                    break
                source = Path(item['sourcePath'])
                if hashlib.sha256(source.read_bytes()).hexdigest() != item['sourceSha256']:
                    raise ValueError('Frozen company source changed')
                target = output/item['ticker']/item['accession']
                if target.exists():
                    # Interrupted drafts are retained for inspection, never silently rerun.
                    state['results'].append({'ticker': item['ticker'], 'state': 'interrupted_review_required', 'published': False})
                    continue
                count += 1; save('generating', activeTicker=item['ticker'], activePeriod=item['periodEnd'])
                result = batch(source, target, manifest['requiredChapters'], redact_numbers=True, reasoning=True)
                state['results'].append({'ticker': item['ticker'], 'periodEnd': item['periodEnd'], 'state': result['stage'],
                    'draftedChapters': len([d for d in result['drafts'] if d['stage'] == 'content_review_pending']), 'published': False})
                save('between_companies', activeTicker=None)
                # A systematic writer failure must be repaired before burning all-company compute.
                if result['stage'] != 'drafts_ready_for_review':
                    save('repair_required', activeTicker=None); return state
            save('review_pending', activeTicker=None)
        except BaseException as exc:
            save('safely_paused' if isinstance(exc, InterruptedError) else 'failed', activeTicker=None, error=str(exc)[:500])
            raise
        finally:
            session.execute(text('SELECT pg_advisory_unlock(624730015831)'))
    return state


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['plan', 'run', 'register-review'])
    p.add_argument('--catalog', type=Path)
    p.add_argument('--plan', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--cutoff', type=date.fromisoformat, default=date.today())
    p.add_argument('--limit', type=int, default=1)
    p.add_argument('--resume', action='store_true')
    a = p.parse_args()
    if a.action == 'plan':
        if not a.catalog: p.error('--catalog required')
        r = plan(a.catalog, a.output, a.cutoff, resume=a.resume)
        print(json.dumps(r['summary']))
    elif a.action=='register-review':
        if not a.plan:p.error('--plan required')
        print(json.dumps(register_review(a.plan,a.output)))
    else:
        if not a.plan: p.error('--plan required')
        r = execute(a.plan, a.output, a.limit)
        print(json.dumps(r, ensure_ascii=False))
