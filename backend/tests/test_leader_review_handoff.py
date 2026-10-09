import json
from pathlib import Path
import pytest
from app.leader_history_batch import reviewed_handoff, readable_status
from app.leader_history_batch import reviewed_attempt_handoff, sha


def test_changed_frozen_source_never_attaches_review(tmp_path):
    source=tmp_path/'source.json';source.write_text('{}')
    with pytest.raises(ValueError,match='Frozen source changed'):
        reviewed_handoff({'sourcePath':str(source),'sourceSha256':'bad'}, {}, tmp_path)


def test_review_display_does_not_claim_publication(tmp_path):
    readable_status(tmp_path,{'jobs':{'a':{'ticker':'AMZN','periodEnd':'2026-06-30',
        'state':'draft_ready_for_content_review','chapters':{},'reviewedReport':{'state':'assistant_reviewed_research_only'}}}})
    text=(tmp_path/'progress.html').read_text(encoding='utf-8')
    assert '整份复审已完成（发布状态另查）' in text
    assert '不自动批准或公开发布' in text


def test_alternate_attempt_parent_must_match_retained_draft(tmp_path):
    parent=tmp_path/'parent.json';parent.write_text(json.dumps({'ticker':'AAPL'}))
    chapter={'reviewParentPath':str(parent),'review':{'parentSha256':sha(parent)}}
    with pytest.raises(ValueError,match='differs from saved draft'):
        reviewed_attempt_handoff(tmp_path/'source.json',chapter,{'ticker':'GOOGL'})


def test_alternate_attempt_parent_hash_cannot_be_bypassed(tmp_path):
    parent=tmp_path/'parent.json';parent.write_text('{}')
    with pytest.raises(ValueError,match='not linked'):
        reviewed_attempt_handoff(tmp_path/'source.json',{'reviewParentPath':str(parent),'review':{'parentSha256':'bad'}},{})


def followup_fixture(tmp_path, monkeypatch):
    import hashlib
    import copy
    import app.dossier_attempt_review as validation
    retained = {'ticker':'AVGO','chapter':'business','sourceFingerprint':'frozen',
        'sourcePacketSha256':'source', 'section':{'analysis':{'zh':'原文','en':'Original'},
        'grounded_claims':[{'passage_id':'p','quote':'Original quote','statement':{'zh':'原','en':'Old'}}]}}
    path=tmp_path/'checkpoint.json';path.write_text(json.dumps(retained),encoding='utf-8')
    monkeypatch.setattr(validation,'validate_checkpoint',lambda *a:copy.deepcopy(retained))
    audit={'reviewer':'codex_assistant','state':'accepted_with_revisions',
        'parentSha256':sha(path),'findings':['Concentration is disclosed'],
        'corrections':{'analysis':{'zh':'修订','en':'Revised'}},
        'claimCorrections':{'p':{'zh':'新','en':'New'}}}
    chapter=copy.deepcopy(retained)
    chapter['section']['analysis']=audit['corrections']['analysis'].copy()
    chapter['section']['grounded_claims'][0]['statement']={'zh':'新','en':'New'}
    chapter['reviewDocument']=audit
    chapter['review']={'parentSha256':sha(path),'findings':audit['findings'],
        'reviewSha256':hashlib.sha256(json.dumps(audit,ensure_ascii=False,indent=2).encode()).hexdigest()}
    return path,chapter


def test_followup_accepts_exact_parent_and_explicit_changes(tmp_path,monkeypatch):
    from app.leader_history_batch import reviewed_followup_handoff
    path,chapter=followup_fixture(tmp_path,monkeypatch)
    reviewed_followup_handoff(path,chapter,path)
    assert json.loads(path.read_text())['section']['analysis']['en']=='Original'


@pytest.mark.parametrize('mutation',['parent','audit','section','quote','source'])
def test_followup_rejects_changed_provenance_or_unreviewed_text(tmp_path,monkeypatch,mutation):
    from app.leader_history_batch import reviewed_followup_handoff
    path,chapter=followup_fixture(tmp_path,monkeypatch)
    if mutation=='parent':chapter['review']['parentSha256']='wrong'
    elif mutation=='audit':chapter['reviewDocument']['findings']=['Different finding']
    elif mutation=='section':chapter['section']['analysis']['en']='Unreviewed'
    elif mutation=='quote':chapter['section']['grounded_claims'][0]['quote']='Invented'
    else:chapter['sourceFingerprint']='other'
    with pytest.raises(ValueError):reviewed_followup_handoff(path,chapter,path)
