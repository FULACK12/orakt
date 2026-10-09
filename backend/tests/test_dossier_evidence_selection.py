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


def test_latest_margin_and_segment_explanations_are_not_hidden_by_early_notes():
    ps=[{'id':str(i),'text':'The foreign currency forward contracts hedge operating expenses.'} for i in range(4)]
    ps += [{'id':'margin','text':'Gross margin increased from a year ago on improved product mix.'},
           {'id':'income','text':'Segment operating income increased, driven by revenue and the non-recurrence of a charge.'},
           {'id':'tax','text':'The effective tax rate increased primarily due to a lower percentage of tax benefits.'}]
    selected,_=select(ps,'financial')
    assert {'margin','income','tax'} <= {p['id'] for p in selected}


def test_identical_prose_still_allows_minimum_distinct_source_ids():
    chosen,_=select([{'id':'a','text':'Same source prose.'},{'id':'b','text':'Same source prose.'}],'business')
    assert len(chosen)==2
    with pytest.raises(ValueError):select([{'id':'a','text':'one'},{'id':'a','text':'two'}],'business')


def test_competitor_landscape_after_early_litigation_is_not_lost():
    ps=[{'id':str(i),'text':f'Patent complaint against subsidiary in jurisdiction {i}.'} for i in range(4)]
    ps += [{'id':'peers','text':'We face intense competition. Our competitors include Samsung and SK hynix.'},
           {'id':'pricing','text':'Cost innovation allows us to competitively price products.'},
           {'id':'deployment','text':'Awards depend on successful deployment of acquired technology.'},
           {'id':'ruling','text':'The appeals court affirmed that the patent was invalid.'}]
    chosen,trace=select(ps,'competition')
    assert {p['id'] for p in chosen}=={'peers','pricing','deployment','ruling'}
    assert trace[0]['reason']=='competitive_landscape'


def test_sole_sources_and_physical_inputs_are_not_hidden_by_risk_summary():
    ps=[{'id':str(i),'text':f'Risks include volatile prices and geopolitical issues {i}.'} for i in range(4)]
    ps += [{'id':'sole','text':'Only a limited number of suppliers qualify; some materials have a single or sole source.'},
           {'id':'yield','text':'Manufacturing yield and defect density affect cost.'},
           {'id':'utility','text':'Reliable supply of electrical power, gas and water is essential.'}]
    chosen,_=select(ps,'supply')
    assert {'sole','yield','utility'}<={p['id'] for p in chosen}


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


def test_aircraft_names_survive_redaction_but_amounts_do_not(monkeypatch):
    import app.dossier_compact_writer as m
    ps=[{'id':'a','text':'MQ-25 and T-7A cost $890 million in 2026.'},
        {'id':'b','text':'KC-46A and VC-25B remain development programs.'}]
    monkeypatch.setattr(m,'chapter_packet',lambda *a:{'original_passages':ps,'financial_ledger':{'comparisons':[]}})
    packet={'ticker':'BA','financial_ledger':{'comparisons':[]},'chapter_passages':{'competition':ps}}
    view=m.writer_view(packet,'competition')
    text=' '.join(p['qualitative_view'] for p in view['passages'])
    assert all(name in text for name in ['MQ-25','T-7A','KC-46A','VC-25B'])
    assert '890' not in text and '2026' not in text
    assert ps[0]['text']=='MQ-25 and T-7A cost $890 million in 2026.'


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
