import pytest
from app.dossier_evidence_selection import select


def test_actual_operations_and_named_dependencies_not_hidden_by_first_four():
    ps=[{'id':str(i),'text':'Inventory cost is computed from purchased semiconductors and manufacturing support costs.'} for i in range(4)]
    ps.extend([{'id':'foundry','text':'We depend on foundries such as Taiwan Semiconductor TSMC and do not own or operate a fab.'},
               {'id':'issue','text':'We recorded an additional net warranty charge for weak packaging materials.'},
               {'id':'yield','text':'Yield problems and limited access to wafer capacity can increase costs.'}])
    chosen,trace=select(ps,'supply')
    assert {p['id'] for p in chosen}=={'foundry','issue','yield','0'}
    assert len(trace)==4 and ps[0]['text'].startswith('Inventory')


def test_identical_prose_still_allows_minimum_distinct_source_ids():
    chosen,_=select([{'id':'a','text':'Same source prose.'},{'id':'b','text':'Same source prose.'}],'business')
    assert len(chosen)==2
    with pytest.raises(ValueError):select([{'id':'a','text':'one'},{'id':'a','text':'two'}],'business')


def test_negatives_remain_negative_when_comparison_improves(monkeypatch):
    import app.dossier_compact_writer as m
    monkeypatch.setattr(m,'chapter_packet',lambda *a:{'original_passages':[],'financial_ledger':{'comparisons':[]}})
    monkeypatch.setattr(m,'disclosed_reference_terms',lambda p:[])
    p={'ticker':'TEST','financial_ledger':{'comparisons':[{'concept':'NetIncomeLoss','periodType':'quarter','direction':'increase','current':{'value':-10},'previous':{'value':-20}}]}}
    v=m.writer_view(p,'financial')['coreFinancialObservations'][0]
    assert v['direction']=='increase' and v['currentSign']==v['comparisonSign']=='loss_or_negative'


def test_original_text_mode_does_not_hide_disclosed_amounts(monkeypatch):
    import app.dossier_compact_writer as m
    ps=[{'id':'p','text':'Revenue declined 40% in fiscal 2010.'},{'id':'q','text':'Cash flow was positive.'}]
    monkeypatch.setattr(m,'chapter_packet',lambda *a:{'original_passages':ps,'financial_ledger':{'comparisons':[]}})
    monkeypatch.setattr(m,'disclosed_reference_terms',lambda p:[])
    p={'ticker':'TEST','financial_ledger':{'comparisons':[]}}
    v=m.writer_view(p,'business',redact_numbers=False)
    assert not v['numbersRedacted'] and '40%' in v['passages'][0]['qualitative_view']
    assert v['passages'][0]['originalContainsQuantities'] and ps[0]['text'].endswith('2010.')


def test_cash_spans_remain_available_after_role_selection(monkeypatch):
    import app.dossier_compact_writer as m
    ps=[{'id':str(i),'text':f'Original unique business text {i}.'} for i in range(6)]
    monkeypatch.setattr(m,'chapter_packet',lambda *a:{'original_passages':ps[:4],'financial_ledger':{'comparisons':[]}})
    monkeypatch.setattr(m,'disclosed_reference_terms',lambda p:[])
    p={'ticker':'TEST','financial_ledger':{'comparisons':[]},'chapter_passages':{'financial':ps},'cash_context_ids':['5']}
    v=m.writer_view(p,'financial',redact_numbers=False)
    assert '5' in {x['id'] for x in v['passages']}


def test_citable_cash_span_must_match_original_offsets_and_hash():
    import hashlib
    from app.dossier_cash_context import validate_context
    text='prefix original cash table suffix';value=text[7:26]
    pid='PASSAGE:'+hashlib.sha256(('hash:7:'+value).encode()).hexdigest()[:16]
    c={'id':pid,'sourceHash':'hash','start':7,'end':26,'text':value}
    p={'raw_sha256':'hash','cash_context_ids':[pid],'chapter_passages':{'financial':[c]}}
    validate_context(p,text)
    c['text']='invented'
    with pytest.raises(ValueError):validate_context(p,text)
