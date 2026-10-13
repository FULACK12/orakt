"""Company-first periodic history queue; local drafts and review are separate.

Uses retained originals only while the existing source collector runs. Unknown
market vintages are deliberately excluded. No publication or automatic approval.
"""
import argparse
import hashlib
import json
import subprocess
import shutil
import time
from collections import Counter
from datetime import date
from html import escape
from pathlib import Path

from sqlalchemy import select, text
from app.company_completion import REPORT_FORMS, check_pause, filing_target
from app.company_history_dossier import CHAPTERS, VERSION, Section, enrich_inline, write_json
from app.core.config import get_settings
from app.db.models import CompanyFiling, CompanyProfile
from app.db.session import get_session_factory
from app.dossier_backfill_pilot import ready_packet
from app.dossier_compact_writer import run as write_chapter, bind
from app.dossier_passages import add_passages
from app.financial_period_ledger import build_ledger
from app.historical_earnings_report import build_packet
from app.leader_report_batch import leaders, now
from app.orakt_history_queue import resource_gate
from app.review_frozen_dossier import load_frozen_packet


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def temporal_check(packet):
    if packet['period_end'] > packet['as_of_date']:
        raise ValueError('Period end after disclosure')
    for fact in packet['facts']:
        if not fact.get('filed_at') or fact['filed_at'] > packet['as_of_date'] or fact['period_end'] > packet['period_end']:
            raise ValueError('Missing or future fact timestamp')
    # Observation date alone does not establish availability of a revised series.
    if packet.get('market_evidence'):
        raise ValueError('Historical market vintages require separate review')


def reviewed_index(directory):
    found={}
    for path in directory.glob('*.json'):
        d=json.loads(path.read_text(encoding='utf-8'))
        if d.get('review',{}).get('state')!='assistant_reviewed_research_only' or len(d.get('chapters',[]))!=9:
            continue
        for source in d.get('sources',[]):
            if source.get('id','').startswith('SEC:'):
                found[(d['ticker'],source['id'][4:])]={'path':str(path),'sha256':sha(path),
                    'state':'existing_review_record','scope':'Previously reviewed artifact retained; not regenerated or newly certified.'}
    return found


def summarize(items):
    return {'filingVersions':len(items),'byState':dict(Counter(i['state'] for i in items)),
        'earliestDisclosure':min((i['filedAt'] for i in items),default=None),
        'latestDisclosure':max((i['filedAt'] for i in items),default=None),
        'reportsApprovedByThisQueue':0,'publishedByThisQueue':0}


