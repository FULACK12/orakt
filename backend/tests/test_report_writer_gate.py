"""Successful legacy parsing must still run report-level review checks."""
import copy
import pytest
import app.dossier_compact_writer as writer
from app.financial_period_ledger import build_ledger


@pytest.fixture
def legacy_pass(monkeypatch):
    # Isolate the newly mandatory gate: even when earlier validators accept,
    # source/metric findings must stop the draft, without invoking a model.
    for name in ('validate_section','check_repetition','check_platform_names',
                 'check_cash_evidence_use','check_source_scope','check_claims'):
        monkeypatch.setattr(writer,name,lambda *a,**k:None)
    import app.dossier_semantic_guards as semantics
    monkeypatch.setattr(semantics,'guard_known_semantics',lambda *a,**k:None)
    ids=['PASSAGE:1111111111111111','PASSAGE:2222222222222222']
    sources=[{'id':ids[0],'text':'The company depends on third-party manufacturing capacity.'},
             {'id':ids[1],'text':'Delayed product qualification may cause missed customer design windows.'}]
    packet={'ticker':'TEST','filing_ref':'SEC:test','facts':[],'chapter_passages':{'business':sources},
            'as_of_date':'2026-08-05','period_end':'2026-06-27'}
    packet['financial_ledger']=build_ledger(packet)
    text={
        'analysis':('公司披露依赖第三方制造产能。','The company depends on external manufacturing capacity.'),
        'mechanism':('如果认证延迟，可能错过客户设计窗口。','If qualification is delayed, customer design windows may be missed.'),
        'counterEvidence':('若产品正常交付，风险未必实现。','If delivery is normal, the risk need not materialize.'),
        'evidenceGaps':('本次所选摘录未量化潜在风险。','Selected excerpts do not quantify the potential exposure.'),
        'validationPlan':('核查交付与认证进度以验证假设。','Check delivery and qualification progress to test the hypothesis.')}
    draft={k:{'zh':z,'en':e,'support_ids':ids} for k,(z,e) in text.items()}
    draft['claims']=[{'passage_id':ids[0],'statement':{'zh':'公司依赖第三方制造。','en':'The company depends on third-party manufacturing.'}},
                     {'passage_id':ids[1],'statement':{'zh':'认证延迟可能错过设计窗口。','en':'Qualification delays may cause missed design windows.'}}]
    view={'passages':[{'id':p['id'],'qualitative_view':p['text']} for p in sources]}
    return packet,draft,view


def test_clean_legacy_pass_remains_pending_not_semantically_approved(legacy_pass):
    packet,draft,view=legacy_pass
    section,_=writer.bind(draft,packet,'business',view)
    assert section.analysis.en.startswith('The company depends')


@pytest.mark.parametrize('bad,code',[
    ('Improved cash flow reflects operating efficiency.','narrative_result_source_mismatch'),
    ('The disclosed amount is [quantity].','placeholder'),
])
def test_report_findings_block_previously_successful_parse(legacy_pass,bad,code):
    packet,draft,view=legacy_pass
    draft=copy.deepcopy(draft);draft['analysis']['en']=bad
    with pytest.raises(ValueError,match=code):writer.bind(draft,packet,'business',view)
