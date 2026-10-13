"""One bounded development report, single GPU, originals retained, no publishing.

Exactly one call per chapter initially. Complete raw responses failing content
guards can be bound as explicitly rejected drafts for review, NEVER approval.
Rejected training candidates stay quarantined. Does not advance the live queue.
"""
import argparse
import hashlib
import json
import time
from datetime import UTC,datetime
from pathlib import Path
from sqlalchemy import text
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.dossier_compact_writer import run as write_chapter
from app.leader_history_batch import cool_down
from app.report_quality import CHAPTERS, worklist
from app.report_rejections import guard, DEFAULT_POLICY, retain_rejected_draft
from app.report_usage import save, collect_usage
from app.review_frozen_dossier import load_frozen_packet
from app.model_workload import MODEL_WORKLOAD_LOCK_ID


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(source,root,holdout,resume=False):
    if root.exists() and not resume:raise ValueError('Preserve previous trial output; do not rerun this report')
    if resume and not root.exists():raise ValueError('No existing trial to resume')
    settings=get_settings();original,_=load_frozen_packet(source,settings.cold_data_root)
    packet=original['packet']
    if packet['ticker'] in {c['groupId'] for c in json.loads(holdout.read_text(encoding='utf-8'))['cases'] if c['split']=='holdout'}:
        raise ValueError('Do not tune on reserved holdout issuers')
    started=time.monotonic();documents=[]
    policy={**DEFAULT_POLICY,'maxModelRequests':9,'maxKnownLocalTokens':120000,'maxWallSeconds':1800}
    state={'ticker':packet['ticker'],'accession':packet['accession'],'startedAt':datetime.now(UTC).isoformat(),
           'sourcePath':str(source),'sourceSha256':sha(source),'developmentOnly':True,
           'policy':policy,'published':False,'trainingEnabled':False,'chapters':{}}
    prior_wall=0
    if resume:
        guard(root)
        state=json.loads((root/'progress.json').read_text(encoding='utf-8'))
        if state.get('stage')!='stopped' or state.get('error')!='Local model busy':
            raise ValueError('Only lock contention may resume; quality/budget failures require separate review')
        if sha(source)!=state['sourceSha256'] or json.loads((root/'source.json').read_text(encoding='utf-8'))!=original:
            raise ValueError('Frozen evidence changed; cannot resume')
        prior_wall=json.loads((root/'usage-summary.json').read_text(encoding='utf-8'))['trialWallSeconds']
        snapshot=root/'interruptions'/(sha(root/'progress.json')+'.json')
        if not snapshot.exists():save(snapshot,state)
        for key in CHAPTERS:
            target=root/'drafts'/key/'revision-1'
            rejected=target/'rejected-bound-chapter.json';accepted=target/'chapter.json'
            if rejected.exists():
                raw=json.loads((target/'attempt-1.json').read_text(encoding='utf-8'))
                view=json.loads((target/'writer-view.json').read_text(encoding='utf-8'))
                doc=json.loads(rejected.read_text(encoding='utf-8'))
                if doc!=retain_rejected_draft(raw,view,original,key):raise ValueError('Changed retained chapter')
                documents.append(doc)
            elif accepted.exists():
                doc=json.loads(accepted.read_text(encoding='utf-8'))
                if doc['sourceFingerprint']!=original['fingerprint']:raise ValueError('Changed retained evidence')
                documents.append(doc)
            elif target.exists():raise ValueError('Partial attempt retained; automatic retry prohibited')
        state.pop('error',None);state.pop('errorType',None)
    else:
        root.mkdir(parents=True)
        save(root/'source.json',original)
    def progress(stage,**extra):
        state.update(stage=stage,**extra);save(root/'progress.json',state)
    with get_session_factory()().get_bind().connect() as lock:
        owned=[]
        try:
            for key in (624730015831,624730015811):
                if not lock.scalar(text('SELECT pg_try_advisory_lock(:key)'),{'key':key}):
                    raise RuntimeError('Another report worker owns the global lock')
                owned.append(key)
            # Own the model for the bounded batch, including cooling. Otherwise
            # an interactive worker can legitimately win between two chapters.
            if not lock.scalar(text('SELECT pg_try_advisory_xact_lock(:key)'),{'key':MODEL_WORKLOAD_LOCK_ID}):
                raise RuntimeError('Local model busy')
            for n,key in enumerate(CHAPTERS):
                if key in {d['chapter'] for d in documents}:continue
                guard(root,key)
                usage=collect_usage(root/'drafts')
                if usage['callCount']>=policy['maxModelRequests'] or usage['inputTokensKnown']+usage['outputTokensKnown']>=policy['maxKnownLocalTokens'] or prior_wall+time.monotonic()-started>=policy['maxWallSeconds']:
                    progress('budget_stopped');return state
                cool_down(root,progress,seconds=15 if n else 0)
                progress('generating',activeChapter=key)
                target=root/'drafts'/key/'revision-1'
                write_chapter(source,target,key,redact_numbers=False,reasoning=True,max_attempts=1,rejection_root=root,model_connection=lock)
                local=json.loads((target/'progress.json').read_text(encoding='utf-8'))
                if (target/'chapter.json').exists():
                    doc=json.loads((target/'chapter.json').read_text(encoding='utf-8'))
                else:
                    raw=json.loads((target/'attempt-1.json').read_text(encoding='utf-8'))
                    view=json.loads((target/'writer-view.json').read_text(encoding='utf-8'))
                    doc=retain_rejected_draft(raw,view,original,key)
                    save(target/'rejected-bound-chapter.json',doc)
                documents.append(doc)
                state['chapters'][key]={'generationState':local['stage'],'error':local.get('error')}
                progress('chapter_retained',activeChapter=key)
            save(root/'draft-report.json',{'ticker':packet['ticker'],'accession':packet['accession'],
                 'sourceFingerprint':original['fingerprint'],'state':'pending_substantive_review',
                 'chapters':documents,'published':False,'createdAt':datetime.now(UTC).isoformat()})
            save(root/'semantic-worklist.json',worklist(packet,documents,complete=True))
            progress('pending_substantive_review',activeChapter=None)
        except BaseException as exc:
            progress('stopped',errorType=type(exc).__name__,error=str(exc)[:500])
            raise
        finally:
            # A stopped run is an explicitly incomplete draft, never silently
            # discarded or represented as a finished nine-chapter report.
            if not (root/'draft-report.json').exists():
                save(root/'partial-draft-report.json',{'ticker':packet['ticker'],
                    'accession':packet['accession'],'chapters':documents,'complete':False,
                    'state':'incomplete_rejected_trial','published':False})
            save(root/'usage-summary.json',{**collect_usage(root/'drafts'),
                 'trialWallSeconds':round(prior_wall+time.monotonic()-started,3),'scopeNote':'Includes active-run cooling; excludes downtime between resumptions; local model time separate; Codex review not metered.'})
            for key in reversed(owned):lock.execute(text('SELECT pg_advisory_unlock(:key)'),{'key':key})
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--holdout',type=Path,required=True);p.add_argument('--resume',action='store_true');a=p.parse_args()
    print(json.dumps(run(a.source,a.root,a.holdout,a.resume),ensure_ascii=False))