def readable_status(root,state):
    rows=[]
    for accession,j in state.get('jobs',{}).items():
        report=root/'drafts'/j['ticker']/accession/'readable-draft.html'
        label=escape(j['state'])
        if j.get('reviewedReport'):
            label+=' · 整份复审已完成（发布状态另查）'
        if report.exists():label='<a href="'+escape(report.as_uri(),quote=True)+'">'+label+'</a>'
        rows.append('<tr><td>'+escape(j['ticker'])+'</td><td>'+escape(j['periodEnd'])+'</td><td>'+str(len(j['chapters']))+'/9</td><td>'+label+'</td></tr>')
    html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="15"><title>ORAKT 本地历史报告队列</title><style>body{font:16px/1.7 system-ui;background:#101921;color:#eaf4f0;max-width:1100px;margin:auto;padding:24px}a{color:#a2e8ca}table{width:100%;border-collapse:collapse}td,th{padding:10px;text-align:left;border-bottom:1px solid #3c4a51}pre{white-space:pre-wrap;overflow-wrap:anywhere}h1{font-size:28px}.notice{color:#f4cf85}</style><h1>ORAKT · 本地历史报告队列</h1><p class="notice">九章生成完成不代表内容复审通过。此队列不自动批准或公开发布报告。</p>'''
    html+='<p>检查时间：'+escape(state.get('checkedAt',''))+'</p><p>状态：'+escape(state.get('stage',''))+' · '+escape(str(state.get('activeTicker') or ''))+' · '+escape(str(state.get('activeChapter') or ''))+'</p>'
    html+='<p>单模型串行；报告间休息；温度或内存超限时保留检查点等待。页面每十五秒刷新。</p><table><tr><th>公司</th><th>财报期末</th><th>已生成章节</th><th>状态／本地草稿</th></tr>'+''.join(rows)+'</table>'
    html+='<details><summary>资源与检查点</summary><pre>'+escape(json.dumps({k:v for k,v in state.items() if k!='jobs'},ensure_ascii=False,indent=2))+'</pre></details></html>'
    target=root/'progress.html';temp=root/'progress.html.tmp';temp.write_text(html,encoding='utf-8');temp.replace(target)


def reviewed_handoff(item, job, folder):
    """Validate an explicit completed audit without replacing original drafts."""
    from app.dossier_consolidation import validate_chapters
    source=Path(item['sourcePath'])
    if sha(source)!=item['sourceSha256']:raise ValueError('Frozen source changed')
    original,_=load_frozen_packet(source,get_settings().cold_data_root)
    raw=(folder/'dossier.json').read_bytes();d=json.loads(raw)
    m=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    if (sha(folder/'dossier.json')!=m['dossierSha256']
        or sha(folder/'readable.html')!=m['readableSha256']
        or d['accession']!=item['accession'] or d['ticker']!=job['ticker']
        or d['sourceFingerprint']!=original['fingerprint']
        or d['sourcePacketSha256']!=item['sourceSha256']
        or d['review']['state']!='assistant_reviewed_research_only'
        or d['review']['humanAccepted'] is not False
        or any(d.get(k) is not False for k in ('published','eligibleForPredictiveBacktest','validatedAlpha'))):
        raise ValueError('Exact unpublished reviewed report required')
    chapters=validate_chapters(original,d['chapters'])
    for chapter in chapters:
        checkpoint=job['chapters'][chapter['chapter']]
        path=Path(checkpoint['path'])
        if sha(path)!=checkpoint['sha256']:raise ValueError('Draft changed')
        retained=json.loads(path.read_text(encoding='utf-8'))
        if retained.get('state')=='assistant_reviewed':
            if chapter['section']!=retained['section'] or chapter['review']!=retained['review']:
                reviewed_followup_handoff(source, chapter, path)
        elif chapter['review']['parentSha256']!=checkpoint['sha256']:
            # A review can bind the retained raw model attempt after a complete
            # draft was already saved. Require the same unreviewed section and
            # a fully validated attempt/review chain, not a permissive hash bypass.
            reviewed_attempt_handoff(source, chapter, retained)
    return {'path':str(folder),'dossierSha256':hashlib.sha256(raw).hexdigest(),
        'state':'assistant_reviewed_research_only','published':False,
        'scope':'Complete descriptive structure with explicit evidence gaps; not investment approval'}


def reviewed_followup_handoff(source, chapter, checkpoint_path):
    """Allow an explicit cross-chapter correction, never silent replacement.

    The retained first review remains a validated queue checkpoint. The next
    audit must name its exact bytes and reproduce the new section exclusively
    through the same bounded narrative/claim corrections as the review writer.
    Review files use company_history_dossier.write_json's canonical encoding.
    """
    from app.dossier_attempt_review import validate_checkpoint
    from app.dossier_chapter_review import apply_claim_corrections
    retained = validate_checkpoint(source, checkpoint_path, chapter['chapter'])
    audit = chapter.get('reviewDocument', {})
    review = chapter.get('review', {})
    serialized = json.dumps(audit, ensure_ascii=False, indent=2)
    # write_text newline translation differs between Windows and Linux.
    audit_hashes = {hashlib.sha256(text.encode('utf-8')).hexdigest()
                    for text in (serialized, serialized.replace('\n', '\r\n'))}
    if (review.get('parentSha256') != sha(checkpoint_path)
            or audit.get('parentSha256') != sha(checkpoint_path)
            or audit.get('reviewer') != 'codex_assistant'
            or audit.get('state') != 'accepted_with_revisions'
            or not audit.get('findings')
            or review.get('findings') != audit['findings']
            or review.get('reviewSha256') not in audit_hashes):
        raise ValueError('Follow-up review provenance differs')
    for key in ('ticker', 'chapter', 'sourceFingerprint', 'sourcePacketSha256'):
        if chapter.get(key) != retained.get(key):
            raise ValueError('Follow-up review source differs')
    corrections = audit.get('corrections', {})
    allowed = {'analysis', 'mechanism', 'counterEvidence', 'evidenceGaps', 'validationPlan'}
    if not corrections or set(corrections)-allowed:
        raise ValueError('Follow-up review exceeds narrative scope')
    expected = apply_claim_corrections(retained['section'], audit.get('claimCorrections', {}))
    expected.update(corrections)
    if expected != chapter['section']:
        raise ValueError('Follow-up section differs from explicit audit')


def reviewed_attempt_handoff(source, chapter, retained):
    from app.dossier_attempt_review import validate_checkpoint
    parent_path=Path(chapter.get('reviewParentPath',''))
    if not parent_path.is_file() or sha(parent_path)!=chapter['review']['parentSha256']:
        raise ValueError('Whole report not linked to retained drafts')
    parent=json.loads(parent_path.read_text(encoding='utf-8'))
    for field in ('ticker','chapter','sourceFingerprint','sourcePacketSha256','section'):
        if parent.get(field)!=retained.get(field):
            raise ValueError('Retained attempt differs from saved draft: '+field)
    artifact=parent_path.parent/'reviewed-chapter.json'
    verified=validate_checkpoint(source,artifact,chapter['chapter'])
    if verified!=chapter:
        raise ValueError('Whole report differs from reviewed attempt artifact')


def attach_review(root, folder):
    """Record review progress under the same supervisor lock; no auto-publication."""
    with get_session_factory()().get_bind().connect() as lock:
        if not lock.scalar(text('SELECT pg_try_advisory_lock(624730015831)')):
            raise RuntimeError('Report worker is still running')
        try:
            plan=json.loads((root/'plan.json').read_text(encoding='utf-8'))
            state=json.loads((root/'generation-progress.json').read_text(encoding='utf-8'))
            d=json.loads((folder/'dossier.json').read_text(encoding='utf-8'))
            item=next(i for i in plan['items'] if i['accession']==d['accession'])
            job=state['jobs'][d['accession']]
            if job['state']!='draft_ready_for_content_review':raise ValueError('Full draft checkpoint required')
            record=reviewed_handoff(item,job,folder)
            if job.get('reviewedReport') and job['reviewedReport']!=record:
                raise ValueError('Existing review must not be replaced')
            job['reviewedReport']=record
            state['checkedAt']=now()
            write_json(root/'generation-progress.json',state);readable_status(root,state)
            return record
        finally:lock.execute(text('SELECT pg_advisory_unlock(624730015831)'))


def readable_draft(source,job,target):
    from app.dossier_consolidation import financial_tables
    original,_=load_frozen_packet(source,get_settings().cold_data_root)
    docs=[validate_draft(source,Path(job['chapters'][k]['path']),k) for k,*_ in CHAPTERS]
    parts=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ORAKT local draft</title><style>body{font:16px/1.8 system-ui;max-width:1050px;margin:auto;padding:24px;background:#101921;color:#edf2f5}section{border-top:1px solid #42515a;padding:24px 0}p,code{overflow-wrap:anywhere}blockquote{border-left:3px solid #648778;padding:12px;color:#bfcfca}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #46514e}.table-wrap{overflow:auto}.notice{color:#e9c180}.en{color:#a8c3ba}a{color:#92d5b6}</style>']
    parts.append('<h1>'+escape(job['ticker']+' · '+job['periodEnd'])+'</h1><p class="notice">待内容复审的本地模型草稿 / UNREVIEWED LOCAL DRAFT. Not approved for publication or investment decisions.</p>')
    parts.append('<p>披露日期 / Disclosure: '+escape(job['filedAt'])+' · 当前生成 / Generated: '+escape(now())+'</p>')
    for d in docs:
        parts.append('<section><h2>'+escape(d['chapter'])+'</h2>')
        for field in ('analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'):
            pair=d['section'][field];parts.append('<h3>'+escape(field)+'</h3><p>'+escape(pair['zh'])+'</p><p class="en">'+escape(pair['en'])+'</p>')
        parts.append('<details><summary>原始引用 / Original quotations</summary>')
        for claim in d['section']['grounded_claims']:
            parts.append('<code>'+escape(claim['passage_id'])+'</code><blockquote>'+escape(claim['quote'])+'</blockquote>')
        parts.append('</details></section>')
    parts.append(financial_tables(original['packet']['financial_ledger'])+'</html>')
    if target.exists():raise ValueError('Preserve existing readable draft')
    target.write_text(''.join(parts),encoding='utf-8')


def plan(root, catalog, reviewed_dir, tickers, cutoff, resume=False):
    path=root/'plan.json'
    if path.exists() and not resume:raise ValueError('Existing plan; explicit resume required')
    companies=leaders(json.loads(catalog.read_text(encoding='utf-8')))
    selected=[c for c in companies if c['ticker'] in tickers and c['marketRegion']=='us']
    if set(tickers)!={c['ticker'] for c in selected}:raise ValueError('Select existing US leaders; CN normalization is a separate queue')
    settings=get_settings();known=reviewed_index(reviewed_dir)
    old=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if old and (old['cutoff']!=str(cutoff) or old['tickers']!=[c['ticker'] for c in selected]):
        raise ValueError('Frozen scope changed')
    previous={i['accession']:i for i in old.get('items',[])}
    items=[]
    result={'version':'leader-history/v31','cutoff':str(cutoff),'createdAt':old.get('createdAt',now()),
        'tickers':[c['ticker'] for c in selected],'frequency':'Each annual/quarterly statutory filing; amendments kept as distinct disclosure versions',
        'sourcePolicy':'Same-accession original facts; no unknown-vintage market series; historical reconstruction is not an ex-ante forecast',
        'published':False,'items':items}
    def save(stage):
        result.update(stage=stage,checkedAt=now(),summary=summarize(items));write_json(path,result)
    with get_session_factory()() as db:
        # Inventory the entire existing issuer database without expanding GPU work.
        counts=db.execute(select(CompanyFiling.ticker,CompanyFiling.accession_number,CompanyFiling.filed_at).where(
            CompanyFiling.form.in_(REPORT_FORMS),CompanyFiling.filed_at<=cutoff)).all()
        result['universe']={'existingUSCompanies':len(db.scalars(select(CompanyProfile.ticker)).all()),
            'indexedPeriodicVersions':len(counts),'curatedLeaders':len(companies),
            'curatedUSLeaders':sum(c['marketRegion']=='us' for c in companies),
            'curatedCNLeaders':sum(c['marketRegion']=='china' for c in companies),
            'note':'Filing versions are not complete validated reports; source and review gaps remain.'}
        for company in selected:
            rows=db.scalars(select(CompanyFiling).where(CompanyFiling.ticker==company['ticker'],
                CompanyFiling.form.in_(REPORT_FORMS),CompanyFiling.filed_at<=cutoff).order_by(
                    CompanyFiling.filed_at,CompanyFiling.accession_number)).all()
            for filing in rows:
                check_pause(root,'reports')
                item={'ticker':filing.ticker,'accession':filing.accession_number,'form':filing.form,
                    'filedAt':str(filing.filed_at),'periodEnd':str(filing.report_date) if filing.report_date else None,
                    'sourceUrl':filing.source_url,'state':'source_preflight','published':False}
                before=previous.get(filing.accession_number)
                if before and before['state'] in {'ready_for_generation','existing_review_record'}:
                    items.append(before);save('source_preflight');continue
                items.append(item)
                existing=known.get((filing.ticker,filing.accession_number))
                if existing:
                    item.update(existing);save('source_preflight');continue
                try:
                    if not filing.report_date or filing.report_date>cutoff:
                        raise ValueError('Missing or future reporting period')
                    original_path=filing_target(filing,settings.cold_data_root)
                    if not original_path.is_file():
                        item.update(state='waiting_original',reason='Original collector has not retained this primary document')
                        save('source_preflight');continue
                    packet=build_packet(db,ticker=filing.ticker,cold_root=settings.cold_data_root,accession=filing.accession_number)
                    packet=enrich_inline(packet,settings.cold_data_root)
                    packet['market_evidence']=[]
                    packet['historical_market_policy']='Unknown release vintages excluded, not substituted with latest series'
                    packet=add_passages(packet,settings.cold_data_root);packet['financial_ledger']=build_ledger(packet)
                    temporal_check(packet);readiness=ready_packet(packet)
                    fingerprint=hashlib.sha256(json.dumps({'version':VERSION,'packet':packet},sort_keys=True).encode()).hexdigest()
                    target=root/'packets'/filing.ticker/filing.accession_number/'source.json'
                    if target.exists():raise ValueError('Unregistered source packet retained for reconciliation')
                    write_json(target,{'version':VERSION,'packet':packet,'fingerprint':fingerprint})
                    item.update(state='ready_for_generation',sourcePath=str(target),sourceSha256=sha(target),readiness=readiness)
                except (ValueError,OSError) as exc:
                    item.update(state='waiting_evidence',reason=str(exc)[:500])
                save('source_preflight')
    save('plan_ready');return result


def validate_draft(source, chapter, key):
    document=json.loads(chapter.read_text(encoding='utf-8'))
    if document.get('state')=='assistant_reviewed':
        from app.dossier_attempt_review import validate_checkpoint
        return validate_checkpoint(source,chapter,key)
    settings=get_settings();original,_=load_frozen_packet(source,settings.cold_data_root)
    packet=original['packet'];temporal_check(packet)
    d=json.loads(chapter.read_text(encoding='utf-8'))
    if (d['sourceFingerprint']!=original['fingerprint'] or d['sourcePacketSha256']!=sha(source)
        or d['chapter']!=key or d['ticker']!=packet['ticker'] or d['state']!='content_review_pending'):
        raise ValueError('Checkpoint identity/state mismatch')
    section=Section.model_validate(d['section'])
    # Reproduce source binding and existing financial/claim validators, not approval.
    view=json.loads((chapter.parent/'writer-view.json').read_text(encoding='utf-8'))
    if d.get('evidenceMigration'):
        from app.leader_evidence_revision import validate_migration
        validate_migration(d,source,original,chapter.parent/'writer-view.json')
    contexts=d['evidenceContext']
    draft={}
    for k in ('analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'):
        suffix=' ['+', '.join(contexts[k])+']'
        pair=section.model_dump()[k]
        if any(not pair[lang].endswith(suffix) for lang in ('zh','en')):
            raise ValueError('Bilingual source context differs')
        draft[k]={lang:pair[lang][:-len(suffix)] for lang in ('zh','en')}
        draft[k]['support_ids']=contexts[k]
    if len(draft['analysis']['zh'])<250 or len(draft['analysis']['en'])<800:
        raise ValueError('Underdeveloped bilingual analysis')
    draft['claims']=[{'passage_id':c.passage_id,'statement':c.statement.model_dump()} for c in section.grounded_claims]
    checked,_=bind(draft,packet,key,view)
    if checked.model_dump()!=section.model_dump():raise ValueError('Checkpoint no longer reproduces')
    return d


def gpu_telemetry():
    executable=shutil.which('nvidia-smi')
    if not executable:return {'state':'sensor_unavailable'}
    try:
        result=subprocess.run([executable,'--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw,power.limit,ecc.errors.uncorrected.volatile.total',
            '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=15,check=True)
        rows=[x.strip().split(', ') for x in result.stdout.splitlines() if x.strip()]
        return {'state':'available','gpus':[dict(zip(('name','temperatureC','utilizationPercent','memoryMiB','totalMemoryMiB','powerW','powerLimitW','uncorrectedEccErrors'),r)) for r in rows],
            'errorCounterScope':'Unsupported/N/A is unknown, not zero errors'}
    except (OSError,subprocess.SubprocessError):return {'state':'sensor_unavailable'}


def recover_attempt(root,accession,key,attempt,reason):
    """Explicit no-GPU reconciliation after a validator repair, NOT approval."""
    if len(reason)<40:raise ValueError('Substantive explicit intervention reason required')
    attempt=attempt.resolve()
    if not attempt.is_relative_to((root/'drafts').resolve()):raise ValueError('Attempt outside this queue')
    with get_session_factory()().get_bind().connect() as lock:
        if not lock.scalar(text('SELECT pg_try_advisory_lock(624730015831)')):raise RuntimeError('Worker active')
        try:
            p=json.loads((root/'plan.json').read_text(encoding='utf-8'))
            item=next(i for i in p['items'] if i['accession']==accession)
            source=Path(item['sourcePath']);original,_=load_frozen_packet(source,get_settings().cold_data_root)
            if sha(source)!=item['sourceSha256']:raise ValueError('Frozen source changed')
            state_path=root/'generation-progress.json';state=json.loads(state_path.read_text(encoding='utf-8'));job=state['jobs'][accession]
            if key in job['chapters']:raise ValueError('Existing successful chapter must not be replaced')
            view=json.loads((attempt.parent/'writer-view.json').read_text(encoding='utf-8'))
            raw=json.loads(attempt.read_text(encoding='utf-8'))
            if raw.get('done_reason')=='length' or raw.get('done') is not True:raise ValueError('Incomplete model response')
            section,contexts=bind(json.loads(raw['message']['content']),original['packet'],key,view)
            output=attempt.parent/'validator-reconciled'
            if output.exists():raise ValueError('Preserve previous reconciliation')
            write_json(output/'writer-view.json',view)
            doc={'ticker':item['ticker'],'chapter':key,'sourceFingerprint':original['fingerprint'],
                'section':section.model_dump(),'evidenceContext':contexts,'state':'content_review_pending',
                'completeDossier':False,'published':False,'authorship':{'narrative':'local_model','groundedClaims':'local_model_unreviewed'},
                'sourcePacketSha256':sha(source),'mechanicalRecovery':{'attemptPath':str(attempt),'attemptSha256':sha(attempt),
                    'reason':reason,'checkedAt':now(),'contentApproved':False}}
            write_json(output/'chapter.json',doc);validate_draft(source,output/'chapter.json',key)
            job['chapters'][key]={'path':str(output/'chapter.json'),'sha256':sha(output/'chapter.json')}
            job.setdefault('interventions',[]).append({'chapter':key,'previousFailures':job['failures'],'reason':reason,'at':now()})
            job.update(failures=0,state='checkpoint_reconciled',error=None)
            state.update(stage='checkpoint_reconciled',checkedAt=now(),activeChapter=None)
            write_json(state_path,state);readable_status(root,state)
            return {'chapter':key,'state':'content_review_pending','modelRequests':0,'reason':reason}
        finally:lock.execute(text('SELECT pg_advisory_unlock(624730015831)'))


def cool_down(root, save, seconds=30):
    # Cooperative sleep occurs in the background worker, not in the UI tool.
    # No driver/power settings are changed. Existing stricter gates still apply.
    start=time.monotonic()
    while True:
        check_pause(root,'reports');telemetry=gpu_telemetry();reason=resource_gate()
        hot=any(float(g['temperatureC'])>=78 for g in telemetry.get('gpus',[]) if g['temperatureC'].isdigit())
        if time.monotonic()-start>=seconds and not reason and not hot:
            save('resources_ready',resources=telemetry);return
        save('cooling',resources=telemetry,coolingReason=reason or ('temperature_above_conservative_target' if hot else 'scheduled_rest'),
            coolingSeconds=round(time.monotonic()-start))
        time.sleep(15)


def run(root, limit=3, retry_failed=False, period_inventory=None, original_text=False):
    plan_path=root/'plan.json';p=json.loads(plan_path.read_text(encoding='utf-8'));settings=get_settings()
    state_path=root/'generation-progress.json'
    state=json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {
        'createdAt':now(),'jobs':{},'published':False,'automaticallyApproved':0}
    scope=None
    if period_inventory:
        inventory=json.loads(period_inventory.read_text(encoding='utf-8'))
        if inventory['cutoff']!=p['cutoff']:raise ValueError('Period inventory cutoff mismatch')
        scope={(g['ticker'],g['periodEnd']):g for g in inventory['periods']}
        state['activeScope']={'path':str(period_inventory),'sha256':sha(period_inventory),'summary':inventory['summary'],
            'rule':'US leaders only; one base report per financial period; amendments require explicit merge review'}
    def save(stage,**extra):
        state.update(stage=stage,checkedAt=now(),**extra)
        state['summary']=dict(Counter(j['state'] for j in state['jobs'].values()))
        write_json(state_path,state)
        readable_status(root,state)
    with get_session_factory()().get_bind().connect() as lock:
        keys=(624730015831,624730015811);owned=[]
        try:
            for key in keys:
                if not lock.scalar(text('SELECT pg_try_advisory_lock(:key)'),{'key':key}):
                    raise RuntimeError('Another report supervisor owns the queue')
                owned.append(key)
            count=0
            for item in p['items']:
                if item['state']!='ready_for_generation':continue
                if scope is not None:
                    group=scope.get((item['ticker'],item['periodEnd']))
                    if not group or group['requiresAmendmentMerge'] or group['primaryAccession']!=item['accession']:continue
                accession=item['accession'];job=state['jobs'].get(accession)
                if job and job['state']=='draft_ready_for_content_review':continue
                if job and job['state'] in {'repair_required','interrupted'} and not retry_failed:continue
                if count>=limit:break
                count+=1;check_pause(root,'reports')
                cool_down(root,save,seconds=0 if count==1 else 60)
                source=Path(item['sourcePath'])
                if sha(source)!=item['sourceSha256']:raise ValueError('Frozen source changed')
                job=state['jobs'].setdefault(accession,{'ticker':item['ticker'],'periodEnd':item['periodEnd'],
                    'filedAt':item['filedAt'],'chapters':{},'failures':0,'state':'starting','published':False})
                job['state']='generating';save('generating',activeTicker=item['ticker'],activeAccession=accession)
                for key,*_ in CHAPTERS:
                    check_pause(root,'reports')
                    old=job['chapters'].get(key)
                    if old:
                        if sha(Path(old['path']))!=old['sha256']:raise ValueError('Saved chapter changed')
                        validate_draft(source,Path(old['path']),key);continue
                    if job['chapters']:cool_down(root,save,seconds=15)
                    base=root/'drafts'/item['ticker']/accession/key
                    revisions=[d for d in base.glob('revision-*') if d.name.removeprefix('revision-').isdigit()]
                    failures=[d for d in revisions if (d/'progress.json').exists() and json.loads((d/'progress.json').read_text(encoding='utf-8')).get('stage') in {'repair_required','failed'}]
                    if len(failures)>=3:
                        save('repair_required',reason='Three failed revisions of this chapter require explicit content intervention');return state
                    attempt=max((int(d.name.removeprefix('revision-')) for d in revisions),default=0)+1;target=base/f'revision-{attempt}'
                    if target.exists():
                        job['state']='interrupted';save('repair_required',reason='Retained unregistered output requires reconciliation');return state
                    save('generating',activeChapter=key,activeChapterProgress=str(target/'progress.json'))
                    try:
                        write_chapter(source,target,key,redact_numbers=not original_text,reasoning=True,rejection_root=base.parent)
                    finally:
                        from app.report_usage import write_usage
                        usage=write_usage(base.parent,ticker=item['ticker'],accession=accession)
                        job['usage']={k:v for k,v in usage.items() if k!='calls'}
                    outcome=json.loads((target/'progress.json').read_text(encoding='utf-8'))
                    if outcome['stage']!='content_review_pending':
                        job['failures']+=1;job['state']='repair_required';job['error']=outcome.get('error')
                        save('repair_required',activeChapter=None);return state
                    doc=target/'chapter.json';validate_draft(source,doc,key)
                    job['chapters'][key]={'path':str(doc),'sha256':sha(doc)};save('generating')
                job['state']='draft_ready_for_content_review'
                job['checks']={'structure':'nine_chapters','originalHash':'matched','financialLedger':'reproduced',
                    'timestamps':'same_filing_only','claims':'exact_source_binding','bilingual':'paired_fields_present; semantic equivalence pending review',
                    'independentContentReview':'pending'}
                readable_draft(source,job,root/'drafts'/item['ticker']/accession/'readable-draft.html')
                write_json(root/'drafts'/item['ticker']/accession/'report-manifest.json',job)
                save('between_reports',activeChapter=None)
            save('review_pending',activeTicker=None,activeAccession=None,activeChapter=None)
        except BaseException as exc:
            save('safely_paused' if isinstance(exc,InterruptedError) else 'failed',error=str(exc)[:500]);raise
        finally:
            for key in reversed(owned):lock.execute(text('SELECT pg_advisory_unlock(:key)'),{'key':key})
    return state


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['plan','run','pause','resume']);parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--catalog',type=Path);parser.add_argument('--reviewed-dir',type=Path)
    parser.add_argument('--tickers',nargs='+',default=['AAPL']);parser.add_argument('--cutoff',type=date.fromisoformat,default=date.today())
    parser.add_argument('--resume',action='store_true');parser.add_argument('--retry-failed',action='store_true')
    parser.add_argument('--period-inventory',type=Path)
    parser.add_argument('--original-text',action='store_true',help='Provide unmasked original values to the model; quantitative prose validation still applies')
    parser.add_argument('--limit',type=int,default=3);args=parser.parse_args()
    if args.action=='pause':
        write_json(args.root/'pause-reports',{'reason':'Explicit audit pause; retained checkpoints are not deleted','createdAt':now()})
        print('Cooperative pause requested')
    elif args.action=='resume':
        marker=args.root/'pause-reports'
        if marker.exists():marker.unlink()
        print('Pause marker cleared; no worker launched')
    elif args.action=='plan':
        if not args.catalog or not args.reviewed_dir or args.cutoff>date.today():parser.error('Catalog, reviewed directory and nonfuture cutoff required')
        result=plan(args.root,args.catalog,args.reviewed_dir,args.tickers,args.cutoff,args.resume)
        print(json.dumps({'summary':result['summary'],'universe':result['universe']}))
    else:
        if not 1<=args.limit<=300:parser.error('Limit must be between 1 and 300')
        result=run(args.root,args.limit,args.retry_failed,args.period_inventory,args.original_text);print(json.dumps({'stage':result['stage'],'summary':result['summary']}))
