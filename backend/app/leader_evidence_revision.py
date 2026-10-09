"""Explicit additive-source fork; retain old queue and migrate only unchanged drafts.

No review approval migrates. A changed chapter's source view must be regenerated.
"""
import argparse
import copy
import json
from pathlib import Path
from sqlalchemy import text
from app.company_history_dossier import write_json
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.leader_history_batch import sha, validate_draft, readable_status, summarize
from app.leader_report_batch import now
from app.review_frozen_dossier import load_frozen_packet


def check_additive(old, new):
    before=copy.deepcopy(old['packet']);after=copy.deepcopy(new['packet'])
    a=before.pop('chapter_passages');b=after.pop('chapter_passages')
    before.pop('earnings_context_ids',None);after.pop('earnings_context_ids',None)
    if before!=after:raise ValueError('Only additive same-filing evidence is allowed')
    for key,rows in a.items():
        lookup={p['id']:p for p in b.get(key,[])}
        if len(lookup)!=len(b.get(key,[])):raise ValueError('Duplicate source identity')
        if any(lookup.get(p['id'])!=p for p in rows):raise ValueError('Prior passages changed')
    return {key for key in a if a[key]==b.get(key)}


def validate_migration(document, source, original, view_path):
    """An unchanged draft may move, but its evidence and wording cannot mutate."""
    record=document.get('evidenceMigration')
    if not record:return
    parent_path=Path(record['parentChapterPath']);old_source=Path(record['parentSourcePath'])
    if sha(parent_path)!=record['parentChapterSha256'] or sha(old_source)!=record['parentSourceSha256']:
        raise ValueError('Migration parent changed')
    old,_=load_frozen_packet(old_source,get_settings().cold_data_root)
    parent=json.loads(parent_path.read_text(encoding='utf-8'))
    if (document['chapter'] not in check_additive(old,original)
        or parent.get('state')!='content_review_pending'
        or parent['sourceFingerprint']!=old['fingerprint']
        or parent['sourcePacketSha256']!=sha(old_source)
        or sha(parent_path.parent/'writer-view.json')!=record['parentWriterViewSha256']
        or sha(view_path)!=record['parentWriterViewSha256']):
        raise ValueError('Migration source view changed')
    expected=copy.deepcopy(parent)
    expected.update(sourceFingerprint=original['fingerprint'],sourcePacketSha256=sha(source),evidenceMigration=record)
    if expected!=document:raise ValueError('Migrated draft wording or state changed')


def fork(parent, source, output, accession):
    if output.exists():raise ValueError('Preserve prior queue revision')
    with get_session_factory()().get_bind().connect() as lock:
        if not lock.scalar(text('SELECT pg_try_advisory_lock(624730015831)')):raise RuntimeError('Worker active')
        try:
            p=json.loads((parent/'plan.json').read_text(encoding='utf-8'))
            state=json.loads((parent/'generation-progress.json').read_text(encoding='utf-8'))
            item=copy.deepcopy(next(i for i in p['items'] if i['accession']==accession))
            job=state['jobs'][accession]
            if job['state']!='repair_required' or job.get('reviewedReport'):raise ValueError('Only failed unapproved job may fork')
            old_path=Path(item['sourcePath']);cold=get_settings().cold_data_root
            if sha(old_path)!=item['sourceSha256']:raise ValueError('Old packet changed')
            old,_=load_frozen_packet(old_path,cold);new,_=load_frozen_packet(source,cold)
            provenance=new.get('evidenceRevision',{})
            if provenance.get('parentSha256')!=sha(old_path) or provenance.get('parentFingerprint')!=old['fingerprint']:
                raise ValueError('Explicit parent revision required')
            unchanged=check_additive(old,new)
            prepared=[]
            for key,checkpoint in job['chapters'].items():
                if key not in unchanged:raise ValueError('Successful chapter evidence changed; explicit review required')
                path=Path(checkpoint['path'])
                if sha(path)!=checkpoint['sha256']:raise ValueError('Checkpoint changed')
                doc=validate_draft(old_path,path,key)
                if doc['state']!='content_review_pending':raise ValueError('Never transfer prior review approval')
                view=path.parent/'writer-view.json'
                prepared.append((key,path,doc,view))
            item.update(sourcePath=str(source),sourceSha256=sha(source),state='ready_for_generation')
            new_job={k:job[k] for k in ('ticker','periodEnd','filedAt')}
            new_job.update(chapters={},failures=0,state='evidence_revision_ready',published=False)
            for key,path,doc,view in prepared:
                target=output/'drafts'/item['ticker']/accession/key/'migration-1'
                migrated=copy.deepcopy(doc)
                migrated.update(sourceFingerprint=new['fingerprint'],sourcePacketSha256=sha(source),
                    evidenceMigration={'parentChapterPath':str(path),'parentChapterSha256':sha(path),
                    'parentSourcePath':str(old_path),'parentSourceSha256':sha(old_path),
                    'parentWriterViewSha256':sha(view),'reason':'Exact unchanged chapter passages and financial ledger; approval not transferred.'})
                write_json(target/'writer-view.json',json.loads(view.read_text(encoding='utf-8')))
                write_json(target/'chapter.json',migrated);validate_draft(source,target/'chapter.json',key)
                new_job['chapters'][key]={'path':str(target/'chapter.json'),'sha256':sha(target/'chapter.json')}
            retained=[{'path':str(f),'sha256':sha(f)} for f in (parent/'drafts'/item['ticker']/accession).rglob('attempt-*.json')]
            plan={**p,'createdAt':now(),'checkedAt':now(),'items':[item],'summary':summarize([item]),
                'continuation':{'parentQueue':str(parent),'parentPlanSha256':sha(parent/'plan.json'),
                'parentProgressSha256':sha(parent/'generation-progress.json'),'retainedAttempts':retained,
                'reason':'Explicit additive earnings evidence revision','contentApproved':False}}
            write_json(output/'plan.json',plan)
            progress={'createdAt':now(),'checkedAt':now(),'stage':'evidence_revision_ready','jobs':{accession:new_job},
                'published':False,'automaticallyApproved':0,'summary':{'evidence_revision_ready':1}}
            write_json(output/'generation-progress.json',progress);readable_status(output,progress)
            return {'ticker':item['ticker'],'migratedUnchangedChapters':list(new_job['chapters']),
                'root':str(output),'oldQueueModified':False,'modelCalls':0,'approved':False}
        finally:lock.execute(text('SELECT pg_advisory_unlock(624730015831)'))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('parent','source','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--accession',required=True);a=p.parse_args()
    print(json.dumps(fork(a.parent,a.source,a.output,a.accession)))
