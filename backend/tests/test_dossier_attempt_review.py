import json
from pathlib import Path
import pytest
from app.dossier_attempt_review import review_attempt, validate_checkpoint


def test_review_never_overwrites_existing_output(tmp_path):
    with pytest.raises(ValueError,match='Preserve'):
        review_attempt(Path('unused'),Path('unused'),'macro',{},tmp_path)


def test_an_automatic_or_empty_review_cannot_approve_raw_output(tmp_path):
    with pytest.raises(ValueError,match='Explicit'):
        review_attempt(Path('unused'),Path('unused'),'macro',{'reviewer':'local_model'},tmp_path/'new')


def test_checkpoint_requires_matching_reviewed_identity(tmp_path,monkeypatch):
    import app.dossier_attempt_review as m
    source=tmp_path/'source.json';source.write_text('{}')
    monkeypatch.setattr(m,'load_frozen_packet',lambda *a:({'fingerprint':'known','packet':{'ticker':'AMZN'}},b''))
    doc=tmp_path/'chapter.json';doc.write_text(json.dumps({'state':'content_review_pending'}))
    with pytest.raises(ValueError,match='identity'):
        validate_checkpoint(source,doc,'macro')


def test_raw_repair_requires_all_explicit_paragraph_replacements(tmp_path):
    with pytest.raises(ValueError,match='all narrative'):
        review_attempt(Path('unused'),Path('unused'),'macro',
            {'reviewer':'codex_assistant','findings':['Explicit issue'],'corrections':{'analysis':{}}},tmp_path/'new')


def test_rejected_prose_can_be_archived_but_normal_generation_still_rejects_it():
    from app.dossier_reviewed_synthesis import bind_narrative_context
    p={'support_ids':['PASSAGE:test'],'zh':'未披露。','en':'Not disclosed.'}
    draft={k:dict(p) for k in ('analysis','mechanism','counterEvidence','evidenceGaps','validationPlan')}
    with pytest.raises(ValueError,match='conditional'):
        bind_narrative_context(draft,{'PASSAGE:test'})
    bound,_=bind_narrative_context(draft,{'PASSAGE:test'},unreviewed_archive=True)
    assert bound['analysis']['zh']=='未披露。 [PASSAGE:test]'
    with pytest.raises(ValueError,match='supplied support_ids'):
        bind_narrative_context(draft,set(),unreviewed_archive=True)
