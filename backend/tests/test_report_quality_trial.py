import json
from types import SimpleNamespace
import pytest
from app.report_usage import save
import app.report_quality_trial as trial


@pytest.mark.parametrize('redact_numbers',[False,True])
def test_resume_only_missing_chapters_and_reuses_model_lock_connection(tmp_path,monkeypatch,redact_numbers):
    source=tmp_path/'source.json';root=tmp_path/'trial';holdout=tmp_path/'holdout.json'
    original={'fingerprint':'immutable','packet':{'ticker':'TEST','accession':'a'}}
    save(source,original);save(holdout,{'cases':[]})
    monkeypatch.setattr(trial,'get_settings',lambda:SimpleNamespace(cold_data_root=tmp_path))
    monkeypatch.setattr(trial,'load_frozen_packet',lambda *a:(original,b''))
    monkeypatch.setattr(trial,'CHAPTERS',('business','financial'))
    monkeypatch.setattr(trial,'cool_down',lambda *a,**k:None)
    monkeypatch.setattr(trial,'worklist',lambda *a,**k:{'automaticApprovalEnabled':False})
    class Connection:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def scalar(self,*a):return True
        def execute(self,*a):pass
    conn=Connection()
    monkeypatch.setattr(trial,'get_session_factory',lambda:lambda:SimpleNamespace(get_bind=lambda:SimpleNamespace(connect=lambda:conn)))
    calls=[];busy=[True]
    def write(src,target,key,**kwargs):
        assert kwargs['max_attempts']==1 and kwargs['model_connection'] is conn
        assert kwargs['redact_numbers'] is redact_numbers
        if key=='financial' and busy[0]:raise RuntimeError('Local model busy')
        calls.append(key)
        save(target/'chapter.json',{'chapter':key,'sourceFingerprint':'immutable'})
        save(target/'progress.json',{'stage':'content_review_pending'})
    monkeypatch.setattr(trial,'write_chapter',write)
    with pytest.raises(RuntimeError,match='busy'):trial.run(source,root,holdout,redact_numbers=redact_numbers)
    assert calls==['business'] and (root/'partial-draft-report.json').exists()
    busy[0]=False
    with pytest.raises(ValueError,match='writer options'):
        trial.run(source,root,holdout,resume=True,redact_numbers=not redact_numbers)
    assert calls==['business']
    trial.run(source,root,holdout,resume=True,redact_numbers=redact_numbers)
    assert calls==['business','financial']
    assert len(json.loads((root/'draft-report.json').read_text())['chapters'])==2
    assert len(list((root/'interruptions').glob('*.json')))==1
    with pytest.raises(ValueError):trial.run(source,root,holdout,resume=True,redact_numbers=redact_numbers)
