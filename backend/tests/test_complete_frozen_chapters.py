import json
from contextlib import nullcontext
from types import SimpleNamespace
from app import complete_frozen_chapters as runner

def setup(monkeypatch,tmp_path):
    source=tmp_path/'original/source.json';source.parent.mkdir()
    packet={'ticker':'TEST','accession':'123','as_of_date':'2025-05-07'}
    original={'version':'old','fingerprint':'old-hash','packet':packet}
    monkeypatch.setattr(runner,'get_settings',lambda:SimpleNamespace(cold_data_root=tmp_path))
    monkeypatch.setattr(runner,'load_frozen_packet',lambda *_:(original,b'frozen fixture'))
    monkeypatch.setattr(runner,'get_session_factory',lambda:lambda:nullcontext(None))
    monkeypatch.setattr(runner,'local_model_workload_lock',lambda _:nullcontext(True))
    def forbidden(*args,**kwargs):raise AssertionError('No model request expected')
    monkeypatch.setattr(runner,'generate',forbidden)
    return source,tmp_path/'revision/reports'

def test_resume_retains_attempts_without_regeneration_or_publication(monkeypatch,tmp_path):
    source,output=setup(monkeypatch,tmp_path)
    for i,(key,*_) in enumerate(runner.CHAPTERS,1):(source.parent/f'{i:02d}-{key}-attempt.json').write_text('{}')
    runner.run(source,output);runner.run(source,output)
    progress=json.loads((output.parent/'chapter-progress.json').read_text())
    assert progress['stage']=='awaiting_assistant_content_review'
    assert progress['published'] is False and len(progress['chapters'])==9
    assert len(list(output.rglob('*-attempt.json')))==9
    assert not list(output.rglob('dossier.json'))

def test_resource_gate_stops_before_missing_chapter(monkeypatch,tmp_path):
    source,output=setup(monkeypatch,tmp_path)
    monkeypatch.setattr(runner,'resource_gate',lambda:'hot GPU')
    runner.run(source,output)
    progress=json.loads((output.parent/'chapter-progress.json').read_text())
    assert progress['stage']=='resource_gate_blocked' and not list(output.rglob('*-attempt.json'))

def test_pause_stops_before_missing_chapter(monkeypatch,tmp_path):
    source,output=setup(monkeypatch,tmp_path)
    monkeypatch.setattr(runner,'resource_gate',lambda:None)
    output.parent.mkdir();(output.parent/'pause').touch()
    runner.run(source,output)
    assert json.loads((output.parent/'chapter-progress.json').read_text())['stage']=='safely_paused'
