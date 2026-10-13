import json
import pytest
from app.report_rejections import guard, reject, events
from app.report_quality_trial import retain_rejected_draft


def inputs(tmp):
    source=tmp/'source.json';candidate=tmp/'candidate.json'
    source.write_text(json.dumps({'fingerprint':'original','packet':{'ticker':'TEST','accession':'abc',
        'raw_sha256':'raw','source_url':'https://example.test/filing','chapter_passages':{'business':[]}}}))
    candidate.write_text(json.dumps({'message':{'content':'rejected'}}))
    return source,candidate


def test_rejected_samples_are_immutable_not_training_ready(tmp_path):
    source,candidate=inputs(tmp_path)
    args=dict(source=source,candidate=candidate,chapter='business',phase='semantic_review',findings=[{'location':'analysis','error':'unsupported'}])
    first=reject(tmp_path,**args)
    assert not first['trainingEligible'] and first['correctedAnswer'] is None
    assert first['rejectedVersion']==json.loads(candidate.read_text())
    assert reject(tmp_path,**args)==first and len(events(tmp_path))==1
    args['findings']=['different']
    with pytest.raises(ValueError,match='immutable'):reject(tmp_path,**args)


def test_three_chapter_rejections_stop_across_restarts(tmp_path):
    source,candidate=inputs(tmp_path)
    for n in range(3):
        guard(tmp_path,'business')
        candidate.write_text(json.dumps({'attempt':n}))
        reject(tmp_path,source=source,candidate=candidate,chapter='business',phase='generation_validation',findings=['bad source'])
    with pytest.raises(RuntimeError,match='Rejection limit'):guard(tmp_path,'business')
    assert guard(tmp_path,'financial')['chapterRejections']==0


def test_two_whole_report_rejections_stop_every_chapter(tmp_path):
    source,candidate=inputs(tmp_path)
    for n in range(2):
        candidate.write_text(json.dumps({'revision':n}))
        reject(tmp_path,source=source,candidate=candidate,chapter=None,phase='whole_report_review',findings=['not ready'])
    with pytest.raises(RuntimeError):guard(tmp_path,'financial')
    with pytest.raises(RuntimeError):guard(tmp_path)


def test_truncated_raw_output_cannot_be_presented_as_full_chapter():
    with pytest.raises(ValueError,match='Incomplete'):
        retain_rejected_draft({'done':True,'done_reason':'length'}, {}, {}, 'financial')


def test_writer_stops_at_third_rejection_and_keeps_diagnostics(tmp_path,monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    import app.dossier_compact_writer as writer
    import app.orakt_history_queue as queue
    from app.financial_period_ledger import build_ledger
    pid='PASSAGE:1111111111111111'
    packet={'ticker':'TEST','accession':'abc','filing_ref':'SEC:abc','facts':[],
            'as_of_date':'2026-08-06','period_end':'2026-06-30',
            'chapter_passages':{'business':[{'id':pid,'text':'Original public source.'}]}}
    packet['financial_ledger']=build_ledger(packet)
    source=tmp_path/'source.json';source.write_text(json.dumps({'fingerprint':'frozen','packet':packet}))
    original=json.loads(source.read_text())
    monkeypatch.setattr(queue,'resource_gate',lambda:None)
    monkeypatch.setattr(writer,'get_settings',lambda:SimpleNamespace(cold_data_root=tmp_path,llm_model='fake-local',llm_base_url='http://local.test'))
    monkeypatch.setattr(writer,'load_frozen_packet',lambda *a:(original,b''))
    monkeypatch.setattr(writer,'writer_view',lambda *a,**kw:{'passages':[{'id':pid}]})
    monkeypatch.setattr(writer,'schema_for',lambda *a,**kw:{})
    @contextmanager
    def session(**kwargs):yield object()
    @contextmanager
    def locked(session):yield True
    monkeypatch.setattr(writer,'get_session_factory',lambda:session)
    monkeypatch.setattr(writer,'local_model_workload_lock',locked)
    body={k:{'support_ids':[pid],'zh':'待审错误草稿。','en':'Rejected prose.'} for k in ('analysis','mechanism','counterEvidence','evidenceGaps','validationPlan')}
    body['claims']=[{'passage_id':pid,'statement':{'zh':'草稿','en':'Draft'}}]
    calls=[]
    def generate(*a):
        calls.append(1)
        return {'done':True,'done_reason':'stop','message':{'content':json.dumps(body)},'prompt_eval_count':1,'eval_count':2}
    monkeypatch.setattr(writer,'generate',generate)
    def failed(*a):raise ValueError('Explicit quality failure')
    monkeypatch.setattr(writer,'bind',failed)
    writer.run(source,tmp_path/'revision-1','business',rejection_root=tmp_path)
    assert len(calls)==2 and len(events(tmp_path))==2
    assert (tmp_path/'revision-1/rejected-attempt-1-worklist.json').exists()
    with pytest.raises(RuntimeError,match='Rejection limit'):
        writer.run(source,tmp_path/'revision-2','business',rejection_root=tmp_path)
    assert len(calls)==3 and len(events(tmp_path))==3
    with pytest.raises(RuntimeError,match='Rejection limit'):
        writer.run(source,tmp_path/'revision-3','business',rejection_root=tmp_path)
    assert len(calls)==3
