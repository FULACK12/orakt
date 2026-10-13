import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from app.dossier_review_context import additive_revision, validate_context
from app.dossier_semantic_guards import known_semantic_errors
from app.dossier_compact_writer import writer_view
from app.financial_period_ledger import build_ledger


def test_additive_context_keeps_originals_and_rejects_ambiguous_anchors(tmp_path,monkeypatch):
    import app.review_frozen_dossier as loader
    html='<p>STATEMENT HEADER</p><p>Six Months Ended 2026 2025 (Millions of dollars)</p><p>Investing Activities: asset sale proceeds 305 932</p><p>END TABLE</p>'
    filing=tmp_path/'raw/sec/company-filings/TEST/123/filing.htm';filing.parent.mkdir(parents=True);filing.write_text(html)
    p={'ticker':'TEST','accession':'123','source_url':'https://example.test/filing.htm',
       'raw_sha256':hashlib.sha256(filing.read_bytes()).hexdigest(),'chapter_passages':{'financial':[]}}
    original={'version':'v1','fingerprint':'parent','packet':p};raw=json.dumps(original).encode()
    monkeypatch.setattr(loader,'load_frozen_packet',lambda *a:(copy.deepcopy(original),raw))
    spec=[{'start':'STATEMENT HEADER','end':'END TABLE','chapters':['financial'],'role':'full_table'}]
    out=tmp_path/'next.json';r=additive_revision(tmp_path/'source.json',tmp_path,out,spec)
    assert not original['packet']['chapter_passages']['financial']
    assert not r['evidenceRevision']['approvalTransferred'] and r['evidenceRevision']['oldEvidencePreserved']
    text=r['packet']['chapter_passages']['financial'][0]['text']
    assert 'Six Months Ended' in text and 'Millions of dollars' in text and 'Investing Activities' in text
    with pytest.raises(ValueError,match='Preserve'):additive_revision(tmp_path/'source.json',tmp_path,out,spec)
    filing.write_text(html+html)
    with pytest.raises(ValueError,match='unique'):additive_revision(tmp_path/'source.json',tmp_path,tmp_path/'other.json',spec)


def test_cash_flow_classification_guard_with_corrected_and_conditional_boundaries():
    packet={'chapter_passages':{'financial':[{'text':'Investing Activities\nProceeds and deposits related to asset sales 305\nFinancing Activities'}]}}
    pair=lambda zh,en:SimpleNamespace(zh=zh,en=en)
    s=SimpleNamespace(**{k:pair('','') for k in ('analysis','mechanism','counterEvidence','evidenceGaps','validationPlan')},grounded_claims=[])
    s.analysis=pair('经营活动现金流增长主要源于资产出售款。','Operating cash flow increased, driven by asset sale proceeds.')
    assert len(known_semantic_errors(s,packet))==2
    s.analysis=pair('不能把资产出售款当成经营活动现金流来源。','Asset-sale proceeds must not be described as an operating cash inflow.')
    assert not known_semantic_errors(s,packet)


def test_short_mask_keeps_original_and_labels():
    pid='PASSAGE:1111111111111111';original='Six Months Ended June 30 2026 2025. Cash in millions of dollars 100 90.'
    p={'ticker':'TEST','as_of_date':'2026-08-06','period_end':'2026-06-30','filing_ref':'SEC:123',
       'facts':[],'chapter_passages':{'financial':[{'id':pid,'text':original}]},'market_evidence':[],'excerpts':[]}
    p['financial_ledger']=build_ledger(p)
    view=writer_view(p,'financial',redact_numbers=True)
    assert '[quantity]' in view['passages'][0]['qualitative_view']
    assert 'millions of dollars' in view['passages'][0]['qualitative_view']
    assert p['chapter_passages']['financial'][0]['text']==original


def test_explicit_selection_excludes_keyword_contamination_but_keeps_archive():
    ids=['PASSAGE:'+str(i)*16 for i in (1,2,3)]
    rows=[{'id':ids[0],'text':'Income tax expense increased; pretax income rose due to prices.'},
          {'id':ids[1],'text':'Consolidated cash flows. Six months ended. Operating and investing activities.'},
          {'id':ids[2],'text':'Cash flow note. Working capital reconciliation and restricted cash.'}]
    p={'ticker':'TEST','as_of_date':'2026-08-06','period_end':'2026-06-30','filing_ref':'SEC:123',
       'facts':[],'chapter_passages':{'financial':rows},'market_evidence':[],'excerpts':[],
       'review_context_ids':ids[1:],'review_chapter_selection':{'financial':ids[1:]}}
    p['financial_ledger']=build_ledger(p)
    view=writer_view(p,'financial')
    assert [r['id'] for r in view['passages']]==ids[1:]
    assert p['chapter_passages']['financial']==rows
    p['cash_context_ids']=[ids[0]]
    with pytest.raises(ValueError,match='mandatory'):writer_view(p,'financial')


def test_full_context_not_misused_as_oversized_claim_quote():
    from app.dossier_compact_writer import schema_for
    rows=[{'id':'a','originalCharacterCount':1900},{'id':'b','originalCharacterCount':4000}]
    with pytest.raises(ValueError,match='Preflight'):schema_for({'passages':rows})
    rows.append({'id':'c','originalCharacterCount':500})
    schema=schema_for({'passages':rows})
    assert schema['properties']['claims']['items']['properties']['passage_id']['enum']==['a','c']
    assert schema['properties']['analysis']['properties']['support_ids']['items']['enum']==['a','b','c']
