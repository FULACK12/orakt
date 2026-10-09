"""Single filing, sequential chapter drafts; no automatic content approval."""
import argparse,hashlib,json,time
from datetime import UTC,datetime
from pathlib import Path
from app.company_history_dossier import CHAPTERS,write_json
from app.dossier_compact_writer import run


def batch(source,output,chapters, *, redact_numbers=False, reasoning=False):
    known=[x[0] for x in CHAPTERS]
    if not chapters or len(set(chapters))!=len(chapters) or set(chapters)-set(known):raise ValueError('Invalid chapter list')
    if output.exists():raise ValueError('Preserve existing batch')
    started=time.monotonic();digest=hashlib.sha256(source.read_bytes()).hexdigest()
    state={'source':str(source),'sourceSha256':digest,'requestedChapters':chapters,'startedAt':datetime.now(UTC).isoformat(),
        'stage':'starting','drafts':[],'reviewedChapters':0,'published':False,'fullReportAccepted':False}
    def save(stage):
        state.update(stage=stage,checkedAt=datetime.now(UTC).isoformat(),elapsedSeconds=round(time.monotonic()-started,2))
        write_json(output/'progress.json',state)
    save('starting')
    try:
        for key in chapters:
            if (output/'pause').exists():raise InterruptedError('Safe pause requested')
            if hashlib.sha256(source.read_bytes()).hexdigest()!=digest:raise ValueError('Frozen source changed')
            state['activeChapter']=key;save('generating')
            if redact_numbers or reasoning:
                run(source,output/key,key,redact_numbers=redact_numbers,reasoning=reasoning)
            else:
                run(source,output/key,key)
            progress=json.loads((output/key/'progress.json').read_text(encoding='utf-8'))
            state['drafts'].append({'chapter':key,'stage':progress['stage'],'elapsedSeconds':progress['elapsedSeconds']})
            if progress['stage']!='content_review_pending':
                state['activeChapter']=None;save('repair_required');return state
        state['activeChapter']=None;save('drafts_ready_for_review')
    except BaseException as exc:
        state['activeChapter']=None;state['errorType']=type(exc).__name__;state['error']=str(exc)[:500]
        save('safely_paused' if isinstance(exc,InterruptedError) else 'failed')
        raise
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--chapters',nargs='+',required=True)
    p.add_argument('--redact-numbers',action='store_true');p.add_argument('--reasoning',action='store_true');a=p.parse_args()
    print(json.dumps(batch(a.source,a.output,a.chapters,redact_numbers=a.redact_numbers,reasoning=a.reasoning),ensure_ascii=False))
