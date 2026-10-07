import json
import pytest
import app.dossier_compact_batch as m
from app.company_history_dossier import write_json


def test_batch_is_sequential_and_never_approves(tmp_path, monkeypatch):
    source=tmp_path/'source.json';source.write_text('{}')
    calls=[]
    def run(s,o,k):
        calls.append(k)
        write_json(o/'progress.json',{'stage':'content_review_pending','elapsedSeconds':1})
    monkeypatch.setattr(m,'run',run)
    state=m.batch(source,tmp_path/'out',['financial','capital'])
    assert calls==['financial','capital']
    assert state['stage']=='drafts_ready_for_review'
    assert state['reviewedChapters']==0 and not state['published'] and not state['fullReportAccepted']


@pytest.mark.parametrize('action',['pause','mutation','repair'])
def test_stops_before_next_chapter(tmp_path,monkeypatch,action):
    source=tmp_path/'source.json';source.write_text('{}');out=tmp_path/'out';calls=[]
    def run(s,o,k):
        calls.append(k)
        write_json(o/'progress.json',{'stage':'repair_required' if action=='repair' else 'content_review_pending','elapsedSeconds':1})
        if action=='pause':(out/'pause').touch()
        if action=='mutation':source.write_text('{"changed":true}')
    monkeypatch.setattr(m,'run',run)
    if action=='repair':m.batch(source,out,['financial','capital'])
    else:
        with pytest.raises((InterruptedError,ValueError)):m.batch(source,out,['financial','capital'])
    state=json.loads((out/'progress.json').read_text(encoding='utf-8'))
    assert calls==['financial'] and state['activeChapter'] is None
    assert state['stage']=={'pause':'safely_paused','mutation':'failed','repair':'repair_required'}[action]


@pytest.mark.parametrize('chapters',[[],['financial','financial'],['unknown']])
def test_invalid_batch_before_source_read(tmp_path,chapters):
    with pytest.raises(ValueError):m.batch(tmp_path/'missing',tmp_path/'out',chapters)
