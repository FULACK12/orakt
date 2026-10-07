import hashlib,json
import pytest
import app.dossier_chapter_review as module


def inputs(tmp_path,monkeypatch):
    passages=[{'id':'PASSAGE:'+str(i)*16,'text':'Archived paragraph with sufficient original text '+str(i)} for i in (1,2)]
    pair={'zh':'这是原文披露的业务信息，需要保留口径，不能推出没有证据的因果关系。'*10+' [PASSAGE:1111111111111111]',
          'en':'This source describes business evidence with a limited scope, not proof of causation. '*10+' [PASSAGE:1111111111111111]'}
    section={k:pair for k in ('analysis','mechanism','counterEvidence','evidenceGaps','validationPlan')}
    section.update(evidence_refs=[p['id'] for p in passages],comparison_checks=[],grounded_claims=[{'passage_id':p['id'],'quote':p['text'],'statement':pair} for p in passages])
    packet={'ticker':'TEST','filing_ref':'SEC:0000000000-00-000001','financial_ledger':{'comparisons':[]},'chapter_passages':{'business':passages}}
    chapter={'ticker':'TEST','chapter':'business','sourceFingerprint':'frozen','section':section,'evidenceContext':{}}
    path=tmp_path/'chapter.json';path.write_text(json.dumps(chapter),encoding='utf-8')
    review={'reviewer':'codex_assistant','state':'accepted_with_revisions','findings':['Scope corrected.'],'parentSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'corrections':{'analysis':pair}}
    rev=tmp_path/'review.json';rev.write_text(json.dumps(review),encoding='utf-8')
    monkeypatch.setattr(module,'load_frozen_packet',lambda *a:({'fingerprint':'frozen','packet':packet},b''))
    return path,rev,tmp_path/'output.json'


def test_review_keeps_full_audit_without_publishing(tmp_path,monkeypatch):
    path,rev,out=inputs(tmp_path,monkeypatch)
    module.revise(path,rev,path,out)
    result=json.loads(out.read_text(encoding='utf-8'))
    assert result['reviewDocument']['findings']==['Scope corrected.']
    assert result['state']=='assistant_reviewed' and result['published'] is False
    assert result['completeDossier'] is False
    with pytest.raises(ValueError,match='already exists'):module.revise(path,rev,path,out)


def test_review_rejects_changed_parent(tmp_path,monkeypatch):
    path,rev,out=inputs(tmp_path,monkeypatch)
    path.write_text(path.read_text(encoding='utf-8')+' ',encoding='utf-8')
    with pytest.raises(ValueError,match='draft changed'):module.revise(path,rev,path,out)
    assert not out.exists()


def test_claim_revision_preserves_quote_identity_and_original():
    s={'grounded_claims':[{'passage_id':'p','quote':'Original text','statement':{'zh':'旧','en':'old'}}]}
    r=module.apply_claim_corrections(s,{'p':{'zh':'更正','en':'corrected'}})
    assert r['grounded_claims'][0]['quote']=='Original text'
    assert r['grounded_claims'][0]['passage_id']=='p'
    assert s['grounded_claims'][0]['statement']['en']=='old'


@pytest.mark.parametrize('changes',[{'missing':{'zh':'更正','en':'corrected'}}, {'p':{'quote':'fabricated','zh':'更正','en':'corrected'}}, {'p':{'en':'only'}}, []])
def test_claim_revision_cannot_replace_evidence(changes):
    with pytest.raises(ValueError):
        module.apply_claim_corrections({'grounded_claims':[{'passage_id':'p','quote':'Original'}]},changes)
